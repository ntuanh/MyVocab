import os
import psycopg2
import psycopg2.extras  # Required for DictCursor
import json
import random


# --- DATABASE CONNECTION ---
def get_db_connection():
    """Establishes and returns a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
        return conn
    except Exception as e:
        print(f"DATABASE CONNECTION ERROR: {e}")
        return None


# --- SCHEMA INITIALIZATION HELPER ---
def initialize_schema(cursor):
    """Runs CREATE TABLE IF NOT EXISTS commands to ensure the schema is present."""
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS words (
                id SERIAL PRIMARY KEY, word TEXT NOT NULL UNIQUE, vietnamese_meaning TEXT,
                english_definition TEXT, example TEXT, image_url TEXT,
                priority_score INTEGER DEFAULT 5, pronunciation_ipa TEXT,
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

        cursor.execute("SELECT COUNT(*) FROM topics;")
        if cursor.fetchone()[0] == 0:
            default_topics = [('Daily life',), ('Work',), ('Cooking',), ('Travel',), ('Technology',)]
            cursor.executemany("INSERT INTO topics (name) VALUES (%s);", default_topics)
    except Exception as e:
        print(f"ERROR during schema initialization: {e}")
        raise e


# --- TRANSACTION DECORATOR (ADVANCED) ---
# This decorator handles connection, cursor, schema initialization, commit/rollback, and closing.
def db_transaction(func):
    def wrapper(*args, **kwargs):
        conn = get_db_connection()
        if not conn:
            # Return a default value appropriate for the wrapped function's return type
            return None if 'get' in func.__name__ else {"status": "error", "message": "Database connection failed."}

        try:
            with conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    initialize_schema(cur)  # Always ensure schema exists at the start of a transaction
                    result = func(cur, *args, **kwargs)  # Execute the original function logic
                    return result
        except Exception as e:
            print(f"DATABASE EXCEPTION in {func.__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None if 'get' in func.__name__ else {"status": "error", "message": "A database error occurred."}
        finally:
            if conn:
                conn.close()

    return wrapper


# --- DATABASE INTERACTION FUNCTIONS (wrapped with the decorator) ---

@db_transaction
def save_word(cur, word_data, topic_ids=None):
    if not word_data or not word_data.get('word'):
        return {"status": "error", "message": "Word data is invalid."}

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


@db_transaction
def get_all_topics(cur):
    query = "SELECT t.id, t.name, COUNT(wt.word_id) as word_count FROM topics t LEFT JOIN word_topics wt ON t.id = wt.topic_id GROUP BY t.id ORDER BY t.name ASC"
    cur.execute(query)
    return [dict(row) for row in cur.fetchall()]


@db_transaction
def add_new_topic(cur, topic_name):
    cur.execute("INSERT INTO topics (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id, name;",
                (topic_name,))
    new_topic = cur.fetchone()
    # If topic already existed, fetch it
    if not new_topic:
        cur.execute("SELECT id, name FROM topics WHERE name = %s;", (topic_name,))
        new_topic = cur.fetchone()
    return dict(new_topic) if new_topic else None


@db_transaction
def get_word_for_exam(cur, topic_ids=None):
    query = "SELECT w.id, w.word, w.image_url, w.priority_score FROM words w"
    params = []
    if topic_ids:
        # Use tuple for params to avoid SQL injection issues with f-strings
        query += " JOIN word_topics wt ON w.id = wt.word_id WHERE wt.topic_id IN %s"
        params.append(tuple(topic_ids))

    cur.execute(query, params if params else None)
    all_words = cur.fetchall()
    if not all_words: return None

    weighted_list = [word for word in all_words for _ in range(word['priority_score'])]
    if not weighted_list: return None

    chosen_word = random.choice(weighted_list)
    return dict(chosen_word)


@db_transaction
def update_word_score(cur, word_id, is_correct):
    cur.execute("SELECT priority_score FROM words WHERE id = %s;", (word_id,))
    result = cur.fetchone()
    if not result: return {"status": "error", "message": "Word not found."}

    current_score = result['priority_score']
    new_score = max(1, current_score - 1) if is_correct else current_score + 1
    cur.execute("UPDATE words SET priority_score = %s WHERE id = %s;", (new_score, word_id))
    return {"status": "success", "new_score": new_score}


@db_transaction
def get_correct_answer_by_id(cur, word_id):
    """
    Fetches both the full Vietnamese meaning and the keywords for a given word ID.
    Returns a dictionary, or None if the word is not found.
    """
    cur.execute("SELECT vietnamese_meaning, vietnamese_keywords FROM words WHERE id = %s;", (word_id,))
    result = cur.fetchone()
    if result:
        return {
            "correct_answer": result['vietnamese_meaning'],
            "keywords": result['vietnamese_keywords']
        }
    return None

@db_transaction
def get_all_saved_words(cur):
    cur.execute("SELECT * FROM words ORDER BY priority_score DESC, word ASC;")
    words = cur.fetchall()
    # Need to process JSON fields for each row
    results = []
    for row in words:
        word_dict = dict(row)
        word_dict['synonyms'] = word_dict.pop('synonyms_json', []) or []
        word_dict['family_words'] = word_dict.pop('family_words_json', []) or []
        results.append(word_dict)
    return results


@db_transaction
def delete_word_by_id(cur, word_id):
    cur.execute("DELETE FROM words WHERE id = %s;", (word_id,))
    return {"status": "success"} if cur.rowcount > 0 else {"status": "error", "message": "Word not found"}


@db_transaction
def delete_topic_by_id(cur, topic_id):
    cur.execute("DELETE FROM topics WHERE id = %s;", (topic_id,))
    return {"status": "success"} if cur.rowcount > 0 else {"status": "error", "message": "Topic not found"}