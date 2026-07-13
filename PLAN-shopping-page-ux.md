# PLAN: Shopping-page UX (keep all calculator functions)

## Rank: UX / product (not blocking ops)

## Goal

Transform `/calculator` from a **step-by-step configurator** into a **product shopping experience** — browse → configure → review → submit — while **keeping every existing business function**:

- Live metal prices (`/api/prices`, GoldAPI + fallback)
- Weight lookup + pricing (`WEIGHT_TABLE`, `compute_total`)
- All category rules (bracelet carats, chain 分, ring size surcharge, 9K chain rule, bracelet 9K/14K/18K color)
- Submit / edit / delete / history / admin status / profile / auth / audit fields

**Non-goal:** real payment gateway, inventory, or public consumer checkout. This is still a **B2B store order tool** that *feels* like shopping.

---

## Current state (why it doesn’t feel like shopping)

| Area | Today | Shopping expectation |
|------|--------|----------------------|
| Entry | Login → “計算機” wizard | Catalog / category landing with product cards |
| Layout | Vertical STEP 1–6 rail, steps appear below | Product hero + options panel side-by-side |
| Selection | Text buttons, steps unlock sequentially | Variant pickers on one product view (swatches, chips) |
| Image | Sidebar preview after style pick | Primary product gallery, always visible |
| Price | Accounting-style line items | Prominent total + optional “price breakdown” toggle |
| CTA | 確認送出 at bottom of summary | Sticky “加入訂單” / “Request quote” with enabled/disabled states |
| Progress | Hidden steps = lost context | Visible “your configuration” chip summary |
| Post-submit | Generic success page | Order confirmation with order # + link to history |
| Nav | 系統首頁 / 計算機 / 歷史 | Shop / Orders / Account (same routes, new labels) |

**Core logic in `static/js/script.js` is fine** — the gap is information architecture, layout, and interaction pattern.

---

## Target user flow (same data, different presentation)

```
Home (catalog)
  → Category page (e.g. 手鍊) — grid of styles A/B/C
    → Product page (one style) — gallery + variant options + live price
      → Review drawer / sticky bar — confirm
        → Success — order saved (existing Submission)
```

Edit mode (`?edit_id=`) maps to **Product page pre-filled**, CTA = “更新訂單”.

---

## What must NOT change (function preservation checklist)

These stay as-is in **Application / Gateway** layer unless noted:

- [ ] `POST /submit`, `POST /edit/<id>`, validation in `validation.py`
- [ ] `lookup_weight`, `compute_total`, price audit on `Submission`
- [ ] `/api/prices` payload (`weightTable`, `laborFee`, ring bounds, etc.)
- [ ] Category-specific rules in JS (`CATEGORY_*`, `braceletNeedsColorStep`, chain 9K+A rule)
- [ ] CSRF + login on all write paths
- [ ] History, admin status, profile, register rate limit
- [ ] i18n keys (extend, don’t remove)

---

## Phase 1 — Product page layout (highest leverage, no new routes)

**Goal:** One screen feels like “buying one product” instead of a form wizard.

### 1.1 Page structure (`templates/index.html` + `style.css`)

Replace left “step stack” with **two-column product layout**:

```
┌─────────────────────────────────────────────────────────┐
│  Breadcrumb: 首頁 > 手鍊 > 銘印手鍊                        │
├──────────────────────┬──────────────────────────────────┤
│  Product gallery     │  Product title + short desc      │
│  (large image)       │  Variant: 克拉 (chips)            │
│                      │  Variant: 成色 (chips)            │
│                      │  Variant: 顏色 (swatches)         │
│                      │  Variant: 戒圍 (ring only)        │
│                      │  ─────────────────────────        │
│                      │  NT$ 總價 (large)                 │
│                      │  [▼ 價格明細] (collapsible)       │
│                      │  [ 加入訂單 ] (primary CTA)       │
└──────────────────────┴──────────────────────────────────┘
```

**Files:** `templates/index.html`, `static/css/style.css`  
**JS:** Reuse `state`, `updateSummary()`, `select*` handlers — only change **what DOM they update** and **visibility rules** (show all relevant variant groups for category, disable invalid combos instead of hiding whole steps).

### 1.2 Category as catalog entry (still single route)

