"""Authoritative Voucher Adventure session behavior."""

from datetime import datetime, timedelta, timezone
import json

import pytest

from voucher_adventure.content import content_catalog
from voucher_adventure.repository import create_voucher_repository
from voucher_adventure.service import VoucherAdventureService, VoucherAPIError


@pytest.fixture
def voucher_service(tmp_path):
    repository = create_voucher_repository(
        database_url=None, sqlite_path=str(tmp_path / "voucher_sessions.db")
    )
    return VoucherAdventureService(repository)


def create_session(service, difficulty="easy", key="create-1", player="player-1"):
    return service.create_session(
        {
            "player_id": player,
            "difficulty": difficulty,
            "content_version": "v1",
        },
        key,
    )


def reveal(service, session, vendor, key="reveal-1"):
    offer = service.repository.fetch_one(
        "SELECT * FROM voucher_session_offers WHERE offer_instance_id = ?",
        (vendor["offer_instance_id"],),
    )
    return service.reveal_offer(
        session["session_id"],
        vendor["offer_instance_id"],
        {
            "dialogue_node_id": offer["dialogue_offer_node_id"],
            "option_id": offer["confirm_option_id"],
        },
        key,
    )


def answer_current_question(service, session_id, offer_instance_id, key_prefix):
    question = service.repository.fetch_one(
        """SELECT * FROM voucher_session_questions
           WHERE offer_instance_id = ? AND completed_at IS NULL
           ORDER BY order_index LIMIT 1""",
        (offer_instance_id,),
    )
    response, status = service.submit_attempt(
        {
            "session_id": session_id,
            "question_instance_id": question["question_instance_id"],
            "answer": question["correct_answer"],
            "answer_unit": "MONEY_CENTS",
            "attempt_number": question["attempt_count"] + 1,
            "english_support_used": False,
            "response_time_ms": 1000,
        },
        f"{key_prefix}-{question['question_instance_id']}",
    )
    return response, status


def solve_offer(service, session_id, offer_instance_id, key_prefix):
    last_response = None
    while service.repository.fetch_one(
        """SELECT question_instance_id FROM voucher_session_questions
           WHERE offer_instance_id = ? AND completed_at IS NULL LIMIT 1""",
        (offer_instance_id,),
    ):
        last_response, _ = answer_current_question(
            service, session_id, offer_instance_id, key_prefix
        )
    return last_response


def test_catalog_contains_45_questions_and_all_variants_are_selectable():
    catalog = content_catalog()
    assert len(catalog) == 15
    assert sum(len(item["questions"]) for item in catalog) == 45
    selectable = [item for item in catalog if item["selectable_for_session"]]
    assert len(selectable) == 15
    assert {item["variant"] for item in selectable} == {"A", "B", "C"}
    assert all(item["content_status"] == "APPROVED" for item in catalog)


def test_create_is_idempotent_and_prevents_second_active_session(voucher_service):
    first, status = create_session(voucher_service)
    replay, replay_status = create_session(voucher_service)
    assert status == replay_status == 201
    assert first == replay
    assert len(first["vendors"]) == 5
    assert first["identity_mode"] == "MVP/DEVELOPMENT_IDENTITY"

    with pytest.raises(VoucherAPIError) as error:
        create_session(voucher_service, key="create-2")
    assert error.value.status == 409
    assert error.value.code == "ACTIVE_SESSION_EXISTS"


def test_reveal_returns_questions_without_price_answer(voucher_service):
    session, _ = create_session(voucher_service)
    vendor = session["vendors"][0]
    revealed, status = reveal(voucher_service, session, vendor)
    assert status == 200
    assert revealed["revealed"] is True
    assert "bundle_price_cents" not in revealed
    assert "effective_unit_price_cents" not in revealed
    assert len(revealed["questions"]) == 2
    for question in revealed["questions"]:
        assert "answer" not in question
        assert "formula_hint" not in question
        assert "correct_feedback" not in question


