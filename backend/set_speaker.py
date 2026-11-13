"""
Set who says a dialogue line, so Unity shows the right name instead of guessing
from turn order. Adds the dialogues.speaker_type column on first use.

Run from the repo root:
    .venv\\Scripts\\python.exe backend/set_speaker.py n_l4_v3_explain NPC
    .venv\\Scripts\\python.exe backend/set_speaker.py n_l4_v3_taro_ball PLAYER n_l4_v3_explain NPC
    .venv\\Scripts\\python.exe backend/set_speaker.py n_l4_v3_explain ""      # clear: back to guessing
    .venv\\Scripts\\python.exe backend/set_speaker.py --csv speakers.csv      # columns node_id, speaker_type

Uses the lesson DB (hok_lesson_data.db); pass --test for hok_test_data.db.
"""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from managers.dialogue_manager import Dialogue_Manager  # noqa: E402

args = sys.argv[1:]
mode = 2
if "--test" in args:
    args.remove("--test")
    mode = 1
pairs = []
if "--csv" in args:
    i = args.index("--csv")
    path = args[i + 1] if i + 1 < len(args) else sys.exit(__doc__)
    del args[i:i + 2]
    with open(path, encoding="utf-8-sig") as f:
        pairs += [(row["node_id"], row["speaker_type"]) for row in csv.DictReader(f)]
if len(args) % 2:
    sys.exit(__doc__)
pairs += list(zip(args[0::2], args[1::2]))
if not pairs:
    sys.exit(__doc__)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

dm = Dialogue_Manager(mode)
for node_id, speaker in pairs:
    if not dm.get_dialogue(node_id):
        sys.exit(f"{node_id} not found; nothing written.")
    if (speaker or "").strip().upper() not in ("PLAYER", "NPC", ""):
        sys.exit(f"{node_id}: speaker_type {speaker!r} must be PLAYER, NPC or empty; nothing written.")
for node_id, speaker in pairs:
    dm.set_speaker_type(node_id, speaker)
    text = dm.get_dialogue_node(node_id)["dialogue"]
    print(f"{node_id}: speaker_type={text['speaker_type'] or '(empty)'}  {text['text']}")
print(f"\n{len(pairs)} lines set.")
