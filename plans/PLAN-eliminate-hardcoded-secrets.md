# PLAN: Eliminate hardcoded secrets + env/doc hardening

## Rank: 4 of 5

## Status (as of 2026-07-08)

**Already done in committed code** — do not redo these steps:

- Git repo initialized with `.gitignore` excluding `instance/`, `.env`, `venv/`
- Hardcoded GoldAPI fallback removed: `GOLDAPI_KEY = os.environ.get('GOLDAPI_KEY')` in `app.py` line 125
- Production refuses to start without `SECRET_KEY` (see `app.py` lines 603–607)
- `.env.example` exists with `SECRET_KEY`, `ADMIN_PASSWORD`, `GOLDAPI_KEY`, `FLASK_DEBUG`, `PORT`
- `python-dotenv` added to `requirements.txt`; `app.py` calls `load_dotenv()` at import (lines 1–2)
- `DATABASE_URL` override exists for tests (line 14)

**Still open** — this plan covers only what remains.

## Goal

Close the last security and configuration gaps:

1. **Git history still contains the old GoldAPI key** in commits `f00b1e9`, `91717b8`, and `a1cb400`. If you ever push this repo to GitHub (even a private repo), the key is recoverable from history. Treat it as compromised until revoked and history is scrubbed or the repo stays local-only forever.
2. **README contradicts the code** — README line 26 says the app does not auto-load `.env`, but `app.py` now calls `load_dotenv()`. A weaker model following README will manually `set` vars unnecessarily, or miss that `.env` already works.
3. **Large uncommitted diff** — category expansion, images, and template changes are not committed. No rollback point for the work in progress.

## Files to touch

- `README.md`
- `.env.example` (optional one-line comment)
- No code changes required unless you choose the git-history rewrite path (see Step 2 Option B)

## Step-by-step

### Step 1 — Revoke the compromised GoldAPI key (manual, do first)

Run:

```powershell
cd "c:\Users\user\Documents\second brain\Efforts\diamond-calculator"
git log --all -S "goldapi-eb915d55941859c5bec9d3d1cbaff238" --oneline
```

If that prints any commits (it will — at minimum `f00b1e9`), the key `goldapi-eb915d55941859c5bec9d3d1cbaff238-io` was committed and must be considered leaked.

1. Log into https://goldapi.io
2. Revoke that key
3. Generate a new key
4. Put the new key only in your local `.env` file (never in source code):

```
GOLDAPI_KEY=your-new-key-here
```

**Edge case:** `load_dotenv()` runs before any other config reads, so a `.env` file in the project root is loaded automatically on `python app.py`. You do not need `set GOLDAPI_KEY=...` in PowerShell if `.env` exists.

### Step 2 — Decide what to do about git history

**Option A — repo stays local-only (simplest):** Revoke the key (Step 1) and stop. History still has the old key string, but nobody can fetch it if you never push. Document this decision in your own notes.

**Option B — you will push to a remote (recommended if unsure):** Rewrite history to remove the key string. Only do this if you have not already pushed these commits to a shared remote, OR you are willing to force-push and coordinate with anyone else who cloned the repo.

```powershell
# Install git-filter-repo if needed: pip install git-filter-repo
git filter-repo --replace-text <(echo "goldapi-eb915d55941859c5bec9d3d1cbaff238-io==>REDACTED") --force
```

On Windows without bash, create a file `replacements.txt`:

```
goldapi-eb915d55941859c5bec9d3d1cbaff238-io==>REDACTED
```

Then:

```powershell
git filter-repo --replace-text replacements.txt --force
del replacements.txt
```

**Edge case:** `git filter-repo --force` rewrites all commit hashes. Any existing remote will need `git push --force` afterward. Do not use `--force` push to `main` on a shared repo without telling collaborators.

### Step 3 — Fix README environment-variable docs

In `README.md`, find this block (around line 26):

```
Copy `.env.example` to `.env` and fill in real values for local dev (the app does not auto-load `.env` — use `set VAR=value` on Windows or export it in your shell before running, or install `python-dotenv` if you want auto-loading).
```