**Option A (minimal):** Keep category buttons but style as **catalog tiles** with icons/thumbnails on `/calculator`.  
**Option B (better):** `/calculator?category=bracelet` or `/shop/bracelet` renders category grid only; clicking a style goes to `?category=bracelet&type=B`.

**New template optional:** `templates/shop_category.html` — or one `index.html` with `view=catalog|product` driven by query params.

**JS changes:**
- `selectCategory` → navigate or set view + render style grid full-width
- `selectType` → switch to product view (set type, show variant panel)
- Remove sequential `hidden` on steps; use **sections** always visible when applicable

### 1.3 Variant controls (shopping patterns)

| Option | Current | Shopping control |
|--------|---------|------------------|
| Style | Card grid STEP 2 | Category catalog + product hero (already have images) |
| Carat | Buttons STEP 3 | Horizontal **size chips** under “鑽石克拉” |
| Metal | Buttons STEP 4 | **Metal chips** with labels 9K/14K/18K/Pt/銀 |
| Color | Buttons STEP 5 | **Color swatches** (circle + label), title 9K顏色 / 14K顏色 for 手鍊 |
| Ring size | Button row STEP 6 | **Size selector** row or compact dropdown styled as chips |

**Invalid options:** `disabled` + tooltip (not removed from DOM) — e.g. chain 9K + style B/C greyed out.

### 1.4 Price presentation

- **Hero price:** `#sum-total` large, always visible when calculable
- **Breakdown:** collapse `<details>` or accordion — diamond / metal / labor / surcharge / gold rate
- **Loading:** skeleton on price until `/api/prices` returns (keep `goldprice_loading` pattern)
- **Sticky mobile bar:** fixed bottom — total + CTA (common e-commerce pattern)

**Files:** `index.html`, `style.css`, small `updateSummary()` tweak to toggle CTA disabled state

### 1.5 CTA states (shopping affordance)

| State | Button |
|-------|--------|
| Incomplete config | Disabled “請完成選項” |
| Price loading | Disabled “計算中…” |
| Ready | Primary “加入訂單” / “確認送出” |
| Edit mode | “更新訂單” |

Reuse existing validation alerts short-term; later inline field errors under each variant group.

### 1.6 Selection feedback (keep current rules)

- **Style cards only:** keep 「已選」 corner tag (do not put on variant chips)
- **Other options:** filled dark + cyan underline (current `.active` buttons)
- **Configuration summary:** horizontal chips under title — `手鍊 · 銘印手鍊 · 0.3ct · 14K · K白` — click chip to scroll to section

---

## Phase 2 — Catalog & navigation

### 2.1 Home → shop front

**File:** `templates/home.html`

- Replace single “開始試算” with **category grid** (5 tiles using existing images)
- Each links to `/calculator?category=pendant` etc.

### 2.2 Nav rename (cosmetic, same routes)

| Route | Current label | Shop label |
|-------|---------------|------------|
| `/` | 系統首頁 | 商品 |
| `/calculator` | 計算機 | (breadcrumb only, or “訂製”) |
| `/history` | 歷史紀錄 | 我的訂單 |
| `/profile` | 帳戶 | 帳戶 |

**Files:** `i18n.js`, `base.html`

### 2.3 Breadcrumbs

Add component in `index.html` / shared partial:

`商品 > {category} > {style name}` — updates from `state` in JS.

---

## Phase 3 — Order confirmation & history (shop post-checkout)

### 3.1 Success page as order confirmation

**File:** `templates/success.html`

- Show last submission id (pass `submission_id` in redirect query or session flash)
- Summary line: style, total, date
- CTAs: “繼續選購”, “查看訂單”

**Gateway change:** `submit()` redirect to `/success?order=<id>` (optional small route tweak)

### 3.2 History as “My orders”

**File:** `templates/history.html`

- Card layout per order (image, title, total, status badge)
- Keep edit/delete for pending — label “修改訂單” / “取消訂單”
- Status pills match admin (待處理 / 確認 / 處理中 / 完成)

No schema change required.

---

## Phase 4 — Polish & mobile

- **Mobile:** gallery full-width top, variants scroll, sticky CTA bottom
- **Images:** consistent aspect ratio; placeholder for missing assets
- **Accessibility:** variant groups as `fieldset` + `legend`, keyboard focus on chips
- **Performance:** don’t re-fetch `/api/prices` on every variant click (already cached TTL)

