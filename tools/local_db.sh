#!/usr/bin/env bash
# The database on this computer; see tools/local_db.py (start, stop, status,
# backup, restore). Kept for the old command:  tools/local_db.sh start
cd "$(dirname "$0")/.."
exec .venv/bin/python tools/local_db.py "$@"
