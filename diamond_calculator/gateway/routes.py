from datetime import datetime, timezone, timedelta
import re
import json

from flask import (
    Blueprint, Response, abort, current_app, flash, jsonify, redirect,
    render_template, request, send_from_directory, session, url_for,
)
from sqlalchemy import func, text
from sqlalchemy.exc import OperationalError
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from diamond_calculator.application.audit import log_admin_action
from diamond_calculator.application.auth import (
    is_locked_out, is_register_locked_out,
    record_login_failure, record_login_success,
    record_register_failure, record_register_success,
    clear_login_lockout,
)
from diamond_calculator.application.invites import (
    consume_invite_code, generate_invite_code, invite_required, validate_invite_code,
)
from diamond_calculator.application.order_pricing import (
    apply_pricing_to_submission, compute_order_pricing,
)
from diamond_calculator.application.rate_limit import limiter
from diamond_calculator.application.pricing import (
    CHIN_TO_GRAMS, DIAMOND_PRICE, LABOR_FEE, METAL_SYMBOL, PURITY_MULTIPLIER, SHOP_DIAMOND_CARATS, TAX_RATE,
    get_metal_prices,
)
from diamond_calculator.application.diamond_options import diamond_options_payload
from diamond_calculator.application.dashboard import build_dashboard_data, dashboard_csv
from diamond_calculator.application.favorites import (
    add_favorite, favorite_config, favorite_payload, get_favorite,
)
from diamond_calculator.application.shop_quote import build_shop_quote
from diamond_calculator.application.shared_config import decode_config
from diamond_calculator.application.ring_sizes import RING_SIZE_MEASURE_CHART, RING_SIZE_REFERENCE
from diamond_calculator.application.bot_metal_feed import (
    fetch_taiwan_bank_prices, get_bot_gold_display, get_price_metadata,
)
from diamond_calculator.application.uploads import (
    UploadError, copy_product_image, delete_product_image, save_product_image,
)
from diamond_calculator.application.validation import (
    CATEGORY_DISPLAY_ORDER,
    RING_SIZE_MAX, RING_SIZE_MIN, VALID_CARATS, VALID_CARATS_CHAIN,
    VALID_CATEGORIES, VALID_COLORS, VALID_GOLDS,
    product_publish_ready, validate_password, validate_product_fields,
    validate_submission_fields, validate_username,
    sort_golds,
)
from diamond_calculator.application.cart import (
    add_cart_item,
    cart_item_detail_payload,
    cart_item_payload,
    checkout_cart,
    enrich_cart_items_for_template,
    get_cart_item,
    update_cart_item,
)
from diamond_calculator.application.order_search import (
    STATUS_LABELS_ZH, apply_submission_search, submissions_by_status,
)
from diamond_calculator.filters import resolve_style_image_url, submission_summary
from diamond_calculator.repository.models import (
    CartItem, FavoriteItem, InviteCode, Product, ProductImage, ProductVariant,
    Submission, User, UserNotification, db,
)

bp = Blueprint('main', __name__)

NOTIFY_RECENT_LIMIT = 8
ORDER_STATUSES = ('pending', 'confirmed', 'processing', 'completed', 'shipped', 'cancelled')


def _status_notification(sub, new_status, reason=''):
    label = STATUS_LABELS_ZH.get(new_status, new_status)
    message = f'訂單狀態已更新為：{label}'
    if new_status == 'cancelled' and reason:
        message += f'。原因：{reason}'
    return UserNotification(
        user_id=sub.user_id,
        kind='status_changed',
        message=message,
        order_id=sub.id,
        order_summary=submission_summary(
            sub.category, sub.style_type, sub.id, product=sub.product,
        ),
    )


def _shared_config_context(token):
    try:
        config = decode_config(token)
    except ValueError:
        abort(404)
    quote = build_shop_quote(config)
    if not quote.get('ready'):
        abort(404)
    try:
        product_id = int(config.get('type'))
    except (TypeError, ValueError):
        abort(404)
    product = db.session.get(Product, product_id)
    if not product or not product.is_published:
        abort(404)
    image_path = resolve_style_image_url(
        config.get('category'), config.get('type'), config.get('gold'),
        config.get('color'), product=product,
    )
    return {
        'config': config,
        'quote': quote,
        'product': product,
        'image_url': url_for('static', filename=image_path) if image_path else None,
    }


def _submission_config(sub):
    return {
        'category': sub.category,
        'type': sub.style_type,
        'gold': sub.gold_purity,
        'color': sub.color,
        'carat': sub.carat,
        'ringSize': sub.ring_size,
        'engravingBand': sub.engraving_band or '',
        'engravingGirdle': sub.engraving_girdle or '',
        'lengthCm': sub.chain_length_cm if sub.category in ('chain', 'bracelet') else None,
        'includeChain': sub.include_chain,
        'chainProductId': sub.chain_product_id,
        'chainGold': sub.chain_gold,
        'chainColor': sub.chain_color,
        'chainLength': sub.chain_length_cm if sub.include_chain else None,
        'diamondKind': sub.diamond_kind or 'white',
        'fancyColor': sub.fancy_color,
        'stoneCount': sub.stone_count,
        'diamondShape': sub.diamond_shape or 'round',
    }


def _notify_time(dt):
    if not dt:
        return ''
    local = dt + timedelta(hours=8)
    now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=8)
    if local.date() == now.date():
        return local.strftime('%H:%M')
    if local.date() == (now - timedelta(days=1)).date():
        return local.strftime('%H:%M')
    return local.strftime('%Y-%m-%d %H:%M')


def _notification_payload(note, show_unread=None):
    unread = (not note.is_read) if show_unread is None else show_unread
    return {
        'id': note.id,
        'kind': note.kind,
        'title': note.order_summary or '系統通知',
        'message': note.message,
        'time': _notify_time(note.created_at),
        'unread': unread,
    }


def _group_notifications(notes):
    now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=8)
    today = now.date()
    yesterday = today - timedelta(days=1)
    order = []
    buckets = {}
    for note in notes:
        d = (note.created_at + timedelta(hours=8)).date() if note.created_at else today
        if d == today:
            key = 'today'
        elif d == yesterday:
            key = 'yesterday'
        else:
            key = d.isoformat()
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(note)
    return [(key, buckets[key]) for key in order]


def _unread_count(user_id):
    return UserNotification.query.filter_by(user_id=user_id, is_read=False).count()


@bp.route('/health')
def health():
    try:
        db.session.execute(text('SELECT 1'))
        return jsonify({'status': 'ok', 'db': 'ok'})
    except Exception:
        db.session.rollback()
        return jsonify({'status': 'degraded', 'db': 'error'}), 503


