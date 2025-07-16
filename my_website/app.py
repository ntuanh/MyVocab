# my_website/app.py

from flask import Flask, render_template, request, jsonify

# Import tất cả các hàm cần thiết từ các file khác
from handle_request import get_dictionary_data
from database import (
    init_db,
    save_word,
    get_word_for_exam,
    update_word_score,
    get_all_saved_words,
    delete_word_by_id,
    get_correct_answer_by_id,
    get_all_topics,
    add_new_topic,
    delete_topic_by_id
)

# Khởi tạo ứng dụng Flask
app = Flask(__name__)

# Khởi tạo database một lần duy nhất khi ứng dụng bắt đầu
# Thao tác này sẽ tạo file myvocab.db và các bảng nếu chúng chưa tồn tại.
with app.app_context():
    init_db()


# --- CÁC ROUTE ĐỂ RENDER TRANG (HTML) ---

@app.route('/')
def index():
    """Render trang tra từ điển chính."""
    return render_template('index.html')


@app.route('/add_topic', methods=['POST'])
def add_topic_route():
    data = request.get_json()
    topic_name = data.get('topic_name')
    if not topic_name:
        return jsonify({"error": "Topic name cannot be empty."}), 400

    new_topic = add_new_topic(topic_name.strip())
    if new_topic:
        return jsonify(new_topic), 201  # 201 Created
    else:
        return jsonify({"error": "Failed to create topic."}), 500

@app.route('/exam')
def exam_page():
    """Render trang kiểm tra từ vựng."""
    # Lấy danh sách chủ đề để truyền sang cho trang exam
    topics = get_all_topics()
    return render_template('exam.html', topics=topics)


@app.route('/data')
def data_page():
    """Render trang hiển thị tất cả các từ đã lưu."""
    saved_words = get_all_saved_words()
    return render_template('data.html', words=saved_words)


# --- CÁC ENDPOINT API (TRẢ VỀ DỮ LIỆU JSON) ---

@app.route('/lookup', methods=['POST'])
def lookup_route():
    """API để tra cứu một từ."""
    data = request.get_json()
    user_message = data.get('message')
    # get_dictionary_data đã trả về một phản hồi JSON hoàn chỉnh
    return get_dictionary_data(user_message)


@app.route('/save_word', methods=['POST'])
def save_word_route():
    """API để lưu một từ và các chủ đề liên quan."""
    print("\n--- Received request on /save_word ---")  # Báo hiệu đã nhận được request

    data = request.get_json()
    print(f"Request JSON data: {data}")  # In ra toàn bộ dữ liệu frontend gửi lên

    word_data = data.get('word_data')
    topic_ids = data.get('topic_ids', [])

    # In ra các biến đã được bóc tách
    print(f"Extracted word_data: {word_data}")
    print(f"Extracted topic_ids: {topic_ids}")

    if not word_data or not isinstance(word_data, dict):
        print("ERROR: word_data is invalid or missing. Aborting.")
        return jsonify({"error": "Dữ liệu từ không hợp lệ hoặc bị thiếu."}), 400

    # Gọi hàm lưu và xem kết quả
    print("Calling database.save_word...")
    result = save_word(word_data, topic_ids)
    print(f"Result from database.save_word: {result}")

    return jsonify(result)

@app.route('/manage_topics')
def manage_topics_page():
    """Render trang quản lý các chủ đề."""
    topics = get_all_topics()
    return render_template('manage_topics.html', topics=topics)

@app.route('/delete_topic/<int:topic_id>', methods=['DELETE'])
def delete_topic_route(topic_id):
    """API để xóa một chủ đề."""
    # Thêm một lớp bảo vệ để không cho xóa chủ đề mặc định
    if topic_id == 1: # Giả sử 'Daily life' có ID là 1
        return jsonify({"error": "Cannot delete the default topic."}), 403
    result = delete_topic_by_id(topic_id)
    return jsonify(result)

@app.route('/get_exam_word', methods=['POST'])
def get_exam_word_route():
    """API để lấy một từ để kiểm tra, có thể lọc theo chủ đề."""
    data = request.get_json()
    topic_ids = data.get('topic_ids', None)

    word = get_word_for_exam(topic_ids)

    if word:
        return jsonify(word)

    # Sửa lỗi: Đảm bảo chuỗi được đóng đúng cách
    return jsonify({"error": "Không có từ nào phù hợp với chủ đề đã chọn."}), 404


@app.route('/submit_answer', methods=['POST'])
def submit_answer_route():
    """API để cập nhật điểm sau khi người dùng trả lời."""
    data = request.get_json()
    word_id = data.get('id')
    is_correct = data.get('is_correct')
    result = update_word_score(word_id, is_correct)
    return jsonify(result)


@app.route('/get_answer/<int:word_id>', methods=['GET'])
def get_answer_route(word_id):
    """API để lấy đáp án đúng cho một từ."""
    correct_answer = get_correct_answer_by_id(word_id)

    if correct_answer is not None:
        return jsonify({"correct_answer": correct_answer})
    return jsonify({"error": "Word not found in database."}), 404


@app.route('/delete_word/<int:word_id>', methods=['DELETE'])
def delete_word_route(word_id):
    """API để xóa một từ."""
    result = delete_word_by_id(word_id)
    return jsonify(result)


@app.route('/get_topics', methods=['GET'])
def get_topics_route():
    """API để lấy danh sách tất cả các chủ đề."""
    topics = get_all_topics()
    return jsonify(topics)


# Đoạn này để có thể chạy server trực tiếp bằng lệnh `python my_website/app.py`
if __name__ == '__main__':
    app.run(debug=True)