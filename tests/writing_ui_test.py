"""Browser checks for the Writing page. Marking is mocked, so Gemini is never called."""
import json, os
from playwright.sync_api import sync_playwright

from common import BASE, FIXTURES
real = json.load(open(f"{FIXTURES}/real_check.json"))   # a real teacher's answer, captured once
results = []
def check(name, ok, detail=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))

TEXT = real["piece"]["text"]
sent = []

def mocked_check(route):
    body = json.loads(route.request.post_data)
    sent.append(body)
    piece = dict(real["piece"], id=500 + len(sent), kind=body["kind"], revision_of=body.get("revision_of"),
                 counted=not body.get("revision_of"), points=0 if body.get("revision_of") else 47)
    route.fulfill(json={"piece": piece, "waiting": False, "progress": dict(real["progress"], points=47, started=True)})

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 1000}, timezone_id="Asia/Ho_Chi_Minh")
    ctx.route("**/*open-meteo.com/**", lambda r: r.abort())
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "ERR_FAILED" not in m.text else None)
    pg.route("**/api/writing/check", mocked_check)
    pg.goto(BASE + "/writing", wait_until="networkidle")

    check("Writing tab current", pg.get_attribute('.practice-tabs a[href="/writing"]', "aria-current") == "page")
    check("three kinds to choose", pg.locator('input[name="kind"]').count() == 3)
    pg.click('input[name="kind"][value="diary"]', force=True)
    pg.wait_for_function("document.getElementById('task-kicker').textContent.includes('idea')")
    check("diary: today's idea shown", len(pg.inner_text("#task-title")) > 10)
    words = pg.eval_on_selector_all("#words-to-try-list li", "ls => ls.map(l => l.dataset.word)")
    check("diary: three saved words to try", len(words) == 3, words)
    check("no timer for a diary", not pg.is_visible("#writing-timer"))
    check("button off before writing", pg.is_disabled("#check-writing"))
    pg.fill("#writing-text", "Too short to mark.")
    check("still off under the minimum", pg.is_disabled("#check-writing") and "at least 40" in pg.inner_text("#word-count"))
    pg.fill("#writing-text", TEXT + f" I tried the word {words[0]} today.")
    check("on once long enough", pg.is_enabled("#check-writing"))
    check("a word to try lights up when used", "used" in pg.get_attribute(f'#words-to-try-list li[data-word="{words[0]}"]', "class"))
    first_idea = pg.inner_text("#task-title")
    pg.click("#task-another")
    pg.wait_for_timeout(600)
    check("another idea", pg.inner_text("#task-title") != first_idea)
    pg.fill("#writing-text", TEXT)

    # A draft survives a reload.
    pg.reload(wait_until="networkidle")
    pg.wait_for_timeout(600)
    check("draft restored after reload", pg.input_value("#writing-text") == TEXT)

    pg.click("#check-writing")
    pg.wait_for_selector("#result-panel:not(.hidden) .score-ring")
    check("sent the kind, idea, words and text", sent[-1]["kind"] == "diary" and sent[-1]["text"] == TEXT
          and sent[-1]["idea"] and len(sent[-1]["words_to_try"]) == 3 and sent[-1]["revision_of"] is None)
    pg.wait_for_timeout(1400)
    check("score ring counts to 47", pg.inner_text(".score-number") == "47")
    check("four criteria with bars", pg.locator(".criterion").count() == 4)
    check("+47 points chip", "+47 points" in pg.inner_text(".result-chips"))
    check("mistakes marked in the text", pg.locator(".marked-text mark").count() == len(real["piece"]["feedback"]["mistakes"]) - 1
          or pg.locator(".marked-text mark").count() >= 4)
    check("corrections listed", pg.locator(".mistake-list li").count() == len(real["piece"]["feedback"]["mistakes"]))
    check("better words", pg.locator(".upgrade-to").count() >= 2)
    check("words to try judged", pg.locator(".words-used li").count() == 2)
    check("Vietnamese summary marked as Vietnamese", pg.get_attribute(".summary-vi", "lang") == "vi")
    pg.click(".improved summary")
    check("improved version opens", pg.is_visible(".improved-text"))
    check("diary celebration", "Diary done for today" in pg.inner_text(".fx-achievements"))
    check("goal panel updated", pg.wait_for_function(
        "document.querySelector('.goal-panel[data-skill=writing] [data-goal=points]').textContent === '47'", timeout=3000) is not None)
    check("draft cleared after marking", pg.evaluate("Object.keys(localStorage).filter(k => k.startsWith('myvocab-writing-draft')).length") == 0)

    pg.click(".result-revise")
    check("revise: text back in the editor with a note", pg.input_value("#writing-text") == TEXT and pg.is_visible("#revising-note"))
    pg.fill("#writing-text", TEXT.replace("I go", "I went"))
    pg.click("#check-writing")
    pg.wait_for_selector("#result-panel:not(.hidden) .score-ring")
    check("revision sent with revision_of", sent[-1]["revision_of"] == 501)
    check("revision shows practice only", "Revision: practice only" in pg.inner_text(".result-chips"))

    # Task 1: chart and timer.
    pg.click('input[name="kind"][value="task1"]', force=True)
    pg.wait_for_selector(".task-chart:not(.hidden) .chart-svg, .task-chart:not(.hidden) .chart-table")
    check("task 1: chart drawn", pg.locator(".task-chart figcaption").count() == 1)
    check("task 1: instructions", "at least 150 words" in pg.inner_text("#task-instructions"))
    check("task 1: timer shows 20:00", pg.is_visible("#writing-timer") and "20:00" in pg.inner_text("#writing-timer"))
    pg.type("#writing-text", "The")
    pg.wait_for_timeout(2300)
    check("task 1: timer starts with typing", pg.inner_text("#writing-timer").strip().startswith("19:5"), pg.inner_text("#writing-timer"))
    tid = pg.evaluate("document.getElementById('task-title').textContent")
    pg.click("#task-another")
    pg.wait_for_timeout(600)
    check("task 1: another question", pg.inner_text("#task-title") != tid)
    pg.click('input[name="kind"][value="task2"]', force=True)
    pg.wait_for_function("document.getElementById('task-kicker').textContent.includes('Task 2')")
    check("task 2: 40 minutes", "40:00" in pg.inner_text("#writing-timer"))
    check("task 2: question type shown", any(t in pg.inner_text("#task-kicker").lower() for t in ("opinion", "discussion", "advantages", "problem", "two-part")))

    # The teacher unavailable: kept, grammar notes, then marked on retry.
    pg.unroute("**/api/writing/check")
    pg.route("**/api/writing/check", lambda r: r.fulfill(json={"waiting": True, "piece": {"id": 777, "kind": "task2"},
        "grammar": {"mistakes": [{"wrong": "goed", "right": "went", "why": "Irregular verb"}], "corrected": "x"},
        "progress": real["progress"]}))
    retried = []
    pg.route("**/api/writing/retry/777", lambda r: (retried.append(1), r.fulfill(json={"waiting": False,
        "piece": dict(real["piece"], id=777, kind="task2", band=6.0), "progress": real["progress"]}))[1])
    pg.fill("#writing-text", TEXT * 2)
    pg.click("#check-writing")
    pg.wait_for_selector(".waiting-note")
    check("waiting: explained, with grammar notes", "could not mark" in pg.inner_text("#result-panel") and "goed" in pg.inner_text("#result-panel"))
    pg.click("text=Mark it now")
    pg.wait_for_selector("#result-panel .score-ring")
    check("retry marks it", retried and "Band ≈ 6.0" in pg.inner_text(".result-chips"))

    # Past writing.
    pg.route("**/api/writing/history", lambda r: r.fulfill(json={"pieces": [
        {"id": 41, "created_at": "2026-10-06T10:00:00+00:00", "kind": "task2", "prompt": "Some people think...", "words": 260,
         "revision_of": None, "status": "scored", "score": 58, "band": 6.5, "counted": True, "points": 58},
        {"id": 40, "created_at": "2026-10-05T10:00:00+00:00", "kind": "diary", "prompt": "What did you eat today?", "words": 120,
         "revision_of": None, "status": "waiting", "score": None, "band": None, "counted": False, "points": 0}]}))
    pg.route("**/api/writing/piece/41", lambda r: r.fulfill(json=dict(real["piece"], id=41, kind="task2", score=58, band=6.5)))
    pg.reload(wait_until="networkidle")
    pg.wait_for_selector(".history-item")
    check("history lists pieces", pg.locator(".history-item").count() == 2 and "58/80" in pg.inner_text(".history-list"))
    check("waiting piece offers marking", "Not marked yet" in pg.inner_text(".history-item.waiting"))
    pg.click(".history-item.scored")
    pg.wait_for_selector("#result-panel:not(.hidden) .score-ring")
    pg.wait_for_timeout(1300)
    check("opening a past piece shows its marks", pg.inner_text(".score-number") == "58")
    check("no console errors", not errs, errs[:3])

    # Phone and Tracking.
    pg.set_viewport_size({"width": 390, "height": 844})
    pg.wait_for_timeout(300)
    check("phone: no sideways scroll", pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") == 0)
    tabs = pg.eval_on_selector(".practice-tabs", "e => [e.getBoundingClientRect().left, e.getBoundingClientRect().right]")
    check("phone: four practice tabs fit", tabs[0] >= 0 and tabs[1] <= 390, tabs)
    pg.set_viewport_size({"width": 1440, "height": 1000})
    pg.goto(BASE + "/tracking#writing", wait_until="networkidle")
    check("Tracking: Practise writing link", pg.get_attribute("#band-writing .band-practice", "href") == "/writing")
    check("Tracking: writing rules", "80 in all" in " ".join(pg.text_content("#band-writing .goal-rules").split()))
    b.close()
print(f"\n{sum(results)}/{len(results)} passed")
raise SystemExit(0 if results and all(results) else 1)
