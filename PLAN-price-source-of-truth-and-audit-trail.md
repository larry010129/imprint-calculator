# PLAN: Single source of truth for pricing + price audit trail on submissions

## Rank: 3 of 5

## Goal

Two related problems in how this app prices things:

**Problem A — duplicated pricing config.** Diamond prices exist in two places that must be kept in sync by hand:
- `app.py`: `DIAMOND_PRICE = {"0.1": 24000, "0.3": 79000, "0.5": 98000, "1": 250000}`
- `static/js/script.js`: `const diamondPrice = { "0.1": 24000, "0.3": 79000, "0.5": 98000, "1": 250000 };`

The server already returns diamond prices in the `/api/prices` response (`{'diamond': DIAMOND_PRICE, ...}`), but the client code ignores that field and uses its own hardcoded copy instead. If you (or a future session) ever update a price in `app.py` — say, carat prices change — and forget the matching edit in `script.js`, the calculator will **display** a stale price to the store user while the calculator's confirm button still submits at the correct, current, server-computed price (the server always recomputes the total server-side via `compute_total()` and ignores whatever `totalPrice` the client sent — verified by reading `submit()` and `edit_submission()` in `app.py`, neither one uses `data.get('totalPrice')` for anything). So this is a **trust/UX bug, not a money-safety bug** — but a store owner who sees one number on screen and gets charged a different one (even if the charged one is the "correct" one) will lose confidence in the tool.

**Problem B — no price audit trail, and a silent repricing-on-edit behavior.** `Submission` stores `total_price` but not the metal rate that was used to compute it. There's a comment in `app.py` at the bottom of `edit_submission()` that already flags this as a known open question:

```python
# ponytail: edit reprices at current metal rate; store rate-at-submit if order locking matters
```

Today: if a store submits an order, then later edits it (only allowed while `status == 'pending'`), the total is silently recalculated using whatever the live metal rate is *at edit time*, which may differ from the rate at original submission time — with no record of either rate anywhere, and no indication to the user in the UI that this recalculation is happening. Six months from now, if a store disputes a price, there is no way to answer "what rate did we actually use for this order."

