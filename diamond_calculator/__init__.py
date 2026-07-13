import logging
import os
import secrets
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, flash, g, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy.exc import OperationalError
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash

from diamond_calculator.application.bot_metal_feed import fetch_taiwan_bank_prices, get_bot_gold_display
from diamond_calculator.application.rate_limit import limiter
from diamond_calculator.module_assets import (
    build_template_loader,
    register_module_static_blueprints,
    register_template_globals,
)
from diamond_calculator.filters import register_filters
from diamond_calculator.gateway.routes import bp as main_bp
from diamond_calculator.repository.models import CartItem, User, UserNotification, db

ROOT = Path(__file__).resolve().parent.parent
TAIPEI = ZoneInfo('Asia/Taipei')
_price_sync_started = False
migrate = Migrate()


def _is_debug_mode():
    return os.environ.get('FLASK_DEBUG', '0') == '1'


def _configure_logging(app):
    level_name = os.environ.get('LOG_LEVEL', 'DEBUG' if app.debug else 'INFO')
    level = getattr(logging, level_name.upper(), logging.INFO)

    handlers = [logging.StreamHandler()]
    log_file = os.environ.get('LOG_FILE')
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

    logging.basicConfig(
        level=level,
        format='%(asctime)s %(levelname)-7s [%(name)s] %(message)s',
        handlers=handlers,
        force=True,
    )
    logging.getLogger('diamond_calculator.audit').setLevel(logging.INFO)


def _should_run_background_jobs(app):
    if os.environ.get('DISABLE_PRICE_SCHEDULER'):
        return False
    if not app.debug:
        return True
    return os.environ.get('WERKZEUG_RUN_MAIN') == 'true'


def _seconds_until_next_taipei_sync(hour=3, minute=0):
    now = datetime.now(TAIPEI)
    nxt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(days=1)
    return (nxt - now).total_seconds()


def _init_price_scheduler(app):
    global _price_sync_started

    if _price_sync_started:
        return

    def daily_sync_loop():
        # The very first sync also happens on this background thread (not
        # inline in create_app()): it clears a real bot challenge via a
        # headless browser and can take up to ~75s, which would otherwise
        # delay the whole app from starting to serve requests.
        with app.app_context():
            fetch_taiwan_bank_prices()
        while True:
            time.sleep(_seconds_until_next_taipei_sync())
            with app.app_context():
                fetch_taiwan_bank_prices()

    threading.Thread(target=daily_sync_loop, daemon=True, name='bot-price-sync').start()
    _price_sync_started = True


