#!/usr/bin/env bash
# Start MyVocab on this computer:  ./run.sh   (or the desktop shortcut)
# run.py does the work, the same on Linux, macOS and Windows: it sets up Python
# and the database the first time, then starts the app and opens the browser.
cd "$(dirname "$0")"
exec python3 run.py "$@"
