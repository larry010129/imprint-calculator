# PLAN: Eliminate hardcoded secrets + add version control safety net

## Rank: 1 of 5 (do this first)

## Goal

Two problems, fixed together because the second protects you while you do the first:

1. `app.py` has a **live GoldAPI key hardcoded as a source-code default** (`goldapi-eb915d55941859c5bec9d3d1cbaff238-io`). Anyone who reads this file — or any copy of it that ends up in a git remote, a zip you send someone, a screenshot, a pasted snippet into an AI chat — has your live key. They can spend your GoldAPI quota or exhaust your plan.
2. This project has **no git repository at all** (`git status` returns "not a git repository"). There is no rollback if any of the next 4 plans (which touch auth config, the database schema, and delete files) goes wrong. You are currently one bad edit away from having no way back.

This plan fixes both, in order: version control first (so everything after this point is reversible), then the secret.

## Files to touch

- `Efforts/diamond-calculator/.gitignore` (new file)
- `Efforts/diamond-calculator/app.py`
- `Efforts/diamond-calculator/README.md`
- `Efforts/diamond-calculator/.env.example` (new file)

## Step-by-step

### Step 0 — Initialize git and commit the current state as a baseline

Run from `Efforts/diamond-calculator/`:

```bash
git init
```

Create `.gitignore` with exactly this content (this repo has real user data and Python caches sitting in it right now — `instance/database.db` and `__pycache__/` must never be committed):

```
__pycache__/
*.pyc
instance/
.env
venv/
*.egg-info/
```

Then:

```bash
git add -A
git commit -m "Initial commit: baseline before secret rotation and hardening"
```

**Edge case a weaker model would miss:** `instance/database.db` already exists on disk with data in it (16 KB as of this plan being written — verify with `ls -la instance/` before you start; if it is larger than a few KB, it may contain real store submissions, so do NOT delete it, only exclude it from git via `.gitignore`). If `git add -A` runs *before* `.gitignore` exists, the database file will get staged. Create `.gitignore` **before** running `git add -A`. If you make this mistake, run `git rm --cached instance/database.db` before committing.

### Step 1 — Rotate the leaked GoldAPI key

