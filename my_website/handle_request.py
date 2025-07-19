# my_website/handle_request.py
# Phiên bản hoàn chỉnh, đã sửa lỗi và tối ưu.

import os
import requests
import json
from flask import jsonify
from concurrent.futures import ThreadPoolExecutor

# Import các thành phần cần thiết
import google.generativeai as genai
from googletrans import Translator  # << SỬA: Import thư viện Translator
from .database import find_word_in_db

# --- CẤU HÌNH ---
# Không cần load_dotenv ở đây nữa, Vercel/Docker sẽ tự nạp biến môi trường
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

# Khởi tạo các client/model một lần duy nhất ở global scope để tái sử dụng
gemini_model = None
translator_client = None

try:
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
        gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest', generation_config=generation_config)
        print("INFO: Gemini model initialized successfully.")
    else:
        print("WARN: GEMINI_API_KEY not found. Gemini features will be disabled.")

    # Khởi tạo Translator client
    translator_client = Translator()
    print("INFO: Googletrans Translator initialized successfully.")

except Exception as e:
    print(f"CRITICAL ERROR during initialization: {e}")


# --- CÁC HÀM TIỆN ÍCH ---

def get_translation(text_to_translate):
    """
    SỬA: Hàm dịch văn bản sử dụng googletrans.
    Trả về 'N/A' nếu có lỗi.
    """
    if not translator_client or not text_to_translate:
        return "N/A"
    try:
        # Dịch từ tiếng Anh sang tiếng Việt
        translation = translator_client.translate(text_to_translate, src='en', dest='vi')
        return translation.text
    except Exception as e:
        print(f"ERROR in get_translation: {e}")
        return "N/A"


# --- CÁC HÀM GỌI API ---

def get_content_from_gemini(word):
    """Gọi Gemini. Trả về một dictionary rỗng {} nếu có lỗi."""
    if not gemini_model: return {}
    try:
        prompt = f"""
        For the English word "{word}", provide these details in a strict JSON format:
        {{
            "english_definition": "A clear, modern, and common English definition.",
            "vietnamese_meaning": "A concise and common Vietnamese meaning.",
            "example_sentence": "A practical example sentence.",
            "family_words": ["noun_form", "verb_form", "adjective_form"]
        }}
        """
        response = gemini_model.generate_content(prompt, request_options={'timeout': 20})
        return json.loads(response.text) if response.text else {}
    except Exception as e:
        print(f"ERROR calling Gemini for '{word}': {e}")
        return {}


def get_image_from_pexels(query):
    """Lấy ảnh từ Pexels. Trả về None nếu có lỗi."""
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
    word_to_lookup = user_word.strip().lower()
    if not word_to_lookup or ' ' in word_to_lookup:
        return jsonify({'error': "Please enter a single English word."}), 400

    # 1. Kiểm tra cache trong DB
    cached_word = find_word_in_db(word_to_lookup)
    if cached_word:
        print(f"INFO: Serving '{word_to_lookup}' from cache.")
        cached_word['is_saved'] = True
        return jsonify(cached_word)

    # 2. Nếu không có cache, gọi các API song song
    print(f"INFO: Fetching '{word_to_lookup}' from APIs.")
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            gemini_future = executor.submit(get_content_from_gemini, word_to_lookup)
            image_future = executor.submit(get_image_from_pexels, word_to_lookup)

            gemini_data = gemini_future.result()
            image_url = image_future.result()

        # 3. Tổng hợp và xử lý dữ liệu
        english_definition = gemini_data.get("english_definition")
        vietnamese_meaning = gemini_data.get("vietnamese_meaning")
        example = gemini_data.get("example_sentence")
        family_words = gemini_data.get("family_words", [])

        # SỬA: Logic dự phòng nếu Gemini không trả về nghĩa tiếng Việt
        if english_definition and not vietnamese_meaning:
            print(f"INFO: Translating definition for '{word_to_lookup}'...")
            vietnamese_meaning = get_translation(english_definition)

        # Kiểm tra xem có dữ liệu hữu ích không
        if not english_definition and not vietnamese_meaning:
            return jsonify({'error': f"Could not find information for '{word_to_lookup}'."}), 404

        result_data = {
            "word": word_to_lookup,
            "vietnamese_meaning": vietnamese_meaning or "N/A",
            "english_definition": english_definition or "N/A",
            "example": example or "N/A",
            "pronunciation_ipa": "N/A",  # Bạn đã xóa DictionaryAPI, nên mục này tạm thời để N/A
            "family_words": family_words,
            "image_url": image_url,
            "synonyms": [],  # Bạn đã xóa DictionaryAPI, nên mục này tạm thời để []
            "is_saved": False
        }

        return jsonify(result_data)

    except Exception as e:
        # Đây là lỗi nghiêm trọng trong logic của chính hàm này
        print(f"CRITICAL ERROR in get_dictionary_data for '{word_to_lookup}': {e}")
        return jsonify({'error': "An unexpected error occurred while processing the word."}), 500