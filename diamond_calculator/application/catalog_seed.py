"""Shared logic to seed Product/ProductVariant/ProductImage rows from the
legacy hardcoded style tables. Used by scripts/seed_products_from_legacy.py
(one-time production seed) and by the test suite (in-memory DB fixtures).
"""
from __future__ import annotations

from pathlib import Path

from diamond_calculator.application.validation import VALID_GOLDS
from diamond_calculator.repository.models import Product, ProductImage, ProductVariant, db

STATIC_ROOT = Path(__file__).resolve().parent.parent.parent / 'static'
IMAGE_COLORS = ('white', 'yellow', 'rose')

# Legacy style display names and chain color-per-style mapping, as they used
# to live in diamond_calculator/filters.py before the catalog migration. Kept
# here only as one-time seed data for Product.name_zh / Product.default_color;
# once seeded, the DB rows are the source of truth and these are unused.
_LEGACY_STYLE_LABELS = {
    'pendant':  {'A': '四爪項墜', 'B': '兔耳項墜', 'C': '水滴項墜'},
    'ring':     {'A': '經典六爪', 'B': '低語之光', 'C': '羽翼'},
    'earring':  {'A': '六爪耳釘', 'B': '款式B', 'C': '款式C'},
    'bracelet': {'A': '微笑單鑽', 'B': '銘印手鍊', 'C': '單鑽手鍊'},
    'chain':    {'A': '斗圓鍊 K白', 'B': '斗圓鍊 K玫瑰', 'C': '斗圓鍊 K黃'},
}

_LEGACY_CHAIN_COLORS = {'A': 'white', 'B': 'rose', 'C': 'yellow'}

# Metal density in 錢 (chin) per cm³. Weight = volume x density. Historical
# constant used only to derive the one-time legacy seed data below; the live
# pricing path (diamond_calculator.application.pricing) no longer uses it —
# variant weights are read straight from the ProductVariant rows this module
# creates.
DENSITY_CHIN_PER_CM3 = {
    '9k':    3.07,
    '14k':   3.60,
    '18k':   4.16,
    'pt950': 5.57,
    's925':  2.76,
}

