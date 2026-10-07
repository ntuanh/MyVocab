"""Updates MyVocab on this computer to a GitHub release. run.py starts it when
the Update button is pressed (see updates.py); it runs on its own, so it
outlives the MyVocab window it closes:

    python tools/update.py --tag v1.2 --wait-pid <run.py's pid> [--relaunch console|terminal|background]

1. download the release and unpack it (MyVocab keeps running meanwhile);
2. save a backup of your words (backup/myvocab-<date>-before-<version>.sql);
3. ask run.py to close MyVocab (.update/stop) and wait for it;
4. put the new files in. .env, .venv, .localdb and backup are not in a
   release, so your keys, packages, words and backups stay;
5. open MyVocab again. run.py then installs any new packages.

Each step is written to .update/status.json for the page. A failure before
step 3 leaves MyVocab running as it was.
"""
import argparse
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from myvocab.updates import REPO, STATE_DIR, VERSION_FILE, write_status  # noqa: E402

STOP_FILE = os.path.join(STATE_DIR, "stop")
WINDOWS = os.name == "nt"


def log(message):
    print(time.strftime("%H:%M:%S"), message, flush=True)


def download(tag):
    """The release's files, unpacked into a temporary folder. Returns that folder."""
    url = f"https://github.com/{REPO}/archive/refs/tags/{tag}.zip"
    log(f"downloading {url}")
    with urllib.request.urlopen(url, timeout=120) as response:
        data = response.read()
    folder = tempfile.mkdtemp(prefix="myvocab-update-")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        archive.extractall(folder)
    inside = [os.path.join(folder, name) for name in os.listdir(folder)]
    source = inside[0] if len(inside) == 1 and os.path.isdir(inside[0]) else folder  # MyVocab-1.2/
    if not all(os.path.exists(os.path.join(source, name)) for name in ("app.py", "run.py", "requirements.txt")):
        raise RuntimeError("The download does not look like MyVocab.")
    return folder, source


def backup(tag):
    """A backup with a name of its own, so it never replaces one made by hand that day."""
    if not os.path.exists(os.path.join(ROOT, ".localdb", "PG_VERSION")):
        return
    os.makedirs(os.path.join(ROOT, "backup"), exist_ok=True)
    path = os.path.join(ROOT, "backup", f"myvocab-{time.strftime('%Y-%m-%d')}-before-{tag}.sql")
    result = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "local_db.py"), "backup", path],
                            capture_output=True, text=True, errors="replace")
    log(result.stdout + result.stderr)
    if result.returncode != 0:
        raise RuntimeError("The backup of your words failed, so nothing was changed.")


def process_alive(pid):
    try:
        import psutil  # comes with the database package
        return psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except ImportError:
        if WINDOWS:
            return True  # without psutil, rely on the time limit below
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    except Exception:  # the process ended between the two questions
        return False


def close_myvocab(pid):
    with open(STOP_FILE, "w") as f:
        f.write(str(time.time()))
    deadline = time.time() + 60
    while process_alive(pid) and time.time() < deadline:
        time.sleep(0.5)
    # The MyVocab window may still be reading the last lines of run.bat: give it a moment.
    time.sleep(3)


def put_in(source):
    for name in os.listdir(source):
        path = os.path.join(source, name)
        target = os.path.join(ROOT, name)
        if os.path.isdir(path):
            shutil.copytree(path, target, dirs_exist_ok=True)
        else:
            shutil.copy2(path, target)


def relaunch(how):
    """Opens MyVocab again. The page that asked for the update is still open, so no new tab."""
    env = dict(os.environ, OPEN_BROWSER="0")
    for name in ("MYVOCAB_LOCAL", "FLASK_RUN_FROM_CLI", "WERKZEUG_SERVER_FD", "WERKZEUG_RUN_MAIN"):
        env.pop(name, None)
    if how == "console" and WINDOWS:
        subprocess.Popen(["cmd", "/c", os.path.join(ROOT, "run.bat")], cwd=ROOT, env=env,
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
        return
    if how == "terminal":
        for terminal in ("x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "xterm"):
            if shutil.which(terminal):
                command = [terminal, "--", os.path.join(ROOT, "run.sh")] if terminal == "gnome-terminal" \
                    else [terminal, "-e", os.path.join(ROOT, "run.sh")]
                subprocess.Popen(command, cwd=ROOT, env=env, start_new_session=True)
                return
    # No window to show it in: run it in the background, with its log in .update/run.log.
    out = open(os.path.join(STATE_DIR, "run.log"), "a")
    system_python = shutil.which("python3") or shutil.which("python") or sys.executable
    subprocess.Popen([system_python, os.path.join(ROOT, "run.py")], cwd=ROOT, env=env, stdout=out,
                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                     **({"creationflags": subprocess.DETACHED_PROCESS} if WINDOWS else {"start_new_session": True}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--wait-pid", type=int, required=True)
    parser.add_argument("--relaunch", default="console" if WINDOWS else "terminal",
                        choices=["console", "terminal", "background"])
    args = parser.parse_args()
    tag = args.tag
    how = os.environ.get("MYVOCAB_RELAUNCH") or args.relaunch

    try:
        write_status("download", f"Downloading MyVocab {tag} ...", tag=tag)
        folder, source = download(tag)
        write_status("backup", "Saving a backup of your words ...", tag=tag)
        backup(tag)
    except Exception as error:
        log(f"failed: {error}")
        write_status("error", f"The update could not start: {error} MyVocab still works as before.", tag=tag)
        return 1

    write_status("restart", "Closing MyVocab to put the new version in ...", tag=tag)
    close_myvocab(args.wait_pid)
    try:
        put_in(source)
        with open(VERSION_FILE, "w", encoding="utf-8") as f:
            f.write(tag + "\n")
        write_status("start", f"Starting MyVocab {tag} ...", tag=tag)
        log(f"updated to {tag}")
        failed = None
    except Exception as error:
        log(f"failed while copying: {error}")
        failed = error
    finally:
        shutil.rmtree(folder, ignore_errors=True)
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
    relaunch(how)
    if failed:
        write_status("error", f"Some new files could not be put in ({failed}). Run MyVocab-Setup to repair it.", tag=tag)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
