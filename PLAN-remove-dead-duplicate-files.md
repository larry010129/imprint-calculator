# PLAN: Remove dead duplicates + deploy product images to live static path

## Rank: 3 of 5

## Status (as of 2026-07-08)

**Already done:**

- Root-level dead prototype files removed in commit `a1cb400`: no `index.html`, `script.js`, `style.css`, or `images/` at project root (only `templates/` and `static/` copies remain).
- Chain product images already deployed: `static/images/chain-A.jpg`, `chain-B.jpg`, `chain-C.jpg`.

**Still open:**

- Source photos sit in `image/` (Chinese folder names) but the app loads from `static/images/{category}-{type}.jpg` (see `static/js/script.js` `imageUrl()` line 108–110 and `app.py` `style_image_url` filter line 102).
- `static/images/README.md` documents the **old** 12-slot naming (`0.1-A.jpg` … `1-C.jpg`) — wrong for the current 5-category app.
- Only 3 of ~15 needed style images exist in `static/images/`. Calculator shows gray placeholders for pendant, ring, earring, bracelet.

## Goal

1. Confirm no new dead duplicate frontend files have reappeared at the project root.
2. Copy/rename source photos from `image/` into `static/images/` using the **live** naming convention so the calculator and admin style preview show real product photos.
3. Update `static/images/README.md` to match the current app (prevent future misplacement).
4. Optionally remove or `.gitignore` the source `image/` folder after successful copy (avoid two copies drifting apart).

## Files to touch

**Verify (read-only grep, no edits unless hits found):**

- `app.py`, `templates/`

**Copy/create (images):**

- `static/images/pendant-A.jpg`, `pendant-B.jpg`, `pendant-C.jpg`
- `static/images/ring-A.jpg`, `ring-B.jpg`, `ring-C.jpg`
- `static/images/earring-A.jpg`
- `static/images/bracelet-A.jpg`, `bracelet-B.jpg`, `bracelet-C.jpg`
- (`chain-A/B/C.jpg` already exist — do not overwrite unless replacing with higher-res source)

**Edit:**

- `static/images/README.md`
- Optionally `.gitignore` (add `image/` source folder)

**Source mapping (from `image/` folder on disk):**

| Source file | Destination |
|---|---|
| `image/墜子/項墜A.jpg` | `static/images/pendant-A.jpg` |
| `image/墜子/項墜B.jpg` | `static/images/pendant-B.jpg` |
| `image/墜子/項墜C.jpg` | `static/images/pendant-C.jpg` |
| `image/戒指/戒指A.jpg` | `static/images/ring-A.jpg` |
| `image/戒指/戒指B.jpg` | `static/images/ring-B.jpg` |
| `image/戒指/戒指C.jpg` | `static/images/ring-C.jpg` |
| `image/耳飾/耳飾A.jpg` | `static/images/earring-A.jpg` |
| `image/手鍊/手鍊A.jpg` | `static/images/bracelet-A.jpg` |
| `image/手鍊/手鍊B.jpg` | `static/images/bracelet-B.jpg` |
| `image/手鍊/手鍊C.jpg` | `static/images/bracelet-C.jpg` |
| `image/鍊條/斗圓鍊.jpg` | already represented by `chain-A.jpg` (K白) — compare visually before overwriting |
| `image/鍊條/斗圓鍊K玫瑰_0.jpg` | already `chain-B.jpg` |
| `image/鍊條/斗圓鍊K黃_0.jpg` | already `chain-C.jpg` |

## Step-by-step

### Step 1 — Confirm root duplicates are still gone

From project root:

```powershell
cd "c:\Users\user\Documents\second brain\Efforts\diamond-calculator"
Get-ChildItem -Name index.html, script.js, style.css -ErrorAction SilentlyContinue
```

All three should return nothing. If any exist, STOP — something reintroduced dead files; investigate before deleting.

Run reference grep:

```powershell
rg "index\.html|style\.css|script\.js|images/" app.py templates/
```

Expected: only `static/css/style.css`, `static/js/script.js`, `static/js/i18n.js`, and `static/images/...` references via `url_for('static', ...)` or `/static/images/...`. No bare root-level paths.

### Step 2 — Copy source photos to live paths

Use PowerShell copy (preserves originals in `image/` until Step 5):

```powershell
cd "c:\Users\user\Documents\second brain\Efforts\diamond-calculator"
Copy-Item "image/墜子/項墜A.jpg" "static/images/pendant-A.jpg"
Copy-Item "image/墜子/項墜B.jpg" "static/images/pendant-B.jpg"
Copy-Item "image/墜子/項墜C.jpg" "static/images/pendant-C.jpg"
Copy-Item "image/戒指/戒指A.jpg" "static/images/ring-A.jpg"
Copy-Item "image/戒指/戒指B.jpg" "static/images/ring-B.jpg"
Copy-Item "image/戒指/戒指C.jpg" "static/images/ring-C.jpg"
Copy-Item "image/耳飾/耳飾A.jpg" "static/images/earring-A.jpg"
Copy-Item "image/手鍊/手鍊A.jpg" "static/images/bracelet-A.jpg"
Copy-Item "image/手鍊/手鍊B.jpg" "static/images/bracelet-B.jpg"
Copy-Item "image/手鍊/手鍊C.jpg" "static/images/bracelet-C.jpg"
```

