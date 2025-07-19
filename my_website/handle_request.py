# my_website/handle_request.py
# Phiên bản cải tiến để tăng độ ổn định khi gọi API

import os
import requests
import json
from flask import jsonify
from concurrent.futures import ThreadPoolExecutor

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from googletrans import Translator
from .database import find_word_in_db

# --- CẤU HÌNH ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

# Khởi tạo các client/model một lần duy nhất
gemini_model = None
translator_client = None

try:
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)

        # SỬA 1: Cấu hình an toàn "dễ tính" hơn
        # Cho phép các nội dung có xác suất rủi ro thấp và trung bình.
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }

        generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
        gemini_model = genai.GenerativeModel(
            'gemini-1.5-flash-latest',
            generation_config=generation_config,
            safety_settings=safety_settings  # Áp dụng cấu hình an toàn
        )
        print("INFO: Gemini model initialized successfully with adjusted safety settings.")
    else:
        print("WARN: GEMINI_API_KEY not found.")

    translator_client = Translator()
    print("INFO: Googletrans Translator initialized successfully.")

except Exception as e:
    print(f"CRITICAL ERROR during initialization: {e}")


# --- CÁC HÀM TIỆN ÍCH VÀ GỌI API ---

def get_translation(text_to_translate):
    if not translator_client or not text_to_translate: return "N/A"
    try:
        return translator_client.translate(text_to_translate, src='en', dest='vi').text
    except Exception as e:
        print(f"ERROR in get_translation: {e}")
        return "N/A"


def get_content_from_gemini(word):
    print("\n--- [DEBUG] ENTERING get_content_from_gemini ---")
    print(f"[DEBUG] Word to process: {word}")

    if not gemini_model:
        print("[DEBUG] EXIT: gemini_model is not initialized.")
        return {}

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
        print(f"[DEBUG] Generated prompt: {prompt}")
        print("[DEBUG] Sending request to Gemini API...")

        response = gemini_model.generate_content(prompt, request_options={'timeout': 20})

        print("[DEBUG] Received response from Gemini.")

        # --- PHẦN DEBUG QUAN TRỌNG NHẤT ---
        # In toàn bộ đối tượng response để kiểm tra
        print(f"[DEBUG] Full Gemini response object: {response}")

        # Kiểm tra xem có bị chặn vì lý do an toàn không
        if response.prompt_feedback.block_reason:
            print(f"[DEBUG] EXIT: Request was blocked. Reason: {response.prompt_feedback.block_reason}")
            return {}

        # Kiểm tra xem có text trả về không
        if not response.parts:
            print("[DEBUG] EXIT: Response has no parts (response.parts is empty).")
            return {}

        response_text = response.text
        print(f"[DEBUG] Extracted response.text: {response_text}")

        # Thử parse JSON
        try:
            parsed_json = json.loads(response_text)
            print(f"[DEBUG] Successfully parsed JSON: {parsed_json}")
            print("--- [DEBUG] EXITING get_content_from_gemini (SUCCESS) ---")
            return parsed_json
        except json.JSONDecodeError as json_error:
            print(f"[DEBUG] EXIT: JSONDecodeError. Could not parse the response text.")
            print(f"[DEBUG] JSON Error details: {json_error}")
            return {}

    except Exception as e:
        print(f"[DEBUG] EXIT: An unexpected exception occurred in the main try block.")
        print(f"[DEBUG] Exception details: {e}")
        # In traceback chi tiết nếu có thể (hữu ích trên Vercel)
        import traceback
        traceback.print_exc()
        return {}
def get_image_from_pexels(query):
    # Hàm này đã ổn, giữ nguyên
    if not PEXELS_API_KEY: return None
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 1}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data["photos"][0]["src"]["large"] if data.get("photos") else None
    except Exception as e:
        print(f"ERROR calling Pexels for '{query}': {e}")
        return None


# --- HÀM XỬ LÝ CHÍNH ---

def get_dictionary_data(user_word):
    # Code trong hàm này đã tốt, không cần sửa
    word_to_lookup = user_word.strip().lower()
    if not word_to_lookup or ' ' in word_to_lookup:
        return jsonify({'error': "Please enter a single English word."}), 400

    cached_word = find_word_in_db(word_to_lookup)
    if cached_word:
        print(f"INFO: Serving '{word_to_lookup}' from cache.")
        cached_word['is_saved'] = True
        return jsonify(cached_word)

    print(f"INFO: Fetching '{word_to_lookup}' from APIs.")
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            gemini_future = executor.submit(get_content_from_gemini, word_to_lookup)
            image_future = executor.submit(get_image_from_pexels, word_to_lookup)
            gemini_data = gemini_future.result()
            image_url = image_future.result()

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
            "pronunciation_ipa": "N/A",
            "family_words": family_words,
            "image_url": image_url,
            "synonyms": [],
            "is_saved": False
        }
        return jsonify(result_data)
    except Exception as e:
        print(f"CRITICAL ERROR in get_dictionary_data for '{word_to_lookup}': {e}")
        return jsonify({'error': "An unexpected error occurred."}), 500