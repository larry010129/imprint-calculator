"""add diamond color and shape fields

Revision ID: a4f2c8d1e9b0
Revises: 9e1c6b8a2d4f
Create Date: 2026-07-10 18:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'a4f2c8d1e9b0'
down_revision = '9e1c6b8a2d4f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('submission', schema=None) as batch_op:
        batch_op.add_column(sa.Column('diamond_kind', sa.String(length=20), nullable=False, server_default='white'))
        batch_op.add_column(sa.Column('fancy_color', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('stone_count', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('diamond_shape', sa.String(length=20), nullable=False, server_default='round'))


def downgrade():
    with op.batch_alter_table('submission', schema=None) as batch_op:
        batch_op.drop_column('diamond_shape')
        batch_op.drop_column('stone_count')
        batch_op.drop_column('fancy_color')
        batch_op.drop_column('diamond_kind')
