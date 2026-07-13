"""
Diamond pricing unit tests. Run from project root: python tests/test_diamond_pricing.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('DISABLE_PRICE_SCHEDULER', '1')

from diamond_calculator.application.diamond_options import compute_diamond_list_price

# White single-stone (image 1)
assert compute_diamond_list_price('0.1', diamond_kind='white', category='ring') == 24000
assert compute_diamond_list_price('0.3', diamond_kind='white', category='ring') == 79000
assert compute_diamond_list_price('0.2', diamond_kind='white', category='ring') == 48000

# White multi-stone (image 3) — earrings only
assert compute_diamond_list_price(
    '0.1', diamond_kind='white', stone_count=2, category='earring',
) == 45600

# Bracelets use single-stone pricing
assert compute_diamond_list_price(
    '0.1', diamond_kind='white', category='bracelet',
) == 24000
assert compute_diamond_list_price(
    '0.2', diamond_kind='white', stone_count=2, category='earring',
) == 86400
assert compute_diamond_list_price(
    '0.5', diamond_kind='white', stone_count=2, category='earring',
) == round(142200 * 0.85)

# Colored single-stone (image 2)
assert compute_diamond_list_price(
    '0.3', diamond_kind='fancy', fancy_color='yellow', category='ring',
) == 102000
assert compute_diamond_list_price(
    '0.5', diamond_kind='fancy', fancy_color='pink', category='ring',
) == 127000
assert compute_diamond_list_price(
    '0.1', diamond_kind='fancy', fancy_color='yellow', category='ring',
) is None

# Colored multi-stone (image 4)
assert compute_diamond_list_price(
    '0.3', diamond_kind='fancy', fancy_color='yellow', stone_count=2, category='earring',
) == 173400
assert compute_diamond_list_price(
    '0.5', diamond_kind='fancy', fancy_color='pink', stone_count=2, category='earring',
) == round(173400 * 0.85)

# Non-round +10% surcharge (0.30ct minimum)
assert compute_diamond_list_price(
    '0.1', diamond_kind='white', diamond_shape='heart', category='ring',
) is None
assert compute_diamond_list_price(
    '0.3', diamond_kind='white', diamond_shape='oval', category='ring',
) == round(79000 * 1.10)
assert compute_diamond_list_price(
    '0.3', diamond_kind='fancy', fancy_color='blue', diamond_shape='heart', category='ring',
) == round(102000 * 1.10)

# Round stays regular price
assert compute_diamond_list_price(
    '0.3', diamond_kind='white', diamond_shape='round', category='ring',
) == 79000

print('test_diamond_pricing.py: all assertions passed')
