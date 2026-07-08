# PLAN: Login brute-force protection + pagination for growing tables

## Rank: 5 of 5

## Goal

Two independent, smaller hardening items that both matter once this tool has been in real use for a while:

**A. `/login` has no protection against repeated password guessing.** There is no lockout, no delay, no attempt counter anywhere in `app.py`. The server binds to `0.0.0.0` in production per the README ("Since it binds to `0.0.0.0`, it will be exposed to your local network"), so anyone on the same network as the server can throw unlimited password guesses at `/login`, particularly at the `admin` account, whose username is fixed and well-known (it's literally hardcoded as `'admin'` in `create_initial_users()`).

**B. `/admin` and `/history` load every submission with no pagination.** `admin()` does `Submission.query.order_by(Submission.created_at.desc()).all()` and `history()` does the same filtered by user. Today, with a near-empty database, this is fine. After months of real store usage, `/admin` will be loading and rendering every order ever placed, by every store, on a single page, on every load. This is a slow-motion problem, not an urgent one, but it's cheap to fix now versus expensive to fix later (once you're also dealing with real users hitting a slow page).

## Files to touch

- `Efforts/diamond-calculator/app.py`
- `Efforts/diamond-calculator/templates/admin.html`
- `Efforts/diamond-calculator/templates/history.html`
- `Efforts/diamond-calculator/static/js/i18n.js`

## Step-by-step

### Part A — Login rate limiting (no new dependency)

