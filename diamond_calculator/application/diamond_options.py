"""Backbone data and pricing for diamond colors, multi-stone bundles, and cut shapes."""

from diamond_calculator.application.pricing import DIAMOND_PRICE

VALID_DIAMOND_KINDS = frozenset({'white', 'fancy'})
VALID_FANCY_COLORS = frozenset({'yellow', 'pink', 'blue'})
VALID_DIAMOND_SHAPES = frozenset({'round'})
VALID_STONE_COUNTS = frozenset({2, 3, 4})

# Minimum shop carat for fancy (colored) diamonds and non-round cuts.
FANCY_MIN_CARAT = '0.3'
NON_ROUND_SHAPE_MIN_CARAT = '0.3'
NON_ROUND_SHAPE_SURCHARGE = 0.10

# ── Image 2: colored single-stone list prices (TWD) ─────────────────────────
COLORED_SINGLE_DIAMOND_PRICE = {
    '0.3': 102000,
    '0.5': 127000,
    '0.6': 147000,
    '0.7': 172000,
    '0.8': 206000,
    '0.9': 260000,
    '1.0': 325000,
    '1': 325000,
    '1.5': 494000,
    '2.0': 910000,
    '2': 910000,
    '3.0': 1287000,
    '3': 1287000,
}

# ── Image 3: white multi-stone bundle prices (earring / bracelet) ───────────
WHITE_MULTI_DIAMOND_PRICE = {
    '0.1': {2: 45600, 3: 61200, 4: 81000},
    '0.2': {2: 86400, 3: 122400, 4: 162000},
    '0.3': {2: 142200, 3: 189600, 4: 250000},
}

# ── Image 4: colored multi-stone bundle prices ──────────────────────────────
COLORED_MULTI_DIAMOND_PRICE = {
    '0.3': {2: 173400, 3: 244800, 4: 322300},
}

# For carats above 0.30ct, apply these multipliers to the 0.30ct bundle row.
MULTI_STONE_ABOVE_03_MULTIPLIER = {2: 0.85, 3: 0.80, 4: 0.75}

# Backward-compatible aliases used in API payloads / tests.
COLORED_DIAMOND_PRICE = COLORED_MULTI_DIAMOND_PRICE
COLORED_DIAMOND_ABOVE_03_MULTIPLIER = MULTI_STONE_ABOVE_03_MULTIPLIER

DIAMOND_SHAPE_SURCHARGE = {
    shape: NON_ROUND_SHAPE_SURCHARGE
    for shape in VALID_DIAMOND_SHAPES
    if shape != 'round'
}

DEFAULT_STONE_COUNT_BY_CATEGORY = {
    'earring': 2,
    'ring': 2,
    'pendant': 2,
}

STONE_COUNT_CATEGORIES = frozenset({'earring'})

# Unified shop picker: white + fancy colors (replaces separate "diamond type" step).
DIAMOND_COLOR_META = [
    {'id': 'white', 'kind': 'white', 'labelZh': '白鑽', 'labelEn': 'White',
     'swatch': '#e8e8e8', 'image': 'diamonds/shapes/round.svg'},
    {'id': 'yellow', 'kind': 'fancy', 'labelZh': '黃鑽', 'labelEn': 'Yellow', 'swatch': '#e6c200',
     'image': 'diamonds/fancy/yellow.svg'},
    {'id': 'pink', 'kind': 'fancy', 'labelZh': '粉鑽', 'labelEn': 'Pink', 'swatch': '#f4a6c8',
     'image': 'diamonds/fancy/pink.svg'},
    {'id': 'blue', 'kind': 'fancy', 'labelZh': '藍鑽', 'labelEn': 'Blue', 'swatch': '#7ec8e3',
     'image': 'diamonds/fancy/blue.svg'},
]

FANCY_COLOR_META = [c for c in DIAMOND_COLOR_META if c['kind'] == 'fancy']

DIAMOND_KIND_META = [
    {'id': 'white', 'labelZh': '白鑽', 'labelEn': 'White'},
    {'id': 'fancy', 'labelZh': '彩鑽', 'labelEn': 'Fancy Color'},
]

DIAMOND_SHAPE_META = [
    {'id': 'round', 'labelZh': '圓鑽', 'labelEn': 'Round', 'image': 'diamonds/shapes/round.svg'},
]



def _carat_float(carat):
    try:
        return float(str(carat).replace('fen', ''))
    except (TypeError, ValueError):
        return None


