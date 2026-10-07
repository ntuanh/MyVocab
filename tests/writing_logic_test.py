"""Writing marking logic with Gemini replaced by canned answers. Cleans up after itself."""
import os, sys
import common  # noqa: F401  (myvocab on the path, and the database under test)
import psycopg2
from myvocab import writing
from myvocab.handle_request import OK, UNAVAILABLE
from datetime import date

results = []
def check(name, ok, detail=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))

conn = psycopg2.connect(os.environ["DATABASE_URL"]); conn.autocommit = True; cur = conn.cursor()
writing.get_writing_done(420)  # makes sure the table exists
cur.execute("SELECT coalesce(max(id),0) FROM writing_pieces"); wp_max = cur.fetchone()[0]
cur.execute("SELECT coalesce(max(id),0) FROM practice_points"); pp_max = cur.fetchone()[0]

def canned(scores, band=6.5, extra=None):
    body = {"criteria": [{"name": "x", "score": s, "comment": f"c{i}"} for i, s in enumerate(scores)],
            "band": band, "overall": "Good effort.", "strengths": ["Clear ideas"],
            "mistakes": [{"wrong": "I goes", "right": "I go", "type": "grammar", "why": "subject-verb agreement"}],
            "vocabulary": [{"word": "good", "better": ["excellent", "superb"], "note": "for stronger praise"}],
            "improved": "Better text.", "next_step": "Practise linking words.", "summary_vi": "Bài viết tốt.",
            "words_used": [{"word": "commute", "used_well": True, "note": "natural"}]}
    body.update(extra or {})
    return lambda *a, **k: (body, OK)

prompts_seen = []
def recording(fn):
    def inner(prompt, *a, **k):
        prompts_seen.append(prompt)
        return fn(prompt, *a, **k)
    return inner

DIARY_TEXT = "Today I goes to the market with my sister. " * 10   # 90 words
TASK_TEXT = "The graph shows how the number of visitors changed over the period. " * 14
day = date.today().toordinal()
try:
    writing.call_gemini_json = recording(canned([15, 14, 13, 16]))
    body, status = writing.check({"kind": "diary", "idea": writing.DIARY[3], "words_to_try": ["commute", "borrow"],
                                  "text": DIARY_TEXT}, 420, day)
    p = body["piece"]
    check("diary marked: 15+14+13+16 = 58", status == 200 and p["score"] == 58 and p["status"] == "scored", p.get("score"))
    check("diary has no band", p["band"] is None)
    check("first diary today counts: +58", p["counted"] and p["points"] == 58)
    check("the idea is kept as the prompt", p["prompt"] == writing.DIARY[3])
    check("words to try reach the teacher", "commute, borrow" in prompts_seen[-1])
    check("feedback cleaned and named by criterion", [c["name"] for c in p["feedback"]["criteria"]] ==
          [n for n, _ in writing.KINDS["diary"]["criteria"]] and p["feedback"]["mistakes"][0]["right"] == "I go")
    cur.execute("SELECT points, skill FROM practice_points WHERE id > %s ORDER BY id DESC LIMIT 1", (pp_max,))
    check("writing points recorded", cur.fetchone() == (58, "writing"))

    body, _ = writing.check({"kind": "diary", "idea": "made up idea", "text": DIARY_TEXT}, 420, day)
    check("second diary today: practice only", not body["piece"]["counted"] and body["piece"]["points"] == 0)
    check("an unknown idea falls back to today's", body["piece"]["prompt"] == writing.diary_prompt(day))

    rev, _ = writing.check({"kind": "diary", "text": DIARY_TEXT + " Better.", "revision_of": p["id"]}, 420, day)
    check("a revision never counts", rev["piece"]["revision_of"] == p["id"] and not rev["piece"]["counted"])

    writing.call_gemini_json = recording(canned([18, 17, 16, 17], band=7.5))
    t, _ = writing.check({"kind": "task1", "prompt_id": "t1-05", "text": TASK_TEXT}, 420, day)
    check("task 1 marked 68 with band 7.5", t["piece"]["score"] == 68 and t["piece"]["band"] == 7.5 and t["piece"]["counted"])
    check("task 1: the chart's numbers reach the teacher", "Harbourton: 35, 55, 78, 90, 96" in prompts_seen[-1])
    t2, _ = writing.check({"kind": "task1", "prompt_id": "t1-05", "text": TASK_TEXT}, 420, day)
    check("same question again: practice only", not t2["piece"]["counted"])
    done = writing.get_writing_done(420)
    check("done list shows t1-05 with its best", done["tasks"].get("t1-05") == 68 and done["diary_today"])
    nxt, _ = writing.prompt_for("task1", 420, day)
    check("next Task 1 skips the done one", nxt["id"] != "t1-05" and nxt["done_count"] == 1)

    # Scores out of range are clamped; a missing band is worked out from the score.
    writing.call_gemini_json = canned([25, -3, "12", 19.6], band=None)
    w, _ = writing.check({"kind": "task2", "prompt_id": "t2-03", "text": TASK_TEXT * 2}, 420, day)
    check("scores clamped to 0-20: 20+0+12+20 = 52", w["piece"]["score"] == 52, w["piece"]["score"])
    check("band from the score when missing", w["piece"]["band"] == writing.band_from_score(52))

    # Unusable answers: missing criteria, then the AI unavailable.
    writing.call_gemini_json = lambda *a, **k: ({"criteria": [{"score": 10}]}, OK)
    bad, status = writing.check({"kind": "task2", "prompt_id": "t2-04", "text": TASK_TEXT * 2}, 420, day)
    check("an incomplete answer leaves the piece waiting", status == 200 and bad["waiting"] and bad["piece"]["status"] == "waiting")
    writing.call_gemini_json = lambda *a, **k: ({}, UNAVAILABLE)
    wait, _ = writing.check({"kind": "task2", "prompt_id": "t2-05", "text": TASK_TEXT * 2}, 420, day)
    check("AI unavailable: kept and waiting", wait["waiting"] and wait["piece"]["status"] == "waiting")
    writing.call_gemini_json = canned([12, 12, 12, 12], band=6)
    again, _ = writing.retry(wait["piece"]["id"], 420)
    check("retry marks it and it counts", not again["waiting"] and again["piece"]["score"] == 48 and again["piece"]["counted"])
    again2, _ = writing.retry(wait["piece"]["id"], 420)
    check("retrying a marked piece changes nothing", again2["piece"]["score"] == 48)

    # Refusals.
    for data, why in [({"kind": "poem", "text": DIARY_TEXT}, "Choose"),
                      ({"kind": "diary", "text": "Too short."}, "at least 40"),
                      ({"kind": "task1", "prompt_id": "t2-01", "text": TASK_TEXT}, "not in the list"),
                      ({"kind": "task2", "prompt_id": "t2-01", "text": "word " * 3000}, "under 6000"),
                      ({"kind": "diary", "text": DIARY_TEXT, "revision_of": 99999999}, "not found")]:
        body, status = writing.check(data, 420, day)
        check(f"refused: {why}", status == 400 and why in body["error"], body.get("error"))
finally:
    cur.execute("DELETE FROM writing_pieces WHERE id > %s", (wp_max,))
    cur.execute("DELETE FROM practice_points WHERE id > %s AND skill = 'writing'", (pp_max,))
    cur.execute("SELECT count(*) FROM writing_pieces WHERE id > %s", (wp_max,))
    check("database back as it was", cur.fetchone()[0] == 0)
print(f"\n{sum(results)}/{len(results)} passed")
raise SystemExit(0 if results and all(results) else 1)
