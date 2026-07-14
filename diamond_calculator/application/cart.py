"""Shopping cart helpers — store configured items before checkout."""

import json

from flask import url_for

from diamond_calculator.application.order_pricing import (
    apply_pricing_to_submission,
    compute_order_pricing,
)
from diamond_calculator.application.validation import validate_submission_fields
from diamond_calculator.filters import (
    CATEGORY_LABELS,
    COLOR_LABELS,
    PURITY_LABELS,
    diamond_color_label,
    resolve_style_image_url,
    submission_summary,
)
from diamond_calculator.repository.models import CartItem, Product, Submission, db


def _item_config(item):
    return json.loads(item.config_json)


def _product_for(item):
    if item.product_id:
        return db.session.get(Product, item.product_id)
    return None


def _image_url_for_item(item, config):
    product = _product_for(item)
    path = resolve_style_image_url(
        item.category,
        item.style_type,
        config.get('gold'),
        config.get('color'),
        product=product,
    )
    return url_for('static', filename=path) if path else None


def _specs_snippet(item, config):
    gold = config.get('gold')
    color = config.get('color')
    return {
        'category': CATEGORY_LABELS.get(item.category, item.category),
        'carat': config.get('carat'),
        'gold': PURITY_LABELS.get(gold, gold),
        'color': COLOR_LABELS.get(color, color) if color else None,
    }


def get_cart_item(user_id, item_id):
    return CartItem.query.filter_by(id=item_id, user_id=user_id).first()


def _submission_from_cleaned(user_id, cleaned, pricing):
    variant = pricing.variant
    submission = Submission(
        user_id=user_id,
        product_id=variant.product_id if variant else None,
        category=cleaned['category'],
        carat=cleaned['carat'],
        style_type=cleaned['type'],
        gold_purity=cleaned['gold'],
        color=cleaned.get('color'),
        diamond_kind=cleaned.get('diamondKind', 'white'),
        fancy_color=cleaned.get('fancyColor'),
        stone_count=cleaned.get('stoneCount'),
        diamond_shape=cleaned.get('diamondShape', 'round'),
        weight=pricing.weight_grams,
        ring_size=cleaned.get('ringSize'),
        engraving_band=cleaned.get('engravingBand'),
        engraving_girdle=cleaned.get('engravingGirdle'),
        include_chain=cleaned.get('includeChain', False),
        chain_product_id=pricing.chain_variant.product_id if pricing.chain_variant else None,
        chain_gold=cleaned.get('chainGold'),
        chain_color=cleaned.get('chainColor'),
        chain_length_cm=cleaned.get('chainLength') if cleaned.get('includeChain') else None,
        chain_weight_chin=pricing.chain_weight_chin or (
            pricing.weight_chin if cleaned['category'] == 'chain' else None
        ),
    )
    if cleaned['category'] in ('chain', 'bracelet'):
        submission.chain_length_cm = cleaned.get('lengthCm')
    apply_pricing_to_submission(submission, cleaned, pricing)
    return submission


def cart_item_payload(item):
    config = _item_config(item)
    return {
        'id': item.id,
        'category': item.category,
        'style_type': item.style_type,
        'summary': item.summary_zh,
        'total_price': item.total_price,
        'created_at': item.created_at.isoformat() if item.created_at else None,
        'image_url': _image_url_for_item(item, config),
        'edit_url': url_for('main.cart_edit', item_id=item.id),
        'specs': _specs_snippet(item, config),
    }