def test_attempt_feedback_progression_and_answer_release(voucher_service):
    session, _ = create_session(voucher_service)
    vendor = session["vendors"][0]
    revealed, _ = reveal(voucher_service, session, vendor)
    first_question = revealed["questions"][0]
    correct_answer = voucher_service.repository.fetch_one(
        """SELECT correct_answer FROM voucher_session_questions
           WHERE question_instance_id = ?""",
        (first_question["question_instance_id"],),
    )["correct_answer"]

    wrong, _ = voucher_service.submit_attempt(
        {
            "session_id": session["session_id"],
            "question_instance_id": first_question["question_instance_id"],
            "answer": correct_answer + 1,
            "answer_unit": "MONEY_CENTS",
            "attempt_number": 1,
            "english_support_used": False,
            "response_time_ms": 100,
        },
        "attempt-wrong-1",
    )
    assert wrong["correct"] is False
    assert wrong["feedback_level"] == "RULE_HINT"
    assert "offer_resolved" not in wrong

    second_wrong, _ = voucher_service.submit_attempt(
        {
            "session_id": session["session_id"],
            "question_instance_id": first_question["question_instance_id"],
            "answer": correct_answer + 2,
            "answer_unit": "MONEY_CENTS",
            "attempt_number": 2,
            "english_support_used": False,
            "response_time_ms": 100,
        },
        "attempt-wrong-2",
    )
    assert second_wrong["feedback_level"] == "FORMULA_HINT"

    correct, _ = voucher_service.submit_attempt(
        {
            "session_id": session["session_id"],
            "question_instance_id": first_question["question_instance_id"],
            "answer": correct_answer,
            "answer_unit": "MONEY_CENTS",
            "attempt_number": 3,
            "english_support_used": False,
            "response_time_ms": 100,
        },
        "attempt-correct-3",
    )
    assert correct["correct"] is True
    assert correct["next_question_instance_id"] is not None
    assert "offer_resolved" not in correct

    final = solve_offer(
        voucher_service,
        session["session_id"],
        vendor["offer_instance_id"],
        "solve-final",
    )
    assert final["offer_resolved"]["bundle_price_cents"] > 0


def test_attempt_number_conflict_returns_expected_number(voucher_service):
    session, _ = create_session(voucher_service)
    vendor = session["vendors"][0]
    revealed, _ = reveal(voucher_service, session, vendor)
    question = revealed["questions"][0]
    with pytest.raises(VoucherAPIError) as error:
        voucher_service.submit_attempt(
            {
                "session_id": session["session_id"],
                "question_instance_id": question["question_instance_id"],
                "answer": 0,
                "answer_unit": "MONEY_CENTS",
                "attempt_number": 2,
                "english_support_used": False,
                "response_time_ms": 0,
            },
            "attempt-skipped",
        )
    assert error.value.status == 409
    assert error.value.details["expected_attempt_number"] == 1


def test_successful_attempt_replays_with_same_idempotency_key(voucher_service):
    session, _ = create_session(voucher_service)
    vendor = session["vendors"][0]
    revealed, _ = reveal(voucher_service, session, vendor)
    question_id = revealed["questions"][0]["question_instance_id"]
    answer = voucher_service.repository.fetch_one(
        "SELECT correct_answer FROM voucher_session_questions WHERE question_instance_id = ?",
        (question_id,),
    )["correct_answer"]
    body = {
        "session_id": session["session_id"],
        "question_instance_id": question_id,
        "answer": answer,
        "answer_unit": "MONEY_CENTS",
        "attempt_number": 1,
        "english_support_used": False,
        "response_time_ms": 100,
    }
    first = voucher_service.submit_attempt(body, "attempt-replay-key")
    replay = voucher_service.submit_attempt(body, "attempt-replay-key")
    assert replay == first
    count = voucher_service.repository.fetch_one(
        "SELECT COUNT(*) AS count FROM voucher_attempts WHERE question_instance_id = ?",
        (question_id,),
    )["count"]
    assert count == 1


def test_hard_mode_rejects_english_support(voucher_service):
    session, _ = create_session(voucher_service, difficulty="hard")
    vendor = session["vendors"][0]
    revealed, _ = reveal(voucher_service, session, vendor)
    question = voucher_service.repository.fetch_one(
        "SELECT * FROM voucher_session_questions WHERE question_instance_id = ?",
        (revealed["questions"][0]["question_instance_id"],),
    )
    with pytest.raises(VoucherAPIError) as error:
        voucher_service.submit_attempt(
            {
                "session_id": session["session_id"],
                "question_instance_id": question["question_instance_id"],
                "answer": question["correct_answer"],
                "answer_unit": "MONEY_CENTS",
                "attempt_number": 1,
                "english_support_used": True,
                "response_time_ms": 100,
            },
            "hard-english",
        )
    assert error.value.code == "ENGLISH_SUPPORT_NOT_ALLOWED"


