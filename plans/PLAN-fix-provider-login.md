# PLAN: Fix broken provider login (BuildError on `url_for('index')`)

## Goal
Every non-admin ("provider") login currently crashes with a 500 error. `app.py` calls `url_for('index')` but no route named `index` exists — the calculator route's view function is named `calculator`. Fix the two broken references and honor the `?next=` redirect that Flask-Login already appends.

## Why this is #1
The core user flow (store logs in → uses calculator) is dead. Nothing else matters until this works.

## Exact files to touch
- `app.py` — only file.

## Current defect locations
1. `app.py` line 59 (inside `login()`): `return redirect(url_for('index'))` → raises `werkzeug.routing.exceptions.BuildError` for every provider login.
2. `app.py` line 127 (inside `admin()`): `return redirect(url_for('index'))` → same crash when a provider manually visits `/admin`.

## Step-by-step implementation
1. Open `app.py`.
2. In `login()`, replace the success branch with:
   ```python
   if user and check_password_hash(user.password_hash, password):
       login_user(user)
       next_page = request.args.get('next')
       # only accept relative paths to avoid open redirect
       if next_page and next_page.startswith('/') and not next_page.startswith('//'):
           return redirect(next_page)
       if user.role == 'admin':
           return redirect(url_for('admin'))
       return redirect(url_for('calculator'))
   ```
3. In `admin()`, change `return redirect(url_for('index'))` to `return redirect(url_for('calculator'))`.
4. Search the whole repo for any other `url_for('index')` — there must be zero occurrences when done. (Templates already correctly use `url_for('calculator')`; do NOT rename the `calculator` view function to `index`, that would break `base.html` and `home.html`.)

## Edge cases a weaker model would miss
- **There are TWO occurrences**, lines 59 and 127. Fixing only the login one leaves `/admin` crashing for providers.
- **Do not rename the route instead.** `templates/base.html` line 18 and `templates/home.html` line 13 use `url_for('calculator')`. Renaming the view function `calculator` → `index` "fixes" app.py but breaks every page render.
- **Open redirect:** Flask-Login sends users to `/login?next=/calculator`. If you blindly `redirect(next_page)`, an attacker can craft `/login?next=https://evil.com` or `/login?next=//evil.com`. The `startswith('/') and not startswith('//')` guard above handles both. Do not use `urlparse` netloc-only checks without also rejecting `//` — browsers treat `//evil.com` as protocol-relative.
- **`next` may point to an admin page for a provider** — that's fine; the `/admin` route itself re-checks the role and now redirects safely instead of crashing.

## Acceptance criteria (verify each)
1. `python -c "import app"` succeeds (no syntax errors).
2. Run `python app.py`, then:
   - Log in as `store_a` / `store123` → lands on `/calculator` with HTTP 200 (previously: 500).
   - Log in as `admin` / `admin123` → lands on `/admin`.
   - While logged in as `store_a`, browse to `/admin` → redirected to `/calculator` with a flash message, no 500.
   - Log out, browse to `/history` → redirected to `/login?next=/history`; log in as `store_a` → land on `/history`, not `/calculator`.
   - Browse to `/login?next=//evil.com` and log in → you land on `/calculator` (or `/admin`), NOT an external URL.
3. `grep -rn "url_for('index')" .` returns nothing.
