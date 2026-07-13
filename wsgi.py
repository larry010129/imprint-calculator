"""WSGI entry point for production hosts (PythonAnywhere, gunicorn, etc.).

PythonAnywhere Web tab → WSGI configuration file:
  from wsgi import application
(after adding the project directory to sys.path — see deploy/pythonanywhere.wsgi.example)
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# SQLite and .env paths are relative to the working directory on some hosts.
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(ROOT / '.env', override=True)

from app import app as application  # noqa: E402
