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
SAVED_WORDS_FILE = Path(__file__).parent.parent / "saved_words.json"
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# API Keys & URLs
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
DICT_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"
PEXELS_API_URL = "https://api.pexels.com/v1/search"

# Khởi tạo các model Gemini
gemini_model_json = None
gemini_model_text = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Model chính để lấy nội dung, có chế độ JSON
        json_generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
        gemini_model_json = genai.GenerativeModel('gemini-1.5-flash-latest', generation_config=json_generation_config)

        # Model phụ để sửa lỗi chính tả, không cần chế độ JSON
        gemini_model_text = genai.GenerativeModel('gemini-1.5-flash-latest')
        print("INFO: Gemini models loaded (JSON and Text).")
    except Exception as e:
        print(f"WARN: Could not initialize Gemini model: {e}")


# --- HÀM XỬ LÝ CHÍNH ---
def get_dictionary_data(user_word):
    word_to_lookup = user_word.strip().lower()
    if ' ' in word_to_lookup:
        return jsonify({'error': "Vui lòng chỉ nhập một từ tiếng Anh."}), 400

    # Kiểm tra trong file đã lưu trước
    saved_word_data = find_word_in_file(word_to_lookup)
    if saved_word_data:
        print(f"INFO: Found '{word_to_lookup}' in local cache.")
        saved_word_data['is_saved'] = True
        return jsonify(saved_word_data)

    print(f"INFO: Fetching '{word_to_lookup}' from APIs.")
    try:
        # Gọi Dictionary API trước
        dict_response = requests.get(f"{DICT_API_URL}{word_to_lookup}", timeout=10)

        # Logic gợi ý khi có lỗi 404
        if dict_response.status_code == 404:
            suggestion = get_spelling_suggestion_from_gemini(word_to_lookup)
            error_message = f"Không tìm thấy từ '{word_to_lookup}'."
            return jsonify({'error': error_message, 'suggestion': suggestion}), 404

        dict_response.raise_for_status()
        dict_data = dict_response.json()[0]

        # Nếu tìm thấy, tiếp tục lấy các thông tin khác
        return get_full_word_details(dict_data)

    except Exception as e:
        print(f"Lỗi xử lý chính: {e}")
        return jsonify({'error': "Đã có lỗi xảy ra khi xử lý từ này."}), 500


def get_full_word_details(dict_data):
    """Hàm tách nhỏ để xử lý khi đã có dữ liệu từ điển."""
    word = dict_data.get('word')

    if not gemini_model_json:
        return jsonify({'error': "Lỗi cấu hình: Gemini API chưa sẵn sàng."}), 500

    with ThreadPoolExecutor(max_workers=2) as executor:
        gemini_future = executor.submit(get_content_from_gemini, word)
        image_future = executor.submit(get_image_from_pexels, word)

        content_data = gemini_future.result()
        image_url = image_future.result()

    ipa = get_ipa_from_dictionary_data(dict_data)

    if "error" in content_data:
        return jsonify(content_data), 500

    result_data = {
        "word": word,
        "vietnamese_meaning": content_data.get("vietnamese_meaning", "N/A"),
        "english_definition": content_data.get("english_definition", "N/A"),
        "example": content_data.get("example_sentence", "N/A"),
        "pronunciation_ipa": ipa,
        "family_words": content_data.get("family_words", []),
        "image_url": image_url,
        "synonyms": dict_data.get('meanings', [{}])[0].get('synonyms', [])[:5],
        "is_saved": False
    }
    return jsonify(result_data)


