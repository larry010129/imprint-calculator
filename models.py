from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='provider') # 'admin' or 'provider'
    store_name = db.Column(db.String(150), nullable=True)

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(50), nullable=True)
    carat = db.Column(db.String(50), nullable=True)
    style_type = db.Column(db.String(50), nullable=True)
    gold_purity = db.Column(db.String(50), nullable=True)
    color = db.Column(db.String(20), nullable=True)
    weight = db.Column(db.Float, nullable=True)
    ring_size = db.Column(db.Float, nullable=True)
    total_price = db.Column(db.Float, nullable=True)
    gold_rate_per_gram = db.Column(db.Float, nullable=True)
    price_source = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = db.Column(db.DateTime, nullable=True)
    user = db.relationship('User', backref=db.backref('submissions', lazy=True))
