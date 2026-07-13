"""Test cart add with forced login session."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env', override=True)

from diamond_calculator import create_app
from diamond_calculator.repository.models import Product, User
from werkzeug.security import check_password_hash

app = create_app()
client = app.test_client()

with app.app_context():
    u = User.query.filter_by(username='store_a').first()
    for pw in ('pass_a', 'store123', 'password', 'test'):
        ok = check_password_hash(u.password_hash, pw)
        print(f'store_a password {pw!r}:', ok)

with client.session_transaction() as sess:
    with app.app_context():
        u = User.query.filter_by(username='store_a').first()
        sess['_user_id'] = str(u.id)
        sess['_fresh'] = True

page = client.get('/calculator')
match = re.search(rb'name="csrf-token" content="([^"]+)"', page.data)
csrf = match.group(1).decode()

with app.app_context():
    ring = Product.query.filter_by(category='ring', is_published=True).first()

payload = {
    'category': 'ring',
    'carat': '0.3',
    'type': str(ring.id),
    'gold': '14k',
    'color': 'white',
    'ringSize': 12,
}
res = client.post('/api/cart/add', json=payload, headers={'X-CSRFToken': csrf})
print('cart add', res.status_code, res.get_json())
