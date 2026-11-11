"""Populate the Lesson 2 Voucher Adventure dialogue data.

The IDs in this module are exclusive to Voucher Adventure.  The script is
safe to run repeatedly: rows owned by these IDs are replaced transactionally.

Run from the backend directory:

    py -3.11 populate_voucher_adventure.py
    py -3.11 populate_voucher_adventure.py --generate-guide-audio

By default both the local test and lesson databases are updated.  Pass
``--database test`` or ``--database lesson`` to update only one database.
"""

import argparse
import json
import os
import sqlite3

from voucher_adventure.content import BASE_OFFER_DEFINITIONS


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASES = {
    "test": os.path.join(BASE_DIR, "database", "hok_test_data.db"),
    "lesson": os.path.join(BASE_DIR, "database", "hok_lesson_data.db"),
}


NPCS = [
    ("npc_va_001", "Pepper Bun Vendor (Variant A)"),
    ("npc_va_002", "Chicken Wing Rice Roll Vendor (Variant A)"),
    ("npc_va_003", "Hsinchu Pork Ball Vendor (Variant A)"),
    ("npc_va_004", "Tube Rice Pudding Vendor (Variant A)"),
    ("npc_va_005", "Steamed Taro Cake Vendor (Variant A)"),
    ("npc_va_guide", "Voucher Guide"),
]

for variant in ("B", "C"):
    NPCS.extend(
        (
            f"{offer['npc_id']}_{variant}",
            f"{offer['vendor_name']} (Variant {variant})",
        )
        for offer in BASE_OFFER_DEFINITIONS
    )

VENDORS = [
    ("v_va_001", "n_va_v1_greet", "npc_va_001", "Pepper Bun Vendor"),
    (
        "v_va_002",
        "n_va_v2_greet",
        "npc_va_002",
        "Chicken Wing Rice Roll Vendor",
    ),
    ("v_va_003", "n_va_v3_greet", "npc_va_003", "Hsinchu Pork Ball Vendor"),
    ("v_va_004", "n_va_v4_greet", "npc_va_004", "Tube Rice Pudding Vendor"),
    ("v_va_005", "n_va_v5_greet", "npc_va_005", "Steamed Taro Cake Vendor"),
    ("v_va_guide", "n_va_guide_intro", "npc_va_guide", "Voucher Guide"),
]

DIALOGUE_NODES = [
    ("n_va_v1_greet", "n_000", "npc_va_001"),
    ("n_va_v1_offer", "n_va_v1_greet", "npc_va_001"),
    ("n_va_v2_greet", "n_000", "npc_va_002"),
    ("n_va_v2_offer", "n_va_v2_greet", "npc_va_002"),
    ("n_va_v3_greet", "n_000", "npc_va_003"),
    ("n_va_v3_offer", "n_va_v3_greet", "npc_va_003"),
    ("n_va_v4_greet", "n_000", "npc_va_004"),
    ("n_va_v4_offer", "n_va_v4_greet", "npc_va_004"),
    ("n_va_v5_greet", "n_000", "npc_va_005"),
    ("n_va_v5_offer", "n_va_v5_greet", "npc_va_005"),
    ("n_va_guide_intro", "n_000", "npc_va_guide"),
]

for variant in ("B", "C"):
    for offer in BASE_OFFER_DEFINITIONS:
        npc_id = f"{offer['npc_id']}_{variant}"
        greet_node = f"{offer['root_node_id']}_{variant}"
        offer_node = f"{offer['offer_node_id']}_{variant}"
        DIALOGUE_NODES.extend(
            [
                (greet_node, "n_000", npc_id),
                (offer_node, greet_node, npc_id),
            ]
        )

