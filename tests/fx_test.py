"""Checks for the effects (fx.js and CSS) and the home page's Today section.
Gemini is never called: lookups and marking are mocked."""
import json, requests
from playwright.sync_api import sync_playwright

from common import BASE
results = []
def check(name, ok, detail=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))

INIT = """(([look, weather, effects]) => { const place = { name: 'Hà Nội', country: 'Vietnam', lat: 21.0285, lon: 105.8542 };
  localStorage.setItem('myvocab-sky', JSON.stringify({ look, effects, place }));
  localStorage.setItem('myvocab-sky-reading', JSON.stringify({ place: `${place.lat.toFixed(3)},${place.lon.toFixed(3)}`,
    fetchedAt: Date.now(), utcOffset: 25200, sunrise: 350, sunset: 1060, isDay: true, temperature: 27, label: 'Test', weather })); })(%s)"""

def page_for(b, look="morning", weather="clear", effects=True, motion="no-preference", size=(1440, 950)):
    ctx = b.new_context(viewport={"width": size[0], "height": size[1]}, reduced_motion=motion)
    ctx.add_init_script(INIT % json.dumps([look, weather, effects]))
    ctx.route("**/*open-meteo.com/**", lambda r: r.abort())
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "ERR_FAILED" not in m.text else None)
    return ctx, pg, errs

base_progress = requests.get(f"{BASE}/api/progress", params={"skill": "vocab", "utc_offset": 420}).json()

