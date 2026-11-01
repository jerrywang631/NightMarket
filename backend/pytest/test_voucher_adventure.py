"""API contract tests for the Lesson 2 Voucher Adventure dialogue."""

import json
import wave
from pathlib import Path

import pytest


VENDORS = [
    ("v_va_001", "npc_va_001", "n_va_v1_greet", "n_va_v1_offer", "pepper_bun", 0),
    (
        "v_va_002",
        "npc_va_002",
        "n_va_v2_greet",
        "n_va_v2_offer",
        "chicken_wing_rice_roll",
        1,
    ),
    (
        "v_va_003",
        "npc_va_003",
        "n_va_v3_greet",
        "n_va_v3_offer",
        "hsinchu_pork_ball",
        2,
    ),
    (
        "v_va_004",
        "npc_va_004",
        "n_va_v4_greet",
        "n_va_v4_offer",
        "tube_rice_pudding",
        3,
    ),
    (
        "v_va_005",
        "npc_va_005",
        "n_va_v5_greet",
        "n_va_v5_offer",
        "steamed_taro_cake",
        4,
    ),
]


@pytest.mark.parametrize(
    "vendor_id,npc_id,root_node,offer_node,offer_id,vendor_index", VENDORS
)
def test_voucher_adventure_vendor_and_dialogue_contract(
    client, vendor_id, npc_id, root_node, offer_node, offer_id, vendor_index
):
    vendor_response = client.get(f"/api/v1/vendors/{vendor_id}")
    assert vendor_response.status_code == 200
    vendor = vendor_response.get_json()["data"]
    assert vendor["vendor_id"] == vendor_id
    assert vendor["dialogue_node_id"] == root_node

    root_response = client.get(f"/api/v1/dialogue/{root_node}")
    assert root_response.status_code == 200
    root = root_response.get_json()["data"]
    assert root["dialogue"]["npc_id"] == npc_id
    assert root["options"][0]["next_node"] == offer_node
    assert root["options"][0]["feedback_type"] == "neutral"
    assert root["options"][0]["events"] == []

    offer_response = client.get(f"/api/v1/dialogue/{offer_node}")
    assert offer_response.status_code == 200
    offer = offer_response.get_json()["data"]
    assert offer["dialogue"]["npc_id"] == npc_id
    assert offer["options"][0]["next_node"] == ""
    assert offer["options"][0]["feedback_type"] == "positive"

    events = offer["options"][0]["events"]
    assert len(events) == 1
    assert events[0]["event_type"] == "VOUCHER_OFFER_REVEALED"
    assert json.loads(events[0]["metadata"]) == {
        "vendor_id": vendor_id,
        "offer_id": offer_id,
        "vendor_index": vendor_index,
    }


def test_voucher_adventure_dialogue_preserves_all_translations(client):
    response = client.get("/api/v1/dialogue/n_va_v1_greet")
    dialogue = response.get_json()["data"]["dialogue"]
    assert dialogue["text"] == "Fresh pepper buns are $8 each."
    assert dialogue["translation_HAN"] == "新鮮的胡椒餅，一個八箍。"
    assert dialogue["translation_POJ"] == "Sin-chhiⁿ ê hô͘-chio-piáⁿ, chi̍t ê peh kho͘."

    option = response.get_json()["data"]["options"][0]["text"]
    assert option == "Do you have a special offer today? / 今仔日有特價無？"


def test_vendor_options_contain_only_english_and_traditional_chinese(client):
    for _, _, greet_node, offer_node, _, _ in VENDORS:
        for node_id in (greet_node, offer_node):
            response = client.get(f"/api/v1/dialogue/{node_id}")
            assert response.status_code == 200
            options = response.get_json()["data"]["options"]
            assert len(options) == 1
            assert options[0]["text"].count(" / ") == 1


def test_shared_voucher_guide_starts_only_voucher_adventure(client):
    vendor_response = client.get("/api/v1/vendors/v_va_guide")
    assert vendor_response.status_code == 200
    vendor = vendor_response.get_json()["data"]
    assert vendor == {
        "vendor_id": "v_va_guide",
        "dialogue_node_id": "n_va_guide_intro",
        "vendor_name": "Voucher Guide",
        "items": [],
    }

    response = client.get("/api/v1/dialogue/n_va_guide_intro")
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["dialogue"]["npc_id"] == "npc_va_guide"
    assert data["dialogue"]["text"] == (
        "Want to try the Voucher Adventure? Listen to five vendors, understand "
        "each offer, and work out the price. Then use your $40 voucher to shop."
    )
    assert data["dialogue"]["translation_HAN"] == (
        "欲試看覓代用券挑戰無？聽五個頭家介紹特價，了解優惠的意思，"
        "閣算出價數。了後用四十箍的代用券買物件。"
    )
    assert data["dialogue"]["translation_POJ"] == (
        "Beh chhì-khòaⁿ-māi tāi-iōng-kǹg thiáu-chiàn bô? Thiaⁿ gō͘ ê "
        "thâu-ke kài-siāu te̍k-kè, liáu-kái iu-hūi ê ì-sù, koh sǹg-chhut "
        "kè-siàu. Liáu-āu ēng sì-cha̍p kho͘ ê tāi-iōng-kǹg bé mi̍h-kiāⁿ."
    )
    assert data["dialogue"]["audio"] == "/audio-clips/n_va_guide_intro.wav"
    assert data["next_nodes"] == []

    options = {option["option_id"]: option for option in data["options"]}
    assert options["o_va_guide_enter"]["text"] == (
        "Enter Voucher Adventure / 進入代用券挑戰"
    )
    assert options["o_va_guide_enter"]["text"].count(" / ") == 1
    assert options["o_va_guide_enter"]["next_node"] == ""
    assert options["o_va_guide_enter"]["feedback_type"] == "positive"
    assert len(options["o_va_guide_enter"]["events"]) == 1
    event = options["o_va_guide_enter"]["events"][0]
    assert event["event_id"] == "e_va_guide_start"
    assert event["event_type"] == "START_MINIGAME"
    assert json.loads(event["metadata"]) == {"minigame_id": "voucher_adventure"}

    assert options["o_va_guide_later"]["text"] == "Maybe later / 後擺才來"
    assert options["o_va_guide_later"]["text"].count(" / ") == 1
    assert options["o_va_guide_later"]["next_node"] == ""
    assert options["o_va_guide_later"]["feedback_type"] == "neutral"
    assert options["o_va_guide_later"]["events"] == []


def test_voucher_guide_audio_files_are_valid():
    audio_dir = Path(__file__).resolve().parents[1] / "audio-clips"
    audio_path = audio_dir / "n_va_guide_intro.wav"
    assert audio_path.is_file()
    with wave.open(str(audio_path), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getframerate() == 16000
        assert audio.getnframes() > 0
