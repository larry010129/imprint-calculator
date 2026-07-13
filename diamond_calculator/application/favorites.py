"""Reusable saved shop configurations."""

import json

from flask import url_for

from diamond_calculator.application.validation import validate_submission_fields
from diamond_calculator.filters import resolve_style_image_url, submission_summary
from diamond_calculator.repository.models import FavoriteItem, Product, db


def _config(item):
    return json.loads(item.config_json)


def favorite_payload(item):
    config = _config(item)
    product = item.product
    image_path = resolve_style_image_url(
        item.category, item.style_type, config.get('gold'), config.get('color'),
        product=product,
    )
    return {
        'id': item.id,
        'summary': item.summary_zh,
        'category': item.category,
        'config': config,
        'image_url': url_for('static', filename=image_path) if image_path else None,
        'load_url': url_for('main.calculator', favorite=item.id),
        'created_at': item.created_at.isoformat() if item.created_at else None,
    }


def add_favorite(user_id, data):
    cleaned, error = validate_submission_fields(data)
    if error:
        return None, error
    product = db.session.get(Product, int(cleaned['type']))
    if not product or not product.is_published:
        return None, 'product not available'
    canonical = json.dumps(cleaned, ensure_ascii=False, sort_keys=True)
    existing = FavoriteItem.query.filter_by(
        user_id=user_id, config_json=canonical,
    ).first()
    if existing:
        return existing, None
    item = FavoriteItem(
        user_id=user_id,
        product_id=product.id,
        category=cleaned['category'],
        style_type=str(cleaned['type']),
        config_json=canonical,
        summary_zh=submission_summary(
            cleaned['category'], cleaned['type'], product=product,
        ),
    )
    db.session.add(item)
    db.session.commit()
    return item, None


def get_favorite(user_id, item_id):
    return FavoriteItem.query.filter_by(id=item_id, user_id=user_id).first()


def favorite_config(item):
    return _config(item)
