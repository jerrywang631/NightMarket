"""Tests for the simplified -> traditional converter used before translation."""

import pytest

from models.zh_convert import CHARS, to_traditional


@pytest.mark.parametrize("simplified, traditional", [
    ("老板好！", "老闆好！"),
    ("这是担仔面！细面条配上鲜美的虾汤。", "這是擔仔麵！細麵條配上鮮美的蝦湯。"),
    ("这是台湾牛肉面！", "這是台灣牛肉麵！"),
    ("里面有肉燥、虾子还有卤蛋！", "裡面有肉燥、蝦子還有滷蛋！"),
    ("没关系，我要一个。", "沒關係，我要一個。"),
    ("加红豆！然后多放一点糖水！", "加紅豆！然後多放一點糖水！"),
    ("完全没有海鲜！只有猪肉、酱油和香料。", "完全沒有海鮮！只有豬肉、醬油和香料。"),
    ("这个里面有牛肉吗？我对牛肉过敏。", "這個裡面有牛肉嗎？我對牛肉過敏。"),
])
def test_converts_lesson_lines(simplified, traditional):
    assert to_traditional(simplified) == traditional


def test_traditional_input_is_unchanged():
    for text in ("這是鳳梨酥。", "彼爿的擔仔位，", "Thâu-ke hó!"):
        assert to_traditional(text) == text


def test_empty_input():
    assert to_traditional("") == ""
    assert to_traditional(None) is None


def test_table_has_no_identity_or_non_han_entries():
    # Guards against the two zip() strings drifting out of alignment
    for s, t in CHARS.items():
        assert s != t
        assert "一" <= s <= "鿿" and "一" <= t <= "鿿"
    # first, middle and last pairs of the table
    assert (CHARS["东"], CHARS["酱"], CHARS["爱"], CHARS["迟"]) == ("東", "醬", "愛", "遲")