def test_basket_is_server_priced_and_revisioned(voucher_service):
    session, _ = create_session(voucher_service)
    vendor = session["vendors"][0]
    reveal(voucher_service, session, vendor)
    solve_offer(
        voucher_service,
        session["session_id"],
        vendor["offer_instance_id"],
        "solve-basket",
    )
    offer = voucher_service.repository.fetch_one(
        "SELECT * FROM voucher_session_offers WHERE offer_instance_id = ?",
        (vendor["offer_instance_id"],),
    )
    basket, _ = voucher_service.update_basket(
        session["session_id"],
        {
            "client_revision": 1,
            "items": [
                {
                    "offer_instance_id": vendor["offer_instance_id"],
                    "quantity": offer["bundle_size"],
                    "spent_cents": 1,
                }
            ],
        },
        "basket-1",
    )
    assert basket["spent_cents"] == offer["bundle_price_cents"]
    assert basket["items"][0]["spent_cents"] == offer["bundle_price_cents"]

    with pytest.raises(VoucherAPIError) as quantity_error:
        voucher_service.update_basket(
            session["session_id"],
            {
                "client_revision": 2,
                "items": [
                    {
                        "offer_instance_id": vendor["offer_instance_id"],
                        "quantity": offer["bundle_size"] * 2,
                    }
                ],
            },
            "basket-multiple-bundles",
        )
    assert quantity_error.value.code == "INVALID_BUNDLE_QUANTITY"

    with pytest.raises(VoucherAPIError) as error:
        voucher_service.update_basket(
            session["session_id"],
            {"client_revision": 1, "items": []},
            "basket-stale",
        )
    assert error.value.code == "STALE_BASKET_REVISION"
    assert error.value.details["current_basket_revision"] == 1


def test_basket_limit_error_uses_current_voucher_value(voucher_service):
    session, _ = create_session(voucher_service, player="limit-message-player")
    vendor = session["vendors"][0]
    reveal(voucher_service, session, vendor, "limit-reveal")
    solve_offer(
        voucher_service,
        session["session_id"],
        vendor["offer_instance_id"],
        "limit-solve",
    )
    offer = voucher_service.repository.fetch_one(
        "SELECT * FROM voucher_session_offers WHERE offer_instance_id = ?",
        (vendor["offer_instance_id"],),
    )
    with voucher_service.repository.transaction() as transaction:
        transaction.execute(
            """UPDATE voucher_session_offers SET bundle_price_cents = 4100
               WHERE offer_instance_id = ?""",
            (vendor["offer_instance_id"],),
        )
    with pytest.raises(VoucherAPIError) as error:
        voucher_service.update_basket(
            session["session_id"],
            {
                "client_revision": 1,
                "items": [
                    {
                        "offer_instance_id": vendor["offer_instance_id"],
                        "quantity": offer["bundle_size"],
                    }
                ],
            },
            "limit-basket",
        )
    assert error.value.code == "VOUCHER_LIMIT_EXCEEDED"
    assert error.value.message == "Basket exceeds the $40 voucher"


def test_medium_offer_explorer_counts_distinct_vendors(voucher_service):
    session, _ = create_session(
        voucher_service,
        difficulty="medium",
        key="medium-create",
        player="medium-player",
    )
    for index, vendor in enumerate(session["vendors"]):
        reveal(voucher_service, session, vendor, f"medium-reveal-{index}")
        solve_offer(
            voucher_service,
            session["session_id"],
            vendor["offer_instance_id"],
            f"medium-solve-{index}",
        )
    offers = voucher_service.repository.fetch_all(
        """SELECT offer_instance_id, bundle_size, bundle_price_cents
           FROM voucher_session_offers WHERE session_id = ?
           ORDER BY bundle_price_cents LIMIT 2""",
        (session["session_id"],),
    )
    basket, _ = voucher_service.update_basket(
        session["session_id"],
        {
            "client_revision": 1,
            "items": [
                {
                    "offer_instance_id": offer["offer_instance_id"],
                    "quantity": offer["bundle_size"],
                }
                for offer in offers
            ],
        },
        "medium-basket",
    )
    assert basket["spent_cents"] <= 4000
    completed, _ = voucher_service.complete_session(
        session["session_id"],
        {"basket_revision": 1},
        "medium-complete",
    )
    assert completed["shopping"]["purchased_vendor_count"] == 2
    assert completed["shopping"]["vendor_target"] == 2
    assert completed["shopping"]["vendor_target_completed"] is True
    assert "exact_spend_completed" not in completed["shopping"]