The key `goldapi-eb915d55941859c5bec9d3d1cbaff238-io` currently sitting in `app.py` line ~77 must be treated as **compromised** (it's been in a plaintext file with no access control). Log into https://goldapi.io, revoke that key, and generate a new one. Do NOT put the new key back into the source file — that's the whole point of this plan.

### Step 2 — Remove the hardcoded fallback from `app.py`

Find this line:

```python
GOLDAPI_KEY = os.environ.get('GOLDAPI_KEY', 'goldapi-eb915d55941859c5bec9d3d1cbaff238-io')
```

Replace it with:

```python
GOLDAPI_KEY = os.environ.get('GOLDAPI_KEY')
```

**Edge case:** `get_metal_prices()` already wraps every GoldAPI call in `try/except Exception` and falls back to `FALLBACK_TWD_PER_GRAM` on any failure (see the loop in `get_metal_prices()`). If `GOLDAPI_KEY` is `None`, the request will fail (401 from GoldAPI, or the request module may error building the header) and get caught by that same `except Exception`, so the app will **not crash** — it will just silently run on fallback prices, same as today when the API times out. This is safe. Confirm this behavior after the change: unset `GOLDAPI_KEY`, run the app, hit `/api/prices` while logged in, and confirm you get `"source": "fallback"` in the JSON response instead of a 500 error.

### Step 3 — Enforce `SECRET_KEY` in production, not just document it

`app.py` currently has:

```python
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
```

The README already tells you to set `SECRET_KEY` in production, but the app happily starts and signs sessions/CSRF tokens with the well-known default if you forget. Since `SECRET_KEY` also signs CSRF tokens (Flask-WTF reads it from `app.config['SECRET_KEY']`), running with the default in production means anyone who has read this open-source-style codebase can forge valid session cookies and CSRF tokens for your app.

Find the bottom of `app.py`:

```python
if __name__ == '__main__':
    if os.environ.get('FLASK_DEBUG') == '1':
        app.run(debug=True)
    else:
        from waitress import serve
        port = int(os.environ.get('PORT', 8000))
        print(f"Serving on http://127.0.0.1:{port}")
        serve(app, host='127.0.0.1', port=port)
```

Change it to fail loudly instead of silently running insecurely:

```python
if __name__ == '__main__':
    if os.environ.get('FLASK_DEBUG') == '1':
        app.run(debug=True)
    else:
        if os.environ.get('SECRET_KEY') is None:
            raise SystemExit(
                "Refusing to start in production mode without SECRET_KEY set. "
                "Set FLASK_DEBUG=1 for local dev, or set SECRET_KEY for production."
            )
        from waitress import serve
        port = int(os.environ.get('PORT', 8000))
        print(f"Serving on http://127.0.0.1:{port}")
        serve(app, host='127.0.0.1', port=port)
```

**Edge case:** this check must live inside the `else` branch (the non-debug/production path), not at module level. Putting it at module level would break local dev (`FLASK_DEBUG=1`) for anyone who hasn't set `SECRET_KEY`, which is the normal dev case per the README's own dev instructions.

### Step 4 — Document the env vars properly instead of relying on tribal knowledge

Create `Efforts/diamond-calculator/.env.example`:

```
SECRET_KEY=
ADMIN_PASSWORD=
GOLDAPI_KEY=
FLASK_DEBUG=1
PORT=8000
```

This file has no real values in it — it's a template so a future setup (yours or anyone else's) knows exactly which vars exist without reading `app.py`. It is safe to commit (it's already excluded from nothing since it contains no secrets — do NOT add it to `.gitignore`).

### Step 5 — Update README.md

In the "Environment variables" table, change the `GOLDAPI_KEY` row's "Purpose" cell from:

```
goldapi.io key for live metal prices; falls back to a built-in key, then to hardcoded fallback prices
```

to:

```
goldapi.io key for live metal prices; if unset, the app runs on hardcoded fallback prices (see FALLBACK_TWD_PER_GRAM in app.py) — there is no longer a built-in key
```

Add a line right after the table:

```
Copy `.env.example` to `.env` and fill in real values for local dev (the app does not auto-load `.env` — use `set VAR=value` on Windows or export it in your shell before running, or install `python-dotenv` if you want auto-loading).
```

### Step 6 — Commit

```bash
git add -A
git commit -m "Remove hardcoded GoldAPI key, enforce SECRET_KEY in production, add .gitignore and .env.example"
```

## Edge cases found while exploring (do not skip these)

- **`db.create_all()` and `create_initial_users()` run at import time**, not inside `if __name__ == '__main__':` (see lines ~53-55 of `app.py`). This means simply `import app` from anywhere (including a Python REPL, or the existing `test_validation.py`, which does `from app import validate_submission_fields`) will connect to and initialize `instance/database.db` and will seed an admin user **if `ADMIN_PASSWORD` happens to be set in your shell's environment at that moment**. This is not something this plan changes, but be aware of it: don't run ad-hoc `python -c "import app"` experiments with `ADMIN_PASSWORD` set unless you mean to create/touch the admin account.
- **`instance/database.db` is currently untracked by git and this plan's `.gitignore` keeps it that way.** That means git gives you no protection for the actual submission data — only for code. Continue following the README's existing backup instructions (`sqlite3 instance/database.db ".backup backup.db"`) separately from git.
- Do not commit `.env` if you create one for local secrets — it's already covered by the `.gitignore` pattern `.env` above, but double check with `git status` before your first commit after creating it.

## Acceptance criteria

1. `git log` shows at least 2 commits in `Efforts/diamond-calculator/`.
2. `git status` shows `instance/` and `__pycache__/` as ignored, not tracked (`git status --ignored` lists them under "Ignored files").
3. `grep -n "goldapi-eb915d55941859c5bec9d3d1cbaff238-io" app.py` returns nothing (the string is gone from the file).
4. The old key is revoked on goldapi.io's dashboard (manual verification — the plan cannot check this for you).
5. Running the app with `SECRET_KEY` unset and `FLASK_DEBUG` unset (production mode) exits immediately with the "Refusing to start..." message instead of serving.
6. Running the app with `FLASK_DEBUG=1` and `SECRET_KEY` unset still starts normally (dev mode unaffected).
7. Running the app with `GOLDAPI_KEY` unset and hitting `GET /api/prices` (while logged in) returns HTTP 200 with `"source": "fallback"` in the JSON body — no 500 error.
8. `.env.example` exists and is tracked by git (`git ls-files | grep .env.example` shows it); no file named `.env` is tracked (`git ls-files | grep -x .env` returns nothing).
