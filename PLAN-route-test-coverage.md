# PLAN: Route-level test coverage (auth, ownership, CSRF, validation boundaries)

## Rank: 1 of 5 — do this first

## Status (as of 2026-07-08)

**Already done:**

- `DATABASE_URL` override in `app.py` line 14
- `test_routes.py` exists with 12 passing tests (auth, submit, delete isolation, bracelet/chain submit, ring size boundaries)
- Tests use in-memory SQLite — do not touch `instance/database.db`
- README documents both test files

**Broken / missing:**

- **`python test_validation.py` currently FAILS** — still tests removed `weight` field, obsolete carat `'1'` (valid is `'1.0'`), obsolete ring size `12` (valid range is 7.0–11.0 per `app.py` lines 310, 358). Any CI or human running "all tests" gets a false failure.
- **No test for `/edit/<id>` cross-tenant isolation** — delete is tested (Test 8) but edit is not. A regression in `edit_submission()` ownership check would not be caught.
- **No test for `/admin/update_status/<id>`** — provider could potentially change order status if auth check regresses.
- **No test for login lockout** — implemented in `app.py` lines 150–172 but untested.

## Goal

Restore a trustworthy test suite that matches the current 5-category app schema, then add the highest-risk missing route tests before doing pricing refactors (PLAN-price-source-of-truth) or asset deploys.

## Files to touch

- `test_validation.py` (rewrite)
- `test_routes.py` (append tests)
- `README.md` (minor clarification only if needed)

## Step-by-step

### Part 1 — Rewrite `test_validation.py`

Replace entire file content with:

```python
"""
Validation unit tests. Run with: python test_validation.py

Does not import app routes — only validate_submission_fields().
"""
import os
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')

from app import validate_submission_fields, RING_SIZE_MIN, RING_SIZE_MAX

# Valid ring submission (weight comes from server table, not client payload)
ok, err = validate_submission_fields({
    'category': 'ring', 'carat': '1.0', 'type': 'A', 'gold': '18k', 'ringSize': 9.0
})
assert err is None, err
assert ok['category'] == 'ring' and ok['carat'] == '1.0' and ok['ringSize'] == 9.0

# Ring without ringSize rejected
_, err = validate_submission_fields({
    'category': 'ring', 'carat': '1.0', 'type': 'A', 'gold': '18k'
})
assert err and 'ringSize' in err

# Invalid category/carat/gold rejected
_, err = validate_submission_fields({
    'category': 'sofa', 'carat': '2', 'type': 'Z', 'gold': 'tin'
})
assert err

# Ring size boundaries
_, err = validate_submission_fields({
    'category': 'ring', 'carat': '0.5', 'type': 'B', 'gold': '14k',
    'ringSize': RING_SIZE_MIN - 0.5
})
assert err and 'ringSize' in err

_, err = validate_submission_fields({
    'category': 'ring', 'carat': '0.5', 'type': 'B', 'gold': '14k',
    'ringSize': RING_SIZE_MAX + 0.5
})
assert err and 'ringSize' in err

ok, err = validate_submission_fields({
    'category': 'ring', 'carat': '0.5', 'type': 'B', 'gold': '14k',
    'ringSize': RING_SIZE_MIN
})
assert err is None, err

# Chain uses 3fen/4fen carats, not ct sizes
ok, err = validate_submission_fields({
    'category': 'chain', 'carat': '3fen', 'type': 'A', 'gold': '18k', 'color': 'white'
})
assert err is None, err

_, err = validate_submission_fields({
    'category': 'chain', 'carat': '0.5', 'type': 'A', 'gold': '18k'
})
assert err and 'carat' in err

# Partial edit mode — only sent fields validated
ok, err = validate_submission_fields({'category': 'pendant'}, partial=True)
assert err is None and ok == {'category': 'pendant'}

_, err = validate_submission_fields({'gold': 'invalid'}, partial=True)
assert err and 'gold' in err

# Optional color
ok, err = validate_submission_fields({
    'category': 'ring', 'carat': '0.3', 'type': 'A', 'gold': '14k',
    'ringSize': 8.0, 'color': 'rose'
})
assert err is None and ok['color'] == 'rose'

_, err = validate_submission_fields({
    'category': 'ring', 'carat': '0.3', 'type': 'A', 'gold': '14k',
    'ringSize': 8.0, 'color': 'purple'
})
assert err and 'color' in err

print("all validation checks passed")
```

**Edge case:** This file imports `app`, which triggers `db.create_all()` at import. `DATABASE_URL=sqlite:///:memory:` must be set **before** `from app import ...`. The `os.environ.setdefault` lines at top handle this.

**Edge case:** Do not test `weight` in validation — client no longer sends weight; server computes via `lookup_weight()` in `submit()`.

Run:

```powershell
python test_validation.py
```

Must print `all validation checks passed`.

### Part 2 — Append tests to `test_routes.py`

Add after Test 12 (before `print("all route tests passed")`):

