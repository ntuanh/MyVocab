"""Browser checks for the setup page during a real first install (tests/run_all.py --install)."""
import os, time
from playwright.sync_api import sync_playwright

# run_all.py --install runs this against a first install it starts in a temporary folder.
from common import SHOTS
INSTALL = os.environ["MYVOCAB_TEST_INSTALL_DIR"]       # the folder being set up
OPENED = os.environ["MYVOCAB_TEST_BROWSER_LOG"]        # where the stand-in browser writes each address
APP_URL = os.environ["MYVOCAB_TEST_INSTALL_URL"]       # where the installed app will answer
results = []
def check(name, ok, detail=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)

for _ in range(60):
    if os.path.exists(OPENED):
        break
    time.sleep(0.5)
url = open(OPENED).read().split()[0]
check("setup page opened by run.py", "?t=" in url, url)

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 900, "height": 1000})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_selector("#steps li")
    check("four steps listed (no icon step on Linux)", pg.locator("#steps li").count() == 4)
    check("links to get keys", pg.get_attribute(".key a[href*='aistudio.google.com/apikey']", "target") == "_blank"
          and pg.locator(".key a[href='https://www.pexels.com/api/']").count() == 1)

    # The bar moves while packages install.
    seen = set()
    for _ in range(120):
        seen.add(int(pg.inner_text("#percent").rstrip("%")))
        if "packages" in pg.inner_text("#now").lower() and max(seen) > 15:
            break
        time.sleep(0.5)
    pg.screenshot(path=f"{SHOTS}/setup-progress.png", full_page=True)
    check("bar shows installing packages", "Installing packages" in pg.inner_text("#now"), pg.inner_text("#now"))
    check("a step is done and one is running", pg.locator("#steps li.done").count() >= 1 and pg.locator("#steps li.now").count() == 1)

    # A wrong key is turned down and not saved; a POST without the secret is refused.
    pg.fill("#gemini", "AIzaThisIsNotARealKey123")
    pg.click("#save")
    pg.wait_for_selector("#gemini-status.bad")
    check("wrong Gemini key turned down", "did not accept" in pg.inner_text("#gemini-status"))
    check("not marked as answered", pg.is_hidden("#answered-note"))
    status = pg.evaluate("fetch('/skip', {method: 'POST', body: '{}'}).then(r => r.status)")
    check("POST without the secret refused", status == 403, status)
    check(".env untouched by the wrong key", "GEMINI_API_KEY=\n" in open(f"{INSTALL}/.env").read())

    pg.set_viewport_size({"width": 390, "height": 844})
    check("phone: no sideways scroll", pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") == 0)
    pg.set_viewport_size({"width": 900, "height": 1000})
    pg.fill("#gemini", "")
    pg.fill("#password", "my words 1")
    pg.click("#save")
    pg.wait_for_selector("#password-status.bad")
    check("password with spaces turned down", "without spaces" in pg.inner_text("#password-status"))
    pg.fill("#password", "mywords1")
    pg.click("#save")
    pg.wait_for_selector("#password-status.ok")
    check("password saved", "VIEW_DATA_PASSWORD=mywords1" in open(f"{INSTALL}/.env").read())
    check("answered note shown", pg.is_visible("#answered-note"))
    pg.wait_for_function("document.getElementById('password-saved').textContent.includes('saved')")
    check("saved password reported, not shown", "mywords1" not in pg.inner_text("#keys-card"))

    pg.wait_for_selector("#finish-card:not(.hidden)", timeout=300000)
    check("bar at 100%", pg.inner_text("#percent") == "100%")
    check("all steps done", pg.locator("#steps li.done").count() == 4)
    pg.screenshot(path=f"{SHOTS}/setup-done.png", full_page=True)
    check("next-time instructions", "MyVocab icon on your desktop" in pg.inner_text("#finish-card"))
    pg.wait_for_url(APP_URL + "/", timeout=15000)
    pg.wait_for_load_state("networkidle")
    check("sent on to the app", "MyVocab" in pg.title(), pg.title())
    stats = pg.evaluate("fetch('/api/today?utc_offset=-420').then(r => r.status)")
    check("app answers with its database", stats == 200, stats)
    check("no page errors", not errs, errs[:3])

    b.close()

opened = open(OPENED).read().split()
check("no second browser tab for the app", len(opened) == 1, opened)
print(f"\n{sum(results)}/{len(results)} passed")
raise SystemExit(0 if results and all(results) else 1)