def test_hard_timer_checkpoints_never_increase(voucher_service):
    session, _ = create_session(voucher_service, difficulty="hard")
    session_id = session["session_id"]
    start = datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)
    voucher_service.record_event(
        session_id,
        {
            "event_id": "event-start",
            "event_type": "SESSION_STARTED",
            "occurred_at": start.isoformat(),
            "metadata": {"remaining_ms": 90000},
        },
        "event-key-start",
    )
    checkpoint, _ = voucher_service.record_event(
        session_id,
        {
            "event_id": "event-checkpoint",
            "event_type": "TIMER_CHECKPOINT",
            "occurred_at": (start + timedelta(seconds=15)).isoformat(),
            "metadata": {"remaining_ms": 75000},
        },
        "event-key-checkpoint",
    )
    assert checkpoint["timer"]["remaining_ms"] == 75000

    stale, _ = voucher_service.record_event(
        session_id,
        {
            "event_id": "event-stale",
            "event_type": "TIMER_CHECKPOINT",
            "occurred_at": (start + timedelta(seconds=5)).isoformat(),
            "metadata": {"remaining_ms": 89000},
        },
        "event-key-stale",
    )
    assert stale["timer"]["accepted"] is False
    restored, _ = voucher_service.get_session(session_id)
    assert restored["timer"]["remaining_ms"] == 75000


def test_complete_uses_authoritative_attempts_and_can_be_restored(voucher_service):
    session, _ = create_session(voucher_service)
    with pytest.raises(VoucherAPIError) as incomplete:
        voucher_service.complete_session(
            session["session_id"], {"basket_revision": 0}, "complete-early"
        )
    assert incomplete.value.code == "LEARNING_INCOMPLETE"

    for index, vendor in enumerate(session["vendors"]):
        reveal(voucher_service, session, vendor, f"reveal-{index}")
        solve_offer(
            voucher_service,
            session["session_id"],
            vendor["offer_instance_id"],
            f"solve-{index}",
        )
    completed, _ = voucher_service.complete_session(
        session["session_id"], {"basket_revision": 0}, "complete-final"
    )
    assert completed["session_status"] == "COMPLETED"
    assert completed["learning"]["rule_completed"] == 5
    assert completed["learning"]["price_completed"] == 5
    assert completed["shopping"]["vendor_target_completed"] is True
    assert "exact_spend_completed" not in completed["shopping"]
    restored, _ = voucher_service.get_session(session["session_id"])
    assert restored["session_status"] == "COMPLETED"
    assert restored["result"]["learning"] == completed["learning"]


def test_abandon_releases_active_session_constraint(voucher_service):
    first, _ = create_session(voucher_service)
    abandoned, _ = voucher_service.abandon_session(first["session_id"], {}, "abandon-1")
    assert abandoned["session_status"] == "ABANDONED"
    second, status = create_session(voucher_service, key="create-after-abandon")
    assert status == 201
    assert second["session_id"] != first["session_id"]


def test_session_dialogue_metadata_is_dynamic(voucher_service):
    session, _ = create_session(voucher_service)
    vendor = session["vendors"][0]
    offer = voucher_service.repository.fetch_one(
        "SELECT * FROM voucher_session_offers WHERE offer_instance_id = ?",
        (vendor["offer_instance_id"],),
    )
    base = {
        "dialogue": {
            "text": "static",
            "translation_HAN": "static",
            "translation_POJ": "static",
            "audio": "",
        },
        "options": [
            {
                "option_id": offer["confirm_option_id"],
                "events": [
                    {
                        "event_id": "static-event",
                        "event_type": "VOUCHER_OFFER_REVEALED",
                        "metadata": "{}",
                    }
                ],
            }
        ],
    }
    rendered = voucher_service.render_dialogue(
        session["session_id"], offer["dialogue_offer_node_id"], base
    )
    metadata = json.loads(rendered["options"][0]["events"][0]["metadata"])
    assert metadata == {
        "session_id": session["session_id"],
        "offer_instance_id": vendor["offer_instance_id"],
        "vendor_id": offer["vendor_id"],
        "offer_id": offer["offer_id"],
    }
    assert rendered["dialogue"]["audio"].startswith("/audio-clips/")
