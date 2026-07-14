"""add product listings

Revision ID: 7c2a4e9f1b3d
Revises: 43d7940e85b9
Create Date: 2026-07-10 15:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c2a4e9f1b3d'
down_revision = '43d7940e85b9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('product',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('category', sa.String(length=50), nullable=False),
    sa.Column('name_zh', sa.String(length=150), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=True),
    sa.Column('description_zh', sa.Text(), nullable=True),
    sa.Column('description_en', sa.Text(), nullable=True),
    sa.Column('default_color', sa.String(length=20), nullable=False),
    sa.Column('is_published', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('product_variant',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('gold', sa.String(length=20), nullable=False),
    sa.Column('carat', sa.String(length=20), nullable=False),
    sa.Column('weight_chin', sa.Float(), nullable=False),
    sa.Column('manual_price_twd', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('product_id', 'gold', 'carat', name='uq_variant_product_gold_carat')
    )
    op.create_table('product_image',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('color', sa.String(length=20), nullable=False),
    sa.Column('file_path', sa.String(length=300), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('product_id', 'color', name='uq_image_product_color')
    )
    with op.batch_alter_table('submission', schema=None) as batch_op:
        batch_op.add_column(sa.Column('product_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_submission_product_id', 'product', ['product_id'], ['id'])


def downgrade():
    with op.batch_alter_table('submission', schema=None) as batch_op:
        batch_op.drop_constraint('fk_submission_product_id', type_='foreignkey')
        batch_op.drop_column('product_id')
    op.drop_table('product_image')
    op.drop_table('product_variant')
    op.drop_table('product')
