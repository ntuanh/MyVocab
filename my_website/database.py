# my_website/database.py
import sqlite3
import random

DATABASE_FILE = 'myvocab.db'


def init_db():
    """Khởi tạo database và các bảng nếu chưa tồn tại."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # SỬA LỖI: Cung cấp đầy đủ các cột cho bảng 'words'
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

    cursor.execute("SELECT COUNT(*) FROM topics")
    if cursor.fetchone()[0] == 0:
        default_topics = ['Daily life', 'Work', 'Cooking', 'Travel', 'Technology']
        for topic in default_topics:
            cursor.execute("INSERT OR IGNORE INTO topics (name) VALUES (?)", (topic,))

    conn.commit()
    conn.close()
    print("INFO: Database with topics initialized successfully.")
def add_new_topic(topic_name):
    """Thêm một chủ đề mới vào database nếu nó chưa tồn tại."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    try:
        # Dùng INSERT OR IGNORE để không báo lỗi nếu tên chủ đề đã có
        cursor.execute("INSERT OR IGNORE INTO topics (name) VALUES (?)", (topic_name,))
        conn.commit()

        # Lấy lại topic vừa được thêm (hoặc đã tồn tại) để trả về ID
        cursor.execute("SELECT id, name FROM topics WHERE name = ?", (topic_name,))
        new_topic = cursor.fetchone()
        conn.row_factory = sqlite3.Row
        cursor.execute("SELECT id, name FROM topics WHERE name = ?", (topic_name,))

        return dict(cursor.fetchone())

    except sqlite3.Error as e:
        print(f"Lỗi DB khi thêm chủ đề: {e}")
        return None
    finally:
        conn.close()


def find_word_in_db(word_to_find):
    """Tìm một từ trong database và trả về dữ liệu của nó nếu có."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM words WHERE word = ?", (word_to_find,))
        word_data = cursor.fetchone()
        if word_data:
            return dict(word_data)
        return None
    finally:
        conn.close()


def save_word(word_data, topic_ids=None):
    """Lưu một từ mới hoặc cập nhật chủ đề cho từ đã có."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    word_to_save = word_data.get('word')

    print(f"\n--- Inside database.save_word ---")
    print(f"Word to save: {word_to_save}")
    print(f"Received topic_ids: {topic_ids}")

    if not word_to_save:
        print("ERROR in DB: word_to_save is None. Returning error.")
        return {"status": "error", "message": "Word data is invalid."}

    try:
        cursor.execute("PRAGMA foreign_keys = ON")

        # --- SỬA LỖI CÚ PHÁP SQL Ở ĐÂY ---
        cursor.execute('''
            INSERT OR IGNORE INTO words (word, vietnamese_meaning, english_definition, example, image_url, priority_score)
            VALUES (?, ?, ?, ?, ?, 1)
        ''', (
            word_to_save,
            word_data.get('vietnamese_meaning'),
            word_data.get('english_definition'),
            word_data.get('example'),
            word_data.get('image_url')
        ))

        was_newly_inserted = cursor.rowcount > 0

        cursor.execute("SELECT id FROM words WHERE word = ?", (word_to_save,))
        word_id = cursor.fetchone()[0]
        print(f"Found/Inserted word with ID: {word_id}")

        if topic_ids is not None:
            print(f"Processing topics for word ID {word_id} with topic IDs: {topic_ids}")
            cursor.execute("DELETE FROM word_topics WHERE word_id = ?", (word_id,))
            print(f"Deleted old topics for word ID {word_id}")
            if topic_ids:
                for topic_id in topic_ids:
                    cursor.execute("INSERT INTO word_topics (word_id, topic_id) VALUES (?, ?)",
                                   (word_id, int(topic_id)))
                    print(f"Linked word ID {word_id} with topic ID {topic_id}")
            else:
                # Logic gán chủ đề mặc định nếu không có topic nào được chọn
                print("No topic IDs provided, linking to default 'Daily life'.")
                cursor.execute("SELECT id FROM topics WHERE name = ?", ('Daily life',))
                default_topic = cursor.fetchone()
                if default_topic:
                    cursor.execute("INSERT INTO word_topics (word_id, topic_id) VALUES (?, ?)",
                                   (word_id, default_topic[0]))
                    print(f"Linked word ID {word_id} with default topic ID {default_topic[0]}")

        conn.commit()
        print("Transaction committed.")

        if was_newly_inserted:
            return {"status": "success", "message": "Word saved!"}
        else:
            return {"status": "updated", "message": "Word topics updated."}

    except Exception as e:
        print(f"DATABASE EXCEPTION in save_word: {e}")
        return {"status": "error", "message": "Failed to save word due to a database error."}
    finally:
        conn.close()

