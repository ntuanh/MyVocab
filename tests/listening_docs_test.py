"""An episode's own files (worksheet, transcript, audio): the checks, privacy,
and adding, opening and deleting them on the Listening page. Removes its files."""
import json, os, tempfile, urllib.request, urllib.error
from common import BASE, ROOT, SHOTS
from playwright.sync_api import sync_playwright

results = []
def check(name, ok, detail=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)

EPISODE = json.load(open(os.path.join(ROOT, "data", "bbc_6min.json")))["episodes"][3]["id"]
PDF = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
       b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
       b"4 0 obj<</Length 44>>stream\nBT /F1 18 Tf 20 100 Td (Worksheet) Tj ET\nendstream endobj\n"
       b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
work = tempfile.mkdtemp(prefix="myvocab-docs-")
def make(name, data):
    path = os.path.join(work, name)
    open(path, "wb").write(data)
    return path
pdf_path = make("6 Minute English worksheet.pdf", PDF)
txt_path = make("transcript.txt", "Neil: Xin chào! Today we talk about heartbreak.".encode())
fake_path = make("not really.pdf", b"<html><script>alert(1)</script></html>")
page_path = make("page.html", b"<html></html>")

def docs_now():
    with urllib.request.urlopen(BASE + "/api/listening/docs") as r:
        return json.load(r)["docs"].get(EPISODE, [])

# --- Privacy: without the password, from another address, every route is closed.
from app import app  # noqa: E402  (the same code, run in-process to act as a visitor from elsewhere)
saved = os.environ.pop("MYVOCAB_LOCAL", None)
try:
    client = app.test_client()
    remote = {"REMOTE_ADDR": "203.0.113.9"}
    statuses = [client.get("/api/listening/docs", environ_base=remote).status_code,
                client.post("/api/listening/docs", data={"episode_id": EPISODE}, environ_base=remote).status_code,
                client.get("/api/listening/docs/1", environ_base=remote).status_code,
                client.delete("/api/listening/docs/1", environ_base=remote).status_code]
    check("online without the password: all four routes locked", statuses == [403] * 4, statuses)
    check("locked answer says so", client.get("/api/listening/docs", environ_base=remote).get_json().get("locked") is True)
finally:
    if saved is not None:
        os.environ["MYVOCAB_LOCAL"] = saved

before = {d["id"] for d in docs_now()}
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    ctx.route("**/*open-meteo.com/**", lambda r: r.abort())
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.goto(f"{BASE}/listening#{EPISODE}", wait_until="networkidle")
    pg.wait_for_selector("#episode-docs")
    check("files box under the video", pg.is_visible("#docs-add") and "Worksheet" in pg.inner_text("#docs-title"))

    # Two good files at once, then the ones that must be refused.
    pg.set_input_files("#docs-input", [pdf_path, txt_path])
    pg.wait_for_selector(".docs-status.gain", timeout=15000)
    check("two files added", "Added 2 files" in pg.inner_text("#docs-status"), pg.inner_text("#docs-status"))
    check("both listed with size", pg.locator(".doc-item").count() == len(before) + 2 and "KB" in pg.inner_text(".docs-list"))
    pg.set_input_files("#docs-input", [fake_path, page_path])
    pg.wait_for_selector(".docs-status.loss", timeout=15000)
    status = pg.inner_text("#docs-status")
    check("a fake PDF is refused", "does not look like a real PDF" in status, status)
    check("a web page is refused", "page.html: Add a PDF" in status, status)
    check("nothing extra kept", pg.locator(".doc-item").count() == len(before) + 2)

    # Opening: the PDF in the page; the text with its Vietnamese intact.
    new = [d for d in docs_now() if d["id"] not in before]
    pdf = next(d for d in new if d["filename"].endswith(".pdf"))
    txt = next(d for d in new if d["filename"].endswith(".txt"))
    pg.click(f'[data-open="{pdf["id"]}"]')
    check("Open shows the PDF in the page", pg.get_attribute(".docs-viewer iframe", "src") == f"/api/listening/docs/{pdf['id']}")
    pg.locator("#episode-docs").screenshot(path=f"{SHOTS}/listening-docs.png")
    pg.click(f'[data-open="{pdf["id"]}"]')
    check("Open again closes it", pg.is_hidden("#docs-viewer"))
    with urllib.request.urlopen(f"{BASE}/api/listening/docs/{pdf['id']}") as r:
        headers, body = r.headers, r.read()
    check("served as a PDF, inline, never sniffed", headers["Content-Type"] == "application/pdf"
          and headers["Content-Disposition"].startswith("inline") and headers["X-Content-Type-Options"] == "nosniff")
    check("the same bytes come back", body == PDF)
    with urllib.request.urlopen(f"{BASE}/api/listening/docs/{pdf['id']}?download=1") as r:
        check("Download sends it as a file with its name", r.headers["Content-Disposition"].startswith("attachment")
              and "worksheet.pdf" in r.headers["Content-Disposition"])
    with urllib.request.urlopen(f"{BASE}/api/listening/docs/{txt['id']}") as r:
        check("text keeps its Vietnamese", "Xin chào" in r.read().decode("utf-8") and "charset=utf-8" in r.headers["Content-Type"])

    # The episode card shows a paperclip; another episode's box is empty.
    count = len(before) + 2
    check("episode card shows a paperclip", pg.inner_text(f'.episode-card[data-id="{EPISODE}"] .episode-docs-count').strip() == str(count))
    other = pg.eval_on_selector(f'.episode-card:not([data-id="{EPISODE}"])', "e => e.dataset.id")
    pg.click(f'.episode-card[data-id="{other}"]')
    pg.wait_for_timeout(500)
    check("another episode does not show these files", "worksheet.pdf" not in pg.inner_text(".docs-list"))

    # Phone layout.
    pg.click(f'.episode-card[data-id="{EPISODE}"]')
    pg.wait_for_selector(".doc-item")
    pg.set_viewport_size({"width": 390, "height": 844})
    pg.wait_for_timeout(400)
    check("phone: no sideways scroll", pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") == 0)
    check("phone: actions fit", pg.eval_on_selector(".doc-actions", "e => e.getBoundingClientRect().right") <= 390)
    pg.locator("#episode-docs").screenshot(path=f"{SHOTS}/listening-docs-phone.png")
    pg.set_viewport_size({"width": 1280, "height": 900})

    # Deleting (the confirm is accepted).
    for doc in new:
        pg.click(f'[data-delete="{doc["id"]}"]')
        pg.wait_for_selector(f'[data-delete="{doc["id"]}"]', state="detached", timeout=10000)
    check("deleted files are gone", {d["id"] for d in docs_now()} == before)
    try:
        urllib.request.urlopen(f"{BASE}/api/listening/docs/{pdf['id']}")
        gone = False
    except urllib.error.HTTPError as e:
        gone = e.code == 404
    check("a deleted file answers 404", gone)
    check("no page errors", not errs, errs[:3])
    b.close()

print(f"\n{sum(results)}/{len(results)} passed")
raise SystemExit(0 if results and all(results) else 1)
