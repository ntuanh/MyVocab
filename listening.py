# File: listening.py
# Listening practice: BBC Learning English's 6 Minute English, played from the
# BBC's YouTube channel. The learner does the episode's BBC quiz or worksheet
# and enters the score here; the score becomes listening points.

import json
import os

from database import save_listening_attempt, get_listening_attempts

SKILL = "listening"
EPISODES_FILE = os.path.join(os.path.dirname(__file__), "data", "bbc_6min.json")

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