DIALOGUES = [
    (
        "n_va_v1_greet",
        "d_va_v1_greet",
        "Fresh pepper buns are $8 each.",
        "新鮮的胡椒餅，一個八箍。",
        "Sin-chhiⁿ ê hô͘-chio-piáⁿ, chi̍t ê peh kho͘.",
        "audio-clips/n_va_v1_greet.wav",
        "npc_va_001",
    ),
    (
        "n_va_v1_offer",
        "d_va_v1_offer",
        "Yeah—the second one is half price.",
        "有，第二個半價。",
        "Ū, tē-jī ê pòaⁿ-kè.",
        "audio-clips/n_va_v1_offer.wav",
        "npc_va_001",
    ),
    (
        "n_va_v2_greet",
        "d_va_v2_greet",
        "Chicken wing rice rolls are normally $10 each.",
        "雞翅包飯原價一個十箍。",
        "Ke-si̍t pau-pn̄g goân-kè chi̍t ê cha̍p kho͘.",
        "audio-clips/n_va_v2_greet.wav",
        "npc_va_002",
    ),
    (
        "n_va_v2_offer",
        "d_va_v2_offer",
        "They're 20% off today.",
        "今仔日減兩成。",
        "Kin-á-ji̍t kiám nn̄g-siâⁿ.",
        "audio-clips/n_va_v2_offer.wav",
        "npc_va_002",
    ),
    (
        "n_va_v3_greet",
        "d_va_v3_greet",
        "Hsinchu pork balls are normally $10 each.",
        "新竹貢丸原價一個十箍。",
        "Sin-tek kòng-oân goân-kè chi̍t ê cha̍p kho͘.",
        "audio-clips/n_va_v3_greet.wav",
        "npc_va_003",
    ),
    (
        "n_va_v3_offer",
        "d_va_v3_offer",
        "They're 30% off today.",
        "今仔日減三成。",
        "Kin-á-ji̍t kiám saⁿ-siâⁿ.",
        "audio-clips/n_va_v3_offer.wav",
        "npc_va_003",
    ),
    (
        "n_va_v4_greet",
        "d_va_v4_greet",
        "Tube rice puddings are $6 each.",
        "筒仔米糕一個六箍。",
        "Tâng-á-bí-ko chi̍t ê la̍k kho͘.",
        "audio-clips/n_va_v4_greet.wav",
        "npc_va_004",
    ),
    (
        "n_va_v4_offer",
        "d_va_v4_offer",
        "Yeah—buy one, get one free.",
        "有，買一個送一個。",
        "Ū, bé chi̍t ê sàng chi̍t ê.",
        "audio-clips/n_va_v4_offer.wav",
        "npc_va_004",
    ),
    (
        "n_va_v5_greet",
        "d_va_v5_greet",
        "Steamed taro cakes are $5 each.",
        "芋粿巧一個五箍。",
        "Ō͘-kóe-khiáu chi̍t ê gō͘ kho͘.",
        "audio-clips/n_va_v5_greet.wav",
        "npc_va_005",
    ),
    (
        "n_va_v5_offer",
        "d_va_v5_offer",
        "Today they're $2 off each.",
        "今仔日一個減兩箍。",
        "Kin-á-ji̍t chi̍t ê kiám nn̄g kho͘.",
        "audio-clips/n_va_v5_offer.wav",
        "npc_va_005",
    ),
    (
        "n_va_guide_intro",
        "d_va_guide_intro",
        (
            "Want to try the Voucher Adventure? Listen to five vendors, understand "
            "each offer, and work out the price. Then use your $40 voucher to shop."
        ),
        (
            "欲試看覓代用券挑戰無？聽五個頭家介紹特價，了解優惠的意思，"
            "閣算出價數。了後用四十箍的代用券買物件。"
        ),
        (
            "Beh chhì-khòaⁿ-māi tāi-iōng-kǹg thiáu-chiàn bô? Thiaⁿ gō͘ ê "
            "thâu-ke kài-siāu te̍k-kè, liáu-kái iu-hūi ê ì-sù, koh sǹg-chhut "
            "kè-siàu. Liáu-āu ēng sì-cha̍p kho͘ ê tāi-iōng-kǹg bé mi̍h-kiāⁿ."
        ),
        "/audio-clips/n_va_guide_intro.wav",
        "npc_va_guide",
    ),
]

