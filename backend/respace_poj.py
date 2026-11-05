"""
Apply HokTranslation.clean() to the POJ already stored for lesson lines, without
re-translating, and regenerate the audio of every line whose text changed.

The 2026-10-25 regeneration was run before clean() put a space after punctuation,
so 26 lines read like "Lâi!To-siā" (the TTS drops "!" and runs the words together).
Without --apply this only prints the changes.

Run from the repo root with the .venv Python:
    .venv\\Scripts\\python.exe backend/respace_poj.py            # preview
    .venv\\Scripts\\python.exe backend/respace_poj.py --apply    # write DB + audio
"""

import argparse
import csv
import datetime
import os
import shutil
import sys
import time

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)
from managers.dialogue_manager import Dialogue_Manager, audio_filename  # noqa: E402
from models.hok_translation import HokTranslation  # noqa: E402
from regenerate_poj import lesson_nodes  # noqa: E402

LOG_FIELDS = ["node_id", "old_poj", "new_poj", "status", "seconds"]


def main():
    today = datetime.date.today().isoformat()
    parser = argparse.ArgumentParser(description="Re-clean stored lesson POJ and redo its audio.")
    parser.add_argument("--apply", action="store_true", help="write the DB and audio (default: preview)")
    parser.add_argument("--out", default=os.path.join(REPO_DIR, "research", "regeneration", f"{today}-respace"),
                        help="folder for log.csv and the DB backup")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    dm = Dialogue_Manager(2)
    changes = []
    for node_id in lesson_nodes(dm):
        _, _, english, han, old_poj, _, _ = dm.get_dialogue(node_id)[0][:7]
        new_poj = HokTranslation.clean(old_poj or "")
        if new_poj != (old_poj or ""):
            changes.append((node_id, english, han, old_poj, new_poj))
    for node_id, _, _, old, new in changes:
        print(f"{node_id}\n  old: {old}\n  new: {new}")
    print(f"\n{len(changes)} lesson lines change.")
    if not changes or not args.apply:
        if changes:
            print("Preview only; run again with --apply to write the DB and regenerate audio.")
        return

    os.makedirs(args.out, exist_ok=True)
    log_path = os.path.join(args.out, "log.csv")
    if os.path.exists(log_path):
        sys.exit(f"{log_path} already exists; use a new --out folder.")
    backup = os.path.join(args.out, f"hok_lesson_data.before-{datetime.datetime.now():%H%M%S}.db")
    shutil.copy2(dm.db.db_path, backup)
    print(f"DB backup: {backup}\nLoading TTS model...")
    from models.hok_tts import HokTTS
    tts = HokTTS()

    failed = 0
    with open(log_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        writer.writeheader()
        for i, (node_id, english, han, old_poj, new_poj) in enumerate(changes, 1):
            t0 = time.time()
            try:
                audio = "audio-clips/" + audio_filename(tts.generate_tts(node_id, new_poj))
                dm.update_dialogue(node_id, english, han, new_poj, audio)
                status = "ok"
            except Exception as e:  # keep the old POJ and audio together
                status, failed = f"error: {type(e).__name__}: {e}", failed + 1
            seconds = round(time.time() - t0, 1)
            writer.writerow({"node_id": node_id, "old_poj": old_poj, "new_poj": new_poj,
                             "status": status, "seconds": seconds})
            f.flush()
            print(f"[{i}/{len(changes)}] {node_id}: {status} ({seconds}s)")

    print(f"\nDone: {len(changes) - failed} ok, {failed} failed. Log: {log_path}")
    print(f"Next: python backend/check_poj.py --out research/after-fix/{today}")


if __name__ == "__main__":
    main()
