"""Checks for the Tracking page and the shared goal panel. Adds six fake past
weeks of Vocab points (mode='__chart_test__') and restores every goal row and
removes every test point afterwards, even on failure."""
import json
import os
from datetime import datetime, time, timedelta, timezone

import psycopg2
import requests
from playwright.sync_api import sync_playwright

from common import BASE, ROOT
ICT = timezone(timedelta(hours=7))
results = []

def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT skill, week_start, target FROM skill_goals ORDER BY 1, 2")
goals_before = cur.fetchall()
cur.execute("SELECT count(*), coalesce(sum(points), 0) FROM practice_points")
points_before = cur.fetchone()

today = datetime.now(ICT).date()
monday = today - timedelta(days=today.weekday())

def seed():
    cur.execute("INSERT INTO skill_goals (skill, week_start, target) VALUES ('vocab', %s, 300), ('vocab', %s, 250)",
                (monday - timedelta(weeks=6), monday - timedelta(weeks=3)))
    for ago, pts in [(6, 320), (5, 180), (4, 450), (3, 200), (2, 300), (1, 260)]:
        at = datetime.combine(monday - timedelta(weeks=ago) + timedelta(days=2), time(12), ICT)
        cur.execute("INSERT INTO practice_points (created_at, skill, word_id, mode, verdict, worth, points) "
                    "VALUES (%s, 'vocab', NULL, '__chart_test__', 'correct', %s, %s)", (at, pts, pts))

def restore():
    cur.execute("DELETE FROM practice_points WHERE mode = '__chart_test__'")
    cur.execute("DELETE FROM skill_goals")
    for row in goals_before:
        cur.execute("INSERT INTO skill_goals (skill, week_start, target) VALUES (%s, %s, %s)", row)