# B/C are review-only Admin trees. Gameplay still uses the five base NPC IDs.
for variant in ("B", "C"):
    for offer in BASE_OFFER_DEFINITIONS:
        npc_id = f"{offer['npc_id']}_{variant}"
        greet_node = f"{offer['root_node_id']}_{variant}"
        offer_node = f"{offer['offer_node_id']}_{variant}"
        greet_en, greet_han, greet_poj = offer["greet"][variant]
        offer_en, offer_han, offer_poj = offer["offer_dialogue"]
        DIALOGUES.extend(
            [
                (
                    greet_node,
                    f"d_{greet_node[2:]}",
                    greet_en,
                    greet_han,
                    greet_poj,
                    f"audio-clips/{greet_node}.wav",
                    npc_id,
                ),
                (
                    offer_node,
                    f"d_{offer_node[2:]}",
                    offer_en,
                    offer_han,
                    offer_poj,
                    f"audio-clips/{offer['offer_node_id']}.wav",
                    npc_id,
                ),
            ]
        )

GUIDE_AUDIO_INPUTS = [
    (
        "n_va_guide_intro",
        next(row[4] for row in DIALOGUES if row[0] == "n_va_guide_intro"),
    ),
]


def option_text(english, han):
    """Store only English and Traditional Chinese in player option text."""
    return f"{english} / {han}"


OPTIONS = [
    (
        "n_va_v1_greet",
        "o_va_v1_ask_offer",
        option_text(
            "Do you have a special offer today?",
            "今仔日有特價無？",
        ),
        "n_va_v1_offer",
        "neutral",
    ),
    (
        "n_va_v1_offer",
        "o_va_v1_confirm_offer",
        option_text(
            "Thanks. I'll work out the price.",
            "多謝，我來算看覓。",
        ),
        "",
        "positive",
    ),
    (
        "n_va_v2_greet",
        "o_va_v2_ask_offer",
        option_text(
            "Do you have a special offer today?",
            "今仔日有特價無？",
        ),
        "n_va_v2_offer",
        "neutral",
    ),
    (
        "n_va_v2_offer",
        "o_va_v2_confirm_offer",
        option_text(
            "Thanks. I'll work out the price.",
            "多謝，我來算看覓。",
        ),
        "",
        "positive",
    ),
    (
        "n_va_v3_greet",
        "o_va_v3_ask_offer",
        option_text(
            "Do you have a special offer today?",
            "今仔日有特價無？",
        ),
        "n_va_v3_offer",
        "neutral",
    ),
    (
        "n_va_v3_offer",
        "o_va_v3_confirm_offer",
        option_text(
            "Thanks. I'll work out the price.",
            "多謝，我來算看覓。",
        ),
        "",
        "positive",
    ),
    (
        "n_va_v4_greet",
        "o_va_v4_ask_offer",
        option_text(
            "If I buy two, is there a special offer?",
            "若買兩個，有特價無？",
        ),
        "n_va_v4_offer",
        "neutral",
    ),
    (
        "n_va_v4_offer",
        "o_va_v4_confirm_offer",
        option_text(
            "Thanks. I'll work out the total price.",
            "多謝，我來算總價。",
        ),
        "",
        "positive",
    ),
    (
        "n_va_v5_greet",
        "o_va_v5_ask_offer",
        option_text(
            "Do you have a special offer today?",
            "今仔日有特價無？",
        ),
        "n_va_v5_offer",
        "neutral",
    ),
    (
        "n_va_v5_offer",
        "o_va_v5_confirm_offer",
        option_text(
            "Thanks. I'll work out the price.",
            "多謝，我來算看覓。",
        ),
        "",
        "positive",
    ),
    (
        "n_va_guide_intro",
        "o_va_guide_enter",
        "Enter Voucher Adventure / 進入代用券挑戰",
        "",
        "positive",
    ),
    (
        "n_va_guide_intro",
        "o_va_guide_later",
        "Maybe later / 後擺才來",
        "",
        "neutral",
    ),
]

base_options = {row[1]: row for row in OPTIONS}
for variant in ("B", "C"):
    for offer in BASE_OFFER_DEFINITIONS:
        ask = base_options[offer["ask_option_id"]]
        confirm = base_options[offer["confirm_option_id"]]
        OPTIONS.extend(
            [
                (
                    f"{offer['root_node_id']}_{variant}",
                    f"{offer['ask_option_id']}_{variant}",
                    ask[2],
                    f"{offer['offer_node_id']}_{variant}",
                    ask[4],
                ),
                (
                    f"{offer['offer_node_id']}_{variant}",
                    f"{offer['confirm_option_id']}_{variant}",
                    confirm[2],
                    "",
                    confirm[4],
                ),
            ]
        )

