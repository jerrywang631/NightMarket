"""
GET /api/v1/dialogue/<node_id> returns each option's translation_HAN /
translation_POJ / audio, so Unity uses the stored Hokkien instead of
re-translating the option on every visit.
"""

import sqlite3

import pytest

from managers.dialogue_manager import Dialogue_Manager


@pytest.fixture
def dm(tmp_path):
    path = tmp_path / "options.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE dialogues (node_id TEXT, dialogue_id TEXT, dialogue TEXT, "
                "translation_HAN TEXT, translation_POJ TEXT, audio_clip TEXT, npc_id TEXT)")
    con.execute("CREATE TABLE dialogue_nodes (node_id TEXT, parent_node_id TEXT, npc_id TEXT)")
    con.execute("CREATE TABLE options (node_id TEXT, option_id TEXT, option_TEXT TEXT, "
                "next_node_id TEXT, feedback_type TEXT)")
    con.execute("CREATE TABLE events (option_id TEXT, event_id TEXT, event_type TEXT, metadata TEXT)")
    con.execute("CREATE TABLE words (dialogue_id TEXT, word_id TEXT, word TEXT, translation TEXT, "
                "context TEXT, audio_clip TEXT)")
    con.execute("CREATE TABLE option_translations (option_id TEXT, translation_HAN TEXT, "
                "translation_POJ TEXT, audio_clip TEXT)")
    con.execute("INSERT INTO dialogues VALUES ('n_q', 'd_q', 'Size?', '', '', '', 'npc_1')")
    con.execute("INSERT INTO options VALUES ('n_q', 'o_big', 'Large please! / 大杯！', 'n_next', 'positive')")
    con.execute("INSERT INTO options VALUES ('n_q', 'o_new', 'Small please! / 小杯！', 'n_next', 'positive')")
    con.execute("INSERT INTO option_translations VALUES ('o_big', '大杯！', 'Tōa-poe--ê!', "
                "'audio-clips/n_l4_v1_large.wav')")
    con.commit()
    con.close()

    manager = Dialogue_Manager(1)
    manager.db.db_path = str(path)
    return manager


def options(dm):
    return {o["option_id"]: o for o in dm.get_dialogue_node("n_q")["options"]}


def test_stored_translation_is_returned(dm):
    big = options(dm)["o_big"]
    assert big["translation_HAN"] == "大杯！"
    assert big["translation_POJ"] == "Tōa-poe--ê!"
    assert big["audio"] == "/audio-clips/n_l4_v1_large.wav"


def test_option_without_translation_returns_empty(dm):
    new = options(dm)["o_new"]
    assert (new["translation_HAN"], new["translation_POJ"], new["audio"]) == ("", "", "")
