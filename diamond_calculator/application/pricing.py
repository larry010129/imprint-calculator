from diamond_calculator.application.bot_metal_feed import (
    FALLBACK_TWD_PER_GRAM,
    get_cached_metal_prices,
    get_price_metadata,
)

# Full diamond list-price table (TWD, tax-inclusive / 牌價). Shop UI uses
# SHOP_DIAMOND_CARATS only; other keys support bracelets, admin, or future SKUs.
DIAMOND_PRICE = {
    '0.1': 24000,
    '0.2': 48000,
    '0.3': 79000,
    '0.5': 98000,
    '0.6': 113000,
    '0.7': 133000,
    '0.8': 159000,
    '0.9': 200000,
    '1.0': 250000,
    '1': 250000,
    '1.5': 380000,
    '2.0': 700000,
    '2': 700000,
    '3.0': 990000,
    '3': 990000,
}

SHOP_DIAMOND_CARATS = frozenset({'0.1', '0.3', '0.5', '1.0'})

PURITY_MULTIPLIER = {
    "9k":    0.50,
    "14k":   0.75,
    "18k":   0.85,
    "pt950": 1.10,
    "s925":  0.925,
    "999":   0.999, "pt": 1.0, "silver925": 0.925,
}
METAL_SYMBOL = {
    "9k": "XAU", "14k": "XAU", "18k": "XAU",
    "pt950": "XPT", "s925": "XAG",
    "999": "XAU", "pt": "XPT", "silver925": "XAG",
}
LABOR_FEE = {
    'pendant': 5000, 'ring': 5000, 'bracelet': 5000,
    'earring': 5000, 'chain': 5000,
}

# 5% sales tax, applied on top of the pre-tax total at display time.
TAX_RATE = 0.05

CHIN_TO_GRAMS = 3.75
CHAIN_REFERENCE_LENGTH_CM = 45
BRACELET_REFERENCE_LENGTH_CM = 18


def get_metal_prices():
    """TWD per gram for XAU/XPT/XAG from BOT cache. Never raises."""
    return get_cached_metal_prices()


def get_product_variant(category, style_type, gold, carat, *, require_published=True):
    """Looks up the ProductVariant for a listing + config.

    style_type is the Product.id (as sent by the shop frontend). Raises
    KeyError if the product/category/variant combo doesn't exist.
    """
    from diamond_calculator.repository.models import Product, ProductVariant

    try:
        product_id = int(style_type)
    except (TypeError, ValueError):
        raise KeyError('invalid product id')

    query = (
        ProductVariant.query
        .join(Product, ProductVariant.product_id == Product.id)
        .filter(Product.id == product_id, Product.category == category,
                ProductVariant.gold == gold, ProductVariant.carat == carat)
    )
    if require_published:
        query = query.filter(Product.is_published.is_(True))
    variant = query.first()
    if variant is None:
        raise KeyError('no matching product variant')
    return variant


def lookup_weight(category, style_type, gold, carat, length_cm=None, *, require_published=True):
    """Returns weight in chin for a product's variant. Raises KeyError if not found."""
    weight = get_product_variant(
        category, style_type, gold, carat, require_published=require_published,
    ).weight_chin
    if category == 'chain' and length_cm is not None:
        weight *= float(length_cm) / CHAIN_REFERENCE_LENGTH_CM
    elif category == 'bracelet' and length_cm is not None:
        weight *= float(length_cm) / BRACELET_REFERENCE_LENGTH_CM
    return weight


def compute_chain_addon(chain_product_id, chain_gold, chain_length_cm, *, require_published=True):
    """Pre-tax chain total (metal×2 + labor) for pendant add-ons. Raises KeyError."""
    chain_variant = get_product_variant(
        'chain', chain_product_id, chain_gold, '3fen',
        require_published=require_published,
    )
    chain_chin = lookup_weight(
        'chain', chain_product_id, chain_gold, '3fen', chain_length_cm,
        require_published=require_published,
    )
    chain_pre_tax, _, _ = compute_total(
        '3fen',
        chain_gold,
        chain_chin * CHIN_TO_GRAMS,
        'chain',
        manual_price_twd=chain_variant.manual_price_twd,
    )
    return chain_pre_tax, chain_chin, chain_variant


def compute_total(
    carat,
    gold,
    weight_grams,
    category='ring',
    ring_size=None,
    manual_price_twd=None,
    *,
    diamond_kind='white',
    fancy_color=None,
    stone_count=None,
    diamond_shape='round',
):
    """Returns (total, per_gram_alloy, source). Total is pre-tax.

    If manual_price_twd is set (a seller-set override on the matched
    variant), it is returned directly instead of the formula below — the
    live gold rate is still fetched so the receipt/audit trail still shows
    what the market rate was at order time.
    """
    from diamond_calculator.application.diamond_options import compute_diamond_list_price

    raw, source = get_metal_prices()
    per_gram = raw[METAL_SYMBOL[gold]] * PURITY_MULTIPLIER[gold]

    if manual_price_twd is not None:
        return manual_price_twd, per_gram, 'manual_override'

    metal_cost = per_gram * weight_grams
    labor = LABOR_FEE.get(category, 5000)

    if category == 'chain':
        total = metal_cost * 2 + labor
    else:
        diamond_cost = compute_diamond_list_price(
            carat,
            diamond_kind=diamond_kind,
            fancy_color=fancy_color,
            stone_count=stone_count,
            diamond_shape=diamond_shape,
            category=category,
        ) or 0
        total = diamond_cost + metal_cost + labor

    return total, per_gram, source
