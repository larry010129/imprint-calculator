# PLAN: Fix wrong purity labels + finish leftovers from the hardening pass

## Goal
Five small, confirmed defects left behind by the last round of changes. Each is a few lines; together they fix a user-visible display bug on every table view, a broken fresh install, and two deprecation/UX loose ends.

1. **`label_purity` maps the wrong purity codes** (`app.py` line 56). It translates `{'18k', '14k', 'pt950'}` — but this app's gold values are `18k, 999, pt, silver925` (see `VALID_GOLDS`, app.py line 106, and `goldLabel` in `static/js/script.js` line 17). Result: every 純金999 / 鉑金 / 925銀 order displays as raw `999` / `pt` / `silver925` in History and Admin. `14k` and `pt950` can never occur.
2. **Fresh install is broken.** `app.py` imports `flask_wtf` (line 4) but `requirements.txt` doesn't list Flask-WTF. On a clean machine `pip install -r requirements.txt && python app.py` crashes with ModuleNotFoundError. (It works on this machine only because Flask-WTF 1.3.0 happens to be installed.)
3. **Unused `import requests`** (`app.py` line 5) — the pricing code uses stdlib `urllib.request`; `requests` is dead weight and another undeclared dependency that would break a fresh install the moment someone "fixes" an import order.
4. **`datetime.utcnow` deprecation** (`models.py` line 25) — deprecated since Python 3.12; this project runs 3.14. Emits DeprecationWarning and will eventually break.
5. **Login ignores `?next=`.** `@login_required` redirects to `/login?next=/history`, but `login()` (app.py lines 186–190) always sends providers to `/calculator`. Users lose their destination.

## Exact files to touch
- `app.py` — items 1, 3, 5.
- `requirements.txt` — item 2.
- `models.py` — item 4.

## Step-by-step implementation

### 1. Fix `label_purity` (app.py line 53–56)
Replace the dict with the app's real codes — copy the values from `goldLabel` in `static/js/script.js` line 17 exactly:
```python
@app.template_filter('label_purity')
def label_purity(purity):
    if not purity: return ''
    return {'18k': '18K金', '999': '純金999', 'pt': '鉑金 Pt', 'silver925': '925銀'}.get(purity, purity)
```

### 2. requirements.txt
Add one line (match the installed version):
```
Flask-WTF==1.3.0
```

### 3. Remove the unused import
Delete `import requests` (app.py line 5). Verify with `grep -n "requests" app.py` → zero matches afterward. Do NOT add `requests` to requirements instead — nothing uses it.

### 4. models.py — replace deprecated utcnow, keep storage identical
```python
from datetime import datetime, timezone
...
created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
```
This still stores **naive UTC**, byte-compatible with existing rows and with the `tz_taiwan` filter (which adds +8h to naive UTC). Do not store aware datetimes or local time — that would skew the +8h conversion for new rows.

### 5. Honor `?next=` in `login()` (app.py, success branch ~line 186)
```python
if user and check_password_hash(user.password_hash, password):
    login_user(user)
    next_page = request.args.get('next')
    # only relative paths; '//evil.com' is protocol-relative → reject
    if next_page and next_page.startswith('/') and not next_page.startswith('//'):
        return redirect(next_page)
    if user.role == 'admin':
        return redirect(url_for('admin'))
    return redirect(url_for('calculator'))
```

## Edge cases a weaker model would miss
- **The purity dict must match `VALID_GOLDS` and script.js `goldLabel` exactly** — the keys are lowercase strings `'999'`, `'pt'`, `'silver925'`. Writing `'PT'` or `'925silver'` reintroduces the bug for that metal, silently (the filter falls back to the raw code).
- **`next` open redirect**: accepting any `next` value lets `/login?next=https://evil.com` or `/login?next=//evil.com` bounce users to an attacker page after login. The `startswith('/') and not startswith('//')` pair rejects both absolute URLs and protocol-relative ones.
- **`next` is read from `request.args` (the query string), not `request.form`** — the form POSTs to `url_for('login')` without the query string being resubmitted... actually Flask keeps the query string on POST because the form's `action` is `{{ url_for('login') }}` which drops `?next=`. Fix the form too: in `templates/login.html` line 68, change the action to preserve the query string:
  ```html
  <form method="POST" action="">
  ```
  (Empty action submits to the current URL, `?next=...` included. This one-character-ish change is required or item 5 silently does nothing.)
- **Keep naive UTC in the DB** (item 4). The `tz_taiwan` filter does `dt + timedelta(hours=8)` on naive datetimes; storing tz-aware or local-time values makes new rows render 8 hours off relative to old rows.
- **Version pin**: `pip show flask-wtf` to confirm 1.3.0 before pinning; pinning a version that isn't installed makes `pip install -r requirements.txt` change the environment underneath a working app.

## Acceptance criteria
1. `/history` and `/admin` show 純金999 / 鉑金 Pt / 925銀 for orders with those metals (create one of each to check), not raw codes. 18K金 still correct.
2. Fresh-env check: `python -m venv t && t\Scripts\pip install -r requirements.txt && t\Scripts\python -c "import app"` succeeds (then delete `t`). Equivalently: every import in app.py/models.py is covered by requirements.txt.
3. `grep -n "import requests" app.py` → no matches; app still boots and `/api/prices` still returns prices.
4. `python -W error::DeprecationWarning -c "import models"` exits 0.
5. Logged out, visit `/history` → redirected to `/login?next=/history`; log in as a provider → land on `/history`. Log in via plain `/login` → land on `/calculator` as before. Visit `/login?next=//evil.com`, log in → you stay on this site.
6. `python test_validation.py` still passes.