```python
# --- Test 13: cross-tenant isolation — store_b cannot edit store_a's submission ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
client.post('/submit', json={
    'category': 'pendant', 'carat': '0.3', 'type': 'A', 'gold': '14k', 'color': 'white'
})
with app.app_context():
    target_id = Submission.query.filter_by(
        user_id=User.query.filter_by(username='store_a').first().id
    ).first().id

client.get('/logout')
login(client, 'store_b', 'pass_b')
res = client.post(f'/edit/{target_id}', json={
    'category': 'pendant', 'carat': '0.5', 'type': 'B', 'gold': '18k', 'color': 'yellow'
})
assert res.status_code == 403, f"store_b editing store_a's order should 403, got {res.status_code}"

# --- Test 14: provider cannot call admin update_status ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
client.post('/submit', json={
    'category': 'earring', 'carat': '0.1', 'type': 'A', 'gold': '18k'
})
with app.app_context():
    sub_id = Submission.query.first().id

res = client.post(f'/admin/update_status/{sub_id}', json={'status': 'completed'})
assert res.status_code == 403, f"provider update_status should 403, got {res.status_code}"

# --- Test 15: admin CAN update status ---
client = fresh_client()
login(client, 'admin_test', 'adminpass')
# create submission as store_a in same DB
with app.app_context():
    store_a_id = User.query.filter_by(username='store_a').first().id
    sub = Submission(user_id=store_a_id, category='bracelet', carat='0.1',
                     style_type='A', gold_purity='s925', total_price=50000, status='pending')
    db.session.add(sub)
    db.session.commit()
    sub_id = sub.id

res = client.post(f'/admin/update_status/{sub_id}', json={'status': 'confirmed'})
assert res.status_code == 200 and res.get_json()['success'] is True
with app.app_context():
    assert db.session.get(Submission, sub_id).status == 'confirmed'

# --- Test 16: login lockout after 5 failures ---
client = fresh_client()
for _ in range(5):
    login(client, 'store_a', 'wrong')
res = login(client, 'store_a', 'pass_a')
assert res.status_code == 200, "6th attempt during lockout should re-render login, not redirect"
assert 'Too many failed attempts' in res.get_data(as_text=True) or \
       '登入失敗次數過多' in res.get_data(as_text=True)
```

**Edge case for Test 15:** `fresh_client()` wipes DB and reseeds users but Test 15 needs a submission. Creating it directly via SQLAlchemy in test (as shown) avoids needing to logout/login as store_a.

**Edge case for Test 16:** Lockout is in-memory — resets on process restart. Test runs in same process, so counter persists on `client` session... Actually each `login()` POST is stateless for lockout (server-side dict keyed by username). Same `client` cookie does not matter. After 5 wrong passwords for `store_a`, 6th with correct password must fail with lockout message.

**Edge case:** Test 16 does not wait 5 minutes — it verifies lockout triggers, not expiry. Expiry testing is manual (see PLAN-operational-hardening acceptance criteria).

### Part 3 — Run full suite

```powershell
cd "c:\Users\user\Documents\second brain\Efforts\diamond-calculator"
python test_validation.py
python test_routes.py
```

Both must exit 0.

### Part 4 — Prove tests catch real bugs (sanity check)

Temporarily comment out ownership check in `app.py` `edit_submission()`:

```python
# if sub.user_id != current_user.id:
#     return jsonify({'success': False, 'message': 'Unauthorized'}), 403
```

Run `python test_routes.py` — Test 13 must fail. Revert comment. Run again — must pass.

Same for `delete_submission()` — Test 8 already catches delete regression.

### Part 5 — README (only if needed)

README already lists both test files. Optionally add:

```
Run both before committing pricing or auth changes.
```

No other README changes required.

## Edge cases found while exploring (do not skip these)

- **`test_validation.py` importing `app` touches in-memory DB**, not `instance/database.db` — same as test_routes. Always set `DATABASE_URL` before import.
- **`/api/prices` requires login** — Test 1 already sends `X-CSRFToken: dummy` header to trigger JSON unauthorized path via `wants_json()`. New tests do not need prices endpoint unless PLAN-price adds Test 6b there.
- **`Submission.query.get()` deprecated in SQLAlchemy 2.x** — existing tests use `db.session.get(Submission, id)` (Test 8). Match that style in new tests.
- **Do not add pytest** — project uses plain assert scripts per README. Adding pytest is out of scope.
- **Test 8 dead code removed** — older plan draft had unused `client_a`/`client_b` variables. Current `test_routes.py` is clean; keep it that way when appending.
- **Earring submit has no ringSize or color required** — Test 14 uses minimal valid earring payload (9k/14k/18k only in weight table).

## Acceptance criteria

1. `python test_validation.py` exits 0 with `all validation checks passed`.
2. `python test_routes.py` exits 0 with `all route tests passed` (16 tests total after append).
3. `instance/database.db` modification time unchanged after running both test files (or file absent if never run app — either is fine).
4. Commenting out `edit_submission` ownership check causes Test 13 to fail; restored code passes.
5. Commenting out `delete_submission` ownership check causes Test 8 to fail; restored code passes.
6. No test references client-sent `weight` field or carat value `'1'` (without `.0`).
7. All ring size test values fall within `RING_SIZE_MIN`–`RING_SIZE_MAX` (7.0–11.0) unless explicitly testing rejection outside range.
