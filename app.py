from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect
from datetime import datetime, timedelta, timezone
import os, json, time, urllib.request
from models import db, User, Submission

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

csrf = CSRFProtect(app)

db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

from flask_wtf.csrf import CSRFError

def wants_json():
    return request.is_json or request.headers.get('X-CSRFToken') is not None

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    if wants_json():
        return jsonify({'success': False, 'status': 'error',
                        'message': 'session expired, please reload the page'}), 400
    flash('表單已過期，請重新送出。')
    return redirect(request.full_path.rstrip('?') or url_for('login'))

@login_manager.unauthorized_handler
def handle_unauthorized():
    if wants_json():
        return jsonify({'success': False, 'status': 'error', 'message': 'login required'}), 401
    return redirect(url_for('login', next=request.full_path.rstrip('?')))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_initial_users():
    admin_password = os.environ.get('ADMIN_PASSWORD')
    if admin_password and User.query.filter_by(username='admin').first() is None:
        db.session.add(User(username='admin',
                            password_hash=generate_password_hash(admin_password),
                            role='admin', store_name='Admin HQ'))
        db.session.commit()

with app.app_context():
    db.create_all()
    create_initial_users()

# ── Template filters ──────────────────────────────────────────────────────────

@app.template_filter('tz_taiwan')
def tz_taiwan(dt):
    if not dt: return ''
    return (dt + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')

CATEGORY_LABELS = {
    'pendant': '項墜', 'ring': '戒指', 'earring': '耳飾',
    'bracelet': '手鍊', 'chain': '鍊條',
    'necklace': '項鍊 (舊)',  # backward compat for old rows
}

@app.template_filter('label_category')
def label_category(cat):
    if not cat: return ''
    return CATEGORY_LABELS.get(cat, cat)

STYLE_LABELS = {
    'pendant':  {'A': '四爪項墜', 'B': '兔耳項墜', 'C': '水滴項墜'},
    'ring':     {'A': '經典六爪', 'B': '低語之光', 'C': '羽翼'},
    'earring':  {'A': '六爪耳釘', 'B': '款式B', 'C': '款式C'},
    'bracelet': {'A': '微笑單鑽', 'B': '銘印手鍊', 'C': '單鑽手鍊'},
    'chain':    {'A': '斗圓鍊'},
}

@app.template_filter('label_style')
def label_style(style, category=None):
    if not style: return ''
    if category and category in STYLE_LABELS:
        return STYLE_LABELS[category].get(style, style)
    return {'A': '款式A', 'B': '款式B', 'C': '款式C'}.get(style, style)

PURITY_LABELS = {
    '9k': '9K金', '14k': '14K金', '18k': '18K金',
    'pt950': '鉑金 Pt950', 's925': '925銀',
    # backward compat
    '999': '純金999', 'pt': '鉑金 Pt', 'silver925': '925銀',
}

@app.template_filter('label_purity')
def label_purity(purity):
    if not purity: return ''
    return PURITY_LABELS.get(purity, purity)

COLOR_LABELS = {'white': 'K白', 'yellow': 'K黃', 'rose': 'K玫瑰'}

@app.template_filter('label_color')
def label_color(color):
    if not color: return ''
    return COLOR_LABELS.get(color, color)

# ── Metal price constants ─────────────────────────────────────────────────────

GOLDAPI_KEY = os.environ.get('GOLDAPI_KEY')

DIAMOND_PRICE = {"0.1": 24000, "0.3": 79000, "0.5": 98000, "1.0": 250000, "1": 250000}

PURITY_MULTIPLIER = {
    "9k":    0.50,
    "14k":   0.75,
    "18k":   0.85,
    "pt950": 1.10,
    "s925":  0.925,
    # backward compat
    "999":   0.999, "pt": 1.0, "silver925": 0.925,
}
METAL_SYMBOL = {
    "9k": "XAU", "14k": "XAU", "18k": "XAU",
    "pt950": "XPT", "s925": "XAG",
    # backward compat
    "999": "XAU", "pt": "XPT", "silver925": "XAG",
}
FALLBACK_TWD_PER_GRAM = {"XAU": 2400, "XPT": 1050, "XAG": 30}
TROY_OZ_GRAMS = 31.1034768

_price_cache = {"prices": None, "fetched_at": 0, "source": "fallback"}
PRICE_TTL_SECONDS = 600

_login_attempts = {}
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 300

def is_locked_out(username):
    entry = _login_attempts.get(username)
    if not entry:
        return False
    fail_count, locked_until = entry
    if fail_count >= LOGIN_MAX_ATTEMPTS and time.time() < locked_until:
        return True
    if fail_count >= LOGIN_MAX_ATTEMPTS and time.time() >= locked_until:
        _login_attempts.pop(username, None)
    return False

def record_login_failure(username):
    fail_count, _ = _login_attempts.get(username, (0, 0))
    fail_count += 1
    locked_until = time.time() + LOGIN_LOCKOUT_SECONDS if fail_count >= LOGIN_MAX_ATTEMPTS else 0
    _login_attempts[username] = (fail_count, locked_until)

def record_login_success(username):
    _login_attempts.pop(username, None)

def get_metal_prices():
    """TWD per gram for XAU/XPT/XAG, cached. Never raises."""
    now = time.time()
    if _price_cache["prices"] and now - _price_cache["fetched_at"] < PRICE_TTL_SECONDS:
        return _price_cache["prices"], _price_cache["source"]
    prices = {}
    source = "live"
    for symbol in ("XAU", "XPT", "XAG"):
        try:
            req = urllib.request.Request(
                f"https://www.goldapi.io/api/{symbol}/TWD",
                headers={"x-access-token": GOLDAPI_KEY})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            prices[symbol] = data["price"] / TROY_OZ_GRAMS
        except Exception:
            prices[symbol] = FALLBACK_TWD_PER_GRAM[symbol]
            source = "fallback"
    _price_cache.update(prices=prices, fetched_at=now, source=source)
    return prices, source

# ── Product data ──────────────────────────────────────────────────────────────

LABOR_FEE = {
    'pendant': 5000, 'ring': 5000, 'bracelet': 5000,
    'earring': 3000, 'chain': 0,
}

CHIN_TO_GRAMS = 3.75

# Weight in 錢 (chin); multiply by 3.75 for grams
WEIGHT_TABLE = {
    'pendant': {
        'A': {  # 四爪項墜
            '9k':    {'0.1': 0.09, '0.3': 0.12, '0.5': 0.15, '1.0': 0.20},
            '14k':   {'0.1': 0.10, '0.3': 0.14, '0.5': 0.17, '1.0': 0.23},
            '18k':   {'0.1': 0.12, '0.3': 0.16, '0.5': 0.20, '1.0': 0.27},
            'pt950': {'0.1': 0.15, '0.3': 0.20, '0.5': 0.25, '1.0': 0.35},
            's925':  {'0.1': 0.08, '0.3': 0.11, '0.5': 0.13, '1.0': 0.18},
        },
        'B': {  # 兔耳項墜
            '9k':    {'0.1': 0.10, '0.3': 0.15, '0.5': 0.19, '1.0': 0.28},
            '14k':   {'0.1': 0.11, '0.3': 0.17, '0.5': 0.22, '1.0': 0.33},
            '18k':   {'0.1': 0.13, '0.3': 0.20, '0.5': 0.26, '1.0': 0.39},
            'pt950': {'0.1': 0.16, '0.3': 0.25, '0.5': 0.34, '1.0': 0.52},
            's925':  {'0.1': 0.09, '0.3': 0.13, '0.5': 0.17, '1.0': 0.25},
        },
        'C': {  # 水滴項墜
            '9k':    {'0.1': 0.14, '0.3': 0.21, '0.5': 0.28, '1.0': 0.46},
            '14k':   {'0.1': 0.16, '0.3': 0.24, '0.5': 0.32, '1.0': 0.52},
            '18k':   {'0.1': 0.19, '0.3': 0.28, '0.5': 0.37, '1.0': 0.60},
            'pt950': {'0.1': 0.25, '0.3': 0.37, '0.5': 0.49, '1.0': 0.80},
            's925':  {'0.1': 0.13, '0.3': 0.19, '0.5': 0.25, '1.0': 0.40},
        },
    },
    'ring': {
        'A': {  # 經典六爪
            '9k':    {'0.1': 0.39, '0.3': 0.48, '0.5': 0.57, '1.0': 0.74},
            '14k':   {'0.1': 0.46, '0.3': 0.57, '0.5': 0.67, '1.0': 0.87},
            '18k':   {'0.1': 0.53, '0.3': 0.65, '0.5': 0.77, '1.0': 1.01},
            'pt950': {'0.1': 0.70, '0.3': 0.86, '0.5': 1.02, '1.0': 1.33},
            's925':  {'0.1': 0.35, '0.3': 0.44, '0.5': 0.52, '1.0': 0.68},
        },
        'B': {  # 低語之光
            '9k':    {'0.1': 0.40, '0.3': 0.62, '0.5': 0.84, '1.0': 1.39},
            '14k':   {'0.1': 0.47, '0.3': 0.75, '0.5': 1.03, '1.0': 1.73},
            '18k':   {'0.1': 0.54, '0.3': 0.86, '0.5': 1.18, '1.0': 1.98},
            'pt950': {'0.1': 0.71, '0.3': 1.13, '0.5': 1.55, '1.0': 2.60},
            's925':  {'0.1': 0.36, '0.3': 0.58, '0.5': 0.80, '1.0': 1.35},
        },
        'C': {  # 羽翼
            '9k':    {'0.1': 0.40, '0.3': 0.69, '0.5': 0.97, '1.0': 1.54},
            '14k':   {'0.1': 0.48, '0.3': 0.82, '0.5': 1.15, '1.0': 1.82},
            '18k':   {'0.1': 0.55, '0.3': 0.92, '0.5': 1.33, '1.0': 2.11},
            'pt950': {'0.1': 0.72, '0.3': 1.24, '0.5': 1.75, '1.0': 2.78},
            's925':  {'0.1': 0.36, '0.3': 0.62, '0.5': 0.88, '1.0': 1.40},
        },
    },
    'earring': {
        'A': {  # 六爪耳釘
            '9k':    {'0.1': 0.09, '0.3': 0.14, '0.5': 0.18, '1.0': 0.27},
            '14k':   {'0.1': 0.10, '0.3': 0.15, '0.5': 0.20, '1.0': 0.30},
            '18k':   {'0.1': 0.12, '0.3': 0.18, '0.5': 0.24, '1.0': 0.36},
        },
    },
    'bracelet': {
        'A': {  # 微笑單鑽手鍊
            '9k':    {'0.1': 0.66}, '14k':   {'0.1': 0.78},
            '18k':   {'0.1': 0.91}, 'pt950': {'0.1': 1.19}, 's925': {'0.1': 0.60},
        },
        'B': {  # 銘印手鍊
            '9k':    {'0.1': 0.46}, '14k':   {'0.1': 0.55},
            '18k':   {'0.1': 0.64}, 'pt950': {'0.1': 0.84}, 's925': {'0.1': 0.77},
        },
        'C': {  # 單鑽手鍊
            '9k':    {'0.1': 0.30}, '14k':   {'0.1': 0.36},
            '18k':   {'0.1': 0.42}, 'pt950': {'0.1': 0.55}, 's925': {'0.1': 0.28},
        },
    },
}

CHAIN_WEIGHT_CHIN = {'3fen': 0.3, '4fen': 0.4}

def lookup_weight(category, style_type, gold, carat):
    """Returns weight in chin. Raises KeyError if combo not in table."""
    if category == 'chain':
        return CHAIN_WEIGHT_CHIN[carat]
    return WEIGHT_TABLE[category][style_type][gold][carat]

def compute_total(carat, gold, weight_grams, category='ring', ring_size=None):
    """Returns (total, per_gram_alloy, source)."""
    raw, source = get_metal_prices()
    per_gram = raw[METAL_SYMBOL[gold]] * PURITY_MULTIPLIER[gold]
    metal_cost = per_gram * weight_grams

    if category == 'chain':
        total = metal_cost * 2
    else:
        diamond_cost = DIAMOND_PRICE.get(carat, 0)
        labor = LABOR_FEE.get(category, 5000)
        ring_surcharge = 0
        if category == 'ring' and ring_size is not None:
            half_above_7 = round((float(ring_size) - 7.0) / 0.5)
            ring_surcharge = max(0, half_above_7) * 500
        total = diamond_cost + metal_cost + labor + ring_surcharge

    return total, per_gram, source

# ── Validation ────────────────────────────────────────────────────────────────

VALID_CATEGORIES = {'pendant', 'ring', 'earring', 'bracelet', 'chain'}
VALID_CARATS     = {'0.1', '0.3', '0.5', '1.0'}
VALID_CARATS_CHAIN = {'3fen', '4fen'}
VALID_TYPES      = {'A', 'B', 'C'}
VALID_GOLDS      = {'9k', '14k', '18k', 'pt950', 's925'}
VALID_COLORS     = {'white', 'yellow', 'rose'}
RING_SIZE_MIN, RING_SIZE_MAX = 7.0, 11.0
PAGE_SIZE = 25

def validate_submission_fields(data, partial=False):
    errors = []
    cleaned = {}

    def check_choice(key, valid, required=True):
        val = data.get(key)
        if val is None:
            if required and not partial:
                errors.append(f'{key} is required')
        elif str(val) not in valid:
            errors.append(f'invalid {key}')
        else:
            cleaned[key] = str(val)

    check_choice('category', VALID_CATEGORIES)
    check_choice('type', VALID_TYPES)
    check_choice('gold', VALID_GOLDS)

    # Carat validation depends on category
    carat = data.get('carat')
    cat = cleaned.get('category') or str(data.get('category', ''))
    if carat is None:
        if not partial:
            errors.append('carat is required')
    else:
        valid_c = VALID_CARATS_CHAIN if cat == 'chain' else VALID_CARATS
        if str(carat) not in valid_c:
            errors.append('invalid carat')
        else:
            cleaned['carat'] = str(carat)

    # Optional color
    color = data.get('color')
    if color is not None and str(color) not in VALID_COLORS:
        errors.append('invalid color')
    elif color is not None:
        cleaned['color'] = str(color)

    # Ring size
    ring_size = data.get('ringSize')
    if ring_size is not None:
        try:
            ring_size = float(ring_size)
        except (TypeError, ValueError):
            ring_size = -1
        if not (RING_SIZE_MIN <= ring_size <= RING_SIZE_MAX):
            errors.append('invalid ringSize')
        else:
            cleaned['ringSize'] = ring_size

    if not partial and cleaned.get('category') == 'ring' and 'ringSize' not in cleaned:
        errors.append('ringSize is required for rings')

    return cleaned, ('; '.join(errors) if errors else None)

# ── API ───────────────────────────────────────────────────────────────────────

@app.route('/api/prices')
@login_required
def api_prices():
    raw, source = get_metal_prices()
    per_gram = {gold: raw[METAL_SYMBOL[gold]] * PURITY_MULTIPLIER[gold]
                for gold in VALID_GOLDS}
    return jsonify({'diamond': DIAMOND_PRICE, 'perGram': per_gram, 'source': source})

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/calculator')
@login_required
def calculator():
    edit_id = request.args.get('edit_id')
    edit_sub = None
    if edit_id:
        edit_sub = Submission.query.get(edit_id)
        if not edit_sub or edit_sub.user_id != current_user.id or edit_sub.status != 'pending':
            flash("無法編輯該訂單 (Invalid or unauthorized order).")
            return redirect(url_for('history'))
    return render_template('index.html', edit_sub=edit_sub)

@app.route('/success')
@login_required
def success():
    return render_template('success.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username and is_locked_out(username):
            flash('登入失敗次數過多，請 5 分鐘後再試。 (Too many failed attempts, try again in 5 minutes.)')
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            record_login_success(username)
            login_user(user)
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                return redirect(next_page)
            if user.role == 'admin':
                return redirect(url_for('admin'))
            return redirect(url_for('calculator'))
        else:
            if username:
                record_login_failure(username)
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        store_name = request.form.get('store_name')
        username = request.form.get('username')
        password = request.form.get('password')

        if User.query.filter_by(username=username).first():
            flash('該帳號已被使用，請選擇其他帳號。')
            return redirect(url_for('register'))

        new_user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role='provider',
            store_name=store_name
        )
        db.session.add(new_user)
        try:
            db.session.commit()
            flash('註冊成功！請登入。')
            return redirect(url_for('login'))
        except Exception:
            db.session.rollback()
            flash('發生錯誤，請稍後再試。')

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/submit', methods=['POST'])
@login_required
def submit():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'status': 'error', 'message': 'invalid JSON'}), 400
    cleaned, error = validate_submission_fields(data)
    if error:
        return jsonify({'status': 'error', 'message': error}), 400

    try:
        weight_chin = lookup_weight(cleaned['category'], cleaned['type'], cleaned['gold'], cleaned['carat'])
    except KeyError:
        return jsonify({'status': 'error', 'message': 'no weight data for this combination'}), 400

    weight_grams = weight_chin * CHIN_TO_GRAMS

    try:
        total_price, rate_used, price_source = compute_total(
            cleaned['carat'], cleaned['gold'], weight_grams,
            cleaned['category'], cleaned.get('ringSize')
        )
    except Exception:
        return jsonify({'status': 'error', 'message': 'pricing error'}), 400

    submission = Submission(
        user_id=current_user.id,
        category=cleaned['category'],
        carat=cleaned['carat'],
        style_type=cleaned['type'],
        gold_purity=cleaned['gold'],
        color=cleaned.get('color'),
        weight=weight_grams,
        ring_size=cleaned.get('ringSize'),
        total_price=total_price,
        gold_rate_per_gram=rate_used,
        price_source=price_source
    )
    db.session.add(submission)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Selection confirmed and saved.',
                    'total_price': submission.total_price})

