"""Start MyVocab on this computer, on Linux, macOS or Windows:

    python run.py           (Windows: MyVocab-Setup.bat the first time, then the desktop icon;
                             Linux/macOS: ./run.sh)
    python run.py --setup   show the setup page again, to change your keys

The first run sets everything up: a Python environment (.venv) with the exact
package versions, a .env file, and a database on this computer. On a new
computer, it loads your newest backup from backup/ into that database. A setup
page opens in the browser. It shows the progress and asks for your Gemini and
Pexels keys. After that, it just starts the app and opens it in the browser.
If MyVocab is already running, it only opens the browser. Stop it with Ctrl+C
or by closing the window.

    PORT=5000         the port to use
    OPEN_BROWSER=0    do not open the browser (and no setup page)
"""
import hashlib
import http.server
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
WINDOWS = os.name == "nt"
VENV = os.path.join(ROOT, ".venv")
PYTHON = os.path.join(VENV, "Scripts", "python.exe") if WINDOWS else os.path.join(VENV, "bin", "python")
PORT = os.environ.get("PORT", "5000")
URL = f"http://127.0.0.1:{PORT}"
LOCAL_DB_PORT = os.environ.get("MYVOCAB_DB_PORT", "5433")  # tools/local_db.py reads the same setting
LOCAL_DB_URL = f"postgresql://myvocab@127.0.0.1:{LOCAL_DB_PORT}/myvocab"
REQUIREMENTS = ["requirements.txt", "requirements-local.txt"]
OPEN_BROWSER = os.environ.get("OPEN_BROWSER", "1") != "0"
UPDATE_DIR = os.path.join(ROOT, ".update")  # the Update button's requests (updates.py, tools/update.py)
EXPECTED_PACKAGES = 19  # what requirements-local.txt pulls in with everything those need (18, +colorama on Windows)

# The setup, as the progress bar shows it: (name, what the learner reads, share of the bar).
STEPS = [
    ("python", "Preparing Python", 8),
    ("packages", "Installing packages", 60),
    ("database", "Preparing your database", 17),
    ("shortcut", "Adding the MyVocab icon", 5),
    ("start", "Starting MyVocab", 10),
]
if not WINDOWS:
    STEPS = [step for step in STEPS if step[0] != "shortcut"]  # made by hand there: tools/make_shortcut.py


def say(message):
    print(f"[MyVocab] {message}", flush=True)


def answering(url=URL, timeout=1.5):
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False


def open_browser_when_ready():
    if not OPEN_BROWSER:
        return
    def wait():
        for _ in range(60):
            if answering():
                webbrowser.open(URL)
                return
            time.sleep(1)
    threading.Thread(target=wait, daemon=True).start()


class Progress:
    """How far the start-up is. It is drawn as a bar in this window and read by the setup page."""

    def __init__(self):
        self.lock = threading.Lock()
        self.current, self.fraction, self.detail = None, 0.0, ""
        self.finished = set()
        self.error = None
        self.ready = False  # the app answers
        self.bar = sys.stdout.isatty()

    def begin(self, name, detail=""):
        with self.lock:
            if self.current:
                self.finished.add(self.current)
            self.current, self.fraction, self.detail = name, 0.0, detail
        self.draw()

    def update(self, fraction, detail=None):
        with self.lock:
            self.fraction = max(self.fraction, min(fraction, 1.0))
            if detail is not None:
                self.detail = detail
        self.draw()

    def done(self):
        with self.lock:
            self.finished = {name for name, _, _ in STEPS}
            self.current, self.detail, self.ready = None, "", True
        self.draw()
        if self.bar:
            print(flush=True)

    def fail(self, message):
        with self.lock:
            self.error = message
        if self.bar:
            print(flush=True)

    def percent(self):
        total = sum(weight for _, _, weight in STEPS)
        got = sum(weight for name, _, weight in STEPS if name in self.finished)
        got += sum(weight for name, _, weight in STEPS if name == self.current) * self.fraction
        return round(100 * got / total)

    def snapshot(self):
        with self.lock:
            return {
                "percent": self.percent(),
                "steps": [{"name": name, "label": label,
                           "state": "done" if name in self.finished else "now" if name == self.current else "todo"}
                          for name, label, _ in STEPS],
                "detail": self.detail,
                "error": self.error,
                "ready": self.ready,
                "app_url": URL,
            }

    def draw(self):
        with self.lock:
            label = next((label for name, label, _ in STEPS if name == self.current), "Ready")
            line_text = label + (f": {self.detail}" if self.detail else "")
            percent = self.percent()
        if not self.bar:
            return
        filled = percent * 24 // 100
        line = f"[MyVocab] [{'#' * filled}{'.' * (24 - filled)}] {percent:3d}%  {line_text}"
        print("\r" + line[:79].ljust(79), end="", flush=True)


