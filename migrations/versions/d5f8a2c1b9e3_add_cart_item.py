"""add cart_item table

Revision ID: d5f8a2c1b9e3
Revises: c3e7a1b9d4f2
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa


revision = 'd5f8a2c1b9e3'
down_revision = 'c3e7a1b9d4f2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'cart_item',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('category', sa.String(length=20), nullable=False),
        sa.Column('style_type', sa.String(length=50), nullable=False),
        sa.Column('config_json', sa.Text(), nullable=False),
        sa.Column('summary_zh', sa.String(length=200), nullable=True),
        sa.Column('total_price', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['product.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cart_item_user_id', 'cart_item', ['user_id'])


def downgrade():
    op.drop_index('ix_cart_item_user_id', table_name='cart_item')
    op.drop_table('cart_item')
