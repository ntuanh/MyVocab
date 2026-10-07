# File: reading.py
# Reading practice: 50 IELTS-style Academic Reading parts written for MyVocab
# (data/reading/*.json), one a day. Answers are marked here, on the server, so
# the page never holds the answer key before you submit.

import glob
import json
import os
import re
from datetime import date, timedelta

from .database import save_reading_attempt, get_reading_attempts

SKILL = "reading"
PARTS_GLOB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "reading", "*.json")

# Each right answer wins these points; each wrong one loses a third as many.
# A blank answer neither wins nor loses, as in the real test.
POINTS_RIGHT = 3
WRONG_LOSES = 1
MINUTES_PER_PART = 20  # a third of the real test's hour

TFNG = ("TRUE", "FALSE", "NOT GIVEN")
LETTERS = "ABCDEFGHIJ"

# Correct answers out of 40 -> Academic Reading band (the published guide).
# A part has about 13 questions, so its score is scaled to 40 first: a rough
# guide to the level, not an official band.
BAND_TABLE = [(39, 9.0), (37, 8.5), (35, 8.0), (33, 7.5), (30, 7.0), (27, 6.5), (23, 6.0),
              (19, 5.5), (15, 5.0), (13, 4.5), (10, 4.0), (8, 3.5), (6, 3.0), (4, 2.5)]


def _check_part(part, seen):
    """Raises ValueError naming what is wrong with a part, so a bad edit to a
    data file stops the app at start-up instead of marking answers wrongly."""
    pid = part.get("id")
    if not isinstance(pid, int) or pid in seen:
        raise ValueError(f"part id {pid!r} is missing or repeated")
    seen.add(pid)
    letters = LETTERS[:len(part["paragraphs"])]
    for group in part["groups"]:
        kind = group["type"]
        for q in group["questions"]:
            a = q["a"]
            ok = {
                "tfng": lambda: a in TFNG,
                "mcq": lambda: a in LETTERS[:len(q["options"])],
                "gap": lambda: isinstance(a, list) and all(
                    len(x.split()) <= group["words"] for x in a),
                "para": lambda: a in letters,
                "heading": lambda: q["q"] in letters and 0 <= a < len(group["headings"]),
            }[kind]()
            if not ok:
                raise ValueError(f"part {pid}: bad answer {a!r} for {q['q'][:40]!r}")
            if "p" in q and q["p"] not in letters:
                raise ValueError(f"part {pid}: paragraph {q['p']!r} does not exist")


def _load_parts():
    parts, seen = [], set()
    for path in sorted(glob.glob(PARTS_GLOB)):
        with open(path, encoding="utf-8") as f:
            for part in json.load(f)["parts"]:
                _check_part(part, seen)
                number = 0
                for group in part["groups"]:
                    for q in group["questions"]:
                        number += 1
                        q["n"] = number
                part["total"] = number
                part["words"] = sum(len(p.split()) for p in part["paragraphs"])
                parts.append(part)
    parts.sort(key=lambda p: p["id"])
    return parts


PARTS = _load_parts()
PARTS_BY_ID = {part["id"]: part for part in PARTS}


def normalize(text):
    """Lower case, no punctuation, single spaces: 'Waggle-dance.' -> 'waggle dance'."""
    text = (text or "").lower().replace("’", "'").replace("-", " ")
    text = re.sub(r"[^\w\s']", " ", text)
    return " ".join(text.split())


def band(correct, total):
    """A rough Academic Reading band for a score, scaled to the test's 40 questions."""
    if not total:
        return None
    scaled = round(correct * 40 / total)
    return next((b for floor, b in BAND_TABLE if scaled >= floor), 2.0)


def public_part(part):
    """A part as the page sees it before submitting: no answers, no evidence."""
    groups = []
    for group in part["groups"]:
        g = {k: v for k, v in group.items() if k != "questions"}
        g["questions"] = [{k: v for k, v in q.items() if k not in ("a", "p")} for q in group["questions"]]
        groups.append(g)
    return {k: v for k, v in part.items() if k != "groups"} | {"groups": groups}


def _answer_text(group, q):
    """The answer as it should be shown in the key."""
    if group["type"] == "gap":
        return " / ".join(q["a"])
    if group["type"] == "heading":
        return roman(q["a"] + 1)
    return q["a"]


def roman(n):
    return ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"][n - 1]


def mark(part, answers):
    """Marks every question. answers maps question numbers (as strings) to what
    was given: a choice, a letter, a heading number or the words written."""
    results = []
    for group in part["groups"]:
        for q in group["questions"]:
            given = str(answers.get(str(q["n"]), "")).strip()
            if group["type"] == "gap":
                right = normalize(given) in {normalize(a) for a in q["a"]}
            elif group["type"] == "heading":
                right = given == str(q["a"])
            else:
                right = given.upper() == q["a"]
            results.append({"n": q["n"], "given": given, "blank": not given, "right": right,
                            "answer": _answer_text(group, q),
                            "paragraph": q.get("p") or (q["a"] if group["type"] == "para" else q["q"]
                                                        if group["type"] == "heading" else None)})
    return results


def _streak(days, today):
    """Days in a row, ending today (or yesterday, if today is still open), with a part done."""
    done = {date.fromisoformat(d) for d in days}
    day = today if today in done else today - timedelta(days=1)
    streak = 0
    while day in done:
        streak += 1
        day -= timedelta(days=1)
    return streak


def plan(offset_minutes):
    """Every part in plan order (one a day) with its scores, today's part and
    the day streak; None if the database could not be read."""
    record = get_reading_attempts(offset_minutes)
    if record is None:
        return None
    today = date.fromisoformat(record["today"])
    parts = [{"id": p["id"], "day": i + 1, "title": p["title"], "topic": p["topic"],
              "words": p["words"], "questions": p["total"], "scores": record["parts"].get(p["id"])}
             for i, p in enumerate(PARTS)]
    done_today = [p["id"] for p in parts if p["scores"] and p["scores"]["first"]
                  and p["scores"]["first"]["day"] == record["today"]]
    next_part = next((p for p in parts if not p["scores"]), None)
    return {"parts": parts, "today": record["today"], "done_today": done_today,
            "next_id": next_part and next_part["id"], "streak": _streak(record["days"], today),
            "minutes": MINUTES_PER_PART}


def submit(part_id, answers):
    """Marks and keeps one submitted part. Returns (body, status)."""
    part = PARTS_BY_ID.get(part_id if isinstance(part_id, int) else None)
    if part is None:
        return {"error": "That reading part does not exist."}, 400
    if not isinstance(answers, dict):
        return {"error": "No answers were sent."}, 400
    results = mark(part, answers)
    correct = sum(r["right"] for r in results)
    wrong = sum(not r["right"] and not r["blank"] for r in results)
    points = correct * POINTS_RIGHT - wrong * WRONG_LOSES
    saved = save_reading_attempt(part["id"], correct, part["total"], part["total"] * POINTS_RIGHT, points,
                                 {str(r["n"]): r["given"] for r in results})
    if saved is None:
        return {"error": "Could not save your answers."}, 500
    return {"results": results, "correct": correct, "wrong": wrong, "total": part["total"],
            "band": band(correct, part["total"]), "counted": saved["counted"],
            "points": saved["points"], "score_points": points}, 200
