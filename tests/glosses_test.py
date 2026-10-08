"""Meanings of a word card's Similar and Family words: the lookup (with Wiktionary
replaced by canned answers) and the box in the browser (with /api/glosses mocked)."""
import json
from common import BASE, DATABASE_URL  # noqa: F401  (sets the database under test)
import psycopg2
from playwright.sync_api import sync_playwright

results = []
def check(name, ok, detail=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)

# --- The lookup ---------------------------------------------------------------
from myvocab import glosses as G  # noqa: E402

class Answer:
    def __init__(self, status, body=None):
        self.status_code, self._body = status, body
    def json(self):
        return self._body

asked = []
def fake_get(url, **kwargs):
    word = url.rsplit("/", 1)[1]
    asked.append(word)
    if word == "zzmissing":
        return Answer(404)
    if word == "zzbroken":
        raise G.requests.ConnectionError("offline")
    senses = [{"definition": "(obsolete) An old <i>sense</i>."},
              {"definition": "Able to <a href='/wiki/recover'>recover</a> quickly &amp; well."}]
    if word == "zzlong":
        senses = [{"definition": "word " * 80}]
    return Answer(200, {"en": [{"partOfSpeech": "Adjective", "definitions": senses}]})

TEST_WORDS = ["zzbouncy", "zzmissing", "zzbroken", "zzlong"]
conn = psycopg2.connect(DATABASE_URL); conn.autocommit = True; cur = conn.cursor()
from myvocab.database import initialize_schema  # noqa: E402
initialize_schema(cur)  # the backup may be older than the word_glosses table
cur.execute("DELETE FROM word_glosses WHERE word = ANY(%s)", (TEST_WORDS,))
cur.execute("SELECT lower(word), english_definition FROM words WHERE coalesce(english_definition,'') NOT IN ('', 'N/A') LIMIT 1")
saved_word, saved_definition = cur.fetchone()
real_get = G.requests.get
G.requests.get = fake_get
try:
    got = G.glosses(["ZZBouncy", "zzmissing", "zzbroken", "zzlong", saved_word, "<b>x</b>", "zzbouncy"])
    check("bad and repeated words are left out", list(got) == ["zzbouncy", "zzmissing", "zzbroken", "zzlong", saved_word], list(got))
    check("old senses skipped, HTML removed", got["zzbouncy"] and got["zzbouncy"]["definition"] == "Able to recover quickly & well.", got["zzbouncy"])
    check("part of speech kept", got["zzbouncy"]["part_of_speech"] == "adjective")
    check("a long definition is shortened", len(got["zzlong"]["definition"]) <= 221 and got["zzlong"]["definition"].endswith("…"))
    check("not found, and no answer, both give nothing", got["zzmissing"] is None and got["zzbroken"] is None)
    check("a saved word uses your own definition, without asking", got[saved_word]["source"] == "your words"
          and saved_word not in asked and got[saved_word]["definition"][:30] == saved_definition[:30])
    cur.execute("SELECT word, definition IS NULL FROM word_glosses WHERE word = ANY(%s) ORDER BY word", (TEST_WORDS,))
    kept = dict(cur.fetchall())
    check("found and not-found are kept; no answer is not", kept == {"zzbouncy": False, "zzlong": False, "zzmissing": True}, kept)
    asked.clear()
    again = G.glosses(["zzbouncy", "zzmissing", "zzbroken"])
    check("second time: only the unanswered word is asked again", asked == ["zzbroken"], asked)
    check("second time: same meaning from the cache", again["zzbouncy"] == got["zzbouncy"] and again["zzmissing"] is None)
finally:
    G.requests.get = real_get
    cur.execute("DELETE FROM word_glosses WHERE word = ANY(%s)", (TEST_WORDS,))

# --- The box ------------------------------------------------------------------
cur.execute("SELECT word, synonyms_json, family_words_json FROM words WHERE jsonb_array_length(coalesce(synonyms_json,'[]')) > 1 "
            "AND jsonb_array_length(coalesce(family_words_json,'[]')) > 1 ORDER BY word LIMIT 1")
