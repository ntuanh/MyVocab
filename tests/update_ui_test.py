"""The Update button's states, with the app's answers mocked (no real update)."""
import json, os
from playwright.sync_api import sync_playwright
from common import BASE, SHOTS
results = []
def check(name, ok, detail=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)
RELEASE = {"tag": "v1.2", "name": "MyVocab v1.2", "published": "2026-10-07T10:00:00Z",
           "notes": "- Add a speaking practice\n- Make **exam** faster\n<script>alert(1)</script>"}
state = {"status": {"enabled": True, "current": "v1.1", "latest": RELEASE, "available": True, "progress": None}}
def status_route(route): route.fulfill(json=state["status"])
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    ctx.route("**/*open-meteo.com/**", lambda r: r.abort())
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "/", wait_until="networkidle")
    check("real dev clone: button hidden", pg.is_hidden("#update-box"))
    pg.route("**/api/update/status", status_route)
    pg.reload(wait_until="networkidle")
    pg.wait_for_selector("#update-box:not([hidden])")
    box = pg.eval_on_selector("#update-box", "e => e.getBoundingClientRect().toJSON()")
    check("small, bottom-left", box["left"] < 30 and box["bottom"] > 850 and box["width"] < 140, box)
    pg.click("#update-button")
    check("notes as a list, markdown and HTML not run", pg.locator("#update-notes li").count() == 2
          and "faster" in pg.inner_text("#update-notes") and "**" not in pg.inner_text("#update-notes")
          and pg.locator("#update-notes script").count() == 0)
    pg.screenshot(path=f"{SHOTS}/update-panel-desktop.png")
    pg.keyboard.press("Escape")
    check("Escape closes the panel", pg.is_hidden("#update-panel"))
    # A failed start shows the error and offers to try again.
    pg.route("**/api/update/start", lambda r: r.fulfill(status=409, json={"error": "An update is already running."}))
    pg.click("#update-button"); pg.click("#update-now")
    pg.wait_for_selector(".update-message.error")
    check("start refused: error shown, Try again", "already running" in pg.inner_text("#update-message") and pg.inner_text("#update-now") == "Try again")
    # Progress, a restart (app away), then the new version: reload and "Updated".
    pg.unroute("**/api/update/start")
    pg.route("**/api/update/start", lambda r: r.fulfill(status=202, json={"ok": True}))
    seq = [{"step": "download", "message": "Downloading MyVocab v1.2 ...", "tag": "v1.2", "at": 1e10}] * 2 + [None] * 2
    def moving(route):
        item = seq.pop(0) if seq else "new"
        if item is None: return route.abort()
        if item == "new":
            return route.fulfill(json={"enabled": True, "current": "v1.2", "latest": RELEASE, "available": False,
                                       "progress": {"step": "done", "message": "", "tag": "v1.2", "at": 1e10}})
        route.fulfill(json=dict(state["status"], progress=item))
    pg.unroute("**/api/update/status"); pg.route("**/api/update/status", moving)
    pg.click("#update-now")
    pg.wait_for_function("document.getElementById('update-message').textContent.includes('Downloading')", timeout=8000)
    check("progress shown while downloading", "Updating" in pg.inner_text("#update-button"))
    pg.wait_for_function("document.getElementById('update-message').textContent.includes('restarting')", timeout=10000)
    check("restart shown when the app is away", True)
    pg.wait_for_selector(".update-box.done", timeout=15000)
    check("after reload: 'Updated to v1.2'", "Updated to v1.2" in pg.inner_text("#update-button"))
    pg.screenshot(path=f"{SHOTS}/update-done.png")
    # Phone and dark.
    ph = b.new_context(viewport={"width": 390, "height": 844}, color_scheme="dark").new_page()
    ph.route("**/api/update/status", status_route)
    ph.goto(BASE + "/practice", wait_until="networkidle")
    ph.wait_for_selector("#update-box:not([hidden])"); ph.click("#update-button")
    panel = ph.eval_on_selector("#update-panel", "e => e.getBoundingClientRect().toJSON()")
    check("phone: panel fits the screen", panel["left"] >= 0 and panel["right"] <= 390 and panel["top"] >= 0, panel)
    check("phone: no sideways scroll", ph.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") == 0)
    ph.screenshot(path=f"{SHOTS}/update-phone-dark.png")
    check("no page errors", not errs, errs[:3])
    b.close()
print(f"\n{sum(results)}/{len(results)} passed")
raise SystemExit(0 if results and all(results) else 1)