@bp.route('/api/notifications/recent')
@login_required
def api_notifications_recent():
    notes = UserNotification.query.filter_by(user_id=current_user.id) \
        .order_by(UserNotification.created_at.desc()) \
        .limit(NOTIFY_RECENT_LIMIT).all()
    return jsonify({
        'notifications': [_notification_payload(n) for n in notes],
        'unread_count': _unread_count(current_user.id),
    })


@bp.route('/api/prices')
def api_prices():
    raw, source = get_metal_prices()
    per_gram = {gold: raw[METAL_SYMBOL[gold]] * PURITY_MULTIPLIER[gold]
                for gold in VALID_GOLDS}
    meta = get_price_metadata()
    return jsonify({
        'diamond': DIAMOND_PRICE,
        'shopDiamondCarats': sorted(SHOP_DIAMOND_CARATS),
        'perGram': per_gram,
        'source': source,
        'lastUpdated': meta.get('bot_posted_at'),
        'bankSell': meta.get('bank_sell'),
        'laborFee': LABOR_FEE,
        'chinToGrams': CHIN_TO_GRAMS,
        'taxRate': TAX_RATE,
        'ringSizeMin': RING_SIZE_MIN,
        'ringSizeMax': RING_SIZE_MAX,
        'ringSizeReference': RING_SIZE_REFERENCE,
        'diamondOptions': diamond_options_payload(),
    })


@bp.route('/api/quote', methods=['POST'])
@limiter.limit('120 per minute')
def api_quote():
    data = request.get_json(silent=True) or {}
    preview = (
        request.args.get('preview') == '1'
        and current_user.is_authenticated
        and current_user.role == 'admin'
    )
    return jsonify(build_shop_quote(data, require_published=not preview))


@bp.route('/api/catalog')
def api_catalog():
    """Published listings grouped by category, for the shop frontend.

    Replaces the old hardcoded CATEGORY_STYLES/STYLE_NAMES/WEIGHT_TABLE
    catalog data with the admin-managed Product/ProductVariant/ProductImage
    rows. Each listing only advertises the metals/carats/colors it actually
    has variants/images for (per-listing catalog, not a blanket category rule).
    """
    from sqlalchemy.orm import joinedload
    preview = request.args.get('preview') == '1'
    if preview and (
        not current_user.is_authenticated or current_user.role != 'admin'
    ):
        return jsonify({'message': 'Unauthorized'}), 403
    query = Product.query.options(
        joinedload(Product.variants), joinedload(Product.images),
    )
    if not preview:
        query = query.filter_by(is_published=True)
    products = query.order_by(Product.category, Product.sort_order, Product.id).all()
    categories = {}
    for p in products:
        golds = sort_golds({v.gold for v in p.variants})
        carats = sorted({v.carat for v in p.variants})
        weights = {}
        manual_prices = {}
        for v in p.variants:
            weights.setdefault(v.gold, {})[v.carat] = v.weight_chin
            if v.manual_price_twd is not None:
                manual_prices.setdefault(v.gold, {})[v.carat] = v.manual_price_twd
        images_by_color = p.images_by_color()
        images = {
            color: [url_for('static', filename=path) for path in paths]
            for color, paths in images_by_color.items()
        }

        categories.setdefault(p.category, []).append({
            'id': p.id,
            'nameZh': p.name_zh,
            'nameEn': p.name_en,
            'descriptionZh': p.description_zh,
            'descriptionEn': p.description_en,
            'defaultColor': p.default_color,
            'golds': golds,
            'carats': carats,
            'colors': sorted(images.keys()),
            'images': images,
            'weights': weights,
            'manualPrices': manual_prices,
            'draft': not p.is_published,
        })

    return jsonify({'categories': categories})


@bp.route('/gold-price')
@login_required
def gold_price():
    quote = get_bot_gold_display()
    raw, _ = get_metal_prices()
    alloy_rates = {
        gold: raw[METAL_SYMBOL[gold]] * PURITY_MULTIPLIER[gold]
        for gold in ('9k', '14k', '18k')
    }
    return render_template(
        'gold/price/index.html',
        quote=quote,
        alloy_rates=alloy_rates,
    )


def _gold_quote_payload():
    quote = get_bot_gold_display()
    raw, _ = get_metal_prices()
    alloy_rates = {
        gold: raw[METAL_SYMBOL[gold]] * PURITY_MULTIPLIER[gold]
        for gold in ('9k', '14k', '18k')
    }
    return {
        'success': quote['available'] and quote['source'] != 'fallback',
        'quote': quote,
        'alloyRates': alloy_rates,
    }


@bp.route('/api/gold/refresh', methods=['POST'])
@login_required
@limiter.limit('5 per minute')
def refresh_gold_prices():
    refreshed = fetch_taiwan_bank_prices()
    payload = _gold_quote_payload()
    quote = payload['quote']
    payload['refreshed'] = refreshed and quote['source'] == 'bot'

    if not quote['available']:
        return jsonify({
            **payload,
            'message': 'could not fetch latest BOT quote; no price available',
        }), 502

    if quote['source'] == 'manual':
        payload['refreshed'] = True
        return jsonify(payload)

    if not payload['refreshed'] and quote['source'] in ('bot', 'cached'):
        return jsonify({
            **payload,
            'message': 'could not fetch latest BOT quote; showing last known prices',
        })

    return jsonify(payload)


@bp.route('/')
def home():
    return render_template('marketing/home/index.html')


@bp.route('/robots.txt')
def robots_txt():
    # This is an internal store-ordering tool, not a public marketing site -
    # keep it out of search engines entirely.
    return Response('User-agent: *\nDisallow: /\n', mimetype='text/plain')


@bp.route('/favicon.ico')
def favicon():
    return redirect(url_for('static', filename='favicon.svg'))


@bp.route('/sw.js')
def service_worker():
    response = send_from_directory(
        current_app.static_folder,
        'sw.js',
        mimetype='application/javascript',
    )
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-cache'
    return response


@bp.route('/styles')
def styles():
    return redirect(url_for('main.calculator'))


