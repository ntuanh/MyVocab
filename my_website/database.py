import os
import psycopg2
from psycopg2.extras import RealDictCursor
import random
import json

DATABASE_URL = os.environ.get('POSTGRES_URL')
_db_initialized = False

def ensure_db_initialized():
    """
    Checks if the database has been initialized in this session.
    If not, it calls init_db(). This prevents redundant checks.
    """
    global _db_initialized
    if not _db_initialized:
        print("INFO: First request received. Ensuring database schema exists...")
        init_db()
        _db_initialized = True

def get_db_connection():
    """Open and return a connection to my Vercel Postgres database."""
    try:
        if not DATABASE_URL:
            raise ValueError("POSTGRES_URL environment variable isn't set. Did you link your DB?")
        # RealDictCursor means I get dict-like results instead of tuples. So much nicer!
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None


def init_db():
    """Creates all tables if they do not exist."""
    conn = get_db_connection()
    if not conn: return
    try:
        with conn.cursor() as cur:
            # ... (toàn bộ các lệnh CREATE TABLE IF NOT EXISTS của bạn giữ nguyên) ...
            cur.execute(''' CREATE TABLE IF NOT EXISTS words (...) ''')
            cur.execute(''' CREATE TABLE IF NOT EXISTS topics (...) ''')
            cur.execute(''' CREATE TABLE IF NOT EXISTS word_topics (...) ''')

            cur.execute("SELECT COUNT(*) FROM topics;")
            if cur.fetchone()[0] == 0:
                default_topics = [('Daily life',), ('Work',), ('Cooking',), ('Travel',), ('Technology',)]
                cur.executemany("INSERT INTO topics (name) VALUES (%s);", default_topics)
        conn.commit()
        print("INFO: Database schema check/initialization complete.")
    except Exception as e:
        conn.rollback()
        print(f"ERROR during init_db: {e}")
    finally:
        if conn: conn.close()

def save_word(word_data, topic_ids=None):
    ensure_db_initialized()
    if not word_data or not word_data.get('word'):
        print("ERROR in save_word: Invalid or missing word data.")
        return {"status": "error", "message": "Word data is invalid."}

    # 2. Get database connection
    conn = get_db_connection()
    if not conn:
        print("ERROR in save_word: Database connection failed.")
        return {"status": "error", "message": "Database connection failed."}

    try:
        # 3. Use 'with conn.cursor()' for automatic resource management
        with conn.cursor() as cur:
            word_to_save = word_data.get('word')

            # 4. Prepare the SQL INSERT statement with PostgreSQL syntax
            # 'ON CONFLICT (word) DO NOTHING' is the PostgreSQL equivalent of 'INSERT OR IGNORE'.
            # It attempts to insert a new row, but if a row with the same 'word' already exists, it does nothing.
            insert_sql = """
                INSERT INTO words (
                    word, vietnamese_meaning, english_definition, example, image_url, 
                    pronunciation_ipa, synonyms_json, family_words_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (word) DO NOTHING;
            """

            # 5. Prepare the data tuple to be passed to the query
            # psycopg2 automatically handles Python lists/dicts when the column type is JSONB.
            # No need to manually call json.dumps().
            data_tuple = (
                word_to_save,
                word_data.get('vietnamese_meaning'),
                word_data.get('english_definition'),
                word_data.get('example'),
                word_data.get('image_url'),
                word_data.get('pronunciation_ipa'),
                word_data.get('synonyms', []),  # Pass the list directly
                word_data.get('family_words', [])  # Pass the list directly
            )

            # 6. Execute the insert command
            cur.execute(insert_sql, data_tuple)

            # Check if a new row was actually inserted
            was_newly_inserted = cur.rowcount > 0

            # 7. Get the ID of the word (whether it was new or already existed)
            cur.execute("SELECT id FROM words WHERE word = %s;", (word_to_save,))
            result = cur.fetchone()
            if not result:
                raise Exception("Could not retrieve word ID after insertion.")
            word_id = result[0]

            # 8. Update topic associations if topic_ids are provided
            if topic_ids is not None:
                # First, remove all existing associations for this word
                cur.execute("DELETE FROM word_topics WHERE word_id = %s;", (word_id,))

                # Then, insert the new associations if any were selected
                if topic_ids:
                    # executemany is efficient for inserting multiple rows
                    topic_data_to_insert = [(word_id, int(tid)) for tid in topic_ids]
                    cur.executemany("INSERT INTO word_topics (word_id, topic_id) VALUES (%s, %s);",
                                    topic_data_to_insert)

        # 9. Commit the transaction to save all changes
        conn.commit()

        print(f"INFO: Successfully saved/updated word '{word_to_save}'.")
        return {"status": "success", "message": "Word saved!"} if was_newly_inserted else {"status": "updated",
                                                                                           "message": "Word topics updated."}

    except Exception as e:
        # 10. If any error occurs, roll back all changes from this transaction
        if conn:
            conn.rollback()
        print(f"DATABASE EXCEPTION in save_word: {e}")
        import traceback
        traceback.print_exc()  # Print full error for better debugging
        return {"status": "error", "message": "Failed to save word due to a database error."}
    finally:
        # 11. Always close the connection
        if conn:
            conn.close()

def find_word_in_db(word_to_find):
    ensure_db_initialized()
    conn = get_db_connection()
    if not conn:
        print(f"ERROR: Database connection failed while trying to find '{word_to_find}'.")
        return None
    word_dict = None

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM words WHERE word = %s;", (word_to_find,))

            word_data_row = cur.fetchone()

            if word_data_row:
                column_names = [desc[0] for desc in cur.description]
                word_dict = dict(zip(column_names, word_data_row))
                word_dict['synonyms'] = word_dict.pop('synonyms_json', []) or []
                word_dict['family_words'] = word_dict.pop('family_words_json', []) or []
                print(f"INFO: Found '{word_to_find}' in PostgreSQL cache.")
    except Exception as e:
        print(f"ERROR: An exception occurred in find_word_in_db for '{word_to_find}': {e}")
        return None
    finally:
        if conn:
            conn.close()

    return word_dict


def get_all_topics():
    ensure_db_initialized()
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
    ensure_db_initialized()
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

            # This is a little trick: words with higher priority_score show up more often in quizzes
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
            # If you get it right, the word shows up less. If you get it wrong, it shows up more!
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