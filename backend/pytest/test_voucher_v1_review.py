"""Review-build coverage for released Voucher Adventure v1 content."""

import json
import os

import pytest

import voucher_adventure.service as service_module
from voucher_adventure.content import (
    build_questions,
    calculate_prices,
    content_catalog,
    get_offer_definitions,
    select_variant_key,
)
from voucher_adventure.repository import create_voucher_repository
from voucher_adventure.service import VoucherAdventureService, VoucherAPIError


def service_at(tmp_path, name, seed=12345, allow_unreleased=True):
    repository = create_voucher_repository(sqlite_path=str(tmp_path / f"{name}.db"))
    return VoucherAdventureService(
        repository,
        allow_unreleased=allow_unreleased,
        seed_provider=lambda: seed,
    )


def create(service, version, difficulty="easy", player="review-player"):
    return service.create_session(
        {
            "player_id": player,
            "difficulty": difficulty,
            "content_version": version,
        },
        f"create-{player}-{version}-{difficulty}",
    )[0]


def selected_variants(service, session_id):
    rows = service.repository.fetch_all(
        """SELECT offer_id, price_variant FROM voucher_session_offers
           WHERE session_id = ? ORDER BY offer_id""",
        (session_id,),
    )
    return [(row["offer_id"], row["price_variant"]) for row in rows]


def test_public_api_accepts_released_v1(tmp_path):
    service = service_at(tmp_path, "public", allow_unreleased=False)
    session = create(service, "v1")
    assert session["content_version"] == "v1"
    assert session["shopping_bonus"] == {
        "vendor_target": 0,
        "required_for_completion": False,
    }


def test_review_service_can_create_v1(tmp_path):
    service = service_at(tmp_path, "review")
    session = create(service, "v1")
    assert session["content_version"] == "v1"
    assert len(session["vendors"]) == 5


def test_session_creation_rejects_unreachable_offer_explorer_target(
    tmp_path, monkeypatch
):
    service = service_at(tmp_path, "unreachable-target", seed=12345)
    monkeypatch.setattr(service_module, "VOUCHER_VALUE_CENTS", 1)
    with pytest.raises(VoucherAPIError) as error:
        create(
            service,
            "v1",
            difficulty="medium",
            player="unreachable-target-player",
        )
    assert error.value.code == "SHOPPING_TARGET_UNREACHABLE"


@pytest.mark.parametrize("content_version", ["va_1", "va_2", "va_999"])
def test_retired_or_unknown_content_version_is_rejected(tmp_path, content_version):
    service = service_at(tmp_path, "unknown-version", allow_unreleased=False)
    with pytest.raises(VoucherAPIError) as error:
        create(service, content_version)
    assert error.value.status == 400
    assert error.value.code == "UNSUPPORTED_CONTENT_VERSION"


def test_v1_covers_all_variants():
    for offer in get_offer_definitions("v1"):
        selected = {
            select_variant_key("v1", offer, seed, allow_unreleased=False)
            for seed in range(500)
        }
        assert selected == {"A", "B", "C"}


def test_same_seed_materializes_same_variants(tmp_path):
    first_service = service_at(tmp_path, "seed-first", seed=98231)
    second_service = service_at(tmp_path, "seed-second", seed=98231)
    first = create(first_service, "v1", player="seed-first")
    second = create(second_service, "v1", player="seed-second")
    assert selected_variants(first_service, first["session_id"]) == selected_variants(
        second_service, second["session_id"]
    )


