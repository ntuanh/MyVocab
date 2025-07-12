# my_website/app.py

from flask import Flask, render_template, request, jsonify

# Import hàm xử lý từ file handle_request.py
from handle_request import get_gemini_response

app = Flask(__name__)

# Dữ liệu chat sẽ được lưu trữ tạm thời trên server.
# Trong ứng dụng thực tế, bạn có thể dùng session hoặc database.
chat_histories = {}

@app.route('/')
def index():
    # Hiển thị trang chat chính
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    # Lấy dữ liệu từ request của client (JavaScript gửi lên)
    data = request.get_json()
    user_id = data.get('user_id', 'default_user') # Lấy user_id để quản lý nhiều cuộc chat
    user_message = data.get('message')

    if not user_message:
        return jsonify({'error': 'Message cannot be empty'}), 400

    # Lấy lịch sử chat của user này, nếu chưa có thì tạo mới
    current_history = chat_histories.get(user_id, [])

    # Gọi hàm xử lý để lấy câu trả lời từ Gemini
    bot_response_text, updated_history = get_gemini_response(user_message, current_history)

    # Cập nhật lại lịch sử chat cho user
    chat_histories[user_id] = updated_history

    # Trả về câu trả lời cho client dưới dạng JSON
    return jsonify({'response': bot_response_text})

if __name__ == '__main__':
    app.run(debug=True)