# PLAN: CSRF protection + secrets/config hardening

## Goal
Every state-changing endpoint (`/submit`, `/edit/<id>`, `/delete/<id>`, `/admin/update_status/<id>`, `/login`, `/register`) is CSRF-able today: session-cookie auth, no token. A malicious page can delete a store's pending orders or flip admin statuses with a hidden form/fetch. Additionally: the Flask `SECRET_KEY` is hardcoded (`app.py` line 8), default admin credentials (`admin/admin123`, `imprint/imprint`) are created automatically AND printed on the public login page (`templates/login.html` lines 76–79), and `debug=True` is hardcoded (`app.py` line 185).

## Exact files to touch
- `requirements.txt` — add `Flask-WTF==1.2.1`.
- `app.py` — enable CSRFProtect, env-based SECRET_KEY, env-gated seeding, env-gated debug.
- `templates/base.html` — expose the CSRF token in a meta tag.
- `templates/login.html` — add hidden token to the form; delete the credentials hint.
- `templates/register.html` — add hidden token to the form.
- `static/js/script.js` — send `X-CSRFToken` header on the `/submit` fetch.
- `templates/history.html` — send the header on the `/edit` and `/delete` fetches (inline script).
- `templates/admin.html` — send the header on the `/admin/update_status` fetch (inline script).

## Step-by-step implementation

### 1. Install and enable
- Add `Flask-WTF==1.2.1` to `requirements.txt`, run `pip install -r requirements.txt`.
- In `app.py`:
  ```python
  from flask_wtf import CSRFProtect
  ...
  app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
  csrf = CSRFProtect(app)
  ```

### 2. HTML forms (login, register)
Both are standalone pages (they do NOT extend base.html). Inside each `<form method="POST" ...>` add as the first child:
```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
```

### 3. JSON fetches — token via meta tag
- In `templates/base.html` `<head>` (inside the existing head, before `{% block extra_head %}`):
  ```html
  <meta name="csrf-token" content="{{ csrf_token() }}">
  ```
- There are FOUR fetch call sites that need the header. In each, add to `headers`:
  ```js
  "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').content
  ```
  1. `static/js/script.js` — the `/submit` fetch (~line 396).
  2. `templates/history.html` inline script — the `/edit/${id}` fetch (~line 128).
  3. `templates/history.html` inline script — the `/delete/${id}` fetch (~line 151). NOTE: this fetch currently has NO `headers` object at all (`fetch(url, { method: 'POST' })`) — you must add one, not just extend one.
  4. `templates/admin.html` inline script — the `/admin/update_status/${id}` fetch (~line 60).

### 4. Seeding and default credentials
Replace `create_initial_users()` in `app.py` with an env-gated version:
```python
def create_initial_users():
    admin_password = os.environ.get('ADMIN_PASSWORD')
    if admin_password and User.query.filter_by(username='admin').first() is None:
        db.session.add(User(username='admin',
                            password_hash=generate_password_hash(admin_password),
                            role='admin', store_name='Admin HQ'))
        db.session.commit()
```
- Remove the `store_a` and `imprint` seed blocks entirely.
- Delete the credentials paragraph from `templates/login.html` (lines 76–79, the `管理員預設帳號...` block).
- IMPORTANT: the existing `instance/database.db` already contains `admin/admin123`, `imprint/imprint`, `store_a/store123`. Seeding changes do NOT remove them. Do NOT delete these users from the DB in code (store_a may own submissions; the FK has no cascade and orphaned rows would crash the admin page via `sub.user.store_name`). Instead print a clear note in the final report telling the user to change those passwords, e.g. via flask shell:
  ```python
  from app import app; from models import db, User
  from werkzeug.security import generate_password_hash
  with app.app_context():
      for name in ('admin', 'imprint', 'store_a'):
          u = User.query.filter_by(username=name).first()
          if u: u.password_hash = generate_password_hash('NEW-PASSWORD-HERE')
      db.session.commit()
  ```

### 5. Debug flag
`app.py` last line:
```python
app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
```

## Edge cases a weaker model would miss
- **CSRFProtect breaks EVERY POST at once.** The moment it's enabled, all six POST endpoints return 400 until their callers send tokens. The delete fetch in history.html is the easy one to miss because it has no headers object today — grep for `method: 'POST'` and `method: "POST"` (both quote styles are present in this codebase) and confirm every call site is covered.
- **login/register don't extend base.html**, so the meta-tag approach doesn't reach them — they need the hidden form input directly. Conversely, base.html's meta tag only helps pages that extend it.
- **`csrf_token()` is available in templates automatically** once CSRFProtect is initialized — no route changes needed to pass it.
- **Changing SECRET_KEY invalidates all existing sessions** (everyone gets logged out once when the env var is first set). Expected; mention it, don't "fix" it.
- **Flash-message wording**: CSRF failures on login/register render Flask-WTF's default 400 page, not a flash. Acceptable for this app; don't build custom error handlers.
- **Do not remove the dev fallback SECRET_KEY** — the app must still boot with zero env vars for local dev. The hardening is that production can override it, and the seeded admin only exists when `ADMIN_PASSWORD` is set.
- **Keep `imprint` removal to seeding only** — the account in the live DB is the user's to clean up; code shouldn't silently delete an admin account they may be using.

## Acceptance criteria
1. `pip install -r requirements.txt` succeeds; app boots with no env vars set.
2. With the server running and a logged-in browser session, all four UI flows still work: calculator submit, history edit, history delete, admin status change. (This proves all four fetch sites got the header.)
3. Login and register forms still work.
4. `curl -X POST http://127.0.0.1:5000/submit -H "Content-Type: application/json" -d "{}" --cookie "session=<valid session cookie>"` returns 400 (CSRF missing), NOT 200/500.
5. Fresh-DB check: delete/rename `instance/database.db`, start the app with no `ADMIN_PASSWORD` → no users are created; start with `ADMIN_PASSWORD=test123` → only `admin` exists and can log in. Restore the original DB afterwards.
6. `templates/login.html` no longer contains any password strings; `grep -n "admin123\|store123\|imprint" templates app.py` returns nothing.
7. `python app.py` runs with debug OFF by default (no Werkzeug debugger on error pages); `FLASK_DEBUG=1 python app.py` enables it.
