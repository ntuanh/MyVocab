"""Short English definitions for the words shown as chips on a word card
(Similar and Family). static/js/glosses.js shows one in a box when the learner
points at a chip.

Where a definition comes from, the first that has it:
1. the learner's own saved word, with the definition they keep;
2. word_glosses, the words looked up before (a definition is kept for 30 days,
   and a word that was not found is asked about again after 7);
3. Wiktionary's free REST API (no key, no AI quota). Its text is CC BY-SA, so the
   box names it as the source.
"""
import html
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import requests

from .database import saved_definitions, cached_glosses, store_glosses

WIKTIONARY_URL = "https://en.wiktionary.org/api/rest_v1/page/definition/{}"
# Wikimedia asks every client to say who it is.
HEADERS = {"User-Agent": "MyVocab (https://github.com/ntuanh/MyVocab; personal English study)"}
TIMEOUT = 5
MAX_WORDS = 16
MAX_LENGTH = 220
KEEP_DAYS, MISS_DAYS = 30, 7
WORD = re.compile(r"^[a-z][a-z' -]{0,39}$")
# Senses a learner should not meet first.
OLD_SENSES = ("obsolete", "archaic", "dated", "rare", "nonstandard", "historical")


def clean(words):
    """The words worth asking about: lower case, plain letters, no repeats, at most MAX_WORDS."""
    out = []
    for word in words or []:
        word = str(word).strip().lower()
        if WORD.match(word) and word not in out:
            out.append(word)
    return out[:MAX_WORDS]


def plain(fragment):
    """Wiktionary's HTML definition as plain text."""
    text = html.unescape(re.sub(r"<[^>]+>", "", fragment or ""))
    return re.sub(r"\s+", " ", text).strip()


def shorten(text):
    if len(text) <= MAX_LENGTH:
        return text
    return text[:MAX_LENGTH].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def from_wiktionary(word):
    """(definition dict or None, found?) — found is None when Wiktionary did not answer."""
    try:
        response = requests.get(WIKTIONARY_URL.format(quote(word)), headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException:
        return None, None
    if response.status_code == 404:
        return None, False
    if response.status_code != 200:
        return None, None
    try:
        entries = response.json().get("en", [])
    except ValueError:
        return None, None
    for entry in entries:
        for sense in entry.get("definitions", []):
            text = plain(sense.get("definition"))
            if not text or any(label in text[:40].lower() for label in OLD_SENSES):
                continue
            return {"definition": shorten(text), "part_of_speech": (entry.get("partOfSpeech") or "").lower(),
                    "source": "Wiktionary"}, True
    return None, False


def glosses(words):
    """{word: {definition, part_of_speech, source} or None} for the given words."""
    words = clean(words)
    if not words:
        return {}
    out = {}
    for word, definition in (saved_definitions(words) or {}).items():
        out[word] = {"definition": shorten(definition), "part_of_speech": "", "source": "your words"}
    rest = [w for w in words if w not in out]
    cached = cached_glosses(rest, KEEP_DAYS, MISS_DAYS) or {}
    for word, row in cached.items():
        out[word] = ({"definition": row["definition"], "part_of_speech": row["part_of_speech"] or "",
                      "source": row["source"]} if row["definition"] else None)
    to_fetch = [w for w in rest if w not in cached]
    if to_fetch:
        with ThreadPoolExecutor(max_workers=min(8, len(to_fetch))) as pool:
            fetched = dict(zip(to_fetch, pool.map(from_wiktionary, to_fetch)))
        keep = []
        for word, (gloss, found) in fetched.items():
            out[word] = gloss
            if found is not None:  # a miss is kept too; no answer at all is tried again next time
                keep.append(dict(gloss or {}, word=word))
        if keep:
            store_glosses(keep)
    return {word: out.get(word) for word in words}
