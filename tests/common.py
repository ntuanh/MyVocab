"""Shared by the test suites: where the copy of MyVocab under test is, and the
PASS/FAIL list each suite prints.

tests/run_all.py starts a separate copy (its own database, made from your
newest backup) and sets the addresses below. A suite can also run alone,
against any copy that is running, for example your own:

    MYVOCAB_TEST_URL=http://127.0.0.1:5000 .venv/bin/python tests/reading_test.py

Suites that write to the database remove what they added, but run them alone
against your own copy only if you are happy for them to touch it.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)  # so a suite can import myvocab.*
os.chdir(ROOT)

BASE = os.environ.get("MYVOCAB_TEST_URL", "http://127.0.0.1:5000").rstrip("/")
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
SHOTS = os.path.join(ROOT, "tests", ".shots")  # screenshots taken along the way (gitignored)
os.makedirs(SHOTS, exist_ok=True)

# The database of the copy under test. myvocab.* reads DATABASE_URL, so it is set for them too.
if os.environ.get("MYVOCAB_TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["MYVOCAB_TEST_DATABASE_URL"]
else:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
DATABASE_URL = os.environ.get("DATABASE_URL", "")
