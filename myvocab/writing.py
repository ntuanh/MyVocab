# File: writing.py
# Writing practice: a daily diary, IELTS Writing Task 1 (describe a chart) or
# Task 2 (an essay). Gemini marks each piece like a teacher: four criteria out
# of 20, so 80 in all, with corrections, better words and an improved version.
# The score is the piece's writing points (see database.mark_writing_piece for
# which pieces count). When Gemini cannot be reached, the piece is kept and
# LanguageTool's grammar notes are shown until it can be marked.

import json
import os
import random
import re

from .database import (add_writing_piece, mark_writing_piece, get_writing_piece,
                      get_writing_done, get_words_to_try)
from .handle_request import OK, call_gemini_json
from .practice import LEARNER, check_with_languagetool

SKILL = "writing"
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "writing")
GEMINI_WRITING_MODEL = (os.environ.get("GEMINI_WRITING_MODEL")
                        or os.environ.get("GEMINI_PRACTICE_MODEL") or None)
MARKING_TIMEOUT = float(os.environ.get("WRITING_TIMEOUT", 90))  # an essay takes a while to mark

MAX_SCORE = 80
CRITERION_MAX = 20
MAX_CHARS = 6000
MAX_MISTAKES = 15


def _load(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


DIARY = _load("diary.json")["ideas"]
TASK1 = _load("task1.json")
TASK2 = _load("task2.json")
TASKS = {p["id"]: dict(p, kind="task1") for p in TASK1["prompts"]}
TASKS.update({p["id"]: dict(p, kind="task2") for p in TASK2["prompts"]})

for _p in TASK1["prompts"]:  # pie charts must add up, or the task would be nonsense
    for _pie in _p["chart"].get("pies", []):
        assert sum(s["value"] for s in _pie["slices"]) == 100, f"{_p['id']} {_pie['label']} does not add up to 100"

# What each kind asks for, and how it is marked.
KINDS = {
    "diary": {
        "name": "Daily diary", "words": 100, "min_words": 40, "minutes": None,
        "criteria": [
            ("Content and ideas", "how fully and clearly the writer tells about their day, thoughts and feelings, with details"),
            ("Organisation", "logical order, paragraphs, and linking words that make it easy to follow"),
            ("Vocabulary", "range, precision and correct use of words and phrases, including any words to try"),
            ("Grammar", "range and accuracy of grammar: tenses, sentence structures, agreement, articles"),
        ],
    },
    "task1": {
        "name": "IELTS Writing Task 1", "words": 150, "min_words": 60, "minutes": 20,
        "criteria": [
            ("Task Achievement", "an overview of the main trends, key features selected and compared, accurate data, no opinions"),
            ("Coherence and Cohesion", "logical organisation, clear paragraphs, varied and accurate linking"),
            ("Lexical Resource", "range and accuracy of vocabulary for describing data and change"),
            ("Grammatical Range and Accuracy", "variety of structures (e.g. comparatives, passives) and how accurate they are"),
        ],
    },
    "task2": {
        "name": "IELTS Writing Task 2", "words": 250, "min_words": 100, "minutes": 40,
        "criteria": [
            ("Task Response", "answers every part of the question with a clear position, developed and supported ideas"),
            ("Coherence and Cohesion", "logical progression, clear paragraphs, varied and accurate linking"),
            ("Lexical Resource", "range, precision and accuracy of vocabulary, collocation and spelling"),
            ("Grammatical Range and Accuracy", "variety of complex structures and how accurate they are"),
        ],
    },
}

MARKING_PROMPT = """
You are an experienced, kind but honest English teacher and IELTS writing examiner.
The writer is {learner}. Mark their writing the way a good teacher would.

Task: {task_name}
{task_block}
The writing ({words} words; the task asks for about {target} words):
{text}

Score each of these four criteria with a whole number from 0 to 20:
{criteria}
Use this scale for every criterion: 20 excellent, like IELTS band 9; 17 very good (band 7.5-8);
14 good (band 6.5-7); 11 fair (band 5-6); 8 limited (band 4); 5 very limited (band 3);
0-2 almost nothing relevant. If the writing is much shorter than {target} words, lower the
first criterion as an examiner would. Do not reward length alone.

Return only a JSON object:
{{
  "criteria": [{{"name": "<criterion name>", "score": <0-20>, "comment": "<one or two specific sentences>"}}],
  "band": {band_rule},
  "overall": "<two or three sentences of overall feedback: specific, encouraging and honest>",
  "strengths": ["<up to three things done well>"],
  "mistakes": [{{"wrong": "<exact words copied from the writing>", "right": "<the corrected words>",
                 "type": "grammar|vocabulary|spelling|punctuation|style", "why": "<a short explanation>"}}],
  "vocabulary": [{{"word": "<a plain word or phrase they used>", "better": ["<stronger alternative>"],
                   "note": "<when to use the alternatives>"}}],
  "improved": "<the whole piece rewritten at a higher level, keeping the writer's ideas and about the same length>",
  "next_step": "<one concrete thing to practise next>",
  "summary_vi": "<one or two sentences in Vietnamese summing up the feedback>"{words_rule}
}}
List the criteria in the order given above. Give at most {max_mistakes} mistakes, the most
important first, and at most five vocabulary suggestions. Use British English.
"""


def count_words(text):
    return len(re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", text or ""))


def _text(value, limit=600):
    return str(value).strip()[:limit] if isinstance(value, (str, int, float)) else ""


def band_from_score(score):
    """A rough IELTS band for a score out of 80, in half bands."""
    return round(score / MAX_SCORE * 9 * 2) / 2


# --- PROMPTS ---

def diary_prompt(offset_day, another=False):
    """Today's diary idea (the same all day), or a different one when asked."""
    i = offset_day % len(DIARY)
    if another:
        i = random.choice([n for n in range(len(DIARY)) if n != i])
    return DIARY[i]


def pick_task(kind, done, after=None):
    """The first IELTS question of this kind not yet done; with `after`, a
    random different one (preferring ones not done)."""
    prompts = [p for p in (TASK1 if kind == "task1" else TASK2)["prompts"]]
    if after:
        fresh = [p for p in prompts if p["id"] != after and p["id"] not in done] or \
                [p for p in prompts if p["id"] != after]
        return random.choice(fresh)
    return next((p for p in prompts if p["id"] not in done), prompts[0])


def prompt_for(kind, offset_minutes, day_number, after=None):
    """What the page needs to show for a kind of writing. Returns (body, status)."""
    if kind not in KINDS:
        return {"error": "Choose a diary, Task 1 or Task 2."}, 400
    done = get_writing_done(offset_minutes)
    if done is None:
        return {"error": "Could not load your writing."}, 500
    info = {k: v for k, v in KINDS[kind].items() if k != "criteria"} | {
        "criteria": [name for name, _ in KINDS[kind]["criteria"]]}
    if kind == "diary":
        words = get_words_to_try(offset_minutes) or []
        return {"kind": kind, "id": "diary", "info": info, "idea": diary_prompt(day_number, bool(after)),
                "words_to_try": words, "done_today": done["diary_today"]}, 200
    task = pick_task(kind, done["tasks"], after)
    body = {"kind": kind, "id": task["id"], "info": info, "prompt": task["prompt"],
            "instructions": (TASK1 if kind == "task1" else TASK2)["instructions"],
            "best": done["tasks"].get(task["id"]),
            "done_count": sum(1 for pid in done["tasks"] if pid.startswith("t1-" if kind == "task1" else "t2-")),
            "total": len((TASK1 if kind == "task1" else TASK2)["prompts"])}
    if kind == "task1":
        body["chart"] = task["chart"]
    else:
        body["type"], body["topic"] = task["type"], task["topic"]
    return body, 200


# --- MARKING ---

def _chart_as_text(chart):
    """Task 1's chart written out for the teacher, who cannot see the picture."""
    lines = [f"Chart: {chart['title']} ({chart.get('unit') or 'values'})"]
    if chart["kind"] in ("line", "bar"):
        lines.append("Categories: " + ", ".join(chart["x"]))
        lines += [f"{s['name']}: " + ", ".join(str(v) for v in s["values"]) for s in chart["series"]]
    elif chart["kind"] == "pie":
        for pie in chart["pies"]:
            lines.append(f"{pie['label']}: " + ", ".join(f"{s['name']} {s['value']}%" for s in pie["slices"]))
    else:
        lines.append(" | ".join(chart["columns"]))
        lines += [" | ".join(str(c) for c in row) for row in chart["rows"]]
    return "\n".join(lines)


def _clean_feedback(raw, kind):
    """Checks the teacher's answer and keeps it within bounds. Returns
    (score, band, feedback) or None when it is unusable."""
    if not isinstance(raw, dict) or not isinstance(raw.get("criteria"), list):
        return None
    names = [name for name, _ in KINDS[kind]["criteria"]]
    criteria = []
    for i, name in enumerate(names):
        item = raw["criteria"][i] if i < len(raw["criteria"]) and isinstance(raw["criteria"][i], dict) else None
        if item is None:
            return None
        try:
            score = int(round(float(item.get("score"))))
        except (TypeError, ValueError):
            return None
        criteria.append({"name": name, "score": max(0, min(CRITERION_MAX, score)),
                         "comment": _text(item.get("comment"), 400)})
    score = sum(c["score"] for c in criteria)

    band = None
    if kind != "diary":
        try:
            band = round(float(raw.get("band")) * 2) / 2
            band = max(0.0, min(9.0, band))
        except (TypeError, ValueError):
            band = band_from_score(score)

    mistakes = []
    for m in raw.get("mistakes") if isinstance(raw.get("mistakes"), list) else []:
        if isinstance(m, dict) and (_text(m.get("wrong")) or _text(m.get("right"))):
            kind_of = _text(m.get("type"), 20).lower()
            mistakes.append({"wrong": _text(m.get("wrong"), 300), "right": _text(m.get("right"), 300),
                             "type": kind_of if kind_of in ("grammar", "vocabulary", "spelling", "punctuation", "style") else "grammar",
                             "why": _text(m.get("why"), 300)})
    vocabulary = []
    for v in raw.get("vocabulary") if isinstance(raw.get("vocabulary"), list) else []:
        if isinstance(v, dict) and _text(v.get("word")):
            better = [_text(b, 80) for b in v.get("better", []) if _text(b)] if isinstance(v.get("better"), list) else []
            vocabulary.append({"word": _text(v.get("word"), 80), "better": better[:4], "note": _text(v.get("note"), 300)})
    words_used = []
    for w in raw.get("words_used") if isinstance(raw.get("words_used"), list) else []:
        if isinstance(w, dict) and _text(w.get("word")):
            words_used.append({"word": _text(w.get("word"), 60), "used_well": bool(w.get("used_well")),
                               "note": _text(w.get("note"), 300)})
    feedback = {
        "source": "ai",
        "criteria": criteria,
        "overall": _text(raw.get("overall"), 800),
        "strengths": [_text(s, 300) for s in raw.get("strengths", []) if _text(s)][:3] if isinstance(raw.get("strengths"), list) else [],
        "mistakes": mistakes[:MAX_MISTAKES],
        "vocabulary": vocabulary[:5],
        "improved": _text(raw.get("improved"), MAX_CHARS + 2000),
        "next_step": _text(raw.get("next_step"), 400),
        "summary_vi": _text(raw.get("summary_vi"), 500),
        "words_used": words_used[:5],
    }
    return score, band, feedback


def _mark(piece):
    """Asks the teacher to mark a stored piece. Returns (score, band, feedback) or None."""
    kind = piece["kind"]
    spec = KINDS[kind]
    if kind == "diary":
        words = (piece.get("feedback") or {}).get("words_to_try") or []
        task_block = f"Diary idea (optional): {piece['prompt']}"
        if words:
            task_block += "\nWords the writer was encouraged to try: " + ", ".join(words)
        words_rule = (',\n  "words_used": [{"word": "<each word to try that appears>", "used_well": true, '
                      '"note": "<how it was used>"}]') if words else ""
    else:
        task = TASKS.get(piece["prompt_id"], {})
        task_block = f"Question: {piece['prompt']}"
        if kind == "task1" and task.get("chart"):
            task_block += "\n" + _chart_as_text(task["chart"])
        words_rule = ""
    prompt = MARKING_PROMPT.format(
        learner=LEARNER, task_name=spec["name"], task_block=task_block, words=piece["words"],
        target=spec["words"], text=json.dumps(piece["text"], ensure_ascii=False),
        criteria="\n".join(f"- {name}: {what}" for name, what in spec["criteria"]),
        band_rule="null" if kind == "diary" else "<overall IELTS band from 0 to 9 in steps of 0.5>",
        words_rule=words_rule, max_mistakes=MAX_MISTAKES)
    content, status = call_gemini_json(prompt, f"writing {piece['id']}", model=GEMINI_WRITING_MODEL,
                                       timeout=MARKING_TIMEOUT)
    if status != OK:
        return None
    return _clean_feedback(content, kind)


def _waiting(piece):
    """A piece the teacher could not mark yet, with LanguageTool's notes if it is reachable."""
    notes = check_with_languagetool(piece["text"][:MAX_CHARS])
    return {"piece": piece, "waiting": True,
            "grammar": notes and {"mistakes": notes["mistakes"], "corrected": notes["corrected"]}}


def check(data, offset_minutes, day_number):
    """Keeps a new piece and has it marked. data holds kind, prompt_id (an IELTS
    question), idea and words_to_try (a diary), text and revision_of. Returns
    (body, status)."""
    kind, prompt_id, revision_of = data.get("kind"), data.get("prompt_id"), data.get("revision_of")
    text = data.get("text")
    if kind not in KINDS:
        return {"error": "Choose a diary, Task 1 or Task 2."}, 400
    text = (text or "").strip()
    words = count_words(text)
    spec = KINDS[kind]
    if words < spec["min_words"]:
        return {"error": f"Write at least {spec['min_words']} words first; {spec['name']} asks for about {spec['words']}."}, 400
    if len(text) > MAX_CHARS:
        return {"error": f"Keep it under {MAX_CHARS} characters."}, 400
    words_to_try = []
    if kind == "diary":
        idea = _text(data.get("idea"), 300)
        prompt = idea if idea in DIARY else diary_prompt(day_number)
        prompt_id = "diary"
        raw_words = data.get("words_to_try")
        words_to_try = [_text(w, 40) for w in raw_words if isinstance(w, str)][:5] if isinstance(raw_words, list) else []
    else:
        task = TASKS.get(prompt_id)
        if task is None or task["kind"] != kind:
            return {"error": "That question is not in the list."}, 400
        prompt = task["prompt"]
    if revision_of is not None:
        original = get_writing_piece(revision_of) if isinstance(revision_of, int) else None
        if original is None or original["kind"] != kind:
            return {"error": "The piece you are revising was not found."}, 400

    start = {"words_to_try": words_to_try}
    piece_id = add_writing_piece(kind, prompt_id, prompt, text, words, revision_of, start)
    if piece_id is None:
        return {"error": "Could not save your writing."}, 500
    piece = {"id": piece_id, "kind": kind, "prompt_id": prompt_id, "prompt": prompt, "text": text,
             "words": words, "feedback": start}
    return score_piece(piece, offset_minutes)


def score_piece(piece, offset_minutes):
    """Marks a stored piece now. Returns (body, status)."""
    marked = _mark(piece)
    if marked is None:
        return _waiting(get_writing_piece(piece["id"]) or piece), 200
    score, band, feedback = marked
    feedback["words_to_try"] = (piece.get("feedback") or {}).get("words_to_try") or []
    saved = mark_writing_piece(piece["id"], score, band, feedback, offset_minutes)
    if saved is None:
        return {"error": "Could not save the marks."}, 500
    return {"piece": saved, "waiting": False}, 200


def retry(piece_id, offset_minutes):
    """Marks a piece that was kept while the teacher was unavailable."""
    piece = get_writing_piece(piece_id)
    if piece is None:
        return {"error": "That piece of writing was not found."}, 404
    if piece["status"] == "scored":
        return {"piece": piece, "waiting": False}, 200
    piece["feedback"] = piece.get("feedback") or {}
    return score_piece(piece, offset_minutes)