def create_app():
    app = Flask(
        __name__,
        template_folder=str(ROOT / 'layout' / 'templates'),
        static_folder=str(ROOT / 'static'),
    )
    app.jinja_loader = build_template_loader()
    register_module_static_blueprints(app)
    register_template_globals(app)
    app.debug = _is_debug_mode()
    _configure_logging(app)

    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        if app.debug:
            # Ephemeral per-process key: fine for local dev, but sessions won't
            # survive a restart. Set SECRET_KEY in .env if you want them to.
            secret_key = secrets.token_hex(32)
        else:
            raise RuntimeError(
                'Refusing to start: SECRET_KEY is not set. Set it in your environment '
                'or .env file (generate one with '
                '`python -c "import secrets; print(secrets.token_hex(32))"`). '
                'A SECRET_KEY is only optional when FLASK_DEBUG=1 for local development.'
            )
    app.config['SECRET_KEY'] = secret_key

    db_uri = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
    # Render / Heroku often provide postgres:// — SQLAlchemy + psycopg3 need
    # postgresql+psycopg:// (or at least postgresql://).
    if db_uri.startswith('postgres://'):
        db_uri = 'postgresql+psycopg://' + db_uri[len('postgres://'):]
    elif db_uri.startswith('postgresql://') and '+psycopg' not in db_uri:
        db_uri = 'postgresql+psycopg://' + db_uri[len('postgresql://'):]
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # Postgres (and other server DBs) can drop idle connections after restarts,
    # maintenance, or pooler timeouts. Pre-ping validates before checkout;
    # recycle avoids holding connections longer than the server allows.
    if not db_uri.startswith('sqlite'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', '300')),
        }

    # Admin product-listing forms can carry several image uploads (up to
    # 5MB each, validated again per-file in application/uploads.py) plus
    # variant/field data in one multipart request.
    app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

    # Trust exactly one reverse-proxy hop (e.g. nginx) for X-Forwarded-* headers
    # so request.remote_addr / request.is_secure / url_for(_external=True) are
    # correct in production. Set TRUSTED_PROXY_COUNT=0 if serving directly.
    trusted_proxy_count = int(os.environ.get('TRUSTED_PROXY_COUNT', '1'))
    if trusted_proxy_count > 0:
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=trusted_proxy_count,
            x_proto=trusted_proxy_count,
            x_host=trusted_proxy_count,
        )

    # Session cookie hardening. SESSION_COOKIE_SECURE is relaxed in debug mode
    # so local http:// development still works; production (behind TLS) requires it.
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = not app.debug
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)

    CSRFProtect(app)
    limiter.init_app(app)

    @limiter.request_filter
    def _skip_limiter_when_testing():
        return app.testing

    db.init_app(app)
    migrate.init_app(app, db)

    @app.before_request
    def generate_csp_nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def inject_csp_nonce():
        return {'csp_nonce': getattr(g, 'csp_nonce', '')}

    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=(self)'
        # Scripts: only same-origin files and inline blocks carrying this
        # request's nonce may run — injected scripts (XSS) are blocked.
        nonce = getattr(g, 'csp_nonce', '')
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}' 'wasm-unsafe-eval'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' blob:; "
            "worker-src 'self' blob:; "
            "media-src 'self' blob:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'"
        )
        if not app.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    login_manager = LoginManager()
    login_manager.login_view = 'main.login'
    login_manager.init_app(app)

    def wants_json():
        return request.is_json or request.headers.get('X-CSRFToken') is not None

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        if wants_json():
            return jsonify({'success': False, 'status': 'error',
                            'message': 'session expired, please reload the page'}), 400
        flash('表單已過期，請重新送出。')
        return redirect(request.full_path.rstrip('?') or url_for('main.login'))

    @login_manager.unauthorized_handler
    def handle_unauthorized():
        if wants_json():
            return jsonify({'success': False, 'status': 'error', 'message': 'login required'}), 401
        return redirect(url_for('main.login', next=request.full_path.rstrip('?')))

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    def _wants_json_error():
        return request.is_json or request.path.startswith('/api/')

    @app.errorhandler(404)
    def handle_not_found(e):
        if _wants_json_error():
            return jsonify({'success': False, 'status': 'error', 'message': 'not found'}), 404
        return render_template('errors/404.html'), 404

    def _safe_referrer():
        # Only bounce back to same-site referrers; anything else goes home.
        ref = request.referrer
        if ref and ref.startswith(request.host_url):
            return ref
        return url_for('main.home')

    @app.errorhandler(OperationalError)
    def handle_db_operational_error(e):
        db.session.rollback()
        app.logger.warning('Database connection lost (%s); client should retry', e.orig)
        if _wants_json_error():
            return jsonify({
                'success': False,
                'status': 'error',
                'message': 'database temporarily unavailable, please retry',
            }), 503
        flash('資料庫連線中斷，請重新整理頁面後再試。')
        return redirect(_safe_referrer())

    @app.errorhandler(500)
    def handle_server_error(e):
        # Never leak stack traces/tracebacks to the client; full details still
        # go to the server logs via Flask's default exception logging.
        app.logger.exception('Unhandled server error on %s %s', request.method, request.path)
        # A DB error may have left the session mid-transaction; roll back so
        # rendering the error page itself (which queries for nav context) works.
        db.session.rollback()
        if _wants_json_error():
            return jsonify({'success': False, 'status': 'error', 'message': 'internal server error'}), 500
        return render_template('errors/500.html'), 500

    # User-facing titles/descriptions for common HTTP errors, so visitors never
    # see Werkzeug's bare default page (which names the framework).
    HTTP_ERROR_COPY = {
        400: ('請求格式錯誤', '伺服器無法處理這個請求，請返回上一頁重試。'),
        403: ('沒有存取權限', '您沒有權限檢視此頁面。'),
        405: ('不支援的操作', '這個頁面不支援該操作方式。'),
        413: ('檔案過大', '上傳的內容超過大小限制，請縮小後再試。'),
        429: ('請求過於頻繁', '操作太頻繁，請稍候幾分鐘後再試。'),
    }

    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        if _wants_json_error():
            return jsonify({'success': False, 'status': 'error', 'message': e.description}), e.code
        if e.code and e.code >= 400:
            title, description = HTTP_ERROR_COPY.get(
                e.code, ('發生錯誤', '請稍後再試。若問題持續發生，請聯絡系統管理員。'))
            try:
                return render_template(
                    'errors/error.html', code=e.code, title=title, description=description,
                ), e.code
            except Exception:
                app.logger.exception('Failed to render error page for HTTP %s', e.code)
        return e

    register_filters(app)
    app.register_blueprint(main_bp)

    @app.context_processor
    def inject_nav_context():
        # Defensive: this runs on EVERY template render, including the error
        # pages themselves. If the DB or gold feed is down, degrade the nav
        # (no gold ticker / badge) instead of crashing the whole render.
        ctx = {'invite_required': False, 'bot_gold': None, 'notification_unread_count': 0, 'cart_count': 0}
        try:
            from diamond_calculator.application.invites import invite_required
            ctx['invite_required'] = invite_required()
            if current_user.is_authenticated:
                ctx['bot_gold'] = get_bot_gold_display()
                ctx['notification_unread_count'] = UserNotification.query.filter_by(
                    user_id=current_user.id, is_read=False,
                ).count()
                ctx['cart_count'] = CartItem.query.filter_by(user_id=current_user.id).count()
        except Exception:
            db.session.rollback()
            app.logger.exception('nav context lookup failed; rendering degraded nav')
        return ctx

    with app.app_context():
        # SQLite (the zero-config dev/small-deployment default) auto-creates its
        # schema for convenience. Any other database (e.g. Postgres in
        # production) is expected to be managed with `flask db upgrade`
        # (Flask-Migrate/Alembic, see migrations/) instead, so schema changes
        # are tracked and reviewable rather than silently applied.
        if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
            db.create_all()
        from diamond_calculator.application.catalog_seed import sync_bracelet_variants
        try:
            sync_bracelet_variants()
        except Exception as exc:
            db.session.rollback()
            app.logger.exception('sync_bracelet_variants failed on startup: %s', exc)
        admin_password = os.environ.get('ADMIN_PASSWORD')
        if admin_password:
            try:
                if User.query.filter_by(username='admin').first() is None:
                    db.session.add(User(
                        username='admin',
                        password_hash=generate_password_hash(admin_password),
                        role='admin',
                        store_name='Admin HQ',
                    ))
                    db.session.commit()
            except Exception as exc:
                db.session.rollback()
                app.logger.exception('Admin seed failed on startup: %s', exc)

    if _should_run_background_jobs(app) and not app.config.get('TESTING'):
        _init_price_scheduler(app)

    return app


__all__ = ['create_app']