RETIRED_OPTION_IDS = [
    "o_va_guide_continue_explain",
    "o_va_guide_continue_shop",
]

RETIRED_DIALOGUE_IDS = [
    "d_va_guide_explain",
    "d_va_guide_shop",
]

RETIRED_NODE_IDS = [
    "n_va_guide_explain",
    "n_va_guide_shop",
]

EVENTS = [
    (
        "o_va_v1_confirm_offer",
        "e_va_v1_offer_revealed",
        "VOUCHER_OFFER_REVEALED",
        '{"vendor_id":"v_va_001","offer_id":"pepper_bun","vendor_index":0}',
    ),
    (
        "o_va_v2_confirm_offer",
        "e_va_v2_offer_revealed",
        "VOUCHER_OFFER_REVEALED",
        (
            '{"vendor_id":"v_va_002","offer_id":'
            '"chicken_wing_rice_roll","vendor_index":1}'
        ),
    ),
    (
        "o_va_v3_confirm_offer",
        "e_va_v3_offer_revealed",
        "VOUCHER_OFFER_REVEALED",
        ('{"vendor_id":"v_va_003","offer_id":' '"hsinchu_pork_ball","vendor_index":2}'),
    ),
    (
        "o_va_v4_confirm_offer",
        "e_va_v4_offer_revealed",
        ("VOUCHER_OFFER_REVEALED"),
        ('{"vendor_id":"v_va_004","offer_id":' '"tube_rice_pudding","vendor_index":3}'),
    ),
    (
        "o_va_v5_confirm_offer",
        "e_va_v5_offer_revealed",
        "VOUCHER_OFFER_REVEALED",
        ('{"vendor_id":"v_va_005","offer_id":' '"steamed_taro_cake","vendor_index":4}'),
    ),
    (
        "o_va_guide_enter",
        "e_va_guide_start",
        "START_MINIGAME",
        '{"minigame_id":"voucher_adventure"}',
    ),
]


def delete_owned_rows(cursor):
    owned = [
        ("events", "event_id", [row[1] for row in EVENTS]),
        (
            "options",
            "option_id",
            [row[1] for row in OPTIONS] + RETIRED_OPTION_IDS,
        ),
        (
            "dialogues",
            "dialogue_id",
            [row[1] for row in DIALOGUES] + RETIRED_DIALOGUE_IDS,
        ),
        (
            "dialogue_nodes",
            "node_id",
            [row[0] for row in DIALOGUE_NODES] + RETIRED_NODE_IDS,
        ),
        ("vendors", "vendor_id", [row[0] for row in VENDORS]),
        ("npcs", "npc_id", [row[0] for row in NPCS]),
    ]
    for table, id_column, ids in owned:
        placeholders = ",".join("?" for _ in ids)
        cursor.execute(
            f"DELETE FROM {table} WHERE {id_column} IN ({placeholders})", ids
        )


