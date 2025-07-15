# my_website/app.py

from flask import Flask, render_template, request, jsonify
# Import hàm xử lý từ file handle_request.py
from handle_request import get_gemini_response

# Khởi tạo ứng dụng Flask
app = Flask(__name__)


# Đối với ứng dụng từ điển, mỗi yêu cầu là độc lập,
# vì vậy chúng ta không cần quản lý lịch sử trò chuyện phức tạp.
# Biến chat_histories đã bị loại bỏ.

@app.route('/')
def index():
    """
    Hàm này render trang chủ (giao diện chat).
    Nó sẽ trả về file 'index.html' từ thư mục 'templates'.
    """
    return render_template('index.html')


@app.route('/chat', methods=['POST'])
def chat():
    """
    Đây là endpoint chính để xử lý yêu cầu chat từ người dùng.
    Nó nhận tin nhắn, gửi đến Gemini và trả về phản hồi.
    """
    # 1. Lấy dữ liệu JSON từ yêu cầu của client (JavaScript gửi lên)
    data = request.get_json()
    user_message = data.get('message')

    # 2. Kiểm tra xem người dùng có gửi tin nhắn rỗng không
    if not user_message:
        return jsonify({'error': 'Message cannot be empty'}), 400

    # 3. Gọi hàm get_gemini_response để xử lý
    #    - Truyền vào tin nhắn của người dùng và một lịch sử rỗng [].
    #    - Dùng dấu gạch dưới `_` để bỏ qua giá trị thứ hai (lịch sử) mà hàm trả về,
    #      vì chúng ta không cần nó trong ứng dụng này.
    bot_response_text, _ = get_gemini_response(user_message, [])

    # 4. Trả kết quả (câu trả lời của bot) về cho giao diện dưới dạng JSON
    return jsonify({'response': bot_response_text})


# Đoạn này đảm bảo server chỉ chạy khi bạn thực thi trực tiếp file này
if __name__ == '__main__':
    # Chạy server ở chế độ debug để tự động tải lại khi có thay đổi
    app.run(debug=True)