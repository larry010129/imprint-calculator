"""add product first published timestamp

Revision ID: e6a9b4c2d7f1
Revises: d5f8a2c1b9e3
Create Date: 2026-07-13
"""
from alembic import op
import sqlalchemy as sa


revision = 'e6a9b4c2d7f1'
down_revision = 'd5f8a2c1b9e3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('product', sa.Column('first_published_at', sa.DateTime(), nullable=True))
    op.execute(
        "UPDATE product SET first_published_at = created_at "
        "WHERE is_published = true"
    )


def downgrade():
    op.drop_column('product', 'first_published_at')
