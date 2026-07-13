"""Server-side shop price quote — single source of truth for the storefront."""

from diamond_calculator.application.order_pricing import compute_order_pricing


def build_shop_quote(data, *, require_published=True):
    """Compute a price breakdown for the current shop configuration."""
    return compute_order_pricing(
        data, partial=True, require_published=require_published,
    ).to_quote_dict()
