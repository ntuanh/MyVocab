"""The word pack: every word and topic, so a new computer starts with the same
words as the developer's, without anyone's scores. data/word_pack.json holds
each word as saved (meanings, definition, example, picture, pronunciation,
synonyms, family words, topics) and the weekly targets. It does not hold points,
attempts, writing, or how hard each word has been in the exam.

    python tools/word_pack.py export [FILE]   # from this computer's database (dev/release.py does it)
    python tools/word_pack.py import [FILE]   # into this computer's database (run.py does it)

Import only adds. A word you already have keeps everything you changed. A word
the pack offered before is not offered again, so a word you deleted stays
deleted (.wordpack lists the words already offered). Targets are only set on a
database that has none. Needs DATABASE_URL (from .env).
"""
import datetime
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
PACK = os.path.join(ROOT, "data", "word_pack.json")
OFFERED = os.path.join(ROOT, ".wordpack")  # the pack's words this computer has been offered
# .wordpack starts with "# <sha256 of the pack>", so run.py can tell when the pack has changed.
FIELDS = ["word", "vietnamese_meaning", "english_definition", "example", "image_url",
          "pronunciation_ipa", "vietnamese_keywords"]


def connect():
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(ROOT, ".env"))
    except ImportError:
        pass
    if not os.environ.get("DATABASE_URL"):
        sys.exit("DATABASE_URL is not set (it is in .env).")
    from myvocab.database import get_db_connection, initialize_schema
    conn = get_db_connection()
    if not conn:
        sys.exit("Could not connect to the database.")
    with conn.cursor() as cur:
        initialize_schema(cur)
    conn.commit()
    return conn


def export(path=PACK):
    conn = connect()
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT {', '.join('w.' + f for f in FIELDS)}, w.synonyms_json, w.family_words_json,
                   coalesce(array_agg(t.name ORDER BY t.name) FILTER (WHERE t.name IS NOT NULL), '{{}}')
            FROM words w
            LEFT JOIN word_topics wt ON wt.word_id = w.id
            LEFT JOIN topics t ON t.id = wt.topic_id
            GROUP BY w.id ORDER BY w.id""")
        words = []
        for row in cur.fetchall():
            entry = dict(zip(FIELDS, row[:len(FIELDS)]))
            entry["synonyms"] = row[len(FIELDS)] or []
            entry["family_words"] = row[len(FIELDS) + 1] or []
            entry["topics"] = list(row[len(FIELDS) + 2])
            words.append(entry)
        cur.execute("SELECT name FROM topics ORDER BY id")
        topics = [name for (name,) in cur.fetchall()]
        # Each skill's current target: the one set for the latest week.
        cur.execute("SELECT DISTINCT ON (skill) skill, target FROM skill_goals ORDER BY skill, week_start DESC")
        targets = dict(cur.fetchall())
    conn.close()
    pack = {"made": datetime.date.today().isoformat(), "topics": topics, "targets": targets, "words": words}
    old = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            old = json.load(f)
    if old and {k: v for k, v in old.items() if k != "made"} == {k: v for k, v in pack.items() if k != "made"}:
        print(f"Word pack unchanged: {len(words)} words.")
        return False
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"Word pack saved: {len(words)} words, {len(topics)} topics -> {os.path.relpath(path, ROOT)}")
    return True


def import_pack(path=PACK):
    if not os.path.exists(path):
        print("No word pack to load.")
        return 0
    with open(path, "rb") as f:
        raw = f.read()
    pack = json.loads(raw)
    offered = set()
    if os.path.exists(OFFERED):
        with open(OFFERED, encoding="utf-8") as f:
            offered = {line for line in f.read().split("\n") if line and not line.startswith("#")}
    conn = connect()
    added = 0
    with conn.cursor() as cur:
        for name in pack.get("topics", []):
            cur.execute("INSERT INTO topics (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (name,))
        cur.execute("SELECT name, id FROM topics")
        topic_ids = dict(cur.fetchall())
        for entry in pack["words"]:
            if entry["word"] in offered:
                continue
            cur.execute(f"""
                INSERT INTO words ({', '.join(FIELDS)}, synonyms_json, family_words_json)
                VALUES ({', '.join(['%s'] * (len(FIELDS) + 2))})
                ON CONFLICT (word) DO NOTHING RETURNING id""",
                [entry.get(f) for f in FIELDS] + [json.dumps(entry.get("synonyms") or []),
                                                  json.dumps(entry.get("family_words") or [])])
            row = cur.fetchone()
            if not row:
                continue  # already here: leave it as it is
            added += 1
            for name in entry.get("topics", []):
                if name in topic_ids:
                    cur.execute("INSERT INTO word_topics (word_id, topic_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                                (row[0], topic_ids[name]))
        cur.execute("SELECT count(*) FROM skill_goals")
        if cur.fetchone()[0] == 0 and pack.get("targets"):
            monday = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())
            for skill, target in pack["targets"].items():
                cur.execute("INSERT INTO skill_goals (skill, week_start, target) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                            (skill, monday, target))
    conn.commit()
    conn.close()
    with open(OFFERED, "w", encoding="utf-8") as f:
        f.write(f"# {hashlib.sha256(raw).hexdigest()}\n")
        f.write("\n".join(sorted(offered | {e["word"] for e in pack["words"]})) + "\n")
    print(f"Word pack: {added} new word{'' if added == 1 else 's'} added." if added else "Word pack: no new words.")
    return added


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    target = sys.argv[2] if len(sys.argv) > 2 else PACK
    if command == "export":
        export(target)
    elif command == "import":
        import_pack(target)
    else:
        sys.exit(__doc__)
