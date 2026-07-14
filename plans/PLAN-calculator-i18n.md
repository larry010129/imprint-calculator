# PLAN: Make the EN/中文 toggle actually work on the calculator page

## Goal
The navbar has a language toggle (i18n.js) that translates any element with `data-i18n`. It works on Home, History, Admin, and Success — but the calculator (`templates/index.html` + `static/js/script.js`), the app's main page, has **zero** `data-i18n` attributes and a dozen hardcoded Chinese strings in JS (alerts, helper text, button labels, dropdown options). Toggling EN on the calculator changes only the navbar. Finish the feature where it matters most.

Scope decision (deliberate): static page text translates via the existing `data-i18n` mechanism; JS-generated strings read the current language at the moment they're produced. Strings already rendered by JS before a toggle (ring-size options, summary values) re-render on toggle via one small hook. No i18n framework, no server-side locale.

## Exact files to touch
- `static/js/i18n.js` — add keys; expose a `t()` helper; emit an event on language change.
- `templates/index.html` — add `data-i18n` attributes.
- `static/js/script.js` — replace hardcoded strings with `t()`; re-render dynamic text on language change.

## Step-by-step implementation

### 1. i18n.js — expose a translation helper + change event
After the `translations` object and `currentLang` (line 74), add:
```js
window.t = key => (translations[currentLang] && translations[currentLang][key]) || key;
```
At the END of `applyLanguage(lang)` add:
```js
document.dispatchEvent(new CustomEvent('langchange'));
```
Add these keys to BOTH `zh` and `en` blocks (zh values = the current hardcoded strings, copy them exactly from the files; en values as given):

| key | zh (from code) | en |
|---|---|---|
| `calc_title` | 鑽石戒指／項鍊 價格試算 | Diamond Ring / Necklace Price Calculator |
| `step_category` | 選擇品項 | Select Item |
| `cat_ring` | 戒指 | Ring |
| `cat_necklace` | 項鍊 | Necklace |
| `step_carat` | 選擇克拉數 | Select Carat |
| `step_type` | 選擇款式 | Select Style |
| `step_gold` | 選擇金屬成色 | Select Metal |
| `step_ring_size` | 選擇戒圍（粗估金重） | Select Ring Size (weight estimate) |
| `step_weight` | 輸入金重 | Enter Metal Weight |
| `weight_label` | 金重 | Metal Weight |
| `ring_size_placeholder` | 請選擇戒圍 | Select ring size |
| `ring_size_option` | 台灣戒圍 # | TW ring size # |
| `helper_estimate` | 依戒圍粗估金重，可於下方微調 | Estimated from ring size; fine-tune below |
| `helper_no_gold` | 尚未選擇金屬成色，暫以18K密度估算，選擇金屬後將自動更新 | No metal selected; estimating with 18K density, updates when chosen |
| `sum_item` / `sum_carat` / `sum_style` / `sum_gold` / `sum_weight` / `sum_goldprice` / `sum_diamond` / `sum_metal_cost` / `sum_total` | 品項／克拉／款式／成色／金重／即時金價／鑽石價格／金屬費用／總價 | Item / Carat / Style / Metal / Weight / Live Metal Price / Diamond Price / Metal Cost / Total |
| `alert_pick_category` | 請先選擇品項！ | Please select an item first! |
| `alert_pick_carat` | 請選擇克拉數！ | Please select a carat! |
| `alert_pick_type` | 請選擇款式！ | Please select a style! |
| `alert_pick_gold` | 請選擇金屬成色！ | Please select a metal! |
| `alert_pick_ring_size` | 請選擇戒圍！ | Please select a ring size! |
| `alert_enter_weight` | 請輸入金重！ | Please enter the metal weight! |
| `btn_confirm` | 確認送出 | Confirm & Submit |
| `btn_update` | 更新訂單 (Update Order) | Update Order |
| `btn_submitting` | 送出中... | Submitting... |
| `save_failed` | 儲存失敗:  | Save failed:  |
| `generic_error` | 發生錯誤 | An error occurred |
| `price_unavailable` | 無法取得金價 | Metal price unavailable |
| `total_unavailable` | 無法計算 | Cannot compute |
| `goldprice_failed` | 無法取得即時金價 | Live metal price unavailable |
| `goldprice_loading` | 讀取中... | Loading... |
| `unit_g` / `unit_chin` / `unit_taijin` | 克／錢／台斤 | g / mace / catty |

