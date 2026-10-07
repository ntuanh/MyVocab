"""Seed the words table from a curated dataset.

A word already in the table is served straight from the database -- see the cache
check at the top of get_dictionary_data -- so pre-seeding removes the Gemini,
Pexels and dictionary API round trips from the first search of every word here.
That is the whole point of this script: pay the API cost once, offline.

Usage (from the project root):

    python dev/seed_words.py                      # dry run, changes nothing
    python dev/seed_words.py --limit 5 --commit   # try five words for real
    python dev/seed_words.py --commit             # seed everything

Needs DATABASE_URL. PEXELS_API_KEY is optional but without it no images are
fetched, which defeats the point -- the script refuses to commit imageless rows
unless you pass --allow-no-image.
"""

import argparse
import json
import os
import sys
import time

# A Windows console defaults to cp1252, which cannot encode Vietnamese. Any
# diacritic reaching stdout -- in a word, a topic name, an error -- would kill
# the run with UnicodeEncodeError partway through seeding.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass

# Import the app's own modules rather than re-implementing any of this, so the
# seeded rows are identical in shape to rows saved through the UI.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# handle_request tunes the dictionary API for a Vercel request with a user
# waiting: 3s per attempt inside an 8s total deadline. Batch seeding has nobody
# waiting, and at those settings most lookups time out and land "N/A" in the IPA
# column. These knobs are read at import time, so they must be set before the
# import below. setdefault, so a value already in the environment still wins.
os.environ.setdefault("DICT_ATTEMPT_TIMEOUT", "10")
os.environ.setdefault("DICT_DEADLINE", "40")
os.environ.setdefault("DICT_MAX_ATTEMPTS", "4")

import requests  # noqa: E402

from myvocab.database import (  # noqa: E402
    save_word,
    get_db_connection,
    initialize_schema,
    get_all_topics,
    add_new_topic,
    derive_keywords,
)
from myvocab.handle_request import get_data_from_dictionary_api  # noqa: E402

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         os.pardir, 'data', 'b1_words.json')

# Pexels' free tier allows 200 requests an hour. A full run is exactly 200 words,
# so it sits right on that ceiling -- hence the delay and the explicit 429 check.
PEXELS_URL = "https://api.pexels.com/v1/search"
RATE_LIMITED = "rate_limited"


def fetch_image(word, api_key, timeout=10):
    """Returns (url, status). Unlike the app's version this reports a 429
    separately: silently seeding 200 rows with no image is the one outcome that
    would waste the whole run, so the caller needs to be able to stop."""
    if not api_key:
        return None, "no_key"
    try:
        r = requests.get(PEXELS_URL,
                         headers={"Authorization": api_key},
                         params={"query": word, "per_page": 1},
                         timeout=timeout)
        if r.status_code == 429:
            return None, RATE_LIMITED
        if r.status_code != 200:
            return None, f"http_{r.status_code}"
        photos = r.json().get("photos") or []
        if not photos:
            return None, "no_result"
        return photos[0]["src"]["large"], "ok"
    except Exception as e:
        return None, f"error: {e}"


def existing_words(words):
    """Returns the subset of `words` that already have a row in the table.

    find_word_in_db() opens its own connection and re-runs the schema DDL on
    every call, so asking it about 200 words costs 200 round trips to a remote
    database -- minutes of waiting before the first word is even fetched. One
    query answers exactly the same question.
    """
    conn = get_db_connection()
    if conn is None:
        sys.exit("Could not connect to the database. Check DATABASE_URL.")
    try:
        with conn:
            with conn.cursor() as cur:
                initialize_schema(cur)  # a brand new database has no words table yet
                cur.execute("SELECT word FROM words WHERE word = ANY(%s);", (list(words),))
                return {r[0] for r in cur.fetchall()}
    finally:
        conn.close()


