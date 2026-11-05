"""
Rule-based screening of dialogue POJ (the "screening script" behind F, F', D, P, R).

Flags each lesson line (dialogues.node_id LIKE 'n_l%') with any of the rules below.
Keep RULES_VERSION and the rules unchanged between the before/after runs so that
F = f / N and F' = f' / N are comparable, and do not tune them after seeing reviewer
results (that would bias P and R).

Usage (from the repo root):
    python backend/check_poj.py --rev b40d52f --out research/baseline/2026-10-22
    python backend/check_poj.py --out research/after-fix/<date>        # current DB file
"""

import argparse
import collections
import csv
import datetime
import hashlib
import os
import re
import sqlite3
import subprocess
import tempfile
import unicodedata

RULES_VERSION = "2026-10-22"
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BACKEND_DIR, "database", "hok_lesson_data.db")
DB_GIT_PATH = "backend/database/hok_lesson_data.db"

RULES = {
    "missing": "POJ is empty.",
    "mojibake": "Contains C1 control characters or UTF-8 bytes read as Latin-1 "
                "(e.g. 'Í\\x98' for the dot in o͘, 'Åª' for Ū).",
    "no_spaces": "Words run together: a space/hyphen/punctuation-separated segment holds "
                 "2+ syllables (2+ vowel groups or 2+ tone marks), or a letter directly "
                 "follows sentence punctuation (e.g. 'Ē-chhiú!To-siā!').",
    "too_long": "Longer than 4 x the English length + 40 characters "
                "(same limit as HokTranslation.validate).",
    "untranslated": "Equals the English source once spaces, punctuation and case are removed.",
    "han_in_poj": "Contains Han characters.",
}
LIMITATIONS = [
    "Rules check form only, not meaning: a well-formed but wrong translation "
    "(e.g. 老板好 -> 'Lāu-pô--á hó') is not flagged, so F is a lower bound.",
    "no_spaces misses joins where two syllables' vowels touch (e.g. 'ê' + 'iah' -> 'êiah').",
    "N counts every lesson line, including lines with empty POJ (flagged as missing) "
    "and WIP or test content inside a lesson tree.",
]

TONE_MARKS = {"̀", "́", "̂", "̄", "̍", "̆", "̌"}
SEPARATORS = r"[\s\-‐–—.,!?;:，。！？、“”\"'()（）…/|]+|[一-鿿\d$%]+"
HAN = re.compile(r"[一-鿿]")


def _joined_syllables(segment):
    nfd = unicodedata.normalize("NFD", segment.lower())
    base = "".join(ch for ch in nfd if not unicodedata.combining(ch))
    vowel_groups = re.findall(r"[aeiou]+", base)
    tone_marks = sum(1 for ch in nfd if ch in TONE_MARKS)
    return len(vowel_groups) >= 2 or tone_marks >= 2


def has_run_together_words(poj):
    if re.search(r"[!?.,;:！？。，](?=[^\W\d_])", poj):
        return True
    return any(_joined_syllables(s) for s in re.split(SEPARATORS, poj) if s)


def flags_for(english, poj):
    english, poj = english or "", (poj or "").strip()
    if not poj:
        return ["missing"]
    found = []
    if re.search("[\x80-\x9f]|Å[\x80-\xbf]", poj):
        found.append("mojibake")
    if has_run_together_words(poj):
        found.append("no_spaces")
    if len(poj) > 4 * len(english) + 40:
        found.append("too_long")
    normalize = lambda s: re.sub(r"[\W_]+", "", s).lower()
    if normalize(poj) and normalize(poj) == normalize(english):
        found.append("untranslated")
    if HAN.search(poj):
        found.append("han_in_poj")
    return found


def load_db(rev):
    """Return (path to a readable DB file, source label)."""
    if not rev:
        return DB_PATH, f"working copy {DB_GIT_PATH}"
    data = subprocess.run(
        ["git", "show", f"{rev}:{DB_GIT_PATH}"],
        cwd=BACKEND_DIR, capture_output=True, check=True,
    ).stdout
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.write(data)
    tmp.close()
    commit = subprocess.run(
        ["git", "rev-parse", "--short", rev], cwd=BACKEND_DIR, capture_output=True, text=True,
    ).stdout.strip()
    return tmp.name, f"git {commit}:{DB_GIT_PATH}"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--rev", help="git revision to read the DB from (default: working copy)")
    parser.add_argument("--out", required=True, help="output directory")
    args = parser.parse_args()

    path, source = load_db(args.rev)
    with open(path, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    rows = db.execute(
        "SELECT node_id, npc_id, dialogue, translation_HAN, translation_POJ "
        "FROM dialogues WHERE node_id LIKE 'n_l%' ORDER BY node_id"
    ).fetchall()
    db.close()
    if args.rev:
        os.unlink(path)

    os.makedirs(args.out, exist_ok=True)
    results = [(row, flags_for(row[2], row[4])) for row in rows]
    with open(os.path.join(args.out, "poj_flags.csv"), "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["node_id", "npc_id", "english", "han", "poj", "flagged", "flags"])
        for (node_id, npc_id, en, han, poj), found in results:
            writer.writerow([node_id, npc_id, en, han, poj, int(bool(found)), ";".join(found)])

    n = len(results)
    f_count = sum(1 for _, found in results if found)
    per_rule = collections.Counter(flag for _, found in results for flag in found)
    lines = [
        "# POJ screening summary",
        "",
        f"- Generated: {datetime.date.today().isoformat()}",
        f"- Source: {source}",
        f"- DB SHA-256: {sha256}",
        f"- Rules version: {RULES_VERSION}",
        "- Scope: lesson lines (`dialogues.node_id LIKE 'n_l%'`)",
        "",
        "| | |",
        "|---|---|",
        f"| N (lines) | {n} |",
        f"| f (lines with ≥1 flag) | {f_count} |",
        f"| F = f / N | {f_count / n:.1%} |",
        "",
        "| Rule | Lines | Definition |",
        "|---|---|---|",
    ]
    lines += [f"| {k} | {per_rule.get(k, 0)} | {v} |" for k, v in RULES.items()]
    lines += ["", "Known limitations:", ""] + [f"- {item}" for item in LIMITATIONS]
    with open(os.path.join(args.out, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"N={n} f={f_count} F={f_count / n:.1%} -> {args.out}")


if __name__ == "__main__":
    main()
