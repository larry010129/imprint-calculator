# PLAN: Server-side validation for /submit and /edit (stop 500s and garbage rows)

## Goal
`/submit` (`app.py` line 98) inserts whatever JSON the client sends. Every `Submission` column is nullable, and the templates format unconditionally — `templates/history.html` line 31 does `"{:.2f}".format(sub.weight)` and line 33 formats `sub.total_price`. One submission with a missing/None `weight` or `total_price` makes `/history` AND `/admin` throw 500 **forever** (the pages render all rows, so one bad row poisons both pages for that user and for the admin). Add a whitelist validator used by both `/submit` and `/edit`, and make the templates tolerate legacy bad rows.

## Exact files to touch
- `app.py` — add validator, use in `submit()` and `edit_submission()`.
- `templates/history.html` — defensive formatting (2 cells).
- `templates/admin.html` — defensive formatting (2 cells).

## Step-by-step implementation

### 1. Add constants + validator to `app.py`
If PLAN-server-side-pricing is already done, `DIAMOND_PRICE` and `PURITY_MULTIPLIER` exist — reuse their keys; do NOT redefine. Otherwise define:
```python
VALID_CATEGORIES = {'ring', 'necklace'}
VALID_CARATS = {'0.1', '0.3', '0.5', '1'}
VALID_TYPES = {'A', 'B', 'C'}
VALID_GOLDS = {'18k', '999', 'pt', 'silver925'}
MAX_WEIGHT_GRAMS = 10000   # 10 kg; generous sanity cap
RING_SIZE_MIN, RING_SIZE_MAX = 5, 25  # must match ringSizeRange in static/js/script.js line 43
```

```python
def validate_submission_fields(data, partial=False):
    """Returns (cleaned_dict, error_message). partial=True for /edit."""
    errors = []
    cleaned = {}

    def check_choice(key, valid):
        val = data.get(key)
        if val is None:
            if not partial:
                errors.append(f'{key} is required')
        elif str(val) not in valid:
            errors.append(f'invalid {key}')
        else:
            cleaned[key] = str(val)

    check_choice('category', VALID_CATEGORIES)
    check_choice('carat', VALID_CARATS)
    check_choice('type', VALID_TYPES)
    check_choice('gold', VALID_GOLDS)

    weight = data.get('weight')
    if weight is None:
        if not partial:
            errors.append('weight is required')
    else:
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            weight = -1
        if not (0 < weight <= MAX_WEIGHT_GRAMS):
            errors.append('invalid weight')
        else:
            cleaned['weight'] = weight

    ring_size = data.get('ringSize')
    if ring_size is not None:
        try:
            ring_size = float(ring_size)
        except (TypeError, ValueError):
            ring_size = -1
        if not (RING_SIZE_MIN <= ring_size <= RING_SIZE_MAX):
            errors.append('invalid ringSize')
        else:
            cleaned['ringSize'] = ring_size

    # ring requires a ring size on full submissions
    if not partial and cleaned.get('category') == 'ring' and 'ringSize' not in cleaned:
        errors.append('ringSize is required for rings')

    return cleaned, ('; '.join(errors) if errors else None)
```

### 2. Use it in `submit()`
```python
@app.route('/submit', methods=['POST'])
@login_required
def submit():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'status': 'error', 'message': 'invalid JSON'}), 400
    cleaned, error = validate_submission_fields(data)
    if error:
        return jsonify({'status': 'error', 'message': error}), 400
    submission = Submission(
        user_id=current_user.id,
        category=cleaned['category'],
        carat=cleaned['carat'],
        style_type=cleaned['type'],
        gold_purity=cleaned['gold'],
        weight=cleaned['weight'],
        ring_size=cleaned.get('ringSize'),
        total_price=...,  # keep existing source: data.get('totalPrice') now,
                          # or compute_total(...) if PLAN-server-side-pricing is done
    )
    ...
```
If total_price still comes from the client (pricing plan not done yet), validate it too: coerce to float, require `0 < total_price <= 100_000_000`, else 400.

