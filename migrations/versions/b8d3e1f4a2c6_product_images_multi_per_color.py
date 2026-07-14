"""allow multiple product images per color

Revision ID: b8d3e1f4a2c6
Revises: a4f2c8d1e9b0
Create Date: 2026-07-10 20:50:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'b8d3e1f4a2c6'
down_revision = 'a4f2c8d1e9b0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('product_image', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))
        batch_op.drop_constraint('uq_image_product_color', type_='unique')


def downgrade():
    with op.batch_alter_table('product_image', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_image_product_color', ['product_id', 'color'])
        batch_op.drop_column('sort_order')
