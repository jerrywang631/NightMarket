# Load model directly
from huggingface_hub import hf_hub_download
from sentencepiece import SentencePieceProcessor
from sentencepiece import sentencepiece_model_pb2
from transformers import AutoModelForCausalLM
import torch
import re


def load_sentencepiece(model_dir, **kwargs):
    """Load the repo's tokenizer.model the way LlamaTokenizer(legacy=False) does.

    This repo ships only tokenizer.model, and transformers 5 converts it into a
    tokenizer with no "▁" word boundaries and no byte fallback ("Greetings." became
    G/reet/ings, "Bô iàu" lost its space, o͘ and Ū were dropped). Every prompt reached
    the model mis-tokenized, and decoding put a space between every token. Reading
    tokenizer.model with SentencePiece avoids that conversion entirely.
    """
    path = hf_hub_download(model_dir, "tokenizer.model", **kwargs)
    proto = sentencepiece_model_pb2.ModelProto.FromString(open(path, "rb").read())
    # legacy=False: text right after <s> gets no leading "▁"
    proto.normalizer_spec.add_dummy_prefix = False
    sp = SentencePieceProcessor()
    sp.LoadFromSerializedProto(proto.SerializeToString())
    return sp


class HokTranslation:
    def __init__(self):
        self.model_dir = "Bohanlu/Taigi-Llama-2-Translator-7B"  # or "Bohanlu/Taigi-Llama-2-Translator-13B" for the 13B model
        self.sp = load_sentencepiece(self.model_dir)
        self.pad_id = self.sp.piece_to_id("<pad>")
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_dir, torch_dtype=torch.float16, device_map="auto", trust_remote_code=True
        )

    def encode_prompt(self, source_sentence: str, target_language: str) -> list:
        prompt = f"[TRANS]\n{source_sentence}\n[/TRANS]\n[{target_language}]\n"
        return [self.sp.bos_id()] + self.sp.encode(prompt)

    def translate(self, source_sentence: str, target_language: str) -> str:
        print(f"[TRANSLATE] Input: '{source_sentence}' -> target: {target_language}")
        input_ids = torch.tensor(
            [self.encode_prompt(source_sentence, target_language)],
            device=self.model.device,
        )
        with torch.no_grad():
            output = self.model.generate(
                input_ids,
                attention_mask=torch.ones_like(input_ids),
                max_new_tokens=256,
                repetition_penalty=1.1,
                # The repo's generation_config samples (temperature 0.6); greedy decoding
                # makes the same input always give the same POJ, so runs are reproducible.
                do_sample=False,
                eos_token_id=[self.sp.eos_id(), self.pad_id],
                pad_token_id=self.pad_id,
            )
        out = self.sp.decode(output[0, input_ids.shape[1]:].tolist())
        print(f"[TRANSLATE] Raw: {out!r}")
        text = self.clean(out)
        print(f"[TRANSLATE] Result: {text}")
        self.validate(text, source_sentence)
        return text

    @staticmethod
    def clean(out: str) -> str:
        end_idx = out.find("[/")
        text = out if end_idx == -1 else out[:end_idx]
        text = re.sub(r"\s*\[.*?[A-Z]+.*?\]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        # The model often drops the space after punctuation ("Lâi!To-siā", "ê,cha̍p-jī").
        # The TTS has no "!" in its vocabulary, so without the space the two words are
        # read as one. Only ASCII punctuation: Han text uses full-width marks, no spaces.
        text = re.sub(r"([!?.,;:])(?=[^\W\d_])", r"\1 ", text)
        # Han characters have no word spaces between them
        return re.sub(r"(?<=[　-鿿＀-￯])\s+(?=[　-鿿＀-￯])", "", text)

    @staticmethod
    def validate(text: str, source_sentence: str):
        # Short or misspelled input (e.g. "Greatings.") can make the model ramble until
        # max_new_tokens; refuse to return that instead of saving it to the DB.
        if not text or len(text) > 4 * len(source_sentence) + 40:
            raise ValueError(
                f"Translation rejected ({len(text)} chars for a "
                f"{len(source_sentence)}-char input): {text[:80]!r}"
            )
