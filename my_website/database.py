# my_website/database.py
# PHIÊN BẢN HOÀN CHỈNH - Dùng cho PostgreSQL trên Vercel

import os
import psycopg2
import psycopg2.extras  # Cần thiết để sử dụng DictCursor
import json


# --- HÀM KẾT NỐI DATABASE ---
def get_db_connection():
    """
    Tạo và trả về một kết nối đến database PostgreSQL.
    Đọc chuỗi kết nối từ biến môi trường DATABASE_URL.
    """
    try:
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
        return conn
    except Exception as e:
        print(f"DATABASE CONNECTION ERROR: {e}")
        return None


# --- HÀM KHỞI TẠO CẤU TRÚC (SCHEMA) ---
def initialize_schema(cursor):
    """
    Chạy các lệnh CREATE TABLE IF NOT EXISTS để đảm bảo các bảng tồn tại.
    Hàm này sẽ được gọi bên trong các hàm khác khi cần.
    """
    print("INFO: Running schema check (CREATE TABLE IF NOT EXISTS)...")
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS words (
                id SERIAL PRIMARY KEY,
                word TEXT NOT NULL UNIQUE,
                vietnamese_meaning TEXT,
                english_definition TEXT,
                example TEXT,
                image_url TEXT,
                priority_score INTEGER DEFAULT 1,
                pronunciation_ipa TEXT,
                synonyms_json JSONB,
                family_words_json JSONB
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS topics (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS word_topics (
                word_id INTEGER REFERENCES words(id) ON DELETE CASCADE,
                topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
                PRIMARY KEY (word_id, topic_id)
            );
        ''')

        # Thêm các chủ đề mặc định nếu bảng topics trống
        cursor.execute("SELECT COUNT(*) FROM topics;")
        if cursor.fetchone()[0] == 0:
            default_topics = [('Daily life',), ('Work',), ('Cooking',), ('Travel',), ('Technology',)]
            cursor.executemany("INSERT INTO topics (name) VALUES (%s);", default_topics)
            print("INFO: Default topics seeded.")

        print("INFO: Schema check complete.")
    except Exception as e:
        print(f"ERROR during schema initialization: {e}")
        # Ném lỗi ra ngoài để giao dịch bên ngoài có thể rollback
        raise e


# --- CÁC HÀM TƯƠNG TÁC VỚI DATABASE ---

# Gói logic khởi tạo và thực thi vào một hàm decorator để tránh lặp code (Nâng cao & Hiệu quả)
def db_transaction(func):
    def wrapper(*args, **kwargs):
        conn = get_db_connection()
        if not conn:
            # Trả về một giá trị mặc định phù hợp với kiểu trả về của hàm gốc
            # Ví dụ: None, [], hoặc một dict lỗi
            return {"status": "error", "message": "Database connection failed."} if 'save' in func.__name__ else None

        try:
            with conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    # Luôn chạy kiểm tra schema ở đầu mỗi giao dịch
                    initialize_schema(cur)
                    # Chạy hàm gốc (ví dụ: save_word_logic)
                    result = func(cur, *args, **kwargs)
                    return result
        except Exception as e:
            print(f"DATABASE EXCEPTION in {func.__name__}: {e}")
            import traceback
            traceback.print_exc()
            # Trả về giá trị mặc định/lỗi
            return {"status": "error", "message": "A database error occurred."} if 'save' in func.__name__ else None
        finally:
            if conn:
                conn.close()

    return wrapper


@db_transaction
def save_word(cur, word_data, topic_ids=None):
    # Logic của hàm save_word giờ nằm ở đây và nhận 'cur' làm tham số
    # ... (Code giống hệt phiên bản trước, chỉ thay 'cursor' bằng 'cur') ...
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
    cur.execute("SELECT id FROM words WHERE word = %s;", (word_to_save,))
    word_id = cur.fetchone()['id']
    if topic_ids is not None:
        cur.execute("DELETE FROM word_topics WHERE word_id = %s;", (word_id,))
        if topic_ids:
            topic_data = [(word_id, int(tid)) for tid in topic_ids]
            cur.executemany("INSERT INTO word_topics (word_id, topic_id) VALUES (%s, %s);", topic_data)
    return {"status": "success", "message": "Word saved!"} if was_newly_inserted else {"status": "updated",
                                                                                       "message": "Word topics updated."}


@db_transaction
def find_word_in_db(cur, word_to_find):
    cur.execute("SELECT * FROM words WHERE word = %s;", (word_to_find,))
    word_data_row = cur.fetchone()
    if word_data_row:
        word_dict = dict(word_data_row)
        word_dict['synonyms'] = word_dict.pop('synonyms_json', []) or []
        word_dict['family_words'] = word_dict.pop('family_words_json', []) or []
        return word_dict
    return None


# ... Bạn có thể áp dụng decorator @db_transaction cho các hàm khác để chúng cũng tự động khởi tạo schema ...
# Ví dụ:
@db_transaction
def get_all_topics(cur):
    query = "SELECT t.id, t.name, COUNT(wt.word_id) as word_count FROM topics t LEFT JOIN word_topics wt ON t.id = wt.topic_id GROUP BY t.id ORDER BY t.name ASC"
    cur.execute(query)
    return [dict(row) for row in cur.fetchall()]

# ... Và các hàm còn lại: get_word_for_exam, update_word_score, v.v...