# my_website/database.py
# PHIÊN BẢN CUỐI CÙNG - Cực kỳ mạnh mẽ

import os
import psycopg2
import psycopg2.extras  # Dùng cho DictCursor
import json


# --- KẾT NỐI DATABASE ---
def get_db_connection():
    try:
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
        return conn
    except Exception as e:
        print(f"DATABASE CONNECTION ERROR: {e}")
        return None


# --- HÀM KHỞI TẠO SCHEMA (QUAN TRỌNG) ---
def initialize_schema(cursor):
    """
    Hàm này chạy các lệnh CREATE TABLE. Nó được gọi bên trong các hàm khác.
    """
    print("INFO: Running schema initialization (CREATE TABLE IF NOT EXISTS)...")
    # Sử dụng DictCursor để dễ dàng làm việc với kết quả
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS words (
            id SERIAL PRIMARY KEY, word TEXT NOT NULL UNIQUE, vietnamese_meaning TEXT,
            english_definition TEXT, example TEXT, image_url TEXT,
            priority_score INTEGER DEFAULT 1, pronunciation_ipa TEXT,
            synonyms_json JSONB, family_words_json JSONB
        );
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS topics (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE
        );
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS word_topics (
            word_id INTEGER REFERENCES words(id) ON DELETE CASCADE,
            topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
            PRIMARY KEY (word_id, topic_id)
        );
    ''')
    # Thêm chủ đề mặc định
    cursor.execute("SELECT COUNT(*) FROM topics;")
    if cursor.fetchone()[0] == 0:
        default_topics = [('Daily life',), ('Work',), ('Cooking',), ('Travel',), ('Technology',)]
        cursor.executemany("INSERT INTO topics (name) VALUES (%s);", default_topics)
    print("INFO: Schema initialization complete.")


# --- HÀM LƯU TỪ (ĐÃ SỬA LẠI HOÀN TOÀN) ---
def save_word(word_data, topic_ids=None):
    if not word_data or not word_data.get('word'):
        return {"status": "error", "message": "Word data is invalid."}

    conn = get_db_connection()
    if not conn: return {"status": "error", "message": "Database connection failed."}

    try:
        # Sử dụng DictCursor để làm việc với dictionary
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # 1. GỌI HÀM KHỞI TẠO NGAY TỪ ĐẦU, BÊN TRONG CÙNG MỘT GIAO DỊCH
            initialize_schema(cur)

            # 2. Chuẩn bị và thực thi lệnh INSERT
            word_to_save = word_data.get('word')
            insert_sql = """
                INSERT INTO words (word, vietnamese_meaning, english_definition, example, image_url, 
                                   pronunciation_ipa, synonyms_json, family_words_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (word) DO NOTHING;
            """
            data_tuple = (
                word_to_save, word_data.get('vietnamese_meaning'), word_data.get('english_definition'),
                word_data.get('example'), word_data.get('image_url'), word_data.get('pronunciation_ipa'),
                json.dumps(word_data.get('synonyms', [])), json.dumps(word_data.get('family_words', []))
            )
            cur.execute(insert_sql, data_tuple)
            was_newly_inserted = cur.rowcount > 0

            # 3. Lấy word_id và cập nhật topics
            cur.execute("SELECT id FROM words WHERE word = %s;", (word_to_save,))
            word_id = cur.fetchone()['id']
            if topic_ids is not None:
                cur.execute("DELETE FROM word_topics WHERE word_id = %s;", (word_id,))
                if topic_ids:
                    topic_data = [(word_id, int(tid)) for tid in topic_ids]
                    cur.executemany("INSERT INTO word_topics (word_id, topic_id) VALUES (%s, %s);", topic_data)

            # 4. Commit toàn bộ giao dịch (cả CREATE TABLE và INSERT)
            conn.commit()
            return {"status": "success", "message": "Word saved!"} if was_newly_inserted else {"status": "updated",
                                                                                               "message": "Word topics updated."}

    except Exception as e:
        if conn: conn.rollback()
        print(f"DATABASE EXCEPTION in save_word: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": "A database error occurred."}
    finally:
        if conn: conn.close()


# --- CÁC HÀM KHÁC CŨNG CẦN ĐƯỢC BẢO VỆ ---
# (Ví dụ cho get_all_topics, bạn có thể làm tương tự cho các hàm khác)
def get_all_topics():
    conn = get_db_connection()
    if not conn: return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Luôn đảm bảo bảng tồn tại trước khi truy vấn
            initialize_schema(cur)
            query = "SELECT t.id, t.name, COUNT(wt.word_id) as word_count FROM topics t LEFT JOIN word_topics wt ON t.id = wt.topic_id GROUP BY t.id ORDER BY t.name ASC"
            cur.execute(query)
            # Không cần commit vì đây là lệnh SELECT
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"DATABASE EXCEPTION in get_all_topics: {e}")
        return []
    finally:
        if conn: conn.close()

# ... Bạn có thể áp dụng logic tương tự (gọi initialize_schema) cho các hàm khác nếu cần ...
# init_db, find_word_in_db, get_word_for_exam, ...