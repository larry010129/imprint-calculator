# Diamond Calculator

## What this is
This is an internal pricing and order tool for diamond rings and necklaces. It is built using Flask and uses a SQLite database to manage store submissions.

## Setup
Create a virtual environment, activate it, and install the dependencies:
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Environment variables

| Var | Required | Purpose |
|---|---|---|
| `SECRET_KEY` | production: yes | session signing; sessions reset when changed |
| `ADMIN_PASSWORD` | first run only | seeds the `admin` account if it doesn't exist |
| `GOLDAPI_KEY` | recommended | goldapi.io key for live metal prices; if unset, the app runs on hardcoded fallback prices (see FALLBACK_TWD_PER_GRAM in app.py) — there is no longer a built-in key |
| `FLASK_DEBUG` | dev only | `1` = Flask dev server with debugger |
| `PORT` | no | production port, default 8000 |

*Note: Changing the `SECRET_KEY` will invalidate all active sessions and log everyone out.*

Copy `.env.example` to `.env` and fill in real values for local dev (the app does not auto-load `.env` — use `set VAR=value` on Windows or export it in your shell before running, or install `python-dotenv` if you want auto-loading).

## Run
**Development**:
```bash
set FLASK_DEBUG=1
python app.py
```

**Production**:
```bash
set SECRET_KEY=your_secure_secret_key
python app.py
```
This serves the application on `http://0.0.0.0:8000` via Waitress. Since it binds to `0.0.0.0`, it will be exposed to your local network. Windows Firewall may prompt you to allow inbound connections on first run.

## First run
Set `ADMIN_PASSWORD` and start the server once. This will seed the `admin` account (only if it doesn't already exist). Log in as `admin`, and stores can self-register at `/register`.
Example:
```bash
set ADMIN_PASSWORD=supersecret
python app.py
```

## Data & backup
All data lives in `instance/database.db`. To back it up, copy that file while the server is stopped, or run the following while it is running:
```bash
sqlite3 instance/database.db ".backup backup.db"
```

## Product images
Images are located in `static/images/`. Refer to `static/images/README.md` for information on the 12 filename slots.

## Testing
Run the tests with:
```bash
python test_validation.py
python test_routes.py
```
Both are plain assert-based scripts (no pytest). `test_routes.py` uses an in-memory SQLite database and never touches `instance/database.db`.
