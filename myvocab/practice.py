"""Practice exercises: Gemini writes them and marks the answers.

The free tier grants only 20 Gemini requests a DAY per model, so every exercise
type is built to spend as few of them as possible:

- one request writes a whole batch of exercises, never one each;
- an answer that matches the expected one is marked here, with no request;
- fill-the-blank falls back to the example sentence saved with each word, so it
  keeps working when Gemini is unreachable or out of quota;
- when Gemini cannot mark an answer, LanguageTool's free public API still
  checks the grammar.

GEMINI_PRACTICE_MODEL moves all of this onto another model, and with it onto a
daily quota of its own, so practising never eats into dictionary lookups.
"""
import json
import os
import re

import requests

from .database import get_words_for_practice, record_practice_points, update_word_score
from .handle_request import OK, call_gemini_json

GEMINI_PRACTICE_MODEL = os.environ.get("GEMINI_PRACTICE_MODEL") or None
LANGUAGETOOL_URL = os.environ.get("LANGUAGETOOL_URL", "https://api.languagetool.org/v2/check")
# The saved dataset is British English ("neighbour", "favourite"); checking it
# as en-US would flag the learner's own vocabulary as misspelt.
LANGUAGETOOL_LANGUAGE = os.environ.get("LANGUAGETOOL_LANGUAGE", "en-GB")
LANGUAGETOOL_TIMEOUT = float(os.environ.get("LANGUAGETOOL_TIMEOUT", 6))

MODES = ("fill_blank", "fix_mistake", "translate", "use_it")
VERDICTS = ("correct", "almost", "incorrect")
MISTAKE_TYPES = ("grammar", "vocabulary", "spelling", "punctuation")
DEFAULT_COUNT = 5
MAX_COUNT = 8
MAX_ANSWER_CHARS = 1000
MAX_TEXT_CHARS = 2000
MAX_MISTAKES = 10
BLANK = "___"

LEARNER = ("a Vietnamese learner of English at about CEFR B1. Use British English "
           "spelling, and keep the sentences natural and everyday")

GENERATE_PROMPTS = {
    "fill_blank": f"""
You are writing fill-in-the-blank exercises for {LEARNER}.
For each word below, write ONE new sentence of 8 to 18 words that uses the word in
whatever form the grammar needs ("commutes", "errands", "tidied"). Do not copy the
example sentence. Replace the word -- every word of it, for a phrase -- with "{BLANK}".
Return JSON: {{"items": [{{
  "word": the word exactly as given,
  "sentence": the sentence containing "{BLANK}" exactly once,
  "answer": the exact text that fills the blank,
  "sentence_vi": a natural Vietnamese translation of the whole sentence
}}]}}
""",
    "fix_mistake": f"""
You are writing "find and fix the mistake" exercises for {LEARNER}.
For each word below, write ONE sentence of 8 to 18 words that uses the word, then
put exactly ONE mistake into it, of a kind Vietnamese learners often make: verb
tense, subject-verb agreement, article, preposition, plural, word form or word
order. The rest of the sentence must be correct.
Return JSON: {{"items": [{{
  "word": the word exactly as given,
  "wrong_sentence": the sentence with the mistake,
  "correct_sentence": the same sentence with only that mistake fixed,
  "explanation_vi": one short sentence in Vietnamese explaining the mistake
}}]}}
""",
    "translate": f"""
You are writing translation exercises for {LEARNER}.
For each word below, write ONE English sentence of 8 to 16 words that uses the
word, then translate it into natural Vietnamese. The learner will see only the
Vietnamese and must translate it back into English using the word.
Return JSON: {{"items": [{{
  "word": the word exactly as given,
  "vietnamese_sentence": the Vietnamese sentence,
  "english_reference": the English sentence
}}]}}
""",
}

