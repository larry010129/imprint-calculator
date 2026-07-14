"""Quick manual test for /api/cart/add against a running server."""
import re
import sys

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8000'
USER = sys.argv[2] if len(sys.argv) > 2 else 'store_a'
PASSWORD = sys.argv[3] if len(sys.argv) > 3 else 'pass_a'

s = requests.Session()
r = s.get(f'{BASE}/login', timeout=5)
r.raise_for_status()
csrf = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
if not csrf:
    raise SystemExit('csrf token missing on login page')
r = s.post(
    f'{BASE}/login',
    data={'username': USER, 'password': PASSWORD, 'csrf_token': csrf.group(1)},
    allow_redirects=False,
)
print('login', r.status_code, r.headers.get('Location', ''))

r = s.get(f'{BASE}/calculator')
r.raise_for_status()
meta = re.search(r'name="csrf-token" content="([^"]+)"', r.text)
print('csrf meta on calculator', bool(meta))

r = s.get(f'{BASE}/api/catalog')
r.raise_for_status()
cat = r.json()
ring = next(p for p in cat['ring'] if p.get('published'))
payload = {
    'category': 'ring',
    'carat': '0.3',
    'type': ring['id'],
    'gold': '14k',
    'color': 'white',
    'ringSize': 12,
}
headers = {'Content-Type': 'application/json'}
if meta:
    headers['X-CSRFToken'] = meta.group(1)
r = s.post(f'{BASE}/api/cart/add', json=payload, headers=headers)
print('cart add', r.status_code, r.text[:800])
