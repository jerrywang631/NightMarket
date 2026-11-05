"""
Regenerate POJ and its audio for every lesson line with the fixed translator.

Each line is written to the DB as soon as it is done, and logged to <out>/log.csv.
Running the same command again skips lines already in the log, so an interrupted
run can simply be restarted. If the translator rejects its output (empty or
runaway), the old POJ and audio are kept and the rejection is logged.

Run from the repo root with the .venv Python. Stop any local backend that loaded
the ML models first (two copies of the 7B model do not fit in memory).

    .venv\\Scripts\\python.exe backend/regenerate_poj.py --limit 3     # try a few lines
    .venv\\Scripts\\python.exe backend/regenerate_poj.py               # everything left
    .venv\\Scripts\\python.exe backend/regenerate_poj.py --only n_l3_v1_greet
"""

import argparse
import csv
import datetime
import os
import shutil
import socket
import sys
import time

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)
from managers.dialogue_manager import Dialogue_Manager, audio_filename  # noqa: E402
from models.zh_convert import to_traditional  # noqa: E402

LOG_FIELDS = ["node_id", "english", "source_text", "old_poj", "new_poj", "status", "seconds"]
SOURCES = ("traditional", "chinese", "english")


def source_text(source, english, han):
    """Translator input for a line; falls back to English when the HAN column is empty."""
    if source == "english" or not (han or "").strip():
        return english
    return to_traditional(han) if source == "traditional" else han


def lesson_nodes(dm):
    rows = dm.db.get_data(
        "SELECT node_id FROM dialogues WHERE node_id LIKE 'n_l%' ORDER BY node_id"
    )
    return [r[0] for r in rows]


def regenerate_line(dm, translator, tts, node_id, source="traditional"):
    """Returns (english, text, old_poj, new_poj, status). Only writes the DB on success."""
    _, _, english, han, old_poj, _, _ = dm.get_dialogue(node_id)[0][:7]
    text = source_text(source, english, han)
    if not (text or "").strip():
        return english, text, old_poj, "", "skipped: no source text"
    try:
        new_poj = translator.translate(text, "POJ")
    except ValueError as e:
        return english, text, old_poj, "", f"rejected: {e}"
    except Exception as e:
        return english, text, old_poj, "", f"error: {type(e).__name__}: {e}"

    status, audio = "ok", ""
    try:
        audio = "audio-clips/" + audio_filename(tts.generate_tts(node_id, new_poj))
    except Exception as e:
        status = f"ok, audio failed: {type(e).__name__}: {e}"
    dm.update_dialogue(node_id, english, han, new_poj, audio)
    return english, text, old_poj, new_poj, status


def backend_is_running():
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", 8000)) == 0


def main():
    today = datetime.date.today().isoformat()
    parser = argparse.ArgumentParser(description="Regenerate lesson POJ and audio.")
    parser.add_argument("--out", default=os.path.join(REPO_DIR, "research", "regeneration", today),
                        help="folder for log.csv and the DB backup")
    parser.add_argument("--limit", type=int, help="only process this many lines")
    parser.add_argument("--only", nargs="+", metavar="NODE_ID",
                        help="process these lines, even if already in the log")
    parser.add_argument("--source", choices=SOURCES, default="traditional",
                        help="translator input: HAN converted to Traditional Chinese (default), "
                             "HAN as stored, or English")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    dm = Dialogue_Manager(2)
    nodes = lesson_nodes(dm)
    log_path = os.path.join(args.out, "log.csv")
    if args.only:
        unknown = sorted(set(args.only) - set(nodes))
        if unknown:
            sys.exit(f"Not lesson lines: {', '.join(unknown)}")
        todo = [n for n in nodes if n in set(args.only)]
    else:
        done = set()
        if os.path.exists(log_path):
            with open(log_path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames and reader.fieldnames != LOG_FIELDS:
                    sys.exit(f"{log_path} was written by an older version of this script; "
                             "use a new --out folder.")
                done = {row["node_id"] for row in reader}
        todo = [n for n in nodes if n not in done]
    if args.limit:
        todo = todo[: args.limit]
    if not todo:
        print("Nothing to do: every lesson line is already in", log_path)
        return

    os.makedirs(args.out, exist_ok=True)
    backup = os.path.join(args.out, f"hok_lesson_data.before-{datetime.datetime.now():%H%M%S}.db")
    shutil.copy2(dm.db.db_path, backup)
    print(f"{len(todo)} of {len(nodes)} lesson lines to process (source: {args.source}). "
          f"DB backup: {backup}")
    if backend_is_running():
        print("WARNING: something is listening on port 8000. If it is a backend with ML "
              "models loaded, stop it (Ctrl+C) to avoid running out of memory.")

    print("Loading translation and TTS models...")
    from models.hok_translation import HokTranslation
    from models.hok_tts import HokTTS
    translator, tts = HokTranslation(), HokTTS()

    new_log = not os.path.exists(log_path)
    started = time.time()
    counts = {"ok": 0, "rejected": 0, "other": 0}
    with open(log_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new_log:
            writer.writeheader()
        for i, node_id in enumerate(todo, 1):
            t0 = time.time()
            english, text, old_poj, new_poj, status = regenerate_line(
                dm, translator, tts, node_id, args.source)
            seconds = round(time.time() - t0, 1)
            writer.writerow({"node_id": node_id, "english": english, "source_text": text,
                             "old_poj": old_poj, "new_poj": new_poj, "status": status,
                             "seconds": seconds})
            f.flush()
            key = "ok" if status.startswith("ok") else "rejected" if status.startswith("rejected") else "other"
            counts[key] += 1
            eta = (time.time() - started) / i * (len(todo) - i) / 60
            print(f"[{i}/{len(todo)}] {node_id}: {status[:60]} | {new_poj[:50]!r} "
                  f"({seconds}s, ~{eta:.0f} min left)")

    print(f"\nDone: {counts['ok']} ok, {counts['rejected']} rejected (old POJ kept), "
          f"{counts['other']} other. Log: {log_path}")
    print(f"Next: python backend/check_poj.py --out research/after-fix/{today}")


if __name__ == "__main__":
    main()