def get_all_topics():
    """
    Lấy tất cả các chủ đề từ DB và đếm số lượng từ trong mỗi chủ đề.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        # Câu lệnh SQL để JOIN 3 bảng và đếm
        # LEFT JOIN đảm bảo các chủ đề không có từ nào vẫn được hiển thị (với count = 0)
        query = """
            SELECT 
                t.id, 
                t.name, 
                COUNT(wt.word_id) as word_count
            FROM 
                topics t
            LEFT JOIN 
                word_topics wt ON t.id = wt.topic_id
            GROUP BY 
                t.id
            ORDER BY 
                t.name ASC
        """
        cursor.execute(query)
        # Chuyển kết quả thành danh sách các dictionary
        topics = [dict(row) for row in cursor.fetchall()]
        return topics
    except Exception as e:
        print(f"Lỗi DB khi lấy chủ đề và số lượng từ: {e}")
        return []
    finally:
        conn.close()


def get_word_for_exam(topic_ids=None):
    """Lấy một từ để kiểm tra, có thể lọc theo chủ đề."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    try:
        query = "SELECT DISTINCT w.id, w.word, w.image_url, w.priority_score FROM words w"
        params = []

        if topic_ids:
            placeholders = ','.join(['?'] * len(topic_ids))
            query += f" JOIN word_topics wt ON w.id = wt.word_id WHERE wt.topic_id IN ({placeholders})"
            params.extend(topic_ids)

        cursor.execute(query, params)
        all_words = cursor.fetchall()

        if not all_words: return None

        weighted_list = [item for item in all_words for _ in range(item[3])]  # item[3] là priority_score

        if not weighted_list: return None

        chosen_word_data = random.choice(weighted_list)
        return {
            "id": chosen_word_data[0],
            "word": chosen_word_data[1],
            "image_url": chosen_word_data[2]
        }
    finally:
        conn.close()


def update_word_score(word_id, is_correct):
    """Cập nhật điểm ưu tiên cho một từ."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT priority_score FROM words WHERE id = ?", (word_id,))
        result = cursor.fetchone()
        if not result: return {"status": "error", "message": "Word not found."}

        current_score = result[0]
        new_score = max(1, current_score - 1) if is_correct else current_score + 1

        cursor.execute("UPDATE words SET priority_score = ? WHERE id = ?", (new_score, word_id))
        conn.commit()
        return {"status": "success", "new_score": new_score}
    finally:
        conn.close()


def get_correct_answer_by_id(word_id):
    """Lấy nghĩa tiếng Việt của một từ dựa trên ID."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT vietnamese_meaning FROM words WHERE id = ?", (word_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        conn.close()


def get_all_saved_words():
    """Lấy tất cả các từ đã được lưu để hiển thị."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM words ORDER BY priority_score DESC, word ASC")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def delete_word_by_id(word_id):
    """Xóa một từ khỏi database dựa trên ID của nó."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM words WHERE id = ?", (word_id,))
        conn.commit()
        return {"status": "success"} if cursor.rowcount > 0 else {"status": "error"}
    finally:
        conn.close()

def delete_topic_by_id(topic_id):
    """Xóa một chủ đề và tất cả các liên kết của nó với các từ."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    try:
        # Bật khóa ngoại để lệnh ON DELETE CASCADE hoạt động
        cursor.execute("PRAGMA foreign_keys = ON")
        # Khi xóa một topic, tất cả các bản ghi trong word_topics có topic_id này sẽ bị xóa theo
        cursor.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
        conn.commit()
        return {"status": "success"} if cursor.rowcount > 0 else {"status": "error", "message": "Topic not found."}
    except Exception as e:
        print(f"Lỗi DB khi xóa chủ đề: {e}")
        return {"status": "error", "message": "Failed to delete topic."}
    finally:
        conn.close()