TASKS = {
    "fill_blank": ("Fill the blank in a sentence. The blank is meant for the target word in "
                   "the right form. If the learner used a different word that also fits, mark "
                   "it \"almost\" and name the target word in vocab_note_vi."),
    "fix_mistake": ("The learner was given a sentence containing one mistake and had to rewrite "
                    "the whole sentence correctly. Any correct rewrite that keeps the meaning "
                    "counts, not only the reference."),
    "translate": ("Translate the Vietnamese sentence into English using the target word. Any "
                  "accurate, natural translation that uses the target word counts, not only "
                  "the reference."),
    "use_it": ("Write an original English sentence that uses the target word correctly. Judge "
               "whether the word is used with the right meaning and form, and whether the "
               "whole sentence is grammatical and natural."),
}

CHECK_PROMPT = """
You are a kind but exact English teacher marking an answer from {learner}.
Task: {task}
Exercise: {exercise}
Learner's answer: {answer}
Mark the answer for grammar and vocabulary.
Return JSON: {{
  "verdict": "correct" if it has no mistakes, "almost" if the meaning and the target word are right but there is a small slip, otherwise "incorrect",
  "corrected": the learner's whole sentence with every mistake fixed and nothing else changed,
  "mistakes": [{{"wrong": the exact wrong text, "right": its fix, "type": "grammar" | "vocabulary" | "spelling" | "punctuation", "why_vi": one short sentence in Vietnamese}}],
  "vocab_note_vi": one short sentence in Vietnamese on how the target word was used,
  "tip_vi": one short, useful tip in Vietnamese, or ""
}}
"""

GRAMMAR_PROMPT = """
You are a kind but exact English teacher checking a text written by {learner}.
Text: {text}
Find every grammar, vocabulary, spelling and punctuation mistake. Do not rewrite
for style when the original is already correct and natural.
Return JSON: {{
  "corrected": the whole text with every mistake fixed and nothing else changed,
  "mistakes": [{{"wrong": the exact wrong text, "right": its fix, "type": "grammar" | "vocabulary" | "spelling" | "punctuation", "why_vi": one short sentence in Vietnamese}}],
  "tip_vi": one short, useful tip in Vietnamese about the most important mistake, or ""
}}
"""


# --- SMALL HELPERS ---

def _text(value, limit=500):
    """A model field as a clean string: anything that is not a string is dropped."""
    return value.strip()[:limit] if isinstance(value, str) else ""


def normalize(text):
    """Folds away differences that do not make an answer wrong: case, curly
    quotes, repeated spaces and the closing full stop."""
    text = (text or "").lower().replace("’", "'").replace("‘", "'")
    text = re.sub(r"\s+", " ", text).strip()
    return text.rstrip(" .!?")


def fill_sentence(sentence, answer):
    return sentence.replace(BLANK, answer.strip(), 1)


def _clean_mistakes(raw):
    mistakes = []
    for m in raw if isinstance(raw, list) else []:
        if not isinstance(m, dict):
            continue
        wrong, right = _text(m.get("wrong"), 200), _text(m.get("right"), 200)
        if not wrong and not right:
            continue
        kind = _text(m.get("type"), 20).lower()
        mistakes.append({
            "wrong": wrong,
            "right": right,
            "type": kind if kind in MISTAKE_TYPES else "grammar",
            "why": _text(m.get("why_vi") or m.get("why"), 300),
        })
    return mistakes[:MAX_MISTAKES]


# --- WRITING EXERCISES ---

def _blank_from_example(row):
    """Builds a fill-the-blank item from the example sentence saved with a word,
    or returns None when the example does not contain it. Matches inflected
    forms too: "commute" finds "commutes", "commuted" and "commuting"."""
    word, example = row.get("word") or "", row.get("example") or ""
    if not word or not example or example == "N/A":
        return None
    stems = [word]
    if len(word) > 3 and word[-1] in "ey":
        stems.append(word[:-1])
    for stem in stems:
        match = re.search(r"\b" + re.escape(stem) + r"[a-z]*\b", example, re.IGNORECASE)
        if match:
            return {
                "word_id": row["id"],
                "word": word,
                "meaning_vi": row.get("vietnamese_meaning") or "",
                "sentence": example[:match.start()] + BLANK + example[match.end():],
                "answer": match.group(0),
                "sentence_vi": "",
            }
    return None


def _use_it_item(row):
    return {
        "word_id": row["id"],
        "word": row["word"],
        "meaning_vi": row.get("vietnamese_meaning") or "",
        "definition": row.get("english_definition") or "",
    }


