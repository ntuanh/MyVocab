# my_website/handle_request.py

import os
import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path

# --- PHẦN CẤU HÌNH - CHỈ CHẠY 1 LẦN KHI FILE ĐƯỢC IMPORT ---

# 1. Chỉ định đường dẫn tới file .env một cách chính xác
env_path = Path(__file__).parent.parent / ".env"

# 2. Chỉ cần gọi load_dotenv MỘT LẦN với đường dẫn đã chỉ định
load_dotenv(dotenv_path=env_path)

# 3. Cấu hình API key và khởi tạo model
# Đặt khối này ở cấp độ module để nó chỉ chạy một lần.
model = None  # Khởi tạo model là None trước
try:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Ném ra lỗi để dừng chương trình nếu không có key, giúp debug dễ hơn
        raise ValueError("CRITICAL: Not found GEMINI_API_KEY. Check file .env and path pls!.")

    genai.configure(api_key=api_key)

    # Sử dụng model mới nhất, nhanh và hiệu quả cho chatbot
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    print("INFO: Gemini model loaded successfully.")

except (ValueError, AttributeError) as e:
    # In ra lỗi nghiêm trọng nếu không thể cấu hình
    print(e)


# --- PHẦN HÀM XỬ LÝ ---

def get_gemini_response(user_message, chat_history):
    """
    Gửi tin nhắn của người dùng và lịch sử chat đến Gemini để nhận phản hồi.
    """
    # Kiểm tra xem model đã được khởi tạo thành công chưa
    if model is None:
        print("ERROR: Model is not initialized due to configuration error.")
        return "Xin lỗi, hệ thống đang gặp lỗi cấu hình. Vui lòng liên hệ quản trị viên.", chat_history

    try:
        # Bắt đầu phiên chat với lịch sử đã có
        chat_session = model.start_chat(history=chat_history)

        # Gửi tin nhắn mới
        response = chat_session.send_message(user_message)

        # Trả về câu trả lời của bot và lịch sử mới nhất
        return response.text, chat_session.history

    except Exception as e:
        print(f"Đã xảy ra lỗi khi gọi Gemini API: {e}")
        return "Xin lỗi, tôi đang gặp sự cố. Vui lòng thử lại sau.", chat_history