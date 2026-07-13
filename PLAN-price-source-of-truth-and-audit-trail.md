# PLAN: Single source of truth for pricing + price audit trail on submissions

## Rank: 2 of 5

## Status (as of 2026-07-08)

**Already done:**

- Diamond prices: client loads from `/api/prices` (`Object.assign(diamondPrice, data.diamond)` in `script.js` line 120). No hardcoded diamond literals in JS.
- Audit columns on `Submission`: `gold_rate_per_gram`, `price_source`, `updated_at` in `models.py` lines 25–29.
- `compute_total()` returns `(total, per_gram, source)` and persists audit fields on submit/edit (`app.py` lines 479–497, 588–595).
- Edit reprice notice in `templates/index.html` line 25.
- Admin/history show "計價金價" column with rate and source.

**Still open — the highest remaining pricing risk:**

- **`WEIGHT_TABLE` is duplicated in full** between `app.py` (lines 205–273) and `static/js/script.js` (lines 49–73). ~25 lines × nested dicts. Server uses it for authoritative submit pricing via `lookup_weight()`; client uses it for display summary only. If one copy is edited (e.g. after a Metal notes change) and the other is not, the store sees one total on screen and gets a different total on submit — same class of trust bug diamond prices had before this plan's first iteration.
- **`LABOR_FEE`, `CHIN_TO_GRAMS`, ring surcharge formula** also duplicated (`app.py` lines 197–202, 294–297 vs `script.js` lines 75–77, 102–104, 303–311). Same drift risk.
- **`test_validation.py` still references removed `weight` field** — unrelated to this plan but blocks verification; fixed in PLAN-route-test-coverage.

## Goal

Make `app.py` the single source of truth for all pricing constants used in total calculation. Client should load weight table and labor fees from the server (same pattern as diamond prices and metal rates), so display total and submit total cannot silently diverge.

Do **not** change business rules (labor amounts, ring surcharge formula, chain 2× metal cost) — only eliminate duplication.

## Files to touch

- `app.py`
- `static/js/script.js`
- `test_routes.py` (add one assertion — optional but recommended)

## Step-by-step

### Part 1 — Extend `/api/prices` to expose product constants

In `app.py`, find `api_prices()` (line 370):

```python
@app.route('/api/prices')
@login_required
def api_prices():
    raw, source = get_metal_prices()
    per_gram = {gold: raw[METAL_SYMBOL[gold]] * PURITY_MULTIPLIER[gold]
                for gold in VALID_GOLDS}
    return jsonify({'diamond': DIAMOND_PRICE, 'perGram': per_gram, 'source': source})
```

Replace return with:

```python
    return jsonify({
        'diamond': DIAMOND_PRICE,
        'perGram': per_gram,
        'source': source,
        'weightTable': WEIGHT_TABLE,
        'chainWeightChin': CHAIN_WEIGHT_CHIN,
        'laborFee': LABOR_FEE,
        'chinToGrams': CHIN_TO_GRAMS,
        'ringSizeMin': RING_SIZE_MIN,
        'ringSizeMax': RING_SIZE_MAX,
        'ringSurchargePerHalf': 500,
    })
```

**Edge case:** `WEIGHT_TABLE` contains only Python-native types (floats, strings as keys) — JSON-serializable as-is. Do not add a custom JSON encoder.

**Edge case:** `CHAIN_WEIGHT_CHIN` is used by server `lookup_weight()` for chain category but is separate from `WEIGHT_TABLE['chain']` nested structure. Expose both — client `lookupWeight()` for chain must use the same logic as server. Read server `lookup_weight()` (lines 277–281):

```python
def lookup_weight(category, style_type, gold, carat):
    if category == 'chain':
        return CHAIN_WEIGHT_CHIN[carat]
    return WEIGHT_TABLE[category][style_type][gold][carat]
```

Client must mirror this exactly after loading constants from API.

### Part 2 — Remove duplicated constants from `script.js`

**Delete** these blocks from `static/js/script.js`:

- `WEIGHT_TABLE` (lines 49–73)
- `LABOR_FEE` (line 75)
- `CHIN_TO_GRAMS` (line 76)
- `RING_SIZE_MIN`, `RING_SIZE_MAX` (line 77)

**Replace** with mutable holders (same pattern as `diamondPrice`):

```javascript
let weightTable = {};
let chainWeightChin = {};
let laborFee = {};
let chinToGrams = 3.75;
let ringSizeMin = 7;
let ringSizeMax = 11;
let ringSurchargePerHalf = 500;
```

**Update `lookupWeight()`** (currently lines 97–100):

```javascript
function lookupWeight(category, type, gold, carat) {
  try {
    if (category === 'chain') return chainWeightChin[carat];
    return weightTable[category][type][gold][carat];
  } catch (e) { return null; }
}
```

**Update `ringHalfAbove7()`** to use loaded constants:

```javascript
function ringHalfAbove7(size) {
  return Math.max(0, Math.round((size - ringSizeMin) / 0.5));
}
```

**Update `updateSummary()`** references:

- `CHIN_TO_GRAMS` → `chinToGrams`
- `LABOR_FEE[state.category]` → `laborFee[state.category]`
- `ringHalfAbove7(state.ringSize) * 500` → `ringHalfAbove7(state.ringSize) * ringSurchargePerHalf`

**Update `populateRingSizeOptions()`** to use `ringSizeMin` / `ringSizeMax` instead of constants.

### Part 3 — Load new fields in `loadMetalPrices()`