def _ai_item(mode, raw, row):
    """Checks one generated item and joins it to its saved word, or returns None."""
    item = {"word_id": row["id"], "word": row["word"],
            "meaning_vi": row.get("vietnamese_meaning") or ""}
    if mode == "fill_blank":
        sentence = re.sub(r"_{2,}", BLANK, _text(raw.get("sentence")))
        answer = _text(raw.get("answer"), 100)
        if sentence.count(BLANK) != 1 or not answer:
            return None
        item.update(sentence=sentence, answer=answer, sentence_vi=_text(raw.get("sentence_vi")))
    elif mode == "fix_mistake":
        wrong, right = _text(raw.get("wrong_sentence")), _text(raw.get("correct_sentence"))
        if not wrong or not right or normalize(wrong) == normalize(right):
            return None
        item.update(wrong_sentence=wrong, correct_sentence=right,
                    explanation_vi=_text(raw.get("explanation_vi")))
    elif mode == "translate":
        vi, en = _text(raw.get("vietnamese_sentence")), _text(raw.get("english_reference"))
        if not vi or not en:
            return None
        item.update(vietnamese_sentence=vi, english_reference=en)
    return item


def _generate_with_ai(mode, rows):
    words = [{"word": r["word"], "meaning_vi": r.get("vietnamese_meaning") or "",
              "example": r.get("example") or ""} for r in rows]
    prompt = GENERATE_PROMPTS[mode] + "\nWords: " + json.dumps(words, ensure_ascii=False)
    content, status = call_gemini_json(prompt, f"{mode} exercises", model=GEMINI_PRACTICE_MODEL)
    if status != OK:
        return []
    raw_items = content.get("items") if isinstance(content, dict) else content
    by_word = {r["word"].lower(): r for r in rows}
    items = []
    for raw in raw_items if isinstance(raw_items, list) else []:
        row = by_word.pop(_text(raw.get("word") if isinstance(raw, dict) else None).lower(), None)
        item = _ai_item(mode, raw, row) if row else None
        if item:
            items.append(item)
    return items


def make_exercises(mode, topic_ids=None, count=DEFAULT_COUNT):
    """Returns (body, http status) for a batch of exercises."""
    if mode not in MODES:
        return {"error": f"Unknown practice type '{mode}'."}, 400
    rows = get_words_for_practice(topic_ids, count)
    if not rows:
        return {"error": "No saved words found for the selected topics."}, 404

    if mode == "use_it":
        return {"mode": mode, "source": "saved", "items": [_use_it_item(r) for r in rows]}, 200

    items = _generate_with_ai(mode, rows)
    if items:
        return {"mode": mode, "source": "ai", "items": items}, 200

    if mode == "fill_blank":
        items = [i for i in (_blank_from_example(r) for r in rows) if i]
        if items:
            return {"mode": mode, "source": "saved", "items": items,
                    "notice": "AI is unavailable right now, so these sentences are the "
                              "examples saved with your words."}, 200

    return {"error": "AI could not write these exercises right now. Try again later, or "
                     "practise with Fill the blank or Use it in a sentence, which work "
                     "without it.", "retryable": True}, 503


# --- MARKING ---

def check_with_languagetool(text):
    """Grammar and spelling notes from LanguageTool, or None when it is unreachable.
    Its explanations are in English only."""
    try:
        response = requests.post(LANGUAGETOOL_URL,
                                 data={"text": text, "language": LANGUAGETOOL_LANGUAGE},
                                 timeout=LANGUAGETOOL_TIMEOUT)
        if response.status_code != 200:
            print(f"ERROR: LanguageTool returned {response.status_code}: {response.text[:300]}")
            return None
        matches = response.json().get("matches", [])
    except Exception as e:
        print(f"ERROR calling LanguageTool: {e}")
        return None

    mistakes, corrected, last_start = [], text, len(text)
    # Apply the fixes from the end so earlier offsets stay valid.
    for m in sorted(matches, key=lambda m: m.get("offset", 0), reverse=True):
        start, length = m.get("offset", 0), m.get("length", 0)
        fix = next((r.get("value") for r in m.get("replacements", []) if r.get("value")), "")
        issue = (m.get("rule") or {}).get("issueType")
        mistakes.append({
            "wrong": text[start:start + length],
            "right": fix,
            "type": "spelling" if issue == "misspelling" else "grammar",
            "why": _text(m.get("message"), 300),
        })
        if fix and start + length <= last_start:
            corrected = corrected[:start] + fix + corrected[start + length:]
            last_start = start
    mistakes.reverse()
    return {"mistakes": mistakes[:MAX_MISTAKES], "corrected": corrected}