try:
    # ---------- API ----------
    r = requests.get(f"{BASE}/api/progress/all", params={"utc_offset": 420}).json()
    skills = [b["skill"] for b in r["bands"]]
    check("all bands: vocab, listening, reading, writing", skills == ["vocab", "listening", "reading", "writing"], skills)
    check("all four bands have a practice", [b["has_practice"] for b in r["bands"]] == [True, True, True, True])
    check("every band has a target", all(b["progress"]["target"] >= 10 for b in r["bands"]))
    check("bands never practised are not started",
          [b["progress"]["started"] for b in r["bands"]][1:] == [False, False, False])
    check("not started: nothing carried, no past weeks", all(b["progress"]["carried"] == 0 and not b["progress"]["past_weeks"]
                                                             for b in r["bands"][1:]))
    g = requests.get(f"{BASE}/api/progress", params={"skill": "listening"})
    check("listening progress can be read", g.status_code == 200 and g.json()["skill"] == "listening")
    t = requests.post(f"{BASE}/api/progress/target", json={"skill": "listening", "target": 120, "utc_offset": 420})
    check("one band's target can be set", t.status_code == 200 and t.json()["target"] == 120, t.text[:120])
    check("unknown skill refused", requests.get(f"{BASE}/api/progress", params={"skill": "chess"}).status_code == 400)

    bad = requests.post(f"{BASE}/api/progress/targets", json={"targets": {"vocab": 400, "reading": 5}, "utc_offset": 420})
    vocab_now = requests.get(f"{BASE}/api/progress", params={"skill": "vocab", "utc_offset": 420}).json()["target"]
    check("one bad target saves nothing", bad.status_code == 400 and bad.json().get("skill") == "reading"
          and vocab_now == 300, f"{bad.json()} vocab={vocab_now}")
    check("bad target names the band", "Reading target from 10 to 5000" in bad.json()["error"], bad.json()["error"])
    check("no targets refused", requests.post(f"{BASE}/api/progress/targets", json={"targets": {}}).status_code == 400)
    check("unknown band in targets refused", requests.post(f"{BASE}/api/progress/targets",
                                                         json={"targets": {"chess": 100}}).status_code == 400)
    ok = requests.post(f"{BASE}/api/progress/targets",
                       json={"targets": {"vocab": 300, "listening": 150, "reading": 200, "writing": 100}, "utc_offset": 420})
    got = {b["skill"]: b["progress"]["target"] for b in ok.json()["bands"]}
    check("all targets saved together", got == {"vocab": 300, "listening": 150, "reading": 200, "writing": 100}, got)

    # A target set weeks before any practice piles up nothing; tracking starts
    # in the week of the first points.
    cur.execute("INSERT INTO skill_goals (skill, week_start, target) VALUES ('listening', %s, 100)",
                (monday - timedelta(weeks=4),))
    lp = requests.get(f"{BASE}/api/progress", params={"skill": "listening", "utc_offset": 420}).json()
    check("no shortfall before the first points", lp["started"] is False and lp["carried"] == 0 and lp["past_weeks"] == [],
          {k: lp[k] for k in ("started", "carried")})
    at = datetime.combine(monday - timedelta(weeks=2) + timedelta(days=1), time(12), ICT)
    cur.execute("INSERT INTO practice_points (created_at, skill, word_id, mode, verdict, worth, points) "
                "VALUES (%s, 'listening', NULL, '__chart_test__', 'correct', 40, 40)", (at,))
    lp = requests.get(f"{BASE}/api/progress", params={"skill": "listening", "utc_offset": 420}).json()
    check("tracking starts the week of the first points", lp["started"] and lp["weeks_done"] == 2
          and lp["past_weeks"][-1]["points"] == 40, [(w["week_start"], w["points"], w["carried"]) for w in lp["past_weeks"]])
    check("and carries from there", lp["carried"] == 160, lp["carried"])  # 100-40=60, then 100+60-0=160
    cur.execute("DELETE FROM practice_points WHERE mode = '__chart_test__'")
    cur.execute("DELETE FROM skill_goals WHERE skill = 'listening' AND week_start = %s", (monday - timedelta(weeks=4),))

    seed()
    full = requests.get(f"{BASE}/api/progress/all", params={"utc_offset": 420}).json()["bands"][0]["progress"]
    check("tracking gets the 7 weeks before this one... (6 exist)", len(full["past_weeks"]) == 6, len(full["past_weeks"]))
    check("weeks met 4 of 6", (full["weeks_met"], full["weeks_done"]) == (4, 6), (full["weeks_met"], full["weeks_done"]))
    four = requests.get(f"{BASE}/api/progress", params={"skill": "vocab", "utc_offset": 420}).json()
    check("practice still gets 4 weeks by default", len(four["past_weeks"]) == 4, len(four["past_weeks"]))
    many = requests.get(f"{BASE}/api/progress", params={"skill": "vocab", "utc_offset": 420, "past_weeks": 99}).json()
    check("past_weeks is capped", len(many["past_weeks"]) == 6)

    # ---------- Browser ----------
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 1000}, timezone_id="Asia/Ho_Chi_Minh")
        ctx.route("**/*open-meteo.com/**", lambda r: r.abort())
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "ERR_FAILED" not in m.text
                and "status of 400" not in m.text else None)  # the bad target is refused on purpose

        for path in ("/", "/exam", "/practice", "/data"):
            page.goto(BASE + path, wait_until="networkidle")
            link = page.locator('.nav-link[href="/tracking"]')
            check(f"{path}: Tracking button in the top bar", link.count() == 1 and link.get_attribute("aria-current") is None)

        page.goto(BASE + "/tracking", wait_until="networkidle")
        check("Tracking button marked current", page.locator('.nav-link[href="/tracking"]').get_attribute("aria-current") == "page")
        tabs = page.locator('[role="tab"]')
        check("four band tiles", tabs.count() == 4, tabs.all_inner_texts())
        check("Vocab open by default", page.get_attribute("#band-tab-vocab", "aria-selected") == "true"
              and page.is_visible("#band-vocab") and not page.is_visible("#band-listening"))
        check("address names the band", page.evaluate("location.hash") == "#vocab")
        tile = page.inner_text("#band-tab-vocab")
        check("Vocab tile shows this week", f"{full['points']} / {full['due']}" in tile and "to go" in tile, tile.replace("\n", " | "))
        check("bands never practised say so", all("Not started yet" in page.inner_text(f"#band-tab-{s}")
                                                    for s in ("listening", "reading", "writing")))

        cols = page.locator("#band-vocab .history-col")
        check("8 week slots", cols.count() == 8, cols.count())
        classes = page.eval_on_selector_all("#band-vocab .history-col", "es => es.map(e => e.className.replace('history-col ', ''))")
        check("weeks coloured by result", classes == ["empty", "met", "short", "met", "short", "met", "met", "current"], classes)
        check("one goal line per tracked week", page.locator("#band-vocab .col-goal").count() == 7)
        check("only this week is labelled on its column", page.locator("#band-vocab .col-value").count() == 1
              and page.inner_text("#band-vocab .col-value") == str(full["points"]))
        check("note sums up the weeks", page.inner_text("#band-vocab .history-note") == "Target met in 4 of 6 finished weeks.")
        rows = page.eval_on_selector_all("#band-vocab .history-table tbody tr", "rs => rs.map(r => [...r.children].map(c => c.textContent))")
        check("table: 7 tracked weeks, newest first", len(rows) == 7 and rows[0][0].startswith("This week"), rows[:2])
        carried = [r for r in rows if "carried" in r[2]]
        check("table shows carry-over", carried and carried[0][2] == "300 (250 + 50 carried)", carried)
        label = cols.nth(2).get_attribute("aria-label")
        check("each column reads out its numbers", "180 of 300 points" in label and "120 short" in label, label)

        cols.nth(2).hover()
        tip = page.inner_text("#viz-tooltip")
        check("hover shows the week", page.is_visible("#viz-tooltip") and "180 of 300 points" in tip and "120 short" in tip, tip.replace("\n", " | "))
        page.mouse.move(5, 5)
        cols.nth(4).focus()
        check("keyboard focus shows it too", page.is_visible("#viz-tooltip") and "200 of 250" in page.inner_text("#viz-tooltip"))

        # Tabs: click, arrows, Home/End, and a link straight to a band.
        page.click("#band-tab-reading")
        check("click opens Reading", page.is_visible("#band-reading") and not page.is_visible("#band-vocab")
              and page.evaluate("location.hash") == "#reading")
        page.click("#band-tab-writing")
        check("Writing links to its practice", page.get_attribute("#band-writing .band-practice", "href") == "/writing")
        check("Writing's target panel says not started", "Not started" in page.inner_text("#band-writing .goal-status"))
        page.click("#band-tab-reading")
        page.keyboard.press("ArrowRight")
        check("ArrowRight moves to Writing", page.evaluate("document.activeElement.id") == "band-tab-writing"
              and page.is_visible("#band-writing"))
        page.keyboard.press("ArrowRight")
        check("and wraps round to Vocab", page.evaluate("document.activeElement.id") == "band-tab-vocab")
        page.keyboard.press("End")
        check("End goes to the last band", page.evaluate("document.activeElement.id") == "band-tab-writing")
        page.keyboard.press("Home")
        tabindexes = page.eval_on_selector_all('[role="tab"]', "ts => ts.map(t => t.tabIndex)")
        check("only the open tab is in the Tab order", tabindexes == [0, -1, -1, -1], tabindexes)

        page.goto(BASE + "/tracking#listening", wait_until="networkidle")
        check("/tracking#listening opens Listening", page.is_visible("#band-listening")
              and page.get_attribute("#band-tab-listening", "aria-selected") == "true")
        page.goto(BASE + "/tracking#nonsense", wait_until="networkidle")
        check("an unknown band falls back to Vocab", page.is_visible("#band-vocab"))

        # Changing the goal here keeps the whole history on screen.
        page.click("#band-vocab .goal-edit-btn")
        page.fill("#goal-input-vocab", "350")
        page.click("#goal-form-vocab button[type=submit]")
        page.wait_for_function("document.querySelector('#band-tab-vocab [data-tile=value]').textContent.endsWith('/ 350')")
        check("new goal shows on the tile", page.inner_text("#band-tab-vocab [data-tile=value]").endswith("/ 350"))
        check("chart keeps all 8 weeks after the change", page.locator("#band-vocab .history-col").count() == 8
              and page.locator("#band-vocab .history-col.met").count() == 4)
        check("form closes after saving", not page.is_visible("#goal-form-vocab"))

        # Set targets: every band at once.
        page.goto(BASE + "/tracking", wait_until="networkidle")
        page.click("#targets-btn")
        values = page.eval_on_selector_all("#targets-form input", "es => es.map(e => [e.name, e.value])")
        check("Set targets opens with the current targets", values == [["vocab", "350"], ["listening", "150"],
              ["reading", "200"], ["writing", "100"]], values)
        check("focus goes to the first target", page.evaluate("document.activeElement.id") == "target-vocab")
        page.fill("#target-writing", "4")
        page.fill("#target-reading", "260")
        page.click(".targets-save")
        page.wait_for_selector("#targets-error:not([hidden])")
        check("a bad target is explained", "Writing target from 10 to 5000" in page.inner_text("#targets-error"))
        check("and its box is marked and focused", page.get_attribute("#target-writing", "aria-invalid") == "true"
              and page.evaluate("document.activeElement.id") == "target-writing")
        check("nothing saved after the error", page.inner_text("#band-tab-reading [data-tile=value]").endswith("/ 200"))
        page.fill("#target-writing", "120")
        page.click(".targets-save")
        page.wait_for_selector("#targets-saved:not([hidden])")
        tiles = {s: page.inner_text(f"#band-tab-{s} [data-tile=value]") for s in ("vocab", "listening", "reading", "writing")}
        check("all tiles show the new targets", tiles == {"vocab": "-3 / 350", "listening": "0 / 150",
              "reading": "0 / 260", "writing": "0 / 120"} or all(v.endswith(t) for v, t in zip(tiles.values(),
              ("/ 350", "/ 150", "/ 260", "/ 120"))), tiles)
        check("form closes and says saved", not page.is_visible("#targets-form")
              and "Targets saved" in page.inner_text("#targets-saved"))
        page.click("#band-tab-reading")
        check("the band's own panel shows it too", page.inner_text('#band-reading [data-goal="due"]') == "260")
        page.click("#targets-btn")
        page.keyboard.press("Escape")
        check("Escape closes Set targets", not page.is_visible("#targets-form")
              and page.evaluate("document.activeElement.id") == "targets-btn")
        page.click("#targets-btn")
        page.click("#targets-cancel")
        check("Cancel closes it", not page.is_visible("#targets-form"))

        # Practice page: the same panel, with a link here.
        page.goto(BASE + "/practice", wait_until="networkidle")
        check("practice: Vocab goal loads", page.inner_text('.goal-panel[data-skill="vocab"] [data-goal="due"]') == "350")
        check("practice: earlier weeks list shows 4", page.locator(".goal-past li").count() == 4)
        more = page.locator(".goal-more")
        check("practice: link to all scores", more.count() == 1 and more.get_attribute("href") == "/tracking#vocab")

        # A marked answer updates the panel (AI mocked).
        fake = dict(four, points=four["points"] + 7, due=350, target=350, remaining=350 - four["points"] - 7)
        page.route("**/api/practice/exercises", lambda r: r.fulfill(json={"items": [{
            "word_id": 1, "word": "borrow", "sentence": "Can I ___ your pen?", "answer": "borrow",
            "hint": "", "explanation_vi": ""}]}))
        page.route("**/api/practice/check", lambda r: r.fulfill(json={
            "verdict": "correct", "source": "match", "corrected": "Can I borrow your pen?",
            "points": {"worth": 7, "change": 7}, "progress": fake}))
        page.click('input[name="mode"][value="fill_blank"]', force=True)
        page.click("#start-practice-btn")
        page.fill("#practice-answer", "borrow")
        page.click("#check-btn")
        page.wait_for_selector("#practice-feedback:not(.hidden)")
        page.wait_for_function(f"document.querySelector('.goal-panel[data-skill=vocab] [data-goal=points]').textContent === '{fake['points']}'", timeout=3000)
        shown = page.inner_text('.goal-panel[data-skill="vocab"] [data-goal="points"]')
        check("practice: a marked answer updates the goal", shown == str(fake["points"]), shown)
        check("practice: points badge", page.inner_text("#feedback-points") == "+7 points")

        page.goto(BASE + "/practice", wait_until="networkidle")
        page.click('.goal-panel[data-skill="vocab"] .goal-edit-btn')
        page.fill("#goal-input-vocab", "300")
        page.click("#goal-form-vocab button[type=submit]")
        page.wait_for_function("document.querySelector('.goal-panel [data-goal=due]').textContent === '300'")
        check("practice: goal can be changed there too", page.inner_text('.goal-panel [data-goal="due"]') == "300")

        check("no console errors", not errors, "; ".join(errors)[:300])
        b.close()
finally:
    restore()
    cur.execute("SELECT skill, week_start, target FROM skill_goals ORDER BY 1, 2")
    after = cur.fetchall()
    cur.execute("SELECT count(*), coalesce(sum(points), 0) FROM practice_points")
    check("database back as it was", after == goals_before and cur.fetchone() == points_before, after)

print(f"\n{sum(results)}/{len(results)} passed")
raise SystemExit(0 if results and all(results) else 1)
