# File: my_website/app.py
# This is my main Flask app for MyVocab. I've tweaked and optimized it for Vercel deployment.

import os
from flask import Flask, render_template, request, jsonify

# --- IMPORTS ---
# Grabbing all the helper functions I need from my other modules in this package.
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
# Setting up the Flask app, making sure it knows where to find my static files and templates.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            static_folder=os.path.join(BASE_DIR, 'static'),
            template_folder=os.path.join(BASE_DIR, 'templates'))


# --- PAGE ROUTES (RENDER HTML) ---

@app.route('/')
def index():
    """This is the main dictionary page – where the magic starts."""
    return render_template('index.html')


@app.route('/exam')
def exam_page():
    """Quiz time! This page lets you test your vocab knowledge."""
    topics = get_all_topics()
    return render_template('exam.html', topics=topics)


@app.route('/data')
def data_page():
    """Here's where you can see all the words you've saved so far."""
    saved_words = get_all_saved_words()
    return render_template('data.html', words=saved_words)


@app.route('/manage_topics')
def manage_topics_page():
    """Manage your custom topics here. Add, remove, or just browse them."""
    topics = get_all_topics()
    return render_template('manage_topics.html', topics=topics)


# --- API ENDPOINTS (RETURN JSON) ---

@app.route('/lookup', methods=['POST'])
def lookup_route():
    """POST here to look up a word. Returns all the juicy details."""
    data = request.get_json()
    user_message = data.get('message')
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    return get_dictionary_data(user_message)


@app.route('/save_word', methods=['POST'])
def save_word_route():
    """Save a word (and its topics) to your personal collection."""
    data = request.get_json()
    word_data = data.get('word_data')
    topic_ids = data.get('topic_ids', [])

    if not word_data or not isinstance(word_data, dict):
        return jsonify({"error": "Word data is missing or invalid."}), 400

    result = save_word(word_data, topic_ids)
    return jsonify(result)


@app.route('/get_exam_word', methods=['POST'])
def get_exam_word_route():
    """Grab a random word for the quiz, filtered by topic if you want."""
    data = request.get_json()
    topic_ids = data.get('topic_ids', None)
    word = get_word_for_exam(topic_ids)
    if word:
        return jsonify(word)
    return jsonify({"error": "No words found for the selected topics."}), 404


@app.route('/submit_answer', methods=['POST'])
def submit_answer_route():
    """Update the score for a word after you answer a quiz question."""
    data = request.get_json()
    word_id = data.get('id')
    is_correct = data.get('is_correct')
    result = update_word_score(word_id, is_correct)
    return jsonify(result)


@app.route('/get_answer/<int:word_id>', methods=['GET'])
def get_answer_route(word_id):
    """Get the correct answer for a word by its ID (for quiz feedback)."""
    correct_answer = get_correct_answer_by_id(word_id)
    if correct_answer is not None:
        return jsonify({"correct_answer": correct_answer})
    return jsonify({"error": "Word not found in database."}), 404


@app.route('/delete_word/<int:word_id>', methods=['DELETE'])
def delete_word_route(word_id):
    """Delete a word from your saved list."""
    result = delete_word_by_id(word_id)
    return jsonify(result)


@app.route('/get_topics', methods=['GET'])
def get_topics_route():
    """Get a list of all your topics (for organizing words)."""
    topics = get_all_topics()
    return jsonify(topics)


@app.route('/add_topic', methods=['POST'])
def add_topic_route():
    """Add a brand new topic to help organize your words."""
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
    """Remove a topic by its ID. (Don't worry, your words are safe!)"""
    result = delete_topic_by_id(topic_id)
    return jsonify(result)