def _learner_sentence(mode, item, answer):
    """The full sentence the learner produced, which is what gets marked."""
    if mode == "fill_blank":
        return fill_sentence(_text(item.get("sentence")), answer)
    return answer


def _exercise_for_prompt(mode, item):
    fields = {
        "fill_blank": ("word", "sentence", "answer"),
        "fix_mistake": ("word", "wrong_sentence", "correct_sentence"),
        "translate": ("word", "vietnamese_sentence", "english_reference"),
        "use_it": ("word", "meaning_vi", "definition"),
    }[mode]
    exercise = {k: _text(item.get(k)) for k in fields}
    exercise["target_word"] = exercise.pop("word")
    return exercise


def _reference(mode, item):
    if mode == "fill_blank":
        return fill_sentence(_text(item.get("sentence")), _text(item.get("answer")))
    return _text(item.get({"fix_mistake": "correct_sentence",
                           "translate": "english_reference"}.get(mode, "")))


# --- POINTS FOR THE WEEKLY GOAL ---
# Everything practised here counts towards the vocab score.
SKILL = "vocab"

# A sentence is worth more the harder it is to produce: the task itself, plus a
# point for every 4 words and one for every long word (7+ letters, which tend to
# be the less common ones). A right answer earns its worth; "almost" loses a
# third of it and a wrong answer half, both rounded down: whole points only.
TASK_POINTS = {"fill_blank": 1, "fix_mistake": 2, "translate": 3, "use_it": 3}
LONG_WORD_LETTERS = 7
MAX_POINTS = 20
PENALTY_DIVISOR = {"almost": 3, "incorrect": 2}