@bp.route('/calculator')
def calculator():
    preview_mode = (
        request.args.get('preview') == '1'
        and current_user.is_authenticated
        and current_user.role == 'admin'
    )
    shop_mode = 'preview' if preview_mode else (
        'order' if current_user.is_authenticated else 'guest'
    )
    edit_id = request.args.get('edit_id')
    edit_sub = None
    prefill_config = None
    if edit_id:
        if not current_user.is_authenticated:
            return redirect(url_for('main.login', next=request.full_path))
        edit_sub = db.session.get(Submission, edit_id)
        if not edit_sub or edit_sub.user_id != current_user.id or edit_sub.status != 'pending':
            flash("無法編輯該訂單 (Invalid or unauthorized order).")
            return redirect(url_for('main.history'))
    reorder_id = request.args.get('reorder', type=int)
    favorite_id = request.args.get('favorite', type=int)
    if reorder_id or favorite_id:
        if not current_user.is_authenticated:
            return redirect(url_for('main.login', next=request.full_path))
        if reorder_id:
            source = Submission.query.filter_by(
                id=reorder_id, user_id=current_user.id,
            ).first()
            if not source:
                abort(404)
            if not source.product or not source.product.is_published:
                flash('此款式已下架，請選擇其他款式。', 'warning')
                return redirect(url_for('main.calculator'))
            prefill_config = _submission_config(source)
        else:
            favorite = get_favorite(current_user.id, favorite_id)
            if not favorite:
                abort(404)
            if not favorite.product or not favorite.product.is_published:
                flash('此款式已下架，請選擇其他款式。', 'warning')
                return redirect(url_for('main.favorites'))
            prefill_config = favorite_config(favorite)
    return render_template(
        'shop/calculator/index.html',
        shop_mode=shop_mode,
        preview_mode=preview_mode,
        edit_sub=edit_sub,
        prefill_config=prefill_config,
        ring_size_measure_chart=RING_SIZE_MEASURE_CHART,
    )


@bp.route('/quote-sheet')
@limiter.limit('60 per minute')
def quote_sheet():
    token = request.args.get('config', '', type=str)
    context = _shared_config_context(token)
    return render_template(
        'share/quote/index.html',
        **context,
        store_name=current_user.store_name if current_user.is_authenticated else '',
        generated_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=8),
    )


@bp.route('/s/<token>')
@limiter.limit('120 per minute')
def shared_summary(token):
    return render_template('share/summary/index.html', **_shared_config_context(token))


@bp.route('/cart')
@login_required
def cart():
    items = CartItem.query.filter_by(user_id=current_user.id) \
        .order_by(CartItem.created_at.desc()).all()
    cart_total = sum(i.total_price or 0 for i in items)
    cart_rows = enrich_cart_items_for_template(items)
    return render_template(
        'cart/index.html',
        items=items,
        cart_rows=cart_rows,
        cart_total=cart_total,
        tax_rate=TAX_RATE,
    )


@bp.route('/favorites')
@login_required
def favorites():
    items = FavoriteItem.query.filter_by(user_id=current_user.id) \
        .order_by(FavoriteItem.created_at.desc()).all()
    return render_template(
        'favorites/index.html',
        favorites=[favorite_payload(item) for item in items],
    )


@bp.route('/api/favorites')
@login_required
def api_favorites():
    items = FavoriteItem.query.filter_by(user_id=current_user.id) \
        .order_by(FavoriteItem.created_at.desc()).all()
    return jsonify({
        'success': True,
        'items': [favorite_payload(item) for item in items],
    })


@bp.route('/api/favorites/add', methods=['POST'])
@login_required
@limiter.limit('60 per hour')
def api_favorites_add():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'success': False, 'message': 'invalid JSON'}), 400
    item, error = add_favorite(current_user.id, data)
    if error:
        return jsonify({'success': False, 'message': error}), 400
    return jsonify({'success': True, 'item': favorite_payload(item)})


@bp.route('/api/favorites/<int:item_id>', methods=['DELETE'])
@login_required
def api_favorites_remove(item_id):
    item = get_favorite(current_user.id, item_id)
    if not item:
        return jsonify({'success': False, 'message': 'not found'}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/cart/<int:item_id>/edit')
@login_required
def cart_edit(item_id):
    item = get_cart_item(current_user.id, item_id)
    if not item:
        flash('找不到購物車品項。')
        return redirect(url_for('main.cart'))
    cart_edit_config = json.loads(item.config_json)
    return render_template(
        'shop/calculator/index.html',
        shop_mode='order',
        edit_sub=None,
        cart_edit_item=item,
        cart_edit_config=cart_edit_config,
        ring_size_measure_chart=RING_SIZE_MEASURE_CHART,
    )


@bp.route('/api/cart')
@login_required
def api_cart_list():
    items = CartItem.query.filter_by(user_id=current_user.id) \
        .order_by(CartItem.created_at.desc()).all()
    return jsonify({
        'items': [cart_item_payload(i) for i in items],
        'count': len(items),
        'total': sum(i.total_price or 0 for i in items),
    })


@bp.route('/api/cart/<int:item_id>')
@login_required
def api_cart_detail(item_id):
    item = get_cart_item(current_user.id, item_id)
    if not item:
        return jsonify({'success': False, 'message': 'not found'}), 404
    return jsonify({'success': True, 'item': cart_item_detail_payload(item, TAX_RATE)})


@bp.route('/api/cart/<int:item_id>', methods=['PUT'])
@login_required
@limiter.limit('60 per hour')
def api_cart_update(item_id):
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'success': False, 'message': 'invalid JSON'}), 400
    item, error = update_cart_item(current_user.id, item_id, data)
    if error:
        status = 404 if error == 'not found' else 400
        return jsonify({'success': False, 'message': error}), status
    return jsonify({
        'success': True,
        'item': cart_item_payload(item),
        'count': CartItem.query.filter_by(user_id=current_user.id).count(),
    })


@bp.route('/api/cart/add', methods=['POST'])
@login_required
@limiter.limit('60 per hour')
def api_cart_add():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'success': False, 'message': 'invalid JSON'}), 400
    try:
        item, error = add_cart_item(current_user.id, data)
    except OperationalError:
        db.session.rollback()
        current_app.logger.exception('cart add failed: database error')
        return jsonify({
            'success': False,
            'message': 'database unavailable — run flask db upgrade if cart is newly enabled',
        }), 503
    except Exception:
        db.session.rollback()
        current_app.logger.exception('cart add failed')
        return jsonify({'success': False, 'message': 'internal server error'}), 500
    if error:
        return jsonify({'success': False, 'message': error}), 400
    return jsonify({
        'success': True,
        'item': cart_item_payload(item),
        'count': CartItem.query.filter_by(user_id=current_user.id).count(),
    })