def test_v1_catalog_prices_questions_and_audio_are_review_ready():
    catalog = content_catalog("v1")
    assert len(catalog) == 15
    assert sum(len(item["questions"]) for item in catalog) == 45
    expected = {
        "pepper_bun": {"A": (800, 1200), "B": (1000, 1500), "C": (1200, 1800)},
        "chicken_wing_rice_roll": {
            "A": (1000, 800),
            "B": (2000, 1600),
            "C": (3000, 2400),
        },
        "hsinchu_pork_ball": {
            "A": (1000, 700),
            "B": (2000, 1400),
            "C": (3000, 2100),
        },
        "tube_rice_pudding": {
            "A": (600, 600),
            "B": (800, 800),
            "C": (1000, 1000),
        },
        "steamed_taro_cake": {
            "A": (500, 300),
            "B": (700, 500),
            "C": (900, 700),
        },
    }
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for item in catalog:
        offer = next(
            offer
            for offer in get_offer_definitions("v1")
            if offer["offer_id"] == item["offer_id"]
        )
        base, _, bundle = calculate_prices(offer, item["variant"])
        assert (base, bundle) == expected[item["offer_id"]][item["variant"]]
        assert isinstance(base, int) and isinstance(bundle, int)
        assert bundle <= 4000
        assert all(item["dialogue"]["greet"])
        for audio_key in ("audio_greet", "audio_offer"):
            path = os.path.join(
                backend_dir,
                item["dialogue"][audio_key].lstrip("/").replace("/", os.sep),
            )
            assert os.path.isfile(path), path


def test_v1_offer_dialogue_matches_approved_review_copy():
    expected = {
        "pepper_bun": (
            "Yeah—the second one is half price.",
            "有，第二個半價。",
            "Ū, tē-jī ê pòaⁿ-kè.",
        ),
        "chicken_wing_rice_roll": (
            "They're 20% off today.",
            "今仔日減兩成。",
            "Kin-á-ji̍t kiám nn̄g-siâⁿ.",
        ),
        "hsinchu_pork_ball": (
            "They're 30% off today.",
            "今仔日減三成。",
            "Kin-á-ji̍t kiám saⁿ-siâⁿ.",
        ),
        "tube_rice_pudding": (
            "Yeah—buy one, get one free.",
            "有，買一個送一個。",
            "Ū, bé chi̍t ê sàng chi̍t ê.",
        ),
        "steamed_taro_cake": (
            "Today they're $2 off each.",
            "今仔日一個減兩箍。",
            "Kin-á-ji̍t chi̍t ê kiám nn̄g kho͘.",
        ),
    }
    for offer in get_offer_definitions("v1"):
        assert offer["offer_dialogue"] == expected[offer["offer_id"]]


def test_v1_uses_only_the_confirmed_canonical_misconceptions():
    offers = {offer["offer_id"]: offer for offer in get_offer_definitions("v1")}

    pepper = build_questions(offers["pepper_bun"], "B", "v1")[1]
    assert pepper["misconceptions"] == {
        "500": (
            "SECOND_ITEM_ONLY",
            "That is only the discounted second bun's price, not the total. "
            "Add the full-price first bun as well.",
        ),
        "1000": (
            "BOTH_ITEMS_TREATED_AS_ONE_FULL_PRICE",
            "That total accounts for only one full-price bun or discounts both "
            "buns. The first bun is full price and the second is half price; add "
            "both prices.",
        ),
    }

    percent_questions = build_questions(offers["chicken_wing_rice_roll"], "B", "v1")
    assert percent_questions[0]["misconceptions"] == {
        "1600": (
            "FINAL_PRICE_AS_DISCOUNT_AMOUNT",
            "That is the price after the discount. The question asks how much is "
            "taken off.",
        )
    }
    assert percent_questions[1]["misconceptions"] == {
        "400": (
            "DISCOUNT_AMOUNT_AS_FINAL_PRICE",
            "That is the amount taken off, not the final price. Subtract it from "
            "the original price.",
        ),
        "2000": (
            "NO_DISCOUNT_APPLIED",
            "That is the original price. Apply the discount before paying.",
        ),
    }
    assert "PERCENT_SUBTRACTED_AS_DOLLARS" not in json.dumps(percent_questions)

    bogo = build_questions(offers["tube_rice_pudding"], "B", "v1")[1]
    assert bogo["misconceptions"]["0"] == (
        "FREE_ITEM_MEANS_TOTAL_IS_ZERO",
        "Only the second item is free. The first item is still full price.",
    )

    fixed = build_questions(offers["steamed_taro_cake"], "B", "v1")[1]
    assert fixed["misconceptions"]["200"] == (
        "DISCOUNT_AMOUNT_AS_FINAL_PRICE",
        "That is the discount amount, not the final price. Subtract it from the "
        "original price.",
    )