with sync_playwright() as p:
    b = p.chromium.launch()

    # Every page has the effects and nothing stays invisible after arriving.
    for path in ("/", "/practice", "/listening", "/reading", "/tracking", "/exam", "/data"):
        ctx, pg, errs = page_for(b)
        pg.goto(BASE + path, wait_until="networkidle")
        pg.wait_for_timeout(1500)
        check(f"{path}: effects loaded", pg.evaluate("typeof MyVocabFx === 'object'"))
        faint = pg.evaluate("""[...document.querySelectorAll('.panel, #practice-setup, #tracking-page, .band-tab, .plan-day, .episode-card')]
            .filter(e => e.offsetParent && +getComputedStyle(e).opacity < 0.99).length""")
        check(f"{path}: every card fully shown after arriving", faint == 0, faint)
        check(f"{path}: no console errors", not errs, errs[:2])
        ctx.close()

    # Reaching the weekly target is celebrated, once, when it happens; loading a page never celebrates.
    ctx, pg, errs = page_for(b)
    reached = dict(base_progress, points=310, due=300, target=300, remaining=0, started=True)
    pg.route("**/api/progress?skill=vocab*", lambda r: r.fulfill(json=dict(base_progress, points=290, remaining=10, started=True)))
    pg.route("**/api/practice/exercises", lambda r: r.fulfill(json={"items": [{
        "word_id": 1, "word": "borrow", "sentence": "Can I ___ your pen?", "answer": "borrow", "hint": "", "explanation_vi": ""}]}))
    pg.route("**/api/practice/check", lambda r: r.fulfill(json={"verdict": "correct", "source": "match",
        "corrected": "Can I borrow your pen?", "points": {"worth": 20, "change": 20}, "progress": reached}))
    pg.goto(BASE + "/practice", wait_until="networkidle")
    pg.wait_for_timeout(700)
    check("no celebration on page load", pg.locator(".fx-achievement").count() == 0)
    pg.click('input[name="mode"][value="fill_blank"]', force=True)
    pg.click("#start-practice-btn")
    pg.fill("#practice-answer", "borrow")
    pg.click("#check-btn")
    pg.wait_for_selector(".fx-achievement", timeout=3000)
    check("target reached: achievement card", "Weekly target reached" in pg.inner_text(".fx-achievement"))
    check("target reached: confetti canvas", pg.locator("canvas.fx-confetti").count() == 1)
    check("points float up from the badge", pg.locator(".fx-float.gain").count() >= 1)
    check("goal bar turns gold", "reached" in pg.get_attribute('.goal-panel[data-skill="vocab"]', "class"))
    pg.wait_for_timeout(5600)
    check("achievement card leaves by itself", pg.locator(".fx-achievement").count() == 0)
    check("no console errors on practice", not errs, errs[:2])
    ctx.close()

    # Reduced motion: no confetti or floating text, numbers jump, the card still appears.
    ctx, pg, errs = page_for(b, motion="reduce")
    pg.goto(BASE + "/", wait_until="networkidle")
    pg.evaluate("MyVocabFx.cannons(); MyVocabFx.floatText(document.body, '+5'); MyVocabFx.celebrate('Hi', 'there')")
    check("reduced motion: no confetti", pg.locator("canvas.fx-confetti").count() == 0)
    check("reduced motion: no floating text", pg.locator(".fx-float").count() == 0)
    check("reduced motion: card still shown", pg.locator(".fx-achievement").count() == 1)
    pg.evaluate("const s = document.createElement('span'); s.id = 'n'; s.textContent = '3'; document.body.append(s); MyVocabFx.countTo(s, 90)")
    check("reduced motion: numbers set at once", pg.inner_text("#n") == "90")
    anim = pg.eval_on_selector(".panel", "e => getComputedStyle(e).animationName")
    check("reduced motion: cards do not rise", anim == "none", anim)
    ctx.close()

    # Falling leaves: dry mornings and evenings with the animation switch on.
    for look, weather, effects, motion, want in (("morning", "clear", True, "no-preference", True),
                                                 ("evening", "partly", True, "no-preference", True),
                                                 ("night", "clear", True, "no-preference", False),
                                                 ("morning", "rain", True, "no-preference", False),
                                                 ("morning", "clear", False, "no-preference", False),
                                                 ("morning", "clear", True, "reduce", False)):
        ctx, pg, _ = page_for(b, look, weather, effects, motion)
        pg.goto(BASE + "/", wait_until="networkidle")
        name = pg.eval_on_selector(".falling-leaves i", "e => getComputedStyle(e).animationName")
        check(f"leaves {'fall' if want else 'stay'}: {look}/{weather}/fx {effects}/{motion}", (name == "fx-leaf") == want, name)
        ctx.close()

    # Home: Today section.
    ctx, pg, errs = page_for(b)
    pg.route("**/api/lookup", lambda r: r.fulfill(json={"status": "error", "message": "mocked"}))
    pg.goto(BASE + "/", wait_until="networkidle")
    today = requests.get(f"{BASE}/api/today", params={"utc_offset": 420}).json()
    check("word of the day shown", pg.inner_text("#wotd-word") == today["word"]["word"])
    check("the same word all day", requests.get(f"{BASE}/api/today", params={"utc_offset": 420}).json()["word"]["id"] == today["word"]["id"])
    check("four band rings", pg.locator(".glance-band").count() == 4)
    check("rings link to their band", pg.get_attribute(".glance-band >> nth=2", "href") == "/tracking#reading")
    check("meaning hidden until asked", not pg.is_visible("#wotd-meaning"))
    pg.click("#wotd-reveal")
    check("meaning revealed", pg.is_visible("#wotd-meaning") and pg.get_attribute("#wotd-reveal", "aria-expanded") == "true")
    with pg.expect_request("**/api/lookup") as req:
        pg.click("#wotd-open")
    check("Open the word card looks the word up", today["word"]["word"] in (req.value.post_data or ""))
    check("home: no console errors", not errs, errs[:2])
    for w in (390, 768):
        pg.set_viewport_size({"width": w, "height": 900})
        check(f"home {w}px: no sideways scroll", pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") == 0)
    ctx.close()
    b.close()

print(f"\n{sum(results)}/{len(results)} passed")
raise SystemExit(0 if results and all(results) else 1)
