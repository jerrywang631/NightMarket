"""Voucher Adventure session state and scoring."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets
import uuid

from .content import (
    SUPPORTED_CONTENT_VERSIONS,
    UNRELEASED_CONTENT_VERSIONS,
    VOUCHER_VALUE_CENTS,
    build_questions,
    calculate_prices,
    get_offer_definition,
    ordered_offer_definitions,
    select_variant_key,
)
from .errors import VoucherAPIError


DIFFICULTIES = {"easy", "medium", "hard"}
EVENT_TYPES = {
    "ENGLISH_SUPPORT_USED",
    "AUDIO_REPLAYED",
    "SESSION_STARTED",
    "SESSION_PAUSED",
    "SESSION_RESUMED",
    "TIMER_CHECKPOINT",
}
TIMER_TOLERANCE_MS = 15000


def utc_now():
    return datetime.now(timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).isoformat()


def parse_time(value, field_name="occurred_at"):
    if not isinstance(value, str) or not value.strip():
        raise VoucherAPIError(400, "INVALID_TIMESTAMP", f"{field_name} is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise VoucherAPIError(
            400, "INVALID_TIMESTAMP", f"{field_name} must be ISO-8601"
        ) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def prefixed_uuid(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def request_hash(payload):
    serialized = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class VoucherAdventureService:
    def __init__(
        self,
        repository,
        dialogue_manager=None,
        now_provider=utc_now,
        allow_unreleased=None,
        seed_provider=None,
    ):
        self.repository = repository
        self.dialogue_manager = dialogue_manager
        self.now_provider = now_provider
        self.allow_unreleased = bool(allow_unreleased)
        self.seed_provider = seed_provider or (lambda: secrets.randbelow(2**31))

    def _now(self):
        return self.now_provider().astimezone(timezone.utc)

    @staticmethod
    def _require_idempotency_key(idempotency_key):
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise VoucherAPIError(
                400, "IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key header is required"
            )
        if len(idempotency_key) > 200:
            raise VoucherAPIError(
                400, "INVALID_IDEMPOTENCY_KEY", "Idempotency-Key is too long"
            )
        return idempotency_key.strip()

    def _idempotent_begin(self, transaction, key, operation, payload):
        key = self._require_idempotency_key(key)
        self.repository.lock_key(transaction, f"idempotency:{key}")
        digest = request_hash(payload)
        existing = transaction.one(
            "SELECT * FROM voucher_idempotency WHERE idempotency_key = ?", (key,)
        )
        if not existing:
            return key, digest, None
        if existing["operation"] != operation or existing["request_hash"] != digest:
            raise VoucherAPIError(
                409,
                "IDEMPOTENCY_KEY_REUSED",
                "Idempotency-Key was already used for a different request",
            )
        return key, digest, (
            json.loads(existing["response_json"]),
            existing["response_status"],
        )

    def _idempotent_finish(
        self, transaction, key, operation, digest, response, status=200
    ):
        transaction.execute(
            """INSERT INTO voucher_idempotency
               (idempotency_key, operation, request_hash, response_status,
                response_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                key,
                operation,
                digest,
                status,
                json.dumps(response, ensure_ascii=False, separators=(",", ":")),
                iso(self._now()),
            ),
        )
        return response, status

    def _expire_sessions(self, transaction, now):
        transaction.execute(
            """UPDATE voucher_sessions
               SET status = 'EXPIRED', updated_at = ?
               WHERE status = 'ACTIVE' AND expires_at <= ?""",
            (iso(now), iso(now)),
        )

    @staticmethod
    def _session(transaction, session_id):
        session = transaction.one(
            "SELECT * FROM voucher_sessions WHERE session_id = ?", (session_id,)
        )
        if not session:
            raise VoucherAPIError(404, "SESSION_NOT_FOUND", "Voucher session not found")
        return session

    def _active_session(self, transaction, session_id, now):
        self._expire_sessions(transaction, now)
        session = self._session(transaction, session_id)
        if session["status"] != "ACTIVE":
            raise VoucherAPIError(
                409,
                "SESSION_NOT_ACTIVE",
                f"Session is {session['status'].lower()}",
                {"session_status": session["status"]},
            )
        return session

    def create_session(self, body, idempotency_key):
        body = body or {}
        player_id = body.get("player_id")
        difficulty = body.get("difficulty")
        content_version = body.get("content_version")
        if not isinstance(player_id, str) or not player_id.strip():
            raise VoucherAPIError(400, "PLAYER_ID_REQUIRED", "player_id is required")
        if difficulty not in DIFFICULTIES:
            raise VoucherAPIError(
                400, "INVALID_DIFFICULTY", "difficulty must be easy, medium, or hard"
            )
        version_supported = content_version in SUPPORTED_CONTENT_VERSIONS
        version_enabled_for_review = (
            self.allow_unreleased and content_version in UNRELEASED_CONTENT_VERSIONS
        )
        if not version_supported and not version_enabled_for_review:
            raise VoucherAPIError(
                400,
                "UNSUPPORTED_CONTENT_VERSION",
                "The requested content_version is not supported",
            )

        payload = {
            "player_id": player_id.strip(),
            "difficulty": difficulty,
            "content_version": content_version,
        }
        now = self._now()
        with self.repository.transaction() as transaction:
            key, digest, replay = self._idempotent_begin(
                transaction, idempotency_key, "CREATE_SESSION", payload
            )
            if replay:
                return replay
            self.repository.lock_key(
                transaction, f"active:{payload['player_id']}:{content_version}"
            )
            self._expire_sessions(transaction, now)
            active = transaction.one(
                """SELECT session_id FROM voucher_sessions
                   WHERE player_id = ? AND content_version = ? AND status = 'ACTIVE'""",
                (payload["player_id"], content_version),
            )
            if active:
                raise VoucherAPIError(
                    409,
                    "ACTIVE_SESSION_EXISTS",
                    "Complete or abandon the existing session before starting a new one",
                    {"session_id": active["session_id"]},
                )

            session_id = prefixed_uuid("va_session")
            seed = self.seed_provider()
            expires_at = now + timedelta(days=7)
            time_limit_ms = 90000 if difficulty == "hard" else None
            timer_state = "NOT_STARTED" if difficulty == "hard" else "NOT_APPLICABLE"
            transaction.execute(
                """INSERT INTO voucher_sessions
                   (session_id, player_id, content_version, difficulty, seed,
                    status, identity_mode, created_at, updated_at, expires_at,
                    timer_state, time_limit_ms, remaining_ms, basket_revision)
                   VALUES (?, ?, ?, ?, ?, 'ACTIVE', 'MVP/DEVELOPMENT_IDENTITY',
                           ?, ?, ?, ?, ?, ?, 0)""",
                (
                    session_id,
                    payload["player_id"],
                    content_version,
                    difficulty,
                    seed,
                    iso(now),
                    iso(now),
                    iso(expires_at),
                    timer_state,
                    time_limit_ms,
                    time_limit_ms,
                ),
            )

            offers = ordered_offer_definitions(content_version, seed)
            response_vendors = []
            selected_bundle_prices = []
            for display_order, offer in enumerate(offers):
                variant_key = select_variant_key(
                    content_version,
                    offer,
                    seed,
                    allow_unreleased=self.allow_unreleased,
                )
                if not variant_key:
                    raise VoucherAPIError(
                        500,
                        "NO_APPROVED_CONTENT",
                        f"No approved variant exists for {offer['offer_id']}",
                    )
                variant = offer["variants"][variant_key]
                _, _, bundle_price = calculate_prices(offer, variant_key)
                selected_bundle_prices.append(bundle_price)
                offer_instance_id = prefixed_uuid("voi")
                transaction.execute(
                    """INSERT INTO voucher_session_offers
                       (offer_instance_id, session_id, vendor_id, offer_id,
                        offer_type, dialogue_root_node_id, dialogue_offer_node_id,
                        ask_option_id, confirm_option_id, price_variant,
                        base_price_cents, bundle_size, bundle_price_cents,
                        parameters_json, label_en, label_han, content_status,
                        approved, display_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        offer_instance_id,
                        session_id,
                        offer["vendor_id"],
                        offer["offer_id"],
                        offer["offer_type"],
                        offer["root_node_id"],
                        offer["offer_node_id"],
                        offer["ask_option_id"],
                        offer["confirm_option_id"],
                        variant_key,
                        variant["base"],
                        offer["bundle_size"],
                        bundle_price,
                        json.dumps(offer["parameters"], separators=(",", ":")),
                        offer["label_en"],
                        offer["label_han"],
                        variant["status"],
                        1 if variant["approved"] else 0,
                        display_order,
                    ),
                )

                questions = build_questions(
                    offer, variant_key, content_version=content_version
                )
                if difficulty != "hard":
                    questions = [
                        question
                        for question in questions
                        if question["skill"] != "TRANSFER"
                    ]
                for question in questions:
                    transaction.execute(
                        """INSERT INTO voucher_session_questions
                           (question_instance_id, session_id, offer_instance_id,
                            skill, prompt_en, answer_unit, order_index,
                            correct_answer, rule_hint, formula_hint,
                            correct_feedback, misconceptions_json, source_variant)
                           VALUES (?, ?, ?, ?, ?, 'MONEY_CENTS', ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            prefixed_uuid("vqi"),
                            session_id,
                            offer_instance_id,
                            question["skill"],
                            question["prompt_en"],
                            question["order"],
                            question["answer"],
                            question["rule_hint"],
                            question["formula_hint"],
                            question["correct_feedback"],
                            json.dumps(
                                question["misconceptions"], separators=(",", ":")
                            ),
                            question.get("source_variant"),
                        ),
                    )
                response_vendors.append(
                    {
                        "vendor_id": offer["vendor_id"],
                        "offer_instance_id": offer_instance_id,
                        "dialogue_node_id": offer["root_node_id"],
                    }
                )

            vendor_target = {"easy": 0, "medium": 2, "hard": 3}[difficulty]
            target_bundle_total = sum(sorted(selected_bundle_prices)[:vendor_target])
            if (
                len(selected_bundle_prices) < vendor_target
                or target_bundle_total > VOUCHER_VALUE_CENTS
            ):
                raise VoucherAPIError(
                    500,
                    "SHOPPING_TARGET_UNREACHABLE",
                    "Generated offers cannot satisfy the Offer Explorer target",
                    {
                        "vendor_target": vendor_target,
                        "minimum_target_spend_cents": target_bundle_total,
                        "voucher_value_cents": VOUCHER_VALUE_CENTS,
                    },
                )
            response = {
                "session_id": session_id,
                "seed": seed,
                "content_version": content_version,
                "difficulty": difficulty,
                "identity_mode": "MVP/DEVELOPMENT_IDENTITY",
                "time_limit_seconds": 90 if difficulty == "hard" else None,
                "shopping_bonus": {
                    "vendor_target": vendor_target,
                    "required_for_completion": False,
                },
                "vendors": response_vendors,
            }
            return self._idempotent_finish(
                transaction, key, "CREATE_SESSION", digest, response, 201
            )

    @staticmethod
    def _question_public(question):
        return {
            "question_instance_id": question["question_instance_id"],
            "skill": question["skill"],
            "prompt_en": question["prompt_en"],
            "answer_unit": question["answer_unit"],
            "order": question["order_index"],
        }

    def _offer_public(self, transaction, offer, include_progress=True):
        questions = transaction.all(
            """SELECT * FROM voucher_session_questions
               WHERE offer_instance_id = ? ORDER BY order_index""",
            (offer["offer_instance_id"],),
        )
        data = {
            "offer_instance_id": offer["offer_instance_id"],
            "offer_id": offer["offer_id"],
            "vendor_id": offer["vendor_id"],
            "offer_type": offer["offer_type"],
            "base_price_cents": offer["base_price_cents"],
            "bundle_size": offer["bundle_size"],
            "parameters": json.loads(offer["parameters_json"]),
            "label_han": offer["label_han"],
            "label_en": offer["label_en"],
            "questions": [self._question_public(question) for question in questions],
        }
        if include_progress:
            data["progress"] = {
                "completed_question_ids": [
                    question["question_instance_id"]
                    for question in questions
                    if question["completed_at"]
                ],
                "current_question_instance_id": next(
                    (
                        question["question_instance_id"]
                        for question in questions
                        if not question["completed_at"]
                    ),
                    None,
                ),
            }
        if offer["resolved_at"]:
            data["offer_resolved"] = {
                "bundle_price_cents": offer["bundle_price_cents"],
                "effective_unit_price_cents": (
                    offer["bundle_price_cents"] // offer["bundle_size"]
                ),
            }
        return data

    def _apply_optional_checkpoint(self, transaction, session, body, now):
        if "remaining_ms" not in body or session["difficulty"] != "hard":
            return session
        submitted = body.get("remaining_ms")
        if not isinstance(submitted, int) or submitted < 0:
            raise VoucherAPIError(
                400,
                "INVALID_REMAINING_TIME",
                "remaining_ms must be a non-negative integer",
            )
        previous = session["remaining_ms"]
        server_estimated = previous
        if session["timer_state"] == "RUNNING" and session["last_checkpoint_at"]:
            elapsed_ms = max(
                0,
                int(
                    (
                        now
                        - parse_time(
                            session["last_checkpoint_at"], "last_checkpoint_at"
                        )
                    ).total_seconds()
                    * 1000
                ),
            )
            server_estimated = max(0, previous - elapsed_ms)
        # A delayed client request must never add time back to the clock.
        remaining = max(
            0, min(previous, submitted, server_estimated + TIMER_TOLERANCE_MS)
        )
        transaction.execute(
            """UPDATE voucher_sessions SET remaining_ms = ?, last_checkpoint_at = ?,
               updated_at = ? WHERE session_id = ?""",
            (remaining, iso(now), iso(now), session["session_id"]),
        )
        session["remaining_ms"] = remaining
        session["last_checkpoint_at"] = iso(now)
        return session

    def reveal_offer(self, session_id, offer_instance_id, body, idempotency_key):
        body = body or {}
        payload = {
            "session_id": session_id,
            "offer_instance_id": offer_instance_id,
            **body,
        }
        now = self._now()
        with self.repository.transaction() as transaction:
            key, digest, replay = self._idempotent_begin(
                transaction,
                idempotency_key,
                f"REVEAL:{session_id}:{offer_instance_id}",
                payload,
            )
            if replay:
                return replay
            session = self._active_session(transaction, session_id, now)
            offer = transaction.one(
                """SELECT * FROM voucher_session_offers
                   WHERE session_id = ? AND offer_instance_id = ?""",
                (session_id, offer_instance_id),
            )
            if not offer:
                raise VoucherAPIError(
                    404, "OFFER_NOT_FOUND", "Offer does not belong to this session"
                )
            if body.get("dialogue_node_id") != offer["dialogue_offer_node_id"]:
                raise VoucherAPIError(
                    400, "INVALID_REVEAL_NODE", "dialogue_node_id is not the offer node"
                )
            if body.get("option_id") != offer["confirm_option_id"]:
                raise VoucherAPIError(
                    400, "INVALID_REVEAL_OPTION", "option_id is not the reveal option"
                )
            if self.dialogue_manager:
                events = self.dialogue_manager.get_option_events(
                    offer["confirm_option_id"]
                )
                if not any(event[2] == "VOUCHER_OFFER_REVEALED" for event in events):
                    raise VoucherAPIError(
                        409,
                        "REVEAL_EVENT_NOT_CONFIGURED",
                        "The dialogue option does not contain the reveal event",
                    )
            self._apply_optional_checkpoint(transaction, session, body, now)
            if not offer["revealed_at"]:
                transaction.execute(
                    """UPDATE voucher_session_offers SET revealed_at = ?
                       WHERE offer_instance_id = ?""",
                    (iso(now), offer_instance_id),
                )
                transaction.execute(
                    """INSERT INTO voucher_session_events
                       (event_id, session_id, event_type, offer_instance_id,
                        dialogue_node_id, occurred_at, received_at, metadata_json, internal)
                       VALUES (?, ?, 'OFFER_REVEALED', ?, ?, ?, ?, ?, 1)""",
                    (
                        prefixed_uuid("vae"),
                        session_id,
                        offer_instance_id,
                        offer["dialogue_offer_node_id"],
                        iso(now),
                        iso(now),
                        "{}",
                    ),
                )
                offer["revealed_at"] = iso(now)
            response = self._offer_public(transaction, offer)
            response["revealed"] = True
            return self._idempotent_finish(
                transaction,
                key,
                f"REVEAL:{session_id}:{offer_instance_id}",
                digest,
                response,
            )

    @staticmethod
    def _feedback(question, difficulty, attempt_number, answer, content_version):
        if answer == question["correct_answer"]:
            return True, None, "CORRECT", question["correct_feedback"]
        misconceptions = json.loads(question["misconceptions_json"])
        misconception_data = misconceptions.get(str(answer))
        misconception = misconception_data[0] if misconception_data else None
        targeted = misconception_data[1] if misconception_data else None
        if difficulty == "hard":
            return False, misconception, "RETRY_ONLY", "Not quite. Try again."
        # Recognized misconceptions take precedence over generic staged hints.
        if content_version == "v1" and targeted:
            return False, misconception, "RULE_HINT", targeted
        if difficulty == "easy" and attempt_number >= 2:
            return False, misconception, "FORMULA_HINT", question["formula_hint"]
        return (
            False,
            misconception,
            "RULE_HINT",
            targeted or question["rule_hint"],
        )

    def submit_attempt(self, body, idempotency_key):
        body = body or {}
        required = (
            "session_id",
            "question_instance_id",
            "answer",
            "answer_unit",
            "attempt_number",
        )
        missing = [field for field in required if field not in body]
        if missing:
            raise VoucherAPIError(
                400,
                "MISSING_FIELDS",
                "Missing required attempt fields",
                {"fields": missing},
            )
        if not isinstance(body["answer"], int):
            raise VoucherAPIError(
                400, "INVALID_ANSWER", "answer must be an integer number of cents"
            )
        if not isinstance(body["attempt_number"], int) or body["attempt_number"] < 1:
            raise VoucherAPIError(
                400,
                "INVALID_ATTEMPT_NUMBER",
                "attempt_number must be a positive integer",
            )
        response_time_ms = body.get("response_time_ms", 0)
        if not isinstance(response_time_ms, int) or response_time_ms < 0:
            raise VoucherAPIError(
                400,
                "INVALID_RESPONSE_TIME",
                "response_time_ms must be a non-negative integer",
            )

        payload = dict(body)
        session_id = body["session_id"]
        question_id = body["question_instance_id"]
        operation = f"ATTEMPT:{session_id}:{question_id}:{body['attempt_number']}"
        now = self._now()
        with self.repository.transaction() as transaction:
            key, digest, replay = self._idempotent_begin(
                transaction, idempotency_key, operation, payload
            )
            if replay:
                return replay
            session = self._active_session(transaction, session_id, now)
            question = transaction.one(
                """SELECT q.*, o.revealed_at, o.resolved_at, o.bundle_price_cents,
                          o.bundle_size, o.offer_instance_id
                   FROM voucher_session_questions q
                   JOIN voucher_session_offers o
                     ON o.offer_instance_id = q.offer_instance_id
                   WHERE q.session_id = ? AND q.question_instance_id = ?""",
                (session_id, question_id),
            )
            if not question:
                raise VoucherAPIError(
                    404,
                    "QUESTION_NOT_FOUND",
                    "Question does not belong to this session",
                )
            if not question["revealed_at"]:
                raise VoucherAPIError(
                    409, "OFFER_NOT_REVEALED", "Reveal the offer before answering"
                )
            if question["completed_at"]:
                raise VoucherAPIError(
                    409, "QUESTION_ALREADY_COMPLETED", "Question was already completed"
                )
            current = transaction.one(
                """SELECT question_instance_id FROM voucher_session_questions
                   WHERE offer_instance_id = ? AND completed_at IS NULL
                   ORDER BY order_index LIMIT 1""",
                (question["offer_instance_id"],),
            )
            if not current or current["question_instance_id"] != question_id:
                raise VoucherAPIError(
                    409,
                    "QUESTION_NOT_AVAILABLE",
                    "Complete the preceding question first",
                    {
                        "current_question_instance_id": current["question_instance_id"]
                        if current
                        else None
                    },
                )
            expected_attempt = question["attempt_count"] + 1
            if body["attempt_number"] != expected_attempt:
                raise VoucherAPIError(
                    409,
                    "UNEXPECTED_ATTEMPT_NUMBER",
                    "attempt_number does not match the server state",
                    {"expected_attempt_number": expected_attempt},
                )
            if body["answer_unit"] != question["answer_unit"]:
                raise VoucherAPIError(
                    400,
                    "ANSWER_UNIT_MISMATCH",
                    "answer_unit does not match the question",
                )
            english_support = bool(body.get("english_support_used", False))
            if session["difficulty"] == "hard" and english_support:
                raise VoucherAPIError(
                    400,
                    "ENGLISH_SUPPORT_NOT_ALLOWED",
                    "English support is disabled in hard mode",
                )
            self._apply_optional_checkpoint(transaction, session, body, now)
            correct, misconception, feedback_level, feedback_en = self._feedback(
                question,
                session["difficulty"],
                body["attempt_number"],
                body["answer"],
                session["content_version"],
            )
            transaction.execute(
                """INSERT INTO voucher_attempts
                   (attempt_id, idempotency_key, session_id, question_instance_id,
                    attempt_number, answer, answer_unit, english_support_used,
                    response_time_ms, correct, misconception, feedback_level,
                    feedback_en, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    prefixed_uuid("vat"),
                    key,
                    session_id,
                    question_id,
                    body["attempt_number"],
                    body["answer"],
                    body["answer_unit"],
                    1 if english_support else 0,
                    response_time_ms,
                    1 if correct else 0,
                    misconception,
                    feedback_level,
                    feedback_en,
                    iso(now),
                ),
            )
            transaction.execute(
                """UPDATE voucher_session_questions
                   SET attempt_count = attempt_count + 1,
                       completed_at = ?, first_try_correct = ?
                   WHERE question_instance_id = ?""",
                (
                    iso(now) if correct else None,
                    (1 if body["attempt_number"] == 1 else 0) if correct else None,
                    question_id,
                ),
            )
            if english_support:
                transaction.execute(
                    """INSERT INTO voucher_session_events
                       (event_id, session_id, event_type, offer_instance_id,
                        occurred_at, received_at, metadata_json, internal)
                       VALUES (?, ?, 'ENGLISH_SUPPORT_USED', ?, ?, ?, '{}', 1)""",
                    (
                        prefixed_uuid("vae"),
                        session_id,
                        question["offer_instance_id"],
                        iso(now),
                        iso(now),
                    ),
                )

            next_question_id = None
            offer_resolved = None
            if correct:
                next_question = transaction.one(
                    """SELECT question_instance_id FROM voucher_session_questions
                       WHERE offer_instance_id = ? AND completed_at IS NULL
                       ORDER BY order_index LIMIT 1""",
                    (question["offer_instance_id"],),
                )
                next_question_id = (
                    next_question["question_instance_id"] if next_question else None
                )
                if not next_question:
                    transaction.execute(
                        """UPDATE voucher_session_offers SET resolved_at = ?
                           WHERE offer_instance_id = ?""",
                        (iso(now), question["offer_instance_id"]),
                    )
                    offer_resolved = {
                        "bundle_price_cents": question["bundle_price_cents"],
                        "effective_unit_price_cents": (
                            question["bundle_price_cents"] // question["bundle_size"]
                        ),
                    }
            response = {
                "correct": correct,
                "misconception": misconception,
                "feedback_level": feedback_level,
                "feedback_en": feedback_en,
                "next_question_instance_id": next_question_id,
            }
            if offer_resolved:
                response["offer_resolved"] = offer_resolved
            return self._idempotent_finish(
                transaction, key, operation, digest, response
            )

    @staticmethod
    def _basket_data(transaction, session):
        items = transaction.all(
            """SELECT b.offer_instance_id, o.vendor_id, o.offer_id,
                      b.quantity, b.spent_cents
               FROM voucher_basket_items b
               JOIN voucher_session_offers o
                 ON o.offer_instance_id = b.offer_instance_id
               WHERE b.session_id = ? ORDER BY o.display_order""",
            (session["session_id"],),
        )
        spent = sum(item["spent_cents"] for item in items)
        return {
            "client_revision": session["basket_revision"],
            "items": items,
            "spent_cents": spent,
            "remaining_cents": VOUCHER_VALUE_CENTS - spent,
        }

    def update_basket(self, session_id, body, idempotency_key):
        body = body or {}
        revision = body.get("client_revision")
        items = body.get("items")
        if not isinstance(revision, int) or revision < 1:
            raise VoucherAPIError(
                400,
                "INVALID_BASKET_REVISION",
                "client_revision must be a positive integer",
            )
        if not isinstance(items, list):
            raise VoucherAPIError(400, "INVALID_BASKET", "items must be an array")
        payload = {"session_id": session_id, **body}
        operation = f"BASKET:{session_id}:{revision}"
        now = self._now()
        with self.repository.transaction() as transaction:
            key, digest, replay = self._idempotent_begin(
                transaction, idempotency_key, operation, payload
            )
            if replay:
                return replay
            session = self._active_session(transaction, session_id, now)
            current_revision = session["basket_revision"]
            if revision <= current_revision:
                raise VoucherAPIError(
                    409,
                    "STALE_BASKET_REVISION",
                    "A newer Basket snapshot already exists",
                    {"current_basket_revision": current_revision},
                )
            if revision != current_revision + 1:
                raise VoucherAPIError(
                    409,
                    "UNEXPECTED_BASKET_REVISION",
                    "Basket revisions must increase by one",
                    {"expected_basket_revision": current_revision + 1},
                )
            self._apply_optional_checkpoint(transaction, session, body, now)
            calculated = []
            seen = set()
            total = 0
            for item in items:
                if not isinstance(item, dict):
                    raise VoucherAPIError(
                        400, "INVALID_BASKET_ITEM", "Each Basket item must be an object"
                    )
                offer_instance_id = item.get("offer_instance_id")
                quantity = item.get("quantity")
                if offer_instance_id in seen:
                    raise VoucherAPIError(
                        400,
                        "DUPLICATE_BASKET_ITEM",
                        "Basket contains a duplicate offer",
                    )
                seen.add(offer_instance_id)
                if not isinstance(quantity, int) or quantity < 1:
                    raise VoucherAPIError(
                        400,
                        "INVALID_QUANTITY",
                        "quantity must be a positive integer",
                    )
                offer = transaction.one(
                    """SELECT * FROM voucher_session_offers
                       WHERE session_id = ? AND offer_instance_id = ?""",
                    (session_id, offer_instance_id),
                )
                if not offer:
                    raise VoucherAPIError(
                        400,
                        "INVALID_BASKET_OFFER",
                        "Offer does not belong to the session",
                    )
                if not offer["resolved_at"]:
                    raise VoucherAPIError(
                        409,
                        "OFFER_NOT_RESOLVED",
                        "Complete the offer questions before purchasing",
                    )
                if quantity != offer["bundle_size"]:
                    raise VoucherAPIError(
                        400,
                        "INVALID_BUNDLE_QUANTITY",
                        "quantity must equal bundle_size; each offer may be purchased once",
                        {"bundle_size": offer["bundle_size"]},
                    )
                spent = offer["bundle_price_cents"]
                total += spent
                calculated.append((offer_instance_id, quantity, spent))
            if total > VOUCHER_VALUE_CENTS:
                voucher_dollars = f"{VOUCHER_VALUE_CENTS / 100:g}"
                raise VoucherAPIError(
                    409,
                    "VOUCHER_LIMIT_EXCEEDED",
                    f"Basket exceeds the ${voucher_dollars} voucher",
                    {"spent_cents": total, "voucher_value_cents": VOUCHER_VALUE_CENTS},
                )
            transaction.execute(
                "DELETE FROM voucher_basket_items WHERE session_id = ?", (session_id,)
            )
            if calculated:
                transaction.many(
                    """INSERT INTO voucher_basket_items
                       (session_id, offer_instance_id, quantity, spent_cents)
                       VALUES (?, ?, ?, ?)""",
                    [(session_id, *item) for item in calculated],
                )
            transaction.execute(
                """UPDATE voucher_sessions SET basket_revision = ?, updated_at = ?
                   WHERE session_id = ?""",
                (revision, iso(now), session_id),
            )
            session["basket_revision"] = revision
            response = self._basket_data(transaction, session)
            return self._idempotent_finish(
                transaction, key, operation, digest, response
            )

    def _timer_event(
        self, transaction, session, event_type, occurred_at, metadata, now
    ):
        if session["difficulty"] != "hard":
            return {"state": "NOT_APPLICABLE", "remaining_ms": None, "accepted": True}
        previous_client_time = session["timer_client_event_at"]
        if previous_client_time and occurred_at <= parse_time(
            previous_client_time, "timer_client_event_at"
        ):
            return {
                "state": session["timer_state"],
                "remaining_ms": session["remaining_ms"],
                "accepted": False,
                "reason": "STALE_TIMER_EVENT",
            }
        state = session["timer_state"]
        remaining = session["remaining_ms"]
        submitted = metadata.get("remaining_ms")
        if submitted is not None and (not isinstance(submitted, int) or submitted < 0):
            raise VoucherAPIError(
                400,
                "INVALID_REMAINING_TIME",
                "metadata.remaining_ms must be a non-negative integer",
            )

        previous_state = state
        server_estimated = remaining
        if previous_state == "RUNNING" and session["last_checkpoint_at"]:
            elapsed_ms = max(
                0,
                int(
                    (
                        now
                        - parse_time(
                            session["last_checkpoint_at"], "last_checkpoint_at"
                        )
                    ).total_seconds()
                    * 1000
                ),
            )
            server_estimated = max(0, remaining - elapsed_ms)

        if event_type == "SESSION_STARTED":
            if state == "NOT_STARTED":
                state = "RUNNING"
        elif event_type == "SESSION_PAUSED":
            state = "PAUSED"
        elif event_type == "SESSION_RESUMED":
            state = "RUNNING"
        elif event_type == "TIMER_CHECKPOINT" and state == "NOT_STARTED":
            raise VoucherAPIError(
                409, "TIMER_NOT_STARTED", "Send SESSION_STARTED before a checkpoint"
            )

        if submitted is not None:
            remaining = max(
                0,
                min(remaining, submitted, server_estimated + TIMER_TOLERANCE_MS),
            )
        elif previous_state == "RUNNING" and event_type in (
            "SESSION_PAUSED",
            "TIMER_CHECKPOINT",
        ):
            remaining = server_estimated
        transaction.execute(
            """UPDATE voucher_sessions
               SET timer_state = ?, remaining_ms = ?, timer_client_event_at = ?,
                   last_checkpoint_at = ?, updated_at = ?
               WHERE session_id = ?""",
            (
                state,
                remaining,
                iso(occurred_at),
                iso(now),
                iso(now),
                session["session_id"],
            ),
        )
        session["timer_state"] = state
        session["remaining_ms"] = remaining
        session["timer_client_event_at"] = iso(occurred_at)
        session["last_checkpoint_at"] = iso(now)
        return {"state": state, "remaining_ms": remaining, "accepted": True}

    def record_event(self, session_id, body, idempotency_key):
        body = body or {}
        event_id = body.get("event_id")
        event_type = body.get("event_type")
        if not isinstance(event_id, str) or not event_id.strip():
            raise VoucherAPIError(400, "EVENT_ID_REQUIRED", "event_id is required")
        if event_type not in EVENT_TYPES:
            raise VoucherAPIError(
                400, "INVALID_EVENT_TYPE", "Unsupported Voucher Adventure event_type"
            )
        occurred_at = parse_time(body.get("occurred_at"))
        metadata = body.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise VoucherAPIError(
                400, "INVALID_EVENT_METADATA", "metadata must be an object"
            )
        payload = {"session_id": session_id, **body}
        operation = f"EVENT:{session_id}:{event_id}"
        now = self._now()
        with self.repository.transaction() as transaction:
            key, digest, replay = self._idempotent_begin(
                transaction, idempotency_key, operation, payload
            )
            if replay:
                return replay
            session = self._active_session(transaction, session_id, now)
            if transaction.one(
                "SELECT event_id FROM voucher_session_events WHERE event_id = ?",
                (event_id,),
            ):
                raise VoucherAPIError(
                    409, "DUPLICATE_EVENT_ID", "event_id already exists"
                )
            offer_instance_id = body.get("offer_instance_id")
            if offer_instance_id:
                offer = transaction.one(
                    """SELECT offer_instance_id FROM voucher_session_offers
                       WHERE session_id = ? AND offer_instance_id = ?""",
                    (session_id, offer_instance_id),
                )
                if not offer:
                    raise VoucherAPIError(
                        400,
                        "INVALID_EVENT_OFFER",
                        "Offer does not belong to the session",
                    )
            if event_type == "ENGLISH_SUPPORT_USED":
                if not offer_instance_id:
                    raise VoucherAPIError(
                        400, "OFFER_ID_REQUIRED", "offer_instance_id is required"
                    )
                if session["difficulty"] == "hard":
                    raise VoucherAPIError(
                        400,
                        "ENGLISH_SUPPORT_NOT_ALLOWED",
                        "English support is disabled in hard mode",
                    )
            timer = None
            if event_type.startswith("SESSION_") or event_type == "TIMER_CHECKPOINT":
                timer = self._timer_event(
                    transaction, session, event_type, occurred_at, metadata, now
                )
            transaction.execute(
                """INSERT INTO voucher_session_events
                   (event_id, idempotency_key, session_id, event_type,
                    offer_instance_id, dialogue_node_id, occurred_at,
                    received_at, metadata_json, internal)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                (
                    event_id,
                    key,
                    session_id,
                    event_type,
                    offer_instance_id,
                    body.get("dialogue_node_id"),
                    iso(occurred_at),
                    iso(now),
                    json.dumps(metadata, separators=(",", ":")),
                ),
            )
            response = {"event_id": event_id, "recorded": True}
            if timer:
                response["timer"] = timer
            return self._idempotent_finish(
                transaction, key, operation, digest, response
            )

    def _completion_summary(self, transaction, session):
        questions = transaction.all(
            "SELECT * FROM voucher_session_questions WHERE session_id = ?",
            (session["session_id"],),
        )
        learning = {}
        for skill, prefix in (
            ("RULE_MEANING", "rule"),
            ("PRICE_CALCULATION", "price"),
            ("TRANSFER", "transfer"),
        ):
            selected = [
                question for question in questions if question["skill"] == skill
            ]
            learning[f"{prefix}_completed"] = sum(
                1 for question in selected if question["completed_at"]
            )
            learning[f"{prefix}_first_try"] = sum(
                1 for question in selected if question["first_try_correct"] == 1
            )
        english = transaction.one(
            """SELECT COUNT(DISTINCT offer_instance_id) AS count
               FROM voucher_session_events
               WHERE session_id = ? AND event_type = 'ENGLISH_SUPPORT_USED'""",
            (session["session_id"],),
        )
        learning["english_support_vendor_count"] = english["count"]

        basket = self._basket_data(transaction, session)
        purchased_vendor_count = len({item["vendor_id"] for item in basket["items"]})
        vendor_target = {"easy": 0, "medium": 2, "hard": 3}[session["difficulty"]]
        speed_completed = (
            session["difficulty"] == "hard"
            and session["timer_state"] != "NOT_STARTED"
            and session["remaining_ms"] is not None
            and session["remaining_ms"] > 0
        )
        shopping = {
            "spent_cents": basket["spent_cents"],
            "remaining_cents": basket["remaining_cents"],
            "purchased_vendor_count": purchased_vendor_count,
            "vendor_target": vendor_target,
            "vendor_target_completed": vendor_target == 0
            or purchased_vendor_count >= vendor_target,
            "speed_bonus_completed": speed_completed,
        }
        return learning, shopping, basket

    def complete_session(self, session_id, body, idempotency_key):
        body = body or {}
        revision = body.get("basket_revision")
        if not isinstance(revision, int) or revision < 0:
            raise VoucherAPIError(
                400,
                "INVALID_BASKET_REVISION",
                "basket_revision must be a non-negative integer",
            )
        payload = {"session_id": session_id, "basket_revision": revision}
        operation = f"COMPLETE:{session_id}"
        now = self._now()
        with self.repository.transaction() as transaction:
            key, digest, replay = self._idempotent_begin(
                transaction, idempotency_key, operation, payload
            )
            if replay:
                return replay
            session = self._session(transaction, session_id)
            if session["status"] not in ("ACTIVE", "COMPLETED"):
                raise VoucherAPIError(
                    409, "SESSION_NOT_ACTIVE", "Session cannot be completed"
                )
            if revision != session["basket_revision"]:
                raise VoucherAPIError(
                    409,
                    "STALE_BASKET_REVISION",
                    "Complete request does not reference the current Basket",
                    {"current_basket_revision": session["basket_revision"]},
                )
            if (
                session["difficulty"] == "hard"
                and session["timer_state"] == "RUNNING"
                and session["last_checkpoint_at"]
            ):
                elapsed_ms = max(
                    0,
                    int(
                        (
                            now
                            - parse_time(
                                session["last_checkpoint_at"], "last_checkpoint_at"
                            )
                        ).total_seconds()
                        * 1000
                    ),
                )
                session["remaining_ms"] = max(0, session["remaining_ms"] - elapsed_ms)
                transaction.execute(
                    """UPDATE voucher_sessions
                       SET remaining_ms = ?, last_checkpoint_at = ?, updated_at = ?
                       WHERE session_id = ?""",
                    (
                        session["remaining_ms"],
                        iso(now),
                        iso(now),
                        session_id,
                    ),
                )
            remaining = transaction.all(
                """SELECT question_instance_id FROM voucher_session_questions
                   WHERE session_id = ? AND completed_at IS NULL
                   ORDER BY question_instance_id""",
                (session_id,),
            )
            if remaining:
                raise VoucherAPIError(
                    409,
                    "LEARNING_INCOMPLETE",
                    "Complete all learning questions first",
                    {
                        "remaining_question_ids": [
                            row["question_instance_id"] for row in remaining
                        ]
                    },
                )
            if session["status"] == "ACTIVE":
                transaction.execute(
                    """UPDATE voucher_sessions
                       SET status = 'COMPLETED', completed_at = ?, updated_at = ?
                       WHERE session_id = ?""",
                    (iso(now), iso(now), session_id),
                )
                session["status"] = "COMPLETED"
                session["completed_at"] = iso(now)
            learning, shopping, basket = self._completion_summary(transaction, session)
            response = {
                "session_id": session_id,
                "session_status": "COMPLETED",
                "learning": learning,
                "shopping": shopping,
                "basket": basket["items"],
            }
            return self._idempotent_finish(
                transaction, key, operation, digest, response
            )

    def abandon_session(self, session_id, body, idempotency_key):
        payload = {"session_id": session_id, **(body or {})}
        operation = f"ABANDON:{session_id}"
        now = self._now()
        with self.repository.transaction() as transaction:
            key, digest, replay = self._idempotent_begin(
                transaction, idempotency_key, operation, payload
            )
            if replay:
                return replay
            session = self._session(transaction, session_id)
            if session["status"] == "COMPLETED":
                raise VoucherAPIError(
                    409, "SESSION_COMPLETED", "A completed session cannot be abandoned"
                )
            if session["status"] == "ACTIVE":
                transaction.execute(
                    """UPDATE voucher_sessions
                       SET status = 'ABANDONED', abandoned_at = ?, updated_at = ?
                       WHERE session_id = ?""",
                    (iso(now), iso(now), session_id),
                )
            response = {"session_id": session_id, "session_status": "ABANDONED"}
            return self._idempotent_finish(
                transaction, key, operation, digest, response
            )

    def get_session(self, session_id):
        now = self._now()
        with self.repository.transaction() as transaction:
            self._expire_sessions(transaction, now)
            session = self._session(transaction, session_id)
            offers = transaction.all(
                """SELECT * FROM voucher_session_offers
                   WHERE session_id = ? ORDER BY display_order""",
                (session_id,),
            )
            vendor_data = []
            for offer in offers:
                vendor = {
                    "vendor_id": offer["vendor_id"],
                    "offer_instance_id": offer["offer_instance_id"],
                    "dialogue_node_id": offer["dialogue_root_node_id"],
                    "revealed": bool(offer["revealed_at"]),
                    "completed": bool(offer["resolved_at"]),
                }
                if offer["revealed_at"]:
                    vendor["offer"] = self._offer_public(transaction, offer)
                vendor_data.append(vendor)
            attempt_rows = transaction.all(
                """SELECT a.question_instance_id, a.attempt_number, a.answer,
                          a.answer_unit, a.english_support_used,
                          a.response_time_ms, a.correct, a.misconception,
                          a.feedback_level, a.feedback_en, a.created_at,
                          q.completed_at AS question_completed_at
                   FROM voucher_attempts a
                   JOIN voucher_session_questions q
                     ON q.question_instance_id = a.question_instance_id
                   WHERE a.session_id = ?
                   ORDER BY a.created_at, a.attempt_number""",
                (session_id,),
            )
            attempts = []
            for attempt in attempt_rows:
                restored = {
                    "question_instance_id": attempt["question_instance_id"],
                    "attempt_number": attempt["attempt_number"],
                    "correct": bool(attempt["correct"]),
                    "misconception": attempt["misconception"],
                    "feedback_level": attempt["feedback_level"],
                    "english_support_used": bool(attempt["english_support_used"]),
                    "response_time_ms": attempt["response_time_ms"],
                    "created_at": attempt["created_at"],
                }
                if attempt["question_completed_at"]:
                    # Hide answer history until the question is resolved.
                    restored.update(
                        {
                            "answer": attempt["answer"],
                            "answer_unit": attempt["answer_unit"],
                            "feedback_en": attempt["feedback_en"],
                        }
                    )
                attempts.append(restored)
            basket = self._basket_data(transaction, session)
            event_summary = transaction.one(
                """SELECT
                       SUM(CASE WHEN event_type = 'AUDIO_REPLAYED' THEN 1 ELSE 0 END)
                           AS audio_replay_count,
                       COUNT(DISTINCT CASE WHEN event_type = 'ENGLISH_SUPPORT_USED'
                                           THEN offer_instance_id END)
                           AS english_support_vendor_count
                   FROM voucher_session_events WHERE session_id = ?""",
                (session_id,),
            )
            response = {
                "session_id": session_id,
                "player_id": session["player_id"],
                "content_version": session["content_version"],
                "difficulty": session["difficulty"],
                "session_status": session["status"],
                "identity_mode": session["identity_mode"],
                "seed": session["seed"],
                "expires_at": session["expires_at"],
                "timer": {
                    "state": session["timer_state"],
                    "time_limit_ms": session["time_limit_ms"],
                    "remaining_ms": session["remaining_ms"],
                    "last_checkpoint_at": session["last_checkpoint_at"],
                },
                "vendors": vendor_data,
                "attempts": attempts,
                "basket": basket,
                "help_usage": {
                    "english_support_vendor_count": event_summary[
                        "english_support_vendor_count"
                    ]
                    or 0,
                    "audio_replay_count": event_summary["audio_replay_count"] or 0,
                },
            }
            if session["status"] == "COMPLETED":
                learning, shopping, _ = self._completion_summary(transaction, session)
                response["result"] = {"learning": learning, "shopping": shopping}
            return response, 200

    def render_dialogue(self, session_id, node_id, base_node):
        with self.repository.transaction() as transaction:
            session = self._session(transaction, session_id)
            if session["status"] in ("ABANDONED", "EXPIRED"):
                raise VoucherAPIError(
                    409, "SESSION_NOT_ACTIVE", "Session cannot render dynamic dialogue"
                )
            offer = transaction.one(
                """SELECT * FROM voucher_session_offers
                   WHERE session_id = ?
                     AND (dialogue_root_node_id = ? OR dialogue_offer_node_id = ?)""",
                (session_id, node_id, node_id),
            )
            if not offer:
                raise VoucherAPIError(
                    404,
                    "DIALOGUE_NOT_IN_SESSION",
                    "Dialogue node is not part of this session",
                )
            definition = get_offer_definition(
                session["content_version"], offer["offer_id"]
            )
            variant = offer["price_variant"]
            if node_id == offer["dialogue_root_node_id"]:
                text, han, poj = definition["greet"][variant]
            else:
                text, han, poj = definition["offer_dialogue"]
            base_node["dialogue"]["text"] = text
            base_node["dialogue"]["translation_HAN"] = han
            base_node["dialogue"]["translation_POJ"] = poj
            if node_id == offer["dialogue_root_node_id"] and variant != "A":
                base_node["dialogue"]["audio"] = f"/audio-clips/{node_id}_{variant}.wav"
            else:
                base_node["dialogue"]["audio"] = f"/audio-clips/{node_id}.wav"
            if node_id == offer["dialogue_offer_node_id"]:
                metadata = json.dumps(
                    {
                        "session_id": session_id,
                        "offer_instance_id": offer["offer_instance_id"],
                        "vendor_id": offer["vendor_id"],
                        "offer_id": offer["offer_id"],
                    },
                    separators=(",", ":"),
                )
                for option in base_node.get("options", []):
                    if option.get("option_id") != offer["confirm_option_id"]:
                        continue
                    for event in option.get("events", []):
                        if event.get("event_type") == "VOUCHER_OFFER_REVEALED":
                            event["metadata"] = metadata
            return base_node