def test_v1_bc_meaning_price_and_transfer_answers_match_review_table():
    expected = {
        ("pepper_bun", "B"): (500, 1500, 1800),
        ("pepper_bun", "C"): (600, 1800, 1200),
        ("chicken_wing_rice_roll", "B"): (400, 1600, 2400),
        ("chicken_wing_rice_roll", "C"): (600, 2400, 800),
        ("hsinchu_pork_ball", "B"): (600, 1400, 2100),
        ("hsinchu_pork_ball", "C"): (900, 2100, 700),
        ("tube_rice_pudding", "B"): (0, 800, 1000),
        ("tube_rice_pudding", "C"): (0, 1000, 600),
        ("steamed_taro_cake", "B"): (200, 500, 700),
        ("steamed_taro_cake", "C"): (200, 700, 300),
    }
    for offer in get_offer_definitions("v1"):
        for variant in ("B", "C"):
            questions = build_questions(offer, variant, "v1")
            assert (
                tuple(question["answer"] for question in questions)
                == expected[(offer["offer_id"], variant)]
            )


@pytest.mark.parametrize(
    "difficulty,questions_per_offer", [("easy", 2), ("medium", 2), ("hard", 3)]
)
def test_v1_difficulty_question_counts(tmp_path, difficulty, questions_per_offer):
    service = service_at(tmp_path, f"difficulty-{difficulty}")
    session = create(
        service, "v1", difficulty=difficulty, player=f"player-{difficulty}"
    )
    counts = service.repository.fetch_all(
        """SELECT offer_instance_id, COUNT(*) AS count
           FROM voucher_session_questions WHERE session_id = ?
           GROUP BY offer_instance_id""",
        (session["session_id"],),
    )
    assert len(counts) == 5
    assert {row["count"] for row in counts} == {questions_per_offer}
    target = {"easy": 0, "medium": 2, "hard": 3}[difficulty]
    offers = service.repository.fetch_all(
        """SELECT bundle_price_cents FROM voucher_session_offers
           WHERE session_id = ?""",
        (session["session_id"],),
    )
    assert session["shopping_bonus"]["vendor_target"] == target
    assert sum(sorted(row["bundle_price_cents"] for row in offers)[:target]) <= 4000


def test_session_restore_uses_materialized_variant(tmp_path):
    service = service_at(tmp_path, "restore", seed=777)
    session = create(service, "v1")
    before = selected_variants(service, session["session_id"])

    restarted = VoucherAdventureService(
        service.repository, allow_unreleased=True, seed_provider=lambda: 1
    )
    restored, _ = restarted.get_session(session["session_id"])
    after = selected_variants(restarted, restored["session_id"])
    assert after == before