# --- HÀM GỢI Ý ---
def get_spelling_suggestion_from_gemini(wrong_word):
    """Gọi Gemini để sửa lỗi chính tả."""
    if not gemini_model_text: return None
    try:
        prompt = f"A user typed '{wrong_word}', which seems to be a spelling mistake. What is the most likely correct English word? Respond with only the single correct word, nothing else. For example, if the input is 'chiken', you respond 'chicken'."
        response = gemini_model_text.generate_content(prompt)
        # Lấy từ được sửa, làm sạch các ký tự thừa và kiểm tra
        suggestion = response.text.strip().lower().split()[0]  # Lấy từ đầu tiên để đảm bảo là 1 từ
        # Kiểm tra xem có phải là một từ hợp lệ không
        if suggestion.isalpha():
            return suggestion
        return None
    except Exception as e:
        print(f"Lỗi khi lấy gợi ý từ Gemini: {e}")
        return None


# --- CÁC HÀM PHỤ ---

# (Hàm find_word_in_file và save_word_to_file giữ nguyên như phiên bản trước)
def find_word_in_file(word):
    if not SAVED_WORDS_FILE.exists(): return None
    with open(SAVED_WORDS_FILE, 'r', encoding='utf-8') as f:
        saved_data = json.load(f)
    for item in saved_data:
        if item.get('word') == word: return item
    return None


def save_word_to_file(word_data):
    try:
        saved_data = []
        if SAVED_WORDS_FILE.exists():
            with open(SAVED_WORDS_FILE, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
        word_to_save = word_data.get('word')
        saved_data = [item for item in saved_data if item.get('word') != word_to_save]
        word_data['saved_at'] = datetime.datetime.now().isoformat()
        saved_data.insert(0, word_data)
        with open(SAVED_WORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(saved_data, f, ensure_ascii=False, indent=4)
        return jsonify({'status': 'success'}), 201
    except Exception as e:
        print(f"Lỗi khi lưu file: {e}")
        return jsonify({'error': 'Failed to save data on server.'}), 500


# Các hàm gọi API
def get_content_from_gemini(word):
    try:
        prompt = f"""For "{word}", provide JSON with: "english_definition", "vietnamese_meaning", "example_sentence", "family_words" (array)."""
        response = gemini_model_json.generate_content(prompt)
        return json.loads(response.text)
    except Exception as e:
        print(f"Lỗi Gemini: {e}")
        return {"error": "Lỗi khi lấy dữ liệu từ AI."}


def get_ipa_from_dictionary_data(data):
    try:
        return next((p['text'] for p in data.get('phonetics', []) if p.get('text')), 'N/A')
    except:
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

# Thêm hàm này vào cuối file handle_request.py

def get_all_saved_words():
    """Đọc và trả về tất cả các từ trong file saved_words.json."""
    try:
        if SAVED_WORDS_FILE.exists():
            with open(SAVED_WORDS_FILE, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            return jsonify(saved_data)
        else:
            # Trả về một danh sách rỗng nếu file không tồn tại
            return jsonify([])
    except Exception as e:
        print(f"Lỗi khi đọc file đã lưu: {e}")
        return jsonify({"error": "Không thể đọc dữ liệu đã lưu."}), 500


# Thêm vào cuối file handle_request.py

def delete_word_from_file(word_to_delete):
    """Xóa một từ khỏi file saved_words.json."""
    try:
        if not SAVED_WORDS_FILE.exists():
            return jsonify({"error": "File không tồn tại."}), 404

        with open(SAVED_WORDS_FILE, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)

        # Tạo một danh sách mới không chứa từ cần xóa
        # So sánh chữ thường để đảm bảo tìm đúng
        original_length = len(saved_data)
        new_data = [item for item in saved_data if item.get('word', '').lower() != word_to_delete.lower()]

        # Kiểm tra xem có thực sự xóa được từ nào không
        if len(new_data) == original_length:
            return jsonify({"error": "Không tìm thấy từ để xóa."}), 404

        # Ghi lại file với danh sách mới
        with open(SAVED_WORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, ensure_ascii=False, indent=4)

        return jsonify({"status": "success", "message": f"Đã xóa từ '{word_to_delete}'."})

    except Exception as e:
        print(f"Lỗi khi xóa file: {e}")
        return jsonify({'error': 'Lỗi server khi xóa từ.'}), 500