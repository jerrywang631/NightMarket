"""
Tests for the POJ screening rules in check_poj.py. These pin the rule behaviour:
changing it between the before/after runs would make F and F' incomparable.
"""

import pytest

from check_poj import flags_for


# Correctly formatted POJ: level 1 quiz choices and output of the fixed translator
WELL_FORMED = [
    "Lāu-pán hó", "Chóaⁿ bōe?", "Lí beh gōa-chōe?", "Chhiáⁿ-mn̄g, che sī siánn-mih?",
    "Ông-lâi-so͘", "Tâng-á-bí-ko", "Ō͘-kué-khiau", "Pe̍h-thn̂g-kué",
    "chhéng-an", "âng-chhài-thâu chhiáⁿ--chi̍t-kóa!", "To-siā lí chiau-thāi.",
    "Lāu-pô--á hó!", "Thâu-ke hó!",
]


@pytest.mark.parametrize("poj", WELL_FORMED)
def test_well_formed_poj_is_not_flagged(poj):
    assert flags_for("Some English text here.", poj) == []


@pytest.mark.parametrize("poj", [
    "Lísiūⁿ-behchia̍hsiáⁿ-mihthn̂g-á?",   # syllables run together
    "Chia-líkhì.",                        # lí + khì joined
    "Ē-chhiú!To-siā!",                    # no space after "!"
])
def test_run_together_words_are_flagged(poj):
    assert "no_spaces" in flags_for("x", poj)


def test_missing():
    assert flags_for("Hello.", "") == ["missing"]
    assert flags_for("Hello.", None) == ["missing"]


def test_mojibake():
    assert "mojibake" in flags_for("Hello.", "ÔÍ\x98!Lâi--ah")
    assert "mojibake" in flags_for("Hello.", "Åªi-tio̍h")


def test_too_long():
    assert "too_long" in flags_for("Greatings.", "Âng-chhun chêng, " * 10)


def test_untranslated():
    assert "untranslated" in flags_for("30% sugar please.", "30%sugarplease.")


def test_han_in_poj():
    assert "han_in_poj" in flags_for("$5 or $12.", "5êiah是12ê。")
