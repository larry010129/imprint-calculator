"""Order list search — server-side SQL filter + client-side search blob."""

from datetime import timedelta

from sqlalchemy import String, cast, or_

from diamond_calculator.repository.models import Product, Submission, User

CATEGORY_LABELS = {
    'pendant': '項墜', 'ring': '戒指', 'earring': '耳飾',
    'bracelet': '手鍊', 'chain': '鍊條',
    'necklace': '項鍊 (舊)',
}

PURITY_LABELS = {
    '9k': '9K金', '14k': '14K金', '18k': '18K金',
    'pt950': '鉑金 Pt950', 's925': '925銀',
    '999': '純金999', 'pt': '鉑金 Pt', 'silver925': '925銀',
}

COLOR_LABELS = {'white': 'K白', 'yellow': 'K黃', 'rose': 'K玫瑰'}

DIAMOND_COLOR_LABELS = {
    'white': '白鑽',
    'yellow': '黃鑽',
    'pink': '粉鑽',
    'blue': '藍鑽',
}

STATUS_LABELS_ZH = {
    'pending': '待處理',
    'confirmed': '訂單成立',
    'processing': '處理中',
    'completed': '已完成',
    'shipped': '已出貨',
    'cancelled': '已取消',
}

_STYLE_FALLBACK = {'A': '款式A', 'B': '款式B', 'C': '款式C'}


def _style_label(sub):
    if sub.product is not None:
        return sub.product.name_zh
    style = sub.style_type or ''
    return _STYLE_FALLBACK.get(str(style).upper(), style)


def _diamond_color_label(sub):
    if sub.category == 'chain':
        return '-'
    if sub.diamond_kind == 'fancy' and sub.fancy_color:
        return DIAMOND_COLOR_LABELS.get(sub.fancy_color, sub.fancy_color)
    return DIAMOND_COLOR_LABELS.get('white', '白鑽')


def submission_search_blob(sub, *, include_store=False):
    """Lowercase plain-text blob attached to table rows for client-side filter."""
    parts = [str(sub.id)]
    if sub.created_at:
        parts.append((sub.created_at + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M'))
    if include_store and sub.user:
        parts.append(sub.user.store_name or '')
        parts.append(sub.user.username or '')
    if sub.category:
        parts.append(CATEGORY_LABELS.get(sub.category, sub.category))
    parts.append(_style_label(sub))
    if sub.gold_purity:
        parts.append(PURITY_LABELS.get(sub.gold_purity, sub.gold_purity))
    if sub.color:
        parts.append(COLOR_LABELS.get(sub.color, sub.color))
    if sub.carat:
        parts.append(str(sub.carat))
    if sub.category != 'chain':
        parts.append(_diamond_color_label(sub))
    if sub.status:
        parts.append(sub.status)
        parts.append(STATUS_LABELS_ZH.get(sub.status, ''))
    if sub.ring_size is not None:
        parts.append(str(sub.ring_size))
    if sub.engraving_band:
        parts.append(sub.engraving_band)
    if sub.engraving_girdle:
        parts.append(sub.engraving_girdle)
    if sub.total_price is not None:
        parts.append(str(int(sub.total_price)))
    return ' '.join(p for p in parts if p).lower()


def apply_submission_search(query, q, *, admin=False):
    """Filter a Submission query by free-text search."""
    q = (q or '').strip()
    if not q:
        return query

    pattern = f'%{q}%'
    clauses = []

    if q.isdigit():
        clauses.append(Submission.id == int(q))

    clauses.extend([
        Submission.category.ilike(pattern),
        Submission.style_type.ilike(pattern),
        Submission.status.ilike(pattern),
        Submission.carat.ilike(pattern),
        Submission.color.ilike(pattern),
        Submission.gold_purity.ilike(pattern),
        Submission.diamond_kind.ilike(pattern),
        Submission.engraving_band.ilike(pattern),
        Submission.engraving_girdle.ilike(pattern),
        cast(Submission.ring_size, String).ilike(pattern),
        cast(Submission.total_price, String).ilike(pattern),
    ])

    for code, label in CATEGORY_LABELS.items():
        if q in label:
            clauses.append(Submission.category == code)

    for code, label in STATUS_LABELS_ZH.items():
        if q in label:
            clauses.append(Submission.status == code)

    for code, label in PURITY_LABELS.items():
        if q in label:
            clauses.append(Submission.gold_purity == code)

    for code, label in COLOR_LABELS.items():
        if q in label:
            clauses.append(Submission.color == code)

    query = query.outerjoin(Product, Submission.product_id == Product.id)
    clauses.append(Product.name_zh.ilike(pattern))

    if admin:
        query = query.outerjoin(User, Submission.user_id == User.id)
        clauses.append(User.store_name.ilike(pattern))
        clauses.append(User.username.ilike(pattern))

    return query.filter(or_(*clauses))


def submissions_by_status(query):
    """Return incomplete, completed, and cancelled order lists from a base query."""
    order = Submission.created_at.desc()
    incomplete = query.filter(
        ~Submission.status.in_(['completed', 'cancelled'])
    ).order_by(order).all()
    complete = query.filter(Submission.status.in_(['completed', 'shipped'])).order_by(order).all()
    cancelled = query.filter(Submission.status == 'cancelled').order_by(order).all()
    return incomplete, complete, cancelled
