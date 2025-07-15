# my_website/handle_request.py

import os
import requests
from flask import jsonify
from dotenv import load_dotenv
from pathlib import Path
import google.generativeai as genai
import json

# --- CẤU HÌNH ---
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# API Keys & URLs
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
DICT_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"
PEXELS_API_URL = "https://api.pexels.com/v1/search"

# Khởi tạo model Gemini với Chế độ JSON được kích hoạt
gemini_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # SỬA LỖI: Kích hoạt chế độ JSON
        generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
        gemini_model = genai.GenerativeModel(
            'gemini-1.5-flash-latest',
            generation_config=generation_config
        )
        print("INFO: Gemini model loaded in JSON mode.")
    except Exception as e:
        print(f"WARN: Could not initialize Gemini model: {e}")


# Hàm chính
def get_dictionary_data(user_word):
    word_to_lookup = user_word.strip().lower()
    if ' ' in word_to_lookup:
        return jsonify({'error': "Vui lòng chỉ nhập một từ tiếng Anh."}), 400

    if not gemini_model:
        return jsonify({'error': "Lỗi cấu hình: Gemini API chưa sẵn sàng."}), 500

    try:
        # --- BƯỚC 1: GỌI GEMINI ĐỂ LẤY NỘI DUNG CHÍNH ---
        # SỬA LỖI: Prompt đơn giản hơn, không cần yêu cầu định dạng JSON nữa
        gemini_prompt = f"""
        For the English word "{word_to_lookup}", provide these details:
        - english_definition: A clear, modern, and common English definition.
        - vietnamese_meaning: A concise and common Vietnamese meaning.
        - example_sentence: A practical example sentence.
        - family_words: An array of related words (noun, verb, adjective, etc.).
        """

        gemini_response = gemini_model.generate_content(gemini_prompt)
        # SỬA LỖI: Vì đã ở chế độ JSON, `response.text` là một chuỗi JSON hợp lệ
        content_data = json.loads(gemini_response.text)

        # --- BƯỚC 2: GỌI CÁC API PHỤ ---
        ipa = get_ipa_from_dictionary_api(word_to_lookup)
        image_url = get_image_from_pexels(word_to_lookup) if PEXELS_API_KEY else None

        # --- BƯỚC 3: TỔNG HỢP KẾT QUẢ ---
        result_data = {
            "word": word_to_lookup,
            "vietnamese_meaning": content_data.get("vietnamese_meaning", "N/A"),
            "english_definition": content_data.get("english_definition", "N/A"),
            "example": content_data.get("example_sentence", "N/A"),
            "pronunciation_ipa": ipa,
            "family_words": content_data.get("family_words", []),
            "image_url": image_url,
            "synonyms": []
        }

        return jsonify(result_data)

    except Exception as e:
        print(f"Lỗi xử lý chính: {e}")
        return jsonify({'error': "Đã có lỗi xảy ra khi xử lý từ này. Có thể từ không hợp lệ hoặc API gặp sự cố."}), 500


# --- CÁC HÀM PHỤ (giữ nguyên) ---

def get_ipa_from_dictionary_api(word):
    try:
        response = requests.get(DICT_API_URL + word, timeout=5)
        if response.status_code == 200:
            data = response.json()[0]
            return next((p['text'] for p in data.get('phonetics', []) if p.get('text')), 'N/A')
    except Exception as e:
        print(f"Lỗi lấy IPA: {e}")
    return "N/A"


def get_image_from_pexels(query):
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