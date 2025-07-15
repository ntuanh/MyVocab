# my_website/handle_request.py

import os
import requests
from flask import jsonify  # Import jsonify để tạo phản hồi JSON
from dotenv import load_dotenv
from pathlib import Path
from googletrans import Translator

# --- CẤU HÌNH ---
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
API_BASE_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"
translator = Translator()


def get_dictionary_data(user_word):
    """
    Lấy dữ liệu từ điển và trả về một đối tượng dictionary của Python.
    """
    word_to_lookup = user_word.strip().lower()
    if ' ' in word_to_lookup:
        # Thay vì trả về chuỗi, trả về JSON lỗi
        return jsonify({'error': "Vui lòng chỉ nhập một từ tiếng Anh."}), 400

    try:
        url = API_BASE_URL + word_to_lookup
        response = requests.get(url, timeout=10)

        if response.status_code == 404:
            return jsonify({'error': f"Không tìm thấy từ '{word_to_lookup}' trong từ điển."}), 404

        response.raise_for_status()
        data = response.json()[0]

        # Bóc tách dữ liệu
        meaning = data.get('meanings', [{}])[0]
        definition_obj = meaning.get('definitions', [{}])[0]
        definition = definition_obj.get('definition', 'N/A')
        example = definition_obj.get('example', 'N/A')

        # Dịch định nghĩa sang tiếng Việt
        vietnamese_meaning = "N/A"
        if definition != 'N/A':
            try:
                translation = translator.translate(definition, src='en', dest='vi')
                vietnamese_meaning = translation.text
            except Exception as e:
                print(f"Lỗi dịch: {e}")

        # Tạo một dictionary để trả về
        result_data = {
            "word": data.get('word', user_word),
            "vietnamese_meaning": vietnamese_meaning,
            "english_definition": definition,
            "example": example
            # Các trường khác sẽ được thêm sau (image, synonyms, family_words)
        }

        # Trả về dữ liệu dưới dạng JSON
        return jsonify(result_data)

    except requests.exceptions.RequestException as e:
        return jsonify({'error': "Lỗi kết nối, không thể truy cập từ điển."}), 500
    except Exception as e:
        print(f"Lỗi xử lý: {e}")
        return jsonify({'error': "Đã có lỗi xảy ra trong quá trình xử lý."}), 500