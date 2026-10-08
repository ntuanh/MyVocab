"""Run every test suite against a separate copy of MyVocab, so your own words
are never touched. It:

1. makes a throwaway database, filled from your newest backup in backup/
   (or, without one, from the database on this computer);
2. starts the app on a free port, with that database;
3. runs each suite (browser checks with Playwright, and logic checks);
4. stops it all and deletes the throwaway database.

    .venv/bin/python tests/run_all.py              # every suite (about 5 minutes)
    .venv/bin/python tests/run_all.py reading fx   # only suites whose name has one of these
    .venv/bin/python tests/run_all.py --install    # also a full first install in a temporary
                                                   # folder, setup page included (needs internet)

Once, before the first run:
    .venv/bin/pip install -r requirements-dev.txt
    .venv/bin/python -m playwright install chromium

Exit code 0 means every check passed. Run it before python3 dev/release.py.
"""
import argparse
import glob
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")
PYTHON = sys.executable
SUITES = ["trees", "fx", "glosses", "tracking", "listening", "listening_docs", "reading", "writing_logic", "writing_ui", "update_ui"]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(url, seconds=60):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def local_db(env, *args):
    result = subprocess.run([PYTHON, os.path.join(ROOT, "tools", "local_db.py"), *args], env=env,
                            capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"tools/local_db.py {' '.join(args)} failed:\n{result.stdout}{result.stderr}")
    return result


def make_database(work):
    """A database of its own on a free port, with your words in it. Returns (its env, its URL)."""
    port = str(free_port())
    env = dict(os.environ, MYVOCAB_DB_DIR=os.path.join(work, "db"), MYVOCAB_DB_PORT=port)
    source = sorted(glob.glob(os.path.join(ROOT, "backup", "*.sql")), key=os.path.getmtime)
    if source:
        source = source[-1]
    elif os.path.exists(os.path.join(ROOT, ".localdb", "PG_VERSION")):
        source = os.path.join(work, "words.sql")
        local_db(dict(os.environ), "backup", source)  # a copy of the database on this computer
    else:
        sys.exit("The tests need words: make a backup first (python3 tools/local_db.py backup).")
    print(f"Test database: {os.path.basename(source)} on port {port}")
    local_db(env, "start")
    local_db(env, "restore", source)
    return env, f"postgresql://myvocab@127.0.0.1:{port}/myvocab"


def start_app(database_url):
    port = free_port()
    env = dict(os.environ, DATABASE_URL=database_url, MYVOCAB_LOCAL="1", OPEN_BROWSER="0")
    log = open(os.path.join(TESTS, ".shots", "app.log"), "w")
    app = subprocess.Popen([PYTHON, "-m", "flask", "--app", "app", "run", "--port", str(port)], cwd=ROOT, env=env,
                           stdout=log, stderr=subprocess.STDOUT,
                           **({} if os.name == "nt" else {"start_new_session": True}))
    url = f"http://127.0.0.1:{port}"
    if not wait_for(url):
        app.kill()
        sys.exit("The app under test did not start. See tests/.shots/app.log.")
    print(f"App under test: {url}")
    return app, url


def stop(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True)
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()


def run_suite(name, env):
    started = time.time()
    result = subprocess.run([PYTHON, os.path.join(TESTS, f"{name}_test.py")], cwd=ROOT, env=env,
                            capture_output=True, text=True, errors="replace")
    output = result.stdout + result.stderr
    tally = re.findall(r"^(\d+)/(\d+) passed", output, flags=re.M)
    passed, total = (int(tally[-1][0]), int(tally[-1][1])) if tally else (0, 0)
    ok = result.returncode == 0 and total > 0
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<14} {passed}/{total}  ({time.time() - started:.0f}s)", flush=True)
    if not ok:
        failed = [line for line in output.splitlines() if line.startswith("FAIL") or "Error" in line]
        for line in (failed or output.splitlines()[-15:])[:15]:
            print("        " + line)
    return ok, passed, total


def run_install(work):
    """A first install in a temporary folder, as on a new computer: run.py with a stand-in browser."""
    folder = os.path.join(work, "install")
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    for name in files:
        if os.path.exists(os.path.join(ROOT, name)):
            os.makedirs(os.path.dirname(os.path.join(folder, name)), exist_ok=True)
            shutil.copy2(os.path.join(ROOT, name), os.path.join(folder, name))
    opened = os.path.join(work, "opened.txt")
    recorder = os.path.join(work, "browser.py")
    with open(recorder, "w") as f:
        f.write(f"import sys\nopen({opened!r}, 'a').write(sys.argv[1] + '\\n')\n")
    app_port = free_port()
    system_python = shutil.which("python3") or shutil.which("python") or PYTHON
    env = dict(os.environ, PORT=str(app_port), MYVOCAB_DB_PORT=str(free_port()),
               BROWSER=f'"{PYTHON}" "{recorder}" %s')
    env.pop("MYVOCAB_DB_DIR", None)
    env.pop("VIRTUAL_ENV", None)
    print(f"Installing into {folder} (packages come from the internet) ...", flush=True)
    setup = subprocess.Popen([system_python, "run.py"], cwd=folder, env=env, stdout=subprocess.DEVNULL,
                             stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    try:
        test_env = dict(os.environ, MYVOCAB_TEST_INSTALL_DIR=folder, MYVOCAB_TEST_BROWSER_LOG=opened,
                        MYVOCAB_TEST_INSTALL_URL=f"http://127.0.0.1:{app_port}")
        return run_suite("setup", test_env)
    finally:
        setup.terminate()  # run.py stops its app and its database
        try:
            setup.wait(timeout=30)
        except subprocess.TimeoutExpired:
            setup.kill()


def main():
    parser = argparse.ArgumentParser(description="Run MyVocab's tests against a separate copy.")
    parser.add_argument("only", nargs="*", help="run only suites whose name contains one of these")
    parser.add_argument("--install", action="store_true", help="also test a full first install")
    args = parser.parse_args()
    suites = [s for s in SUITES if not args.only or any(word in s for word in args.only)]
    os.makedirs(os.path.join(TESTS, ".shots"), exist_ok=True)

    work = tempfile.mkdtemp(prefix="myvocab-test-")
    db_env, app = None, None
    results = []
    started = time.time()
    try:
        if suites:
            db_env, database_url = make_database(work)
            app, url = start_app(database_url)
            env = dict(os.environ, MYVOCAB_TEST_URL=url, MYVOCAB_TEST_DATABASE_URL=database_url)
            print(f"Running {len(suites)} suites:")
            for name in suites:
                results.append(run_suite(name, env))
        if args.install:
            results.append(run_install(work))
    finally:
        if app:
            stop(app)
        if db_env:
            subprocess.run([PYTHON, os.path.join(ROOT, "tools", "local_db.py"), "stop"], env=db_env, capture_output=True)
        shutil.rmtree(work, ignore_errors=True)

    passed = sum(r[1] for r in results)
    total = sum(r[2] for r in results)
    good = all(r[0] for r in results) and results
    print(f"\n{'All passed' if good else 'SOME FAILED'}: {passed}/{total} checks in {len(results)} suites, "
          f"{time.time() - started:.0f}s")
    sys.exit(0 if good else 1)


if __name__ == "__main__":
    main()
