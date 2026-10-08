import copy
import functools
import os
import re
from datetime import timedelta

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
                synonyms_json JSONB, family_words_json JSONB,
                vietnamese_keywords TEXT
            );
        ''')
        # Migration for databases created before vietnamese_keywords existed.
        cursor.execute("ALTER TABLE words ADD COLUMN IF NOT EXISTS vietnamese_keywords TEXT;")
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
        # One row per marked answer: the skill it trains, what the sentence was
        # worth and the points it won or lost. word_id has no foreign key, so
        # deleting a word keeps the history of the weeks it was practised.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS practice_points (
                id SERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                skill TEXT NOT NULL DEFAULT 'vocab', word_id INTEGER, mode TEXT NOT NULL,
                verdict TEXT NOT NULL, worth INTEGER NOT NULL, points INTEGER NOT NULL
            );
        ''')
        # A skill's weekly goal from the week it was set (a Monday) until the next
        # change, so changing it never rewrites the goal of a past week.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS skill_goals (
                skill TEXT NOT NULL, week_start DATE NOT NULL, target INTEGER NOT NULL,
                PRIMARY KEY (skill, week_start)
            );
        ''')
        # One row per piece of writing: a diary entry or an IELTS task. The
        # teacher's marks (four criteria out of 20, so 80 in all) and feedback
        # are kept with it; status is 'waiting' when the AI could not mark it yet.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS writing_pieces (
                id SERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                kind TEXT NOT NULL, prompt_id TEXT NOT NULL, prompt TEXT NOT NULL,
                text TEXT NOT NULL, words INTEGER NOT NULL, revision_of INTEGER,
                status TEXT NOT NULL DEFAULT 'waiting', score INTEGER, band REAL,
                feedback JSONB, counted BOOLEAN NOT NULL DEFAULT FALSE,
                points INTEGER NOT NULL DEFAULT 0, scored_at TIMESTAMPTZ
            );
        ''')
        # One row per submitted reading part (an id from data/reading/). Only the
        # first submission of a part earns points; answers keeps what was written.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reading_attempts (
                id SERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                part_id INTEGER NOT NULL, correct INTEGER NOT NULL, total INTEGER NOT NULL,
                points INTEGER NOT NULL, counted BOOLEAN NOT NULL, answers JSONB
            );
        ''')
        # One row per score entered for a listening episode (an id from
        # data/bbc_6min.json). Only the first score of an episode earns points.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS listening_attempts (
                id SERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                episode_id TEXT NOT NULL, correct INTEGER NOT NULL, total INTEGER NOT NULL,
                points INTEGER NOT NULL, counted BOOLEAN NOT NULL
            );
        ''')
        # Files the learner adds to a listening episode: the BBC worksheet, the
        # transcript, the audio. Kept in the database so a backup carries them; they
        # are private (My Words access) and never go into the word pack or to GitHub.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS listening_docs (
                id SERIAL PRIMARY KEY, uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                episode_id TEXT NOT NULL, filename TEXT NOT NULL, content_type TEXT NOT NULL,
                size INTEGER NOT NULL, data BYTEA NOT NULL
            );
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS listening_docs_episode ON listening_docs (episode_id);")

        cursor.execute("SELECT COUNT(*) FROM topics;")
        if cursor.fetchone()[0] == 0:
            default_topics = [('Daily life',), ('Work',), ('Cooking',), ('Travel',), ('Technology',)]
            cursor.executemany("INSERT INTO topics (name) VALUES (%s);", default_topics)
    except Exception as e:
        print(f"ERROR during schema initialization: {e}")
        raise e


# --- KEYWORD HELPER ---
def derive_keywords(vietnamese_meaning):
    """Builds a comma-separated keyword list from a Vietnamese meaning.

    The exam marks a typed answer correct when it contains one of these keywords,
    so a long meaning like "kien cuong, deo dai truoc kho khan" stays answerable.
    """
    if not vietnamese_meaning:
        return None
    parts = [p.strip() for p in re.split(r'[,;/()]', vietnamese_meaning) if p.strip()]
    return ", ".join(parts) if parts else None


