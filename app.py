from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect
from datetime import datetime, timedelta
import os, json, time, urllib.request
from models import db, User, Submission

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

csrf = CSRFProtect(app)

db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

from flask_wtf.csrf import CSRFError

def wants_json():
    # fetch callers send JSON or the CSRF header; browser form posts do neither
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

@app.template_filter('tz_taiwan')
def tz_taiwan(dt):
    if not dt: return ''
    return (dt + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')

@app.template_filter('label_category')
def label_category(cat):
    if not cat: return ''
    return {'ring': '戒指 (Ring)', 'necklace': '項鍊 (Necklace)'}.get(cat, cat)

@app.template_filter('label_style')
def label_style(style):
    if not style: return ''
    return {'A': '款式A', 'B': '款式B', 'C': '款式C'}.get(style, style)

@app.template_filter('label_purity')
def label_purity(purity):
    if not purity: return ''
    return {'18k': '18K金', '999': '純金999', 'pt': '鉑金 Pt', 'silver925': '925銀'}.get(purity, purity)

GOLDAPI_KEY = os.environ.get('GOLDAPI_KEY', 'goldapi-eb915d55941859c5bec9d3d1cbaff238-io')

DIAMOND_PRICE = {"0.1": 24000, "0.3": 79000, "0.5": 98000, "1": 250000}
PURITY_MULTIPLIER = {"18k": 0.75, "999": 0.999, "pt": 1, "silver925": 0.925}
METAL_SYMBOL = {"18k": "XAU", "999": "XAU", "pt": "XPT", "silver925": "XAG"}
FALLBACK_TWD_PER_GRAM = {"XAU": 2400, "XPT": 1050, "XAG": 30}
TROY_OZ_GRAMS = 31.1034768

_price_cache = {"prices": None, "fetched_at": 0, "source": "fallback"}
PRICE_TTL_SECONDS = 600

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

@app.route('/api/prices')
@login_required
def api_prices():
    raw, source = get_metal_prices()
    per_gram = {gold: raw[METAL_SYMBOL[gold]] * PURITY_MULTIPLIER[gold]
                for gold in PURITY_MULTIPLIER}
    return jsonify({'diamond': DIAMOND_PRICE, 'perGram': per_gram, 'source': source})

def compute_total(carat, gold, weight_grams):
    raw, _ = get_metal_prices()
    per_gram = raw[METAL_SYMBOL[gold]] * PURITY_MULTIPLIER[gold]
    return DIAMOND_PRICE[carat] + per_gram * weight_grams

VALID_CATEGORIES = {'ring', 'necklace'}
VALID_CARATS = {'0.1', '0.3', '0.5', '1'}
VALID_TYPES = {'A', 'B', 'C'}
VALID_GOLDS = {'18k', '999', 'pt', 'silver925'}
MAX_WEIGHT_GRAMS = 10000
RING_SIZE_MIN, RING_SIZE_MAX = 5, 25

def validate_submission_fields(data, partial=False):
    errors = []
    cleaned = {}

    def check_choice(key, valid):
        val = data.get(key)
        if val is None:
            if not partial:
                errors.append(f'{key} is required')
        elif str(val) not in valid:
            errors.append(f'invalid {key}')
        else:
            cleaned[key] = str(val)

    check_choice('category', VALID_CATEGORIES)
    check_choice('carat', VALID_CARATS)
    check_choice('type', VALID_TYPES)
    check_choice('gold', VALID_GOLDS)

    weight = data.get('weight')
    if weight is None:
        if not partial:
            errors.append('weight is required')
    else:
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            weight = -1
        if not (0 < weight <= MAX_WEIGHT_GRAMS):
            errors.append('invalid weight')
        else:
            cleaned['weight'] = weight

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
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                return redirect(next_page)
            if user.role == 'admin':
                return redirect(url_for('admin'))
            return redirect(url_for('calculator'))
        else:
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
        total_price = compute_total(cleaned['carat'], cleaned['gold'], cleaned['weight'])
    except Exception:
        return jsonify({'status': 'error', 'message': 'invalid selection'}), 400

    submission = Submission(
        user_id=current_user.id,
        category=cleaned['category'],
        carat=cleaned['carat'],
        style_type=cleaned['type'],
        gold_purity=cleaned['gold'],
        weight=cleaned['weight'],
        ring_size=cleaned.get('ringSize'),
        total_price=total_price
    )
    db.session.add(submission)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Selection confirmed and saved.', 'total_price': submission.total_price})

@app.route('/history')
@login_required
def history():
    submissions = Submission.query.filter_by(user_id=current_user.id).order_by(Submission.created_at.desc()).all()
    return render_template('history.html', submissions=submissions)

@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('calculator'))
    submissions = Submission.query.order_by(Submission.created_at.desc()).all()
    return render_template('admin.html', submissions=submissions)

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
        
    sub.category = cleaned['category']
    sub.carat = cleaned['carat']
    sub.style_type = cleaned['type']
    sub.gold_purity = cleaned['gold']
    sub.weight = cleaned['weight']
    sub.ring_size = cleaned.get('ringSize')
    
    try:
        # ponytail: edit reprices at current metal rate; store rate-at-submit if order locking matters
        sub.total_price = compute_total(sub.carat, sub.gold_purity, sub.weight)
    except Exception:
        return jsonify({'success': False, 'message': 'invalid selection'}), 400
        
    db.session.commit()
    return jsonify({'success': True})

if __name__ == '__main__':
    if os.environ.get('FLASK_DEBUG') == '1':
        app.run(debug=True)
    else:
        from waitress import serve
        port = int(os.environ.get('PORT', 8000))
        print(f"Serving on http://127.0.0.1:{port}")
        serve(app, host='127.0.0.1', port=port)
