"""add favorite_item table

Revision ID: f7b2c4d8e1a3
Revises: e6a9b4c2d7f1
Create Date: 2026-07-13
"""

from alembic import op
import sqlalchemy as sa


revision = 'f7b2c4d8e1a3'
down_revision = 'e6a9b4c2d7f1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'favorite_item',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('category', sa.String(length=20), nullable=False),
        sa.Column('style_type', sa.String(length=50), nullable=False),
        sa.Column('config_json', sa.Text(), nullable=False),
        sa.Column('summary_zh', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['product.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_favorite_item_user_id', 'favorite_item', ['user_id'])


def downgrade():
    op.drop_index('ix_favorite_item_user_id', table_name='favorite_item')
    op.drop_table('favorite_item')