**Edge case:** PowerShell may fail on Unicode paths if encoding is wrong. If copy fails, use File Explorer manually with the mapping table above. Filenames in `static/images/` must be ASCII (`pendant-A.jpg`) — the app builds URLs as `` `/static/images/${category}-${type}.jpg` ``.

**Edge case:** Chain images already exist. Open `chain-A.jpg` vs `image/鍊條/斗圓鍊.jpg` side by side. Only overwrite if the source is clearly better; otherwise skip chain copies.

### Step 3 — Replace `static/images/README.md`

Delete the old 12-slot carat-based doc. Replace entire file with:

```markdown
# Product style images

Drop photos here using `{category}-{style}.jpg`. The calculator loads them automatically — no code changes needed.

## Required filenames (15 slots)

| Category | Files |
|---|---|
| pendant | `pendant-A.jpg`, `pendant-B.jpg`, `pendant-C.jpg` |
| ring | `ring-A.jpg`, `ring-B.jpg`, `ring-C.jpg` |
| earring | `earring-A.jpg` (style B/C not offered) |
| bracelet | `bracelet-A.jpg`, `bracelet-B.jpg`, `bracelet-C.jpg` |
| chain | `chain-A.jpg` (K白), `chain-B.jpg` (K玫瑰), `chain-C.jpg` (K黃) |

Style letters map to product names in `app.py` `STYLE_LABELS` and `static/js/i18n.js`.

Until a file exists, the calculator shows a gray placeholder labeled with the expected filename (e.g. `pendant-A`).

## Do not use

- Root-level `image/` folder — source/archive only; not served by Flask
- Old carat-based names like `0.1-A.jpg` — obsolete after 5-category expansion
```

### Step 4 — Manual browser verification

```powershell
set FLASK_DEBUG=1
python app.py
```

Log in. For each category (pendant, ring, earring, bracelet, chain):

1. Select category → style step shows real photos (not gray placeholders)
2. Network tab: image requests go to `/static/images/{category}-{type}.jpg` with HTTP 200
3. Admin `/admin`: hover style name — preview tooltip shows same image (uses `style_image_url` filter)

**Edge case:** Earring category only has style A in `CATEGORY_STYLES` (`script.js` line 8). Only `earring-A.jpg` is required — do not create B/C files unless product line expands.

### Step 5 — Optional: stop maintaining two image folders

After Step 4 passes, pick one:

**Option A (keep source archive):** Add to `.gitignore`:

```
image/
```

Commit `static/images/*.jpg` and updated README. Keep `image/` locally as source backup but out of git.

**Option B (single folder):** Delete `image/` after confirming copies in `static/images/` are correct:

```powershell
Remove-Item -Recurse -Force image/
```

Only do Option B if you are sure `static/images/` has everything.

### Step 6 — Commit

```powershell
git add static/images/
git add static/images/README.md
# git add .gitignore  # if Option A
git commit -m "assets: deploy product style images and update static/images README"
```

## Edge cases found while exploring (do not skip these)

- **Do not confuse `image/` (source, not served) with `static/images/` (live).** Flask only serves files under `static/`. Photos in `image/` never appear in the browser no matter what you name them.
- **`style_image_url` in `app.py` and `imageUrl()` in `script.js` must stay in sync** — both use `{category}-{style}.jpg`. If you rename one side, rename both or previews break.
- **Chain color is encoded in style type, not a separate image per color.** Style A = K白, B = K玫瑰, C = K黃 (`CHAIN_TYPE_COLORS` in `script.js` line 106). Three chain images cover all metal/color combos.
- **Bracelet carat is always 0.1ct** — images are per style (A/B/C), not per carat. Same for all non-chain categories: one image per style, shared across carat sizes.
- **Large JPGs slow page load.** If any source file is >500 KB, consider resizing before commit (optional, out of scope unless Larry asks).

## Acceptance criteria

1. No `index.html`, `script.js`, `style.css` at project root.
2. `static/images/` contains at minimum: all pendant, ring, earring, bracelet files from mapping table + existing chain files (15 files total when complete).
3. Calculator style step shows real photos for every category (no gray `IMG` fallback boxes for deployed styles).
4. `static/images/README.md` documents `{category}-{style}.jpg` convention — no `0.1-A.jpg` references remain.
5. `rg "0\.1-A\.jpg" static/images/README.md` returns nothing.
6. Admin style hover preview works for at least one submission per category (create test orders if needed).
7. `git log -1 --stat` shows image files committed under `static/images/` only, not duplicate paths under root `image/` (unless you explicitly chose to commit sources).
