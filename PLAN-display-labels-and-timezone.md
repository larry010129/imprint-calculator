# PLAN: Human-readable labels + Taiwan-local timestamps in history/admin tables

## Goal
Two user-facing data-display defects on `/history` and `/admin`:
1. **Raw internal codes in the tables.** The DB stores `category="ring"`, `gold_purity="18k"`, `style_type="A"` — and the tables print them verbatim. A store owner sees "ring / 18k / A" in an otherwise Traditional-Chinese UI instead of「戒指 / 18K金 / 款式 A」.
2. **Timestamps are 8 hours off.** `Submission.created_at` stores naive UTC (`datetime.utcnow`, `models.py` line 25) and the templates render it raw. A Taiwan user submitting at 14:00 sees 06:00. Also, `datetime.utcnow` is deprecated (this project runs Python 3.14 per `__pycache__`).

## Exact files to touch
- `app.py` — label dicts + two Jinja filters.
- `models.py` — replace deprecated `datetime.utcnow`.
- `templates/history.html` — use filters (3 cells + date cell).
- `templates/admin.html` — use filters (3 cells + date cell).

## Step-by-step implementation

### 1. Label dicts + filters in `app.py`
```python
from datetime import timezone, timedelta

# ponytail: fixed +8 offset instead of zoneinfo — Taiwan has no DST; avoids the
# tzdata dependency that zoneinfo needs on Windows.
TAIPEI_TZ = timezone(timedelta(hours=8))

CATEGORY_LABEL = {'ring': '戒指', 'necklace': '項鍊'}
GOLD_LABEL = {'18k': '18K金', '999': '純金999', 'pt': '鉑金 Pt', 'silver925': '925銀'}
TYPE_LABEL = {'A': '款式 A', 'B': '款式 B', 'C': '款式 C'}

@app.template_filter('label')
def label_filter(value, kind):
    table = {'category': CATEGORY_LABEL, 'gold': GOLD_LABEL, 'type': TYPE_LABEL}[kind]
    return table.get(value, value or '-')

@app.template_filter('taipei')
def taipei_filter(dt):
    if dt is None:
        return '-'
    return dt.replace(tzinfo=timezone.utc).astimezone(TAIPEI_TZ).strftime('%Y-%m-%d %H:%M')
```
These label values must match `goldLabel` / `types` in `static/js/script.js` (lines 10–17) — copy them exactly.

### 2. `models.py` — fix deprecated utcnow, keep storage semantics identical
```python
from datetime import datetime, timezone
...
created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
```
This still stores **naive UTC**, byte-for-byte compatible with every existing row — only the deprecated call goes away.

### 3. Templates
In BOTH `templates/history.html` and `templates/admin.html`:
- Date cell: `{{ sub.created_at.strftime('%Y-%m-%d %H:%M') }}` → `{{ sub.created_at|taipei }}`
- `{{ sub.category }}` → `{{ sub.category|label('category') }}`
- `{{ sub.style_type }}` → `{{ sub.style_type|label('type') }}`
- `{{ sub.gold_purity }}` → `{{ sub.gold_purity|label('gold') }}`

(history.html rows ~26–30; admin.html rows ~26–31. Do NOT touch the `data-*` attributes on the edit button in history.html line 53 — the edit modal needs the raw codes, only the visible `<td>` text changes.)

## Edge cases a weaker model would miss
- **Do NOT use `zoneinfo.ZoneInfo("Asia/Taipei")` here.** On Windows (this machine), Python's zoneinfo has no system tz database and raises `ZoneInfoNotFoundError` unless the `tzdata` pip package is installed. A fixed `timezone(timedelta(hours=8))` is permanently correct for Taiwan (no DST since 1979) and needs no dependency.
- **Do NOT change what's stored in the DB.** Switching storage to local time or aware datetimes would make old rows (naive UTC) and new rows inconsistent, silently skewing old timestamps by 8 hours when the filter converts them. Keep storing naive UTC; convert only at render.
- **`.replace(tzinfo=utc)` vs `.astimezone()` order matters**: the stored datetimes are naive, so calling `.astimezone(TAIPEI_TZ)` directly would interpret them as *local machine time*, producing wrong output on any machine not set to UTC. Attach UTC first, then convert (as in the filter above).
- **The raw codes are load-bearing elsewhere**: the edit modal (`data-carat`, `data-gold`, `data-type` attributes) and the status `<select>` values must keep raw values. Only the display text cells change.
- **`created_at` can theoretically be NULL** on legacy/hand-inserted rows — the filter returns `-` instead of crashing on `None.strftime`.
- **i18n limitation (accepted)**: these labels are server-rendered Chinese; the EN toggle (i18n.js) translates only `data-i18n` chrome, not data cells. That's the existing behavior for status options too. Do not build a server-side i18n system for this — out of scope; note it and move on.

## Acceptance criteria
1. Submit a new order, note the wall-clock time in Taiwan (UTC+8): `/history` shows that local time, not 8 hours earlier. Pre-existing rows also shift +8h consistently.
2. `/history` and `/admin` show 戒指/項鍊, 款式 A/B/C, and 18K金/純金999/鉑金 Pt/925銀 instead of ring/necklace, A/B/C, 18k/999/pt/silver925.
3. Editing a pending order still pre-fills the modal correctly and saves (raw data-attributes untouched).
4. Admin status dropdown still works (values untouched).
5. `python -W error::DeprecationWarning -c "import models"` raises no utcnow deprecation warning.
6. App still boots and renders with no new packages installed (`pip freeze` unchanged).
