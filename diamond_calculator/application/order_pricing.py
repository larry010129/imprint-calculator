"""Unified order pricing — single source of truth for quote and submit."""

from __future__ import annotations

from dataclasses import dataclass

from diamond_calculator.application.diamond_options import compute_diamond_list_price
from diamond_calculator.application.pricing import (
    CHIN_TO_GRAMS,
    LABOR_FEE,
    METAL_SYMBOL,
    PURITY_MULTIPLIER,
    TAX_RATE,
    compute_chain_addon,
    get_metal_prices,
    get_product_variant,
    lookup_weight,
)
from diamond_calculator.application.validation import validate_submission_fields


@dataclass
class OrderPricingResult:
    ready: bool
    error: str | None = None
    diamond_price: float | None = None
    taijin_pre_tax: float | None = None
    taijin_display: float | None = None
    labor_pre_tax: float | None = None
    labor_display: float | None = None
    chain_display: float | None = None
    chain_pre_tax: float | None = None
    tax_amount: float | None = None
    total: float | None = None
    manual_override: bool = False
    gold_rate_per_gram: float | None = None
    price_source: str | None = None
    variant: object = None
    chain_variant: object = None
    chain_weight_chin: float | None = None
    weight_chin: float | None = None
    weight_grams: float | None = None

    def to_quote_dict(self) -> dict:
        if not self.ready:
            out = {'ready': False}
            if self.error:
                out['error'] = self.error
            return out
        if self.manual_override:
            return {
                'ready': True,
                'diamondPrice': None,
                'taijinPrice': None,
                'laborPrice': None,
                'total': self.total,
                'manualOverride': True,
            }
        return {
            'ready': True,
            'diamondPrice': self.diamond_price,
            'taijinPrice': self.taijin_display,
            'laborPrice': self.labor_display,
            'chainPrice': self.chain_display,
            'total': self.total,
            'manualOverride': False,
        }


def _metal_pre_tax(gold, weight_grams, category):
    raw, source = get_metal_prices()
    per_gram = raw[METAL_SYMBOL[gold]] * PURITY_MULTIPLIER[gold]
    multiplier = 2 if category == 'chain' else 1
    return per_gram * weight_grams * multiplier, per_gram, source


def compute_order_pricing(data, *, partial=False, require_published=True) -> OrderPricingResult:
    """Compute tax-aware pricing for shop quote and order submit."""
    cleaned, error = validate_submission_fields(data, partial=partial)
    if error:
        return OrderPricingResult(ready=False, error=error)

    category = cleaned.get('category')
    carat = cleaned.get('carat')
    gold = cleaned.get('gold')
    type_id = cleaned.get('type')
    if not all([category, carat, gold, type_id]):
        return OrderPricingResult(ready=False)

    # Chains/bracelets are priced by length; without it there is no quote yet.
    # (For full submits, validation has already rejected the missing field.)
    if category in ('chain', 'bracelet') and cleaned.get('lengthCm') is None:
        return OrderPricingResult(ready=False)

    diamond_kind = cleaned.get('diamondKind', 'white')
    fancy_color = cleaned.get('fancyColor')
    stone_count = cleaned.get('stoneCount')
    diamond_shape = cleaned.get('diamondShape', 'round')

    try:
        variant = get_product_variant(
            category, type_id, gold, carat,
            require_published=require_published,
        )
        weight_chin = lookup_weight(
            category, type_id, gold, carat, cleaned.get('lengthCm'),
            require_published=require_published,
        )
    except KeyError:
        return OrderPricingResult(ready=False, error='product not available')

    weight_grams = weight_chin * CHIN_TO_GRAMS
    labor_pre_tax = LABOR_FEE.get(category, 5000)

    if variant.manual_price_twd is not None:
        raw, source = get_metal_prices()
        rate_used = raw[METAL_SYMBOL[gold]] * PURITY_MULTIPLIER[gold]
        return OrderPricingResult(
            ready=True,
            total=variant.manual_price_twd,
            manual_override=True,
            gold_rate_per_gram=rate_used,
            price_source=source,
            variant=variant,
            weight_chin=weight_chin,
            weight_grams=weight_grams,
        )

    try:
        taijin_pre_tax, rate_used, source = _metal_pre_tax(gold, weight_grams, category)
    except Exception:
        return OrderPricingResult(ready=False)

    taijin_display = round(taijin_pre_tax * (1 + TAX_RATE))
    labor_display = round(labor_pre_tax * (1 + TAX_RATE))
    tax_amount = (taijin_display - taijin_pre_tax) + (labor_display - labor_pre_tax)

    diamond_price = None
    if category != 'chain':
        diamond_price = compute_diamond_list_price(
            carat,
            diamond_kind=diamond_kind,
            fancy_color=fancy_color,
            stone_count=stone_count,
            diamond_shape=diamond_shape,
            category=category,
        )
        if diamond_price is None:
            return OrderPricingResult(ready=False)

    total = (diamond_price or 0) + taijin_display + labor_display
    chain_display = None
    chain_pre_tax = None
    chain_variant = None
    chain_weight_chin = None

    if category == 'pendant' and cleaned.get('includeChain'):
        chain_id = cleaned.get('chainProductId')
        chain_gold = cleaned.get('chainGold')
        chain_length = cleaned.get('chainLength')
        if all([chain_id, chain_gold, chain_length]):
            try:
                chain_pre_tax, chain_weight_chin, chain_variant = compute_chain_addon(
                    chain_id, chain_gold, chain_length,
                    require_published=require_published,
                )
                chain_display = round(chain_pre_tax * (1 + TAX_RATE))
                tax_amount += chain_display - chain_pre_tax
                total += chain_display
            except KeyError:
                return OrderPricingResult(ready=False, error='invalid chain option')

    return OrderPricingResult(
        ready=True,
        diamond_price=diamond_price,
        taijin_pre_tax=taijin_pre_tax,
        taijin_display=taijin_display,
        labor_pre_tax=labor_pre_tax,
        labor_display=labor_display,
        chain_display=chain_display,
        chain_pre_tax=chain_pre_tax,
        tax_amount=round(tax_amount),
        total=round(total),
        gold_rate_per_gram=rate_used,
        price_source=source,
        variant=variant,
        chain_variant=chain_variant,
        chain_weight_chin=chain_weight_chin,
        weight_chin=weight_chin,
        weight_grams=weight_grams,
    )


def apply_pricing_to_submission(submission, cleaned, pricing: OrderPricingResult) -> None:
    """Copy computed pricing onto a Submission model instance."""
    submission.total_price = pricing.total
    submission.diamond_price_twd = pricing.diamond_price
    submission.taijin_price_twd = pricing.taijin_display
    submission.labor_price_twd = pricing.labor_display
    submission.tax_amount_twd = pricing.tax_amount
    submission.gold_rate_per_gram = pricing.gold_rate_per_gram
    submission.price_source = pricing.price_source
    if pricing.chain_display is not None:
        submission.chain_total_twd = pricing.chain_display
    elif not cleaned.get('includeChain'):
        submission.chain_total_twd = None