# --- TRANSACTION DECORATOR ---
# Handles connection, cursor, schema initialization, commit/rollback, and closing.
# `on_error` is what callers get when the database is unreachable or the query blows
# up; it must match the shape the caller expects (a list stays a list, never None).
def db_transaction(on_error):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            conn = get_db_connection()
            if not conn:
                return copy.deepcopy(on_error)

            try:
                with conn:
                    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                        initialize_schema(cur)  # Always ensure schema exists at the start of a transaction
                        return func(cur, *args, **kwargs)
            except Exception as e:
                print(f"DATABASE EXCEPTION in {func.__name__}: {e}")
                import traceback
                traceback.print_exc()
                return copy.deepcopy(on_error)
            finally:
                conn.close()

        return wrapper

    return decorator


# --- DATABASE INTERACTION FUNCTIONS (wrapped with the decorator) ---

@db_transaction(on_error={"status": "error", "message": "A database error occurred."})
def save_word(cur, word_data, topic_ids=None):
    if not word_data or not word_data.get('word'):
        return {"status": "error", "message": "Word data is invalid."}

    word_to_save = word_data.get('word')
    insert_sql = """
        INSERT INTO words (word, vietnamese_meaning, english_definition, example, image_url, 
                           pronunciation_ipa, synonyms_json, family_words_json, vietnamese_keywords)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (word) DO NOTHING;
    """
    data_tuple = (
        word_to_save, word_data.get('vietnamese_meaning'), word_data.get('english_definition'),
        word_data.get('example'), word_data.get('image_url'), word_data.get('pronunciation_ipa'),
        json.dumps(word_data.get('synonyms', [])), json.dumps(word_data.get('family_words', [])),
        word_data.get('vietnamese_keywords') or derive_keywords(word_data.get('vietnamese_meaning'))
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


@db_transaction(on_error=None)
def find_word_in_db(cur, word_to_find):
    cur.execute("SELECT * FROM words WHERE word = %s;", (word_to_find,))
    word_data_row = cur.fetchone()
    if word_data_row:
        word_dict = dict(word_data_row)
        word_dict['synonyms'] = word_dict.pop('synonyms_json', []) or []
        word_dict['family_words'] = word_dict.pop('family_words_json', []) or []
        return word_dict
    return None


@db_transaction(on_error=[])
def get_all_topics(cur):
    query = "SELECT t.id, t.name, COUNT(wt.word_id) as word_count FROM topics t LEFT JOIN word_topics wt ON t.id = wt.topic_id GROUP BY t.id ORDER BY t.name ASC"
    cur.execute(query)
    return [dict(row) for row in cur.fetchall()]


@db_transaction(on_error=None)
def add_new_topic(cur, topic_name):
    cur.execute("INSERT INTO topics (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id, name;",
                (topic_name,))
    new_topic = cur.fetchone()
    # If topic already existed, fetch it
    if not new_topic:
        cur.execute("SELECT id, name FROM topics WHERE name = %s;", (topic_name,))
        new_topic = cur.fetchone()
    return dict(new_topic) if new_topic else None


@db_transaction(on_error=None)
def get_word_for_exam(cur, topic_ids=None):
    query = "SELECT w.id, w.word, w.image_url, w.priority_score, w.vietnamese_meaning FROM words w"
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


@db_transaction(on_error=[])
def get_words_for_practice(cur, topic_ids=None, count=5):
    """Picks up to `count` different words, weighted by priority_score the same
    way the exam is, so the words you keep missing come up most often."""
    query = ("SELECT DISTINCT w.id, w.word, w.vietnamese_meaning, w.english_definition, "
             "w.example, w.priority_score FROM words w")
    params = []
    if topic_ids:
        query += " JOIN word_topics wt ON w.id = wt.word_id WHERE wt.topic_id IN %s"
        params.append(tuple(topic_ids))

    cur.execute(query, params if params else None)
    pool = [dict(row) for row in cur.fetchall()]

    chosen = []
    while pool and len(chosen) < count:
        weights = [max(1, row['priority_score'] or 1) for row in pool]
        chosen.append(pool.pop(random.choices(range(len(pool)), weights=weights)[0]))
    return chosen


@db_transaction(on_error={"status": "error", "message": "A database error occurred."})
def update_word_score(cur, word_id, is_correct):
    cur.execute("SELECT priority_score FROM words WHERE id = %s;", (word_id,))
    result = cur.fetchone()
    if not result: return {"status": "error", "message": "Word not found."}

    current_score = result['priority_score']
    new_score = max(1, current_score - 1) if is_correct else current_score + 1
    cur.execute("UPDATE words SET priority_score = %s WHERE id = %s;", (new_score, word_id))
    return {"status": "success", "new_score": new_score}


# Skills that keep a weekly points goal. Practice scores vocab; listening,
# reading and writing are meant to join with their own points and goals.
# One score per skill; each is a band on the Tracking page.
SKILLS = ("vocab", "listening", "reading", "writing")
DEFAULT_WEEKLY_TARGET = 300
PAST_WEEKS_SHOWN = 4


def _local_day(column):
    """SQL for the learner's calendar day of a UTC timestamp. Takes one parameter:
    the learner's clock in minutes ahead of UTC (420 in Vietnam)."""
    return f"({column} AT TIME ZONE 'UTC' + make_interval(mins => %s))::date"


def _today_and_monday(cur, offset_minutes):
    cur.execute(f"SELECT {_local_day('now()')} AS today;", (offset_minutes,))
    today = cur.fetchone()['today']
    return today, today - timedelta(days=today.weekday())


@db_transaction(on_error=None)
def record_practice_points(cur, skill, word_id, mode, verdict, worth, points):
    cur.execute("INSERT INTO practice_points (skill, word_id, mode, verdict, worth, points) "
                "VALUES (%s, %s, %s, %s, %s, %s);",
                (skill, word_id if isinstance(word_id, int) else None, mode, verdict, worth, points))
    return True


@db_transaction(on_error=None)
def set_weekly_targets(cur, targets, offset_minutes=0):
    """Weekly goals for one or more skills ({skill: points}), saved together. A
    new goal counts from this week on; past weeks keep the one they had."""
    _, monday = _today_and_monday(cur, offset_minutes)
    for skill, target in targets.items():
        cur.execute("INSERT INTO skill_goals (skill, week_start, target) VALUES (%s, %s, %s) "
                    "ON CONFLICT (skill, week_start) DO UPDATE SET target = EXCLUDED.target;",
                    (skill, monday, int(target)))
    return True


@db_transaction(on_error=None)
def get_progress(cur, skill, offset_minutes=0, past_weeks=PAST_WEEKS_SHOWN):
    """This week's points for a skill against its goal. The goal is cumulative:
    whatever a week falls short of is added to the next one, and keeps carrying
    until it is made up (points beyond a goal are not carried). Weeks run Monday
    to Sunday on the learner's clock, not the server's."""
    today, monday = _today_and_monday(cur, offset_minutes)

    # A skill gets the default goal the first time it is looked at.
    cur.execute("INSERT INTO skill_goals (skill, week_start, target) SELECT %s, %s, %s "
                "WHERE NOT EXISTS (SELECT 1 FROM skill_goals WHERE skill = %s);",
                (skill, monday, DEFAULT_WEEKLY_TARGET, skill))
    cur.execute("SELECT week_start, target FROM skill_goals WHERE skill = %s ORDER BY week_start;",
                (skill,))
    goals = [(r['week_start'], r['target']) for r in cur.fetchall()]

    # Tracking starts in the week of the skill's first points (and never before
    # its first goal), so a skill set up before it is practised, like a target
    # for listening before there is a listening practice, piles up no shortfall.
    cur.execute(f"SELECT MIN({_local_day('created_at')}) AS first_day FROM practice_points "
                "WHERE skill = %s;", (offset_minutes, skill))
    first_day = cur.fetchone()['first_day']
    started = first_day is not None
    start = max(goals[0][0], first_day - timedelta(days=first_day.weekday())) if started else monday

    def target_for(week):
        return next((t for since, t in reversed(goals) if since <= week), goals[0][1])

    # A day of margin on the UTC side; days before the start are dropped below.
    cur.execute(f"SELECT {_local_day('created_at')} AS day, SUM(points) AS points "
                "FROM practice_points WHERE skill = %s AND created_at >= %s::date - 1 "
                "GROUP BY day;", (offset_minutes, skill, start))
    per_day = {r['day']: int(r['points']) for r in cur.fetchall() if r['day'] >= start}
    per_week = {}
    for day, points in per_day.items():
        week = day - timedelta(days=day.weekday())
        per_week[week] = per_week.get(week, 0) + points

    past, carried, week = [], 0, start
    while week < monday:
        due = target_for(week) + carried
        points = per_week.get(week, 0)
        past.append({"week_start": week.isoformat(), "target": target_for(week),
                     "carried": carried, "points": points, "met": points >= due})
        carried = max(0, due - points)
        week += timedelta(weeks=1)

    target = target_for(monday)
    due = target + carried
    points = per_week.get(monday, 0)
    remaining = max(0, due - points)
    days_left = 7 - today.weekday()  # today included

    # Weeks in a row that met their goal; this week joins once it is met, and
    # until then it is still open rather than a break in the run.
    streak = 1 if points >= due else 0
    for done in reversed(past):
        if not done["met"]:
            break
        streak += 1

    return {
        "skill": skill,
        "started": started,
        "week_start": monday.isoformat(),
        "target": target,
        "carried": carried,
        "due": due,
        "points": points,
        "remaining": remaining,
        "days_left": days_left,
        "per_day_needed": -(-remaining // days_left),  # rounded up, whole points
        "days": [{"date": (monday + timedelta(days=n)).isoformat(),
                  "points": per_day.get(monday + timedelta(days=n), 0)} for n in range(7)],
        "streak": streak,
        "weeks_met": sum(1 for done in past if done["met"]),
        "weeks_done": len(past),
        "past_weeks": past[-past_weeks:][::-1] if past_weeks else [],  # newest first
    }


@db_transaction(on_error=None)
def save_listening_attempt(cur, episode_id, correct, total, worth, points):
    """Keeps one score for a listening episode. The first score of an episode
    adds its points to the listening skill; later ones are kept as practice
    only, so retaking a quiz you already know cannot farm points. The lock
    stops two quick saves from both counting as the first."""
    cur.execute("LOCK TABLE listening_attempts IN SHARE ROW EXCLUSIVE MODE;")
    cur.execute("SELECT EXISTS (SELECT 1 FROM listening_attempts WHERE episode_id = %s) AS done;",
                (episode_id,))
    counted = not cur.fetchone()['done']
    earned = points if counted else 0
    cur.execute("INSERT INTO listening_attempts (episode_id, correct, total, points, counted) "
                "VALUES (%s, %s, %s, %s, %s);", (episode_id, correct, total, earned, counted))
    if counted:
        cur.execute("INSERT INTO practice_points (skill, word_id, mode, verdict, worth, points) "
                    "VALUES ('listening', NULL, 'bbc_6min', 'exam', %s, %s);", (worth, earned))
    return {"counted": counted, "points": earned}


DOC_FIELDS = "id, episode_id, filename, content_type, size, uploaded_at"


@db_transaction(on_error=None)
def add_listening_doc(cur, episode_id, filename, content_type, data):
    """Saves a file for an episode; returns its details (without the bytes)."""
    cur.execute(f"INSERT INTO listening_docs (episode_id, filename, content_type, size, data) "
                f"VALUES (%s, %s, %s, %s, %s) RETURNING {DOC_FIELDS};",
                (episode_id, filename, content_type, len(data), psycopg2.Binary(data)))
    return dict(cur.fetchone())


@db_transaction(on_error=None)
def list_listening_docs(cur):
    """Every episode's files, oldest first, without their bytes."""
    cur.execute(f"SELECT {DOC_FIELDS} FROM listening_docs ORDER BY uploaded_at, id;")
    return [dict(row) for row in cur.fetchall()]


@db_transaction(on_error=None)
def get_listening_doc(cur, doc_id):
    """One file with its bytes, or None."""
    cur.execute(f"SELECT {DOC_FIELDS}, data FROM listening_docs WHERE id = %s;", (doc_id,))
    row = cur.fetchone()
    return dict(row, data=bytes(row['data'])) if row else None


@db_transaction(on_error=False)
def delete_listening_doc(cur, doc_id):
    cur.execute("DELETE FROM listening_docs WHERE id = %s;", (doc_id,))
    return cur.rowcount == 1


@db_transaction(on_error=None)
def get_listening_attempts(cur):
    """Per episode: its first score (the one that counted), its best, and how many tries."""
    cur.execute("SELECT episode_id, correct, total, points, counted FROM listening_attempts "
                "ORDER BY created_at, id;")
    out = {}
    for row in cur.fetchall():
        episode = out.setdefault(row['episode_id'], {"first": None, "best": None, "tries": 0})
        score = {"correct": row['correct'], "total": row['total'], "points": row['points']}
        if row['counted'] and episode["first"] is None:
            episode["first"] = score
        best = episode["best"]
        if best is None or row['correct'] / row['total'] > best["correct"] / best["total"]:
            episode["best"] = score
        episode["tries"] += 1
    return out


WRITING_COLUMNS = ("id, created_at, kind, prompt_id, prompt, text, words, revision_of, status, "
                   "score, band, feedback, counted, points, scored_at")


def _writing_row(row):
    piece = dict(row)
    for key in ("created_at", "scored_at"):
        if piece.get(key):
            piece[key] = piece[key].isoformat()
    return piece


@db_transaction(on_error=None)
def add_writing_piece(cur, kind, prompt_id, prompt, text, words, revision_of=None, feedback=None):
    """Keeps a new piece of writing, not yet marked (feedback may hold what the
    marking will need, such as a diary's words to try). Returns its id."""
    cur.execute("INSERT INTO writing_pieces (kind, prompt_id, prompt, text, words, revision_of, feedback) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id;",
                (kind, prompt_id, prompt, text, words, revision_of,
                 psycopg2.extras.Json(feedback) if feedback is not None else None))
    return cur.fetchone()['id']


@db_transaction(on_error=None)
def mark_writing_piece(cur, piece_id, score, band, feedback, offset_minutes=0):
    """Records the teacher's marks for a piece and decides whether it earns
    writing points: a revision never does; a diary does once a day (on the
    learner's clock); an IELTS task does once per question. The lock stops two
    quick submissions from both counting. Returns the piece."""
    cur.execute("LOCK TABLE writing_pieces IN SHARE ROW EXCLUSIVE MODE;")
    cur.execute("SELECT kind, prompt_id, revision_of, counted FROM writing_pieces WHERE id = %s;", (piece_id,))
    row = cur.fetchone()
    if row is None:
        return None
    counted = False
    if row['revision_of'] is None and not row['counted']:
        if row['kind'] == 'diary':
            cur.execute(f"SELECT EXISTS (SELECT 1 FROM writing_pieces WHERE kind = 'diary' AND counted "
                        f"AND {_local_day('scored_at')} = {_local_day('now()')}) AS done;",
                        (offset_minutes, offset_minutes))
        else:
            cur.execute("SELECT EXISTS (SELECT 1 FROM writing_pieces WHERE prompt_id = %s AND counted) AS done;",
                        (row['prompt_id'],))
        counted = not cur.fetchone()['done']
    points = score if counted else 0
    cur.execute("UPDATE writing_pieces SET status = 'scored', score = %s, band = %s, feedback = %s, "
                "counted = %s, points = %s, scored_at = now() WHERE id = %s;",
                (score, band, psycopg2.extras.Json(feedback), counted, points, piece_id))
    if counted:
        cur.execute("INSERT INTO practice_points (skill, word_id, mode, verdict, worth, points) "
                    "VALUES ('writing', NULL, %s, 'marked', 80, %s);", (row['kind'], points))
    cur.execute(f"SELECT {WRITING_COLUMNS} FROM writing_pieces WHERE id = %s;", (piece_id,))
    return _writing_row(cur.fetchone())


@db_transaction(on_error=None)
def get_writing_piece(cur, piece_id):
    cur.execute(f"SELECT {WRITING_COLUMNS} FROM writing_pieces WHERE id = %s;", (piece_id,))
    row = cur.fetchone()
    return _writing_row(row) if row else None


@db_transaction(on_error=None)
def get_writing_history(cur, limit=60):
    """The newest pieces first, without their full text and feedback."""
    cur.execute("SELECT id, created_at, kind, prompt_id, prompt, words, revision_of, status, score, band, "
                "counted, points FROM writing_pieces ORDER BY created_at DESC, id DESC LIMIT %s;", (limit,))
    return [_writing_row(r) for r in cur.fetchall()]


@db_transaction(on_error=None)
def get_writing_done(cur, offset_minutes=0):
    """Which IELTS questions have earned points already, with their scores, and
    whether today's diary is done."""
    cur.execute("SELECT prompt_id, MAX(score) AS best FROM writing_pieces WHERE counted AND kind <> 'diary' "
                "GROUP BY prompt_id;")
    done = {r['prompt_id']: r['best'] for r in cur.fetchall()}
    cur.execute(f"SELECT EXISTS (SELECT 1 FROM writing_pieces WHERE kind = 'diary' AND counted "
                f"AND {_local_day('scored_at')} = {_local_day('now()')}) AS done;", (offset_minutes, offset_minutes))
    return {"tasks": done, "diary_today": cur.fetchone()['done']}


@db_transaction(on_error=None)
def get_words_to_try(cur, offset_minutes=0, count=3):
    """A few saved words for today's diary, the same all day: the ones most in
    need of practice come first (highest priority score)."""
    today, _ = _today_and_monday(cur, offset_minutes)
    cur.execute("SELECT count(*) AS n FROM words;")
    total = cur.fetchone()['n']
    if not total:
        return []
    start = today.toordinal() * 104729 % total
    cur.execute("SELECT word, vietnamese_meaning FROM words ORDER BY priority_score DESC, id "
                "OFFSET %s LIMIT %s;", (start, count))
    rows = [dict(r) for r in cur.fetchall()]
    if len(rows) < count:  # wrap round to the start of the list
        cur.execute("SELECT word, vietnamese_meaning FROM words ORDER BY priority_score DESC, id LIMIT %s;",
                    (count - len(rows),))
        rows += [dict(r) for r in cur.fetchall()]
    return rows


@db_transaction(on_error=None)
def get_word_of_the_day(cur, offset_minutes=0):
    """One saved word for today on the learner's clock: the same all day, a
    different one tomorrow. Words with a picture come first. {} if none saved."""
    today, _ = _today_and_monday(cur, offset_minutes)
    cur.execute("SELECT count(*) AS n FROM words;")
    count = cur.fetchone()['n']
    if not count:
        return {}
    # A large prime stride, so that one day's word is far from the next day's.
    cur.execute("SELECT id, word, pronunciation_ipa, vietnamese_meaning, english_definition, example, image_url "
                "FROM words ORDER BY (image_url IS NULL OR image_url = ''), id OFFSET %s LIMIT 1;",
                (today.toordinal() * 7919 % count,))
    return dict(cur.fetchone())


@db_transaction(on_error=None)
def save_reading_attempt(cur, part_id, correct, total, worth, points, answers):
    """Keeps one submitted reading part. The first submission of a part adds
    its points to the reading skill; later ones are practice only. The lock
    stops two quick submissions from both counting as the first."""
    cur.execute("LOCK TABLE reading_attempts IN SHARE ROW EXCLUSIVE MODE;")
    cur.execute("SELECT EXISTS (SELECT 1 FROM reading_attempts WHERE part_id = %s) AS done;", (part_id,))
    counted = not cur.fetchone()['done']
    earned = points if counted else 0
    cur.execute("INSERT INTO reading_attempts (part_id, correct, total, points, counted, answers) "
                "VALUES (%s, %s, %s, %s, %s, %s);",
                (part_id, correct, total, earned, counted, psycopg2.extras.Json(answers)))
    if counted:
        cur.execute("INSERT INTO practice_points (skill, word_id, mode, verdict, worth, points) "
                    "VALUES ('reading', NULL, 'ielts_part', 'exam', %s, %s);", (worth, earned))
    return {"counted": counted, "points": earned}


@db_transaction(on_error=None)
def get_reading_attempts(cur, offset_minutes=0):
    """Per part: its first score (the one that counted), its best and how many
    tries; plus the learner's days (on their clock) with a counted part, newest
    first, and today's date there."""
    cur.execute(f"SELECT part_id, correct, total, points, counted, {_local_day('created_at')} AS day "
                "FROM reading_attempts ORDER BY created_at, id;", (offset_minutes,))
    parts, days = {}, set()
    for row in cur.fetchall():
        part = parts.setdefault(row['part_id'], {"first": None, "best": None, "tries": 0})
        score = {"correct": row['correct'], "total": row['total'], "points": row['points'],
                 "day": row['day'].isoformat()}
        if row['counted'] and part["first"] is None:
            part["first"] = score
            days.add(row['day'])
        if part["best"] is None or row['correct'] > part["best"]["correct"]:
            part["best"] = score
        part["tries"] += 1
    today, _ = _today_and_monday(cur, offset_minutes)
    return {"parts": parts, "days": sorted((d.isoformat() for d in days), reverse=True),
            "today": today.isoformat()}


@db_transaction(on_error=None)
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
            "keywords": result['vietnamese_keywords'] or derive_keywords(result['vietnamese_meaning'])
        }
    return None

@db_transaction(on_error=[])
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


@db_transaction(on_error={"status": "error", "message": "A database error occurred."})
def delete_word_by_id(cur, word_id):
    cur.execute("DELETE FROM words WHERE id = %s;", (word_id,))
    return {"status": "success"} if cur.rowcount > 0 else {"status": "error", "message": "Word not found"}


@db_transaction(on_error={"status": "error", "message": "A database error occurred."})
def delete_topic_by_id(cur, topic_id):
    cur.execute("DELETE FROM topics WHERE id = %s;", (topic_id,))
    return {"status": "success"} if cur.rowcount > 0 else {"status": "error", "message": "Topic not found"}