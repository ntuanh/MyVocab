"""The database on this computer: a real PostgreSQL from the pgserver pip
package, so nothing is installed system-wide. Its data lives in .localdb/
(gitignored). Works the same on Linux, macOS and Windows.

    python tools/local_db.py start              # create it the first time, then start it
    python tools/local_db.py stop
    python tools/local_db.py status
    python tools/local_db.py backup [FILE]      # save every word, topic and score to a .sql file
    python tools/local_db.py restore FILE       # replace an empty database with a backup

run.py calls start (and, on a new computer, restore) for you. To use it, .env needs:
    DATABASE_URL=postgresql://myvocab@127.0.0.1:5433/myvocab
Backups go to backup/ (gitignored): they hold your own words and writing.
"""
import datetime
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("MYVOCAB_DB_DIR") or os.path.join(ROOT, ".localdb")
PORT = os.environ.get("MYVOCAB_DB_PORT", "5433")
NAME = "myvocab"
URL = f"postgresql://{NAME}@127.0.0.1:{PORT}/{NAME}"
BACKUP_DIR = os.path.join(ROOT, "backup")
CONNECT = ["-h", "127.0.0.1", "-p", PORT, "-U", NAME]


def bin_path(tool):
    try:
        import pgserver
    except ImportError:
        sys.exit("pgserver is not installed. Run run.py (or: pip install -r requirements-local.txt).")
    exe = tool + (".exe" if os.name == "nt" else "")
    return os.path.join(os.path.dirname(pgserver.__file__), "pginstall", "bin", exe)


def run(tool, *args, quiet=True):
    result = subprocess.run([bin_path(tool), *args], capture_output=quiet, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip() if quiet else ""
        sys.exit(f"{tool} failed{': ' + detail if detail else ''}")
    return result


def running():
    """True when the database answers on its port. Not `pg_ctl status`: that
    trusts postmaster.pid, and a stale one can look alive (see stale_lock)."""
    return subprocess.run([bin_path("pg_isready"), "-h", "127.0.0.1", "-p", PORT, "-q"],
                          capture_output=True).returncode == 0


def stale_lock():
    """True when postmaster.pid is left over from a database that is gone. A
    computer switched off with the database on leaves the file behind. After a
    restart its process number may belong to another program, so pg_ctl would
    take the database for running and never start it. The file only counts
    while its process is a postgres."""
    path = os.path.join(DATA, "postmaster.pid")
    if not os.path.exists(path):
        return False
    try:
        with open(path) as f:
            pid = int(f.readline())
    except (OSError, ValueError):
        return True
    try:
        import psutil  # comes with pgserver
    except ImportError:
        return False  # cannot tell: leave the file alone
    try:
        return "postgres" not in psutil.Process(pid).name().lower()
    except psutil.Error:  # no such process (or not ours to look at)
        return not psutil.pid_exists(pid)


def start():
    """Starts the database, creating it first if needed. Returns True when it was just created."""
    created = not os.path.exists(os.path.join(DATA, "PG_VERSION"))
    if created:
        print(f"Creating the database in {DATA} ...")
        run("initdb", "-D", DATA, "-U", NAME, "--auth=trust", "-E", "UTF8", "--no-locale")
        # Reachable only from this computer, over TCP, so no system socket folder is needed.
        with open(os.path.join(DATA, "postgresql.conf"), "a", encoding="utf-8") as conf:
            conf.write(f"\nlisten_addresses = '127.0.0.1'\nport = {PORT}\nunix_socket_directories = ''\n")
    if not running():
        if stale_lock():
            os.remove(os.path.join(DATA, "postmaster.pid"))
            print("Removed a lock file left when the computer was switched off with the database on.")
        run("pg_ctl", "-D", DATA, "-l", os.path.join(DATA, "server.log"), "-w", "start")
    if created:
        run("createdb", *CONNECT, NAME)
    print(f"Database running: {URL}")
    return created


def stop():
    if running():
        run("pg_ctl", "-D", DATA, "-w", "stop")
        print("Database stopped.")
    else:
        print("Database was not running.")


def backup(path=None):
    """Saves everything to a .sql file. A database that was stopped is started
    just for the backup and stopped again afterwards."""
    was_running = running()
    if not was_running:
        start()
    os.makedirs(BACKUP_DIR, exist_ok=True)
    path = path or os.path.join(BACKUP_DIR, f"myvocab-{datetime.date.today().isoformat()}.sql")
    try:
        run("pg_dump", *CONNECT, "--no-owner", "--no-privileges", "-f", path, NAME)
    finally:
        if not was_running:
            stop()
    print(f"Backup saved: {path} ({os.path.getsize(path) // 1024} KB)")
    return path


def has_words():
    table = run("psql", *CONNECT, "-d", NAME, "-tAc", "SELECT to_regclass('public.words') IS NOT NULL;")
    if table.stdout.strip() != "t":
        return False
    count = run("psql", *CONNECT, "-d", NAME, "-tAc", "SELECT count(*) FROM words;")
    return int(count.stdout.strip() or 0) > 0


def restore(path, force=False):
    if not os.path.exists(path):
        sys.exit(f"No such file: {path}")
    if not running():
        start()
    if has_words() and not force:
        sys.exit("This database already has words, and restoring replaces everything in it. "
                 "Add --force if that is what you want.")
    # A clean slate: the app may already have made its empty tables here.
    run("psql", *CONNECT, "-d", NAME, "-qc", "DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    run("psql", *CONNECT, "-d", NAME, "-v", "ON_ERROR_STOP=1", "-q", "-f", path)
    print(f"Restored {path}")


def newest_backup():
    files = sorted(glob.glob(os.path.join(BACKUP_DIR, "*.sql")), key=os.path.getmtime)
    return files[-1] if files else None


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "start"
    if command == "start":
        start()
    elif command == "stop":
        stop()
    elif command == "status":
        print("running" if running() else "stopped", URL)
    elif command == "backup":
        backup(sys.argv[2] if len(sys.argv) > 2 else None)
    elif command == "restore" and len(sys.argv) > 2:
        restore(sys.argv[2], force="--force" in sys.argv)
    else:
        sys.exit(__doc__)
