# PLAN: Production serving + operations README

## Goal
The app is one `python app.py` away from being used by real stores, but that runs Flask's dev server (single-threaded, explicitly "do not use in production", now with debug correctly off by default). There is also no written record of the env vars the app now depends on (`SECRET_KEY`, `ADMIN_PASSWORD`, `GOLDAPI_KEY`, `FLASK_DEBUG`), no first-run instructions, and no backup story for the SQLite DB that now holds real orders. Ship a production entrypoint (waitress — the standard WSGI server for Windows) and a README.

## Exact files to touch
- `requirements.txt` — add waitress.
- `app.py` — replace the `__main__` block.
- `README.md` — new file (repo root).

## Step-by-step implementation

### 1. requirements.txt
Add:
```
waitress==3.0.2
```
Then `pip install -r requirements.txt`.

### 2. app.py `__main__` block (currently line 335–336)
```python
if __name__ == '__main__':
    if os.environ.get('FLASK_DEBUG') == '1':
        app.run(debug=True)
    else:
        from waitress import serve
        port = int(os.environ.get('PORT', 8000))
        print(f"Serving on http://0.0.0.0:{port}")
        serve(app, host='0.0.0.0', port=port)
```

### 3. README.md
Write it with exactly these sections (fill in from the codebase, don't invent features):
- **What this is** — 2 sentences: internal pricing/order tool for diamond rings & necklaces, Flask + SQLite.
- **Setup** — `python -m venv venv`, activate, `pip install -r requirements.txt`.
- **Environment variables** (table):
  | Var | Required | Purpose |
  |---|---|---|
  | `SECRET_KEY` | production: yes | session signing; sessions reset when changed |
  | `ADMIN_PASSWORD` | first run only | seeds the `admin` account if it doesn't exist |
  | `GOLDAPI_KEY` | recommended | goldapi.io key for live metal prices; falls back to a built-in key, then to hardcoded fallback prices |
  | `FLASK_DEBUG` | dev only | `1` = Flask dev server with debugger |
  | `PORT` | no | production port, default 8000 |
- **Run** — dev: `set FLASK_DEBUG=1 && python app.py`; production: `set SECRET_KEY=... && python app.py` (serves on 0.0.0.0:8000 via waitress).
- **First run** — set `ADMIN_PASSWORD`, start once, log in as `admin`; stores self-register at `/register`.
- **Data & backup** — all data lives in `instance/database.db`; back it up by copying that file while the server is stopped (or use `sqlite3 instance/database.db ".backup backup.db"` while running).
- **Product images** — point to `static/images/README.md` (12 filename slots).
- **Testing** — `python test_validation.py`.

## Edge cases a weaker model would miss
- **Do NOT delete the dev path.** `FLASK_DEBUG=1` must still give the auto-reloading dev server; waitress has no reloader and makes iteration painful. The branch above keeps both.
- **waitress, not gunicorn** — gunicorn doesn't run on Windows (no `fcntl`). This machine and likely the deployment box are Windows 11.
- **`host='0.0.0.0'` is deliberate** — the point of production serving is that store machines on the LAN can reach it. But say so in the README so the user knows it's network-exposed, and note Windows Firewall will prompt to allow inbound on first run.
- **SQLite + waitress's default 4 threads is fine** at this scale, but SQLite locks on concurrent writes; do not raise the thread count or add `processes` — with this traffic (a handful of stores) the defaults hold. If you want, note it: `# ponytail: waitress defaults + SQLite; move to Postgres if stores > dozens`.
- **`SECRET_KEY` rotation logs everyone out** — mention in the README table so it isn't reported as a bug.
- **The default GoldAPI key baked into app.py line 58 is rate-limited and was previously exposed client-side** — the README should tell the operator to get their own free key at goldapi.io and set `GOLDAPI_KEY`. Do not print the baked-in key in the README.
- **README claims must match the code** — e.g. the admin seed only runs when `ADMIN_PASSWORD` is set AND no `admin` user exists (app.py lines 26–32); it does not reset an existing admin's password. Say that, or the operator will set the var, see no change, and file a bug.

## Acceptance criteria
1. `pip install -r requirements.txt` succeeds.
2. `python app.py` (no env vars) starts waitress on port 8000; the app is reachable at `http://localhost:8000`, login/calculator/submit all work.
3. `set FLASK_DEBUG=1 && python app.py` still starts the Flask dev server on port 5000 with the debugger.
4. `set PORT=9000 && python app.py` serves on 9000.
5. From another device on the same network (or `http://<machine-LAN-IP>:8000` locally), the app responds.
6. README.md exists; every env var it documents appears in `app.py` (`grep os.environ app.py` cross-check), and every `os.environ` read in app.py is documented.
