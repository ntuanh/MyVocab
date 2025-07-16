# my_website/app.py
from flask import Flask, render_template, request, jsonify
from handle_request import get_dictionary_data
# Import các hàm từ database.py
from database import init_db, save_word, get_word_for_exam, update_word_score , get_all_saved_words , delete_word_by_id
from database import get_correct_answer_by_id

app = Flask(__name__)
# Khởi tạo database khi ứng dụng bắt đầu
init_db()


# --- Endpoint tra từ điển (giữ nguyên) ---
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/lookup', methods=['POST'])  # Đổi tên endpoint cho rõ ràng
def lookup():
    data = request.get_json()
    user_message = data.get('message')
    return get_dictionary_data(user_message)


# --- Các Endpoint mới cho chức năng Lưu và Kiểm tra ---

@app.route('/save_word', methods=['POST'])
def save_word_route():
    word_data = request.get_json()
    result = save_word(word_data)
    return jsonify(result)

@app.route('/exam')
def exam_page():
    return render_template('exam.html')

@app.route('/delete_word/<int:word_id>', methods=['DELETE'])
def delete_word_route(word_id):
    """Endpoint để xóa một từ."""
    result = delete_word_by_id(word_id)
    return jsonify(result)

@app.route('/data')
def data_page():
    """Trang hiển thị tất cả các từ đã lưu."""
    saved_words = get_all_saved_words()
    return render_template('data.html', words=saved_words)

@app.route('/get_exam_word', methods=['GET'])
def get_exam_word_route():
    word = get_word_for_exam()
    if word:
        return jsonify(word)
    return jsonify({"error": "Không có từ nào để kiểm tra. Hãy lưu một vài từ trước!"}), 404


@app.route('/submit_answer', methods=['POST'])
def submit_answer_route():
    data = request.get_json()
    word_id = data.get('id')
    user_answer = data.get('answer')

    # Logic kiểm tra đơn giản (so sánh chuỗi sau khi làm sạch)
    # Trong thực tế, có thể cần logic so sánh linh hoạt hơn
    # Ở đây chúng ta sẽ lấy đáp án đúng từ DB và để frontend so sánh
    is_correct = data.get('is_correct')  # Giả sử frontend tự quyết định đúng/sai trước
    result = update_word_score(word_id, is_correct)

    return jsonify(result)


@app.route('/get_answer/<int:word_id>', methods=['GET'])
def get_answer_route(word_id):
    """Endpoint để lấy đáp án đúng cho một từ."""
    correct_answer = get_correct_answer_by_id(word_id)

    if correct_answer is not None:
        return jsonify({"correct_answer": correct_answer})
    else:
        return jsonify({"error": "Word not found in database."}), 404


if __name__ == '__main__':
    app.run(debug=True)