word, synonyms, family = cur.fetchone()
chips = synonyms + family
canned = {w.lower(): {"definition": f"Meaning of {w}.", "part_of_speech": "noun", "source": "Wiktionary"} for w in chips}
canned[family[-1].lower()] = None  # one with nothing found
calls = []
def glosses_route(route):
    asked_words = json.loads(route.request.post_data)["words"]
    calls.append(asked_words)
    route.fulfill(json={"glosses": {w: canned.get(w) for w in asked_words}})

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    ctx.route("**/*open-meteo.com/**", lambda r: r.abort())
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/api/glosses", glosses_route)
    pg.goto(BASE + "/", wait_until="networkidle")
    pg.fill("#word-input", word)
    pg.press("#word-input", "Enter")
    pg.wait_for_selector("#synonym-list [data-gloss]")
    pg.wait_for_timeout(500)
    check("meanings asked for once, for every chip", len(calls) == 1 and sorted(calls[0]) == sorted({c.lower() for c in chips}), calls)
    check("chips can be focused and show a hint", pg.get_attribute("#synonym-list .tag", "tabindex") == "0"
          and "has-gloss" in pg.get_attribute("#synonym-list .tag", "class"))

    first = pg.locator("#synonym-list [data-gloss]").first
    first.hover()
    pg.wait_for_selector("#gloss-tip.shown")
    check("pointing shows the meaning", pg.inner_text(".gloss-def") == f"Meaning of {synonyms[0]}." and pg.inner_text(".gloss-word") == synonyms[0])
    check("with its part of speech and source", pg.inner_text(".gloss-pos") == "noun" and "Wiktionary" in pg.inner_text(".gloss-src"))
    tip_box, chip_box = pg.locator("#gloss-tip").bounding_box(), first.bounding_box()
    check("the box sits just above the chip", tip_box["y"] + tip_box["height"] <= chip_box["y"] and chip_box["y"] - (tip_box["y"] + tip_box["height"]) < 20)
    check("the chip points to the box", first.get_attribute("aria-describedby") == "gloss-tip")
    check("no new request when pointing", len(calls) == 1)
    pg.wait_for_timeout(300)  # the fade-in
    pg.screenshot(path=__import__("common").SHOTS + "/gloss-box.png")
    pg.mouse.move(5, 5)
    pg.wait_for_selector("#gloss-tip", state="hidden")
    check("moving away hides it", pg.is_hidden("#gloss-tip"))

    pg.locator("#family-list [data-gloss]").last.hover()
    pg.wait_for_selector("#gloss-tip.shown")
    check("a word with no meaning says so", "No short definition" in pg.inner_text(".gloss-def"))
    # A word the server leaves out is asked about once, never again and again.
    before_calls = len(calls)
    pg.evaluate("""() => { const t = document.createElement('span'); t.className = 'tag has-gloss'; t.tabIndex = 0;
                           t.dataset.gloss = 'route-omits-me'; t.textContent = 'route-omits-me';
                           document.getElementById('family-list').append(t); }""")
    canned.pop("route-omits-me", None)
    pg.route("**/api/glosses", lambda r: (calls.append(json.loads(r.request.post_data)["words"]), r.fulfill(json={"glosses": {}}))[1])
    pg.locator('[data-gloss="route-omits-me"]').hover()
    pg.wait_for_timeout(1200)
    check("a word left out of the answer is asked about once", len(calls) - before_calls == 1, calls[before_calls:])
    check("and then says there is no meaning", "No short definition" in pg.inner_text(".gloss-def"))
    pg.mouse.move(5, 5)

    pg.locator("#family-list [data-gloss]").first.focus()
    pg.wait_for_selector("#gloss-tip.shown")
    check("keyboard focus shows it", pg.inner_text(".gloss-word") == family[0])
    pg.keyboard.press("Escape")
    check("Escape hides it", pg.is_hidden("#gloss-tip"))

    # A phone: a long press opens it, touching elsewhere closes it, and it stays on screen.
    phone = b.new_context(viewport={"width": 360, "height": 740}, has_touch=True, is_mobile=True)
    phone.route("**/*open-meteo.com/**", lambda r: r.abort())
    ph = phone.new_page()
    ph.route("**/api/glosses", glosses_route)
    ph.goto(BASE + "/", wait_until="networkidle")
    ph.fill("#word-input", word)
    ph.press("#word-input", "Enter")
    ph.wait_for_selector("#family-list [data-gloss]")
    chip = ph.locator("#family-list [data-gloss]").first
    chip.scroll_into_view_if_needed()
    chip.dispatch_event("pointerdown", {"pointerType": "touch", "bubbles": True})
    ph.wait_for_timeout(250)
    check("phone: a short touch does not open it", ph.is_hidden("#gloss-tip"))
    ph.wait_for_timeout(450)
    check("phone: a long press opens it", ph.is_visible("#gloss-tip"))
    box = ph.locator("#gloss-tip").bounding_box()
    check("phone: the box stays on screen", box["x"] >= 0 and box["x"] + box["width"] <= 360, box)
    chip.dispatch_event("pointerup", {"pointerType": "touch", "bubbles": True})
    ph.locator("#word-title").dispatch_event("pointerdown", {"pointerType": "touch", "bubbles": True})
    check("phone: touching elsewhere closes it", ph.is_hidden("#gloss-tip"))
    check("no page errors", not errs, errs[:3])
    b.close()

print(f"\n{sum(results)}/{len(results)} passed")
raise SystemExit(0 if results and all(results) else 1)