---

## Phase 5 — Optional enhancements (later)

Only if Larry wants deeper “shop” — **not required for MVP shopping feel**:

| Feature | Notes |
|---------|--------|
| URL shareable config | `?category=bracelet&type=B&carat=0.3&gold=14k&color=white` — deep link for stores |
| Compare styles | Side-by-side two styles same category |
| Saved drafts | localStorage before submit |
| Product copy | Short descriptions per style in i18n |
| Color-specific images | `bracelet-B-rose.jpg` — needs asset pipeline |
| Public catalog | read-only browse without login (still submit requires auth) |

---

## File change map (by phase)

| Phase | Templates | Static | Gateway | Tests |
|-------|-----------|--------|---------|-------|
| 1 | `index.html` | `style.css`, `script.js` | — | extend UI smoke in `test_routes.py` optional |
| 2 | `home.html`, `base.html` | `i18n.js`, `style.css` | optional query on `/calculator` | — |
| 3 | `success.html`, `history.html` | `style.css` | `routes.py` redirect param | 1 route test for success query |
| 4 | — | responsive CSS | — | — |

**Do not split pricing logic** — keep SSoT in `pricing.py` + `/api/prices`.

---

## `script.js` refactor strategy (avoid big-bang)

1. Extract **view layer** from **state layer**:
   - `state.js` — category, type, gold, color, carat, ringSize (unchanged)
   - `pricing.js` — loadMetalPrices, updateSummary, lookupWeight
   - `shop-ui.js` — renderVariantPanels(), updateBreadcrumb(), updateCtaState()
2. Keep `selectCategory`, `selectType`, etc. as state mutators; UI listens and re-renders panels.
3. Replace `classList.add("hidden")` on steps with `renderProductPage(state)` that shows/hides **sections** by category rules.

This can be done incrementally inside existing `script.js` before splitting files.

---

## Edge cases (must still work after UX change)

- [ ] Edit mode pre-fill cascade (`window.editData`)
- [ ] Chain: carat = 3fen/4fen, color from style, double metal price
- [ ] Bracelet: 0.1–1.0ct, 9K/14K/18K color step labels
- [ ] Ring: ring size required, surcharge in breakdown
- [ ] Earring: no pt950/s925 in metal list
- [ ] Price re-fetch on edit save (reprice notice)
- [ ] Lang toggle updates variant labels + breadcrumbs
- [ ] Admin/provider role nav differences

---

## Acceptance criteria

### Phase 1 done when:
1. User can configure a full item on **one product view** without scrolling through STEP 1–6 unlock sequence.
2. Product image is **primary left (desktop) or top (mobile)**, price block separate with collapsible breakdown.
3. All 5 categories submit successfully with same payloads as today.
4. Style cards retain 「已選」 tag; other variants use chip active state without covering text.
5. CTA disabled until valid; enabled shows live total.

### Phase 2 done when:
6. Home shows category catalog; user reaches product view in ≤2 clicks.
7. Breadcrumb reflects current selection.

### Phase 3 done when:
8. Success page shows order reference; history reads as order list with images.

---

## Suggested implementation order

1. **Phase 1.1 + 1.4 + 1.5** — layout + price + CTA (biggest feel change, ~1–2 sessions)
2. **Phase 1.3 + 1.6** — variant chips + config summary
3. **Phase 1.2** — catalog entry via query param
4. **Phase 2** — home + nav + breadcrumbs
5. **Phase 3** — success + history cards
6. **Phase 4** — mobile sticky bar + a11y pass

---

## Out of scope (explicit)

- Payment processing (Stripe, etc.)
- SKU/inventory/stock counts
- Shipping address / logistics
- Multi-item cart (multiple products one checkout) — current model is **one Submission = one configured piece**; cart would need schema + API design later
- Rewriting backend RAG layout or pricing formulas

---

## Open questions for Larry (before Phase 2+)

1. **One product URL per style** — OK with query params, or want `/shop/bracelet/B` paths?
2. **Cart** — ever need multiple items per order, or always one piece per submit?
3. **Browse without login** — stores see catalog before login, or keep login wall?
4. **Marketing copy** — short descriptions per style, or images + names only?

---

*Plan written for codebase state as of 2026-07-08. All existing PLAN-*.md operational items remain independent.*
