# my_website/app.py
from flask import Flask, render_template, request, jsonify, send_from_directory
# Import các hàm cần thiết
from handle_request import get_dictionary_data, save_word_to_file, get_all_saved_words, delete_word_from_file

app = Flask(__name__)

# Route cho trang chủ
@app.route('/')
def index():
    return render_template('index.html')

# ROUTE MỚI: Để render trang history.html
@app.route('/history')
def history():
    return render_template('history.html')

# ROUTE MỚI: Endpoint để cung cấp dữ liệu JSON
@app.route('/get_saved_words')
def api_get_saved_words():
    return get_all_saved_words()

# Các endpoint cũ
@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    return get_dictionary_data(data.get('message'))

@app.route('/save_word', methods=['POST'])
def save_word():
    return save_word_to_file(request.get_json())

@app.route('/delete_word', methods=['POST'])
def delete_word():
    data = request.get_json()
    word_to_delete = data.get('word')
    if not word_to_delete:
        return jsonify({"error": "Thiếu từ cần xóa."}), 400
    return delete_word_from_file(word_to_delete)

if __name__ == '__main__':
    app.run(debug=True)