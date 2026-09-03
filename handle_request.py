import os
import time
import requests
import json
from flask import jsonify
from concurrent.futures import ThreadPoolExecutor

from googletrans import Translator
from database import find_word_in_db, derive_keywords

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
DICT_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"

# Called over plain REST rather than the google-generativeai SDK: that SDK is end
# of life and pulls ~120MB of transitive deps into the Vercel bundle for one call.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# The three upstream fetches run in parallel, so a lookup costs roughly the
# slowest of them plus the translation step. Keep the total comfortably inside
# the Vercel function time limit.
GEMINI_TIMEOUT = float(os.environ.get("GEMINI_TIMEOUT", 8))
PEXELS_TIMEOUT = float(os.environ.get("PEXELS_TIMEOUT", 5))

# api.dictionaryapi.dev has a bimodal response time: usually well under a second,
# but a slice of requests stall for 20s or more. A request that has already
# stalled rarely recovers, so a short per-attempt timeout with a fresh retry
# beats one long wait. DICT_DEADLINE caps what the retries cost in total.
# A healthy response lands in well under a second, so 3s is already generous and
# leaves room for three real tries inside the deadline.
DICT_ATTEMPT_TIMEOUT = float(os.environ.get("DICT_ATTEMPT_TIMEOUT", 3))
DICT_MAX_ATTEMPTS = int(os.environ.get("DICT_MAX_ATTEMPTS", 3))
DICT_DEADLINE = float(os.environ.get("DICT_DEADLINE", 8))
# Below this much budget left, a further attempt would time out before a healthy
# response could arrive, so spend the remainder on failing fast instead.
DICT_MIN_ATTEMPT_TIMEOUT = 1.0

# Outcome of an upstream call. UNAVAILABLE and NOT_FOUND have to stay distinct:
# only NOT_FOUND is evidence that a word does not exist.
OK = "ok"
NOT_FOUND = "not_found"
UNAVAILABLE = "unavailable"
SKIPPED = "skipped"

translator_client = None

if GEMINI_API_KEY:
    print(f"INFO: Gemini configured with model '{GEMINI_MODEL}'.")
else:
    print("WARN: GEMINI_API_KEY not found. Every lookup will fall back to the "
          "dictionary API, so there will be no family words and no Gemini "
          "definitions. Set it in your Vercel project's Environment Variables.")

try:
    translator_client = Translator()
    print("INFO: Googletrans Translator initialized successfully.")
except Exception as e:
    print(f"CRITICAL ERROR during initialization: {e}")


# --- API ---

def get_translation(text_to_translate):
    if not translator_client or not text_to_translate: return "N/A"
    try:
        return translator_client.translate(text_to_translate, src='en', dest='vi').text
    except Exception as e:
        print(f"ERROR in get_translation: {e}")
        return "N/A"


SAFETY_SETTINGS = [
    {"category": c, "threshold": "BLOCK_ONLY_HIGH"}
    for c in ("HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
              "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT")
]


def get_content_from_gemini(word):
    """Returns (content, status). An empty content dict is never silent -- the
    status and the log line say whether the key was missing, the call failed, or
    the model declined to answer."""
    if not GEMINI_API_KEY:
        return {}, SKIPPED
    try:
        prompt = f"""
        Analyze the English word "{word}". 
        Please provide a JSON object with the following keys. If a piece of information is not available, provide an empty string or an empty list.
        {{
            "english_definition": "A clear and common English definition.",
            "vietnamese_meaning": "A concise Vietnamese meaning.",
            "example_sentence": "A practical example sentence using the word.",
            "family_words": ["related_noun", "related_verb", "related_adjective"]
        }}
        """
        response = requests.post(
            f"{GEMINI_API_URL}/{GEMINI_MODEL}:generateContent",
            headers={"x-goog-api-key": GEMINI_API_KEY},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"response_mime_type": "application/json"},
                "safetySettings": SAFETY_SETTINGS,
            },
            timeout=GEMINI_TIMEOUT,
        )
        if response.status_code != 200:
            print(f"ERROR: Gemini returned {response.status_code} for '{word}': {response.text[:300]}")
            return {}, UNAVAILABLE

        payload = response.json()
        candidates = payload.get("candidates") or []
        if not candidates:
            # A safety block or a truncated generation comes back with no
            # candidate at all rather than with an error status.
            print(f"WARN: Gemini returned no candidates for '{word}': {json.dumps(payload)[:300]}")
            return {}, UNAVAILABLE

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        if not text:
            print(f"WARN: Gemini returned an empty body for '{word}'.")
            return {}, UNAVAILABLE
        return json.loads(text), OK
    except Exception as e:
        print(f"ERROR calling Gemini for '{word}': {e}")
        return {}, UNAVAILABLE


def get_image_from_pexels(query):
    if not PEXELS_API_KEY: return None
    try:
        response = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": PEXELS_API_KEY},
                                params={"query": query, "per_page": 1}, timeout=PEXELS_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            return data["photos"][0]["src"]["large"] if data.get("photos") else None
    except Exception as e:
        print(f"ERROR calling Pexels for '{query}': {e}")
        return None


