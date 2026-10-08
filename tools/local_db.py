"""The database on this computer: a real PostgreSQL from the pgserver pip
package, so nothing is installed system-wide. Its data lives in .localdb/
(gitignored). Works the same on Linux, macOS and Windows.

    python tools/local_db.py start              # create it the first time, then start it
    python tools/local_db.py stop
    python tools/local_db.py status
    python tools/local_db.py backup [FILE]      # save every word, topic and score to a .sql file
    python tools/local_db.py restore FILE       # replace an empty database with a backup
    python tools/local_db.py compact            # rebuild it smaller, same data (run.py does it once)

run.py calls start (and, on a new computer, restore) for you. To use it, .env needs:
    DATABASE_URL=postgresql://myvocab@127.0.0.1:5433/myvocab
Backups go to backup/ (gitignored): they hold your own words and writing.
"""
import datetime
import glob
import os
import shutil
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


# Sized for one person on one computer, not a server: less shared memory, fewer
# helper processes, no replication, and a small change log (WAL). Written into
# postgresql.conf before every start, so databases made by older versions get it too.
LIGHT_BEGIN = "# --- MyVocab: sized for one person (tools/local_db.py writes this) ---"
LIGHT_END = "# --- end of MyVocab settings ---"


def wal_segment_mb():
    """The size of one change-log file: 16 MB in databases made before v1.7, 1 MB after."""
    out = subprocess.run([bin_path("pg_controldata"), "-D", DATA], capture_output=True, text=True,
                         env=dict(os.environ, LC_ALL="C")).stdout
    for line in out.splitlines():
        if line.startswith("Bytes per WAL segment"):
            return max(1, int(line.split(":")[1]) // (1024 * 1024))
    return 16


def tune():
    seg = wal_segment_mb()
    settings = {
        "shared_buffers": "16MB", "max_connections": "30",
        "max_worker_processes": "2", "max_parallel_workers": "0", "max_parallel_workers_per_gather": "0",
        "autovacuum_max_workers": "1",
        "wal_level": "minimal", "max_wal_senders": "0", "max_replication_slots": "0",
        "max_logical_replication_workers": "0",
        "min_wal_size": f"{2 * seg}MB", "max_wal_size": f"{max(16, 4 * seg)}MB",
    }
    path = os.path.join(DATA, "postgresql.conf")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if LIGHT_BEGIN in text:
        text = text[:text.index(LIGHT_BEGIN)].rstrip("\n") + text[text.index(LIGHT_END) + len(LIGHT_END):]
    block = "\n".join([LIGHT_BEGIN, *(f"{k} = {v}" for k, v in settings.items()), LIGHT_END])
    with open(path, "w", encoding="utf-8") as f:
        f.write(text.rstrip("\n") + "\n\n" + block + "\n")


def start():
    """Starts the database, creating it first if needed. Returns True when it was just created."""
    created = not os.path.exists(os.path.join(DATA, "PG_VERSION"))
    if created:
        print(f"Creating the database in {DATA} ...")
        # 1 MB change-log files instead of 16 MB: the log keeps a few of them at all times.
        run("initdb", "-D", DATA, "-U", NAME, "--auth=trust", "-E", "UTF8", "--no-locale", "--wal-segsize=1")
        # Reachable only from this computer, over TCP, so no system socket folder is needed.
        with open(os.path.join(DATA, "postgresql.conf"), "a", encoding="utf-8") as conf:
            conf.write(f"\nlisten_addresses = '127.0.0.1'\nport = {PORT}\nunix_socket_directories = ''\n")
    if not running():
        if stale_lock():
            os.remove(os.path.join(DATA, "postmaster.pid"))
            print("Removed a lock file left when the computer was switched off with the database on.")
        tune()
        run("pg_ctl", "-D", DATA, "-l", os.path.join(DATA, "server.log"), "-w", "start")
    if created:
        run("createdb", *CONNECT, NAME)
        # PostgreSQL's spare "postgres" database (7 MB) is never used by MyVocab.
        run("psql", *CONNECT, "-d", NAME, "-qc", "DROP DATABASE IF EXISTS postgres;")
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


def table_counts():
    """{table: rows} for every table, to check a rebuilt database has everything."""
    names = run("psql", *CONNECT, "-d", NAME, "-tAc",
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1;").stdout.split()
    return {t: int(run("psql", *CONNECT, "-d", NAME, "-tAc", f'SELECT count(*) FROM "{t}";').stdout) for t in names}


def compact(only_if_needed=False):
    """Rebuilds the database files in today's lighter layout (1 MB change-log files,
    no spare "postgres" database) with exactly the same data: a backup, a new
    database, the backup loaded into it, and every table's row count checked.
    Only then are the old files removed; if anything goes wrong they are put back."""
    if not os.path.exists(os.path.join(DATA, "PG_VERSION")):
        print("No database here yet.")
        return
    if only_if_needed and wal_segment_mb() <= 1:
        return
    old = DATA + "-old"
    if os.path.exists(old):
        sys.exit(f"{old} is left from an earlier try. Check it holds nothing you need, delete it, and run again.")
    was_running = running()
    if not was_running:
        start()
    size_before = folder_mb(DATA)
    before = table_counts()
    dump = backup(os.path.join(BACKUP_DIR, f"myvocab-{datetime.date.today().isoformat()}-before-compact.sql"))
    stop()
    os.rename(DATA, old)
    try:
        start()
        restore(dump)
        after = table_counts()
        if after != before:
            raise RuntimeError(f"the rebuilt database differs: {before} != {after}")
    except BaseException as error:  # also sys.exit from a failed step
        if running():
            stop()
        shutil.rmtree(DATA, ignore_errors=True)
        os.rename(old, DATA)
        if was_running:
            start()
        sys.exit(f"Compacting stopped ({error}). Your database is back as it was; the backup is {dump}.")
    shutil.rmtree(old)
    if not was_running:
        stop()
    print(f"Compacted: {size_before:.0f} MB -> {folder_mb(DATA):.0f} MB, {sum(before.values())} rows in {len(before)} tables, all there.")


def folder_mb(path):
    return sum(os.path.getsize(os.path.join(d, f)) for d, _, files in os.walk(path) for f in files) / 1048576


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
    elif command == "compact":
        compact(only_if_needed="--if-needed" in sys.argv)
    else:
        sys.exit(__doc__)