### 3. Use it in `edit_submission()`
After the existing ownership/status checks:
```python
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'success': False, 'message': 'invalid JSON'}), 400
    cleaned, error = validate_submission_fields(data, partial=True)
    if error:
        return jsonify({'success': False, 'message': error}), 400
    if 'weight' in cleaned: sub.weight = cleaned['weight']
    if 'ringSize' in cleaned: sub.ring_size = cleaned['ringSize']
    if 'carat' in cleaned: sub.carat = cleaned['carat']
    if 'type' in cleaned: sub.style_type = cleaned['type']
    if 'gold' in cleaned: sub.gold_purity = cleaned['gold']
```
(Then recompute total per the pricing plan, or apply the validated client totalPrice if that plan isn't done.)

### 4. Defensive templates (legacy rows may already have NULLs)
`instance/database.db` already exists and may contain rows saved before validation. In BOTH `templates/history.html` (lines 31, 33) and `templates/admin.html` (lines 32, 34) change:
- `{{ "{:.2f}".format(sub.weight) }}` → `{{ "{:.2f}".format(sub.weight) if sub.weight is not none else '-' }}`
- `{{ "{:,.0f}".format(sub.total_price) }}` → `{{ "{:,.0f}".format(sub.total_price) if sub.total_price is not none else '-' }}`

### 5. Leave one runnable check behind
Create `test_validation.py` at repo root (stdlib only, run with `python test_validation.py`):
```python
from app import validate_submission_fields

ok, err = validate_submission_fields({'category': 'ring', 'carat': '1', 'type': 'A',
                                      'gold': '18k', 'weight': 3.5, 'ringSize': 12})
assert err is None and ok['weight'] == 3.5, err

_, err = validate_submission_fields({'category': 'ring', 'carat': '1', 'type': 'A',
                                     'gold': '18k', 'weight': 3.5})  # ring, no size
assert err and 'ringSize' in err

_, err = validate_submission_fields({'category': 'sofa', 'carat': '2', 'type': 'Z',
                                     'gold': 'tin', 'weight': -1})
assert err

_, err = validate_submission_fields({'weight': 'abc'}, partial=True)
assert err and 'weight' in err

ok, err = validate_submission_fields({'weight': 4.2}, partial=True)
assert err is None and ok == {'weight': 4.2}

print("all validation checks passed")
```
Note: importing `app` triggers `db.create_all()` against the instance DB — that is harmless (it only creates missing tables).

## Edge cases a weaker model would miss
- **`request.json` raises on wrong/missing Content-Type** (415 in Flask 3.x) instead of returning None — use `request.get_json(silent=True)` and check for `None`, otherwise a curl without headers produces an unhandled error page instead of a clean 400.
- **One bad row breaks the page for everyone, permanently** — the crash is at render time, not insert time. That's why step 4 (template guards) is required even after validation exists: the existing DB may already hold NULL rows.
- **JSON numbers vs strings**: the client sends `carat` as a string (`"0.1"`) but `weight` as a number. A validator comparing `data.get('carat') in {0.1, 0.3}` (floats) always fails; comparing weight with `isinstance(str)` always fails. Coerce with `str()` for choices and `float()` for numerics as above.
- **`float('nan')` and `float('inf')` pass naive `> 0` checks** — `nan > 0` is False so the range check `0 < weight <= MAX` correctly rejects NaN, and the upper bound rejects inf. Do not "simplify" the check to `weight > 0` only.
- **`ringSize` must stay optional for necklaces** but required for rings — the client already enforces this (script.js line 372) but the server must too; the edit modal also sends `ringSize: null` for necklaces (history.html line 125), which must not error (the `is not None` guard handles it).
- **`/edit` accepts more fields than the modal sends** (carat/type/gold — app.py lines 177–179). Validate all of them, not just weight/ringSize; a crafted request can currently set `carat` to `"<script>..."` which then renders into the admin table. Whitelisting fixes stored-XSS-shaped data even though Jinja autoescaping is the real defense.
- **Truthiness bug in the existing edit code**: `if data.get('carat'):` treats empty string as "not provided" — fine — but the same pattern applied to `weight` would treat `0` as missing. Keep the explicit `is not None` / `'key' in cleaned` style.

## Acceptance criteria
1. `python test_validation.py` prints `all validation checks passed`.
2. Logged in, `curl -X POST /submit` with no body/headers returns 400 JSON, not an HTML error page.
3. Submitting `{"category":"ring","carat":"9","type":"Z","gold":"tin","weight":-5}` returns 400 listing the invalid fields; DB row count unchanged.
4. A normal calculator submission (ring, 0.5ct, A, 18k, size 12) still succeeds end-to-end.
5. Manually insert a NULL-weight row (`sqlite3 instance/database.db "insert into submission (user_id, status) values (2, 'pending')"`) → `/history` and `/admin` render with `-` in the weight/price cells, no 500. Delete the row afterwards.
6. Editing a pending order to weight `abc` or ring size `99` returns 400 and changes nothing.