def run_quietly(command, progress, detail=None):
    """Runs a command with its output kept back (the bar stays tidy). On failure
    the output is printed and the start-up stops."""
    result = subprocess.run(command, capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip()
        progress.fail(detail or "A step failed.")
        print(output, flush=True)
        sys.exit(detail or "A step failed; see above.")
    return result


def setup_python(progress):
    """The .venv with exactly the packages in the requirements files, reinstalled
    when they change. Returns True on the very first run."""
    progress.begin("python")
    if sys.version_info < (3, 9):
        progress.fail("Python is too old.")
        sys.exit("MyVocab needs Python 3.9 or newer (3.12 is best).")
    first = not os.path.exists(PYTHON)
    if first:
        progress.update(0.2, f"Python {sys.version.split()[0]} in .venv")
        run_quietly([sys.executable, "-m", "venv", VENV], progress, "Python could not make the .venv folder.")
    progress.begin("packages")
    digest = hashlib.sha256(b"".join(open(f, "rb").read() for f in REQUIREMENTS)).hexdigest()
    marker = os.path.join(VENV, ".installed")
    if not os.path.exists(marker) or open(marker).read().strip() != digest:
        install_packages(progress)
        with open(marker, "w") as f:
            f.write(digest)
    return first


def install_packages(progress):
    """pip install, with its output read line by line to move the bar along."""
    progress.update(0.01, "Starting ...")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    pip = subprocess.Popen([PYTHON, "-m", "pip", "install", "--disable-pip-version-check", "--progress-bar", "off",
                            "-r", "requirements-local.txt"],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                           errors="replace", env=env)
    log, seen = [], 0
    installing = threading.Event()

    def creep():
        # pip says nothing while it installs, so the bar inches on towards 97%.
        while installing.is_set() and pip.poll() is None:
            progress.update(progress.fraction + (0.97 - progress.fraction) * 0.06)
            time.sleep(1)
    for line in pip.stdout:
        log.append(line)
        words = line.split()
        if line.startswith(("Collecting ", "Requirement already satisfied: ")):
            seen += 1
            name = words[1] if line.startswith("Collecting") else words[3]
            progress.update(0.7 * min(seen / EXPECTED_PACKAGES, 1), f"getting {name.split('==')[0]}")
        elif line.startswith("Installing collected packages") and not installing.is_set():
            progress.update(0.72, "installing (the longest part, about a minute)")
            installing.set()
            threading.Thread(target=creep, daemon=True).start()
    installing.clear()
    if pip.wait() != 0:
        progress.fail("Installing packages failed.")
        print("".join(log[-25:]), flush=True)
        venv_version = subprocess.run([PYTHON, "-c", "import sys; print(sys.version_info[:2] >= (3, 13))"],
                                      capture_output=True, text=True).stdout.strip()
        hint = ("\nThe built-in database package has no build for Python 3.13 or newer yet. Install Python 3.12 "
                "(https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe on Windows), delete the .venv folder, and run again."
                if venv_version == "True" else "\nCheck the internet connection and run again.")
        sys.exit("Installing packages failed." + hint)
    progress.update(1.0, "done")


def read_env():
    values = {}
    with open(".env", encoding="utf-8") as f:
        for line in f:
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def set_env(key, value):
    """Sets KEY=value in .env, on its existing line (keeping that line's ending) or on a new one."""
    with open(".env", encoding="utf-8", newline="") as f:
        lines = f.read().splitlines(keepends=True)
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("#") and line.split("=", 1)[0].strip() == key and "=" in line:
            lines[i] = f"{key}={value}" + line[len(line.rstrip("\r\n")):]
            break
    else:
        lines.append(f"\n{key}={value}\n")
    with open(".env", "w", encoding="utf-8", newline="") as f:
        f.write("".join(lines))


def setup_env():
    """A .env file; with no database set, the database on this computer is used,
    and a missing secret key is made up (it only signs this computer's cookies)."""
    if not os.path.exists(".env"):
        shutil.copy(".env.example", ".env")
    env = read_env()
    if not env.get("DATABASE_URL"):
        set_env("DATABASE_URL", LOCAL_DB_URL)
        env["DATABASE_URL"] = LOCAL_DB_URL
    if not env.get("FLASK_SECRET_KEY"):
        set_env("FLASK_SECRET_KEY", secrets.token_hex(32))
    return env


# Where files were before v1.2 sorted them into folders. An update only adds
# files, so an installed copy that came from an older version still has these.
OLD_LAYOUT = [
    "database.py", "handle_request.py", "practice.py", "listening.py", "reading.py", "writing.py", "updates.py",
    "static/*.js", "static/*.css", "static/*.svg", "static/favicon.png",  # static/favicon.ico: old desktop icons use it
    "templates/_*.html",
    "tools/seed_words.py", "tools/fill_missing.py", "tools/draw_trees.py", "tools/release.py", "tools/local_db.sh",
    "images/*.png",
]


def tidy_old_layout():
    """Removes the old copies once the new layout is in. Never in a git clone: git moved those files itself."""
    if os.path.isdir(os.path.join(ROOT, ".git")) or not os.path.exists(os.path.join(ROOT, "myvocab", "__init__.py")):
        return
    import glob
    for pattern in OLD_LAYOUT:
        for path in glob.glob(os.path.join(ROOT, pattern)):
            os.remove(path)
    for folder in ("images", "__pycache__"):
        shutil.rmtree(os.path.join(ROOT, folder), ignore_errors=True)


def local_db(*args):
    return subprocess.run([PYTHON, os.path.join("tools", "local_db.py"), *args], capture_output=True, text=True,
                          errors="replace")


def start_local_db(progress):
    """Starts the database on this computer. Returns True if this run started it."""
    progress.begin("database", "checking")
    if local_db("status").stdout.startswith("running"):
        return False
    created = not os.path.exists(os.path.join(".localdb", "PG_VERSION"))
    progress.update(0.2, "creating it (only the first time)" if created else "starting")
    started = local_db("start")
    if started.returncode != 0:
        progress.fail("The database could not start.")
        print(started.stdout + started.stderr, flush=True)
        sys.exit("The database could not start. See .localdb/server.log.")
    if created:
        backups = sorted((os.path.join("backup", f) for f in os.listdir("backup") if f.endswith(".sql")),
                         key=os.path.getmtime) if os.path.isdir("backup") else []
        if backups:
            progress.update(0.6, f"loading your backup {os.path.basename(backups[-1])}")
            restored = local_db("restore", backups[-1])
            if restored.returncode != 0:
                print("\n" + (restored.stdout + restored.stderr).strip(), flush=True)
                say("Your backup could not be loaded; MyVocab starts with an empty database.")
    progress.update(1.0, "")
    return True


def load_word_pack(progress):
    """Words from data/word_pack.json (tools/word_pack.py): all of them on a new
    computer, and after an update only the words added since. It runs only when
    the pack is not the one loaded last time."""
    pack = os.path.join(ROOT, "data", "word_pack.json")
    if not os.path.exists(pack):
        return
    with open(pack, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    try:
        with open(os.path.join(ROOT, ".wordpack"), encoding="utf-8") as f:
            if f.readline().strip() == f"# {digest}":
                return
    except OSError:
        pass
    if progress.current != "database":
        progress.begin("database")
    progress.update(0.8, "adding the words from the word pack")
    loaded = subprocess.run([PYTHON, os.path.join("tools", "word_pack.py"), "import"], capture_output=True,
                            text=True, errors="replace")
    if loaded.returncode != 0:
        print("\n" + (loaded.stdout + loaded.stderr).strip(), flush=True)
        say("The word pack could not be loaded; MyVocab starts without those words.")
    progress.update(1.0, "")


def make_shortcut(progress):
    progress.begin("shortcut", "on the desktop and in the Start menu")
    made = subprocess.run([PYTHON, os.path.join("tools", "make_shortcut.py")], capture_output=True, text=True,
                          errors="replace")
    if made.returncode != 0:
        print("\n" + (made.stdout + made.stderr).strip(), flush=True)
        say("The desktop icon could not be made; double-click run.bat instead.")


# --- The setup page -------------------------------------------------------------

def check_key(kind, key):
    """Asks the service whether it accepts the key: 'ok', 'bad', or 'unknown' (no answer)."""
    if kind == "gemini":
        request = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1",
                                         headers={"x-goog-api-key": key})
    else:
        request = urllib.request.Request("https://api.pexels.com/v1/search?query=tree&per_page=1",
                                         headers={"Authorization": key, "User-Agent": "MyVocab-setup"})
    try:
        urllib.request.urlopen(request, timeout=12)
        return "ok"
    except urllib.error.HTTPError as error:
        return "bad" if error.code in (400, 401, 403) else "unknown"
    except Exception:
        return "unknown"


def masked(value):
    return (value[:4] + "…" + value[-3:]) if len(value) > 10 else ("set" if value else "")


SETUP_PAGE = None


class SetupPage:
    """A page on this computer only (a random port and a secret in its address)
    that shows the progress and takes the keys, so nobody has to open .env."""
    FIELDS = {"gemini": "GEMINI_API_KEY", "pexels": "PEXELS_API_KEY", "password": "VIEW_DATA_PASSWORD"}

    def __init__(self, progress):
        self.progress = progress
        self.token = secrets.token_urlsafe(16)
        self.answered = False
        self.last_seen = time.time()
        page = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def reply(self, status, body, kind="application/json"):
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", kind)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                path = self.path.split("?")[0]
                if path == "/":
                    html = open(os.path.join(ROOT, "tools", "setup.html"), encoding="utf-8").read()
                    self.reply(200, html.replace("{{TOKEN}}", page.token).encode(), "text/html; charset=utf-8")
                elif path == "/state":
                    page.last_seen = time.time()
                    self.reply(200, dict(page.progress.snapshot(), keys=page.keys(), answered=page.answered))
                elif path in ("/static/img/favicon.png", "/static/img/scene-morning.svg"):
                    kind = "image/png" if path.endswith(".png") else "image/svg+xml"
                    self.reply(200, open(os.path.join(ROOT, "static", "img", os.path.basename(path)), "rb").read(), kind)
                else:
                    self.reply(404, {"error": "not found"})

            def do_POST(self):
                if self.headers.get("X-Setup-Token") != page.token:
                    return self.reply(403, {"error": "forbidden"})
                length = int(self.headers.get("Content-Length") or 0)
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                except ValueError:
                    return self.reply(400, {"error": "bad request"})
                if self.path == "/keys":
                    self.reply(200, page.save_keys(body))
                elif self.path == "/skip":
                    page.answered = True
                    self.reply(200, {"ok": True})
                else:
                    self.reply(404, {"error": "not found"})

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def keys(self):
        env = read_env() if os.path.exists(".env") else {}
        return {field: masked(env.get(name, "")) for field, name in self.FIELDS.items()}

    def save_keys(self, body):
        """Checks each new key with its service and saves the ones that are not turned down."""
        results = {}
        for field, name in self.FIELDS.items():
            value = str(body.get(field) or "").strip()
            if not value:
                continue
            if any(c.isspace() for c in value) or len(value) > 200:
                results[field] = "bad"
                continue
            results[field] = "ok" if field == "password" else check_key(field, value)
            if results[field] != "bad":
                set_env(name, value)
        if "bad" not in results.values():
            self.answered = True
        return {"results": results, "keys": self.keys(), "answered": self.answered}

    def is_open(self):
        return time.time() - self.last_seen < 20

    def wait_for_keys(self):
        while not self.answered and self.is_open():
            time.sleep(0.3)

    def close_later(self):
        def close():
            time.sleep(20)  # time for the page to see the app is up
            self.server.shutdown()
        threading.Thread(target=close, daemon=True).start()


# --- Start-up --------------------------------------------------------------------

def pass_on_log(app, progress):
    """The app's log, shown in this window once the bar is done (all of it, if it fails to start)."""
    held = []
    for line in app.stdout:
        if progress.ready or progress.error:
            if held:
                print("".join(held), end="", flush=True)
                held.clear()
            print(line, end="", flush=True)
        else:
            held.append(line)
    if held:
        print("\n" + "".join(held), end="", flush=True)



def main():
    show_setup = "--setup" in sys.argv[1:]
    if answering():
        if show_setup:
            say("MyVocab is already running. Close its window first, then run the setup again to change your keys.")
        else:
            say(f"Already running at {URL}; opening it.")
        if OPEN_BROWSER:
            webbrowser.open(URL)
        return 0

    # Closing the terminal window sends SIGHUP: stop cleanly, as Ctrl+C does.
    def stop(*_):
        raise KeyboardInterrupt
    for name in ("SIGHUP", "SIGTERM"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), stop)

    tidy_old_layout()
    progress = Progress()
    first_time = not os.path.exists(PYTHON) or not os.path.exists(".env")
    global SETUP_PAGE
    page = None
    if (show_setup or first_time) and OPEN_BROWSER:
        page = SETUP_PAGE = SetupPage(progress)
        say(f"The setup page is open in your browser ({page.url}).")
        webbrowser.open(page.url + "?t=" + page.token)
    app, started_db = None, False
    try:
        env = setup_env()
        first_run = setup_python(progress)
        if f"@127.0.0.1:{LOCAL_DB_PORT}/" in env.get("DATABASE_URL", ""):
            started_db = start_local_db(progress)
        load_word_pack(progress)
        if WINDOWS and (first_run or show_setup):
            make_shortcut(progress)

        progress.begin("start")
        if page and not page.answered and page.is_open():
            progress.update(0, "waiting for your keys")
            page.wait_for_keys()
            progress.update(0.1, "")

        for leftover in ("request.json", "stop"):  # from a run that did not end cleanly
            if os.path.exists(os.path.join(UPDATE_DIR, leftover)):
                os.remove(os.path.join(UPDATE_DIR, leftover))
        # Debug mode (reload on save, error pages) only in a developer's git clone:
        # installed copies do without the debugger, and nothing reloads mid-update.
        # Its reloader runs the server in a second process, so the app gets a
        # process group of its own (on Linux and macOS) and the whole group is stopped.
        debug = ["--debug"] if os.path.isdir(os.path.join(ROOT, ".git")) or os.environ.get("MYVOCAB_DEBUG") == "1" else []
        app = subprocess.Popen([PYTHON, "-m", "flask", "--app", "app", "run", *debug, "--port", PORT],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                               env=dict(os.environ, MYVOCAB_LOCAL="1"),
                               **({} if WINDOWS else {"start_new_session": True}))
        threading.Thread(target=pass_on_log, args=(app, progress), daemon=True).start()
        # The setup page sends the browser on to the app; otherwise a new tab opens.
        if not (page and page.is_open()):
            open_browser_when_ready()
        for second in range(90):
            if app.poll() is not None or answering():
                break
            progress.update(0.1 + 0.85 * second / 20)
            time.sleep(1)
        if app.poll() is None:
            progress.done()
            say(f"MyVocab is running at {URL}")
            say("Keep this window open while you study. Close it (or press Ctrl+C) to stop MyVocab.")
            if page:
                page.close_later()
        else:
            progress.fail("MyVocab stopped while starting. The black window says why.")
        while app.poll() is None:
            if watch_for_update():
                say("Closing for the update. MyVocab opens again by itself in a moment.")
                return 0
            time.sleep(1)
        return app.returncode
    except KeyboardInterrupt:
        print(flush=True)
        say("Stopping ...")
        return 0
    finally:
        if app:
            stop_app(app)
        # The database stops with the app, unless it was already running before.
        if started_db:
            local_db("stop")


