# PLAN: Login brute-force protection + pagination + remaining ops hardening

## Rank: 5 of 5

## Status (as of 2026-07-08)

**Already done (commit `ca1ab42` and later):**

- Login brute-force lockout: `_login_attempts`, `is_locked_out()`, `record_login_failure/success()` in `app.py` lines 150–172, wired in `login()` lines 407–423.
- Pagination: `PAGE_SIZE = 25`, `.paginate(..., error_out=False)` on `/history` and `/admin` (lines 507–521).
- Pagination UI in `templates/admin.html` and `templates/history.html` with i18n keys `pg_prev`, `pg_page`, `pg_of`, `pg_next`.
- Admin status dropdown JS works on current page only — no changes needed for pagination.

**Still open:**

- **`/register` has no rate limiting** — open self-registration with unlimited attempts enables username enumeration and store spam. Lower risk than `/login` (no admin password) but same LAN exposure if server is reachable.
- **README host binding wrong** — partially addressed in PLAN-eliminate-hardcoded-secrets Step 3; if not done yet, do it here or cross-reference.
- **Login lockout untested until PLAN-route-test-coverage Test 16 is added** — implementation exists, verification pending.

## Goal

Close remaining operational gaps that matter once the tool runs on a store network for months:

**A.** Add registration rate limiting using the same in-memory pattern as login (no new dependencies).

**B.** Verify pagination and lockout still work after recent category expansion commits.

This plan does **not** re-implement login lockout or pagination — only finish what's missing.

## Files to touch

- `app.py`
- `templates/register.html` (only if you add a visible lockout message — optional, flash may suffice)
- `README.md` (register abuse note — one sentence)

## Step-by-step

### Part A — Registration rate limiting

**In `app.py`**, after the login attempt helpers (after line 172), add:

```python
_register_attempts = {}  # ip -> (fail_count, locked_until_timestamp)
REGISTER_MAX_ATTEMPTS = 10
REGISTER_LOCKOUT_SECONDS = 600  # 10 minutes

def _client_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()

def is_register_locked_out():
    entry = _register_attempts.get(_client_ip())
    if not entry:
        return False
    fail_count, locked_until = entry
    if fail_count >= REGISTER_MAX_ATTEMPTS and time.time() < locked_until:
        return True
    if fail_count >= REGISTER_MAX_ATTEMPTS and time.time() >= locked_until:
        _register_attempts.pop(_client_ip(), None)
    return False

def record_register_failure():
    ip = _client_ip()
    fail_count, _ = _register_attempts.get(ip, (0, 0))
    fail_count += 1
    locked_until = time.time() + REGISTER_LOCKOUT_SECONDS if fail_count >= REGISTER_MAX_ATTEMPTS else 0
    _register_attempts[ip] = (fail_count, locked_until)

def record_register_success():
    _register_attempts.pop(_client_ip(), None)
```

Find `register()` route (line 427). At start of POST handling, add lockout check:

```python
    if request.method == 'POST':
        if is_register_locked_out():
            flash('註冊嘗試次數過多，請 10 分鐘後再試。 (Too many registration attempts, try again in 10 minutes.)')
            return render_template('register.html')

        store_name = request.form.get('store_name')
        username = request.form.get('username')
        password = request.form.get('password')
```

On successful registration (before redirect to login), add:

```python
            record_register_success()
            flash('註冊成功！請登入。')
```

On failure paths, call `record_register_failure()`:

- When username already exists (before redirect)
- When `db.session.commit()` raises (in except block)

Example for duplicate username block:

```python
        if User.query.filter_by(username=username).first():
            record_register_failure()
            flash('該帳號已被使用，請選擇其他帳號。')
            return redirect(url_for('register'))
```

**Edge case:** Key by IP, not username — prevents spamming new username attempts from one machine. Same tradeoff as login lockout: in-memory, resets on server restart. Acceptable for single-process Waitress deployment.

**Edge case:** `_client_ip()` behind reverse proxy — `X-Forwarded-For` first hop used if present. App currently binds `127.0.0.1` only — no proxy in default setup. Do not over-engineer.

**Edge case:** Successful registration clears IP counter — someone who mistyped 9 times then succeeds can register again later same day. Good.

### Part B — Manual verification of existing features (regression check)

After category expansion, confirm pagination and lockout were not broken:

**Login lockout (5 min):**

```powershell
set FLASK_DEBUG=1
python app.py
```

In browser, attempt login as any username with wrong password 5 times. 6th attempt (even with correct password) shows bilingual lockout flash.

**Pagination:**

Seed 26+ test submissions (SQLite insert or repeated submits). Confirm `/history` and `/admin` show 25 rows and page 2 link. `/admin?page=999` shows empty table, not HTTP 404.

If PLAN-route-test-coverage Test 16 is implemented, lockout is also automated — prefer that for repeat verification.

### Part C — README note

Add under "First run" or new "Security notes" subsection:

```
Registration and login apply in-memory rate limits (per-username for login, per-IP for registration). Limits reset when the server process restarts.
```

## Edge cases found while exploring (do not skip these)

- **Do not reuse `_login_attempts` for register** — different key spaces (username vs IP) and different thresholds (5 vs 10). Separate dicts avoid accidental cross-lockout.
- **Register route has no `@login_required`** — intentional (new stores self-register). Rate limit is the only abuse control besides username uniqueness.
- **`record_register_failure()` on duplicate username** counts toward lockout even though the attacker learned the username exists — this is acceptable; slows enumeration.
- **Pagination `error_out=False` is already set** — do not change to `True` or bookmarked page URLs 404 when data shrinks.
- **Admin inline status JS** (`templates/admin.html` bottom script) only affects visible rows — still correct with pagination; do not add "select all pages" functionality in this plan.
- **Waitress single process** (`serve(app, ...)` no threads arg) — in-memory counters are thread-safe enough for default Waitress. If you later add multiple workers, these counters break — document that limitation in README rather than adding Redis now.

## Acceptance criteria

1. Login lockout: 5 failed attempts → 6th shows lockout message (manual or Test 16 automated).
2. Successful login clears failure counter for that username (manual: 4 fails, 1 success, 4 more fails needed to lock again).
3. Registration lockout: 10 failed attempts (duplicate usernames or DB errors) from same machine → 11th shows registration lockout flash without creating user.
4. Successful registration clears IP failure counter.
5. `/admin` with 26+ submissions shows pagination; page 2 works; `?page=999` returns 200 with empty state.
6. `/history` same behavior for a store with 26+ own submissions.
7. `python test_routes.py` still passes after register changes (register tests not required in this plan, but must not break existing 16 tests).
8. README mentions in-memory rate limit behavior and server restart reset.

## Prerequisite

Execute **PLAN-route-test-coverage** first (Test 16 covers login lockout). This plan can run in parallel with PLAN-eliminate-hardcoded-secrets README fixes — no file conflicts except `app.py` and `README.md`; if both touch README, merge sentences rather than duplicating.