def is_fancy_carat_allowed(carat):
    value = _carat_float(carat)
    return value is not None and value >= float(FANCY_MIN_CARAT)


def is_shape_carat_allowed(carat, diamond_shape='round'):
    shape = diamond_shape or 'round'
    if shape == 'round':
        return True
    return is_fancy_carat_allowed(carat)


def shape_surcharge_rate(diamond_shape='round'):
    shape = diamond_shape or 'round'
    if shape == 'round':
        return 0
    return NON_ROUND_SHAPE_SURCHARGE


def _multi_stone_tier(carat, *, table):
    if carat in table:
        return carat
    value = _carat_float(carat)
    if value is not None and value > float(FANCY_MIN_CARAT):
        return '0.3_plus'
    return None


def _resolve_multi_price(table, tier, stone_count):
    if tier == '0.3_plus':
        row = table.get('0.3', {})
        multiplier = MULTI_STONE_ABOVE_03_MULTIPLIER.get(stone_count)
        base_row = row.get(stone_count)
        return round(base_row * multiplier) if base_row is not None and multiplier else None
    return table.get(tier, {}).get(stone_count)


def compute_diamond_list_price(
    carat,
    *,
    diamond_kind='white',
    fancy_color=None,
    stone_count=None,
    diamond_shape='round',
    category=None,
):
    """Return diamond list price in TWD, or None if the combination is invalid."""
    if not carat or category == 'chain':
        return None

    diamond_kind = diamond_kind or 'white'
    diamond_shape = diamond_shape or 'round'
    multi_stone = category in STONE_COUNT_CATEGORIES

    if not is_shape_carat_allowed(carat, diamond_shape):
        return None

    if diamond_kind == 'white':
        if multi_stone:
            if stone_count not in VALID_STONE_COUNTS:
                stone_count = DEFAULT_STONE_COUNT_BY_CATEGORY.get(category, 2)
            tier = _multi_stone_tier(carat, table=WHITE_MULTI_DIAMOND_PRICE)
            if tier is None:
                return None
            base = _resolve_multi_price(WHITE_MULTI_DIAMOND_PRICE, tier, stone_count)
        else:
            base = DIAMOND_PRICE.get(carat)
    elif diamond_kind == 'fancy':
        if fancy_color not in VALID_FANCY_COLORS:
            return None
        if not is_fancy_carat_allowed(carat):
            return None
        if multi_stone:
            if stone_count not in VALID_STONE_COUNTS:
                stone_count = DEFAULT_STONE_COUNT_BY_CATEGORY.get(category, 2)
            tier = _multi_stone_tier(carat, table=COLORED_MULTI_DIAMOND_PRICE)
            if tier is None:
                return None
            base = _resolve_multi_price(COLORED_MULTI_DIAMOND_PRICE, tier, stone_count)
        else:
            base = COLORED_SINGLE_DIAMOND_PRICE.get(carat)
            if base is None and carat == '1.0':
                base = COLORED_SINGLE_DIAMOND_PRICE.get('1')
    else:
        return None

    if base is None:
        return None

    surcharge = shape_surcharge_rate(diamond_shape)
    if surcharge:
        base = round(base * (1 + surcharge))
    return base


def diamond_options_payload():
    """Metadata exposed to the shop frontend via /api/prices."""
    return {
        'kinds': DIAMOND_KIND_META,
        'diamondColors': DIAMOND_COLOR_META,
        'fancyColors': FANCY_COLOR_META,
        'shapes': DIAMOND_SHAPE_META,
        'stoneCounts': sorted(VALID_STONE_COUNTS),
        'defaultStoneCountByCategory': DEFAULT_STONE_COUNT_BY_CATEGORY,
        'stoneCountCategories': sorted(STONE_COUNT_CATEGORIES),
        'fancyMinCarat': FANCY_MIN_CARAT,
        'nonRoundShapeMinCarat': NON_ROUND_SHAPE_MIN_CARAT,
        'nonRoundShapeSurcharge': NON_ROUND_SHAPE_SURCHARGE,
        'coloredDiamondPrice': COLORED_MULTI_DIAMOND_PRICE,
        'coloredSingleDiamondPrice': COLORED_SINGLE_DIAMOND_PRICE,
        'whiteMultiDiamondPrice': WHITE_MULTI_DIAMOND_PRICE,
        'coloredAbove03Multiplier': MULTI_STONE_ABOVE_03_MULTIPLIER,
        'shapeSurcharge': DIAMOND_SHAPE_SURCHARGE,
    }
