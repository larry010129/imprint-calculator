"""
Route-level tests. Run from project root: python tests/test_routes.py
"""
import os
import sys
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ.setdefault('SECRET_KEY', 'test-secret-key-not-for-production')
os.environ['DISABLE_PRICE_SCHEDULER'] = '1'

from diamond_calculator.application.auth import _login_attempts
from diamond_calculator.application.catalog_seed import seed_legacy_products
from diamond_calculator.application.shared_config import encode_config
from diamond_calculator.application.validation import RING_SIZE_MAX, RING_SIZE_MIN, validate_submission_fields
from diamond_calculator import create_app
from diamond_calculator.repository.models import (
    CartItem, FavoriteItem, Product, Submission, User, UserNotification, db,
)

from werkzeug.security import generate_password_hash
from PIL import Image

app = create_app()
app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False


def fresh_client():
    """Fresh test client with clean in-memory DB, three seeded users, and the
    13 legacy-style catalog products (so /submit + /edit can resolve variants)."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        admin = User(username='admin_test', password_hash=generate_password_hash('adminpass'),
                     role='admin', store_name='Admin HQ')
        store_a = User(username='store_a', password_hash=generate_password_hash('pass_a'),
                       role='provider', store_name='Store A')
        store_b = User(username='store_b', password_hash=generate_password_hash('pass_b'),
                       role='provider', store_name='Store B')
        db.session.add_all([admin, store_a, store_b])
        db.session.commit()
        seed_legacy_products()
    return app.test_client()


def pid(category, letter):
    """Product id for a legacy style slot (e.g. pid('ring', 'A'))."""
    with app.app_context():
        product = Product.query.filter_by(category=category, sort_order=ord(letter) - ord('A')).first()
        assert product, f'no seeded product for {category}/{letter}'
        return str(product.id)


def login(client, username, password):
    return client.post('/login', data={'username': username, 'password': password},
                       follow_redirects=False)


def _csrf(client):
    return ''



# --- Test 1: unauthenticated access to protected routes is blocked ---
client = fresh_client()
res = client.get('/calculator', follow_redirects=False)
assert res.status_code == 200, f"expected 200 for anon /calculator, got {res.status_code}"
assert b'shop-catalog' in res.data
assert b'shop-guest-banner' in res.data
assert b'id="confirm-btn"' in res.data
assert b'id="cart-btn"' not in res.data
assert b'/login' in res.data

res = client.get('/styles', follow_redirects=False)
assert res.status_code == 302
assert '/calculator' in res.headers.get('Location', '')

res = client.get('/api/prices', headers={'X-CSRFToken': 'dummy'})
assert res.status_code == 200, f"expected 200 for anon /api/prices (guest shop), got {res.status_code}"

# --- Test 2: login redirects providers to /calculator, admin to /admin ---
client = fresh_client()
res = login(client, 'store_a', 'pass_a')
assert res.status_code == 302 and res.headers['Location'].endswith('/calculator'), \
    f"provider login should redirect to /calculator, got {res.headers.get('Location')}"

client = fresh_client()
res = login(client, 'admin_test', 'adminpass')
assert res.status_code == 302 and res.headers['Location'].endswith('/admin/dashboard'), \
    f"admin login should redirect to /admin/dashboard, got {res.headers.get('Location')}"

# --- Test 3: wrong password is rejected ---
client = fresh_client()
res = login(client, 'store_a', 'wrong-password')
assert res.status_code == 200, "failed login should re-render login page, not redirect"

# --- Test 4: provider cannot view /admin ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
res = client.get('/admin', follow_redirects=False)
assert res.status_code == 302, f"provider hitting /admin should be redirected, got {res.status_code}"
assert '/admin' not in res.headers.get('Location', ''), "must not redirect back into /admin"

# --- Test 5: /submit rejects invalid data and does not create a row ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
with app.app_context():
    before_count = Submission.query.count()
res = client.post('/submit', json={'category': 'sofa', 'carat': '99', 'type': 'Z',
                                    'gold': 'tin'})
assert res.status_code == 400, f"invalid /submit should 400, got {res.status_code}"
with app.app_context():
    after_count = Submission.query.count()
assert after_count == before_count, "invalid /submit must not create a Submission row"

# --- Test 6: valid ring submit creates one row with positive total and recorded rate ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
res = client.post('/submit', json={
    'category': 'ring', 'carat': '1.0', 'type': pid('ring', 'A'), 'gold': '18k', 'color': 'white', 'ringSize': 9
})
assert res.status_code == 200, f"valid /submit should 200, got {res.status_code} body={res.get_json()}"
body = res.get_json()
assert body['status'] == 'success', f"expected success, got {body}"
assert body['total_price'] > 0, "total_price should be positive"
with app.app_context():
    subs = Submission.query.all()
    assert len(subs) == 1, f"expected 1 submission, found {len(subs)}"
    assert subs[0].user_id == User.query.filter_by(username='store_a').first().id
    assert subs[0].gold_rate_per_gram is not None, "gold_rate_per_gram should be recorded"
    assert subs[0].price_source in ('bot', 'fallback', 'cached'), "price_source must be bot, cached, or fallback"
    assert subs[0].weight is not None and subs[0].weight > 0, "weight should be auto-computed"

# --- Test 7: ring without ringSize is rejected ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
res = client.post('/submit', json={'category': 'ring', 'carat': '1.0', 'type': pid('ring', 'A'),
                                    'gold': '18k'})
assert res.status_code == 400, "ring without ringSize must be rejected"
assert 'ringSize' in res.get_json()['message']

# --- Test 8: cross-tenant isolation — store_b cannot delete store_a's submission ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
client.post('/submit', json={
    'category': 'pendant', 'carat': '0.5', 'type': pid('pendant', 'B'), 'gold': 'pt950'
})
with app.app_context():
    target_id = Submission.query.filter_by(
        user_id=User.query.filter_by(username='store_a').first().id
    ).first().id

client.post('/logout')
login(client, 'store_b', 'pass_b')
res = client.post(f'/delete/{target_id}')
assert res.status_code == 403, f"store_b deleting store_a's order should 403, got {res.status_code}"
with app.app_context():
    assert db.session.get(Submission, target_id) is not None, \
        "store_a's submission must still exist after blocked delete"

# --- Test 9: owner can delete their own pending submission ---
client.post('/logout')
login(client, 'store_a', 'pass_a')
res = client.post(f'/delete/{target_id}')
assert res.status_code == 200 and res.get_json()['success'] is True, \
    "owner should be able to delete their own pending order"
with app.app_context():
    assert db.session.get(Submission, target_id) is None, "submission should be gone after owner deletes"

# --- Test 10: ring size boundary validation ---

_, err = validate_submission_fields({
    'category': 'ring', 'carat': '1.0', 'type': 'A', 'gold': '18k',
    'ringSize': RING_SIZE_MIN - 0.5
})
assert err and 'ringSize' in err, "ringSize below RING_SIZE_MIN must be rejected"

_, err = validate_submission_fields({
    'category': 'ring', 'carat': '1.0', 'type': 'A', 'gold': '18k',
    'ringSize': RING_SIZE_MAX + 0.5
})
assert err and 'ringSize' in err, "ringSize above RING_SIZE_MAX must be rejected"

ok, err = validate_submission_fields({
    'category': 'ring', 'carat': '1.0', 'type': 'A', 'gold': '18k', 'color': 'white',
    'ringSize': RING_SIZE_MIN
})
assert err is None, f"minimum valid ringSize should be accepted, got: {err}"

ok, err = validate_submission_fields({
    'category': 'ring', 'carat': '1.0', 'type': 'A', 'gold': '18k', 'color': 'white',
    'ringSize': RING_SIZE_MAX
})
assert err is None, f"maximum valid ringSize should be accepted, got: {err}"

# --- Test 11: bracelet weight auto-lookup (volume x density) ---
from diamond_calculator.application.catalog_seed import DENSITY_CHIN_PER_CM3, VOLUME_TABLE

client = fresh_client()
login(client, 'store_a', 'pass_a')
res = client.post('/submit', json={
    'category': 'bracelet', 'carat': '0.1', 'type': pid('bracelet', 'C'), 'gold': 's925',
    'lengthCm': 18,
})
assert res.status_code == 200, f"bracelet submit should succeed, got {res.get_json()}"
with app.app_context():
    sub = Submission.query.first()
    expected_weight = VOLUME_TABLE['bracelet']['C']['0.1'] * DENSITY_CHIN_PER_CM3['s925'] * 3.75
    assert abs(sub.weight - expected_weight) < 0.001, \
        f"bracelet weight should be {expected_weight}g (volume x density), got {sub.weight}"

# --- Test 11b: bracelet 銘印手鍊 0.1ct weight lookup ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
res = client.post('/submit', json={
    'category': 'bracelet', 'carat': '0.1', 'type': pid('bracelet', 'B'), 'gold': '14k', 'color': 'white',
    'lengthCm': 18,
})
assert res.status_code == 200, f"bracelet 0.1ct submit should succeed, got {res.get_json()}"
with app.app_context():
    sub = Submission.query.first()
    expected_weight = VOLUME_TABLE['bracelet']['B']['0.1'] * DENSITY_CHIN_PER_CM3['14k'] * 3.75
    assert abs(sub.weight - expected_weight) < 0.001, \
        f"bracelet 0.1ct weight should be {expected_weight}g, got {sub.weight}"

# --- Test 12: chain submit (3fen, no ring size required) ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
res = client.post('/submit', json={
    'category': 'chain', 'carat': '3fen', 'type': pid('chain', 'A'), 'gold': '18k', 'color': 'white',
    'lengthCm': 45,
})
assert res.status_code == 200, f"chain submit should succeed, got {res.get_json()}"
with app.app_context():
    sub = Submission.query.first()
    assert sub.category == 'chain'
    assert sub.carat == '3fen'
    assert abs(sub.weight - 0.3 * 3.75) < 0.001, "chain 3fen weight should be 1.125g"

# --- Test 12b: pendant with matching chain in quote and submit ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
pendant_quote_payload = {
    'category': 'pendant', 'carat': '0.3', 'type': pid('pendant', 'A'), 'gold': '14k', 'color': 'white',
    'includeChain': False,
}
res = client.post('/api/quote', json=pendant_quote_payload)
assert res.status_code == 200
pendant_only = res.get_json()
assert pendant_only['ready'] and pendant_only.get('chainPrice') is None

chain_quote_payload = {
    **pendant_quote_payload,
    'includeChain': True,
    'chainProductId': pid('chain', 'A'),
    'chainGold': '14k',
    'chainColor': 'white',
    'chainLength': 45,
}
res = client.post('/api/quote', json=chain_quote_payload)
assert res.status_code == 200
with_chain = res.get_json()
assert with_chain['ready'], with_chain
assert with_chain['chainPrice'] > 0
assert with_chain['total'] > pendant_only['total']

res = client.post('/submit', json=chain_quote_payload)
assert res.status_code == 200, f"pendant+chain submit should succeed, got {res.get_json()}"
with app.app_context():
    sub = Submission.query.first()
    assert sub.include_chain is True
    assert sub.chain_product_id is not None
    assert sub.chain_length_cm == 45
    assert sub.chain_total_twd is not None and sub.chain_total_twd > 0
    assert sub.total_price > sub.chain_total_twd

# --- Test 6b: /api/prices includes shared pricing constants for client sync ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
res = client.get('/api/prices', headers={'X-CSRFToken': 'dummy'})
assert res.status_code == 200
data = res.get_json()
assert data['laborFee']['ring'] == 5000
assert data['laborFee']['earring'] == 5000
assert data['laborFee']['chain'] == 5000
assert data['chinToGrams'] == 3.75
assert data['taxRate'] == 0.05

# --- Test 13: cross-tenant isolation — store_b cannot edit store_a's submission ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
client.post('/submit', json={
    'category': 'pendant', 'carat': '0.3', 'type': pid('pendant', 'A'), 'gold': '14k', 'color': 'white'
})
with app.app_context():
    target_id = Submission.query.filter_by(
        user_id=User.query.filter_by(username='store_a').first().id
    ).first().id

client.post('/logout')
login(client, 'store_b', 'pass_b')
res = client.post(f'/edit/{target_id}', json={
    'category': 'pendant', 'carat': '0.5', 'type': pid('pendant', 'B'), 'gold': '18k', 'color': 'yellow'
})
assert res.status_code == 403, f"store_b editing store_a's order should 403, got {res.status_code}"

# --- Test 14: provider cannot call admin update_status ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
client.post('/submit', json={
    'category': 'earring', 'carat': '0.1', 'type': pid('earring', 'A'), 'gold': '18k', 'color': 'white'
})
with app.app_context():
    sub_id = Submission.query.first().id

res = client.post(f'/admin/update_status/{sub_id}', json={'status': 'completed'})
assert res.status_code == 403, f"provider update_status should 403, got {res.status_code}"

# --- Test 15: admin CAN update status ---
client = fresh_client()
login(client, 'admin_test', 'adminpass')
with app.app_context():
    store_a_id = User.query.filter_by(username='store_a').first().id
    sub = Submission(user_id=store_a_id, category='bracelet', carat='0.1',
                     style_type='A', gold_purity='s925', total_price=50000, status='pending')
    db.session.add(sub)
    db.session.commit()
    sub_id = sub.id

res = client.post(f'/admin/update_status/{sub_id}', json={'status': 'confirmed'})
assert res.status_code == 200 and res.get_json()['success'] is True
with app.app_context():
    assert db.session.get(Submission, sub_id).status == 'confirmed'

# --- Test 15b: cancelled order appears in store history cancelled tab ---
client = fresh_client()
login(client, 'admin_test', 'adminpass')
with app.app_context():
    store_a_id = User.query.filter_by(username='store_a').first().id
    sub = Submission(user_id=store_a_id, category='ring', carat='0.3',
                     style_type='A', gold_purity='14k', total_price=120000, status='pending')
    db.session.add(sub)
    db.session.commit()
    cancelled_id = sub.id

res = client.post(
    f'/admin/update_status/{cancelled_id}',
    json={'status': 'cancelled', 'reason': 'Out of stock'},
)
assert res.status_code == 200 and res.get_json()['success'] is True

client.post('/logout')
login(client, 'store_a', 'pass_a')
res = client.get('/history?tab=cancelled')
assert res.status_code == 200
body = res.get_data(as_text=True)
cancelled_pos = body.find('history-tbody-cancelled')
row_pos = body.find(f'id="row-{cancelled_id}"')
assert cancelled_pos != -1 and row_pos != -1 and row_pos > cancelled_pos

# --- Test 16: login lockout after 5 failures ---
client = fresh_client()
for _ in range(5):
    login(client, 'store_a', 'wrong')
res = login(client, 'store_a', 'pass_a')
assert res.status_code == 200, "6th attempt during lockout should re-render login, not redirect"
body = res.get_data(as_text=True)
assert 'Too many failed attempts' in body or '登入失敗次數過多' in body

# --- Test 17: profile requires login ---
_login_attempts.clear()

client = fresh_client()
res = client.get('/profile', follow_redirects=False)
assert res.status_code == 302 and '/login' in res.headers.get('Location', '')

# --- Test 18: profile shows store info when logged in ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
res = client.get('/profile')
assert res.status_code == 200
assert b'Store A' in res.data

# --- Test 19: /gold-price requires login ---
client = fresh_client()
res = client.get('/gold-price', follow_redirects=False)
assert res.status_code == 302 and '/login' in res.headers.get('Location', '')

client = fresh_client()
login(client, 'store_a', 'pass_a')
res = client.get('/gold-price')
assert res.status_code == 200
assert b'NT$' in res.data or b'gold-price' in res.data
assert b'Manual (.env)' not in res.data

# --- Test 20: /api/gold/refresh requires login and returns JSON ---
client = fresh_client()
res = client.post('/api/gold/refresh', headers={'X-CSRFToken': 'dummy'})
assert res.status_code == 401

client = fresh_client()
login(client, 'store_a', 'pass_a')
res = client.post('/api/gold/refresh', headers={'X-CSRFToken': 'dummy'})
assert res.status_code == 200
body = res.get_json()
assert 'quote' in body and 'alloyRates' in body
assert 'refreshed' in body

# --- Test 21: admin accounts page ---
import re

client = fresh_client()
login(client, 'store_a', 'pass_a')
res = client.get('/admin/accounts', follow_redirects=False)
assert res.status_code == 302, 'provider must not access admin accounts'

client = fresh_client()
login(client, 'admin_test', 'adminpass')
res = client.get('/admin/accounts')
assert res.status_code == 200
assert b'store_a' in res.data
assert b'store_b' in res.data
assert '已加密'.encode() in res.data or b'Encrypted' in res.data

# --- Test 22: admin can reset a user password ---
csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', res.get_data(as_text=True))
assert csrf_match, 'csrf token required on admin accounts page'
csrf = csrf_match.group(1)
with app.app_context():
    store_b_id = User.query.filter_by(username='store_b').first().id

res = client.post(f'/admin/accounts/{store_b_id}/reset-password', data={
    'csrf_token': csrf,
    'new_password': 'newpass_b',
})
assert res.status_code == 302
assert client.post('/login', data={'username': 'store_b', 'password': 'newpass_b'},
                   follow_redirects=False).status_code == 302

# --- Test 23: admin delete creates notification and removes order ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
client.post('/submit', json={
    'category': 'ring', 'carat': '1.0', 'type': pid('ring', 'A'), 'gold': '18k', 'color': 'white', 'ringSize': 10
})
with app.app_context():
    sub_id = Submission.query.first().id
    store_a_id = User.query.filter_by(username='store_a').first().id

client.post('/logout')
login(client, 'admin_test', 'adminpass')
res = client.post(f'/admin/delete/{sub_id}', json={'message': 'Duplicate order removed.'})
assert res.status_code == 200 and res.get_json()['success'] is True, res.get_json()
with app.app_context():
    assert db.session.get(Submission, sub_id) is None
    note = UserNotification.query.filter_by(user_id=store_a_id).first()
    assert note is not None, 'notification should be created for store owner'
    assert note.message == 'Duplicate order removed.'
    assert note.kind == 'order_removed'
    assert note.order_id == sub_id
    assert note.is_read is False

# --- Test 24: admin delete requires message ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
client.post('/submit', json={
    'category': 'pendant', 'carat': '0.3', 'type': pid('pendant', 'A'), 'gold': '14k', 'color': 'white'
})
with app.app_context():
    sub_id = Submission.query.first().id

client.post('/logout')
login(client, 'admin_test', 'adminpass')
res = client.post(f'/admin/delete/{sub_id}', json={'message': '   '})
assert res.status_code == 400

# --- Test 25: provider cannot admin-delete ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
client.post('/submit', json={
    'category': 'earring', 'carat': '0.1', 'type': pid('earring', 'A'), 'gold': '18k', 'color': 'white'
})
with app.app_context():
    sub_id = Submission.query.first().id

res = client.post(f'/admin/delete/{sub_id}', json={'message': 'nope'})
assert res.status_code == 403
with app.app_context():
    assert db.session.get(Submission, sub_id) is not None

# --- Test 26: provider notifications page and unread badge ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
with app.app_context():
    store_a_id = User.query.filter_by(username='store_a').first().id
    db.session.add(UserNotification(
        user_id=store_a_id,
        kind='order_removed',
        message='Your order was cancelled.',
        order_id=99,
        order_summary='訂單 #99 · 戒指 · 款式A',
    ))
    db.session.commit()

res = client.get('/calculator')
assert res.status_code == 200
assert b'nav-notify-badge' in res.data

res = client.get('/notifications')
assert res.status_code == 200
assert b'Your order was cancelled.' in res.data
assert b'notifications-feed-item--unread' in res.data
assert b'notifications-feed-dot' in res.data
calc_after = client.get('/calculator')
assert b'nav-notify-badge' in calc_after.data
assert b'nav-notify-badge" hidden' in calc_after.data or b'nav-notify-badge" id="nav-notify-badge" hidden' in calc_after.data

res = client.get('/api/notifications/recent')
assert res.status_code == 200
recent = res.get_json()
assert 'notifications' in recent and len(recent['notifications']) >= 1

# --- Test 27: user can delete their notification ---
with app.app_context():
    note_id = UserNotification.query.filter_by(user_id=store_a_id).first().id

res = client.post(f'/notifications/delete/{note_id}')
assert res.status_code == 200 and res.get_json()['success'] is True
with app.app_context():
    assert db.session.get(UserNotification, note_id) is None

res = client.post(f'/notifications/delete/{note_id}')
assert res.status_code == 404

client.post('/logout')
login(client, 'store_b', 'pass_b')
with app.app_context():
    other_note = UserNotification(
        user_id=User.query.filter_by(username='store_a').first().id,
        kind='order_removed',
        message='Private note',
        order_id=1,
    )
    db.session.add(other_note)
    db.session.commit()
    other_id = other_note.id

res = client.post(f'/notifications/delete/{other_id}')
assert res.status_code == 403

client.post('/logout')
login(client, 'admin_test', 'adminpass')
res = client.get('/notifications')
assert res.status_code == 200

# --- Health endpoint ---
client = fresh_client()
res = client.get('/health')
assert res.status_code == 200
data = res.get_json()
assert data.get('status') == 'ok'

# --- Unpublished product cannot be submitted ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
with app.app_context():
    draft = Product.query.filter_by(category='ring').first()
    draft.is_published = False
    db.session.commit()
    draft_id = str(draft.id)
res = client.post('/submit', json={
    'category': 'ring', 'type': draft_id, 'gold': '18k', 'color': 'white',
    'carat': '0.3', 'ringSize': 12,
})
assert res.status_code == 400

# --- Admin invite codes: create, delete does not remove users ---
client = fresh_client()
login(client, 'admin_test', 'adminpass')
with app.app_context():
    from diamond_calculator.repository.models import InviteCode, User
    InviteCode.query.delete()
    db.session.commit()
res = client.post('/admin/invites/create', data={
    'csrf_token': _csrf(client),
    'max_uses': '3',
}, follow_redirects=True)
assert res.status_code == 200
with app.app_context():
    invite = InviteCode.query.order_by(InviteCode.id.desc()).first()
    assert invite is not None
    assert invite.max_uses == 3
    assert invite.is_active is True
    invite_id = invite.id
    invite_code = invite.code

# Register a store with this invite (if invite required)
os.environ['REQUIRE_INVITE_CODE'] = '1'
client2 = app.test_client()
res = client2.post('/register', data={
    'csrf_token': _csrf(client2),
    'username': 'invite_store',
    'store_name': 'Invite Store',
    'password': 'pass_invite',
    'invite_code': invite_code,
}, follow_redirects=True)
assert res.status_code == 200
with app.app_context():
    new_user = User.query.filter_by(username='invite_store').first()
    assert new_user is not None
    invite = db.session.get(InviteCode, invite_id)
    assert invite.use_count == 1

res = client.post(f'/admin/invites/{invite_id}/delete', data={
    'csrf_token': _csrf(client),
}, follow_redirects=True)
assert res.status_code == 200
with app.app_context():
    assert db.session.get(InviteCode, invite_id) is None
    assert User.query.filter_by(username='invite_store').first() is not None
os.environ.pop('REQUIRE_INVITE_CODE', None)

# --- Test 28: shopping cart add + checkout ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
with app.app_context():
    user_id = User.query.filter_by(username='store_a').first().id
    before_count = Submission.query.filter_by(user_id=user_id).count()

ring_payload = {
    'category': 'ring', 'carat': '0.3', 'type': pid('ring', 'A'),
    'gold': '14k', 'color': 'white', 'ringSize': 12,
}
pendant_payload = {
    'category': 'pendant', 'carat': '0.3', 'type': pid('pendant', 'A'),
    'gold': '14k', 'color': 'white',
}

res = client.post('/api/cart/add', json=ring_payload)
assert res.status_code == 200 and res.get_json()['success'] is True
ring_item_id = res.get_json()['item']['id']
res = client.post('/api/cart/add', json=pendant_payload)
assert res.status_code == 200 and res.get_json()['success'] is True
pendant_item_id = res.get_json()['item']['id']

res = client.get('/api/cart')
assert res.get_json()['count'] == 2

res = client.get(f'/api/cart/{ring_item_id}')
assert res.status_code == 200
detail = res.get_json()['item']
assert detail.get('image_url') is not None
assert detail.get('specs', {}).get('category')

res = client.post('/api/cart/checkout', json={'item_ids': [ring_item_id]})
assert res.status_code == 200 and res.get_json()['success'] is True
with app.app_context():
    after_partial = Submission.query.filter_by(user_id=user_id).count()
    assert after_partial == before_count + 1
    assert CartItem.query.filter_by(user_id=user_id).count() == 1
    remaining = CartItem.query.filter_by(user_id=user_id).first()
    assert remaining.id == pendant_item_id

updated_payload = dict(pendant_payload)
updated_payload['carat'] = '0.5'
res = client.put(f'/api/cart/{pendant_item_id}', json=updated_payload)
assert res.status_code == 200 and res.get_json()['success'] is True
assert res.get_json()['item']['total_price'] != detail['total_price']

res = client.get(f'/cart/{pendant_item_id}/edit')
assert res.status_code == 200
assert b'window.cartEditData' in res.data

login(client, 'store_b', 'pass_b')
res = client.get(f'/cart/{pendant_item_id}/edit')
assert res.status_code == 404 or res.status_code == 302

login(client, 'store_a', 'pass_a')
res = client.post('/api/cart/checkout')
assert res.status_code == 200 and res.get_json()['success'] is True
with app.app_context():
    after_count = Submission.query.filter_by(user_id=user_id).count()
    assert after_count == before_count + 2
    assert CartItem.query.filter_by(user_id=user_id).count() == 0

# --- Test 29: admin product publishing workflow ---
client = fresh_client()
login(client, 'admin_test', 'adminpass')

invalid = client.post('/admin/products', data={
    'category': 'ring',
    'name_zh': '',
    'default_color': 'white',
})
assert invalid.status_code == 400
assert invalid.is_json and invalid.get_json()['errors']['name_zh']

image_buffer = io.BytesIO()
Image.new('RGB', (8, 8), 'white').save(image_buffer, format='PNG')
image_buffer.seek(0)
create = client.post('/admin/products', data={
    'category': 'ring',
    'name_zh': '測試上架商品',
    'name_en': 'Publishing test',
    'default_color': 'white',
    'variant_gold': ['14k'],
    'variant_carat': ['0.3'],
    'variant_weight': ['0.8'],
    'variant_price': [''],
    'image_white': (image_buffer, 'test.png'),
}, content_type='multipart/form-data')
assert create.status_code == 200
assert create.get_json()['success'] is True

with app.app_context():
    created_product = Product.query.filter_by(name_zh='測試上架商品').first()
    assert created_product is not None
    created_id = created_product.id
    assert len(created_product.images) == 1
    incomplete = Product(
        category='ring', name_zh='不完整商品', default_color='white',
        is_published=False,
    )
    db.session.add(incomplete)
    db.session.commit()
    incomplete_id = incomplete.id

publish_bad = client.post(f'/admin/products/{incomplete_id}/publish')
assert publish_bad.status_code == 400

publish_good = client.post(f'/admin/products/{created_id}/publish')
assert publish_good.status_code == 200
with app.app_context():
    published = db.session.get(Product, created_id)
    assert published.is_published is True
    assert published.first_published_at is not None

duplicate = client.post(f'/admin/products/{created_id}/duplicate')
assert duplicate.status_code == 302
with app.app_context():
    clone = Product.query.filter(Product.name_zh.like('測試上架商品%複製%')).first()
    assert clone is not None
    clone_id = clone.id
    assert len(clone.images) == 1
    assert Path('static', clone.images[0].file_path).exists()

with app.app_context():
    ring_ids = [
        product.id for product in
        Product.query.filter_by(category='ring').order_by(Product.sort_order, Product.id).all()
    ]
reversed_ids = list(reversed(ring_ids))
reorder = client.post('/admin/products/reorder', json={
    'category': 'ring', 'ids': reversed_ids,
})
assert reorder.status_code == 200
with app.app_context():
    reordered_ids = [
        product.id for product in
        Product.query.filter_by(category='ring').order_by(Product.sort_order, Product.id).all()
    ]
    assert reordered_ids == reversed_ids

preview = client.get('/api/catalog?preview=1')
assert preview.status_code == 200
preview_products = preview.get_json()['categories']['ring']
assert any(product['id'] == clone_id and product['draft'] for product in preview_products)

login(client, 'store_a', 'pass_a')
assert client.get('/api/catalog?preview=1').status_code == 403

login(client, 'admin_test', 'adminpass')
assert client.post(f'/admin/products/{clone_id}/delete').status_code == 200
assert client.post(f'/admin/products/{created_id}/delete').status_code == 200
assert client.post(f'/admin/products/{incomplete_id}/delete').status_code == 200

# --- Test 30: shipped status is grouped as complete and notifies the store ---
client = fresh_client()
with app.app_context():
    store_a_id = User.query.filter_by(username='store_a').first().id
    product = Product.query.filter_by(category='ring', is_published=True).first()
    sub = Submission(
        user_id=store_a_id, product_id=product.id, category='ring',
        style_type=str(product.id), carat='0.3', gold_purity='14k',
        color='white', ring_size=12, total_price=88000, status='completed',
    )
    db.session.add(sub)
    db.session.commit()
    shipped_id = sub.id
login(client, 'admin_test', 'adminpass')
res = client.post(f'/admin/update_status/{shipped_id}', json={'status': 'shipped'})
assert res.status_code == 200 and res.get_json()['success'] is True
with app.app_context():
    shipped = db.session.get(Submission, shipped_id)
    assert shipped.status == 'shipped'
    note = UserNotification.query.filter_by(
        user_id=store_a_id, order_id=shipped_id, kind='status_changed',
    ).first()
    assert note is not None and '已出貨' in note.message
client.post('/logout')
login(client, 'store_a', 'pass_a')
history_body = client.get('/history?tab=complete').get_data(as_text=True)
assert f'id="row-{shipped_id}"' in history_body
assert 'status_shipped' in history_body

# --- Test 31: dashboard and CSV are admin-only ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
assert client.get('/admin/dashboard', follow_redirects=False).status_code == 302
assert client.get('/admin/dashboard/export?month=2026-07').status_code == 403
client.post('/logout')
login(client, 'admin_test', 'adminpass')
dashboard = client.get('/admin/dashboard')
assert dashboard.status_code == 200 and b'cms-admin-sidebar' in dashboard.data
csv_export = client.get('/admin/dashboard/export?month=2026-07')
assert csv_export.status_code == 200
assert csv_export.mimetype == 'text/csv'
assert csv_export.get_data().startswith(b'\xef\xbb\xbf')
assert client.get('/admin/dashboard/export?month=not-a-month').status_code == 400

# --- Test 32: favorites CRUD and calculator prefill ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
favorite_payload = {
    'category': 'ring', 'carat': '0.3', 'type': pid('ring', 'A'),
    'gold': '14k', 'color': 'white', 'ringSize': 12,
}
added = client.post('/api/favorites/add', json=favorite_payload)
assert added.status_code == 200 and added.get_json()['success'] is True
favorite_id = added.get_json()['item']['id']
assert client.get('/api/favorites').get_json()['items'][0]['id'] == favorite_id
favorites_page = client.get('/favorites')
assert favorites_page.status_code == 200 and b'favorite-card' in favorites_page.data
prefill = client.get(f'/calculator?favorite={favorite_id}')
assert prefill.status_code == 200 and b'window.prefillData' in prefill.data
assert client.delete(f'/api/favorites/{favorite_id}').status_code == 200
with app.app_context():
    assert db.session.get(FavoriteItem, favorite_id) is None

# --- Test 33: reorder owns the source and uses fresh prefill mode ---
submitted = client.post('/submit', json=favorite_payload)
assert submitted.status_code == 200
with app.app_context():
    store_a_id = User.query.filter_by(username='store_a').first().id
    reorder_id = Submission.query.filter_by(user_id=store_a_id).first().id
reorder_page = client.get(f'/calculator?reorder={reorder_id}')
assert reorder_page.status_code == 200
assert b'window.prefillData' in reorder_page.data
assert b'window.editData' not in reorder_page.data
client.post('/logout')
login(client, 'store_b', 'pass_b')
assert client.get(f'/calculator?reorder={reorder_id}').status_code == 404

# --- Test 34: public quote sheet and share-summary card validate tokens ---
client = fresh_client()
share_payload = {
    'category': 'ring', 'carat': '0.3', 'type': pid('ring', 'A'),
    'gold': '14k', 'color': 'white', 'ringSize': 12,
}
token = encode_config(share_payload)
quote_sheet = client.get(f'/quote-sheet?config={token}')
assert quote_sheet.status_code == 200 and b'quote-sheet' in quote_sheet.data
assert b'quote-sheet.js' in quote_sheet.data
assert b'onclick=' not in quote_sheet.data
share_page = client.get(f'/s/{token}')
assert share_page.status_code == 200 and b'share-card' in share_page.data
assert client.get('/quote-sheet?config=bad-token').status_code == 404
assert client.get('/s/bad-token').status_code == 404

# --- Test 35: PWA manifest and root-scoped service worker ---
assert client.get('/static/manifest.webmanifest').status_code == 200
service_worker = client.get('/sw.js')
assert service_worker.status_code == 200
assert service_worker.headers.get('Service-Worker-Allowed') == '/'

print("all route tests passed")