def resolve_topics(entries, commit):
    """Maps each topic name in the dataset to a topic id, creating any that the
    database does not have yet. Returns {name: id} (empty on a dry run)."""
    wanted = sorted({e["topic"] for e in entries})
    existing = {t["name"]: t["id"] for t in get_all_topics()}
    mapping = {}
    for name in wanted:
        if name in existing:
            mapping[name] = existing[name]
            continue
        if not commit:
            print(f"  would create topic: {name}")
            continue
        created = add_new_topic(name)
        if created:
            mapping[name] = created["id"]
            print(f"  created topic: {name} (id {created['id']})")
        else:
            print(f"  WARN: could not create topic {name!r}; words will be untagged")
    return mapping


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--commit', action='store_true',
                   help='actually write to the database (default is a dry run)')
    p.add_argument('--limit', type=int, help='only process the first N new words')
    p.add_argument('--delay', type=float, default=1.0,
                   help='seconds to wait between words (default 1.0)')
    p.add_argument('--allow-no-image', action='store_true',
                   help='seed a word even when no image could be fetched')
    p.add_argument('--data', default=DATA_FILE, help='path to the word dataset')
    args = p.parse_args()

    if not os.environ.get("DATABASE_URL"):
        sys.exit("DATABASE_URL is not set. Put it in .env or export it first.")

    pexels_key = os.environ.get("PEXELS_API_KEY")
    if not pexels_key and not args.allow_no_image:
        sys.exit("PEXELS_API_KEY is not set, so no images would be fetched.\n"
                 "Set it, or pass --allow-no-image if you really want rows without images.")

    with open(args.data, encoding='utf-8') as fh:
        entries = json.load(fh)
    print(f"dataset: {len(entries)} words from {os.path.relpath(args.data)}")

    mode = "COMMIT" if args.commit else "DRY RUN (nothing will be written)"
    print(f"mode:    {mode}\n")

    # A word already in the table is skipped outright rather than re-saved.
    # save_word() deletes and rewrites a word's topic rows, so calling it on an
    # existing word would silently discard topic choices made in the UI.
    print("checking which words are already in the database...")
    present = existing_words([e["word"] for e in entries])
    todo = [e for e in entries if e["word"] not in present]
    skipped = len(entries) - len(todo)
    print(f"  {skipped} already present, {len(todo)} to add")

    if args.limit:
        todo = todo[:args.limit]
        print(f"  --limit {args.limit}: processing {len(todo)}")
    if not todo:
        print("\nNothing to do.")
        return
    print()

    # Only the topics of the words being added, so --limit leaves no empty topics.
    print("topics:")
    topic_ids = resolve_topics(todo, args.commit)
    print()

    added = failed = no_image = 0
    for i, entry in enumerate(todo, 1):
        word = entry["word"]
        prefix = f"[{i}/{len(todo)}] {word:<16}"

        image_url, image_status = fetch_image(word, pexels_key)
        if image_status == RATE_LIMITED:
            print(f"{prefix} PEXELS RATE LIMIT REACHED -- stopping here.")
            print("  Pexels allows 200 requests an hour. Wait an hour and run again;")
            print("  the words already seeded will be skipped automatically.")
            break
        if image_url is None:
            no_image += 1
            if not args.allow_no_image:
                print(f"{prefix} no image ({image_status}) -- skipped")
                failed += 1
                time.sleep(args.delay)
                continue

        # IPA and synonyms come from the free dictionary API (no key required);
        # the definition and the Vietnamese meaning stay as curated in the dataset.
        dict_data = get_data_from_dictionary_api(word)

        word_data = {
            "word": word,
            "vietnamese_meaning": entry["vietnamese_meaning"],
            "english_definition": entry["english_definition"],
            "example": entry["example"],
            "image_url": image_url,
            "pronunciation_ipa": dict_data.get("pronunciation") or "N/A",
            "synonyms": dict_data.get("synonyms") or [],
            "family_words": [],
            "vietnamese_keywords": derive_keywords(entry["vietnamese_meaning"]),
        }

        ipa = word_data["pronunciation_ipa"]
        img = "img" if image_url else "no-img"
        if not args.commit:
            print(f"{prefix} would add  {ipa:<18} {img}")
            added += 1
        else:
            tid = topic_ids.get(entry["topic"])
            result = save_word(word_data, [tid] if tid else [])
            if result.get("status") in ("success", "updated"):
                print(f"{prefix} added      {ipa:<18} {img}  [{entry['topic']}]")
                added += 1
            else:
                print(f"{prefix} FAILED: {result.get('message')}")
                failed += 1

        time.sleep(args.delay)

    print()
    print(f"{'would add' if not args.commit else 'added'}: {added}   "
          f"failed/skipped: {failed}   without image: {no_image}")
    if not args.commit:
        print("\nThis was a dry run. Re-run with --commit to write these to the database.")


if __name__ == '__main__':
    main()
