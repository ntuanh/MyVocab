import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

from .handle_request import get_dictionary_data
from .database import (
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

# A secret key is required for Flask sessions to work.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a_super_secret_key_for_local_development_only")

@app.route('/')
def index():
    """Renders the main dictionary page."""
    return render_template('index.html')

@app.route('/exam')
def exam_page():
    """Renders the exam page."""
    return render_template('exam.html')

@app.route('/data')
def data_page():    
    if not session.get('data_access_granted'):
        return redirect(url_for('index'))
    return render_template('data.html')

@app.route('/manage_topics')
def manage_topics_page():
    """Renders the topic management page."""
    return render_template('manage_topics.html')

@app.route('/api/verify_password', methods=['POST'])
def verify_password():
    """Verifies the password for accessing the data page."""
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
    """API endpoint to fetch all saved data (protected by session)."""
    if not session.get('data_access_granted'):
        return jsonify({'error': 'Unauthorized'}), 401
    words = get_all_saved_words()
    return jsonify(words)

@app.route('/api/lookup', methods=['POST'])
def lookup_route():
    """API endpoint to look up a word."""
    data = request.get_json()
    user_word = data.get('word') # Assuming the key is 'word' now
    if not user_word:
        return jsonify({'error': 'No word provided'}), 400
    return get_dictionary_data(user_word)

@app.route('/api/save_word', methods=['POST'])
def save_word_route():
    """API endpoint to save a word."""
    data = request.get_json()
    word_data = data.get('word_data')
    topic_ids = data.get('topic_ids', [])
    if not word_data:
        return jsonify({"error": "Word data is missing."}), 400
    result = save_word(word_data, topic_ids)
    return jsonify(result)

@app.route('/api/get_exam_word', methods=['POST'])
def get_exam_word_route():
    """API endpoint to get a word for the exam."""
    data = request.get_json()
    topic_ids = data.get('topic_ids', None)
    word = get_word_for_exam(topic_ids)
    if word:
        return jsonify(word)
    return jsonify({"error": "No words found for the selected topics."}), 404

@app.route('/api/submit_answer', methods=['POST'])
def submit_answer_route():
    """API endpoint to submit an exam answer."""
    data = request.get_json()
    word_id = data.get('id')
    is_correct = data.get('is_correct')
    result = update_word_score(word_id, is_correct)
    return jsonify(result)


@app.route('/api/get_answer', methods=['GET'])  # Bỏ <int:word_id> khỏi URL
def get_answer_route():
    # Lấy 'id' từ query parameter của URL
    word_id = request.args.get('id', type=int)

    if not word_id:
        return jsonify({"error": "Word ID is required."}), 400

    answer_data = get_correct_answer_by_id(word_id)

    if answer_data:
        return jsonify(answer_data)

    return jsonify({"error": "Word not found."}), 404

@app.route('/api/delete_word/<int:word_id>', methods=['DELETE'])
def delete_word_route(word_id):
    """API endpoint to delete a saved word."""
    result = delete_word_by_id(word_id)
    return jsonify(result)

@app.route('/api/get_topics', methods=['GET'])
def get_topics_route():
    """API endpoint to get the list of all topics."""
    topics = get_all_topics()
    return jsonify(topics)

@app.route('/api/add_topic', methods=['POST'])
def add_topic_route():
    """API endpoint to add a new topic."""
    data = request.get_json()
    topic_name = data.get('topic_name')
    if not topic_name:
        return jsonify({"error": "Topic name cannot be empty."}), 400
    new_topic = add_new_topic(topic_name.strip())
    if new_topic:
        return jsonify(new_topic), 201
    return jsonify({"error": "Failed to create topic."}), 500

@app.route('/api/delete_topic/<int:topic_id>', methods=['DELETE'])
def delete_topic_route(topic_id):
    """API endpoint to delete a topic."""
    result = delete_topic_by_id(topic_id)
    return jsonify(result)