# Legacy per-metal weight table (chin), as originally hand-tuned per style.
# Kept only as the source data from which the metal-independent VOLUME_TABLE
# is derived (via the 14K column); effective weights are recomputed below as
# volume x density.
_LEGACY_WEIGHT_TABLE = {
    'pendant': {
        'A': {
            '9k':    {'0.1': 0.09, '0.3': 0.12, '0.5': 0.15, '1.0': 0.20},
            '14k':   {'0.1': 0.10, '0.3': 0.14, '0.5': 0.17, '1.0': 0.23},
            '18k':   {'0.1': 0.12, '0.3': 0.16, '0.5': 0.20, '1.0': 0.27},
            'pt950': {'0.1': 0.15, '0.3': 0.20, '0.5': 0.25, '1.0': 0.35},
            's925':  {'0.1': 0.08, '0.3': 0.11, '0.5': 0.13, '1.0': 0.18},
        },
        'B': {
            '9k':    {'0.1': 0.10, '0.3': 0.15, '0.5': 0.19, '1.0': 0.28},
            '14k':   {'0.1': 0.11, '0.3': 0.17, '0.5': 0.22, '1.0': 0.33},
            '18k':   {'0.1': 0.13, '0.3': 0.20, '0.5': 0.26, '1.0': 0.39},
            'pt950': {'0.1': 0.16, '0.3': 0.25, '0.5': 0.34, '1.0': 0.52},
            's925':  {'0.1': 0.09, '0.3': 0.13, '0.5': 0.17, '1.0': 0.25},
        },
        'C': {
            '9k':    {'0.1': 0.14, '0.3': 0.21, '0.5': 0.28, '1.0': 0.46},
            '14k':   {'0.1': 0.16, '0.3': 0.24, '0.5': 0.32, '1.0': 0.52},
            '18k':   {'0.1': 0.19, '0.3': 0.28, '0.5': 0.37, '1.0': 0.60},
            'pt950': {'0.1': 0.25, '0.3': 0.37, '0.5': 0.49, '1.0': 0.80},
            's925':  {'0.1': 0.13, '0.3': 0.19, '0.5': 0.25, '1.0': 0.40},
        },
    },
    'ring': {
        'A': {
            '9k':    {'0.1': 0.39, '0.3': 0.48, '0.5': 0.57, '1.0': 0.74},
            '14k':   {'0.1': 0.46, '0.3': 0.57, '0.5': 0.67, '1.0': 0.87},
            '18k':   {'0.1': 0.53, '0.3': 0.65, '0.5': 0.77, '1.0': 1.01},
            'pt950': {'0.1': 0.70, '0.3': 0.86, '0.5': 1.02, '1.0': 1.33},
            's925':  {'0.1': 0.35, '0.3': 0.44, '0.5': 0.52, '1.0': 0.68},
        },
        'B': {
            '9k':    {'0.1': 0.40, '0.3': 0.62, '0.5': 0.84, '1.0': 1.39},
            '14k':   {'0.1': 0.47, '0.3': 0.75, '0.5': 1.03, '1.0': 1.73},
            '18k':   {'0.1': 0.54, '0.3': 0.86, '0.5': 1.18, '1.0': 1.98},
            'pt950': {'0.1': 0.71, '0.3': 1.13, '0.5': 1.55, '1.0': 2.60},
            's925':  {'0.1': 0.36, '0.3': 0.58, '0.5': 0.80, '1.0': 1.35},
        },
        'C': {
            '9k':    {'0.1': 0.40, '0.3': 0.69, '0.5': 0.97, '1.0': 1.54},
            '14k':   {'0.1': 0.48, '0.3': 0.82, '0.5': 1.15, '1.0': 1.82},
            '18k':   {'0.1': 0.55, '0.3': 0.92, '0.5': 1.33, '1.0': 2.11},
            'pt950': {'0.1': 0.72, '0.3': 1.24, '0.5': 1.75, '1.0': 2.78},
            's925':  {'0.1': 0.36, '0.3': 0.62, '0.5': 0.88, '1.0': 1.40},
        },
    },
    'earring': {
        'A': {
            '9k':    {'0.1': 0.09, '0.3': 0.14, '0.5': 0.18, '1.0': 0.27},
            '14k':   {'0.1': 0.10, '0.3': 0.15, '0.5': 0.20, '1.0': 0.30},
            '18k':   {'0.1': 0.12, '0.3': 0.18, '0.5': 0.24, '1.0': 0.36},
        },
    },
    'bracelet': {
        'A': {
            '9k':    {'0.1': 0.66, '0.3': 0.88, '0.5': 1.10, '1.0': 1.47},
            '14k':   {'0.1': 0.78, '0.3': 1.09, '0.5': 1.33, '1.0': 1.79},
            '18k':   {'0.1': 0.91, '0.3': 1.21, '0.5': 1.52, '1.0': 2.05},
            'pt950': {'0.1': 1.19, '0.3': 1.59, '0.5': 1.98, '1.0': 2.78},
            's925':  {'0.1': 0.60, '0.3': 0.83, '0.5': 0.97, '1.0': 1.35},
        },
        'B': {
            '9k':    {'0.1': 0.46, '0.3': 0.61, '0.5': 0.77, '1.0': 1.02},
            '14k':   {'0.1': 0.55, '0.3': 0.77, '0.5': 0.94, '1.0': 1.27},
            '18k':   {'0.1': 0.64, '0.3': 0.85, '0.5': 1.07, '1.0': 1.44},
            'pt950': {'0.1': 0.84, '0.3': 1.12, '0.5': 1.40, '1.0': 1.96},
            's925':  {'0.1': 0.77, '0.3': 1.06, '0.5': 1.25, '1.0': 1.73},
        },
        'C': {
            '9k':    {'0.1': 0.30, '0.3': 0.40, '0.5': 0.50, '1.0': 0.67},
            '14k':   {'0.1': 0.36, '0.3': 0.50, '0.5': 0.61, '1.0': 0.83},
            '18k':   {'0.1': 0.42, '0.3': 0.56, '0.5': 0.70, '1.0': 0.95},
            'pt950': {'0.1': 0.55, '0.3': 0.73, '0.5': 0.92, '1.0': 1.28},
            's925':  {'0.1': 0.28, '0.3': 0.39, '0.5': 0.46, '1.0': 0.63},
        },
    },
}

def _carat02_weight(w01: float, w03: float) -> float:
    return round(w01 + (w03 - w01) * 0.5, 4)


def _apply_bracelet_carat_rules(table: dict) -> None:
    """銘印手鍊 (B) only 0.1 ct; other bracelets offer 0.1 and 0.2 ct."""
    bracelet = table.get('bracelet')
    if not bracelet:
        return
    for style, golds in bracelet.items():
        for gold, carats in golds.items():
            w01 = carats.get('0.1')
            w03 = carats.get('0.3', w01)
            if style == 'B':
                golds[gold] = {'0.1': w01}
            else:
                golds[gold] = {'0.1': w01, '0.2': _carat02_weight(w01, w03)}


