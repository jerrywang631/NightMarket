"""
Tests for HokTranslation's tokenization and output handling, without loading the 7B model.

Background: under transformers 5, AutoTokenizer converts this model's tokenizer.model
into a tokenizer with no "▁" word boundaries or byte fallback, so prompts were
mis-tokenized and output came back as "N oh k ám - k ak s ng" (or, with the old
decode(), with no spaces at all and o͘/Ū turned into "Í\\x98"/"Åª").

The module imports transformers/torch, so this file is skipped where they aren't
installed (e.g. the Render build). Tokenizer tests also need tokenizer.model in the
local Hugging Face cache.
"""

import pytest

pytest.importorskip("transformers")
pytest.importorskip("sentencepiece")
from models.hok_translation import HokTranslation, load_sentencepiece

MODEL_DIR = "Bohanlu/Taigi-Llama-2-Translator-7B"


@pytest.fixture(scope="module")
def translator():
    try:
        sp = load_sentencepiece(MODEL_DIR, local_files_only=True)
    except Exception:
        pytest.skip("tokenizer.model is not in the local Hugging Face cache")
    t = object.__new__(HokTranslation)
    t.sp = sp
    return t


class TestSentencePiece:

    @pytest.mark.parametrize("text", [
        "Thâu-ke hó!",
        "Kàu hit ē-po͘, Ū i-tio̍h thò͘-lō͘.",
        "m̄-thang chi̍t-ê siⁿ",
        "頭家好！",
    ])
    def test_roundtrip_is_lossless(self, translator, text):
        sp = translator.sp
        assert sp.decode(sp.encode(text)).strip() == text

    def test_words_keep_boundary_markers(self, translator):
        pieces = translator.sp.id_to_piece(translator.sp.encode("Bô iàu-kín"))
        assert "▁i" in pieces  # transformers 5 produced ['B', 'ô', 'i', ...]

    def test_prompt_starts_with_bos_then_bracket(self, translator):
        ids = translator.encode_prompt("Greetings.", "POJ")
        assert ids[0] == translator.sp.bos_id()
        # LlamaTokenizer(legacy=False): no "▁" right after <s>
        assert translator.sp.id_to_piece(ids[1]) == "["

    def test_prompt_ends_with_target_tag(self, translator):
        ids = translator.encode_prompt("Hello!", "POJ")
        assert translator.sp.decode(ids[1:]).endswith("[/TRANS]\n[POJ]\n")


class TestClean:

    def test_cuts_at_closing_tag(self):
        assert HokTranslation.clean("Thâu-ke hó!\n[/POJ]\nextra") == "Thâu-ke hó!"

    def test_collapses_whitespace(self):
        assert HokTranslation.clean("  Kàu  hit\nē-po͘ ") == "Kàu hit ē-po͘"

    def test_no_spaces_between_han(self):
        assert HokTranslation.clean("頭家 好！") == "頭家好！"

    def test_keeps_space_between_han_and_poj(self):
        assert HokTranslation.clean("頭家好！ Thâu-ke hó!") == "頭家好！ Thâu-ke hó!"

    def test_space_after_punctuation(self):
        assert HokTranslation.clean("Lâi!To-siā hō͘-thāi!") == "Lâi! To-siā hō͘-thāi!"
        assert HokTranslation.clean("Tio̍h,lāi-té ū gû-bah.Pháiⁿ-sè!") == "Tio̍h, lāi-té ū gû-bah. Pháiⁿ-sè!"

    def test_punctuation_runs_and_digits_untouched(self):
        assert HokTranslation.clean("siáⁿ-mih?!") == "siáⁿ-mih?!"
        assert HokTranslation.clean("1.5 kho͘") == "1.5 kho͘"

    def test_space_after_punctuation_is_poj_only(self):
        assert HokTranslation.clean("頭家，好！") == "頭家，好！"


class TestValidate:

    def test_normal_translation_passes(self):
        HokTranslation.validate("Thâu-ke hó!", "Greetings.")

    def test_runaway_output_is_rejected(self):
        # "Greatings." produced a 326-char story in production
        with pytest.raises(ValueError, match="rejected"):
            HokTranslation.validate("Âng-chhun chêng, " * 20, "Greatings.")

    def test_empty_output_is_rejected(self):
        with pytest.raises(ValueError):
            HokTranslation.validate("", "Hi.")
