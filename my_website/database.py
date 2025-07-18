# File: my_website/database.py
# Phiên bản hoàn chỉnh, đã sửa lỗi và tối ưu cho Vercel.

import sqlite3
import random
import os

# --- PHẦN CẤU HÌNH DATABASE ---

# Kiểm tra xem có đang chạy trên môi trường Vercel không bằng cách đọc biến môi trường 'VERCEL'.
IS_VERCEL = os.environ.get('VERCEL')

# Nếu đang chạy trên Vercel, đường dẫn database sẽ trỏ đến thư mục /tmp (được phép ghi).
# Nếu không (chạy ở máy local), nó sẽ tạo file myvocab.db ngay tại thư mục dự án.
if IS_VERCEL:
    DB_PATH = '/tmp/myvocab.db'
else:
    DB_PATH = 'myvocab.db'

def get_db_connection():
    """
    Hàm trung tâm để tạo và trả về một kết nối đến database.
    Luôn sử dụng đường dẫn DB_PATH đã được xác định ở trên.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Giúp trả về kết quả dạng dictionary
        conn.execute("PRAGMA foreign_keys = ON") # Bật khóa ngoại cho mọi kết nối
        return conn
    except sqlite3.Error as e:
        print(f"Lỗi kết nối database tại {DB_PATH}: {e}")
        return None

# --- CÁC HÀM XỬ LÝ DATABASE ---

def init_db():
    """Khởi tạo database và các bảng nếu chúng chưa tồn tại."""
    conn = get_db_connection()
    if not conn: return # Dừng lại nếu không kết nối được DB

    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL UNIQUE,
                vietnamese_meaning TEXT,
                english_definition TEXT,
                example TEXT,
                image_url TEXT,
                priority_score INTEGER DEFAULT 1
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS word_topics (
                word_id INTEGER,
                topic_id INTEGER,
                FOREIGN KEY (word_id) REFERENCES words (id) ON DELETE CASCADE,
                FOREIGN KEY (topic_id) REFERENCES topics (id) ON DELETE CASCADE,
                PRIMARY KEY (word_id, topic_id)
            )
        ''')

        # Thêm các chủ đề mặc định nếu bảng topics trống
        cursor.execute("SELECT COUNT(*) FROM topics")
        if cursor.fetchone()['COUNT(*)'] == 0:
            default_topics = ['Daily life', 'Work', 'Cooking', 'Travel', 'Technology']
            cursor.executemany("INSERT OR IGNORE INTO topics (name) VALUES (?)", [(topic,) for topic in default_topics])

        conn.commit()
        print(f"INFO: Database initialized successfully at: {DB_PATH}")
    except sqlite3.Error as e:
        print(f"Lỗi trong init_db: {e}")
    finally:
        if conn:
            conn.close()

def add_new_topic(topic_name):
    """Thêm một chủ đề mới và trả về thông tin của nó."""
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO topics (name) VALUES (?)", (topic_name,))
        conn.commit()
        cursor.execute("SELECT id, name FROM topics WHERE name = ?", (topic_name,))
        topic = cursor.fetchone()
        return dict(topic) if topic else None
    except sqlite3.Error as e:
        print(f"Lỗi DB khi thêm chủ đề: {e}")
        return None
    finally:
        if conn:
            conn.close()

def find_word_in_db(word_to_find):
    """Tìm một từ trong database."""
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM words WHERE word = ?", (word_to_find,))
        word_data = cursor.fetchone()
        return dict(word_data) if word_data else None
    finally:
        if conn:
            conn.close()

def save_word(word_data, topic_ids=None):
    """Lưu từ mới hoặc cập nhật chủ đề cho từ đã có."""
    if not word_data or not word_data.get('word'):
        return {"status": "error", "message": "Word data is invalid."}

    conn = get_db_connection()
    if not conn:
        return {"status": "error", "message": "Database connection failed."}

    try:
        cursor = conn.cursor()
        word_to_save = word_data['word']

        # Thêm hoặc bỏ qua từ mới
        cursor.execute('''
            INSERT OR IGNORE INTO words (word, vietnamese_meaning, english_definition, example, image_url)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            word_to_save,
            word_data.get('vietnamese_meaning'),
            word_data.get('english_definition'),
            word_data.get('example'),
            word_data.get('image_url')
        ))
        was_newly_inserted = cursor.rowcount > 0

        # Lấy word_id (dù là mới thêm hay đã có sẵn)
        cursor.execute("SELECT id FROM words WHERE word = ?", (word_to_save,))
        result = cursor.fetchone()
        if not result:
            raise sqlite3.Error("Failed to retrieve word ID after insert/ignore.")
        word_id = result['id']

        # Cập nhật liên kết chủ đề
        if topic_ids is not None:
            cursor.execute("DELETE FROM word_topics WHERE word_id = ?", (word_id,))
            if topic_ids:
                # Chuyển đổi topic_ids sang int để đảm bảo
                valid_topic_ids = [(word_id, int(tid)) for tid in topic_ids]
                cursor.executemany("INSERT INTO word_topics (word_id, topic_id) VALUES (?, ?)", valid_topic_ids)

        conn.commit()
        return {"status": "success", "message": "Word saved!"} if was_newly_inserted else {"status": "updated", "message": "Word topics updated."}
    except sqlite3.Error as e:
        print(f"DATABASE EXCEPTION in save_word: {e}")
        conn.rollback() # Hoàn tác các thay đổi nếu có lỗi
        return {"status": "error", "message": "Failed to save word due to a database error."}
    finally:
        if conn:
            conn.close()

def get_all_topics():
    """Lấy tất cả các chủ đề cùng với số lượng từ trong mỗi chủ đề."""
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor()
        query = """
            SELECT t.id, t.name, COUNT(wt.word_id) as word_count
            FROM topics t
            LEFT JOIN word_topics wt ON t.id = wt.topic_id
            GROUP BY t.id ORDER BY t.name ASC
        """
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Lỗi DB khi lấy chủ đề: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_word_for_exam(topic_ids=None):
    """Lấy một từ ngẫu nhiên để kiểm tra, có trọng số theo điểm ưu tiên."""
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        query = "SELECT w.id, w.word, w.image_url, w.priority_score FROM words w"
        params = []
        if topic_ids:
            placeholders = ','.join(['?'] * len(topic_ids))
            query += f" JOIN word_topics wt ON w.id = wt.word_id WHERE wt.topic_id IN ({placeholders})"
            params.extend(topic_ids)

        cursor.execute(query, params)
        all_words = cursor.fetchall()

        if not all_words: return None
        # Tạo danh sách có trọng số
        weighted_list = [word for word in all_words for _ in range(word['priority_score'])]
        if not weighted_list: return None

        chosen_word = random.choice(weighted_list)
        return dict(chosen_word)
    except sqlite3.Error as e:
        print(f"Lỗi DB khi lấy từ kiểm tra: {e}")
        return None
    finally:
        if conn:
            conn.close()

def update_word_score(word_id, is_correct):
    """Cập nhật điểm ưu tiên cho từ: giảm nếu đúng, tăng nếu sai."""
    conn = get_db_connection()
    if not conn: return {"status": "error", "message": "DB connection failed"}
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT priority_score FROM words WHERE id = ?", (word_id,))
        result = cursor.fetchone()
        if not result: return {"status": "error", "message": "Word not found."}

        current_score = result['priority_score']
        new_score = max(1, current_score - 1) if is_correct else current_score + 2 # Tăng 2 điểm nếu sai
        cursor.execute("UPDATE words SET priority_score = ? WHERE id = ?", (new_score, word_id))
        conn.commit()
        return {"status": "success", "new_score": new_score}
    except sqlite3.Error as e:
        print(f"Lỗi DB khi cập nhật điểm: {e}")
        return {"status": "error", "message": "DB update failed"}
    finally:
        if conn:
            conn.close()

def get_correct_answer_by_id(word_id):
    """Lấy nghĩa tiếng Việt của một từ theo ID."""
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT vietnamese_meaning FROM words WHERE id = ?", (word_id,))
        result = cursor.fetchone()
        return result['vietnamese_meaning'] if result else None
    finally:
        if conn:
            conn.close()

def get_all_saved_words():
    """Lấy tất cả các từ đã lưu, sắp xếp theo điểm ưu tiên rồi đến alphabet."""
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM words ORDER BY priority_score DESC, word ASC")
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Lỗi DB khi lấy tất cả các từ: {e}")
        return []
    finally:
        if conn:
            conn.close()

def delete_word_by_id(word_id):
    """Xóa một từ theo ID."""
    conn = get_db_connection()
    if not conn: return {"status": "error", "message": "DB connection failed"}
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM words WHERE id = ?", (word_id,))
        conn.commit()
        return {"status": "success"} if cursor.rowcount > 0 else {"status": "error", "message": "Word not found"}
    except sqlite3.Error as e:
        print(f"Lỗi DB khi xóa từ: {e}")
        return {"status": "error", "message": "Delete failed"}
    finally:
        if conn:
            conn.close()

def delete_topic_by_id(topic_id):
    """Xóa một chủ đề theo ID. Liên kết trong word_topics sẽ tự động bị xóa nhờ khóa ngoại."""
    conn = get_db_connection()
    if not conn: return {"status": "error", "message": "DB connection failed"}
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
        conn.commit()
        return {"status": "success"} if cursor.rowcount > 0 else {"status": "error", "message": "Topic not found"}
    except sqlite3.Error as e:
        print(f"Lỗi DB khi xóa chủ đề: {e}")
        return {"status": "error", "message": "Delete failed"}
    finally:
        if conn:
            conn.close()