@app.route('/history')
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    pagination = Submission.query.filter_by(user_id=current_user.id) \
        .order_by(Submission.created_at.desc()) \
        .paginate(page=page, per_page=PAGE_SIZE, error_out=False)
    return render_template('history.html', submissions=pagination.items, pagination=pagination)

@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('calculator'))
    page = request.args.get('page', 1, type=int)
    pagination = Submission.query.order_by(Submission.created_at.desc()) \
        .paginate(page=page, per_page=PAGE_SIZE, error_out=False)
    return render_template('admin.html', submissions=pagination.items, pagination=pagination)

@app.route('/admin/update_status/<int:id>', methods=['POST'])
@login_required
def admin_update_status(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    sub = Submission.query.get_or_404(id)
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'success': False, 'message': 'invalid JSON'}), 400
    new_status = data.get('status')

    if new_status in ['pending', 'confirmed', 'processing', 'completed']:
        sub.status = new_status
        db.session.commit()
        return jsonify({'success': True})

    return jsonify({'success': False, 'message': 'Invalid status'}), 400

@app.route('/delete/<int:id>', methods=['POST'])
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

@app.route('/edit/<int:id>', methods=['POST'])
@login_required
def edit_submission(id):
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

    try:
        weight_chin = lookup_weight(cleaned['category'], cleaned['type'], cleaned['gold'], cleaned['carat'])
    except KeyError:
        return jsonify({'success': False, 'message': 'no weight data for this combination'}), 400

    weight_grams = weight_chin * CHIN_TO_GRAMS

    sub.category = cleaned['category']
    sub.carat = cleaned['carat']
    sub.style_type = cleaned['type']
    sub.gold_purity = cleaned['gold']
    sub.color = cleaned.get('color')
    sub.weight = weight_grams
    sub.ring_size = cleaned.get('ringSize')

    try:
        sub.total_price, sub.gold_rate_per_gram, sub.price_source = compute_total(
            sub.carat, sub.gold_purity, sub.weight, sub.category, sub.ring_size
        )
    except Exception:
        return jsonify({'success': False, 'message': 'pricing error'}), 400

    sub.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    return jsonify({'success': True})

if __name__ == '__main__':
    if os.environ.get('FLASK_DEBUG') == '1':
        app.run(debug=True)
    else:
        if os.environ.get('SECRET_KEY') is None:
            raise SystemExit(
                "Refusing to start in production mode without SECRET_KEY set. "
                "Set FLASK_DEBUG=1 for local dev, or set SECRET_KEY for production."
            )
        from waitress import serve
        port = int(os.environ.get('PORT', 8000))
        print(f"Serving on http://127.0.0.1:{port}")
        serve(app, host='127.0.0.1', port=port)
