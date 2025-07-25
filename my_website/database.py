import os
import psycopg2
from psycopg2.extras import RealDictCursor  # This makes query results act like Python dicts, which is way easier to work with
import random
import json

# Vercel & Neon will automatically provide this environment variable after you link your DB
DATABASE_URL = os.environ.get('POSTGRES_URL')


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


# --- DATABASE FUNCTIONS (UPDATED FOR POSTGRES) ---
# IMPORTANT: Postgres uses %s as a placeholder, not ? like SQLite

def init_db():
    """
    Creates all necessary tables in the PostgreSQL database if they don't exist yet.
    This version includes columns for caching IPA, synonyms, and family words.
    """
    conn = get_db_connection()
    if not conn:
        print("CRITICAL: Database connection failed during initialization.")
        return "Database connection failed"

    try:
        # 'with conn.cursor()' handles closing the cursor automatically
        with conn.cursor() as cur:

            # --- UPDATED 'words' TABLE SCHEMA ---
            # 'SERIAL PRIMARY KEY' is the PostgreSQL equivalent of AUTOINCREMENT.
            # 'TEXT' is a suitable type for storing strings of any length.
            # 'JSONB' is the recommended type for storing JSON data in PostgreSQL.
            # It's more efficient for storage and can be indexed.
            cur.execute('''
                CREATE TABLE IF NOT EXISTS words (
                    id SERIAL PRIMARY KEY,
                    word TEXT NOT NULL UNIQUE,
                    vietnamese_meaning TEXT,
                    english_definition TEXT,
                    example TEXT,
                    image_url TEXT,
                    priority_score INTEGER DEFAULT 1,

                    -- NEW COLUMNS ADDED --
                    pronunciation_ipa TEXT,
                    synonyms_json JSONB,      -- Use JSONB for lists of synonyms
                    family_words_json JSONB   -- Use JSONB for lists of family words
                );
            ''')

            # --- 'topics' TABLE ---
            cur.execute('''
                CREATE TABLE IF NOT EXISTS topics (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE
                );
            ''')

            # --- 'word_topics' JUNCTION TABLE ---
            # This table links words and topics (many-to-many relationship).
            cur.execute('''
                CREATE TABLE IF NOT EXISTS word_topics (
                    word_id INTEGER REFERENCES words(id) ON DELETE CASCADE,
                    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
                    PRIMARY KEY (word_id, topic_id)
                );
            ''')

            # --- SEED DEFAULT TOPICS ---
            # Check if the topics table is empty before inserting default values.
            cur.execute("SELECT COUNT(*) FROM topics;")
            # The cursor for psycopg2 (Postgres driver) returns a tuple
            if cur.fetchone()[0] == 0:
                default_topics = [('Daily life',), ('Work',), ('Cooking',), ('Travel',), ('Technology',)]
                # 'executemany' is the efficient way to insert multiple rows.
                # '%s' is the placeholder for PostgreSQL queries with psycopg2.
                cur.executemany("INSERT INTO topics (name) VALUES (%s);", default_topics)

        conn.commit()  # Persist all the changes to the database
        print("INFO: Database initialized successfully with the new schema.")
        return "Database initialized successfully."
    except Exception as e:
        conn.rollback()  # If any error occurs, undo all changes in this transaction
        print(f"ERROR: Could not initialize database. Details: {e}")
        return f"Error initializing database: {e}"
    finally:
        if conn:
            conn.close()  # Always close the connection

def save_word(word_data, topic_ids=None):
    """Save a new word, or update its topics if it already exists."""
    conn = get_db_connection()
    if not conn: return {"status": "error", "message": "DB connection failed"}

    word_to_save = word_data.get('word')
    if not word_to_save: return {"status": "error", "message": "Word data invalid"}

    try:
        with conn.cursor() as cur:
            # ON CONFLICT is like INSERT OR IGNORE in SQLite. Super handy for avoiding duplicates!
            cur.execute('''
                INSERT INTO words (word, vietnamese_meaning, english_definition, example, image_url)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (word) DO NOTHING;
            ''', (
                word_to_save,
                word_data.get('vietnamese_meaning'),
                word_data.get('english_definition'),
                word_data.get('example'),
                word_data.get('image_url'),
                word_data.get('pronunciation_ipa'),
                json.dumps(word_data.get('synonyms', [])),
                json.dumps(word_data.get('family_words', []))
            ))

            # Grab the word's ID (works for both new and existing words)
            cur.execute("SELECT id FROM words WHERE word = %s;", (word_to_save,))
            word_id = cur.fetchone()['id']

            # Now update the topics for this word
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
    if not conn:
        print(f"ERROR: Database connection failed while trying to find '{word_to_find}'.")
        return None

    # This will hold the final dictionary result
    word_dict = None

    try:
        with conn.cursor() as cur:
            # Query to select all columns for the specific word
            cur.execute("SELECT * FROM words WHERE word = %s;", (word_to_find,))

            # Fetch one result
            word_data_row = cur.fetchone()

            if word_data_row:
                # Get column names from the cursor description
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