def sentence_points(mode, sentence):
    """What a sentence is worth, from 1 to MAX_POINTS."""
    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", sentence or "")
    long_words = sum(1 for w in words if len(w) >= LONG_WORD_LETTERS)
    return max(1, min(MAX_POINTS, TASK_POINTS[mode] + len(words) // 4 + long_words))


def _award(mode, item, verdict, sentence):
    """Records what this answer won or lost, and returns {"worth", "change"}.
    Exercises are scored on their own sentence, so a long answer cannot inflate
    them; "use it in a sentence" has none, so the learner's sentence is scored."""
    if verdict != "correct" and verdict not in PENALTY_DIVISOR:
        return None
    worth = sentence_points(mode, sentence if mode == "use_it" else _reference(mode, item))
    change = worth if verdict == "correct" else -(worth // PENALTY_DIVISOR[verdict])
    record_practice_points(SKILL, item.get("word_id"), mode, verdict, worth, change)
    return {"worth": worth, "change": change}


def give_up(mode, item):
    """"Show answer" counts as a wrong answer, for the word and for the points."""
    if mode not in MODES or mode == "use_it" or not isinstance(item, dict):
        return {"error": "This exercise is not valid."}, 400
    _record(item, "incorrect")
    return {"points": _award(mode, item, "incorrect", None)}, 200


def _record(item, verdict):
    """Feeds the result into the word's priority score, which the exam shares.
    "almost" changes nothing: the word was known, the slip was elsewhere."""
    word_id = item.get("word_id")
    if not isinstance(word_id, int) or verdict not in ("correct", "incorrect"):
        return None
    return update_word_score(word_id, verdict == "correct")


def _result(verdict, source, **fields):
    result = {"verdict": verdict, "source": source, "corrected": None, "reference": None,
              "mistakes": [], "vocab_note": None, "tip": None, "explanation": None}
    result.update(fields)
    return result


def check_answer(mode, item, answer):
    """Returns (body, http status) with the verdict on one answer."""
    if mode not in MODES or not isinstance(item, dict):
        return {"error": "This exercise is not valid."}, 400
    answer = (answer or "").strip()
    if not answer:
        return {"error": "Write an answer first."}, 400
    if len(answer) > MAX_ANSWER_CHARS:
        return {"error": f"Keep the answer under {MAX_ANSWER_CHARS} characters."}, 400

    sentence = _learner_sentence(mode, item, answer)
    reference = _reference(mode, item)
    explanation = _text(item.get("explanation_vi")) or None

    # An exact match needs no marking: spend no request on it.
    expected = {"fill_blank": item.get("answer"),
                "fix_mistake": item.get("correct_sentence")}.get(mode)
    if expected and normalize(answer) == normalize(expected):
        result = _result("correct", "match", corrected=sentence, reference=reference,
                         explanation=explanation)
        result["score"] = _record(item, "correct")
        result["points"] = _award(mode, item, "correct", sentence)
        return result, 200

    prompt = CHECK_PROMPT.format(
        learner=LEARNER, task=TASKS[mode],
        exercise=json.dumps(_exercise_for_prompt(mode, item), ensure_ascii=False),
        answer=json.dumps(sentence if mode == "fill_blank" else answer, ensure_ascii=False))
    content, status = call_gemini_json(prompt, f"{mode} answer", model=GEMINI_PRACTICE_MODEL)
    verdict = _text(content.get("verdict"), 20).lower() if isinstance(content, dict) else ""

    if status == OK and verdict in VERDICTS:
        result = _result(
            verdict, "ai",
            corrected=_text(content.get("corrected"), MAX_ANSWER_CHARS) or sentence,
            reference=reference or None,
            mistakes=_clean_mistakes(content.get("mistakes")),
            vocab_note=_text(content.get("vocab_note_vi")) or None,
            tip=_text(content.get("tip_vi")) or None,
            explanation=explanation)
        result["score"] = _record(item, verdict)
        result["points"] = _award(mode, item, verdict, sentence)
        return result, 200

    # No AI. A fill-the-blank answer that is not the target word is still wrong
    # for vocabulary practice; anything free-form can only be grammar-checked.
    notes = check_with_languagetool(sentence)
    fields = dict(reference=reference or None, explanation=explanation,
                  mistakes=notes["mistakes"] if notes else [],
                  corrected=notes["corrected"] if notes else None)
    if mode == "fill_blank":
        result = _result("incorrect", "languagetool" if notes else "none", **fields)
        result["score"] = _record(item, "incorrect")
        result["points"] = _award(mode, item, "incorrect", sentence)
    else:
        # Nothing judged the sentence, so it neither wins nor loses points.
        result = _result("unchecked", "languagetool" if notes else "none", **fields)
        result["score"] = None
        result["points"] = None
    return result, 200


def check_grammar(text):
    """Returns (body, http status) with corrections for free text."""
    text = (text or "").strip()
    if not text:
        return {"error": "Write some English first."}, 400
    if len(text) > MAX_TEXT_CHARS:
        return {"error": f"Keep the text under {MAX_TEXT_CHARS} characters."}, 400

    prompt = GRAMMAR_PROMPT.format(learner=LEARNER, text=json.dumps(text, ensure_ascii=False))
    content, status = call_gemini_json(prompt, "grammar check", model=GEMINI_PRACTICE_MODEL)
    if status == OK and isinstance(content, dict) and isinstance(content.get("corrected"), str):
        mistakes = _clean_mistakes(content.get("mistakes"))
        return _result("correct" if not mistakes else "incorrect", "ai",
                       corrected=_text(content.get("corrected"), MAX_TEXT_CHARS),
                       mistakes=mistakes, tip=_text(content.get("tip_vi")) or None), 200

    notes = check_with_languagetool(text)
    if notes is None:
        return {"error": "Neither AI nor the grammar checker could be reached. Please try "
                         "again.", "retryable": True}, 503
    return _result("correct" if not notes["mistakes"] else "incorrect", "languagetool",
                   corrected=notes["corrected"], mistakes=notes["mistakes"]), 200