@pytest.mark.parametrize(
    "difficulty,expected_levels",
    [
        ("easy", ["RULE_HINT", "FORMULA_HINT"]),
        ("medium", ["RULE_HINT", "RULE_HINT"]),
        ("hard", ["RETRY_ONLY", "RETRY_ONLY"]),
    ],
)
def test_v1_feedback_policy_by_difficulty(tmp_path, difficulty, expected_levels):
    service = service_at(tmp_path, f"feedback-{difficulty}", seed=123)
    session = create(
        service,
        "v1",
        difficulty=difficulty,
        player=f"feedback-{difficulty}",
    )
    vendor = session["vendors"][0]
    offer = service.repository.fetch_one(
        "SELECT * FROM voucher_session_offers WHERE offer_instance_id = ?",
        (vendor["offer_instance_id"],),
    )
    revealed, _ = service.reveal_offer(
        session["session_id"],
        vendor["offer_instance_id"],
        {
            "dialogue_node_id": offer["dialogue_offer_node_id"],
            "option_id": offer["confirm_option_id"],
        },
        f"feedback-reveal-{difficulty}",
    )
    question_id = revealed["questions"][0]["question_instance_id"]
    question = service.repository.fetch_one(
        "SELECT * FROM voucher_session_questions WHERE question_instance_id = ?",
        (question_id,),
    )
    observed = []
    for attempt_number in (1, 2):
        response, _ = service.submit_attempt(
            {
                "session_id": session["session_id"],
                "question_instance_id": question_id,
                "answer": question["correct_answer"] + 12345,
                "answer_unit": "MONEY_CENTS",
                "attempt_number": attempt_number,
                "english_support_used": False,
                "response_time_ms": 100,
            },
            f"feedback-{difficulty}-{attempt_number}",
        )
        observed.append(response["feedback_level"])
        assert "correct_answer" not in response
    assert observed == expected_levels


def test_restore_redacts_incomplete_attempt_and_restores_completed_attempt(
    tmp_path,
):
    service = service_at(tmp_path, "redaction", seed=50)
    session = create(service, "v1")
    vendor = session["vendors"][0]
    offer = service.repository.fetch_one(
        "SELECT * FROM voucher_session_offers WHERE offer_instance_id = ?",
        (vendor["offer_instance_id"],),
    )
    revealed, _ = service.reveal_offer(
        session["session_id"],
        vendor["offer_instance_id"],
        {
            "dialogue_node_id": offer["dialogue_offer_node_id"],
            "option_id": offer["confirm_option_id"],
        },
        "redaction-reveal",
    )
    question_id = revealed["questions"][0]["question_instance_id"]
    question = service.repository.fetch_one(
        "SELECT * FROM voucher_session_questions WHERE question_instance_id = ?",
        (question_id,),
    )
    wrong_body = {
        "session_id": session["session_id"],
        "question_instance_id": question_id,
        "answer": question["correct_answer"] + 1,
        "answer_unit": "MONEY_CENTS",
        "attempt_number": 1,
        "english_support_used": False,
        "response_time_ms": 100,
    }
    service.submit_attempt(wrong_body, "redaction-wrong")
    incomplete, _ = service.get_session(session["session_id"])
    assert "answer" not in incomplete["attempts"][0]
    assert "feedback_en" not in incomplete["attempts"][0]

    correct_body = dict(wrong_body)
    correct_body.update(answer=question["correct_answer"], attempt_number=2)
    service.submit_attempt(correct_body, "redaction-correct")
    completed, _ = service.get_session(session["session_id"])
    assert all("answer" in attempt for attempt in completed["attempts"])
    assert all("feedback_en" in attempt for attempt in completed["attempts"])


def test_review_manifest_has_15_entries_and_no_missing_audio():
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(backend_dir, "voucher_adventure_v1_review.json")
    with open(path, encoding="utf-8") as review_file:
        manifest = json.load(review_file)
    assert len(manifest) == 15
    assert all(entry["dialogue"]["greet"]["audio_exists"] for entry in manifest)
    assert all(entry["dialogue"]["offer"]["audio_exists"] for entry in manifest)
    assert all(
        entry["dialogue"][node]["language_review"] == "APPROVED"
        for entry in manifest
        for node in ("greet", "offer")
    )
    assert all(
        entry["dialogue"][node]["audio_review"] == "APPROVED"
        for entry in manifest
        if entry["variant"] in {"B", "C"}
        for node in ("greet", "offer")
    )
    assert {entry["status"] for entry in manifest} == {"APPROVED"}
    assert all(entry["approved"] for entry in manifest)
    assert all(entry["selectable_for_production"] for entry in manifest)
