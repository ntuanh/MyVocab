"""Checks for the Listening page. Everything it saves is removed afterwards."""
import json, os, threading
import psycopg2, requests
from playwright.sync_api import sync_playwright

from common import BASE
results = []
def check(name, ok, detail=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))

conn = psycopg2.connect(os.environ["DATABASE_URL"]); conn.autocommit = True; cur = conn.cursor()
requests.get(f"{BASE}/api/listening/episodes")  # makes sure the table exists
cur.execute("SELECT coalesce(max(id), 0) FROM practice_points"); pp_max = cur.fetchone()[0]
cur.execute("SELECT coalesce(max(id), 0) FROM listening_attempts"); la_max = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM listening_attempts"); la_before = cur.fetchone()[0]

def post(ep, c, t):
    return requests.post(f"{BASE}/api/listening/score", json={"episode_id": ep, "correct": c, "total": t, "utc_offset": 420})

try:
    eps = requests.get(f"{BASE}/api/listening/episodes").json()["episodes"]
    check("50 episodes", len(eps) == 50 and len({e["id"] for e in eps}) == 50)
    check("each has a title, length and topic", all(e["title"] and e["duration"] and e["topic"] for e in eps))
    a, b, c, d = eps[10]["id"], eps[11]["id"], eps[12]["id"], eps[13]["id"]
    for args, why in [(("nope", 1, 2), "not in the list"), ((a, 1, 0), "1 to 30"), ((a, 7, 6), "from 0 to 6"),
                      ((a, "x", 6), "two whole numbers"), ((a, 1, 31), "1 to 30")]:
        r = post(*args)
        check(f"refused: {args}", r.status_code == 400 and why in r.json()["error"], r.json().get("error"))
    cur.execute("SELECT count(*) FROM listening_attempts"); check("nothing saved by refused scores", cur.fetchone()[0] == la_before)

    before = requests.get(f"{BASE}/api/progress", params={"skill": "listening", "utc_offset": 420}).json()["points"]
    r = post(a, 5, 6).json()
    check("first score counts: 5/6 = +18", r["counted"] and r["points"] == 18, r)
    check("listening progress rises by 18", r["progress"]["points"] == before + 18 and r["progress"]["started"],
          (before, r["progress"]["points"]))
    r2 = post(a, 6, 6).json()
    check("second score is practice only", not r2["counted"] and r2["points"] == 0 and r2["progress"]["points"] == before + 18, r2)
    r3 = post(b, 0, 6).json()
    check("0/6 loses 12", r3["counted"] and r3["points"] == -12)
    ep = {e["id"]: e for e in requests.get(f"{BASE}/api/listening/episodes").json()["episodes"]}
    s = ep[a]["scores"]
    check("episode keeps first, best and tries", s["first"] == {"correct": 5, "total": 6, "points": 18}
          and s["best"]["correct"] == 6 and s["tries"] == 2, s)

    # Two saves at once for a new episode: only one may count.
    out = []
    ts = [threading.Thread(target=lambda: out.append(post(c, 4, 5).json())) for _ in range(2)]
    [t.start() for t in ts]; [t.join() for t in ts]
    check("two quick saves count once", sorted(x["counted"] for x in out) == [False, True], [x["counted"] for x in out])

    tr = requests.get(f"{BASE}/api/progress/all", params={"utc_offset": 420}).json()["bands"]
    lb = next(x for x in tr if x["skill"] == "listening")
    check("Tracking: listening has a practice now", lb["has_practice"] and lb["progress"]["points"] == before + 18 - 12 + 14,
          lb["progress"]["points"])

    with sync_playwright() as p:
        br = p.chromium.launch()
        ctx = br.new_context(viewport={"width": 1440, "height": 1000}, timezone_id="Asia/Ho_Chi_Minh")
        ctx.route("**/*open-meteo.com/**", lambda r: r.abort())
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "youtube" not in m.text.lower()
              and "ERR_FAILED" not in m.text and "status of 400" not in m.text else None)
        pg.goto(BASE + "/listening", wait_until="networkidle")
        check("50 cards", pg.locator(".episode-card").count() == 50)
        check("Practice is current in the top bar", pg.get_attribute('.nav-link[href="/practice"]', "aria-current") == "page")
        check("Listening tab is current", pg.get_attribute('.practice-tabs a[href="/listening"]', "aria-current") == "page")
        first_todo = next(e for e in eps if e["id"] not in (a, b, c))
        check("opens the newest episode still to do", pg.inner_text("#episode-title") == first_todo["title"])
        check("counts: 3 done", pg.inner_text('[data-count="done"]') == "3" and pg.inner_text('[data-count="todo"]') == "47")
        pg.click('[data-filter="done"]')
        check("Done filter shows the 3", pg.locator(".episode-card").count() == 3)
        pg.click('[data-filter="all"]')
        pg.select_option("#topic-filter", "Sport")
        check("topic filter", pg.locator(".episode-card").count() == sum(e["topic"] == "Sport" for e in eps))
        pg.select_option("#topic-filter", "")

        pg.click(f'.episode-card[data-id="{d}"]')
        check("choosing a card opens it", pg.inner_text("#episode-title") == ep[d]["title"]
              and d in pg.get_attribute("#video-frame iframe", "src") and pg.evaluate("location.hash") == f"#{d}")
        check("YouTube link points at the episode", pg.get_attribute("#episode-youtube", "href").endswith(d))
        pg.fill("#score-correct", "4"); pg.fill("#score-total", "6")
        check("preview shows the points", pg.inner_text("#score-preview") == "4/6 is worth +12 points.", pg.inner_text("#score-preview"))
        pg.click("#score-save")
        pg.wait_for_selector("#score-result:not(.hidden)")
        check("saved message", "Saved: 4/6, +12 points" in pg.inner_text("#score-result"), pg.inner_text("#score-result"))
        check("card shows done", "✓ 4/6" in pg.inner_text(f'.episode-card[data-id="{d}"]'))
        check("history line", "First score 4/6 (+12 points)" in pg.inner_text("#score-history"))
        want = str(before + 18 - 12 + 14 + 12)
        pg.wait_for_function(f"document.querySelector('.goal-panel[data-skill=listening] [data-goal=points]').textContent === '{want}'", timeout=3000)
        check("goal panel updated", pg.inner_text('.goal-panel[data-skill="listening"] [data-goal="points"]') == want)
        pg.fill("#score-correct", "6")
        check("preview says practice only now", "practice only" in pg.inner_text("#score-preview"))
        pg.fill("#score-correct", "9")
        pg.click("#score-save")
        pg.wait_for_selector("#score-result.loss")
        check("bad score explained", "from 0 to 6" in pg.inner_text("#score-result"))

        pg.goto(BASE + f"/listening#{b}", wait_until="networkidle")
        check("/listening#id opens that episode", pg.inner_text("#episode-title") == ep[b]["title"])
        pg.goto(BASE + "/tracking#listening", wait_until="networkidle")
        check("Tracking: Practise listening link", pg.get_attribute("#band-listening .band-practice", "href") == "/listening")
        check("Tracking: listening has rules", "Each right answer wins 4 points" in pg.text_content("#band-listening .goal-rules"))
        pg.goto(BASE + "/practice", wait_until="networkidle")
        check("Practice page has the tabs", pg.get_attribute('.practice-tabs a[href="/practice"]', "aria-current") == "page")
        for w in (390, 768, 1024):
            pg.set_viewport_size({"width": w, "height": 900})
            pg.goto(BASE + "/listening", wait_until="networkidle")
            check(f"{w}px: no sideways scroll", pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") == 0)
        check("no console errors", not errs, errs[:3])
        br.close()
finally:
    cur.execute("DELETE FROM listening_attempts WHERE id > %s", (la_max,))
    cur.execute("DELETE FROM practice_points WHERE id > %s AND skill = 'listening'", (pp_max,))
    cur.execute("SELECT count(*) FROM listening_attempts"); la_after = cur.fetchone()[0]
    cur.execute("SELECT coalesce(max(id),0) FROM practice_points WHERE skill='listening'")
    check("database back as it was", la_after == la_before and cur.fetchone()[0] <= pp_max)
print(f"\n{sum(results)}/{len(results)} passed")
raise SystemExit(0 if results and all(results) else 1)
