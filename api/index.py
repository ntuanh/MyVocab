# file: /api/index.py
# Vercel entrypoint. It looks for a module-level `app` in this file.

import os
import sys

# The lambda runs this file from inside api/, so put the project root on the
# path before importing app.py / database.py / handle_request.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
