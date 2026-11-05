"""
Compare translator input sources on a few lesson lines (read-only, no DB writes):
English, the HAN column as stored (often simplified), and the HAN column converted
to Traditional Chinese. Also translates the first line twice to confirm that greedy
decoding gives identical output.

Run from the repo root with the .venv Python; stop any backend that loaded the models:
    .venv\\Scripts\\python.exe backend/compare_sources.py
"""

import argparse
import collections
import csv
import datetime
import os
import sqlite3
import sys
import time

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)
from check_poj import flags_for  # noqa: E402
from models.zh_convert import to_traditional  # noqa: E402

LINES = [
    "n_l0_pb_answer", "n_l4_v2_greet", "n_l0_pb_point", "n_l1_v3_price",
    "n_l3_v5_allergen_ask", "n_l4_v1_large", "n_l4_v2_red_bean", "n_l1_v2_explain",
    "n_l3_v3_explain", "n_l2_v4_order", "n_l3_v4_explain", "n_l3_v3_vendor_inside",
]


def main():
    today = datetime.date.today().isoformat()
    parser = argparse.ArgumentParser(description="Compare English / simplified / traditional input.")
    parser.add_argument("--out", default=os.path.join(
        REPO_DIR, "research", "regeneration", today, "source_comparison_3way.csv"))
    parser.add_argument("--limit", type=int, help="only the first N lines")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    db = sqlite3.connect(f"file:{os.path.join(BACKEND_DIR, 'database', 'hok_lesson_data.db')}?mode=ro", uri=True)
    lines = LINES[: args.limit] if args.limit else LINES
    print("Loading translation model...")
    from models.hok_translation import HokTranslation
    translator = HokTranslation()

    def run(text, english):
        t0 = time.time()
        try:
            poj = translator.translate(text, "POJ")
        except Exception as e:
            poj = f"<{type(e).__name__}: {str(e)[:60]}>"
        return poj, ";".join(flags_for(english, poj)), round(time.time() - t0, 1)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    totals = collections.defaultdict(lambda: [0, 0, 0.0])  # source -> [lines, flagged, seconds]
    with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["node_id", "source", "input", "poj", "flags", "seconds"])
        for i, node_id in enumerate(lines, 1):
            english, han = db.execute(
                "SELECT dialogue, translation_HAN FROM dialogues WHERE node_id = ?", (node_id,)
            ).fetchone()
            traditional = to_traditional(han)
            results = {}
            for source, text in (("english", english), ("chinese", han), ("traditional", traditional)):
                if source == "traditional" and traditional == han:
                    results[source] = results["chinese"]  # already traditional: same input
                else:
                    results[source] = run(text, english)
                poj, flags, secs = results[source]
                writer.writerow([node_id, source, text, poj, flags, secs])
                f.flush()
                totals[source][0] += 1
                totals[source][1] += bool(flags)
                totals[source][2] += secs
                print(f"[{i}/{len(lines)}] {node_id:22s} {source:11s} {text[:24]!r:28s} -> {poj!r} [{flags}] ({secs}s)")
            if i == 1:
                again = run(english, english)[0]
                same = again == results["english"][0]
                print(f"Determinism check: second run of {node_id} english is "
                      f"{'IDENTICAL' if same else 'DIFFERENT: ' + repr(again)}")

    print("\nsource       lines  flagged  avg seconds")
    for source, (n, flagged, secs) in totals.items():
        print(f"{source:12s} {n:5d}  {flagged:7d}  {secs / n:11.0f}")
    print("Saved", args.out)


if __name__ == "__main__":
    main()
