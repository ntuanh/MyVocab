# my_website/app.py
from flask import Flask, render_template, request
from handle_request import get_dictionary_data # Đổi tên hàm import

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message')
    # Gọi thẳng hàm mới, nó đã trả về định dạng response của Flask
    return get_dictionary_data(user_message)

if __name__ == '__main__':
    app.run(debug=True)