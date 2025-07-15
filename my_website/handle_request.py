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


# --- PHẦN HÀM XỬ LÝ (PHIÊN BẢN SỬA LỖI MỚI NHẤT) ---

def get_gemini_response(user_message, chat_history):
    """
    Nhận một từ tiếng Anh từ người dùng và trả về 5 thông tin chi tiết về từ đó.
    """
    if model is None:
        print("ERROR: Model is not initialized.")
        return "Xin lỗi, hệ thống đang gặp lỗi cấu hình.", []

    # --- BƯỚC 1: PYTHON KIỂM TRA TÍNH HỢP LỆ CỦA INPUT ---
    # Kiểm tra xem user_message có phải là một từ đơn và chỉ chứa chữ cái không
    if ' ' in user_message.strip() or not user_message.isalpha():
        # Nếu có dấu cách hoặc có ký tự không phải chữ cái, trả về lỗi ngay lập tức
        return "Vui lòng chỉ nhập một từ tiếng Anh hợp lệ (không chứa số, ký tự đặc biệt hoặc dấu cách).", []

    # --- BƯỚC 2: TẠO PROMPT ĐƠN GIẢN HÓA CHO AI ---
    # Chúng ta đã xóa câu lệnh điều kiện "If the input is invalid..."
    system_prompt = f"""
    You are an expert English-Vietnamese dictionary assistant.
    A user has provided the English word: "{user_message}".
    Your only task is to provide 5 specific pieces of information about this word.
    Format the output using Markdown, with each point on a new line.

    1.  **Nghĩa Tiếng Việt:** (Provide common Vietnamese meaning(s)).
    2.  **English Definition:** (Provide a clear English-English definition).
    3.  **Example Sentence:** (Provide a practical example sentence in English).
    4.  **Word Family:** (List related words like nouns, verbs, adjectives).
    5.  **Pronunciation (IPA):** (Provide the IPA transcription).

    Do not add any other text, conversation, or introduction.
    """

    try:
        response = model.generate_content(system_prompt)

        # ... (Phần code xử lý response an toàn giữ nguyên như cũ) ...
        print("DEBUG: Full Gemini Response:", response)

        if response.candidates and response.candidates[0].content.parts:
            bot_text = response.text
        else:
            bot_text = "Xin lỗi, không thể xử lý từ này. Vui lòng thử một từ khác."
            print("WARN: Response was blocked or empty. Feedback:", response.prompt_feedback)

        return bot_text, []

    except Exception as e:
        print(f"Đã xảy ra lỗi nghiêm trọng khi gọi Gemini API: {e}")
        return "Xin lỗi, tôi đang gặp sự cố hệ thống.", []