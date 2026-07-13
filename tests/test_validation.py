"""
Validation unit tests. Run from project root: python tests/test_validation.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('DISABLE_PRICE_SCHEDULER', '1')

from diamond_calculator.application.validation import (
    validate_submission_fields, RING_SIZE_MIN, RING_SIZE_MAX,
)

ok, err = validate_submission_fields({
    'category': 'ring', 'carat': '1.0', 'type': 'A', 'gold': '18k', 'color': 'white', 'ringSize': 9.0
})
assert err is None, err
assert ok['category'] == 'ring' and ok['carat'] == '1.0' and ok['ringSize'] == 9.0

_, err = validate_submission_fields({
    'category': 'ring', 'carat': '1.0', 'type': 'A', 'gold': '18k'
})
assert err and 'ringSize' in err

_, err = validate_submission_fields({
    'category': 'sofa', 'carat': '2', 'type': 'Z', 'gold': 'tin'
})
assert err

_, err = validate_submission_fields({
    'category': 'ring', 'carat': '0.5', 'type': 'B', 'gold': '14k',
    'ringSize': RING_SIZE_MIN - 0.5
})
assert err and 'ringSize' in err

ok, err = validate_submission_fields({
    'category': 'ring', 'carat': '1.0', 'type': 'A', 'gold': '18k', 'color': 'white',
    'ringSize': RING_SIZE_MAX
})
assert err is None, f"maximum valid ringSize should be accepted, got: {err}"

ok, err = validate_submission_fields({
    'category': 'bracelet', 'carat': '0.1', 'type': 'B', 'gold': '14k', 'lengthCm': 18,
})
assert err and 'color' in err, f"14k should require color, got: {err}"

ok, err = validate_submission_fields({
    'category': 'bracelet', 'carat': '0.1', 'type': 'B', 'gold': '14k', 'color': 'rose', 'lengthCm': 18,
})
assert err is None, f"14k with color should be valid, got: {err}"
assert ok.get('stoneCount') is None, f"bracelet should use single stone, got stoneCount={ok.get('stoneCount')}"

ok, err = validate_submission_fields({
    'category': 'ring', 'carat': '0.5', 'type': 'B', 'gold': '9k', 'ringSize': 9.0
})
assert err is None, f"9k without color should default to white, got: {err}"
assert ok.get('color') == 'white'

_, err = validate_submission_fields({
    'category': 'ring', 'carat': '0.5', 'type': 'B', 'gold': '9k', 'color': 'yellow', 'ringSize': 9.0
})
assert err and '9k' in err, f"9k yellow should be rejected, got: {err}"

ok, err = validate_submission_fields({
    'category': 'ring', 'carat': '0.5', 'type': 'B', 'gold': '18k', 'color': 'white',
    'ringSize': 9, 'engravingBand': 'LOVE', 'engravingGirdle': '2026',
})
assert err is None and ok['engravingBand'] == 'LOVE' and ok['engravingGirdle'] == '2026'

_, err = validate_submission_fields({
    'category': 'ring', 'carat': '0.5', 'type': 'B', 'gold': '18k', 'color': 'white',
    'ringSize': 9, 'engravingGirdle': 'LOVE!',
})
assert err and 'engravingGirdle' in err, f"symbols in girdle should be rejected, got: {err}"

_, err = validate_submission_fields({
    'category': 'ring', 'carat': '0.5', 'type': 'B', 'gold': '18k', 'color': 'white',
    'ringSize': 9, 'engravingGirdle': '愛',
})
assert err and 'engravingGirdle' in err, f"CJK in girdle should be rejected, got: {err}"

_, err = validate_submission_fields({
    'category': 'ring', 'carat': '0.5', 'type': 'B', 'gold': '18k', 'color': 'white',
    'ringSize': 9, 'engravingGirdle': 'ABCDEFGHIJK',
})
assert err and 'engravingGirdle' in err, f"11+ chars in girdle should be rejected, got: {err}"

ok, err = validate_submission_fields({
    'category': 'ring', 'carat': '0.5', 'type': 'B', 'gold': '18k', 'color': 'white',
    'ringSize': 9, 'engravingBand': 'LOVE YOU',
})
assert err is None and ok['engravingBand'] == 'LOVE YOU', f"band engraving allows spaces, got: {err}"

_, err = validate_submission_fields({
    'category': 'chain', 'carat': '3fen', 'type': 'A', 'gold': '18k', 'color': 'white',
})
assert err and 'lengthCm' in err, f"chain length should be required, got: {err}"

ok, err = validate_submission_fields({
    'category': 'chain', 'carat': '3fen', 'type': 'A', 'gold': '18k', 'color': 'white',
    'lengthCm': 45,
})
assert err is None and ok['lengthCm'] == 45

ok, err = validate_submission_fields({
    'category': 'pendant', 'carat': '0.3', 'type': '1', 'gold': '14k', 'color': 'white',
    'includeChain': True,
}, partial=True)
assert err is None, f"partial pendant quote should allow incomplete chain options, got: {err}"
assert ok.get('includeChain') is True

_, err = validate_submission_fields({
    'category': 'pendant', 'carat': '0.3', 'type': '1', 'gold': '14k', 'color': 'white',
    'includeChain': True,
})
assert err and 'chainProductId' in err, f"full submit should require chain options, got: {err}"

print('all validation checks passed')
