"""Checks for the Reading page. Everything it saves is removed afterwards."""
import os, sys, threading
import psycopg2, requests
from playwright.sync_api import sync_playwright

from common import BASE, ROOT
from myvocab import reading  # the answer key, to answer like a real reader

results = []
def check(name, ok, detail=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))

conn = psycopg2.connect(os.environ["DATABASE_URL"]); conn.autocommit = True; cur = conn.cursor()
requests.get(f"{BASE}/api/reading/plan")  # makes sure the table exists
cur.execute("SELECT coalesce(max(id), 0) FROM practice_points"); pp_max = cur.fetchone()[0]
cur.execute("SELECT coalesce(max(id), 0) FROM reading_attempts"); ra_max = cur.fetchone()[0]

def key(part):
    """{n: right answer as the page sends it}"""
    out = {}
    for g in part["groups"]:
        for q in g["questions"]:
            out[str(q["n"])] = q["a"][0] if g["type"] == "gap" else str(q["a"])
    return out

try:
    # ---------- API ----------
    plan = requests.get(f"{BASE}/api/reading/plan", params={"utc_offset": 420}).json()
    check("plan has 50 days in order", [p["day"] for p in plan["parts"]] == list(range(1, 51)))
    check("today's part is day 1", plan["next_id"] == 1 and plan["done_today"] == [] and plan["streak"] == 0)
    pub = requests.get(f"{BASE}/api/reading/part/1").json()
    flat = [q for g in pub["groups"] for q in g["questions"]]
    check("a part reaches the page without answers", all("a" not in q and "p" not in q for q in flat), flat[0])
    check("unknown part is 404", requests.get(f"{BASE}/api/reading/part/999").status_code == 404)
    bad = requests.post(f"{BASE}/api/reading/submit", json={"part_id": 999, "answers": {}})
    check("unknown part refused", bad.status_code == 400)

    p2 = reading.PARTS_BY_ID[2]
    k2 = key(p2)
    answers = dict(k2)
    answers["1"] = "0" if k2["1"] != "0" else "1"     # a wrong heading
    del answers["13"]                                 # a blank
    gap_n = next(str(q["n"]) for g in p2["groups"] if g["type"] == "gap" for q in g["questions"])
    answers[gap_n] = "  " + k2[gap_n].upper() + ". "  # case and punctuation do not matter
    r = requests.post(f"{BASE}/api/reading/submit", json={"part_id": 2, "answers": answers, "utc_offset": 420}).json()
    check("marks 11 right, 1 wrong, 1 blank", (r["correct"], r["wrong"], r["total"]) == (11, 1, 13), (r["correct"], r["wrong"]))
    check("points: 11×3 − 1 = +32", r["counted"] and r["points"] == 32, r["points"])
    check("band estimate for 11/13", r["band"] == reading.band(11, 13) and r["band"] >= 7, r["band"])
    check("a blank is marked blank", next(x for x in r["results"] if x["n"] == 13)["blank"])
    check("the key comes back with each mark", all(x["answer"] for x in r["results"]))
    check("reading progress updated", r["progress"]["skill"] == "reading" and r["progress"]["points"] >= 32 and r["progress"]["started"])
    r2 = requests.post(f"{BASE}/api/reading/submit", json={"part_id": 2, "answers": k2, "utc_offset": 420}).json()
    check("second try is practice only", not r2["counted"] and r2["points"] == 0 and r2["correct"] == 13)
    plan = requests.get(f"{BASE}/api/reading/plan", params={"utc_offset": 420}).json()
    d2 = plan["parts"][1]
    check("plan shows day 2 done with its first score", d2["scores"]["first"]["correct"] == 11 and d2["scores"]["tries"] == 2)
    check("done today and a 1-day streak", plan["done_today"] == [2] and plan["streak"] == 1)
    check("today's part is still day 1", plan["next_id"] == 1)

    out = []
    ts = [threading.Thread(target=lambda: out.append(requests.post(f"{BASE}/api/reading/submit",
          json={"part_id": 3, "answers": {}, "utc_offset": 420}).json())) for _ in range(2)]
    [t.start() for t in ts]; [t.join() for t in ts]
    check("two quick submissions count once", sorted(x["counted"] for x in out) == [False, True])

    # ---------- Browser ----------
    with sync_playwright() as p:
        br = p.chromium.launch()
        ctx = br.new_context(viewport={"width": 1440, "height": 950}, timezone_id="Asia/Ho_Chi_Minh")
        ctx.route("**/*open-meteo.com/**", lambda r: r.abort())
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "ERR_FAILED" not in m.text else None)
        pg.goto(BASE + "/reading", wait_until="networkidle")
        check("Reading tab current, Practice in the top bar", pg.get_attribute('.practice-tabs a[href="/reading"]', "aria-current") == "page"
              and pg.get_attribute('.nav-link[href="/practice"]', "aria-current") == "page")
        check("plan grid: 50 days, 2 and 3 done, 1 next", pg.locator(".plan-day").count() == 50
              and pg.locator(".plan-day.done").count() == 2 and "next" in pg.get_attribute(".plan-day >> nth=0", "class"))
        check("today card shows the part done today", "done" in pg.inner_text("#today-kicker").lower())
        check("streak shown", "1 day in a row" in pg.inner_text("#day-streak"))

        pg.click("#today-start")
        pg.wait_for_selector("#reading-test:not(.hidden)")
        check("opens day 1 with the passage", pg.inner_text("#test-title") == reading.PARTS_BY_ID[1]["title"]
              and pg.locator(".para").count() == len(reading.PARTS_BY_ID[1]["paragraphs"]))
        check("13 questions", pg.locator(".q").count() == 13)
        check("timer starts at 20:00", pg.inner_text("#timer-text") in ("20:00", "19:59"))
        check("address names the part", pg.evaluate("location.hash") == "#part-1")
        # Answer all but question 13, then leave and come back: the draft survives.
        k1 = key(reading.PARTS_BY_ID[1])
        types = {str(q["n"]): g["type"] for g in reading.PARTS_BY_ID[1]["groups"] for q in g["questions"]}
        for n, a in k1.items():
            if n == "13":
                continue
            if types[n] == "gap":
                pg.fill(f'input[name="q{n}"]', a)
            elif types[n] in ("tfng", "mcq"):
                pg.check(f'input[name="q{n}"][value="{a}"]')
            else:
                pg.select_option(f'select[name="q{n}"]', a)
        check("answered count 12/13", pg.inner_text("#answered-count") == "12/13")
        pg.click("#test-exit")
        check("back to the plan", pg.is_visible("#plan-grid") and not pg.is_visible("#reading-test"))
        pg.reload(wait_until="networkidle")
        pg.click('.plan-day >> nth=0')
        pg.wait_for_selector("#reading-test:not(.hidden)")
        check("draft answers restored", pg.inner_text("#answered-count") == "12/13")
        pg.click("#test-submit")
        check("a blank asks for a second click", "Submit anyway" in pg.inner_text("#test-submit"))
        pg.click("#test-submit")
        pg.wait_for_selector("#test-result:not(.hidden) .result-score")
        check("result: 12/13", "12/13" in pg.inner_text("#test-result"), pg.inner_text("#test-result")[:80])
        check("result shows +36 points and a band", "+36 points" in pg.inner_text("#test-result") and "band" in pg.inner_text("#test-result"))
        check("questions marked", pg.locator(".q.right").count() == 12 and pg.locator(".q.blank").count() == 1)
        check("inputs locked after marking", pg.locator("#questions-pane input:enabled").count() == 0)
        pg.wait_for_timeout(900)  # the number counts up to its new value
        check("goal panel updated", int(pg.inner_text('.goal-panel[data-skill="reading"] [data-goal="points"]')) >= 32 + 36)
        pg.click(".q.blank .q-where")
        pg.wait_for_timeout(300)
        check("See paragraph highlights it", pg.locator(".para.flash").count() == 1)
        check("Next part offered", "Next: Day" in pg.inner_text("#test-result"))
        pg.click(".result-back")
        pg.wait_for_function("document.querySelectorAll('.plan-day.done').length === 3", timeout=5000)
        check("plan now shows 3 done", pg.locator(".plan-day.done").count() == 3)

        pg.goto(BASE + "/reading#part-5", wait_until="networkidle")
        pg.wait_for_selector("#reading-test:not(.hidden)")
        check("/reading#part-5 opens day 5", pg.inner_text("#test-title") == reading.PARTS_BY_ID[5]["title"])
        check("heading list and selects", pg.locator(".heading-list li").count() == 8 and pg.locator("select.q-select").count() == 6)
        pg.fill(".q-gap >> nth=0", "far too many words here")
        check("gap over the word limit is flagged", "too-many" in pg.get_attribute(".q-gap >> nth=0", "class"))

        pg.set_viewport_size({"width": 390, "height": 844})
        pg.wait_for_timeout(200)
        check("phone: passage first, questions hidden", pg.is_visible("#passage-pane") and not pg.is_visible("#questions-pane"))
        pg.click("#show-questions")
        check("phone: questions tab", pg.is_visible("#questions-pane") and not pg.is_visible("#passage-pane"))
        check("phone: no sideways scroll", pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") == 0)
        pg.click("#test-exit")
        check("phone: plan, no sideways scroll", pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") == 0)

        pg.set_viewport_size({"width": 1440, "height": 950})
        pg.goto(BASE + "/tracking#reading", wait_until="networkidle")
        check("Tracking: Practise reading link", pg.get_attribute("#band-reading .band-practice", "href") == "/reading")
        check("Tracking: reading rules", "Each right answer wins 3 points" in " ".join(pg.text_content("#band-reading .goal-rules").split()))
        check("no console errors", not errs, errs[:3])
        br.close()
finally:
    cur.execute("DELETE FROM reading_attempts WHERE id > %s", (ra_max,))
    cur.execute("DELETE FROM practice_points WHERE id > %s AND skill = 'reading'", (pp_max,))
    cur.execute("SELECT count(*) FROM reading_attempts WHERE id > %s", (ra_max,)); left = cur.fetchone()[0]
    check("database back as it was", left == 0)
print(f"\n{sum(results)}/{len(results)} passed")
raise SystemExit(0 if results and all(results) else 1)