@bp.route('/api/cart/<int:item_id>', methods=['DELETE'])
@login_required
def api_cart_remove(item_id):
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not item:
        return jsonify({'success': False, 'message': 'not found'}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({
        'success': True,
        'count': CartItem.query.filter_by(user_id=current_user.id).count(),
    })


@bp.route('/api/cart/checkout', methods=['POST'])
@login_required
@limiter.limit('20 per hour')
def api_cart_checkout():
    body = request.get_json(silent=True) or {}
    item_ids = body.get('item_ids')
    if item_ids is not None:
        if not isinstance(item_ids, list):
            return jsonify({'success': False, 'message': 'invalid item_ids'}), 400
        try:
            item_ids = [int(i) for i in item_ids]
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': 'invalid item_ids'}), 400
    created_ids, error = checkout_cart(current_user.id, item_ids=item_ids)
    if error:
        return jsonify({'success': False, 'message': error}), 400
    return jsonify({'success': True, 'order_ids': created_ids, 'count': len(created_ids)})







@bp.route('/success')
@login_required
def success():
    return render_template('marketing/success/index.html')


@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('20 per 5 minutes')
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username and is_locked_out(username):
            flash('登入失敗次數過多，請 5 分鐘後再試。 (Too many failed attempts, try again in 5 minutes.)')
            return render_template('auth/index.html', auth_mode='login', invite_required=invite_required())

        user = User.query.filter_by(username=username).first()
        if user and not getattr(user, 'is_active', True):
            flash('此帳號已停用，請聯絡管理員。 (This account has been disabled.)')
            return render_template('auth/index.html', auth_mode='login', invite_required=invite_required())
        if user and check_password_hash(user.password_hash, password):
            record_login_success(username)
            session.clear()
            login_user(user)
            user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.session.commit()
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                return redirect(next_page)
            if user.role == 'admin':
                return redirect(url_for('main.admin_dashboard'))
            return redirect(url_for('main.calculator'))
        else:
            if username:
                record_login_failure(username)
            flash('Invalid username or password')
    return render_template('auth/index.html', auth_mode='login', invite_required=invite_required())


@bp.route('/register', methods=['GET', 'POST'])
@limiter.limit('10 per hour')
def register():
    if request.method == 'POST':
        if is_register_locked_out():
            flash('註冊嘗試次數過多，請 10 分鐘後再試。 (Too many registration attempts, try again in 10 minutes.)')
            return render_template('auth/index.html', auth_mode='register', invite_required=invite_required())

        store_name = (request.form.get('store_name') or '').strip()
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        invite_code = (request.form.get('invite_code') or '').strip()

        invite_error = validate_invite_code(invite_code)
        if invite_error:
            record_register_failure()
            flash(invite_error)
            return render_template('auth/index.html', auth_mode='register', invite_required=invite_required())

        username_error = validate_username(username)
        password_error = validate_password(password, username=username)
        if username_error or password_error:
            record_register_failure()
            flash(username_error or password_error)
            return render_template('auth/index.html', auth_mode='register', invite_required=invite_required())

        if not store_name:
            record_register_failure()
            flash('店家名稱為必填欄位。 (Store name is required.)')
            return render_template('auth/index.html', auth_mode='register', invite_required=invite_required())

        if User.query.filter_by(username=username).first():
            record_register_failure()
            flash('該帳號已被使用，請選擇其他帳號。')
            return redirect(url_for('main.register'))

        new_user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role='provider',
            store_name=store_name
        )
        db.session.add(new_user)
        try:
            db.session.flush()
            consume_invite_code(invite_code, new_user.id)
            db.session.commit()
            record_register_success()
            flash('註冊成功！請登入。', 'success')
            return redirect(url_for('main.login'))
        except Exception as exc:
            db.session.rollback()
            record_register_failure()
            from flask import current_app
            current_app.logger.exception('Registration failed for %s: %s', username, exc)
            flash('發生錯誤，請稍後再試。')

    return render_template('auth/index.html', auth_mode='register', invite_required=invite_required())


@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    stats = {
        'total': Submission.query.filter_by(user_id=current_user.id).count(),
        'pending': Submission.query.filter_by(user_id=current_user.id, status='pending').count(),
    }
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_store':
            new_name = (request.form.get('store_name') or '').strip()
            if new_name:
                current_user.store_name = new_name
                db.session.commit()
                flash('店家名稱已更新。 (Store name updated.)', 'success')
        elif action == 'change_password':
            current_pw = request.form.get('current_password') or ''
            new_pw = request.form.get('new_password') or ''
            confirm_pw = request.form.get('confirm_password') or ''
            password_error = validate_password(new_pw, username=current_user.username)
            if not check_password_hash(current_user.password_hash, current_pw):
                flash('目前密碼不正確。 (Current password is incorrect.)')
            elif password_error:
                flash(password_error)
            elif new_pw != confirm_pw:
                flash('新密碼與確認密碼不一致。 (Passwords do not match.)')
            else:
                current_user.password_hash = generate_password_hash(new_pw)
                db.session.commit()
                flash('密碼已更新。 (Password updated.)', 'success')
        return redirect(url_for('main.profile'))
    return render_template('profile/index.html', stats=stats)


@bp.route('/submit', methods=['POST'])
@login_required
@limiter.limit('30 per hour')
def submit():
    from flask import current_app
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'status': 'error', 'message': 'invalid JSON'}), 400
    cleaned, error = validate_submission_fields(data)
    if error:
        return jsonify({'status': 'error', 'message': error}), 400

    pricing = compute_order_pricing(cleaned, partial=False)
    if not pricing.ready:
        return jsonify({'status': 'error', 'message': pricing.error or 'pricing error'}), 400

    variant = pricing.variant
    submission = Submission(
        user_id=current_user.id,
        product_id=variant.product_id,
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
    try:
        db.session.add(submission)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Submit failed for user %s: %s', current_user.id, exc)
        return jsonify({'status': 'error', 'message': 'save failed'}), 400
    return jsonify({'status': 'success', 'message': 'Selection confirmed and saved.',
                    'total_price': submission.total_price})


@bp.route('/history')
@login_required
def history():
    search_q = request.args.get('q', '', type=str).strip()
    active_tab = request.args.get('tab', 'incomplete', type=str)
    if active_tab not in ('incomplete', 'complete', 'cancelled'):
        active_tab = 'incomplete'
    query = Submission.query.filter_by(user_id=current_user.id)
    query = apply_submission_search(query, search_q, admin=False)
    incomplete_subs, complete_subs, cancelled_subs = submissions_by_status(query)
    return render_template(
        'orders/history/index.html',
        incomplete_subs=incomplete_subs,
        complete_subs=complete_subs,
        cancelled_subs=cancelled_subs,
        active_tab=active_tab,
        tax_rate=TAX_RATE,
        search_q=search_q,
    )


@bp.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('main.calculator'))
    search_q = request.args.get('q', '', type=str).strip()
    active_tab = request.args.get('tab', 'incomplete', type=str)
    if active_tab not in ('incomplete', 'complete'):
        active_tab = 'incomplete'
    query = Submission.query
    query = apply_submission_search(query, search_q, admin=True)
    incomplete_subs, complete_subs, _cancelled_subs = submissions_by_status(query)
    all_total = db.session.query(func.sum(Submission.total_price)).scalar() or 0
    completed_total_all = db.session.query(func.sum(Submission.total_price)) \
        .filter(Submission.status.in_(['completed', 'shipped'])).scalar() or 0
    return render_template(
        'admin/orders/index.html',
        incomplete_subs=incomplete_subs,
        complete_subs=complete_subs,
        active_tab=active_tab,
        admin_section='orders',
        all_total=all_total,
        completed_total_all=completed_total_all,
        tax_rate=TAX_RATE,
        search_q=search_q,
    )


