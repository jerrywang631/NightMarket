"""
Copy the Hokkien quiz banks from the Unity project into backend/quizzes/*.json, and
their pre-made choice audio into backend/audio-clips, so the game can load every
quiz from GET /api/v1/quizzes/<level_id> with no runtime translation or TTS.

Reads Assets/Hokkien/LessonContent/"<Level> Data.asset" (level name -> question
bank) and the "<Level> Questions.asset" banks. File names use the same level id
HokkienQuizLauncher.BuildBackendLevelId requests ("0" -> level_0, "Tutorial" ->
tutorial). Run it again after the banks change in Unity; a file's version goes up
only when its content changed.

    .venv\\Scripts\\python.exe backend/import_unity_quizzes.py
    .venv\\Scripts\\python.exe backend/import_unity_quizzes.py --unity D:\\path\\to\\LinguaQuestGame
"""

import argparse
import filecmp
import glob
import json
import os
import re
import shutil
import sys

import yaml

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BACKEND_DIR)
QUIZ_DIR = os.path.join(BACKEND_DIR, "quizzes")
AUDIO_DIR = os.path.join(BACKEND_DIR, "audio-clips")
LESSON_CONTENT = os.path.join("Assets", "Hokkien", "LessonContent")
AUDIO_EXTENSIONS = (".wav", ".mp3", ".ogg")


def level_id(level_name):
    """Same rule as HokkienQuizLauncher.BuildBackendLevelId."""
    normalized = re.sub(r"[^a-z0-9_-]+", "_", (level_name or "").strip().lower())
    return f"level_{int(normalized)}" if normalized.isdigit() else normalized


def load_unity_asset(path):
    """The MonoBehaviour fields of a single-object Unity .asset file."""
    with open(path, encoding="utf-8") as f:
        lines = [l for l in f.read().splitlines() if not l.startswith(("%", "---"))]
    return yaml.safe_load("\n".join(lines))["MonoBehaviour"]


def meta_guid(path):
    with open(path + ".meta", encoding="utf-8") as f:
        return re.search(r"^guid: (\w+)", f.read(), re.M).group(1)


def at(values, i):
    values = values or []
    value = values[i] if i < len(values) else None
    return (value or "").strip()


def convert_bank(questions, find_audio):
    """Unity QuizQuestionEntry list -> backend quiz questions (+ audio files used)."""
    out, audio_files = [], []
    for entry in questions or []:
        choices = []
        for i, text in enumerate(entry.get("choices") or []):
            resource = at(entry.get("choiceAudioResourcePaths"), i)
            audio = ""
            if resource:
                src = find_audio(resource)
                audio = "/audio-clips/" + os.path.basename(src)
                audio_files.append(src)
            choices.append({
                "text": (text or "").strip(),
                "poj": at(entry.get("choiceHokkienRomanizedTexts"), i),
                "audio": audio,
                "explanation": at(entry.get("choiceExplanations"), i),
            })
        out.append({
            "question": (entry.get("question") or "").strip(),
            "choices": choices,
            "correct_answer_index": entry.get("correctAnswerIndex", 0),
        })
    return out, audio_files


def resource_finder(unity_dir):
    resource_dirs = glob.glob(os.path.join(unity_dir, "Assets", "**", "Resources"), recursive=True)

    def find(resource):
        for d in resource_dirs:
            for ext in AUDIO_EXTENSIONS:
                path = os.path.join(d, *resource.split("/")) + ext
                if os.path.isfile(path):
                    return path
        raise FileNotFoundError(f"Resources audio '{resource}' not found under {unity_dir}")

    return find


def main():
    parser = argparse.ArgumentParser(description="Import Unity quiz banks into backend/quizzes.")
    parser.add_argument("--unity", default=os.path.join(os.path.dirname(REPO_DIR), "LinguaQuestGame"),
                        help="path to the LinguaQuestGame Unity project")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    content_dir = os.path.join(args.unity, LESSON_CONTENT)
    banks = {meta_guid(p): p for p in glob.glob(os.path.join(content_dir, "*.asset"))
             if "questions" in load_unity_asset(p)}
    find_audio = resource_finder(args.unity)
    os.makedirs(QUIZ_DIR, exist_ok=True)

    for data_path in sorted(glob.glob(os.path.join(content_dir, "*.asset"))):
        data = load_unity_asset(data_path)
        if "levelName" not in data:
            continue
        quiz_id = level_id(str(data["levelName"]))
        bank_path = banks.get((data.get("questionBank") or {}).get("guid"))
        if not bank_path:
            print(f"{os.path.basename(data_path)}: no question bank, skipped")
            continue

        questions, audio_files = convert_bank(load_unity_asset(bank_path)["questions"], find_audio)
        copied = 0
        for src in audio_files:
            dst = os.path.join(AUDIO_DIR, os.path.basename(src))
            if not (os.path.exists(dst) and filecmp.cmp(src, dst, shallow=False)):
                shutil.copy2(src, dst)
                copied += 1

        out_path = os.path.join(QUIZ_DIR, f"{quiz_id}.json")
        version = 1
        if os.path.exists(out_path):
            with open(out_path, encoding="utf-8") as f:
                old = json.load(f)
            same = old.get("questions") == questions
            version = old.get("version", 1) if same else old.get("version", 0) + 1
        quiz = {
            "quiz_id": quiz_id,
            "version": version,
            "source": os.path.relpath(bank_path, args.unity).replace("\\", "/"),
            "questions": questions,
        }
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(quiz, f, ensure_ascii=False, indent=2)
            f.write("\n")
        with_audio = sum(bool(c["audio"]) for q in questions for c in q["choices"])
        total = sum(len(q["choices"]) for q in questions)
        print(f"{quiz_id}.json v{version}: {len(questions)} questions, {with_audio}/{total} choices "
              f"with audio, {copied} audio files copied")


if __name__ == "__main__":
    main()
