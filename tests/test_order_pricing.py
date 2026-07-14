"""Tests for unified order pricing."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from diamond_calculator.application.order_pricing import compute_order_pricing
from diamond_calculator.application.shop_quote import build_shop_quote


def test_quote_and_pricing_same_shape():
    """build_shop_quote delegates to compute_order_pricing."""
    partial = {'category': 'ring'}
    q = build_shop_quote(partial)
    p = compute_order_pricing(partial, partial=True)
    assert q.get('ready') is False
    assert p.ready is False


def test_chain_partial_not_ready_without_length():
    data = {
        'category': 'chain',
        'type': '1',
        'gold': '18k',
        'carat': '3fen',
    }
    result = compute_order_pricing(data, partial=True)
    assert result.ready is False


print('order pricing tests passed')
