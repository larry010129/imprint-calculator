"""add order customization fields

Revision ID: 9e1c6b8a2d4f
Revises: 7c2a4e9f1b3d
Create Date: 2026-07-10 17:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '9e1c6b8a2d4f'
down_revision = '7c2a4e9f1b3d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('submission', schema=None) as batch_op:
        batch_op.add_column(sa.Column('engraving_band', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('engraving_girdle', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('include_chain', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('chain_product_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('chain_gold', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('chain_color', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('chain_length_cm', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('chain_weight_chin', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('chain_total_twd', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('cancel_reason', sa.String(length=500), nullable=True))
        batch_op.create_foreign_key(
            'fk_submission_chain_product_id', 'product', ['chain_product_id'], ['id'],
        )


def downgrade():
    with op.batch_alter_table('submission', schema=None) as batch_op:
        batch_op.drop_constraint('fk_submission_chain_product_id', type_='foreignkey')
        batch_op.drop_column('cancel_reason')
        batch_op.drop_column('chain_total_twd')
        batch_op.drop_column('chain_weight_chin')
        batch_op.drop_column('chain_length_cm')
        batch_op.drop_column('chain_color')
        batch_op.drop_column('chain_gold')
        batch_op.drop_column('chain_product_id')
        batch_op.drop_column('include_chain')
        batch_op.drop_column('engraving_girdle')
        batch_op.drop_column('engraving_band')
