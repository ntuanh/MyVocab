# my_website/handle_request.py

import os
import requests
from flask import jsonify
from dotenv import load_dotenv
from pathlib import Path
import google.generativeai as genai
import json
import datetime
from concurrent.futures import ThreadPoolExecutor

# --- CẤU HÌNH ---
# Đường dẫn đến file lưu trữ
SAVED_WORDS_FILE = Path(__file__).parent.parent / "saved_words.json"

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# API Keys & URLs
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
DICT_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"
PEXELS_API_URL = "https://api.pexels.com/v1/search"

# Khởi tạo model Gemini
gemini_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
        gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest', generation_config=generation_config)
        print("INFO: Gemini model loaded in JSON mode.")
    except Exception as e:
        print(f"WARN: Could not initialize Gemini model: {e}")


# --- HÀM XỬ LÝ CHÍNH (ĐÃ NÂNG CẤP) ---

def get_dictionary_data(user_word):
    word_to_lookup = user_word.strip().lower()
    if ' ' in word_to_lookup:
        return jsonify({'error': "Vui lòng chỉ nhập một từ tiếng Anh."}), 400

    # --- BƯỚC 1: KIỂM TRA TRONG FILE ĐÃ LƯU TRƯỚC ---
    saved_word_data = find_word_in_file(word_to_lookup)
    if saved_word_data:
        print(f"INFO: Found '{word_to_lookup}' in local cache.")
        # Thêm một trường để báo cho frontend biết đây là dữ liệu đã lưu
        saved_word_data['is_saved'] = True
        return jsonify(saved_word_data)

    # --- BƯỚC 2: NẾU KHÔNG CÓ, TIẾP TỤC GỌI API NHƯ CŨ ---
    print(f"INFO: Fetching '{word_to_lookup}' from APIs.")
    if not gemini_model:
        return jsonify({'error': "Lỗi cấu hình: Gemini API chưa sẵn sàng."}), 500

    try:
        # Sử dụng ThreadPoolExecutor để chạy các tác vụ API song song
        with ThreadPoolExecutor(max_workers=2) as executor:
            gemini_future = executor.submit(get_content_from_gemini, word_to_lookup)
            ipa_future = executor.submit(get_ipa_from_dictionary_api, word_to_lookup)

            content_data = gemini_future.result()
            ipa = ipa_future.result()

        if "error" in content_data:
            return jsonify(content_data), 500

        # Gọi Pexels API tuần tự sau khi có content, vì có thể không cần
        image_url = get_image_from_pexels(word_to_lookup) if PEXELS_API_KEY else None

        # Tổng hợp kết quả
        result_data = {
            "word": word_to_lookup,
            "vietnamese_meaning": content_data.get("vietnamese_meaning", "N/A"),
            "english_definition": content_data.get("english_definition", "N/A"),
            "example": content_data.get("example_sentence", "N/A"),
            "pronunciation_ipa": ipa,
            "family_words": content_data.get("family_words", []),
            "image_url": image_url,
            "synonyms": [],
            "is_saved": False  # Báo cho frontend đây là dữ liệu mới
        }

        return jsonify(result_data)
    except Exception as e:
        print(f"Lỗi xử lý chính: {e}")
        return jsonify({'error': "Đã có lỗi xảy ra khi xử lý từ này."}), 500


# --- CÁC HÀM PHỤ ---

def find_word_in_file(word):
    """Tìm một từ trong file JSON. Trả về dữ liệu của từ nếu tìm thấy, ngược lại trả về None."""
    if not SAVED_WORDS_FILE.exists():
        return None
    with open(SAVED_WORDS_FILE, 'r', encoding='utf-8') as f:
        saved_data = json.load(f)
    for item in saved_data:
        if item.get('word') == word:
            return item
    return None


def save_word_to_file(word_data):
    """Lưu dữ liệu của một từ vào file saved_words.json"""
    try:
        saved_data = []
        if SAVED_WORDS_FILE.exists():
            with open(SAVED_WORDS_FILE, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)

        word_to_save = word_data.get('word')
        # Tìm và xóa bản ghi cũ nếu có để cập nhật
        saved_data = [item for item in saved_data if item.get('word') != word_to_save]

        word_data['saved_at'] = datetime.datetime.now().isoformat()
        saved_data.insert(0, word_data)  # Thêm vào đầu danh sách

        with open(SAVED_WORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(saved_data, f, ensure_ascii=False, indent=4)

        return jsonify({'status': 'success', 'message': 'Word saved successfully.'}), 201
    except Exception as e:
        print(f"Lỗi khi lưu file: {e}")
        return jsonify({'error': 'Failed to save data on server.'}), 500


# Các hàm gọi API (get_content_from_gemini, get_ipa_from_dictionary_api, get_image_from_pexels) giữ nguyên như cũ
def get_content_from_gemini(word):
    try:
        prompt = f"""For the English word "{word}", provide these details in JSON format: "english_definition", "vietnamese_meaning", "example_sentence", "family_words" (as an array)."""
        response = gemini_model.generate_content(prompt)
        return json.loads(response.text)
    except Exception as e:
        print(f"Lỗi Gemini: {e}")
        return {"error": "Lỗi khi lấy dữ liệu từ AI."}


def get_ipa_from_dictionary_api(word):
    try:
        response = requests.get(f"{DICT_API_URL}{word}", timeout=5)
        if response.status_code == 200:
            data = response.json()[0]
            return next((p['text'] for p in data.get('phonetics', []) if p.get('text')), 'N/A')
    except Exception as e:
        print(f"Lỗi lấy IPA: {e}")
    return "N/A"


def get_image_from_pexels(query):
    if not PEXELS_API_KEY: return None
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 1, "orientation": "landscape"}
    try:
        response = requests.get(PEXELS_API_URL, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data['photos']:
            return data['photos'][0]['src']['large']
    except Exception as e:
        print(f"Lỗi Pexels: {e}")
    return None