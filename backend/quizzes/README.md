# Backend quiz content

Quiz content lives here instead of in `hok_lesson_data.db`. Unity requests it
from `GET /api/v1/quizzes/<level_id>` whenever a quiz starts, and only falls back
to its local question bank if the request fails.

The files are generated from the Unity question banks
(`Assets/Hokkien/LessonContent/* Questions.asset`) by
`backend/import_unity_quizzes.py`, which also copies each choice's pre-made audio
into `backend/audio-clips`. Edit the banks in Unity and re-run the script rather
than editing these files by hand; a file's `version` goes up when its questions change.

File names follow `HokkienQuizLauncher.BuildBackendLevelId`: level name `0` →
`level_0.json`, `Tutorial` → `tutorial.json`.

Each choice has:

| Field | Meaning |
|---|---|
| `text` | What the button shows (Chinese, English, or both) |
| `poj` | Hokkien POJ shown under `text`; empty for non-Hokkien choices |
| `audio` | Server-relative WAV URL (`/audio-clips/...`); empty for no audio |
| `explanation` | Shown after the player answers |

`correct_answer_index` is zero-based.
