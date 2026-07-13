from datetime import timedelta, datetime, timezone

from flask import url_for

from diamond_calculator.application.order_search import submission_search_blob

CATEGORY_LABELS = {
    'pendant': '項墜', 'ring': '戒指', 'earring': '耳飾',
    'bracelet': '手鍊', 'chain': '鍊條',
    'necklace': '項鍊 (舊)',
}

STYLE_IMAGE_CATEGORIES = frozenset({'pendant', 'ring', 'earring', 'bracelet', 'chain'})

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

GOLD_COLOR_METALS = frozenset({'9k', '14k', '18k'})
VALID_ASSET_COLORS = frozenset({'white', 'yellow', 'rose'})


def asset_color_key(gold, color, category=None, style_type=None):
    """Match static/js/script.js assetColorKey.

    category/style_type are accepted for call-site compatibility (product
    image lookups pass them through) but no longer affect the result — a
    listing's color is now an explicit Product field (default_color) rather
    than implied by a hardcoded chain style-to-color mapping.
    """
    if gold in ('9k', 'pt950', 's925'):
        return 'white'
    if color in VALID_ASSET_COLORS:
        return color
    return 'white'


def submission_summary(category, style_type, order_id=None, product=None):
    """Human-readable summary for a submission.

    `product` is the linked admin-managed Product row (Submission.product);
    style_type stores a numeric product id for submissions created after the
    catalog migration, so `product` is the only way to resolve a name for
    those. Submissions predating the migration (no linked product) fall back
    to a generic "款式A/B/C" label since the old per-style names no longer
    live in code (they're baked into the seeded Product rows instead).
    """
    if not category or not style_type:
        return ''
    cat = CATEGORY_LABELS.get(category, category)
    if product is not None:
        style = product.name_zh
    else:
        style = {'A': '款式A', 'B': '款式B', 'C': '款式C'}.get(str(style_type).upper(), style_type)
    prefix = f'訂單 #{order_id} · ' if order_id else ''
    return f'{prefix}{cat} · {style}'


def resolve_style_image_urls(category, style_type, gold=None, color=None, product=None):
    if product is not None:
        images = product.images_by_color()
        if not images:
            return []
        color_key = asset_color_key(gold, color, category, style_type)
        paths = images.get(color_key) or images.get(product.default_color)
        if paths:
            return list(paths)
        for paths in images.values():
            if paths:
                return list(paths)
        return []
    if not category or not style_type:
        return []
    cat = category.lower()
    style = str(style_type).upper()
    if cat not in STYLE_IMAGE_CATEGORIES or style not in ('A', 'B', 'C'):
        return []
    color_key = asset_color_key(gold, color, cat, style)
    return [f'images/{color_key}/{cat}-{style}.png']


def resolve_style_image_url(category, style_type, gold=None, color=None, product=None):
    paths = resolve_style_image_urls(category, style_type, gold, color, product)
    return paths[0] if paths else ''


def diamond_color_label(diamond_kind='white', fancy_color=None, category=None):
    if category == 'chain':
        return '-'
    if diamond_kind == 'fancy' and fancy_color:
        return DIAMOND_COLOR_LABELS.get(fancy_color, fancy_color)
    return DIAMOND_COLOR_LABELS.get('white', '白鑽')


def register_filters(app):
    @app.template_filter('tz_taiwan')
    def tz_taiwan(dt):
        if not dt:
            return ''
        return (dt + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')

    @app.template_filter('notify_time')
    def notify_time(dt):
        if not dt:
            return ''
        local = dt + timedelta(hours=8)
        now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=8)
        if local.date() == now.date() or local.date() == (now - timedelta(days=1)).date():
            return local.strftime('%H:%M')
        return local.strftime('%Y-%m-%d %H:%M')

    @app.template_filter('label_category')
    def label_category(cat):
        if not cat:
            return ''
        return CATEGORY_LABELS.get(cat, cat)

    @app.template_filter('label_style')
    def label_style(style, category=None, product=None):
        if product is not None:
            return product.name_zh
        if not style:
            return ''
        return {'A': '款式A', 'B': '款式B', 'C': '款式C'}.get(style, style)

    @app.template_filter('style_image_url')
    def style_image_url(category, style_type, gold=None, color=None, product=None):
        path = resolve_style_image_url(category, style_type, gold, color, product)
        return url_for('static', filename=path) if path else ''

    @app.template_filter('style_images')
    def style_images(category, style_type, gold=None, color=None, product=None):
        paths = resolve_style_image_urls(category, style_type, gold, color, product)
        return [url_for('static', filename=p) for p in paths]

    @app.template_filter('label_purity')
    def label_purity(purity):
        if not purity:
            return ''
        return PURITY_LABELS.get(purity, purity)

    @app.template_filter('label_color')
    def label_color(color):
        if not color:
            return ''
        return COLOR_LABELS.get(color, color)

    @app.template_filter('label_diamond_color')
    def label_diamond_color(sub):
        return diamond_color_label(
            diamond_kind=getattr(sub, 'diamond_kind', None) or 'white',
            fancy_color=getattr(sub, 'fancy_color', None),
            category=getattr(sub, 'category', None),
        )

    @app.template_filter('search_blob')
    def search_blob(sub, include_store=False):
        return submission_search_blob(sub, include_store=include_store)
