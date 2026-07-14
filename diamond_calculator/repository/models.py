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
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime, nullable=True)

class Product(db.Model):
    """A listing (style) an admin manages, within one of the 5 fixed categories."""
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    name_zh = db.Column(db.String(150), nullable=False)
    name_en = db.Column(db.String(150), nullable=True)
    description_zh = db.Column(db.Text, nullable=True)
    description_en = db.Column(db.Text, nullable=True)
    default_color = db.Column(db.String(20), nullable=False, default='white')
    is_published = db.Column(db.Boolean, nullable=False, default=False)
    first_published_at = db.Column(db.DateTime, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = db.Column(db.DateTime,
                            default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
                            onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    created_by = db.relationship('User')
    variants = db.relationship('ProductVariant', backref='product',
                                cascade='all, delete-orphan', lazy=True,
                                order_by='ProductVariant.id')
    images = db.relationship('ProductImage', backref='product',
                              cascade='all, delete-orphan', lazy=True,
                              order_by='ProductImage.sort_order, ProductImage.id')

    def image_map(self):
        """{color: file_path} — first image per color (thumbnail)."""
        out = {}
        for img in self.images:
            out.setdefault(img.color, img.file_path)
        return out

    def images_by_color(self):
        """{color: [file_path, ...]} in sort order."""
        out = {}
        for img in self.images:
            out.setdefault(img.color, []).append(img.file_path)
        return out

    def variant_lookup(self):
        """{(gold, carat): ProductVariant} for quick pricing lookups."""
        return {(v.gold, v.carat): v for v in self.variants}


class ProductVariant(db.Model):
    """One metal+carat combination a listing offers, with its metal weight."""
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    gold = db.Column(db.String(20), nullable=False)
    carat = db.Column(db.String(20), nullable=False)
    weight_chin = db.Column(db.Float, nullable=False)
    manual_price_twd = db.Column(db.Float, nullable=True)

    __table_args__ = (
        db.UniqueConstraint('product_id', 'gold', 'carat', name='uq_variant_product_gold_carat'),
    )


class ProductImage(db.Model):
    """One uploaded photo for a listing color; multiple rows per color allowed."""
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    color = db.Column(db.String(20), nullable=False)
    file_path = db.Column(db.String(300), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    category = db.Column(db.String(50), nullable=True)
    carat = db.Column(db.String(50), nullable=True)
    style_type = db.Column(db.String(50), nullable=True)
    gold_purity = db.Column(db.String(50), nullable=True)
    color = db.Column(db.String(20), nullable=True)
    diamond_kind = db.Column(db.String(20), nullable=False, default='white')
    fancy_color = db.Column(db.String(20), nullable=True)
    stone_count = db.Column(db.Integer, nullable=True)
    diamond_shape = db.Column(db.String(20), nullable=False, default='round')
    weight = db.Column(db.Float, nullable=True)
    ring_size = db.Column(db.Float, nullable=True)
    engraving_band = db.Column(db.String(10), nullable=True)
    engraving_girdle = db.Column(db.String(10), nullable=True)
    include_chain = db.Column(db.Boolean, nullable=False, default=False)
    chain_product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    chain_gold = db.Column(db.String(20), nullable=True)
    chain_color = db.Column(db.String(20), nullable=True)
    chain_length_cm = db.Column(db.Integer, nullable=True)
    chain_weight_chin = db.Column(db.Float, nullable=True)
    chain_total_twd = db.Column(db.Float, nullable=True)
    cancel_reason = db.Column(db.String(500), nullable=True)
    diamond_price_twd = db.Column(db.Float, nullable=True)
    taijin_price_twd = db.Column(db.Float, nullable=True)
    labor_price_twd = db.Column(db.Float, nullable=True)
    tax_amount_twd = db.Column(db.Float, nullable=True)
    total_price = db.Column(db.Float, nullable=True)
    gold_rate_per_gram = db.Column(db.Float, nullable=True)
    price_source = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = db.Column(db.DateTime, nullable=True)
    user = db.relationship('User', backref=db.backref('submissions', lazy=True))
    product = db.relationship('Product', foreign_keys=[product_id])
    chain_product = db.relationship('Product', foreign_keys=[chain_product_id])

    def subtotal_before_tax(self, tax_rate=0.05):
        """Pre-tax subtotal for display; uses breakdown when available."""
        if self.tax_amount_twd is not None and self.total_price is not None:
            return self.total_price - self.tax_amount_twd
        if self.total_price is not None:
            return self.total_price
        return None

    def display_tax(self, tax_rate=0.05):
        if self.tax_amount_twd is not None:
            return self.tax_amount_twd
        if self.total_price is not None:
            return self.total_price * tax_rate
        return None

    def display_total_with_tax(self, tax_rate=0.05):
        if self.tax_amount_twd is not None and self.total_price is not None:
            return self.total_price
        if self.total_price is not None:
            return self.total_price * (1 + tax_rate)
        return None


class InviteCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    used_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    use_count = db.Column(db.Integer, nullable=False, default=0)
    max_uses = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    # When true, accounts registered with this code get role=admin.
    grants_admin = db.Column(db.Boolean, nullable=False, default=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    created_by = db.relationship('User', foreign_keys=[created_by_id])
    used_by = db.relationship('User', foreign_keys=[used_by_id])


class UserNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    kind = db.Column(db.String(32), nullable=False, default='order_removed')
    message = db.Column(db.String(500), nullable=False)
    order_id = db.Column(db.Integer, nullable=True)
    order_summary = db.Column(db.String(200), nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    user = db.relationship('User', backref=db.backref('notifications', lazy=True))


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    category = db.Column(db.String(20), nullable=False)
    style_type = db.Column(db.String(50), nullable=False)
    config_json = db.Column(db.Text, nullable=False)
    summary_zh = db.Column(db.String(200), nullable=True)
    total_price = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    user = db.relationship('User', backref=db.backref('cart_items', lazy=True, cascade='all, delete-orphan'))
    product = db.relationship('Product', foreign_keys=[product_id])


class FavoriteItem(db.Model):
    """A user's reusable saved shop configuration."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    category = db.Column(db.String(20), nullable=False)
    style_type = db.Column(db.String(50), nullable=False)
    config_json = db.Column(db.Text, nullable=False)
    summary_zh = db.Column(db.String(200), nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
    user = db.relationship(
        'User', backref=db.backref('favorite_items', lazy=True, cascade='all, delete-orphan'),
    )
    product = db.relationship('Product', foreign_keys=[product_id])