@bp.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('main.calculator'))
    month = request.args.get('month', '', type=str).strip()
    granularity = request.args.get('granularity', '', type=str).strip().lower()
    period = request.args.get('period', '', type=str).strip()
    start = request.args.get('start', '', type=str).strip()
    end = request.args.get('end', '', type=str).strip()
    return render_template(
        'admin/dashboard/index.html',
        dashboard=build_dashboard_data(
            month=month or None,
            granularity=granularity or None,
            period=period or None,
            start=start or None,
            end=end or None,
        ),
        admin_section='dashboard',
    )


@bp.route('/admin/dashboard/export')
@login_required
def admin_dashboard_export():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    month = request.args.get('month', '', type=str).strip()
    granularity = request.args.get('granularity', '', type=str).strip().lower()
    period = request.args.get('period', '', type=str).strip()
    start = request.args.get('start', '', type=str).strip()
    end = request.args.get('end', '', type=str).strip()
    if month:
        try:
            datetime.strptime(month, '%Y-%m')
        except ValueError:
            return jsonify({'success': False, 'message': 'invalid month'}), 400
    if granularity == 'week' and period:
        if not re.fullmatch(r'\d{4}-W\d{2}', period):
            return jsonify({'success': False, 'message': 'invalid week'}), 400
    if granularity == 'day':
        for value, label in ((start, 'start'), (end, 'end')):
            if value:
                try:
                    datetime.strptime(value, '%Y-%m-%d')
                except ValueError:
                    return jsonify({'success': False, 'message': f'invalid {label} date'}), 400
    csv_body, slug = dashboard_csv(
        month=month or None,
        granularity=granularity or None,
        period=period or None,
        start=start or None,
        end=end or None,
    )
    filename = f'orders-{slug}.csv'
    return Response(
        csv_body,
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@bp.route('/admin/accounts')
@login_required
def admin_accounts():
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('main.calculator'))
    users = User.query.order_by(User.role.desc(), User.username).all()
    return render_template('admin/accounts/index.html', users=users, admin_section='accounts')


@bp.route('/admin/accounts/<int:user_id>/reset-password', methods=['POST'])
@login_required
def admin_reset_password(user_id):
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('main.calculator'))

    user = db.session.get(User, user_id)
    if user is None:
        flash('找不到該帳號。')
        return redirect(url_for('main.admin_accounts'))

    new_pw = request.form.get('new_password') or ''
    password_error = validate_password(new_pw, username=user.username)
    if password_error:
        flash(password_error)
        return redirect(url_for('main.admin_accounts'))

    user.password_hash = generate_password_hash(new_pw)
    db.session.commit()
    log_admin_action('reset_password', target_user=user.username, target_user_id=user.id)
    flash(f'已重設帳號「{user.username}」的密碼。', 'success')
    return redirect(url_for('main.admin_accounts'))


@bp.route('/admin/accounts/<int:user_id>/toggle-active', methods=['POST'])
@login_required
def admin_toggle_user_active(user_id):
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('main.calculator'))
    user = db.session.get(User, user_id)
    if user is None or user.id == current_user.id:
        flash('無法變更此帳號狀態。')
        return redirect(url_for('main.admin_accounts'))
    user.is_active = not getattr(user, 'is_active', True)
    db.session.commit()
    log_admin_action('toggle_user_active', target_user=user.username, active=user.is_active)
    flash(f'帳號「{user.username}」已{"啟用" if user.is_active else "停用"}。', 'success')
    return redirect(url_for('main.admin_accounts'))


@bp.route('/admin/accounts/<int:user_id>/clear-lockout', methods=['POST'])
@login_required
def admin_clear_lockout(user_id):
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('main.calculator'))
    user = db.session.get(User, user_id)
    if user is None:
        flash('找不到該帳號。')
        return redirect(url_for('main.admin_accounts'))
    clear_login_lockout(user.username)
    flash(f'已清除「{user.username}」的登入鎖定。', 'success')
    return redirect(url_for('main.admin_accounts'))


@bp.route('/admin/accounts/<int:user_id>/delete', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('main.calculator'))

    user = db.session.get(User, user_id)
    if user is None:
        flash('找不到該帳號。')
        return redirect(url_for('main.admin_accounts'))
    if user.id == current_user.id:
        flash('無法刪除目前登入中的帳號。')
        return redirect(url_for('main.admin_accounts'))
    if user.role == 'admin':
        flash('無法刪除管理員帳號。')
        return redirect(url_for('main.admin_accounts'))

    username = user.username
    submission_ids = [s.id for s in Submission.query.filter_by(user_id=user.id).all()]
    UserNotification.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    Submission.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    InviteCode.query.filter_by(used_by_id=user.id).update(
        {InviteCode.used_by_id: None}, synchronize_session=False,
    )
    clear_login_lockout(username)
    db.session.delete(user)
    db.session.commit()
    log_admin_action(
        'delete_user',
        target_user=username,
        target_user_id=user_id,
        submission_ids=submission_ids,
    )
    flash(f'已刪除帳號「{username}」。', 'success')
    return redirect(url_for('main.admin_accounts'))


@bp.route('/admin/invites')
@login_required
def admin_invites():
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('main.calculator'))
    invites = InviteCode.query.order_by(InviteCode.created_at.desc()).all()
    return render_template('admin/invites/index.html', invites=invites, admin_section='invites')


@bp.route('/admin/invites/create', methods=['POST'])
@login_required
@limiter.limit('20 per hour')
def admin_invite_create():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    max_uses = request.form.get('max_uses', type=int) or 1
    max_uses = max(1, min(max_uses, 100))
    code = generate_invite_code()
    invite = InviteCode(
        code=code,
        created_by_id=current_user.id,
        max_uses=max_uses,
        is_active=True,
    )
    db.session.add(invite)
    db.session.commit()
    log_admin_action('create_invite', code=code, max_uses=max_uses)
    flash(f'已建立邀請碼：{code}', 'success')
    return redirect(url_for('main.admin_invites'))


