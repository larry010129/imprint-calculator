"""Test cart add with Flask test client and real CSRF."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env', override=True)

from diamond_calculator import create_app
from diamond_calculator.repository.models import Product, User

app = create_app()
client = app.test_client()

login_page = client.get('/login')
csrf_login = re.search(rb'name="csrf_token" value="([^"]+)"', login_page.data)
print('login csrf', bool(csrf_login))
res = client.post('/login', data={
    'username': 'store_a',
    'password': 'pass_a',
    'csrf_token': csrf_login.group(1).decode() if csrf_login else '',
}, follow_redirects=False)
print('login status', res.status_code, res.headers.get('Location', ''))

page = client.get('/calculator')
print('calc status', page.status_code)
match = re.search(rb'name="csrf-token" content="([^"]+)"', page.data)
print('calc csrf meta', bool(match))
if not match:
    raise SystemExit('csrf meta missing on calculator')
csrf = match.group(1).decode()

with app.app_context():
    users = [u.username for u in User.query.limit(10).all()]
    print('users sample', users)
    ring = Product.query.filter_by(category='ring', is_published=True).first()
    print('ring product', ring.id if ring else None)

payload = {
    'category': 'ring',
    'carat': '0.3',
    'type': str(ring.id),
    'gold': '14k',
    'color': 'white',
    'ringSize': 12,
}
res = client.post('/api/cart/add', json=payload, headers={'X-CSRFToken': csrf})
print('cart add status', res.status_code)
print('cart add body', res.get_json())
