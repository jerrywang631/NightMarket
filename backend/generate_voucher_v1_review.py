"""Generate the internal v1 review manifest and optional draft audio.

The resulting JSON intentionally contains answers and must never be served by
the player API.
"""

import argparse
import json
import os

from voucher_adventure.content import (
    calculate_prices,
    content_catalog,
    get_offer_definition,
)


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BACKEND_DIR, "audio-clips")
DEFAULT_OUTPUT = os.path.join(BACKEND_DIR, "voucher_adventure_v1_review.json")
TTS_MODEL = "facebook/mms-tts-nan"


def local_audio_path(api_path):
    return os.path.join(BACKEND_DIR, api_path.lstrip("/").replace("/", os.sep))


def generate_audio(catalog):
    from models.hok_tts import HokTTS

    tts = HokTTS()
    generated_offer_nodes = set()
    for item in catalog:
        offer = get_offer_definition("v1", item["offer_id"])
        if offer["offer_node_id"] not in generated_offer_nodes:
            node_id = offer["offer_node_id"]
            poj = item["dialogue"]["offer"][2]
            print(f"Generating {node_id}.wav from POJ: {ascii(poj)}")
            tts.generate_tts(node_id, poj)
            generated_offer_nodes.add(node_id)
        if item["variant"] != "A":
            node_id = f"{offer['root_node_id']}_{item['variant']}"
            poj = item["dialogue"]["greet"][2]
            print(f"Generating {node_id}.wav from POJ: {ascii(poj)}")
            tts.generate_tts(node_id, poj)


def node_review(english, han, poj, audio, status):
    return {
        "english": english,
        "han": han,
        "poj": poj,
        "audio": audio,
        "audio_exists": os.path.isfile(local_audio_path(audio)),
        "language_review": "APPROVED",
        "audio_review": "APPROVED",
        "tts_model": TTS_MODEL,
        "tts_input": poj,
    }


def build_review_manifest():
    manifest = []
    for item in content_catalog("v1"):
        offer = get_offer_definition("v1", item["offer_id"])
        variant = item["variant"]
        base, _, bundle = calculate_prices(offer, variant)
        status = item["content_status"]
        greet = item["dialogue"]["greet"]
        offer_dialogue = item["dialogue"]["offer"]
        manifest.append(
            {
                "content_version": "v1",
                "offer_id": item["offer_id"],
                "variant": variant,
                "base_price_cents": base,
                "bundle_price_cents": bundle,
                "effective_unit_price_cents": bundle // offer["bundle_size"],
                "parameters": offer["parameters"],
                "bundle_size": offer["bundle_size"],
                "dialogue": {
                    "greet": node_review(
                        *greet,
                        item["dialogue"]["audio_greet"],
                        status,
                    ),
                    "offer": node_review(
                        *offer_dialogue,
                        item["dialogue"]["audio_offer"],
                        status,
                    ),
                },
                "questions": [
                    {
                        "skill": question["skill"],
                        "prompt_en": question["prompt_en"],
                        "correct_answer": question["answer"],
                        "answer_unit": "MONEY_CENTS",
                        "rule_hint": question["rule_hint"],
                        "formula_hint": question["formula_hint"],
                        "correct_feedback": question["correct_feedback"],
                        "misconceptions": question["misconceptions"],
                        "source_variant": question.get("source_variant"),
                    }
                    for question in item["questions"]
                ],
                "status": status,
                "approved": status == "APPROVED",
                "selectable_for_production": status == "APPROVED",
            }
        )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate-audio", action="store_true")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    catalog = content_catalog("v1")
    if args.generate_audio:
        generate_audio(catalog)

    manifest = build_review_manifest()
    with open(args.output, "w", encoding="utf-8") as output_file:
        json.dump(manifest, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")
    print(f"Wrote {len(manifest)} review entries to {args.output}")


if __name__ == "__main__":
    main()