@bp.route('/admin/invites/<int:invite_id>/revoke', methods=['POST'])
@login_required
def admin_invite_revoke(invite_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    invite = InviteCode.query.get_or_404(invite_id)
    invite.is_active = False
    db.session.commit()
    log_admin_action('revoke_invite', code=invite.code)
    flash('邀請碼已停用。', 'success')
    return redirect(url_for('main.admin_invites'))


@bp.route('/admin/invites/<int:invite_id>/delete', methods=['POST'])
@login_required
def admin_invite_delete(invite_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    invite = InviteCode.query.get_or_404(invite_id)
    code = invite.code
    db.session.delete(invite)
    db.session.commit()
    log_admin_action('delete_invite', code=code)
    flash('邀請碼已刪除。已用此碼註冊的帳戶不受影響。', 'success')
    return redirect(url_for('main.admin_invites'))


@bp.route('/admin/products/<int:id>/duplicate', methods=['POST'])
@login_required
def admin_product_duplicate(id):
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('main.calculator'))
    source = Product.query.get_or_404(id)
    clone = Product(
        category=source.category,
        name_zh=f'{source.name_zh} (複製)',
        name_en=source.name_en,
        description_zh=source.description_zh,
        description_en=source.description_en,
        default_color=source.default_color,
        is_published=False,
        sort_order=source.sort_order,
        created_by_id=current_user.id,
    )
    db.session.add(clone)
    db.session.flush()
    for v in source.variants:
        db.session.add(ProductVariant(
            product_id=clone.id, gold=v.gold, carat=v.carat,
            weight_chin=v.weight_chin, manual_price_twd=v.manual_price_twd,
        ))
    copied_paths = []
    try:
        for image in source.images:
            path = copy_product_image(
                image.file_path, clone.id, image.color,
            )
            copied_paths.append(path)
            db.session.add(ProductImage(
                product_id=clone.id,
                color=image.color,
                file_path=path,
                sort_order=image.sort_order,
            ))
        db.session.commit()
    except (UploadError, OSError) as error:
        db.session.rollback()
        for path in copied_paths:
            delete_product_image(path)
        flash(f'複製失敗：{error}')
        return redirect(url_for('main.admin_products'))
    log_admin_action('duplicate_product', source_id=source.id, new_id=clone.id)
    flash(f'已複製商品為草稿「{clone.name_zh}」。', 'success')
    return redirect(url_for('main.admin_product_edit', id=clone.id))


def _apply_product_images(product, cleaned, files):
    """Deletes removed images and saves newly-uploaded ones. Call after product.id exists.

    Returns the list of newly-saved file paths (for rollback if a later
    upload in the same request fails validation).
    """
    for img_id in cleaned.get('remove_image_ids', ()):
        existing = db.session.get(ProductImage, img_id)
        if existing and existing.product_id == product.id:
            delete_product_image(existing.file_path)
            db.session.delete(existing)

    ordered_ids = cleaned.get('image_order_ids', ())
    if ordered_ids:
        images_by_id = {img.id: img for img in product.images}
        color_positions = {}
        for img_id in ordered_ids:
            image = images_by_id.get(img_id)
            if not image or image.product_id != product.id:
                continue
            image.sort_order = color_positions.get(image.color, 0)
            color_positions[image.color] = image.sort_order + 1

    new_paths = []
    try:
        for color, file_list in cleaned.get('uploads_by_color', {}).items():
            next_sort = max(
                (img.sort_order for img in product.images if img.color == color),
                default=-1,
            ) + 1
            for file_storage in file_list:
                new_path = save_product_image(product.id, color, file_storage)
                new_paths.append(new_path)
                db.session.add(ProductImage(
                    product_id=product.id,
                    color=color,
                    file_path=new_path,
                    sort_order=next_sort,
                ))
                next_sort += 1
    except UploadError:
        for path in new_paths:
            delete_product_image(path)
        raise
    return new_paths


def _replace_product_variants(product, variants):
    for old in list(product.variants):
        db.session.delete(old)
    # Flush the deletes before inserting replacements — otherwise SQLAlchemy
    # may order the new inserts before the old deletes within the same
    # flush and trip the (product_id, gold, carat) unique constraint on any
    # combo that's kept across the edit.
    db.session.flush()
    for v in variants:
        db.session.add(ProductVariant(
            product_id=product.id, gold=v['gold'], carat=v['carat'],
            weight_chin=v['weight_chin'], manual_price_twd=v['manual_price_twd'],
        ))


def _product_form_context(product=None):
    return {
        'categories': CATEGORY_DISPLAY_ORDER,
        'golds': sort_golds(VALID_GOLDS),
        'carats': sorted(VALID_CARATS),
        'chain_carats': sorted(VALID_CARATS_CHAIN),
        'colors': sorted(VALID_COLORS),
        'product': product,
    }


def _product_error_payload(error):
    """Group validation messages for inline admin-form display."""
    errors = {'form': []}
    for message in (error or '').split('; '):
        field = 'form'
        if 'name_zh' in message:
            field = 'name_zh'
        elif 'category' in message:
            field = 'category'
        elif 'description' in message:
            field = 'description_zh'
        elif 'default color' in message or 'default_color' in message:
            field = 'default_color'
        elif 'variant' in message or 'weight' in message or 'metal' in message or 'carat' in message:
            field = 'variants'
        elif 'image' in message:
            field = 'images'
        errors.setdefault(field, []).append(message)
    return {key: messages for key, messages in errors.items() if messages}


@bp.route('/admin/products')
@login_required
def admin_products():
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('main.calculator'))
    products = Product.query.order_by(Product.category, Product.sort_order, Product.id).all()
    ctx = _product_form_context(None)
    ctx.update(
        products=products,
        publish_readiness={p.id: product_publish_ready(p) for p in products},
        admin_section='products',
        edit_mode=False,
    )
    return render_template('admin/products/index.html', **ctx)


@bp.route('/admin/products/reorder', methods=['POST'])
@login_required
def admin_products_reorder():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    data = request.get_json(silent=True) or {}
    category = data.get('category')
    ids = data.get('ids')
    if category not in VALID_CATEGORIES or not isinstance(ids, list):
        return jsonify({'success': False, 'message': 'Invalid reorder data'}), 400
    try:
        product_ids = [int(product_id) for product_id in ids]
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid product ids'}), 400
    products = Product.query.filter_by(category=category).all()
    by_id = {product.id: product for product in products}
    if set(product_ids) != set(by_id):
        return jsonify({'success': False, 'message': 'Product list changed; reload and retry'}), 409
    for sort_order, product_id in enumerate(product_ids):
        by_id[product_id].sort_order = sort_order
    db.session.commit()
    log_admin_action('reorder_products', category=category, product_ids=product_ids)
    return jsonify({'success': True})


@bp.route('/admin/products/new')
@login_required
def admin_product_new():
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('main.calculator'))
    ctx = _product_form_context(None)
    ctx.update(admin_section='products', edit_mode=True)
    return render_template('admin/products/form.html', **ctx)


