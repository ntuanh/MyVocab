# File: my_website/database.py
# PHIÊN BẢN CUỐI CÙNG - Hoàn thiện 100% cho Vercel Postgres.

import os
import psycopg2
from psycopg2.extras import RealDictCursor  # Giúp trả về kết quả dạng dictionary
import random

# Vercel & Neon sẽ tự động cung cấp biến môi trường này sau khi bạn liên kết DB
DATABASE_URL = os.environ.get('POSTGRES_URL')


def get_db_connection():
    """Tạo và trả về một kết nối đến Vercel Postgres."""
    try:
        if not DATABASE_URL:
            raise ValueError("Biến môi trường POSTGRES_URL chưa được thiết lập.")
        # Dùng RealDictCursor để kết quả trả về giống dictionary (dễ xử lý)
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"Lỗi kết nối database: {e}")
        return None


# --- CÁC HÀM XỬ LÝ DATABASE (ĐÃ CẬP NHẬT CHO POSTGRES) ---
# LƯU Ý QUAN TRỌNG: Postgres dùng %s làm placeholder, không phải ? như SQLite

def init_db():
    """Khởi tạo các bảng trong database Postgres nếu chúng chưa tồn tại."""
    conn = get_db_connection()
    if not conn: return "Database connection failed"

    try:
        with conn.cursor() as cur:
            # SERIAL PRIMARY KEY trong Postgres tự động tăng
            cur.execute('''
                CREATE TABLE IF NOT EXISTS words (
                    id SERIAL PRIMARY KEY,
                    word TEXT NOT NULL UNIQUE,
                    vietnamese_meaning TEXT,
                    english_definition TEXT,
                    example TEXT,
                    image_url TEXT,
                    priority_score INTEGER DEFAULT 1
                );
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS topics (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE
                );
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS word_topics (
                    word_id INTEGER REFERENCES words(id) ON DELETE CASCADE,
                    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
                    PRIMARY KEY (word_id, topic_id)
                );
            ''')

            cur.execute("SELECT COUNT(*) FROM topics;")
            # psycopg2 trả về dict, truy cập bằng key 'count'
            if cur.fetchone()['count'] == 0:
                default_topics = [('Daily life',), ('Work',), ('Cooking',), ('Travel',), ('Technology',)]
                # executemany dùng cho việc chèn nhiều dòng
                cur.executemany("INSERT INTO topics (name) VALUES (%s);", default_topics)

        conn.commit()  # Lưu tất cả thay đổi
        return "Database initialized successfully."
    except Exception as e:
        conn.rollback()  # Hoàn tác nếu có lỗi
        return f"Error initializing database: {e}"
    finally:
        if conn:
            conn.close()