def cart_item_detail_payload(item, tax_rate=0.05):
    config = _item_config(item)
    cleaned, error = validate_submission_fields(config)
    pricing = compute_order_pricing(config, partial=False) if not error else None
    specs = _specs_snippet(item, config)
    specs['diamond_color'] = diamond_color_label(
        cleaned.get('diamondKind', 'white') if cleaned else config.get('diamondKind', 'white'),
        cleaned.get('fancyColor') if cleaned else config.get('fancyColor'),
        category=item.category,
    )
    if cleaned:
        specs['ring_size'] = cleaned.get('ringSize')
        specs['length_cm'] = cleaned.get('lengthCm') or cleaned.get('chainLength')
        specs['engraving_band'] = cleaned.get('engravingBand') or None
        specs['engraving_girdle'] = cleaned.get('engravingGirdle') or None

    breakdown = {}
    if pricing and pricing.ready and not pricing.manual_override:
        breakdown = {
            'diamond_price': pricing.diamond_price,
            'taijin_price': pricing.taijin_display,
            'labor_price': pricing.labor_display,
            'chain_price': pricing.chain_display,
            'tax_amount': pricing.tax_amount,
            'total': pricing.total,
        }
    elif pricing and pricing.ready:
        breakdown = {'total': pricing.total, 'manual_override': True}

    return {
        **cart_item_payload(item),
        'specs': specs,
        'breakdown': breakdown,
        'tax_rate': tax_rate,
    }


def add_cart_item(user_id, data):
    cleaned, error = validate_submission_fields(data)
    if error:
        return None, error
    pricing = compute_order_pricing(cleaned, partial=False)
    if not pricing.ready:
        return None, pricing.error or 'pricing error'

    product = db.session.get(Product, pricing.variant.product_id) if pricing.variant else None
    item = CartItem(
        user_id=user_id,
        product_id=pricing.variant.product_id if pricing.variant else None,
        category=cleaned['category'],
        style_type=cleaned['type'],
        config_json=json.dumps(data, ensure_ascii=False),
        summary_zh=submission_summary(cleaned['category'], cleaned['type'], product=product),
        total_price=pricing.total,
    )
    db.session.add(item)
    db.session.commit()
    return item, None


def update_cart_item(user_id, item_id, data):
    item = get_cart_item(user_id, item_id)
    if not item:
        return None, 'not found'
    cleaned, error = validate_submission_fields(data)
    if error:
        return None, error
    pricing = compute_order_pricing(cleaned, partial=False)
    if not pricing.ready:
        return None, pricing.error or 'pricing error'

    product = db.session.get(Product, pricing.variant.product_id) if pricing.variant else None
    item.product_id = pricing.variant.product_id if pricing.variant else None
    item.category = cleaned['category']
    item.style_type = cleaned['type']
    item.config_json = json.dumps(data, ensure_ascii=False)
    item.summary_zh = submission_summary(cleaned['category'], cleaned['type'], product=product)
    item.total_price = pricing.total
    db.session.commit()
    return item, None


def checkout_cart(user_id, item_ids=None):
    query = CartItem.query.filter_by(user_id=user_id)
    if item_ids is not None:
        if not item_ids:
            return [], 'no items selected'
        query = query.filter(CartItem.id.in_(item_ids))
    items = query.order_by(CartItem.created_at.asc()).all()
    if not items:
        return [], 'cart is empty'

    if item_ids is not None and len(items) != len(set(item_ids)):
        return [], 'invalid item selection'

    created_ids = []
    for item in items:
        data = json.loads(item.config_json)
        cleaned, error = validate_submission_fields(data)
        if error:
            db.session.rollback()
            return [], error
        pricing = compute_order_pricing(cleaned, partial=False)
        if not pricing.ready:
            db.session.rollback()
            return [], pricing.error or 'pricing error'
        submission = _submission_from_cleaned(user_id, cleaned, pricing)
        db.session.add(submission)
        db.session.flush()
        created_ids.append(submission.id)

    for item in items:
        db.session.delete(item)
    db.session.commit()
    return created_ids, None


def enrich_cart_items_for_template(items):
    """Server-side enrichment for cart.html first paint."""
    enriched = []
    for item in items:
        config = _item_config(item)
        enriched.append({
            'item': item,
            'image_url': _image_url_for_item(item, config),
            'specs': _specs_snippet(item, config),
        })
    return enriched
