"""Server entry point. Run: python app.py  (or: flask run)"""
import os
import sys
from pathlib import Path

from flask import Flask

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env', override=True)

from diamond_calculator import create_app  # noqa: E402

app: Flask = create_app()

if __name__ == '__main__':
    # SECRET_KEY presence (required outside of FLASK_DEBUG=1) is already
    # enforced inside create_app(), regardless of how the app is started.
    use_flask_dev = os.environ.get('FLASK_DEBUG', '0') == '1'
    port = int(os.environ.get('PORT', 8000))
    host = os.environ.get('HOST', '0.0.0.0')

    if use_flask_dev:
        app.run(debug=True, host=host, port=port)
    else:
        from waitress import serve
        # ident=None suppresses the "Server: waitress" response header so the
        # stack isn't advertised to clients.
        serve(app, host=host, port=port, ident=None)
