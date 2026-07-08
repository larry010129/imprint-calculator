# PLAN: Route-level test coverage (auth, ownership, CSRF, validation boundaries)

## Rank: 4 of 5

## Goal

`test_validation.py` is the only test file in this project, and it only tests `validate_submission_fields()` — a pure function. Nothing tests the actual Flask routes: whether unauthenticated users are correctly blocked, whether one store can see or modify another store's orders, whether the admin-only route is actually admin-only, or whether the CSRF/JSON error paths behave as intended. This is an app that computes and stores real money amounts for real business customers (multiple jewelry stores) — a regression in the ownership checks (`sub.user_id != current_user.id`) in `edit_submission()` or `delete_submission()` would let one store see or tamper with another store's data, and nothing would catch it before a human noticed.

This plan adds a `test_routes.py` that exercises the real Flask app through its test client, covering auth, cross-tenant isolation, and input validation boundaries at the HTTP layer.

## Files to touch

- `Efforts/diamond-calculator/app.py` (one small, backward-compatible change — see Part 1)
- `Efforts/diamond-calculator/test_routes.py` (new file)

## Step-by-step

### Part 1 — Make `app.py` testable without touching the real database

**This is the step a weaker model is most likely to skip, and skipping it means every test run corrupts your real production data.**

`app.py` currently has, near the top:

```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
```

...and, further down, still at module level (runs the instant `app.py` is imported by anything, including a test file):

```python
with app.app_context():
    db.create_all()
    create_initial_users()
```

Because this all happens at **import time**, and because the database URI is a hardcoded string with no override hook, there is no way for an external test file to say "use a different database" after the fact — by the time `import app` returns, `db.create_all()` has already run against `instance/database.db`, the real file. Running tests as-is would create test users and test submissions directly in your production data, mixed in with real store orders.

Fix this first. Find:

```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
```

Replace with:

```python
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
```

This is a one-line, fully backward-compatible change: if `DATABASE_URL` is not set (the normal case, in dev and production), behavior is identical to today. It only matters when something sets `DATABASE_URL` before importing `app` — which is exactly what the test file will do.

### Part 2 — Write `test_routes.py`