Find `loadMetalPrices()` in `script.js` (line 114). After `Object.assign(diamondPrice, data.diamond);` add:

```javascript
    Object.assign(weightTable, data.weightTable);
    Object.assign(chainWeightChin, data.chainWeightChin);
    Object.assign(laborFee, data.laborFee);
    if (data.chinToGrams != null) chinToGrams = data.chinToGrams;
    if (data.ringSizeMin != null) ringSizeMin = data.ringSizeMin;
    if (data.ringSizeMax != null) ringSizeMax = data.ringSizeMax;
    if (data.ringSurchargePerHalf != null) ringSurchargePerHalf = data.ringSurchargePerHalf;
    populateRingSizeOptions(); // rebuild dropdown if bounds changed
```

Move `populateRingSizeOptions()` call: it currently runs at line 480 **before** prices load. Change to:

1. Define `populateRingSizeOptions()` but do **not** call it at module load.
2. Call it once inside `loadMetalPrices()` after constants load (clears and rebuilds `#ring-size-select` options).
3. Keep `loadMetalPrices()` call at bottom of file.

**Edge case:** `populateRingSizeOptions()` appends options without clearing — add at start of function:

```javascript
function populateRingSizeOptions() {
  const select = document.getElementById("ring-size-select");
  select.innerHTML = '<option value="" data-i18n="ring_size_placeholder">請選擇戒圍</option>';
  for (let s = ringSizeMin; s <= ringSizeMax; s += 0.5) {
    // ... existing option creation ...
  }
}
```

Check `templates/index.html` for the placeholder option — if it already exists in HTML, preserve its i18n attribute when clearing.

**Edge case:** Before `/api/prices` resolves, `lookupWeight()` returns `null` and summary shows `-` for weight/total — same as diamond loading state. Do not show `0` or `NaN`.

### Part 4 — Handle edit-mode timing

Edit mode (`window.editData`) uses `setTimeout` chains starting at line 485. It runs **before** `loadMetalPrices()` may finish. After this change, if edit restore runs before constants load, weight/total may briefly show `-` then correct when fetch completes.

Fix: at end of `loadMetalPrices()`, after assigning constants, call:

```javascript
    updateSummary();
    if (window.editData) { /* re-run ring size display if already selected */ }
```

The existing `updateSummary()` call at line 121 already runs — ensure edit mode's delayed clicks still work. If ring size dropdown was populated late, re-set value:

```javascript
    if (window.editData?.ringSize) {
      document.getElementById("ring-size-select").value = window.editData.ringSize;
      selectRingSize(window.editData.ringSize);
    }
```

Only add this inside `loadMetalPrices()` success path — not on every page load without edit data.

### Part 5 — Verify server/client totals match

Add optional test in `test_routes.py` after Test 6:

```python
# --- Test 6b: /api/prices includes weightTable for client sync ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
res = client.get('/api/prices', headers={'X-CSRFToken': 'dummy'})
assert res.status_code == 200
data = res.get_json()
assert 'weightTable' in data and 'ring' in data['weightTable']
assert data['laborFee']['ring'] == 5000
assert data['chinToGrams'] == 3.75
```

## Edge cases found while exploring (do not skip these)

- **`DIAMOND_PRICE` has both `"1.0"` and `"1"` keys** in `app.py` line 127 for backward compat. Client `diamondPrice` init uses `"1.0"` only. `/api/prices` returns full dict — `Object.assign` covers both. Do not remove `"1"` key from server without checking old DB rows use `carat='1'`.
- **Chain pricing is `metal_cost * 2`** on server (`compute_total` line 289–290) and client (`updateSummary` line 323–324). Constants sync does not change this — but if you refactor, both sides must keep `* 2`.
- **Earring weight table has no pt950/s925** — only 9k/14k/18k. Validation allows all metals for all categories except chain 9k restriction (client alert line 540). Server `lookup_weight()` will KeyError on invalid combo → 400 on submit. Client should disable invalid metal buttons per category (`CATEGORY_METALS` in script.js) — already done; do not break that when moving weight table.
- **Do not move `CATEGORY_STYLES`, `CATEGORY_METALS`, `METAL_COLORS` to server in this plan** — those control UI availability, not pricing math. Scope creep causes bugs. Only move constants that affect computed totals.
- **`db.create_all()` migration is NOT needed** for this plan — no schema changes.

## Acceptance criteria

1. `rg "WEIGHT_TABLE|LABOR_FEE|CHIN_TO_GRAMS" static/js/script.js` returns nothing (duplicates removed).
2. `GET /api/prices` (authenticated) JSON includes keys: `weightTable`, `chainWeightChin`, `laborFee`, `chinToGrams`, `ringSizeMin`, `ringSizeMax`, `ringSurchargePerHalf`.
3. Browser: complete a ring order (0.5ct, style A, 18k, size 9) — summary total matches `total_price` in `/submit` JSON response (same integer NT$ after rounding).
4. Browser: complete a chain order (3fen, style B, 14k) — summary shows metal×2 total matching submit response.
5. Edit mode: open `/calculator?edit_id=<pending-id>` — weight in 錢/g and total populate correctly after page load (not stuck on `-`).
6. Change one weight value in **only** `app.py` `WEIGHT_TABLE` (e.g. bump one cell by 0.01), reload calculator **without** editing JS — displayed weight changes. Proves client reads server table.
7. Revert the test weight change before committing.
8. `python test_routes.py` passes (including new Test 6b if added).
9. Existing audit trail behavior unchanged: new submissions still have non-null `gold_rate_per_gram` and `price_source`.