### 2. index.html — attach `data-i18n`
Add `data-i18n="<key>"` to: the `<h1>` (keep the 編輯模式 suffix outside the attribute-bearing span — wrap the base title in a `<span data-i18n="calc_title">`), the four step `<h2>`/`<h3>` headings, the two category buttons, the weight label, the summary `<p>` label texts (wrap each label in a `<span data-i18n=...>` so the value `<span>`s aren't clobbered — i18n.js sets `textContent`, which would wipe nested value spans if you put the attribute on the whole `<p>`), the confirm button (`data-i18n="btn_confirm"`), the ring-size placeholder `<option>`, the three unit `<option>`s, and the 讀取中... span (`data-i18n="goldprice_loading"`).

### 3. script.js — dynamic strings
- Replace every hardcoded Chinese string with `t('key')`: the six alerts (lines 339–360), helper text in `updateRingHelperText` (lines 232–234), 無法取得金價 / 無法計算 in `updateTotal` (280–281), 無法取得即時金價 in `loadMetalPrices` (90), button text 送出中.../確認送出/更新訂單 (365, 313, 398), 儲存失敗/發生錯誤 (391, 395).
- Ring-size options: in `populateRingSizeOptions` use `opt.textContent = t('ring_size_option') + size;` and give each option `opt.dataset.size = size`.
- Unit label map: change `unitLabel` lookups to `t('unit_' + unit)` in `updateWeightSummaryDisplay` (delete the `unitLabel` const).
- Re-render on toggle: at the end of script.js add
  ```js
  document.addEventListener('langchange', () => {
    document.querySelectorAll('#ring-size-select option[data-size]').forEach(o => {
      o.textContent = t('ring_size_option') + o.dataset.size;
    });
    updateWeightSummaryDisplay();
    updateRingHelperText();
    updateTotal();
  });
  ```

## Edge cases a weaker model would miss
- **Script load order**: index.html loads `script.js` inside the content block, BEFORE `base.html` loads `i18n.js` at the end of `<body>`. So `window.t` does not exist while script.js's top level runs. Two consequences: (a) `t()` may only be called inside functions/handlers that run after DOM load — never at script.js top level; (b) `populateRingSizeOptions()` runs at top level (line 308) and would crash calling `t()`. Fix: guard with a fallback at the top of script.js: `const t = k => (window.t ? window.t(k) : k);` — wait, that shadows and freezes... NO: define `function tr(k) { return window.t ? window.t(k) : k; }` in script.js and use `tr()` everywhere in that file. The initial zh render then comes from `applyLanguage(currentLang)` on DOMContentLoaded plus the `langchange` listener — make `applyLanguage` also fire the event on init (it does, since the DOMContentLoaded init calls `applyLanguage`), which re-renders the option texts correctly even on first load.
- **`data-i18n` on elements with child spans wipes the children**: i18n.js sets `el.textContent`, destroying nested elements. Summary lines like `<p>品項：<span id="sum-cat">-</span></p>` MUST have the label wrapped in its own span; putting `data-i18n` on the `<p>` deletes `#sum-cat` and script.js then crashes on `getElementById(...).textContent`.
- **The confirm button's `data-i18n` fights the JS that rewrites its text** (edit mode sets 更新訂單, submit sets 送出中...). On langchange, i18n.js will reset the button to `btn_confirm` even in edit mode. Handle it in the `langchange` listener: `document.getElementById('confirm-btn').textContent = window.editData ? tr('btn_update') : tr('btn_confirm');` — and therefore do NOT put `data-i18n` on the button at all (remove it from step 2's list; JS owns that element's text).
- **`selectCategory` reads `btn.textContent` as the summary label** (script.js line 291: `selectCategory(btn.dataset.cat, btn.textContent)`) — after translation the summary shows whatever language the button showed when clicked, and goes stale on toggle. Acceptable drift for already-selected values EXCEPT it feeds `#sum-cat`; the `langchange` listener above doesn't fix it. Cheap fix: change the wiring to `selectCategory(btn.dataset.cat, tr(btn.dataset.cat === 'ring' ? 'cat_ring' : 'cat_necklace'))` and in the langchange listener re-set `#sum-cat` the same way when `state.category` is set.
- **Alerts/`goldLabel`/`types` names (款式 A, 18K金) are product vocabulary**, shared with server-side labels — leave `goldLabel` and `types` untranslated (they match what History/Admin render from the server). Translating them client-side but not server-side would make the same order read differently on two pages.
- **`success.html`, navbar, tables already work** — do not touch them; adding duplicate keys with different values breaks existing pages' translations.

## Acceptance criteria
1. On `/calculator`, click EN: page title, step headings, category buttons, summary labels, ring-size options, unit options, and placeholder text all switch to English; click 中文: all revert. No element disappears (check `#sum-cat`, `#sum-total` still update when selecting).
2. With EN active: click 確認送出 with nothing selected → English alert. Complete a submission → button shows "Submitting…" then navigates to `/success` (English if toggled).
3. Edit mode (`/calculator?edit_id=N`) with EN: button reads "Update Order", and toggling language keeps it "Update Order"/"更新訂單" — never "Confirm & Submit".
4. Select 戒指 in zh, toggle EN → summary Item row shows "Ring" (not stale 戒指).
5. History/Admin/Home/Success pages translate exactly as before (regression check).
6. No console errors on page load in either language (verifies the script-order guard).
