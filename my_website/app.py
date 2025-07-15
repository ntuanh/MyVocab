# my_website/app.py

from flask import Flask, render_template, request, jsonify
# Đảm bảo bạn đang import đúng các hàm
from handle_request import get_dictionary_data, save_word_to_file

app = Flask(__name__)

@app.route('/')
def index():
    """
    Hàm này rất quan trọng. Nó nói cho Flask biết phải làm gì
    khi người dùng truy cập vào trang chủ http://127.0.0.1:5000.
    Nó sẽ tìm và hiển thị file 'index.html'.
    """
    return render_template('index.html')
# --------------------------------------

@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint để tra từ"""
    data = request.get_json()
    user_message = data.get('message')
    return get_dictionary_data(user_message)

@app.route('/save_word', methods=['POST'])
def save_word():
    """Endpoint để lưu từ"""
    word_data = request.get_json()
    return save_word_to_file(word_data)

if __name__ == '__main__':
    app.run(debug=True)