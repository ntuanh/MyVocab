# File: listening.py
# Listening practice: BBC Learning English's 6 Minute English, played from the
# BBC's YouTube channel. The learner does the episode's BBC quiz or worksheet
# and enters the score here; the score becomes listening points. The learner can
# also keep the episode's files here (worksheet, transcript, audio): see check_doc.

import json
import os

from .database import save_listening_attempt, get_listening_attempts
from .database import add_listening_doc, list_listening_docs

SKILL = "listening"
EPISODES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "bbc_6min.json")

# Each right answer wins these points; each wrong one loses half as many,
# rounded down, so a guess on a three-way question is worth nothing on average.
POINTS_PER_ANSWER = 4
WRONG_LOSES = POINTS_PER_ANSWER // 2
MAX_QUESTIONS = 30

with open(EPISODES_FILE, encoding="utf-8") as f:
    EPISODES = json.load(f)["episodes"]
EPISODE_IDS = {episode["id"] for episode in EPISODES}


def score_points(correct, total):
    """Points for a score of correct out of total: whole numbers, may be negative."""
    return correct * POINTS_PER_ANSWER - (total - correct) * WRONG_LOSES


def episodes_with_scores():
    """Every episode, newest first, with the learner's scores so far; None if
    the database could not be read."""
    attempts = get_listening_attempts()
    if attempts is None:
        return None
    return [{**episode, "scores": attempts.get(episode["id"])} for episode in EPISODES]


def save_score(episode_id, correct, total):
    """Checks and keeps a score. Returns (body, status)."""
    if episode_id not in EPISODE_IDS:
        return {"error": "That episode is not in the list."}, 400
    try:
        correct, total = int(correct), int(total)
    except (TypeError, ValueError):
        return {"error": "Enter your score as two whole numbers."}, 400
    if not 1 <= total <= MAX_QUESTIONS:
        return {"error": f"The quiz should have from 1 to {MAX_QUESTIONS} questions."}, 400
    if not 0 <= correct <= total:
        return {"error": f"Right answers must be from 0 to {total}."}, 400

    saved = save_listening_attempt(episode_id, correct, total,
                                   total * POINTS_PER_ANSWER, score_points(correct, total))
    if saved is None:
        return {"error": "Could not save your score."}, 500
    return {"correct": correct, "total": total, "counted": saved["counted"],
            "points": saved["points"], "score_points": score_points(correct, total)}, 200


# --- Episode files ---
# What can be added: the kinds a BBC worksheet, transcript or audio comes in.
# Each is checked by its first bytes as well as its name, and none of them is a
# web page, so a file can never run as part of MyVocab.
DOC_TYPES = {
    ".pdf": ("application/pdf", (b"%PDF-",)),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", (b"PK\x03\x04",)),
    ".doc": ("application/msword", (b"\xd0\xcf\x11\xe0",)),
    ".txt": ("text/plain; charset=utf-8", None),  # any UTF-8 text
    ".png": ("image/png", (b"\x89PNG",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".webp": ("image/webp", (b"RIFF",)),
    ".mp3": ("audio/mpeg", (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")),
}
MAX_DOC_BYTES = 20 * 1024 * 1024
MAX_DOCS_PER_EPISODE = 10


def clean_filename(name):
    """The file's own name, without folders or odd characters, at most 120 characters."""
    name = os.path.basename((name or "").replace("\\", "/")).strip()
    name = "".join(c for c in name if c.isprintable() and c not in '<>:"|?*')
    return name[-120:] or "file"


def check_doc(episode_id, filename, data, existing_count):
    """Returns (content_type, None) for a file that can be kept, or (None, why not)."""
    if episode_id not in EPISODE_IDS:
        return None, "That episode is not in the list."
    if existing_count >= MAX_DOCS_PER_EPISODE:
        return None, f"An episode can keep at most {MAX_DOCS_PER_EPISODE} files. Delete one first."
    ext = os.path.splitext(filename)[1].lower()
    if ext not in DOC_TYPES:
        return None, "Add a PDF, Word, text, picture (PNG, JPG, WebP) or MP3 file."
    if not data:
        return None, "That file is empty."
    if len(data) > MAX_DOC_BYTES:
        return None, f"That file is over {MAX_DOC_BYTES // (1024 * 1024)} MB."
    content_type, magic = DOC_TYPES[ext]
    if magic is None:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            return None, "That text file is not plain UTF-8 text."
    elif not data.startswith(magic) or (ext == ".webp" and data[8:12] != b"WEBP"):
        return None, f"That file does not look like a real {ext[1:].upper()} file."
    return content_type, None


def docs_by_episode():
    """{episode id: [file details]}, or None if the database could not be read."""
    docs = list_listening_docs()
    if docs is None:
        return None
    out = {}
    for doc in docs:
        doc["uploaded_at"] = doc["uploaded_at"].isoformat()
        out.setdefault(doc["episode_id"], []).append(doc)
    return out


def save_doc(episode_id, filename, data):
    """Checks and keeps one file. Returns (body, status)."""
    filename = clean_filename(filename)
    docs = docs_by_episode()
    if docs is None:
        return {"error": "Could not read your files."}, 500
    content_type, problem = check_doc(episode_id, filename, data, len(docs.get(episode_id, [])))
    if problem:
        return {"error": problem}, 400
    saved = add_listening_doc(episode_id, filename, content_type, data)
    if saved is None:
        return {"error": "Could not save the file."}, 500
    saved["uploaded_at"] = saved["uploaded_at"].isoformat()
    return {"doc": saved}, 200
