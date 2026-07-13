# PLAN: Fix silent order corruption in the new edit flow

## Goal
The new edit-in-calculator flow (`/calculator?edit_id=N` → full re-selection → POST `/edit/<id>`) silently corrupts orders in two ways:

1. **Category is never updated.** The client sends the full state including `category`, but `edit_submission()` (`app.py` lines 320–324) applies weight/ringSize/carat/type/gold and skips `category`. Edit a ring into a necklace → DB still says `ring`.
2. **Stale ring size is never cleared.** When the edited order becomes a necklace, the payload has `ringSize: null`; validation drops `None` values, and `if 'ringSize' in cleaned` never fires — so the old ring size stays on a necklace order. Combined with (1), an edited order can be a chimera: `category=ring`, style/carat of the new selection, ring_size from the old one.

There's also a validation loophole: with `partial=True`, editing to `category=ring` without a ring size passes (the "ringSize required for rings" rule only runs when `not partial`).

Root cause: `/edit` still validates as a *partial* update, but its only caller (the calculator in edit mode, `static/js/script.js` lines 311–400) always sends a **complete** state. Fix: validate edits as full submissions and apply every field.

## Exact files to touch
- `app.py` — `edit_submission()` only.
- `test_validation.py` — no change needed (keep `partial` param in the validator; the tests use it).

## Step-by-step implementation
1. In `app.py`, `edit_submission()` (line 303): change the validation call from
   `validate_submission_fields(data, partial=True)` to
   `validate_submission_fields(data)` (full validation — every field required, ring⇒ringSize enforced).
2. Replace the five conditional assignments (lines 320–324) with unconditional ones:
   ```python
   sub.category = cleaned['category']
   sub.carat = cleaned['carat']
   sub.style_type = cleaned['type']
   sub.gold_purity = cleaned['gold']
   sub.weight = cleaned['weight']
   sub.ring_size = cleaned.get('ringSize')   # None for necklaces — clears stale size
   ```
   The `.get()` for ringSize is the fix for defect 2: necklaces must NULL it out.
3. Leave `compute_total` recompute and the commit as they are.
4. Do NOT remove the `partial` parameter from `validate_submission_fields` — `test_validation.py` exercises it and a future partial API could use it. Only the call site changes.

## Edge cases a weaker model would miss
- **`cleaned.get('ringSize')` vs `if 'ringSize' in cleaned`** is the entire fix for the stale-size bug. Keeping the conditional style "to be safe" preserves the corruption.
- **The old edit modal is gone** — `templates/history.html` now links to `/calculator?edit_id=N` (line 53); there is no other caller of `/edit` sending partial payloads. Full validation cannot break an existing client.
- **The client always sends the whole state**: script.js's confirm handler blocks submission until category/carat/type/gold/weight (+ringSize for rings) are all chosen, and edit mode pre-clicks every selection from `window.editData` (script.js lines 311–335). So requiring all fields server-side matches reality.
- **Payload has extra keys** (`weightSource`, `weightUnit`, `totalPrice`) — the validator ignores unknown keys; don't add rejection for them.
- **Ring→necklace edit is the test that matters**, not necklace→ring: the client hides the ring-size selector for necklaces, so `ringSize` arrives as `null` and previously survived. Necklace→ring is already forced correct by client validation (alert 請選擇戒圍).
- **`/calculator?edit_id=X` with a non-numeric or foreign id** is already handled (app.py lines 166–172: ownership + pending checks, redirect to history). Don't re-add checks in `/edit` — it has its own ownership/status guards (lines 307–310). Both layers already exist; touch neither.
- **Repricing on edit is intentional** — the `# ponytail:` comment at line 327 documents that edits reprice at the current metal rate. Leave it.

## Acceptance criteria
1. `python test_validation.py` still prints `all validation checks passed`.
2. Manual flow — create a pending **ring** order (e.g. 0.5ct, A, 18k, size 12). In History click 編輯, switch category to 項鍊 (necklace), pick carat/style/gold, enter weight, submit. In the DB / History table the row now shows: category 項鍊, ring size `-` (NULL), and a total consistent with the new selection. (Before the fix: category stays 戒指 and ring size stays 12.)
3. Edit the same order again without changing anything → succeeds, values unchanged except total (may reprice within a few NT$).
4. `curl` a partial payload at `/edit/<id>` (valid session + CSRF token, body `{"weight": 5}`) → 400 listing the missing required fields, and the row is unchanged.
5. Ring order edited to a different ring size → new size stored, total recomputed for the new weight.
