# PLAN: Remove dead duplicate prototype files at the project root

## Rank: 2 of 5

## Goal

The project root contains a second, stale, disconnected copy of the frontend that predates the Flask app: `index.html`, `script.js`, `style.css`, and `images/` at `Efforts/diamond-calculator/` (top level, siblings of `app.py`). The **live** app is served entirely from `templates/` (Jinja HTML) and `static/` (`static/css/style.css`, `static/js/script.js`, `static/js/i18n.js`, `static/images/`).

These root files are not referenced anywhere by `app.py` or any file under `templates/` — confirmed by grepping for `index.html`, `style.css`, `script.js`, and `images/` across `app.py` and `templates/`: zero hits. They are pure dead weight, but they are dangerous dead weight: they are a near-identical, older snapshot of the real app (the root `script.js` is 328 lines vs. the live `static/js/script.js` at 416 lines — it's missing i18n support, editing, and other features that were added later). Anyone — you, or a future AI coding session — who opens this project, sees `script.js` sitting right next to `app.py` at the root, and edits it, will make changes that silently do nothing, because the running app never loads that file.

This has already happened once in a way: this repository had 10 stale `PLAN-*.md` files sitting in this same root before this session removed them. The root-level duplicate frontend files are the same category of problem — leftover artifacts nobody is using but that look live.

## Files to touch (delete)

- `Efforts/diamond-calculator/index.html`
- `Efforts/diamond-calculator/script.js`
- `Efforts/diamond-calculator/style.css`
- `Efforts/diamond-calculator/images/` (entire directory, including `images/README.md`)

## Files to NOT touch (these are the real, live ones — verify you are not deleting these)

- `Efforts/diamond-calculator/templates/index.html`
- `Efforts/diamond-calculator/static/js/script.js`
- `Efforts/diamond-calculator/static/js/i18n.js`
- `Efforts/diamond-calculator/static/css/style.css`
- `Efforts/diamond-calculator/static/images/` (and its `README.md`)

## Step-by-step

### Step 1 — Confirm this plan's premise before deleting anything

This is the single most important step. Do not skip it. Run, from `Efforts/diamond-calculator/`:

```bash
grep -rn "index\.html\|style\.css\|script\.js\|images/" app.py templates/
```

You should see references **only** to `static/css/style.css`, `static/js/script.js`, `static/js/i18n.js`, and `static/images/...` (all with the `static/` prefix, and always via `{{ url_for('static', filename=...) }}` in the templates, or as literal `/static/images/...` paths inside `static/js/script.js`). If you see any reference to a bare `index.html`, `style.css`, `script.js`, or `images/` **without** a `static/` or `templates/` prefix, STOP and re-investigate before deleting — it means something changed since this plan was written and the premise no longer holds.

### Step 2 — Diff the two style.css files for anything worth preserving

Before deleting, confirm there is nothing in the root `style.css` that isn't already in the live one:

```bash
diff style.css static/css/style.css
```

This will show differences (the files are not identical — the root one is an older version). Skim the diff. If you see any CSS rule for a UI element that still exists in `templates/*.html` but does NOT appear in `static/css/style.css`, that's a real regression risk — note it and port that one rule into `static/css/style.css` before deleting. In the exploration for this plan, no such gap was found (the live `static/css/style.css` is a strict superset — it's just larger and more developed), but re-verify at execution time since the files may have changed.

### Step 3 — Confirm the app runs correctly using only the `static/`/`templates/` copies

Start the app (`set FLASK_DEBUG=1` then `python app.py` on Windows), log in, and click through the full calculator flow (category → carat → style → gold → weight → confirm) in a browser. Confirm images load from `/static/images/...` (they'll show the gray placeholder boxes if no real photos have been dropped in yet — that's expected and correct, not a bug caused by this plan). This proves the app has zero dependency on the root files even while they still exist, which de-risks the deletion.

### Step 4 — Delete the dead files

```bash
git rm -r index.html script.js style.css images/
```

(Use `git rm` rather than plain `rm` so the deletion is staged and recorded in history — this assumes `PLAN-eliminate-hardcoded-secrets.md` has already been executed and this is a git repo. If it is not yet a git repo, run `rm -r index.html script.js style.css images/` instead, but strongly prefer doing the git-init plan first so this deletion is reversible.)

### Step 5 — Re-verify the app still runs

Repeat Step 3's manual click-through. Nothing should have changed in behavior — this is a pure no-op from the running app's perspective.

### Step 6 — Commit

```bash
git commit -m "Remove dead root-level duplicate frontend (superseded by templates/ and static/)"
```

## Edge cases found while exploring that a weaker model would miss

- **Do not confuse `images/README.md` (root) with `static/images/README.md` (live).** Both exist and both describe the same 12-filename-slot convention (`0.1-A.jpg` through `1-C.jpg`). They are near-identical text. It is easy to delete the wrong one by pattern-matching on filename alone — always check the full path, and only delete the one at the repository root (`Efforts/diamond-calculator/images/README.md`), never `Efforts/diamond-calculator/static/images/README.md`.
- **Both `images/` directories are currently empty of actual photos** (only `README.md` in each, no `.jpg` files) — so there is no product photography to lose or accidentally leave orphaned in the deleted directory. If, by the time you execute this plan, someone has since dropped real `.jpg` files into the root `images/` folder (as opposed to `static/images/`), that would mean product photos were added to the *dead* folder by mistake — copy any `.jpg` files found in root `images/` into `static/images/` (matching filenames) before deleting the root folder, so real photography isn't lost.
- **The root `script.js` is not merely outdated, it is a different implementation** (328 vs. 416 lines) — it does not have `window.editData` handling, does not have the `tr()` i18n wrapper, and would produce a broken/half-translated UI if it were ever accidentally loaded instead of the real one. This is why "just leave it, it's harmless" is not a safe assumption — if `templates/index.html`'s `<script src="...">` line were ever accidentally edited to point at the wrong path, the failure mode is a silently broken calculator, not an obvious 404.

## Acceptance criteria

1. `Efforts/diamond-calculator/index.html`, `Efforts/diamond-calculator/script.js`, `Efforts/diamond-calculator/style.css`, and `Efforts/diamond-calculator/images/` no longer exist (`ls Efforts/diamond-calculator/` shows only `app.py`, `models.py`, `test_validation.py`, `requirements.txt`, `README.md`, `templates/`, `static/`, `instance/`, `.claude/`, plus whatever files earlier plans added like `.gitignore`/`.env.example`).
2. `Efforts/diamond-calculator/templates/index.html`, `Efforts/diamond-calculator/static/css/style.css`, `Efforts/diamond-calculator/static/js/script.js`, `Efforts/diamond-calculator/static/js/i18n.js`, and `Efforts/diamond-calculator/static/images/README.md` all still exist, untouched.
3. The app starts without error and the full calculator flow (all 4 selection steps + submit) works end to end in a browser, with translated text visible when toggling the language switch — proving `static/js/i18n.js` and `static/js/script.js` are the ones actually running.
4. `git log` shows a commit removing these 4 paths (if git was initialized per the prerequisite plan).