def populate(cursor):
    delete_owned_rows(cursor)
    cursor.executemany("INSERT INTO npcs (npc_id, npc_name) VALUES (?, ?)", NPCS)
    cursor.executemany(
        """INSERT INTO vendors (vendor_id, node_id, npc_id, vendor_name)
           VALUES (?, ?, ?, ?)""",
        VENDORS,
    )
    cursor.executemany(
        """INSERT INTO dialogue_nodes (node_id, parent_node_id, npc_id)
           VALUES (?, ?, ?)""",
        DIALOGUE_NODES,
    )
    cursor.executemany(
        """INSERT INTO dialogues
           (node_id, dialogue_id, dialogue, translation_HAN, translation_POJ,
            audio_clip, npc_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        DIALOGUES,
    )
    cursor.executemany(
        """INSERT INTO options
           (node_id, option_id, option_TEXT, next_node_id, feedback_type)
           VALUES (?, ?, ?, ?, ?)""",
        OPTIONS,
    )
    cursor.executemany(
        """INSERT INTO events (option_id, event_id, event_type, metadata)
           VALUES (?, ?, ?, ?)""",
        EVENTS,
    )


def verify(cursor):
    expected_counts = {
        "npcs": ("npc_id", "npc_va_%", 16),
        "vendors": ("vendor_id", "v_va_%", 6),
        "dialogue_nodes": ("node_id", "n_va_%", 31),
        "dialogues": ("dialogue_id", "d_va_%", 31),
        "options": ("option_id", "o_va_%", 32),
        "events": ("event_id", "e_va_%", 6),
    }
    for table, (column, pattern, expected) in expected_counts.items():
        actual = cursor.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {column} LIKE ?", (pattern,)
        ).fetchone()[0]
        if actual != expected:
            raise RuntimeError(
                f"{table}: expected {expected} Voucher Adventure rows, got {actual}"
            )

    for vendor_id, node_id, npc_id, _ in VENDORS:
        actual = cursor.execute(
            "SELECT node_id, npc_id FROM vendors WHERE vendor_id = ?", (vendor_id,)
        ).fetchone()
        if actual != (node_id, npc_id):
            raise RuntimeError(f"Vendor mapping mismatch for {vendor_id}: {actual}")

    for node_id, _, _, _, _, audio_clip, _ in DIALOGUES:
        if not audio_clip:
            raise RuntimeError(f"Dialogue {node_id} has no audio_clip")
        audio_path = os.path.join(BASE_DIR, "audio-clips", os.path.basename(audio_clip))
        if not os.path.isfile(audio_path):
            raise RuntimeError(f"Dialogue {node_id} audio is missing: {audio_path}")

    review_npcs = [npc_id for npc_id, _ in NPCS if npc_id.endswith(("_B", "_C"))]
    placeholders = ",".join("?" for _ in review_npcs)
    review_vendors = cursor.execute(
        f"SELECT vendor_id FROM vendors WHERE npc_id IN ({placeholders})", review_npcs
    ).fetchall()
    if review_vendors:
        raise RuntimeError(f"Review-only NPCs must not be vendors: {review_vendors}")

    review_events = cursor.execute(
        """SELECT event_id FROM events
           WHERE option_id LIKE 'o_va_%_B' OR option_id LIKE 'o_va_%_C'"""
    ).fetchall()
    if review_events:
        raise RuntimeError(f"Review-only options must not have events: {review_events}")

    for option_id, _, event_type, metadata in EVENTS:
        payload = json.loads(metadata)
        if event_type == "VOUCHER_OFFER_REVEALED":
            if set(payload) != {"vendor_id", "offer_id", "vendor_index"}:
                raise RuntimeError(
                    f"Unexpected event metadata for {option_id}: {payload}"
                )
        elif event_type == "START_MINIGAME":
            if payload != {"minigame_id": "voucher_adventure"}:
                raise RuntimeError(
                    f"Unexpected minigame metadata for {option_id}: {payload}"
                )
        else:
            raise RuntimeError(f"Unexpected event type for {option_id}: {event_type}")
        next_node = cursor.execute(
            "SELECT next_node_id FROM options WHERE option_id = ?", (option_id,)
        ).fetchone()[0]
        if next_node != "":
            raise RuntimeError(f"Final option {option_id} must have an empty next_node")

    forbidden = cursor.execute(
        """SELECT event_id, event_type FROM events
           WHERE event_id LIKE 'e_va_%'
             AND event_type IN ('ADD_TO_INVENTORY', 'LESSON_COMPLETE')"""
    ).fetchall()
    if forbidden:
        raise RuntimeError(f"Voucher Adventure has forbidden events: {forbidden}")


def populate_database(path):
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Database not found: {path}")
    with sqlite3.connect(path) as connection:
        cursor = connection.cursor()
        populate(cursor)
        verify(cursor)
    print(f"Populated and verified: {path}")


def generate_guide_audio():
    """Generate the approved Guide clip from its POJ text."""
    from models.hok_tts import HokTTS

    tts = HokTTS()
    for node_id, poj in GUIDE_AUDIO_INPUTS:
        tts.generate_tts(node_id, poj)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        choices=("all", "test", "lesson"),
        default="all",
        help="Database to update (default: all)",
    )
    parser.add_argument(
        "--generate-guide-audio",
        action="store_true",
        help="Generate the Voucher Guide WAV file from its POJ text",
    )
    args = parser.parse_args()
    if args.generate_guide_audio:
        generate_guide_audio()
    targets = (
        DATABASES.values() if args.database == "all" else [DATABASES[args.database]]
    )
    for path in targets:
        populate_database(path)


if __name__ == "__main__":
    main()