def watch_for_update():
    """Starts tools/update.py when the Update button asks, and returns True when
    that script asks for MyVocab to close so it can put the new files in."""
    request = os.path.join(UPDATE_DIR, "request.json")
    if os.path.exists(request):
        try:
            with open(request, encoding="utf-8") as f:
                tag = json.load(f)["tag"]
        except (OSError, ValueError, KeyError):
            tag = None
        os.remove(request)
        if tag:
            say(f"Updating to {tag}: the page shows how far it has got.")
            # On its own (not a child of this window), so it outlives the window it closes.
            relaunch = "console" if WINDOWS else ("terminal" if sys.stdout.isatty() and os.environ.get("DISPLAY") else "background")
            subprocess.Popen([PYTHON, os.path.join("tools", "update.py"), "--tag", tag, "--wait-pid", str(os.getpid()),
                              "--relaunch", relaunch],
                             stdout=open(os.path.join(UPDATE_DIR, "update.log"), "a"), stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL,
                             **({"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
                                if WINDOWS else {"start_new_session": True}))
    return os.path.exists(os.path.join(UPDATE_DIR, "stop"))


def stop_app(app):
    if app.poll() is not None:
        return
    if WINDOWS:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(app.pid)], capture_output=True)
    else:
        os.killpg(app.pid, signal.SIGTERM)
    try:
        app.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if not WINDOWS:
            os.killpg(app.pid, signal.SIGKILL)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit as stop:
        if stop.code not in (0, None) and SETUP_PAGE and SETUP_PAGE.is_open():
            time.sleep(2.5)  # the setup page asks every second: let it show what went wrong
        raise