def save_word(word_data, topic_ids=None):
    """Lưu từ mới hoặc cập nhật chủ đề cho từ đã có."""
    conn = get_db_connection()
    if not conn: return {"status": "error", "message": "DB connection failed"}

    word_to_save = word_data.get('word')
    if not word_to_save: return {"status": "error", "message": "Word data invalid"}

    try:
        with conn.cursor() as cur:
            # Dùng ON CONFLICT để xử lý trường hợp từ đã tồn tại (tương đương INSERT OR IGNORE)
            cur.execute('''
                INSERT INTO words (word, vietnamese_meaning, english_definition, example, image_url)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (word) DO NOTHING;
            ''', (
                word_to_save,
                word_data.get('vietnamese_meaning'),
                word_data.get('english_definition'),
                word_data.get('example'),
                word_data.get('image_url')
            ))

            # Lấy ID của từ (dù là mới thêm hay đã có)
            cur.execute("SELECT id FROM words WHERE word = %s;", (word_to_save,))
            word_id = cur.fetchone()['id']

            # Cập nhật chủ đề
            if topic_ids is not None:
                cur.execute("DELETE FROM word_topics WHERE word_id = %s;", (word_id,))
                if topic_ids:
                    valid_topic_ids = [(word_id, int(tid)) for tid in topic_ids]
                    cur.executemany("INSERT INTO word_topics (word_id, topic_id) VALUES (%s, %s);", valid_topic_ids)

        conn.commit()
        return {"status": "success", "message": "Word saved/updated successfully."}
    except Exception as e:
        conn.rollback()
        print(f"ERROR in save_word: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        if conn:
            conn.close()


def find_word_in_db(word_to_find):
    conn = get_db_connection()
    if not conn: return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM words WHERE word = %s;", (word_to_find,))
            return cur.fetchone()
    except Exception as e:
        print(f"ERROR in find_word_in_db: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_all_topics():
    conn = get_db_connection()
    if not conn: return []
    try:
        with conn.cursor() as cur:
            query = """
                SELECT t.id, t.name, COUNT(wt.word_id) as word_count
                FROM topics t
                LEFT JOIN word_topics wt ON t.id = wt.topic_id
                GROUP BY t.id ORDER BY t.name ASC;
            """
            cur.execute(query)
            return cur.fetchall()
    except Exception as e:
        print(f"ERROR in get_all_topics: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_word_for_exam(topic_ids=None):
    conn = get_db_connection()
    if not conn: return None
    try:
        with conn.cursor() as cur:
            query = "SELECT w.id, w.word, w.image_url, w.priority_score FROM words w"
            params = []
            if topic_ids:
                query += " JOIN word_topics wt ON w.id = wt.word_id WHERE wt.topic_id = ANY(%s)"
                params.append(list(map(int, topic_ids)))

            cur.execute(query, params)
            all_words = cur.fetchall()
            if not all_words: return None

            weighted_list = [word for word in all_words for _ in range(word['priority_score'])]
            if not weighted_list: return None

            return random.choice(weighted_list)
    except Exception as e:
        print(f"ERROR in get_word_for_exam: {e}")
        return None
    finally:
        if conn:
            conn.close()


def update_word_score(word_id, is_correct):
    conn = get_db_connection()
    if not conn: return {"status": "error", "message": "DB connection failed"}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT priority_score FROM words WHERE id = %s;", (word_id,))
            result = cur.fetchone()
            if not result: return {"status": "error", "message": "Word not found."}

            current_score = result['priority_score']
            new_score = max(1, current_score - 1) if is_correct else current_score + 1
            cur.execute("UPDATE words SET priority_score = %s WHERE id = %s;", (new_score, word_id))
            conn.commit()
            return {"status": "success", "new_score": new_score}
    except Exception as e:
        conn.rollback()
        print(f"ERROR in update_word_score: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        if conn:
            conn.close()


def get_correct_answer_by_id(word_id):
    conn = get_db_connection()
    if not conn: return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT vietnamese_meaning FROM words WHERE id = %s;", (word_id,))
            result = cur.fetchone()
            return result['vietnamese_meaning'] if result else None
    finally:
        if conn:
            conn.close()


def get_all_saved_words():
    conn = get_db_connection()
    if not conn: return []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM words ORDER BY priority_score DESC, word ASC;")
            return cur.fetchall()
    except Exception as e:
        print(f"ERROR in get_all_saved_words: {e}")
        return []
    finally:
        if conn:
            conn.close()


def delete_word_by_id(word_id):
    conn = get_db_connection()
    if not conn: return {"status": "error", "message": "DB connection failed"}
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM words WHERE id = %s;", (word_id,))
            conn.commit()
            return {"status": "success"} if cur.rowcount > 0 else {"status": "error", "message": "Word not found"}
    except Exception as e:
        conn.rollback()
        print(f"ERROR in delete_word_by_id: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        if conn:
            conn.close()


def delete_topic_by_id(topic_id):
    conn = get_db_connection()
    if not conn: return {"status": "error", "message": "DB connection failed"}
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM topics WHERE id = %s;", (topic_id,))
            conn.commit()
            return {"status": "success"} if cur.rowcount > 0 else {"status": "error", "message": "Topic not found"}
    except Exception as e:
        conn.rollback()
        print(f"ERROR in delete_topic_by_id: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        if conn:
            conn.close()


def add_new_topic(topic_name):
    conn = get_db_connection()
    if not conn: return None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO topics (name) VALUES (%s) ON CONFLICT (name) DO NOTHING;", (topic_name,))
            cur.execute("SELECT * FROM topics WHERE name = %s;", (topic_name,))
            conn.commit()
            return cur.fetchone()
    except Exception as e:
        conn.rollback()
        print(f"ERROR in add_new_topic: {e}")
        return None
    finally:
        if conn:
            conn.close()