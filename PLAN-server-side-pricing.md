# PLAN: Move pricing server-side (hide GoldAPI key, stop trusting client prices, fix stale price on edit)

## Goal
Three related defects, one root cause — all pricing lives in the browser:
1. The GoldAPI key is exposed in `static/js/script.js` line 24 (the code comment there explicitly says to move it behind a backend proxy).
2. `/submit` (`app.py` line 98) stores whatever `totalPrice` the client sends. Anyone logged in can POST a fake price; it also means every fallback/hiccup in the browser's price fetch silently produces wrong stored totals.
3. `/edit` (`app.py` line 161) updates `weight` but never recomputes `total_price`, so an edited order's stored price no longer matches its weight.

Fix: the server owns the price table and metal-price fetch; the client fetches prices from our own endpoint for display; the server computes `total_price` on submit and edit, ignoring any client-sent total.

## Exact files to touch
- `app.py` — add pricing constants, a cached metal-price fetcher, a `/api/prices` endpoint; compute totals in `/submit` and `/edit`.
- `static/js/script.js` — delete the GoldAPI key and direct fetch; fetch `/api/prices` instead; stop sending `totalPrice` as authoritative (server returns the saved total).
- `requirements.txt` — NO change needed (use stdlib `urllib.request`, not `requests`).

## Step-by-step implementation

### 1. Add pricing constants to `app.py` (near the top, after config)
These duplicate the JS constants — the server copy is now the source of truth:
```python
import json, time, urllib.request

GOLDAPI_KEY = os.environ.get('GOLDAPI_KEY', 'goldapi-eb915d55941859c5bec9d3d1cbaff238-io')

DIAMOND_PRICE = {"0.1": 24000, "0.3": 79000, "0.5": 98000, "1": 250000}
PURITY_MULTIPLIER = {"18k": 0.75, "999": 0.999, "pt": 1, "silver925": 0.925}
METAL_SYMBOL = {"18k": "XAU", "999": "XAU", "pt": "XPT", "silver925": "XAG"}
FALLBACK_TWD_PER_GRAM = {"XAU": 2400, "XPT": 1050, "XAG": 30}
TROY_OZ_GRAMS = 31.1034768
```
CRITICAL: `DIAMOND_PRICE` keys are the exact strings `"0.1"`, `"0.3"`, `"0.5"`, `"1"` — the client sends carat as a string and `"1"` must NOT be written as `"1.0"`, it won't match.

### 2. Add a cached fetcher in `app.py`
```python
_price_cache = {"prices": None, "fetched_at": 0, "source": "fallback"}
PRICE_TTL_SECONDS = 600  # goldapi free tier is heavily rate-limited; do not lower

def get_metal_prices():
    """TWD per gram for XAU/XPT/XAG, cached. Never raises."""
    now = time.time()
    if _price_cache["prices"] and now - _price_cache["fetched_at"] < PRICE_TTL_SECONDS:
        return _price_cache["prices"], _price_cache["source"]
    prices = {}
    source = "live"
    for symbol in ("XAU", "XPT", "XAG"):
        try:
            req = urllib.request.Request(
                f"https://www.goldapi.io/api/{symbol}/TWD",
                headers={"x-access-token": GOLDAPI_KEY})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            prices[symbol] = data["price"] / TROY_OZ_GRAMS  # API returns TWD per troy oz
        except Exception:
            prices[symbol] = FALLBACK_TWD_PER_GRAM[symbol]
            source = "fallback"
    _price_cache.update(prices=prices, fetched_at=now, source=source)
    return prices, source
```

### 3. Add the endpoint in `app.py`
```python
@app.route('/api/prices')
@login_required
def api_prices():
    raw, source = get_metal_prices()
    per_gram = {gold: raw[METAL_SYMBOL[gold]] * PURITY_MULTIPLIER[gold]
                for gold in PURITY_MULTIPLIER}
    return jsonify({'diamond': DIAMOND_PRICE, 'perGram': per_gram, 'source': source})
```

### 4. Add a server-side total helper and use it in `/submit` and `/edit`
```python
def compute_total(carat, gold, weight_grams):
    raw, _ = get_metal_prices()
    per_gram = raw[METAL_SYMBOL[gold]] * PURITY_MULTIPLIER[gold]
    return DIAMOND_PRICE[carat] + per_gram * weight_grams
```
- In `submit()`: replace `total_price=data.get('totalPrice')` with `total_price=compute_total(data.get('carat'), data.get('gold'), data.get('weight'))`. Return the saved total: `return jsonify({'status': 'success', 'total_price': submission.total_price})`.
- In `edit_submission()`: after applying field updates, recompute — `sub.total_price = compute_total(sub.carat, sub.gold_purity, sub.weight)` — then commit. Delete the `if data.get('totalPrice') is not None:` branch entirely.
- NOTE: `compute_total` will `KeyError` on bad carat/gold values. If PLAN-validate-submissions has been done first, inputs are already whitelisted. If not, wrap the call: on `KeyError`/`TypeError` return `jsonify({'status': 'error', 'message': 'invalid selection'}), 400`.

