"""
Route-level tests. Run with: python test_routes.py

IMPORTANT: sets DATABASE_URL to in-memory sqlite BEFORE importing app,
so it never touches instance/database.db. Do not remove or reorder the
os.environ line below the imports.
"""
import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ.setdefault('SECRET_KEY', 'test-secret-key-not-for-production')

from app import app, db
from models import User, Submission
from sqlalchemy import select
from werkzeug.security import generate_password_hash

app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False


def fresh_client():
    """Fresh test client with clean in-memory DB and three seeded users."""
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
    return app.test_client()


def login(client, username, password):
    return client.post('/login', data={'username': username, 'password': password},
                       follow_redirects=False)


# --- Test 1: unauthenticated access to protected routes is blocked ---
client = fresh_client()
res = client.get('/calculator', follow_redirects=False)
assert res.status_code == 302, f"expected redirect for anon /calculator, got {res.status_code}"
assert '/login' in res.headers.get('Location', ''), "anon /calculator should redirect to /login"

res = client.get('/api/prices', headers={'X-CSRFToken': 'dummy'})
assert res.status_code == 401, f"expected 401 for anon /api/prices, got {res.status_code}"

# --- Test 2: login redirects providers to /calculator, admin to /admin ---
client = fresh_client()
res = login(client, 'store_a', 'pass_a')
assert res.status_code == 302 and res.headers['Location'].endswith('/calculator'), \
    f"provider login should redirect to /calculator, got {res.headers.get('Location')}"

client = fresh_client()
res = login(client, 'admin_test', 'adminpass')
assert res.status_code == 302 and res.headers['Location'].endswith('/admin'), \
    f"admin login should redirect to /admin, got {res.headers.get('Location')}"

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
                                    'gold': 'tin', 'weight': -5})
assert res.status_code == 400, f"invalid /submit should 400, got {res.status_code}"
with app.app_context():
    after_count = Submission.query.count()
assert after_count == before_count, "invalid /submit must not create a Submission row"

# --- Test 6: valid ring submit creates one row with positive total and recorded rate ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
res = client.post('/submit', json={
    'category': 'ring', 'carat': '1', 'type': 'A', 'gold': '18k', 'weight': 3.5, 'ringSize': 12
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
    assert subs[0].price_source in ('live', 'fallback'), "price_source must be 'live' or 'fallback'"

# --- Test 7: ring without ringSize is rejected ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
res = client.post('/submit', json={'category': 'ring', 'carat': '1', 'type': 'A',
                                    'gold': '18k', 'weight': 3.5})
assert res.status_code == 400, "ring without ringSize must be rejected"
assert 'ringSize' in res.get_json()['message']

# --- Test 8: cross-tenant isolation — store_b cannot delete store_a's submission ---
client = fresh_client()
login(client, 'store_a', 'pass_a')
client.post('/submit', json={
    'category': 'necklace', 'carat': '0.5', 'type': 'B', 'gold': 'pt', 'weight': 5.0
})
with app.app_context():
    target_id = Submission.query.filter_by(
        user_id=User.query.filter_by(username='store_a').first().id
    ).first().id

client.get('/logout')
login(client, 'store_b', 'pass_b')
res = client.post(f'/delete/{target_id}')
assert res.status_code == 403, f"store_b deleting store_a's order should 403, got {res.status_code}"
with app.app_context():
    assert db.session.get(Submission, target_id) is not None, \
        "store_a's submission must still exist after blocked delete"

# --- Test 9: owner can delete their own pending submission ---
client.get('/logout')
login(client, 'store_a', 'pass_a')
res = client.post(f'/delete/{target_id}')
assert res.status_code == 200 and res.get_json()['success'] is True, \
    "owner should be able to delete their own pending order"
with app.app_context():
    assert db.session.get(Submission, target_id) is None, "submission should be gone after owner deletes"

# --- Test 10: weight and ring size boundary validation ---
from app import validate_submission_fields, MAX_WEIGHT_GRAMS, RING_SIZE_MIN, RING_SIZE_MAX

_, err = validate_submission_fields({
    'category': 'ring', 'carat': '1', 'type': 'A', 'gold': '18k',
    'weight': MAX_WEIGHT_GRAMS + 0.01, 'ringSize': 12
})
assert err and 'weight' in err, "weight just above MAX_WEIGHT_GRAMS must be rejected"

_, err = validate_submission_fields({
    'category': 'ring', 'carat': '1', 'type': 'A', 'gold': '18k',
    'weight': 3.5, 'ringSize': RING_SIZE_MIN - 1
})
assert err and 'ringSize' in err, "ringSize below RING_SIZE_MIN must be rejected"

_, err = validate_submission_fields({
    'category': 'ring', 'carat': '1', 'type': 'A', 'gold': '18k',
    'weight': 3.5, 'ringSize': RING_SIZE_MAX + 1
})
assert err and 'ringSize' in err, "ringSize above RING_SIZE_MAX must be rejected"

ok, err = validate_submission_fields({
    'category': 'ring', 'carat': '1', 'type': 'A', 'gold': '18k',
    'weight': 0.01, 'ringSize': RING_SIZE_MIN
})
assert err is None, f"boundary-minimum weight/ringSize should be accepted, got: {err}"

print("all route tests passed")
