import glob
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from import_unity_quizzes import QUIZ_DIR, AUDIO_DIR, convert_bank, level_id  # noqa: E402


class TestLevelId:
    """Must match HokkienQuizLauncher.BuildBackendLevelId in Unity."""

    def test_numeric_level(self):
        assert level_id("0") == "level_0"
        assert level_id(" 4 ") == "level_4"

    def test_named_level(self):
        assert level_id("Tutorial") == "tutorial"
        assert level_id("Voucher Adventure") == "voucher_adventure"


class TestConvertBank:

    ENTRY = {
        "question": "How do you say \"One please.\"?\n",
        "choices": ["我要一个 ", "打三折", "English only"],
        "choiceHokkienRomanizedTexts": ["Guá beh chi̍t-ê", "Phah saⁿ-chiat"],
        "choiceAudioResourcePaths": ["HokkienQuizAudio/level0_one", "", None],
        "choiceExplanations": ["一 = 1 = one"],
        "correctAnswerIndex": 0,
    }

    def convert(self):
        return convert_bank([self.ENTRY], lambda r: f"/unity/Resources/{r}.wav")

    def test_choice_fields(self):
        questions, _ = self.convert()
        first = questions[0]["choices"][0]
        assert first == {"text": "我要一个", "poj": "Guá beh chi̍t-ê",
                         "audio": "/audio-clips/level0_one.wav", "explanation": "一 = 1 = one"}

    def test_missing_entries_become_empty(self):
        questions, _ = self.convert()
        assert questions[0]["choices"][2] == {"text": "English only", "poj": "", "audio": "", "explanation": ""}

    def test_question_stripped_and_answer_kept(self):
        questions, audio = self.convert()
        assert questions[0]["question"] == "How do you say \"One please.\"?"
        assert questions[0]["correct_answer_index"] == 0
        assert audio == ["/unity/Resources/HokkienQuizAudio/level0_one.wav"]


QUIZ_FILES = sorted(glob.glob(os.path.join(QUIZ_DIR, "*.json")))


@pytest.mark.parametrize("path", QUIZ_FILES, ids=os.path.basename)
def test_quiz_files_are_complete(path):
    with open(path, encoding="utf-8") as f:
        quiz = json.load(f)
    assert quiz["quiz_id"] == os.path.basename(path)[:-5]
    for q in quiz["questions"]:
        assert 0 <= q["correct_answer_index"] < len(q["choices"])
        for c in q["choices"]:
            assert c["text"]
            if c["audio"]:
                assert os.path.isfile(os.path.join(AUDIO_DIR, os.path.basename(c["audio"]))), c["audio"]