@bp.route('/admin/products', methods=['POST'])
@login_required
def admin_product_create():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    cleaned, error = validate_product_fields(request.form, request.files)
    if error:
        return jsonify({
            'success': False,
            'message': '請修正表單錯誤。',
            'errors': _product_error_payload(error),
        }), 400

    next_order = (
        db.session.query(func.max(Product.sort_order))
        .filter(Product.category == cleaned['category'])
        .scalar()
    )

    product = Product(
        category=cleaned['category'],
        name_zh=cleaned['name_zh'],
        name_en=cleaned['name_en'],
        description_zh=cleaned['description_zh'],
        description_en=cleaned['description_en'],
        default_color=cleaned['default_color'],
        is_published=cleaned['is_published'],
        first_published_at=(
            datetime.now(timezone.utc).replace(tzinfo=None)
            if cleaned['is_published'] else None
        ),
        sort_order=(next_order if next_order is not None else -1) + 1,
        created_by_id=current_user.id,
    )
    db.session.add(product)
    db.session.flush()  # assign product.id before saving variants/images

    for v in cleaned['variants']:
        db.session.add(ProductVariant(
            product_id=product.id, gold=v['gold'], carat=v['carat'],
            weight_chin=v['weight_chin'], manual_price_twd=v['manual_price_twd'],
        ))
    saved_paths = []
    try:
        for color, file_list in cleaned.get('uploads_by_color', {}).items():
            for sort_order, file_storage in enumerate(file_list):
                path = save_product_image(product.id, color, file_storage)
                saved_paths.append(path)
                db.session.add(ProductImage(
                    product_id=product.id,
                    color=color,
                    file_path=path,
                    sort_order=sort_order,
                ))
    except UploadError as e:
        db.session.rollback()
        for path in saved_paths:
            delete_product_image(path)
        return jsonify({
            'success': False, 'message': str(e),
            'errors': {'images': [str(e)]},
        }), 400

    db.session.commit()
    log_admin_action('create_product', product_id=product.id, name=product.name_zh)
    return jsonify({
        'success': True,
        'redirect': url_for('main.admin_products'),
    })


@bp.route('/admin/products/<int:id>/edit')
@login_required
def admin_product_edit(id):
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('main.calculator'))
    product = Product.query.get_or_404(id)
    ctx = _product_form_context(product)
    ctx.update(admin_section='products', edit_mode=True)
    return render_template('admin/products/form.html', **ctx)


@bp.route('/admin/products/<int:id>', methods=['POST'])
@login_required
def admin_product_update(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    product = Product.query.get_or_404(id)
    existing_image_ids_by_color = {}
    for img in product.images:
        existing_image_ids_by_color.setdefault(img.color, []).append(img.id)
    cleaned, error = validate_product_fields(
        request.form, request.files, existing_image_ids_by_color=existing_image_ids_by_color,
    )
    if error:
        return jsonify({
            'success': False,
            'message': '請修正表單錯誤。',
            'errors': _product_error_payload(error),
        }), 400

    product.category = cleaned['category']
    product.name_zh = cleaned['name_zh']
    product.name_en = cleaned['name_en']
    product.description_zh = cleaned['description_zh']
    product.description_en = cleaned['description_en']
    product.default_color = cleaned['default_color']
    product.is_published = cleaned['is_published']
    if product.is_published and product.first_published_at is None:
        product.first_published_at = datetime.now(timezone.utc).replace(tzinfo=None)

    _replace_product_variants(product, cleaned['variants'])
    try:
        new_paths = _apply_product_images(product, cleaned, request.files)
    except UploadError as e:
        db.session.rollback()
        return jsonify({
            'success': False, 'message': str(e),
            'errors': {'images': [str(e)]},
        }), 400

    db.session.commit()
    log_admin_action('update_product', product_id=product.id, name=product.name_zh)
    return jsonify({
        'success': True,
        'redirect': url_for('main.admin_products'),
    })


@bp.route('/admin/products/<int:id>/publish', methods=['POST'])
@login_required
def admin_product_publish(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    product = Product.query.get_or_404(id)
    ready, message = product_publish_ready(product)
    if not ready:
        return jsonify({'success': False, 'message': message}), 400
    product.is_published = True
    if product.first_published_at is None:
        product.first_published_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    log_admin_action('publish_product', product_id=id)
    return jsonify({'success': True})


@bp.route('/admin/products/<int:id>/unpublish', methods=['POST'])
@login_required
def admin_product_unpublish(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    product = Product.query.get_or_404(id)
    product.is_published = False
    db.session.commit()
    log_admin_action('unpublish_product', product_id=id)
    return jsonify({'success': True})


@bp.route('/admin/products/<int:id>/delete', methods=['POST'])
@login_required
def admin_product_delete(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    product = Product.query.get_or_404(id)

    if Submission.query.filter_by(product_id=product.id).first() is not None:
        # Referenced by order history — force-unpublish instead of a hard
        # delete so past orders keep rendering correctly.
        product.is_published = False
        db.session.commit()
        log_admin_action('unpublish_product_blocked_delete', product_id=id)
        return jsonify({
            'success': True, 'deleted': False,
            'message': '此商品已有訂單紀錄，無法刪除，已自動下架。 (Product has order history; unpublished instead of deleted.)',
        })

    for img in list(product.images):
        delete_product_image(img.file_path)
    db.session.delete(product)
    db.session.commit()
    log_admin_action('delete_product', product_id=id)
    return jsonify({'success': True, 'deleted': True})


@bp.route('/admin/update_status/<int:id>', methods=['POST'])
@login_required
def admin_update_status(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    sub = Submission.query.get_or_404(id)
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'success': False, 'message': 'invalid JSON'}), 400
    new_status = data.get('status')

    if new_status in ORDER_STATUSES:
        reason = (data.get('reason') or '').strip()
        if new_status == 'cancelled' and not reason:
            return jsonify({'success': False, 'message': 'a cancellation reason is required'}), 400
        if len(reason) > ADMIN_DELETE_MSG_MAX:
            return jsonify({'success': False, 'message': 'reason too long'}), 400
        old_status = sub.status
        sub.status = new_status
        sub.cancel_reason = reason if new_status == 'cancelled' else None
        if old_status != new_status:
            db.session.add(_status_notification(sub, new_status, reason))
        db.session.commit()
        log_admin_action('update_status', submission_id=sub.id, status=new_status)
        return jsonify({'success': True})

    return jsonify({'success': False, 'message': 'Invalid status'}), 400


ADMIN_DELETE_MSG_MAX = 500


@bp.route('/admin/bulk-update-status', methods=['POST'])
@login_required
def admin_bulk_update_status():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'success': False, 'message': 'invalid JSON'}), 400

    ids = data.get('ids') or []
    new_status = data.get('status', '')
    if not ids:
        return jsonify({'success': False, 'message': 'no ids provided'}), 400
    if new_status not in ORDER_STATUSES:
        return jsonify({'success': False, 'message': 'invalid status'}), 400
    reason = (data.get('reason') or '').strip()
    if new_status == 'cancelled' and not reason:
        return jsonify({'success': False, 'message': 'a cancellation reason is required'}), 400
    if len(reason) > ADMIN_DELETE_MSG_MAX:
        return jsonify({'success': False, 'message': 'reason too long'}), 400

    updated_ids = []
    for sub_id in ids:
        sub = db.session.get(Submission, sub_id)
        if sub:
            old_status = sub.status
            sub.status = new_status
            sub.cancel_reason = reason if new_status == 'cancelled' else None
            if old_status != new_status:
                db.session.add(_status_notification(sub, new_status, reason))
            updated_ids.append(sub_id)

    db.session.commit()
    log_admin_action('bulk_update_status', submission_ids=updated_ids, status=new_status)
    return jsonify({'success': True, 'updated_ids': updated_ids, 'status': new_status})


@bp.route('/admin/bulk-delete', methods=['POST'])
@login_required
def admin_bulk_delete():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'success': False, 'message': 'invalid JSON'}), 400

    ids = data.get('ids') or []
    message = (data.get('message') or '').strip()

    if not ids:
        return jsonify({'success': False, 'message': 'no ids provided'}), 400
    if not message:
        return jsonify({'success': False, 'message': 'message is required'}), 400
    if len(message) > ADMIN_DELETE_MSG_MAX:
        return jsonify({'success': False, 'message': 'message too long'}), 400

    deleted_ids = []
    for sub_id in ids:
        sub = db.session.get(Submission, sub_id)
        if sub:
            summary = submission_summary(sub.category, sub.style_type, sub.id, product=sub.product)
            db.session.add(UserNotification(
                user_id=sub.user_id,
                kind='order_removed',
                message=message,
                order_id=sub.id,
                order_summary=summary,
            ))
            db.session.delete(sub)
            deleted_ids.append(sub_id)

    db.session.commit()
    log_admin_action('bulk_delete', submission_ids=deleted_ids)
    return jsonify({'success': True, 'deleted_ids': deleted_ids})