This project has a minimal `requirements.txt` (Flask, Flask-SQLAlchemy, Flask-Login, Werkzeug, Flask-WTF, waitress) and runs as a single Waitress process (not a multi-process/multi-worker deployment — confirmed by reading the bottom of `app.py`: `serve(app, host='127.0.0.1', port=port)` with no worker count configured, which is Waitress's single-process default). That means a simple in-process, in-memory counter is a legitimate, correctly-scoped solution here — do not reach for `Flask-Limiter` or Redis for a single-process internal tool; that would be solving a distributed-systems problem this app doesn't have.

**In `app.py`**, add near the top, after the existing cache-related globals (`_price_cache`, `PRICE_TTL_SECONDS`):

```python
_login_attempts = {}  # username -> (fail_count, locked_until_timestamp)
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 300  # 5 minutes

def is_locked_out(username):
    entry = _login_attempts.get(username)
    if not entry:
        return False
    fail_count, locked_until = entry
    if fail_count >= LOGIN_MAX_ATTEMPTS and time.time() < locked_until:
        return True
    if fail_count >= LOGIN_MAX_ATTEMPTS and time.time() >= locked_until:
        _login_attempts.pop(username, None)  # lockout expired, reset
    return False

def record_login_failure(username):
    fail_count, _ = _login_attempts.get(username, (0, 0))
    fail_count += 1
    locked_until = time.time() + LOGIN_LOCKOUT_SECONDS if fail_count >= LOGIN_MAX_ATTEMPTS else 0
    _login_attempts[username] = (fail_count, locked_until)

def record_login_success(username):
    _login_attempts.pop(username, None)
```

Find the existing `login()` route:

```python
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                return redirect(next_page)
            if user.role == 'admin':
                return redirect(url_for('admin'))
            return redirect(url_for('calculator'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')
```

Replace with:

```python
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username and is_locked_out(username):
            flash('登入失敗次數過多，請 5 分鐘後再試。 (Too many failed attempts, try again in 5 minutes.)')
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            record_login_success(username)
            login_user(user)
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                return redirect(next_page)
            if user.role == 'admin':
                return redirect(url_for('admin'))
            return redirect(url_for('calculator'))
        else:
            if username:
                record_login_failure(username)
            flash('Invalid username or password')
    return render_template('login.html')
```

**Edge case:** the lockout key is the submitted `username` string, not the resolved `User` object — this is intentional. It means the lockout applies even when the username doesn't exist in the database, which is correct (you want to rate-limit guesses at usernames too, not just password guesses against known accounts — otherwise an attacker just probes for valid usernames with zero friction, since only real accounts would ever get locked). Do not change this to key off `user.id`, which would only work after `User.query.filter_by(...)` already found a match.

**Edge case:** `_login_attempts` is a plain in-memory `dict` at module scope — it resets to empty every time the process restarts. This is a deliberate, acceptable tradeoff for a single small internal tool (restarting the server to clear a lockout is a fine manual escape hatch, and there's no requirement here to persist lockouts across restarts). Do not add this to the database — that would be solving a problem this app doesn't have and would add migration complexity for no real benefit.

### Part B — Pagination for `/admin` and `/history`

Flask-SQLAlchemy ships `.paginate()` on any query — no new dependency needed (confirmed available since `Flask-SQLAlchemy==3.1.1` is already in `requirements.txt`, and this method has existed since Flask-SQLAlchemy 2.1).

**In `app.py`**, find:

```python
@app.route('/history')
@login_required
def history():
    submissions = Submission.query.filter_by(user_id=current_user.id).order_by(Submission.created_at.desc()).all()
    return render_template('history.html', submissions=submissions)
```

Replace with:

```python
PAGE_SIZE = 25

@app.route('/history')
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    pagination = Submission.query.filter_by(user_id=current_user.id) \
        .order_by(Submission.created_at.desc()) \
        .paginate(page=page, per_page=PAGE_SIZE, error_out=False)
    return render_template('history.html', submissions=pagination.items, pagination=pagination)
```

Find:

```python
@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('calculator'))
    submissions = Submission.query.order_by(Submission.created_at.desc()).all()
    return render_template('admin.html', submissions=submissions)
```

Replace with:

```python
@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('calculator'))
    page = request.args.get('page', 1, type=int)
    pagination = Submission.query.order_by(Submission.created_at.desc()) \
        .paginate(page=page, per_page=PAGE_SIZE, error_out=False)
    return render_template('admin.html', submissions=pagination.items, pagination=pagination)
```

**Edge case:** `error_out=False` is required, not optional. The Flask-SQLAlchemy default is `error_out=True`, which raises a 404 if the requested page number is out of range (e.g., someone bookmarks `?page=3` and then enough orders get deleted that there are only 2 pages left). `error_out=False` instead just returns an empty `.items` list for out-of-range pages, which the templates below already handle via their existing `{% else %}` "no records" branch — do not skip this parameter or you'll turn "list is now shorter" into a user-facing 404.

**In `templates/history.html`**, right after the closing `</table>` tag and before the closing `</div>`, add pagination controls:

```html
{% if pagination.pages > 1 %}
<div class="pagination" style="text-align:center; margin-top: 20px;">
  {% if pagination.has_prev %}
    <a href="{{ url_for('history', page=pagination.prev_num) }}">&laquo; <span data-i18n="pg_prev">上一頁</span></a>
  {% endif %}
  <span data-i18n="pg_page">第</span> {{ pagination.page }} / {{ pagination.pages }} <span data-i18n="pg_of">頁</span>
  {% if pagination.has_next %}
    <a href="{{ url_for('history', page=pagination.next_num) }}"><span data-i18n="pg_next">下一頁</span> &raquo;</a>
  {% endif %}
</div>
{% endif %}
```

**In `templates/admin.html`**, do the same thing but with `url_for('admin', page=...)` instead of `url_for('history', page=...)`.

**In `static/js/i18n.js`**, add to both `zh` and `en` blocks (near the `status_*` keys is a reasonable spot):

`zh`: `"pg_prev": "上一頁", "pg_page": "第", "pg_of": "頁", "pg_next": "下一頁",`

`en`: `"pg_prev": "Prev", "pg_page": "Page", "pg_of": "of", "pg_next": "Next",`

(These are static server-rendered pagination links, not dynamically updated by `applyLanguage()`'s `data-i18n` sweep on click — that sweep only re-labels elements already in the DOM, and it does run on these too since they have `data-i18n` attributes, so this works correctly without extra JS. No further script.js changes needed for Part B.)

## Edge cases found while exploring that a weaker model would miss

- **`PAGE_SIZE = 25` is defined once, above both routes, and reused by both** — do not duplicate the constant per-route. Place it right after the existing `RING_SIZE_MIN, RING_SIZE_MAX = 5, 25` line (or anywhere else at module scope before both route definitions) so both `history()` and `admin()` can reference it.
- **The admin status-update JavaScript in `templates/admin.html` (the inline `<script>` block at the bottom that handles `.status-select` change events) selects rows by `document.querySelectorAll('.status-select')`.** Since pagination now means only `PAGE_SIZE` rows are on the page at once, this still works correctly with no changes needed — it only ever needed to operate on rows currently in the DOM, and that's still true, there are just fewer of them per page now. Do not "fix" this file for pagination; it already works.
- **`history.html`'s delete button JS (`document.querySelectorAll('.delete-btn')`) has the same property** — no changes needed there either, for the same reason.
- **Do not change `PAGE_SIZE` to something tiny like 5 "to make testing easier" and forget to change it back.** 25 is a reasonable default for an admin table; leave it at 25 unless you have an actual UX reason to change it (e.g. Larry explicitly asks for a different page size).
- **This plan does not add pagination anywhere else** (there's no other unbounded list in the app — `/api/prices` returns a fixed small dict, not a query result). Don't over-apply this pattern to routes that don't need it.

## Acceptance criteria

1. Attempting to log in with a wrong password 5 times in a row for the same username causes the 6th attempt (even with the correct password) to show the lockout message instead of logging in.
2. Waiting 5 minutes (or manually adjusting `LOGIN_LOCKOUT_SECONDS` down to `5` temporarily for a fast manual test, then reverting) and retrying with the correct password succeeds and clears the lockout.
3. A successful login at any point resets that username's failure counter (log in correctly once, then confirm 5 *new* failed attempts are required to trigger another lockout — not fewer, proving `record_login_success` actually clears state).
4. With more than 25 submissions in the test/dev database for a single store, `/history` shows only 25 rows and a "第 1 / N 頁" pagination control at the bottom; clicking "下一頁" navigates to `?page=2` and shows the next batch, correctly ordered (still newest-first).
5. Same behavior verified for `/admin` with more than 25 total submissions across all stores.
6. Requesting `/admin?page=999` (a page number far beyond the actual data) does not 404 or 500 — it renders the page with the existing "尚無任何紀錄" (no records) empty state.
7. `python test_routes.py` (from the test-coverage plan, if already implemented) still passes — pagination changes must not break the existing route behavior for `/submit`, `/delete`, `/edit`, or auth checks.