### 5. Rewrite the price-loading part of `static/js/script.js`
- DELETE: the `GOLDAPI_KEY` constant (line 24), `metalSymbol` (line 20), the whole `fetchMetalPriceTwd()` function (lines 91–114), and the fallback price table inside it.
- REPLACE `loadMetalPrices()` body with one fetch:
  ```js
  async function loadMetalPrices() {
    try {
      const res = await fetch("/api/prices");
      if (!res.ok) throw new Error(`API returned ${res.status}`);
      const data = await res.json();
      Object.keys(data.perGram).forEach(goldId => { pricePerGram[goldId] = data.perGram[goldId]; });
      updateGoldPriceDisplay();
      updateTotal();
    } catch (err) {
      document.getElementById("sum-goldprice").textContent = "無法取得即時金價";
      console.error("metal price fetch failed:", err);
    }
  }
  ```
- Keep `pricePerGram` (line 30) as-is; `pricePerGramRaw` (line 27) is now unused — delete it.
- In the confirm-button handler: keep sending the payload (server ignores `totalPrice` now, harmless), but after a successful response use `result.total_price` for the success message if you show one. The displayed running total in the sidebar stays client-computed for responsiveness — that's display only.

## Edge cases a weaker model would miss
- **Carat dict key `"1"` vs `"1.0"`** — the client sends the literal string `"1"`. A float-keyed or `"1.0"`-keyed dict silently breaks 1ct pricing.
- **GoldAPI returns TWD per TROY OUNCE, not per gram.** Divide by 31.1034768. Forgetting this inflates metal cost ~31×.
- **The free-tier key is rate-limited** — that's why the current JS has fallback prices. Without the 10-minute server cache, every page load burns 3 API calls and you'll hit the cap within a day. Cache is not optional.
- **`urlopen` without `timeout=` hangs the Flask worker** if goldapi stalls; the dev server is single-threaded-ish, so one hung request can freeze the whole app. `timeout=5` is required.
- **Never raise from `get_metal_prices()`** — a pricing hiccup must degrade to fallback prices, not 500 the submit flow.
- **Client price drift is expected**: sidebar total is computed from prices fetched at page load; the server recomputes at submit time. They can differ by a few NT$ if a cache refresh happened in between. Server value wins; do not "fix" this by trusting the client again.
- **Edit reprices at today's rate**, not the original submit-time rate, because we don't store the rate used. This is a deliberate, acceptable simplification — note it with a `# ponytail:` comment: `# ponytail: edit reprices at current metal rate; store rate-at-submit if order locking matters`.
- **`weight` from the client is grams** — `state.weight` in script.js is always internal grams regardless of the display unit (克/錢/台斤). Do not convert again server-side.
- **Do not add the `requests` library** — stdlib `urllib.request` covers this; keep requirements.txt unchanged.
- **The old key must be fully removed from script.js**, not just unused — it's still exposed if the string remains in the served file. (It's already public in git-less history here, but rotating the goldapi key afterwards is a good idea; note that to the user, key rotation happens on goldapi.io, not in code.)

## Acceptance criteria
1. `grep -rn "goldapi" static/` returns nothing.
2. Logged in, `GET /api/prices` returns JSON with `diamond` (4 keys), `perGram` (4 keys: 18k, 999, pt, silver925), and `source` of `"live"` or `"fallback"`. Logged out, it redirects to login.
3. Two rapid successive requests to `/api/prices` hit the goldapi API at most once (check: second response is instant; or temporarily log inside the fetch loop).
4. Calculator page still shows a live gold price per gram and computes a sidebar total.
5. Submit an order: the stored `total_price` in the DB equals `DIAMOND_PRICE[carat] + perGram[gold] * weight` within rounding — and does NOT change if you tamper with `totalPrice` in the browser devtools before submitting.
6. Edit a pending order's weight from 3.0g to 6.0g in History: the stored `total_price` increases accordingly (previously it stayed frozen).
7. Disconnect from the internet (or point the URL at a bad host) and restart: `/api/prices` still returns 200 with `source: "fallback"`, and submits still work.