@bp.route('/admin/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_submission(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'success': False, 'message': 'invalid JSON'}), 400

    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({'success': False, 'message': 'message is required'}), 400
    if len(message) > ADMIN_DELETE_MSG_MAX:
        return jsonify({'success': False, 'message': 'message too long'}), 400

    sub = Submission.query.get_or_404(id)
    summary = submission_summary(sub.category, sub.style_type, sub.id, product=sub.product)
    db.session.add(UserNotification(
        user_id=sub.user_id,
        kind='order_removed',
        message=message,
        order_id=sub.id,
        order_summary=summary,
    ))
    db.session.delete(sub)
    db.session.commit()
    log_admin_action('delete_submission', submission_id=id)
    return jsonify({'success': True})


@bp.route('/notifications')
@login_required
def notifications():
    notes = UserNotification.query.filter_by(user_id=current_user.id) \
        .order_by(UserNotification.created_at.desc()) \
        .limit(100).all()

    for note in notes:
        note.show_unread = not note.is_read

    unread_count = sum(1 for note in notes if note.show_unread)

    if unread_count:
        UserNotification.query.filter_by(user_id=current_user.id, is_read=False) \
            .update({UserNotification.is_read: True})
        db.session.commit()

    groups = _group_notifications(notes)
    return render_template(
        'notifications/index.html',
        notifications=notes,
        notification_groups=groups,
        unread_count=unread_count,
    )


@bp.route('/notifications/delete/<int:id>', methods=['POST'])
@login_required
def delete_notification(id):
    note = UserNotification.query.get_or_404(id)
    if note.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    db.session.delete(note)
    db.session.commit()
    return jsonify({'success': True, 'unread_count': _unread_count(current_user.id)})


@bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_submission(id):
    sub = Submission.query.get_or_404(id)
    if sub.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    if sub.status != 'pending':
        return jsonify({'success': False, 'message': 'Only pending submissions can be deleted'}), 400

    db.session.delete(sub)
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/edit/<int:id>', methods=['POST'])
@login_required
@limiter.limit('30 per hour')
def edit_submission(id):
    from flask import current_app
    sub = Submission.query.get_or_404(id)
    if sub.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    if sub.status != 'pending':
        return jsonify({'success': False, 'message': 'Only pending submissions can be edited'}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'success': False, 'message': 'invalid JSON'}), 400

    cleaned, error = validate_submission_fields(data)
    if error:
        return jsonify({'success': False, 'message': error}), 400

    pricing = compute_order_pricing(cleaned, partial=False)
    if not pricing.ready:
        return jsonify({'success': False, 'message': pricing.error or 'pricing error'}), 400

    variant = pricing.variant
    sub.product_id = variant.product_id
    sub.category = cleaned['category']
    sub.carat = cleaned['carat']
    sub.style_type = cleaned['type']
    sub.gold_purity = cleaned['gold']
    sub.color = cleaned.get('color')
    sub.diamond_kind = cleaned.get('diamondKind', 'white')
    sub.fancy_color = cleaned.get('fancyColor')
    sub.stone_count = cleaned.get('stoneCount')
    sub.diamond_shape = cleaned.get('diamondShape', 'round')
    sub.weight = pricing.weight_grams
    sub.ring_size = cleaned.get('ringSize')
    sub.engraving_band = cleaned.get('engravingBand')
    sub.engraving_girdle = cleaned.get('engravingGirdle')
    sub.include_chain = cleaned.get('includeChain', False)
    sub.chain_length_cm = cleaned.get('lengthCm') if cleaned['category'] in ('chain', 'bracelet') else None

    if sub.include_chain:
        sub.chain_product_id = pricing.chain_variant.product_id if pricing.chain_variant else None
        sub.chain_gold = cleaned.get('chainGold')
        sub.chain_color = cleaned.get('chainColor')
        sub.chain_length_cm = cleaned.get('chainLength')
        sub.chain_weight_chin = pricing.chain_weight_chin
    else:
        sub.chain_product_id = None
        sub.chain_gold = None
        sub.chain_color = None
        sub.chain_weight_chin = None
        if cleaned['category'] == 'chain':
            sub.chain_length_cm = cleaned.get('lengthCm')
            sub.chain_weight_chin = pricing.weight_chin

    apply_pricing_to_submission(sub, cleaned, pricing)
    sub.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Edit failed for submission %s: %s', id, exc)
        return jsonify({'success': False, 'message': 'save failed'}), 400
    return jsonify({'success': True})
