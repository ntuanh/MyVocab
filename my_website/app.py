# my_website/app.py
# Phiên bản đã sửa lỗi trùng lặp endpoint và gộp logic.

import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

# --- IMPORTS ---
from .handle_request import get_dictionary_data
from .database import (
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

# --- FLASK APP SETUP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            static_folder=os.path.join(BASE_DIR, 'static'),
            template_folder=os.path.join(BASE_DIR, 'templates'))

# Cần secret key để Flask session hoạt động
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a_super_secret_key_for_local_development_only")


# --- PAGE ROUTES (RENDER HTML) ---

@app.route('/')
def index():
    """Trang từ điển chính."""
    return render_template('index.html')

@app.route('/exam')
def exam_page():
    """Trang làm bài kiểm tra."""
    topics = get_all_topics()
    return render_template('exam.html', topics=topics)

# <<< SỬA LỖI: Gộp hai hàm data_page thành một >>>
@app.route('/data')
def data_page():
    """
    Trang xem dữ liệu.
    Hàm này giờ đây vừa bảo vệ route, vừa lấy dữ liệu.
    """
    # 1. "Người gác cổng": Kiểm tra quyền truy cập trong session
    if not session.get('data_access_granted'):
        # Nếu chưa được cấp quyền, chuyển hướng về trang chủ
        return redirect(url_for('index'))

    # 2. Nếu đã được cấp quyền, lấy dữ liệu và render trang
    # (Code này được chuyển từ hàm data_page bị trùng lặp)
    saved_words = get_all_saved_words()
    return render_template('data.html', words=saved_words)


@app.route('/manage_topics')
def manage_topics_page():
    """Trang quản lý chủ đề."""
    topics = get_all_topics()
    return render_template('manage_topics.html', topics=topics)


# --- API ENDPOINTS (RETURN JSON) ---

@app.route('/api/verify_password', methods=['POST'])
def verify_password():
    """Xác thực mật khẩu để xem dữ liệu."""
    correct_password = os.environ.get('VIEW_DATA_PASSWORD')
    if not correct_password:
        return jsonify({'error': 'Server configuration error'}), 500

    data = request.get_json()
    submitted_password = data.get('password')

    if submitted_password == correct_password:
        session['data_access_granted'] = True
        return jsonify({'status': 'success'}), 200
    else:
        return jsonify({'error': 'Incorrect password'}), 401

@app.route('/api/all_data')
def get_all_data():
    """API endpoint để lấy tất cả dữ liệu (cũng được bảo vệ bằng session)."""
    if not session.get('data_access_granted'):
        return jsonify({'error': 'Unauthorized'}), 401
    words = get_all_saved_words()
    return jsonify(words)

@app.route('/lookup', methods=['POST'])
def lookup_route():
    """API endpoint để tra từ."""
    data = request.get_json()
    user_message = data.get('message')
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    return get_dictionary_data(user_message)

@app.route('/save_word', methods=['POST'])
def save_word_route():
    """API endpoint để lưu từ."""
    data = request.get_json()
    word_data = data.get('word_data')
    topic_ids = data.get('topic_ids', [])
    if not word_data or not isinstance(word_data, dict):
        return jsonify({"error": "Word data is missing or invalid."}), 400
    result = save_word(word_data, topic_ids)
    return jsonify(result)

@app.route('/get_exam_word', methods=['POST'])
def get_exam_word_route():
    """API endpoint để lấy từ cho bài kiểm tra."""
    data = request.get_json()
    topic_ids = data.get('topic_ids', None)
    word = get_word_for_exam(topic_ids)
    if word:
        return jsonify(word)
    return jsonify({"error": "No words found for the selected topics."}), 404

@app.route('/submit_answer', methods=['POST'])
def submit_answer_route():
    """API endpoint để gửi đáp án và cập nhật điểm."""
    data = request.get_json()
    word_id = data.get('id')
    is_correct = data.get('is_correct')
    result = update_word_score(word_id, is_correct)
    return jsonify(result)

@app.route('/get_answer/<int:word_id>', methods=['GET'])
def get_answer_route(word_id):
    """API endpoint để lấy đáp án đúng."""
    correct_answer = get_correct_answer_by_id(word_id)
    if correct_answer is not None:
        return jsonify({"correct_answer": correct_answer})
    return jsonify({"error": "Word not found in database."}), 404

@app.route('/delete_word/<int:word_id>', methods=['DELETE'])
def delete_word_route(word_id):
    """API endpoint để xóa từ."""
    result = delete_word_by_id(word_id)
    return jsonify(result)

@app.route('/get_topics', methods=['GET'])
def get_topics_route():
    """API endpoint để lấy danh sách chủ đề."""
    topics = get_all_topics()
    return jsonify(topics)

@app.route('/add_topic', methods=['POST'])
def add_topic_route():
    """API endpoint để thêm chủ đề mới."""
    data = request.get_json()
    topic_name = data.get('topic_name')
    if not topic_name:
        return jsonify({"error": "Topic name cannot be empty."}), 400
    new_topic = add_new_topic(topic_name.strip())
    if new_topic:
        return jsonify(new_topic), 201
    return jsonify({"error": "Failed to create topic."}), 500

@app.route('/delete_topic/<int:topic_id>', methods=['DELETE'])
def delete_topic_route(topic_id):
    """API endpoint để xóa chủ đề."""
    result = delete_topic_by_id(topic_id)
    return jsonify(result)