_apply_bracelet_carat_rules(_LEGACY_WEIGHT_TABLE)

CHAIN_WEIGHT_CHIN = {'3fen': 0.3, '4fen': 0.4}

# Volume (cm³) per category/style/carat, derived from the legacy 14K weights
# (volume is metal-independent: volume = weight / density).
VOLUME_TABLE = {
    category: {
        style: {
            carat: round(weight_chin / DENSITY_CHIN_PER_CM3['14k'], 4)
            for carat, weight_chin in styles['14k'].items()
        }
        for style, styles in types.items()
    }
    for category, types in _LEGACY_WEIGHT_TABLE.items()
}

# Effective weight table (chin): weight = volume x density.
WEIGHT_TABLE = {
    category: {
        style: {
            gold: {
                carat: round(volume * DENSITY_CHIN_PER_CM3[gold], 4)
                for carat, volume in carats.items()
            }
            for gold in _LEGACY_WEIGHT_TABLE[category][style]
        }
        for style, carats in types.items()
    }
    for category, types in VOLUME_TABLE.items()
}


def _image_for(category: str, style: str, color: str, check_exists: bool):
    rel = f'images/{color}/{category}-{style}.png'
    if check_exists and not (STATIC_ROOT / rel).exists():
        return None
    return rel


def seed_legacy_products(check_images_exist: bool = True) -> int:
    """Creates Product/ProductVariant/ProductImage rows for the legacy 13
    style slots. Returns the number of products created. No-op (returns 0)
    if any Product already exists.
    """
    if Product.query.count() > 0:
        return 0

    created = 0
    for category, styles in WEIGHT_TABLE.items():
        for style, golds in styles.items():
            product = Product(
                category=category,
                name_zh=_LEGACY_STYLE_LABELS.get(category, {}).get(style, style),
                default_color='white',
                is_published=True,
                sort_order=ord(style) - ord('A'),
            )
            for gold, carats in golds.items():
                for carat, weight_chin in carats.items():
                    product.variants.append(ProductVariant(gold=gold, carat=carat, weight_chin=weight_chin))
            for color in IMAGE_COLORS:
                path = _image_for(category, style, color, check_images_exist)
                if path:
                    product.images.append(ProductImage(color=color, file_path=path))
            db.session.add(product)
            created += 1

    for style, color in _LEGACY_CHAIN_COLORS.items():
        product = Product(
            category='chain',
            name_zh=_LEGACY_STYLE_LABELS.get('chain', {}).get(style, style),
            default_color=color,
            is_published=True,
            sort_order=ord(style) - ord('A'),
        )
        for gold in sorted(VALID_GOLDS):
            for carat, weight_chin in CHAIN_WEIGHT_CHIN.items():
                product.variants.append(ProductVariant(gold=gold, carat=carat, weight_chin=weight_chin))
        path = _image_for('chain', style, color, check_images_exist)
        if path:
            product.images.append(ProductImage(color=color, file_path=path))
        db.session.add(product)
        created += 1

    db.session.commit()
    return created


def _allowed_bracelet_carats(product: Product) -> set[str]:
    if product.sort_order == 1:
        return {'0.1'}
    return {'0.1', '0.2'}


def sync_bracelet_variants() -> tuple[int, int]:
    """Ensure bracelet listings match carat rules (銘印 0.1 only; others 0.1/0.2)."""
    products = Product.query.filter_by(category='bracelet').order_by(Product.sort_order).all()
    removed = added = 0
    for product in products:
        allowed = _allowed_bracelet_carats(product)
        for variant in list(product.variants):
            if variant.carat in allowed:
                continue
            db.session.delete(variant)
            removed += 1
        existing = {(v.gold, v.carat) for v in product.variants}
        golds = {v.gold for v in product.variants}
        for gold in golds:
            if '0.2' not in allowed or (gold, '0.2') in existing:
                continue
            base = next((v for v in product.variants if v.gold == gold and v.carat == '0.1'), None)
            if not base:
                continue
            ref = ProductVariant.query.filter_by(
                product_id=product.id, gold=gold, carat='0.3',
            ).first()
            w03 = ref.weight_chin if ref else base.weight_chin
            product.variants.append(ProductVariant(
                gold=gold,
                carat='0.2',
                weight_chin=_carat02_weight(base.weight_chin, w03),
            ))
            added += 1
    if removed or added:
        db.session.commit()
    return removed, added
