# my_website/database.py
import sqlite3
import random

DATABASE_FILE = 'myvocab.db'


def init_db():
    """Khởi tạo database và bảng nếu chưa tồn tại."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    # Tạo bảng words
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
    conn.commit()
    conn.close()
    print("INFO: Database initialized successfully.")


# Sửa lại hàm save_word để không lưu lại từ đã có
def save_word(word_data):
    """Lưu một từ mới. Nếu từ đã tồn tại, không làm gì cả."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    try:
        # Dùng INSERT OR IGNORE.
        # Nếu từ (do có ràng buộc UNIQUE) đã tồn tại, lệnh này sẽ được bỏ qua.
        cursor.execute('''
            INSERT OR IGNORE INTO words (word, vietnamese_meaning, english_definition, example, image_url)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            word_data.get('word'),
            word_data.get('vietnamese_meaning'),
            word_data.get('english_definition'),
            word_data.get('example'),
            word_data.get('image_url')
        ))
        conn.commit()
        # rowcount > 0 có nghĩa là một hàng mới đã được chèn vào
        if cursor.rowcount > 0:
            print(f"INFO: Word '{word_data.get('word')}' saved.")
            return {"status": "success", "message": "Word saved!"}
        else:
            print(f"INFO: Word '{word_data.get('word')}' already exists.")
            return {"status": "exists", "message": "Word already saved."}
    except sqlite3.Error as e:
        print(f"Lỗi DB khi lưu từ: {e}")
        return {"status": "error", "message": "Failed to save word."}
    finally:
        conn.close()


def get_word_for_exam():
    """Lấy một từ để kiểm tra, ưu tiên từ có điểm cao."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    try:
        # Lấy tất cả các từ và điểm của chúng
        cursor.execute("SELECT id, word, image_url, priority_score FROM words")
        all_words = cursor.fetchall()

        if not all_words:
            return None

        # Tạo một danh sách "xổ số" dựa trên điểm ưu tiên
        # Từ có điểm 3 sẽ xuất hiện 3 lần trong danh sách này
        weighted_list = []
        for word_id, word, image_url, score in all_words:
            weighted_list.extend([(word_id, word, image_url)] * score)

        # Chọn ngẫu nhiên một từ từ danh sách đã được "làm nặng"
        chosen_word_id, chosen_word, chosen_image_url = random.choice(weighted_list)

        return {
            "id": chosen_word_id,
            "word": chosen_word,
            "image_url": chosen_image_url
        }
    except Exception as e:
        print(f"Lỗi DB khi lấy từ kiểm tra: {e}")
        return None
    finally:
        conn.close()


def update_word_score(word_id, is_correct):
    """Cập nhật điểm ưu tiên cho một từ."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    try:
        # Lấy điểm hiện tại
        cursor.execute("SELECT priority_score FROM words WHERE id = ?", (word_id,))
        current_score = cursor.fetchone()[0]

        if is_correct:
            # Nếu đúng, trừ 1 điểm, nhưng không thấp hơn 1
            new_score = max(1, current_score - 1)
        else:
            # Nếu sai, cộng 1 điểm
            new_score = current_score + 1

        cursor.execute("UPDATE words SET priority_score = ? WHERE id = ?", (new_score, word_id))
        conn.commit()

        # Kiểm tra câu trả lời
        cursor.execute("SELECT vietnamese_meaning FROM words WHERE id = ?", (word_id,))
        correct_answer = cursor.fetchone()[0]

        return {"status": "success", "new_score": new_score, "correct_answer": correct_answer}
    except Exception as e:
        print(f"Lỗi DB khi cập nhật điểm: {e}")
        return {"status": "error", "message": "Failed to update score."}
    finally:
        conn.close()
def get_all_saved_words():
    """Lấy tất cả các từ đã được lưu, sắp xếp theo điểm ưu tiên giảm dần."""
    conn = sqlite3.connect(DATABASE_FILE)
    # Trả về kết quả dưới dạng dictionary để dễ dùng
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM words ORDER BY priority_score DESC")
        words = [dict(row) for row in cursor.fetchall()]
        return words
    except Exception as e:
        print(f"Lỗi DB khi lấy tất cả từ: {e}")
        return []
    finally:
        conn.close()

# my_website/database.py
# ... (thêm vào cuối file) ...

def delete_word_by_id(word_id):
    """Xóa một từ khỏi database dựa trên ID của nó."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM words WHERE id = ?", (word_id,))
        conn.commit()
        # rowcount sẽ trả về số dòng đã bị ảnh hưởng (xóa)
        if cursor.rowcount > 0:
            return {"status": "success", "message": "Word deleted successfully."}
        else:
            return {"status": "error", "message": "Word not found."}
    except Exception as e:
        print(f"Lỗi DB khi xóa từ: {e}")
        return {"status": "error", "message": "Failed to delete word."}
    finally:
        conn.close()

# HÀM MỚI ĐỂ TÌM TỪ
def find_word_in_db(word_to_find):
    """Tìm một từ trong database và trả về dữ liệu của nó nếu có."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row # Để có thể truy cập cột bằng tên
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM words WHERE word = ?", (word_to_find,))
        word_data = cursor.fetchone()
        if word_data:
            return dict(word_data) # Chuyển đổi thành dictionary
        return None
    except Exception as e:
        print(f"Lỗi DB khi tìm từ: {e}")
        return None
    finally:
        conn.close()
