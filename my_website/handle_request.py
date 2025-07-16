# my_website/handle_request.py

import os
import requests
from flask import jsonify
from dotenv import load_dotenv
from pathlib import Path
import google.generativeai as genai
import json
from concurrent.futures import ThreadPoolExecutor  # Giữ lại để tối ưu tốc độ
from database import find_word_in_db

# --- CẤU HÌNH ---
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
        gemini_model = genai.GenerativeModel(
            'gemini-1.5-flash-latest',
            generation_config=generation_config
        )
        print("INFO: Gemini model loaded in JSON mode.")
    except Exception as e:
        print(f"WARN: Could not initialize Gemini model: {e}")


# --- HÀM XỬ LÝ CHÍNH (ĐÃ ĐƯỢC TÁI CẤU TRÚC) ---
# Hàm chính được cập nhật với logic cache
def get_dictionary_data(user_word):
    word_to_lookup = user_word.strip().lower()
    if ' ' in word_to_lookup:
        return jsonify({'error': "Vui lòng chỉ nhập một từ tiếng Anh."}), 400

    # --- BƯỚC 1: KIỂM TRA TRONG DATABASE (CACHE) TRƯỚC ---
    cached_word = find_word_in_db(word_to_lookup)
    if cached_word:
        print(f"INFO: Found '{word_to_lookup}' in local database. Serving from cache.")
        # Thêm một trường để báo cho frontend biết từ này đã được lưu
        cached_word['is_saved'] = True
        return jsonify(cached_word)

    # --- BƯỚC 2: NẾU KHÔNG CÓ, TIẾP TỤC GỌI CÁC API NHƯ CŨ ---
    print(f"INFO: '{word_to_lookup}' not in cache. Fetching from APIs.")
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            gemini_future = executor.submit(get_content_from_gemini, word_to_lookup)
            dict_api_future = executor.submit(get_data_from_dictionary_api, word_to_lookup)
            image_future = executor.submit(get_image_from_pexels, word_to_lookup)

            gemini_data = gemini_future.result()
            dict_data = dict_api_future.result()
            image_url = image_future.result()

        # Logic dự phòng
        definition = gemini_data.get("english_definition") or dict_data.get("definition", "N/A")
        example = gemini_data.get("example_sentence") or dict_data.get("example", "N/A")
        # ... (phần còn lại của logic dự phòng và tổng hợp kết quả giữ nguyên) ...
        vietnamese_meaning = gemini_data.get("vietnamese_meaning", "N/A")
        if vietnamese_meaning == "N/A" and definition != "N/A":
            vietnamese_meaning = get_translation(definition)

        family_words = gemini_data.get("family_words", [])
        ipa = dict_data.get("pronunciation", "N/A")
        synonyms = dict_data.get("synonyms", [])

        if definition == "N/A" and ipa == "N/A":
            return jsonify({'error': f"Không tìm thấy thông tin cho từ '{word_to_lookup}'."}), 404

        result_data = {
            "word": word_to_lookup,
            "vietnamese_meaning": vietnamese_meaning,
            "english_definition": definition,
            "example": example,
            "pronunciation_ipa": ipa,
            "family_words": family_words,
            "image_url": image_url,
            "synonyms": synonyms,
            "is_saved": False  # Báo cho frontend biết từ này chưa được lưu
        }

        return jsonify(result_data)

    except Exception as e:
        print(f"Lỗi xử lý chính: {e}")
        return jsonify({'error': "Đã có lỗi xảy ra khi xử lý từ này."}), 500


# --- CÁC HÀM PHỤ GỌI API (Được sửa đổi để chống lỗi tốt hơn) ---

def get_content_from_gemini(word):
    """Gọi Gemini. Trả về một dictionary rỗng {} nếu có bất kỳ lỗi nào."""
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
        # Kiểm tra xem Gemini có thực sự trả về nội dung không
        if response.text:
            return json.loads(response.text)
        return {}
    except Exception as e:
        print(f"Lỗi Gemini khi tra từ '{word}': {e}")
        return {}  # Rất quan trọng: trả về dict rỗng để logic dự phòng hoạt động


def get_data_from_dictionary_api(word):
    """Lấy dữ liệu từ Free Dictionary API. Trả về dict rỗng {} nếu có lỗi."""
    try:
        response = requests.get(f"{DICT_API_URL}{word}", timeout=10)
        if response.status_code == 200:
            data = response.json()[0]
            meaning = data.get('meanings', [{}])[0]
            definition_obj = meaning.get('definitions', [{}])[0]

            return {
                "definition": definition_obj.get('definition', 'N/A'),
                "example": definition_obj.get('example', 'N/A'),
                "synonyms": meaning.get('synonyms', [])[:5],  # Giới hạn 5 từ
                "pronunciation": next((p['text'] for p in data.get('phonetics', []) if p.get('text')), 'N/A')
            }
    except Exception as e:
        print(f"Lỗi Dictionary API cho từ '{word}': {e}")
    return {}  # Trả về dict rỗng nếu có lỗi


def get_image_from_pexels(query):
    """Hàm gọi Pexels API. Trả về None nếu có lỗi."""
    if not PEXELS_API_KEY: return None
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 1, "orientation": "landscape"}
    try:
        response = requests.get(PEXELS_API_URL, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('photos'):
            return data['photos'][0]['src']['large']
    except Exception as e:
        print(f"Lỗi Pexels cho từ '{query}': {e}")
    return None

# Các hàm liên quan đến database/file JSON của bạn có thể giữ nguyên và đặt ở đây
# Ví dụ: find_word_in_file, save_word_to_file, get_all_saved_words, delete_word_from_file...
# Tôi sẽ không thêm chúng vào đây để tránh làm bạn rối, bạn chỉ cần giữ nguyên chúng như file cũ.