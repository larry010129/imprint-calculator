# PLAN: Sane error responses for the JSON endpoints (CSRF failures, expired sessions)

## Goal
Every fetch-based flow fails with a useless generic alert when anything non-2xx-JSON happens, because the server answers JSON clients with HTML:

1. **CSRF failure → HTML 400.** Flask-WTF's default CSRF error page is HTML. `res.json()` throws in the client, the user sees 「發生錯誤」/ "Network error" with no hint. This happens in practice when a tab sits open long enough for the session (and its CSRF token) to expire.
2. **Expired/missing login → redirect chain into HTML.** `@login_required` on `/submit`, `/edit`, `/delete`, `/api/prices`, `/admin/update_status` answers a fetch with a 302 to `/login`; fetch follows it, gets the login page HTML with status 200, and `res.json()` throws. Worse for `/api/prices`: `loadMetalPrices()` silently falls into its catch and the calculator shows 無法取得即時金價 when the real problem is "you're logged out".
3. `admin_update_status` uses `request.get_json()` without `silent=True` (app.py line 280) — a malformed body produces an unhandled 415/400 HTML page instead of the endpoint's own JSON error shape.

Fix: return JSON errors to JSON callers server-side, and make the three client fetch sites redirect to `/login` on 401.

## Exact files to touch
- `app.py` — CSRF error handler, Flask-Login unauthorized handler, one-line fix in `admin_update_status`.
- `static/js/script.js` — handle 401 in the confirm-button fetch and in `loadMetalPrices`.
- `templates/history.html` — handle 401 in the delete fetch.
- `templates/admin.html` — handle 401 in the status fetch.

## Step-by-step implementation

### 1. app.py — JSON-aware error handlers (add after `csrf = CSRFProtect(app)` / login_manager setup)
```python
from flask_wtf.csrf import CSRFError

def wants_json():
    # fetch callers send JSON or the CSRF header; browser form posts do neither
    return request.is_json or request.headers.get('X-CSRFToken') is not None

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    if wants_json():
        return jsonify({'success': False, 'status': 'error',
                        'message': 'session expired, please reload the page'}), 400
    flash('表單已過期，請重新送出。')
    return redirect(request.full_path or url_for('login'))

@login_manager.unauthorized_handler
def handle_unauthorized():
    if wants_json():
        return jsonify({'success': False, 'status': 'error', 'message': 'login required'}), 401
    return redirect(url_for('login', next=request.full_path))
```
Note: defining `@login_manager.unauthorized_handler` replaces Flask-Login's built-in redirect — the `else` branch above must reproduce it (redirect to login with `next`), or normal page navigation breaks for logged-out users.

### 2. app.py — `admin_update_status` (line 280)
```python
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'success': False, 'message': 'invalid JSON'}), 400
    new_status = data.get('status')
```

### 3. Client: handle 401 → go to login (3 call sites)
Add right after each `const res = await fetch(...)`:
```js
if (res.status === 401) { window.location.href = "/login"; return; }
```
Call sites:
1. `static/js/script.js` — confirm-button handler (~line 379, after the fetch).
2. `templates/history.html` — delete fetch (~line 78).
3. `templates/admin.html` — status-update fetch (~line 60).

For `loadMetalPrices` in script.js, don't redirect (it runs on page load and the page itself is already `@login_required`-gated); its existing catch is fine.

### 4. Client: show server error messages on non-OK
In the script.js confirm handler the failure branch already shows `result.message` — good. In history.html/admin.html the `data.message` fallback already exists for delete; admin.html's status handler shows a fixed string — change `alert("Failed to update status.")` to `alert(data.message || "Failed to update status.")`.

## Edge cases a weaker model would miss
- **`wants_json()` cannot be `request.is_json` alone**: the delete fetch in history.html sends NO body and NO Content-Type — only the `X-CSRFToken` header. `request.is_json` is false for it. Checking the CSRF header too is what makes the discrimination reliable for all five endpoints.
- **Login/register form posts must keep getting HTML behavior.** They send `csrf_token` as a form field, not a header, so `wants_json()` is false → flash + redirect. If you make the CSRF handler always return JSON, a user with an expired login form sees raw JSON in the browser.
- **Overriding `unauthorized_handler` disables `login_manager.login_view` routing entirely** — every logged-out page visit goes through your function now. Forgetting the redirect branch turns the whole site into a JSON 401 for logged-out visitors.
- **fetch follows redirects silently** — you cannot detect the 302 client-side; that's why the fix must be server-side (return a real 401 for JSON callers) rather than "check res.redirected" hacks in four places.
- **`request.full_path` appends a bare `?`** when there's no query string (`/history?`). Flask handles it fine as a redirect target, but if you want it clean use `request.full_path.rstrip('?')`.
- **Don't wire a 401 redirect into `loadMetalPrices`** — it would bounce users to login during normal page load races. The page routes already gate access; the price fetch failing shows its existing fallback text.
- **Keep both `success: False` and `status: 'error'` keys** in the JSON errors: script.js checks `result.status === "success" || result.success`, the inline scripts check `data.success`. Two client conventions exist; serve both rather than refactoring all call sites.

## Acceptance criteria
1. Logged in, open the calculator, then in devtools delete the session cookie. Click 確認送出 → browser navigates to `/login` (no cryptic 「發生錯誤」 alert).
2. Same setup on `/history` delete and `/admin` status change → redirected to `/login`.
3. Logged in, tamper the CSRF meta tag content in devtools, submit → alert shows the "session expired" message from the server (a readable failure, not a JSON parse error).
4. Logged out, `curl -i http://localhost:PORT/api/prices` → 302 redirect to login (browser navigation unaffected); `curl -i -H "X-CSRFToken: x" http://localhost:PORT/api/prices` → 401 JSON.
5. Logged-out browser visit to `/history` still redirects to the login page with `?next=/history` (proves the unauthorized handler's HTML branch works).
6. Login and register forms still work end-to-end (proves the CSRF handler's form branch didn't break them).
7. Admin: `curl -X POST /admin/update_status/1` with valid session/CSRF but no JSON body → `{"success": false, "message": "invalid JSON"}` 400, not an HTML error page.
