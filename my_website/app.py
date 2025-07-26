# my_website/app.py
# PHIÊN BẢN DEBUG - Tối giản để tìm lỗi

import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

# Import các hàm cần thiết. Chúng ta sẽ chỉ dùng get_db_connection trực tiếp.
from .database import get_db_connection

# --- FLASK APP SETUP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            static_folder=os.path.join(BASE_DIR, 'static'),
            template_folder=os.path.join(BASE_DIR, 'templates'))

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a_super_secret_key_for_local_dev")


# --- ROUTE CHÍNH - Tối giản ---
@app.route('/')
def index():
    return render_template('index.html')


# --- [DEBUG] ENDPOINT ĐỂ KHỞI TẠO DATABASE ---
# Endpoint này sẽ là công cụ duy nhất của chúng ta để tạo bảng.
@app.route('/api/setup_database')
def setup_database_route():
    print("--- [DEBUG] Received request for /api/setup_database ---")

    conn = get_db_connection()
    if not conn:
        print("[DEBUG] FAILED: Database connection returned None.")
        return "Database connection failed. Check DATABASE_URL environment variable and logs.", 500

    try:
        # Dùng 'with' để đảm bảo cursor và connection được đóng đúng cách
        with conn:
            with conn.cursor() as cur:
                print("[DEBUG] Connection successful. Creating tables...")

                # Chạy các lệnh CREATE TABLE IF NOT EXISTS
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS words (
                        id SERIAL PRIMARY KEY, word TEXT NOT NULL UNIQUE, vietnamese_meaning TEXT,
                        english_definition TEXT, example TEXT, image_url TEXT,
                        priority_score INTEGER DEFAULT 1, pronunciation_ipa TEXT,
                        synonyms_json JSONB, family_words_json JSONB
                    );
                ''')
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS topics (
                        id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE
                    );
                ''')
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS word_topics (
                        word_id INTEGER REFERENCES words(id) ON DELETE CASCADE,
                        topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
                        PRIMARY KEY (word_id, topic_id)
                    );
                ''')
                print("[DEBUG] CREATE TABLE commands executed.")

                # Thêm chủ đề mặc định
                cur.execute("SELECT COUNT(*) FROM topics;")
                if cur.fetchone()[0] == 0:
                    print("[DEBUG] Topics table is empty. Seeding default topics...")
                    default_topics = [('Daily life',), ('Work',), ('Cooking',), ('Travel',), ('Technology',)]
                    cur.executemany("INSERT INTO topics (name) VALUES (%s);", default_topics)
                    print("[DEBUG] Default topics seeded.")

                # conn.commit() được tự động gọi khi thoát khỏi khối 'with conn:'

        print("[DEBUG] SUCCESS: Database setup complete.")
        return "Database setup successful! Tables have been created.", 200

    except Exception as e:
        print(f"[DEBUG] FAILED: An exception occurred during database setup: {e}")
        import traceback
        traceback.print_exc()
        return f"An error occurred: {e}", 500

# --- CÁC ROUTE CÒN LẠI (TẠM THỜI VÔ HIỆU HÓA HOẶC GIỮ NGUYÊN) ---
# Chúng ta sẽ không đụng đến chúng cho đến khi database được thiết lập thành công.
# ... (Bạn có thể giữ nguyên các route còn lại của mình ở đây) ...
# ...
# @app.route('/api/verify_password', methods=['POST'])
# def verify_password():
#     #...
#
# @app.route('/data')
# def data_page():
#     #...
#
# @app.route('/lookup', methods=['POST'])
# def lookup_route():
#     #...