Replace with:

```
Copy `.env.example` to `.env` and fill in real values for local dev. The app auto-loads `.env` on startup via `python-dotenv` (see `load_dotenv()` at the top of `app.py`). Shell `set`/`export` still works and overrides `.env` if both are set.
```

Also fix the production host documentation. README line 40 says:

```
This serves the application on `http://0.0.0.0:8000` via Waitress.
```

But `app.py` line 611 actually binds to `127.0.0.1`:

```python
serve(app, host='127.0.0.1', port=port)
```

Change README line 40–41 to:

```
This serves the application on `http://127.0.0.1:8000` via Waitress (localhost only — not exposed to the LAN unless you change `host` in `app.py`).
```

Remove the sentence about Windows Firewall and local network exposure — it is wrong for the current code.

Add `DATABASE_URL` to the environment variables table (used by tests only in normal operation):

| `DATABASE_URL` | no | Override SQLite path; `test_routes.py` sets `sqlite:///:memory:` |

### Step 4 — Verify `.env.example` is complete

Confirm `.env.example` contains (it should already):

```
SECRET_KEY=
ADMIN_PASSWORD=
GOLDAPI_KEY=
FLASK_DEBUG=1
PORT=8000
```

Optional: add a comment line at the top:

```
# Copy to .env and fill in. Loaded automatically by python-dotenv.
```

Do not put real secrets in `.env.example`.

### Step 5 — Commit current work as a checkpoint

Before executing other plans, commit the in-progress category expansion so git protects you:

```powershell
cd "c:\Users\user\Documents\second brain\Efforts\diamond-calculator"
git status
git add app.py requirements.txt static/ templates/ static/images/chain-*.jpg
git add README.md .env.example
# Do NOT git add .env, instance/, or image/ unless you explicitly want source photos in git
git commit -m "feat: five-category calculator expansion with chain images and dotenv loading"
```

**Edge case:** `instance/database.db` must stay out of git (`.gitignore` covers it). Run `git status` before commit and confirm `instance/` does not appear under "Changes to be committed".

## Edge cases found while exploring (do not skip these)

- **`db.create_all()` and `create_initial_users()` run at import time** (`app.py` lines 55–57). Importing `app` from a REPL with `ADMIN_PASSWORD` set will seed the admin account. This is unchanged and unrelated to secrets, but do not `python -c "import app"` casually with production env vars loaded.
- **Git history retention:** Even after Step 2 Option B, anyone who already cloned before the rewrite still has the old history locally. Revocation on goldapi.io (Step 1) is the real fix; history scrub is defense in depth.
- **`.env` in `.gitignore`:** If you create `.env` with the new key, `git status` must not show it as trackable. If it does, `.gitignore` is broken — fix before committing.
- **`SECRET_KEY` dev default still exists** (`dev-secret-key-change-in-prod`). This is acceptable for `FLASK_DEBUG=1` only. Production path already blocks startup without `SECRET_KEY`. Do not remove the dev default — that would break local dev per README.

## Acceptance criteria

1. `rg "goldapi-eb915d55941859c5bec9d3d1cbaff238" app.py` returns nothing (already true — verify, do not regress).
2. The old GoldAPI key is revoked on goldapi.io (manual check — plan cannot verify).
3. README accurately describes `.env` auto-loading and `127.0.0.1` bind address — no mention of `0.0.0.0` unless you intentionally change `app.py` to match.
4. `git status` shows a clean working tree after Step 5 commit (or only intentionally untracked files like `image/` source photos).
5. Running with `FLASK_DEBUG=1` and a `.env` file containing `GOLDAPI_KEY=<new-key>`: log in, hit `/api/prices`, response JSON has `"source": "live"` (or `"fallback"` if API is down — but not HTTP 500).
6. Running without `FLASK_DEBUG` and without `SECRET_KEY`: app exits with "Refusing to start in production mode without SECRET_KEY".
7. If you chose Step 2 Option B: `git log --all -S "goldapi-eb915d55941859c5bec9d3d1cbaff238" --oneline` returns nothing.
