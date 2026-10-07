"""Fill in what saved words are missing: a picture, the IPA, synonyms and family words.

A word seeded while a service was down or a key was not set comes out with gaps.
This finds those gaps and asks again, so the curated meaning, definition and
example are kept and nothing else is touched.

Usage (from the project root):

    .venv/bin/python dev/fill_missing.py            # dry run: count the gaps
    .venv/bin/python dev/fill_missing.py --commit   # fill them in

Where each part comes from:
  - IPA and synonyms: the free dictionary API, no key needed.
  - Pictures: Pexels, needs PEXELS_API_KEY.
  - Family words, plus IPA and synonyms the dictionary API does not know:
    Gemini, needs GEMINI_API_KEY. It asks about 25 words per request, so 200
    words cost 8 requests of the free tier's 20 a day per model.
A part whose key is missing is skipped; run again after adding the key.
"""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# One Gemini request here answers for 25 words, so it needs far longer than the
# 10s a single lookup gets. Read at import time, so set before the import below.
os.environ.setdefault("GEMINI_TIMEOUT", "90")

import psycopg2.extras  # noqa: E402

# seed_words loads .env and tunes the dictionary API timeouts for batch work.
from seed_words import fetch_image, RATE_LIMITED  # noqa: E402
from myvocab.database import get_db_connection, initialize_schema  # noqa: E402
from myvocab.handle_request import get_data_from_dictionary_api, call_gemini_json, OK  # noqa: E402

GEMINI_BATCH = 25


def missing_ipa(row):
    return not row["pronunciation_ipa"] or row["pronunciation_ipa"] == "N/A"


def load_words(conn):
    with conn, conn.cursor() as cur:
        initialize_schema(cur)  # it reads rows by position, so not a dict cursor
    with conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT id, word, image_url, pronunciation_ipa, synonyms_json, family_words_json "
                    "FROM words ORDER BY id;")
        return [dict(r) for r in cur.fetchall()]


def save(conn, word_id, **fields):
    columns = ", ".join(f"{name} = %s" for name in fields)
    values = [psycopg2.extras.Json(v) if isinstance(v, list) else v for v in fields.values()]
    with conn, conn.cursor() as cur:
        cur.execute(f"UPDATE words SET {columns} WHERE id = %s;", (*values, word_id))


def fill_from_dictionary(conn, rows, commit):
    todo = [r for r in rows if missing_ipa(r)]
    print(f"\nIPA and synonyms from the dictionary API: {len(todo)} words")
    if not commit or not todo:
        return
    found = 0
    # The API is slow and flaky rather than rate limited, so a few at a time.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for row, data in zip(todo, pool.map(lambda r: get_data_from_dictionary_api(r["word"]), todo)):
            ipa = data.get("pronunciation")
            if ipa and ipa != "N/A":
                row["pronunciation_ipa"] = ipa
                row["synonyms_json"] = row["synonyms_json"] or data.get("synonyms") or []
                save(conn, row["id"], pronunciation_ipa=ipa, synonyms_json=row["synonyms_json"])
                found += 1
    print(f"  found {found}; {len(todo) - found} left for Gemini")


def fill_images(conn, rows, commit):
    todo = [r for r in rows if not r["image_url"]]
    key = os.environ.get("PEXELS_API_KEY")
    print(f"\nPictures from Pexels: {len(todo)} words")
    if not todo:
        return
    if not key:
        print("  skipped: PEXELS_API_KEY is not set")
        return
    if not commit:
        return
    found = 0
    for row in todo:
        url, status = fetch_image(row["word"], key)
        if status == RATE_LIMITED:
            print("  Pexels allows 200 requests an hour; stopping. Run again later to finish.")
            break
        if url:
            save(conn, row["id"], image_url=url)
            found += 1
    print(f"  found {found}")


def gemini_prompt(words):
    listed = "\n".join(f"- {w}" for w in words)
    return f"""
    For each English word below, give its British English IPA pronunciation,
    up to 4 common synonyms, and up to 4 words from the same word family
    (related nouns, verbs, adjectives or adverbs, not the word itself).
    Return a JSON object keyed by the word exactly as written:
    {{"word": {{"ipa": "/.../", "synonyms": ["..."], "family_words": ["..."]}}}}
    Use an empty list when there are none.

    {listed}
    """


def clean_list(value, word):
    if not isinstance(value, list):
        return []
    items = [v.strip() for v in value if isinstance(v, str) and v.strip()]
    return [v for v in items if v.lower() != word.lower()][:4]


def fill_from_gemini(conn, rows, commit):
    todo = [r for r in rows if not r["family_words_json"] or missing_ipa(r) or not r["synonyms_json"]]
    print(f"\nFamily words (and missing IPA or synonyms) from Gemini: {len(todo)} words")
    if not todo:
        return
    if not os.environ.get("GEMINI_API_KEY"):
        print("  skipped: GEMINI_API_KEY is not set")
        return
    batches = [todo[i:i + GEMINI_BATCH] for i in range(0, len(todo), GEMINI_BATCH)]
    print(f"  {len(batches)} Gemini requests")
    if not commit:
        return
    filled = 0
    for n, batch in enumerate(batches, 1):
        content, status = call_gemini_json(gemini_prompt([r["word"] for r in batch]),
                                           f"fill batch {n}/{len(batches)}")
        if status != OK or not isinstance(content, dict):
            print(f"  batch {n} failed; stopping. Run again later to finish.")
            break
        for row in batch:
            answer = content.get(row["word"])
            if not isinstance(answer, dict):
                continue
            fields = {}
            ipa = answer.get("ipa")
            if missing_ipa(row) and isinstance(ipa, str) and ipa.strip():
                fields["pronunciation_ipa"] = ipa.strip()
            if not row["synonyms_json"]:
                fields["synonyms_json"] = clean_list(answer.get("synonyms"), row["word"])
            if not row["family_words_json"]:
                fields["family_words_json"] = clean_list(answer.get("family_words"), row["word"])
            if fields:
                save(conn, row["id"], **fields)
                filled += 1
        print(f"  batch {n}/{len(batches)} done")
    print(f"  filled {filled}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--commit", action="store_true",
                   help="actually write to the database (default is a dry run)")
    args = p.parse_args()

    if not os.environ.get("DATABASE_URL"):
        sys.exit("DATABASE_URL is not set. Put it in .env or export it first.")
    conn = get_db_connection()
    if conn is None:
        sys.exit("Could not connect to the database. Check DATABASE_URL.")
    try:
        rows = load_words(conn)
        print(f"{len(rows)} words; mode: {'COMMIT' if args.commit else 'DRY RUN (nothing will be written)'}")
        fill_from_dictionary(conn, rows, args.commit)
        fill_images(conn, rows, args.commit)
        fill_from_gemini(conn, rows, args.commit)
    finally:
        conn.close()
    if not args.commit:
        print("\nThis was a dry run. Re-run with --commit to fill these in.")


if __name__ == "__main__":
    main()
