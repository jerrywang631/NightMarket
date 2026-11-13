"""
GET /api/v1/dialogue/<node_id> returns dialogue.speaker_type (PLAYER / NPC) so
Unity shows who is talking instead of guessing from turn order.
"""

import sqlite3

import pytest

from managers.dialogue_manager import Dialogue_Manager

SEVEN_COLUMN_DIALOGUES = (
    "node_id TEXT, dialogue_id TEXT, dialogue TEXT, translation_HAN TEXT, "
    "translation_POJ TEXT, audio_clip TEXT, npc_id TEXT"
)


@pytest.fixture
def dm(tmp_path):
    """A Dialogue_Manager on a throwaway DB shaped like the lesson DB before
    speaker_type existed (7-column dialogues)."""
    path = tmp_path / "speaker.db"
    con = sqlite3.connect(path)
    con.execute(f"CREATE TABLE dialogues ({SEVEN_COLUMN_DIALOGUES})")
    con.execute("CREATE TABLE dialogue_nodes (node_id TEXT, parent_node_id TEXT, npc_id TEXT)")
    con.execute("CREATE TABLE options (node_id TEXT, option_id TEXT, option_TEXT TEXT, "
                "next_node_id TEXT, feedback_type TEXT)")
    con.execute("CREATE TABLE events (option_id TEXT, event_id TEXT, event_type TEXT, metadata TEXT)")
    con.execute("CREATE TABLE words (dialogue_id TEXT, word_id TEXT, word TEXT, translation TEXT, "
                "context TEXT, audio_clip TEXT)")
    con.execute("INSERT INTO dialogues VALUES ('n_a', 'd_a', 'Hi.', '你好。', 'Lí hó.', '', 'npc_1')")
    con.commit()
    con.close()

    manager = Dialogue_Manager(1)
    manager.db.db_path = str(path)
    return manager


def speaker(dm, node_id):
    return dm.get_dialogue_node(node_id)["dialogue"]["speaker_type"]


def test_old_db_without_column_returns_empty(dm):
    assert not dm.has_speaker_column()
    assert speaker(dm, "n_a") == ""


def test_set_adds_column_and_is_returned(dm):
    dm.set_speaker_type("n_a", "npc")
    assert dm.has_speaker_column()
    assert speaker(dm, "n_a") == "NPC"
    dm.set_speaker_type("n_a", "PLAYER")
    assert speaker(dm, "n_a") == "PLAYER"


def test_clear_and_invalid(dm):
    dm.set_speaker_type("n_a", "PLAYER")
    dm.set_speaker_type("n_a", "")
    assert speaker(dm, "n_a") == ""
    with pytest.raises(ValueError):
        dm.set_speaker_type("n_a", "vendor_x")


def test_every_lesson_line_has_a_speaker():
    lesson = Dialogue_Manager(2)
    assert lesson.has_speaker_column()
    rows = lesson.db.get_data(
        "SELECT node_id, speaker_type FROM dialogues WHERE node_id LIKE 'n_l%'")
    missing = [n for n, s in rows if s not in ("PLAYER", "NPC")]
    assert rows and not missing, f"lesson lines without speaker_type: {missing}"
