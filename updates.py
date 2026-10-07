"""New versions for MyVocab installed on a computer. GitHub releases are the
versions: tools/release.py publishes one. The app asks GitHub about every half
hour, and the Update button (static/update.js) shows when a newer release is out.

Pressing it leaves a request in .update/. run.py, which started the app, sees
the request and starts tools/update.py. That script downloads the release,
saves a backup, asks run.py to close MyVocab, puts the new files in, and opens
MyVocab again. Progress goes to .update/status.json, which the page reads here.

Only for a copy run by run.py (MYVOCAB_LOCAL=1) that is not a git clone.
A developer's clone updates with git, and Vercel deploys from GitHub by itself.
MYVOCAB_UPDATES=1 turns updates on anyway (for testing).
"""
import json
import os
import threading
import time

import requests

REPO = "ntuanh/MyVocab"
ROOT = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(ROOT, ".update")
STATUS_FILE = os.path.join(STATE_DIR, "status.json")
REQUEST_FILE = os.path.join(STATE_DIR, "request.json")
VERSION_FILE = os.path.join(ROOT, ".version")
CHECK_EVERY = 30 * 60   # seconds between questions to GitHub (it allows 60 an hour)
RETRY_AFTER = 10 * 60   # sooner after a failed question (offline, say)

_lock = threading.Lock()
_latest = {"checked": 0.0, "release": None}


def enabled():
    if os.environ.get("MYVOCAB_UPDATES") == "1":
        return True
    return os.environ.get("MYVOCAB_LOCAL") == "1" and not os.path.isdir(os.path.join(ROOT, ".git"))


def current_version():
    """The release this copy came from (written by the setup and by tools/update.py), or None if unknown."""
    try:
        with open(VERSION_FILE, encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def latest_release():
    """The newest release on GitHub, asked at most every CHECK_EVERY seconds."""
    with _lock:
        if time.time() - _latest["checked"] < CHECK_EVERY:
            return _latest["release"]
        _latest["checked"] = time.time()
    try:
        response = requests.get(f"https://api.github.com/repos/{REPO}/releases/latest",
                                headers={"Accept": "application/vnd.github+json"}, timeout=6)
        if response.status_code != 200:
            raise requests.RequestException(f"GitHub returned {response.status_code}")
        data = response.json()
        _latest["release"] = {
            "tag": data["tag_name"],
            "name": data.get("name") or data["tag_name"],
            "notes": (data.get("body") or "").strip()[:2000],
            "published": data.get("published_at"),
        }
    except (requests.RequestException, ValueError, KeyError) as error:
        print(f"WARN: could not ask GitHub for a new version: {error}")
        _latest["checked"] = time.time() - CHECK_EVERY + RETRY_AFTER
    return _latest["release"]


def read_status():
    try:
        with open(STATUS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_status(step, message, **extra):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(dict(step=step, message=message, at=time.time(), **extra), f)


def status():
    if not enabled():
        return {"enabled": False}
    release = latest_release()
    current = current_version()
    progress = read_status()
    if progress and progress["step"] == "start" and progress.get("tag") == current:
        write_status("done", f"MyVocab is updated to {current}.", tag=current)  # the new version is up
        progress = read_status()
    return {
        "enabled": True,
        "current": current,
        "latest": release,
        "available": bool(release and release["tag"] != current),
        "progress": progress,
    }


def busy():
    progress = read_status()
    return bool(progress and progress["step"] not in ("done", "error") and time.time() - progress.get("at", 0) < 15 * 60)


def start(tag):
    """Leaves the request for run.py. Returns an error message, or None."""
    if not enabled():
        return "Updates are only for MyVocab installed on a computer."
    release = latest_release()
    if not release or release["tag"] != tag:
        return "That version is not the newest one any more. Reload the page."
    if busy():
        return "An update is already running."
    write_status("waiting", "Starting the update ...", tag=tag)
    with open(REQUEST_FILE, "w", encoding="utf-8") as f:
        json.dump({"tag": tag, "at": time.time()}, f)
    return None
