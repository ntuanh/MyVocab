import os
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

translator_client = None

if GEMINI_API_KEY:
    print(f"INFO: Gemini configured with model '{GEMINI_MODEL}'.")
else:
    print("WARN: GEMINI_API_KEY not found.")

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
    if not GEMINI_API_KEY: return {}
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
            timeout=20,
        )
        if response.status_code != 200:
            print(f"ERROR: Gemini returned {response.status_code} for '{word}': {response.text[:300]}")
            return {}

        parts = response.json()["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts)
        return json.loads(text) if text else {}
    except Exception as e:
        print(f"ERROR calling Gemini for '{word}': {e}")
        return {}


def get_image_from_pexels(query):
    if not PEXELS_API_KEY: return None
    try:
        response = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": PEXELS_API_KEY},
                                params={"query": query, "per_page": 1}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data["photos"][0]["src"]["large"] if data.get("photos") else None
    except Exception as e:
        print(f"ERROR calling Pexels for '{query}': {e}")
        return None


def get_data_from_dictionary_api(word):
    default_result = {"pronunciation": "N/A", "synonyms": []}
    try:
        response = requests.get(f"{DICT_API_URL}{word}", timeout=10)
        if response.status_code == 200:
            data = response.json()[0]

            pronunciation = next((p['text'] for p in data.get('phonetics', []) if p.get('text')), "N/A")

            first_meaning = data.get('meanings', [{}])[0]
            synonyms = first_meaning.get('synonyms', [])[:5] 

            return {"pronunciation": pronunciation, "synonyms": synonyms}
    except Exception as e:
        print(f"ERROR calling Dictionary API for '{word}': {e}")

    return default_result


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

            gemini_data = gemini_future.result()
            image_url = image_future.result()
            dict_data = dict_api_future.result()

        english_definition = gemini_data.get("english_definition")
        vietnamese_meaning = gemini_data.get("vietnamese_meaning")
        example = gemini_data.get("example_sentence")
        family_words = gemini_data.get("family_words", [])

        if english_definition and (not vietnamese_meaning or vietnamese_meaning.strip() == ""):
            vietnamese_meaning = get_translation(english_definition)

        if not english_definition and not vietnamese_meaning:
            return jsonify({'error': f"Could not find information for '{word_to_lookup}'."}), 404

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