def _fetch_dictionary_entries(word):
    """Returns (entries, status). Retries a stalled or failed request until
    DICT_DEADLINE, and reports NOT_FOUND only when the API itself answered 404."""
    deadline = time.monotonic() + DICT_DEADLINE
    last_error = None

    for attempt in range(1, DICT_MAX_ATTEMPTS + 1):
        remaining = deadline - time.monotonic()
        if remaining < DICT_MIN_ATTEMPT_TIMEOUT:
            break
        try:
            response = requests.get(f"{DICT_API_URL}{word}",
                                    timeout=min(DICT_ATTEMPT_TIMEOUT, remaining))
            if response.status_code == 404:
                return None, NOT_FOUND
            if response.status_code != 200:
                last_error = f"HTTP {response.status_code}"
            else:
                return response.json(), OK
        except Exception as e:
            last_error = e
        print(f"WARN: Dictionary API attempt {attempt}/{DICT_MAX_ATTEMPTS} for "
              f"'{word}' failed: {last_error}")

    print(f"ERROR: Dictionary API unavailable for '{word}': {last_error}")
    return None, UNAVAILABLE


def get_data_from_dictionary_api(word):
    """Pronunciation, synonyms and a fallback definition from the free dictionary API.

    The API returns several entries per word, each with several senses, roughly in
    Wiktionary order -- for "pink" the first is a species of minnow. So scan every
    entry and prefer a sense that ships a usage example, which tracks the common
    meaning far better than simply taking the first one.
    """
    entries, status = _fetch_dictionary_entries(word)
    if entries is None:
        return {"pronunciation": "N/A", "synonyms": [], "definition": None,
                "example": None, "status": status}

    pronunciation = "N/A"
    synonyms = []
    with_example = None
    without_example = None

    for entry in entries:
        if pronunciation == "N/A":
            pronunciation = next((p['text'] for p in entry.get('phonetics', []) if p.get('text')),
                                 "N/A")
        for meaning in entry.get('meanings', []):
            if not synonyms:
                synonyms = meaning.get('synonyms', [])[:5]
            for definition in meaning.get('definitions', []):
                if not definition.get('definition'):
                    continue
                if definition.get('example') and with_example is None:
                    with_example = definition
                elif without_example is None:
                    without_example = definition

    chosen = with_example or without_example or {}
    return {
        "pronunciation": pronunciation,
        "synonyms": synonyms,
        "definition": chosen.get('definition'),
        "example": chosen.get('example'),
        # The API answered, so an entry carrying no usable sense is a real miss.
        "status": OK if chosen else NOT_FOUND,
    }


def get_dictionary_data(user_word):
    word_to_lookup = user_word.strip().lower()
    if not word_to_lookup or ' ' in word_to_lookup:
        return jsonify({'error': "Please enter a single English word."}), 400

    cached_word = find_word_in_db(word_to_lookup)
    if cached_word and cached_word.get('word'):
        print(f"INFO: Serving '{word_to_lookup}' from cache.")
        cached_word['is_saved'] = True
        return jsonify(cached_word)

    print(f"INFO: Fetching '{word_to_lookup}' from APIs.")
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            gemini_future = executor.submit(get_content_from_gemini, word_to_lookup)
            image_future = executor.submit(get_image_from_pexels, word_to_lookup)
            dict_api_future = executor.submit(get_data_from_dictionary_api, word_to_lookup)

            gemini_data, gemini_status = gemini_future.result()
            image_url = image_future.result()
            dict_data = dict_api_future.result()

        english_definition = gemini_data.get("english_definition")
        vietnamese_meaning = gemini_data.get("vietnamese_meaning")
        example = gemini_data.get("example_sentence")
        family_words = gemini_data.get("family_words", [])

        # Gemini is the best source but not the only one. If it is unavailable
        # (no key, quota, retired model) fall back to the free dictionary API
        # rather than discarding a lookup the other sources answered.
        if not english_definition:
            english_definition = dict_data.get("definition")
            if english_definition:
                print(f"INFO: Gemini unavailable for '{word_to_lookup}'; used dictionary API definition.")
        if not example:
            example = dict_data.get("example")

        if english_definition and (not vietnamese_meaning or vietnamese_meaning.strip() == ""):
            vietnamese_meaning = get_translation(english_definition)

        if not english_definition and not vietnamese_meaning:
            # Only call a word missing when every source actually answered. A
            # dictionary API timeout says nothing about whether the word exists,
            # and telling the user it does not is both wrong and unactionable.
            if gemini_status == UNAVAILABLE or dict_data.get("status") == UNAVAILABLE:
                print(f"WARN: No source reachable for '{word_to_lookup}' "
                      f"(gemini={gemini_status}, dictionary={dict_data.get('status')}).")
                return jsonify({
                    'error': f"Could not reach the dictionary service for '{word_to_lookup}'. Please try again.",
                    'retryable': True,
                }), 503
            return jsonify({
                'error': f"Could not find information for '{word_to_lookup}'.",
                'retryable': False,
            }), 404

        result_data = {
            "word": word_to_lookup,
            "vietnamese_meaning": vietnamese_meaning or "N/A",
            "english_definition": english_definition or "N/A",
            "example": example or "N/A",
            "pronunciation_ipa": dict_data.get("pronunciation", "N/A"),
            "family_words": family_words,
            "image_url": image_url,
            "synonyms": dict_data.get("synonyms", []),
            "vietnamese_keywords": derive_keywords(vietnamese_meaning),
            "is_saved": False
        }
        return jsonify(result_data)
    except Exception as e:
        print(f"CRITICAL ERROR in get_dictionary_data for '{word_to_lookup}': {e}")
        return jsonify({'error': "An unexpected error occurred."}), 500