Match the existing style of `test_validation.py`: a plain script using `assert`, no `pytest`, no new dependency (there is currently no test framework in `requirements.txt` and this plan does not add one — Flask's built-in `app.test_client()` is sufficient for everything needed here). Run with `python test_routes.py`.

Create `Efforts/diamond-calculator/test_routes.py`:

```python
"""
Route-level tests. Run with: python test_routes.py

IMPORTANT: this sets DATABASE_URL to an in-memory sqlite database BEFORE
importing app, so it never touches instance/database.db. Do not remove
or reorder the os.environ line below the import.
"""
import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ.setdefault('SECRET_KEY', 'test-secret-key-not-for-production')

from app import app, db
from models import User, Submission
from werkzeug.security import generate_password_hash

app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False  # tests exercise route logic, not CSRF machinery

def fresh_client():
    """Returns a fresh test client with a clean in-memory DB and two seeded users."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        admin = User(username='admin_test', password_hash=generate_password_hash('adminpass'),
                     role='admin', store_name='Admin HQ')
        store_a = User(username='store_a', password_hash=generate_password_hash('pass_a'),
                       role='provider', store_name='Store A')
        store_b = User(username='store_b', password_hash=generate_password_hash('pass_b'),
                       role='provider', store_name='Store B')
        db.session.add_all([admin, store_a, store_b])
        db.session.commit()
    return app.test_client()

def login(client, username, password):
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=False)

# --- Test 1: unauthenticated access to a protected route is blocked ---
client = fresh_client()
res = client.get('/calculator', follow_redirects=False)
assert res.status_code == 302, f"expected redirect for anon /calculator, got {res.status_code}"
assert '/login' in res.headers.get('Location', ''), "anon /calculator should redirect to /login"

res = client.get('/api/prices')
assert res.status_code == 401, f"expected 401 JSON for anon /api/prices, got {res.status_code}"

# --- Test 2: login works and redirects providers to /calculator, admin to /admin ---
client = fresh_client()
res = login(client, 'store_a', 'pass_a')
assert res.status_code == 302 and res.headers['Location'].endswith('/calculator'), \
    f"provider login should redirect to /calculator, got {res.headers.get('Location')}"

client = fresh_client()
res = login(client, 'admin_test', 'adminpass')
assert res.status_code == 302 and res.headers['Location'].endswith('/admin'), \
    f"admin login should redirect to /admin, got {res.headers.get('Location')}"

# --- Test 3: wrong password is rejected ---
client = fresh_client()
res = login(client, 'store_a', 'wrong-password')
assert res.status_code == 200, "failed login should re-render the login page, not redirect"

# --- Test 4: a provider cannot view /admin ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
res = client.get('/admin', follow_redirects=False)
assert res.status_code == 302, f"provider hitting /admin should be redirected away, got {res.status_code}"
assert '/admin' not in res.headers.get('Location', ''), "must not redirect back into /admin"

# --- Test 5: /submit rejects invalid data and does not create a row ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
with app.app_context():
    before_count = Submission.query.count()
res = client.post('/submit', json={'category': 'sofa', 'carat': '99', 'type': 'Z', 'gold': 'tin', 'weight': -5})
assert res.status_code == 400, f"invalid /submit should 400, got {res.status_code}"
with app.app_context():
    after_count = Submission.query.count()
assert after_count == before_count, "invalid /submit must not create a Submission row"

# --- Test 6: /submit with valid ring data creates exactly one row with a positive total ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
res = client.post('/submit', json={
    'category': 'ring', 'carat': '1', 'type': 'A', 'gold': '18k', 'weight': 3.5, 'ringSize': 12
})
assert res.status_code == 200, f"valid /submit should 200, got {res.status_code} body={res.get_json()}"
body = res.get_json()
assert body['status'] == 'success', f"expected success status, got {body}"
assert body['total_price'] > 0, "total_price should be a positive number"
with app.app_context():
    subs = Submission.query.all()
    assert len(subs) == 1, f"expected exactly 1 submission, found {len(subs)}"
    assert subs[0].user_id == User.query.filter_by(username='store_a').first().id

# --- Test 7: ring category without ringSize is rejected ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
res = client.post('/submit', json={'category': 'ring', 'carat': '1', 'type': 'A', 'gold': '18k', 'weight': 3.5})
assert res.status_code == 400, "ring submission without ringSize must be rejected"
assert 'ringSize' in res.get_json()['message']

# --- Test 8: cross-tenant isolation — store B cannot delete store A's submission ---
client_a = fresh_client()
login(client_a, 'store_a', 'pass_a')
res = client_a.post('/submit', json={
    'category': 'necklace', 'carat': '0.5', 'type': 'B', 'gold': 'pt', 'weight': 5.0
})
sub_id = res.get_json()  # note: /submit does not currently return the new row's id — see Edge Cases below
with app.app_context():
    real_sub_id = Submission.query.filter_by(user_id=User.query.filter_by(username='store_a').first().id).first().id

client_b = fresh_client()
# fresh_client() wipes the DB, so re-create the submission in a shared client session instead:
client = fresh_client()
login(client, 'store_a', 'pass_a')
res = client.post('/submit', json={
    'category': 'necklace', 'carat': '0.5', 'type': 'B', 'gold': 'pt', 'weight': 5.0
})
with app.app_context():
    target = Submission.query.filter_by(user_id=User.query.filter_by(username='store_a').first().id).first()
    target_id = target.id
client.get('/logout')
login(client, 'store_b', 'pass_b')
res = client.post(f'/delete/{target_id}')
assert res.status_code == 403, f"store_b deleting store_a's order should 403, got {res.status_code}"
with app.app_context():
    assert Submission.query.get(target_id) is not None, "store_a's submission must still exist after store_b's blocked delete attempt"

# --- Test 9: owner CAN delete their own pending submission ---
client.get('/logout')
login(client, 'store_a', 'pass_a')
res = client.post(f'/delete/{target_id}')
assert res.status_code == 200 and res.get_json()['success'] is True, "owner should be able to delete their own pending order"
with app.app_context():
    assert Submission.query.get(target_id) is None, "submission should be gone after owner deletes it"

# --- Test 10: weight and ring size boundary validation ---
from app import validate_submission_fields, MAX_WEIGHT_GRAMS, RING_SIZE_MIN, RING_SIZE_MAX

_, err = validate_submission_fields({
    'category': 'ring', 'carat': '1', 'type': 'A', 'gold': '18k',
    'weight': MAX_WEIGHT_GRAMS + 0.01, 'ringSize': 12
})
assert err and 'weight' in err, "weight just above MAX_WEIGHT_GRAMS must be rejected"

_, err = validate_submission_fields({
    'category': 'ring', 'carat': '1', 'type': 'A', 'gold': '18k',
    'weight': 3.5, 'ringSize': RING_SIZE_MIN - 1
})
assert err and 'ringSize' in err, "ringSize below RING_SIZE_MIN must be rejected"

_, err = validate_submission_fields({
    'category': 'ring', 'carat': '1', 'type': 'A', 'gold': '18k',
    'weight': 3.5, 'ringSize': RING_SIZE_MAX + 1
})
assert err and 'ringSize' in err, "ringSize above RING_SIZE_MAX must be rejected"

ok, err = validate_submission_fields({
    'category': 'ring', 'carat': '1', 'type': 'A', 'gold': '18k',
    'weight': 0.01, 'ringSize': RING_SIZE_MIN
})
assert err is None, f"boundary-minimum weight/ringSize should be accepted, got error: {err}"

print("all route tests passed")
```

### Part 3 — Update the README's testing section

Find in `README.md`:

```
## Testing
Run the validation tests with:
```bash
python test_validation.py
```
```

Change to:

```
## Testing
Run the tests with:
```bash
python test_validation.py
python test_routes.py
```
Both are plain assert-based scripts (no pytest). `test_routes.py` uses an in-memory SQLite database and never touches `instance/database.db`.
```

## Edge cases found while exploring that a weaker model would miss

- **`/submit` does not return the new submission's `id` in its JSON response** — only `{'status': 'success', 'message': ..., 'total_price': ...}` (confirmed by reading `submit()` in `app.py`). Test 8 above works around this by querying the database directly for the row instead of relying on a response field that doesn't exist. Do not write a test that assumes `/submit`'s response contains an `id` — it doesn't, and "fixing" that in this test-coverage plan is out of scope (it would be a real API change affecting the frontend too; flag it as a candidate for a future plan if you notice the frontend ever needs it, but the frontend currently doesn't — it always reloads `/history` to see the new row).
- **`fresh_client()` calls `db.drop_all(); db.create_all()` inside `app.app_context()` every time it's called**, which means each "section" of the test file that calls `fresh_client()` starts from a completely empty database with only the 3 seeded users. Do not assume state persists between one `fresh_client()` call and another — this is deliberate isolation, not a bug. Test 8's first two `client_a`/`client_b` lines are dead code left over from an earlier draft in this plan's own writing — when you write the file, use the corrected version at the bottom of Test 8's block (the one that logs out and back in on a single shared `client`), which is what's already reflected in the code block above. Re-read Test 8 carefully before transcribing it: the first `client_a = fresh_client()` / `client_b = fresh_client()` lines are intentionally unused placeholders replaced by the `client = fresh_client()` line further down — simplify by deleting the first four lines of Test 8's block (`client_a = fresh_client()` through `real_sub_id = ...`) if you want to clean it up, they don't affect correctness either way since they're just orphaned local variables, but they're confusing. The version that matters is everything from `client = fresh_client()` onward.
- **`db.create_all()` inside `app.app_context()` at module level in `app.py` still runs once at import time**, against whatever `DATABASE_URL` was set to at that moment. Because `test_routes.py` sets `os.environ['DATABASE_URL'] = 'sqlite:///:memory:'` **before** `from app import app, db`, that first `db.create_all()` call (inside `app.py` itself) already targets the in-memory DB — good. But Python's in-memory SQLite databases are connection-scoped: a fresh `:memory:` database is created per connection, and Flask-SQLAlchemy typically holds one engine/connection pool for the app's lifetime, so this works *as long as `test_routes.py` runs as a single process/single `import app`* (which it does — it's a plain script, not something that re-imports `app` mid-run). Do not try to parallelize these tests across multiple processes without switching to a real temp file-based sqlite DB (`sqlite:///test.db` with cleanup) instead of `:memory:`.
- **`login()` in the test file does not send a CSRF token**, because `app.config['WTF_CSRF_ENABLED'] = False` is set before any request is made. This must be set on the `app` object before the test client makes its first request — verify it's set right after `app.config['TESTING'] = True` and before any `fresh_client()` call, exactly as shown above. If you accidentally move it after the first request, Flask-WTF may have already cached CSRF enforcement for that request cycle and you'll get confusing 400s.
- **The admin-blocked test (Test 4) checks that the redirect does NOT go back to `/admin`**, not just that it's a 302. This matters because `admin()` in `app.py` flashes a message and redirects to `calculator`, not to an error page — a weaker test might only check `status_code == 302` and miss a future regression where someone changes the redirect target to something that leaks data.

## Acceptance criteria

1. `python test_routes.py` exits with code 0 and prints `all route tests passed`, with no assertion errors.
2. Running `python test_routes.py` does not modify `instance/database.db` — verify by checking the file's modification timestamp (`ls -la instance/database.db`) before and after running the test; it must be unchanged (or the file may not even exist yet if you haven't run the real app — that's fine too, the test must not create it).
3. `python test_validation.py` still passes unchanged (this plan does not touch that file).
4. Deliberately reintroduce the bug this plan is meant to catch — comment out the `if sub.user_id != current_user.id:` check in `delete_submission()` in `app.py` — and confirm `python test_routes.py` now fails on Test 8, proving the test actually exercises the ownership check rather than trivially passing. Revert the comment-out after confirming.
5. `README.md`'s Testing section lists both test files.