This plan does not change the business policy of *whether* editing should reprice (that's your call, not a call to make silently in a plan) — it makes the existing behavior **visible and auditable**: every priced total (at submit and at every edit) is stored alongside the rate and source used to compute it, and the edit screen tells the user up front that saving will use today's rate.

## Files to touch

- `Efforts/diamond-calculator/app.py`
- `Efforts/diamond-calculator/models.py`
- `Efforts/diamond-calculator/static/js/script.js`
- `Efforts/diamond-calculator/templates/index.html`
- `Efforts/diamond-calculator/templates/admin.html`
- `Efforts/diamond-calculator/templates/history.html`

## Step-by-step

### Part 1 — Fix the duplicated diamond price (client-side)

**In `static/js/script.js`:**

Find this near the top of the file:

```javascript
const diamondPrice = {
  "0.1": 24000,
  "0.3": 79000,
  "0.5": 98000,
  "1": 250000
};
```

Replace with (mirrors the existing `pricePerGram` pattern used two blocks below it, which starts `null` per key and gets filled in after fetch):

```javascript
let diamondPrice = { "0.1": null, "0.3": null, "0.5": null, "1": null };
```

Find `loadMetalPrices()`:

```javascript
async function loadMetalPrices() {
  try {
    const res = await fetch("/api/prices");
    if (!res.ok) throw new Error(`API returned ${res.status}`);
    const data = await res.json();
    Object.keys(data.perGram).forEach(goldId => { pricePerGram[goldId] = data.perGram[goldId]; });
    updateGoldPriceDisplay();
    updateTotal();
  } catch (err) {
    document.getElementById("sum-goldprice").textContent = tr('goldprice_failed');
    console.error("metal price fetch failed:", err);
  }
}
```

Add one line so it also consumes `data.diamond` (the field the server already sends):

```javascript
async function loadMetalPrices() {
  try {
    const res = await fetch("/api/prices");
    if (!res.ok) throw new Error(`API returned ${res.status}`);
    const data = await res.json();
    Object.keys(data.perGram).forEach(goldId => { pricePerGram[goldId] = data.perGram[goldId]; });
    Object.keys(data.diamond).forEach(carat => { diamondPrice[carat] = data.diamond[carat]; });
    updateGoldPriceDisplay();
    updateTotal();
  } catch (err) {
    document.getElementById("sum-goldprice").textContent = tr('goldprice_failed');
    console.error("metal price fetch failed:", err);
  }
}
```

Now find `updateTotal()`:

```javascript
function updateTotal() {
  const dPrice = state.carat ? diamondPrice[state.carat] : 0;
  const goldPriceUnavailable = state.gold && pricePerGram[state.gold] === null;
  const gRate = state.gold && pricePerGram[state.gold] ? pricePerGram[state.gold] : 0;
  const gCost = gRate * state.weight;
  const total = dPrice + gCost;

  document.getElementById("sum-diamond-price").textContent = dPrice.toLocaleString();

  if (goldPriceUnavailable) {
    document.getElementById("sum-gold-cost").textContent = tr('price_unavailable');
    document.getElementById("sum-total").textContent = tr('total_unavailable');
  } else {
    document.getElementById("sum-gold-cost").textContent = Math.round(gCost).toLocaleString();
    document.getElementById("sum-total").textContent = Math.round(total).toLocaleString();
  }
}
```

`diamondPrice[state.carat]` can now be `null` (before the fetch resolves), which would make `dPrice.toLocaleString()` throw ("Cannot read properties of null") and `dPrice + gCost` evaluate to `NaN` in the total. Replace the whole function with:

```javascript
function updateTotal() {
  const diamondPriceUnavailable = state.carat && diamondPrice[state.carat] === null;
  const dPrice = state.carat && diamondPrice[state.carat] ? diamondPrice[state.carat] : 0;
  const goldPriceUnavailable = state.gold && pricePerGram[state.gold] === null;
  const gRate = state.gold && pricePerGram[state.gold] ? pricePerGram[state.gold] : 0;
  const gCost = gRate * state.weight;
  const total = dPrice + gCost;

  document.getElementById("sum-diamond-price").textContent =
    diamondPriceUnavailable ? tr('goldprice_loading') : dPrice.toLocaleString();

  if (goldPriceUnavailable || diamondPriceUnavailable) {
    document.getElementById("sum-gold-cost").textContent = tr('price_unavailable');
    document.getElementById("sum-total").textContent = tr('total_unavailable');
  } else {
    document.getElementById("sum-gold-cost").textContent = Math.round(gCost).toLocaleString();
    document.getElementById("sum-total").textContent = Math.round(total).toLocaleString();
  }
}
```

There is a second, near-identical block inside the `confirm-btn` click handler (search for the second occurrence of `const dPrice = state.carat ? diamondPrice[state.carat] : 0;` — it's inside `document.getElementById('confirm-btn').addEventListener(...)`). Change that line the same way:

```javascript
const dPrice = state.carat && diamondPrice[state.carat] ? diamondPrice[state.carat] : 0;
```

This one doesn't need the full null-guard treatment because it only runs after the "please select..." validation checks have already passed, and because — as noted above — this client-computed `total` is sent to the server purely as a display echo; the server recomputes it independently and does not trust it.

### Part 2 — Add price audit columns to the database

**In `models.py`**, find the `Submission` class:

```python
class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(50), nullable=True)
    carat = db.Column(db.String(50), nullable=True)
    style_type = db.Column(db.String(50), nullable=True)
    gold_purity = db.Column(db.String(50), nullable=True)
    weight = db.Column(db.Float, nullable=True)
    ring_size = db.Column(db.Float, nullable=True)
    total_price = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    user = db.relationship('User', backref=db.backref('submissions', lazy=True))
```

Add two columns right after `total_price`:

```python
class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(50), nullable=True)
    carat = db.Column(db.String(50), nullable=True)
    style_type = db.Column(db.String(50), nullable=True)
    gold_purity = db.Column(db.String(50), nullable=True)
    weight = db.Column(db.Float, nullable=True)
    ring_size = db.Column(db.Float, nullable=True)
    total_price = db.Column(db.Float, nullable=True)
    gold_rate_per_gram = db.Column(db.Float, nullable=True)
    price_source = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = db.Column(db.DateTime, nullable=True)
    user = db.relationship('User', backref=db.backref('submissions', lazy=True))
```

(`updated_at` is added too — right now there's no record of *when* an order was last edited, only when it was created, which matters once you're storing a rate that can change on edit.)

### ⚠️ CRITICAL EDGE CASE — this will crash the app if you skip it

`app.py` calls `db.create_all()` at import time (near the top of the file). **`db.create_all()` only creates tables that don't exist yet — it does NOT add new columns to a table that already exists.** `instance/database.db` already has a `submission` table from before this change. After you edit `models.py`, the running app's SQLAlchemy model will expect columns (`gold_rate_per_gram`, `price_source`, `updated_at`) that do not exist in the actual `.db` file on disk. The first attempt to insert or query a `Submission` will fail with `sqlite3.OperationalError: no such column: submission.gold_rate_per_gram` (or similar) and every page that touches submissions (`/history`, `/admin`, `/submit`) will 500.

You must migrate the existing database file. Two options — pick based on whether the current data matters:

**Option A (current data doesn't matter / this is still dev):** stop the server, delete `instance/database.db`, restart the server (it will be recreated fresh with the new schema via `db.create_all()`). You will need to re-set `ADMIN_PASSWORD` to reseed the admin account, and any existing submissions/users are lost. Only do this if you've confirmed with a real look at the data (`sqlite3 instance/database.db "SELECT COUNT(*) FROM submission;"`) that there's nothing worth keeping.

**Option B (preserve existing data — do this unless you've confirmed Option A is safe):** stop the server, then run:

```bash
sqlite3 instance/database.db "ALTER TABLE submission ADD COLUMN gold_rate_per_gram FLOAT;"
sqlite3 instance/database.db "ALTER TABLE submission ADD COLUMN price_source VARCHAR(20);"
sqlite3 instance/database.db "ALTER TABLE submission ADD COLUMN updated_at DATETIME;"
```

SQLite's `ALTER TABLE ... ADD COLUMN` is safe for this case (adding a nullable column with no default computation) and does not touch existing rows' other data. Existing rows will simply have `NULL` in the three new columns, which is fine — they were priced before this plan existed and there's no way to retroactively know their rate; the UI (Part 3 below) must handle `NULL` gracefully, not assume it's always populated.

After migrating, restart the server and confirm `/history` and `/admin` still load without error before proceeding.

### Part 3 — Compute and store the rate at submit/edit time

**In `app.py`**, find `compute_total()`:

```python
def compute_total(carat, gold, weight_grams):
    raw, _ = get_metal_prices()
    per_gram = raw[METAL_SYMBOL[gold]] * PURITY_MULTIPLIER[gold]
    return DIAMOND_PRICE[carat] + per_gram * weight_grams
```

Replace it with a version that also returns the rate and source, since both `submit()` and `edit_submission()` need to persist them:

```python
def compute_total(carat, gold, weight_grams):
    raw, source = get_metal_prices()
    per_gram = raw[METAL_SYMBOL[gold]] * PURITY_MULTIPLIER[gold]
    total = DIAMOND_PRICE[carat] + per_gram * weight_grams
    return total, per_gram, source
```

**This changes the function's return type from a single float to a 3-tuple.** Both call sites must be updated or the app will break (`total_price = compute_total(...)` would set `total_price` to a tuple, and `db.Column(db.Float)` would then either error or silently store garbage). Find both call sites:

In `submit()`:

```python
    try:
        total_price = compute_total(cleaned['carat'], cleaned['gold'], cleaned['weight'])
    except Exception:
        return jsonify({'status': 'error', 'message': 'invalid selection'}), 400

    submission = Submission(
        user_id=current_user.id,
        category=cleaned['category'],
        carat=cleaned['carat'],
        style_type=cleaned['type'],
        gold_purity=cleaned['gold'],
        weight=cleaned['weight'],
        ring_size=cleaned.get('ringSize'),
        total_price=total_price
    )
```

Change to:

```python
    try:
        total_price, rate_used, price_source = compute_total(cleaned['carat'], cleaned['gold'], cleaned['weight'])
    except Exception:
        return jsonify({'status': 'error', 'message': 'invalid selection'}), 400

    submission = Submission(
        user_id=current_user.id,
        category=cleaned['category'],
        carat=cleaned['carat'],
        style_type=cleaned['type'],
        gold_purity=cleaned['gold'],
        weight=cleaned['weight'],
        ring_size=cleaned.get('ringSize'),
        total_price=total_price,
        gold_rate_per_gram=rate_used,
        price_source=price_source
    )
```

In `edit_submission()`:

```python
    try:
        # ponytail: edit reprices at current metal rate; store rate-at-submit if order locking matters
        sub.total_price = compute_total(sub.carat, sub.gold_purity, sub.weight)
    except Exception:
        return jsonify({'success': False, 'message': 'invalid selection'}), 400
        
    db.session.commit()
    return jsonify({'success': True})
```

Change to:

```python
    try:
        sub.total_price, sub.gold_rate_per_gram, sub.price_source = compute_total(sub.carat, sub.gold_purity, sub.weight)
    except Exception:
        return jsonify({'success': False, 'message': 'invalid selection'}), 400

    sub.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    return jsonify({'success': True})
```

This removes the old `# ponytail:` comment because the plan resolves what it was flagging — the rate is now recorded, so "store rate-at-submit if order locking matters" is done (as an audit trail; the reprice-on-edit behavior itself is intentionally left as-is per this plan's Goal section, just no longer silent).

**Also add the import** `edit_submission` now needs `datetime` and `timezone` — check the top of `app.py`; it currently imports `from datetime import datetime, timedelta` but not `timezone`. Change that import line to:

```python
from datetime import datetime, timedelta, timezone
```

### Part 4 — Surface the audit trail in the UI

**In `templates/admin.html`**, inside the `<thead>` table row, add a column after `table_purity` (成色) and before `table_weight`:

```html
      <th data-i18n="table_rate">計價金價</th>
```

And in the `<tbody>` row, add the matching `<td>` after the `gold_purity` cell:

```html
      <td>{{ ("{:,.0f}".format(sub.gold_rate_per_gram) + ' (' + sub.price_source + ')') if sub.gold_rate_per_gram is not none else '-' }}</td>
```

**In `templates/history.html`**, do the same: add `<th data-i18n="table_rate">計價金價</th>` to the header row (after `table_purity`), and the matching `<td>` in the body row.

**In `static/js/i18n.js`**, add the new translation key to both the `zh` and `en` blocks. In the `zh` block, right after `"table_purity": "成色",` add:

```javascript
    "table_rate": "計價金價",
```

In the `en` block, right after `"table_purity": "Purity",` add:

```javascript
    "table_rate": "Rate Used",
```

**In `templates/index.html`**, inside the `{% if edit_sub %}` block near the top (where `window.editData` is set), add a visible notice for the user editing an order. Find:

```html
{% if edit_sub %}
<script>
  window.editData = {
    id: {{ edit_sub.id }},
    category: "{{ edit_sub.category }}",
    carat: "{{ edit_sub.carat }}",
    type: "{{ edit_sub.style_type }}",
    gold: "{{ edit_sub.gold_purity }}",
    weight: {{ edit_sub.weight if edit_sub.weight is not none else 'null' }},
    ringSize: {{ edit_sub.ring_size if edit_sub.ring_size is not none else 'null' }}
  };
</script>
{% endif %}

<h1><span data-i18n="calc_title">鑽石戒指／項鍊 價格試算</span>{% if edit_sub %} (編輯模式){% endif %}</h1>
```

Change the `<h1>` line to add a notice right after it:

```html
<h1><span data-i18n="calc_title">鑽石戒指／項鍊 價格試算</span>{% if edit_sub %} (編輯模式){% endif %}</h1>
{% if edit_sub %}
<p class="helper-text" data-i18n="edit_reprice_notice">儲存後將以目前金價重新計算總價。</p>
{% endif %}
```

Add the matching i18n keys in `static/js/i18n.js`: in `zh`, add `"edit_reprice_notice": "儲存後將以目前金價重新計算總價。",` and in `en`, add `"edit_reprice_notice": "Saving will recalculate the total using today's metal rate.",`.

## Edge cases found while exploring that a weaker model would miss

- **The `db.create_all()`-does-not-migrate problem above is the single biggest risk in this whole plan.** If you only edit `models.py` and restart, you get a 500 on every submission-related page. This is not hypothetical — it is guaranteed to happen, because `instance/database.db` already exists on disk right now with the old schema.
- **`compute_total`'s return type change is a breaking change to its signature.** There are exactly two call sites (`submit()` and `edit_submission()`) — both are covered above, but if any future code adds a third caller expecting a single float, it will break silently (a tuple where a float is expected won't throw at assignment time in Python, only later when arithmetic is attempted on it, which could surface far from the actual bug).
- **Existing rows will have `NULL` for `gold_rate_per_gram` and `price_source` after migration (Option B).** The template snippets above already guard for `is not none`, rendering `-` for old rows. Do not remove that guard — old orders genuinely have no recorded rate and showing a fabricated `0` or `-` that looks like a real value would be worse than an honest blank.
- **`price_source` will be the string `"live"` or `"fallback"`** (matching what `get_metal_prices()` already returns and uses internally) — not a boolean. The admin table snippet formats it as `"NT$X (live)"` or `"NT$X (fallback)"`; keep that human-readable, since "fallback" pricing on a real order is something an admin should be able to spot at a glance (it means GoldAPI was down/misconfigured when that order was priced).

## Acceptance criteria

1. `grep -n "24000" static/js/script.js` returns nothing (the hardcoded diamond price literal is gone from the client).
2. With the server running, opening the calculator, selecting a carat, and watching the network tab: the "鑽石價格" (diamond price) figure only appears after `/api/prices` responds — briefly showing a loading state, not `0` or `NaN`, if you select a carat before the fetch resolves (hard to trigger manually since the fetch is fast, but the code path must not throw — check the browser console for errors after reloading and immediately clicking through all 4 steps).
3. `sqlite3 instance/database.db ".schema submission"` shows `gold_rate_per_gram`, `price_source`, and `updated_at` columns.
4. Submitting a new order via the calculator UI results in a row in `submission` with non-null `gold_rate_per_gram` and `price_source` set to either `live` or `fallback`.
5. Editing an existing pending order updates `updated_at` to the current time and re-populates `gold_rate_per_gram`/`price_source` with the rate at edit time (which may differ from the original submit-time rate — confirm by editing an order, then checking the DB row's `gold_rate_per_gram` changed if the live rate has moved, or stayed the same if using fallback prices with no live connection).
6. The admin (`/admin`) and history (`/history`) pages both display a "計價金價" / "Rate Used" column with a value like `2,412 (live)` for new orders and `-` for any pre-migration orders that have `NULL` in that column.
7. Opening the calculator in edit mode (`/calculator?edit_id=<id>` for a pending order you own) shows the notice "儲存後將以目前金價重新計算總價。" (or its English equivalent when language is toggled) directly under the page title.
8. No existing functionality regresses: submitting, editing, and deleting orders all still work; `/history` and `/admin` load without server errors.
