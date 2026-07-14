"""invites and price breakdown

Revision ID: c3e7a1b9d4f2
Revises: b8d3e1f4a2c6
Create Date: 2026-07-11

"""
from alembic import op
import sqlalchemy as sa


revision = 'c3e7a1b9d4f2'
down_revision = 'b8d3e1f4a2c6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'invite_code',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=32), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('used_by_id', sa.Integer(), nullable=True),
        sa.Column('use_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_uses', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id']),
        sa.ForeignKeyConstraint(['used_by_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    with op.batch_alter_table('submission', schema=None) as batch_op:
        batch_op.add_column(sa.Column('diamond_price_twd', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('taijin_price_twd', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('labor_price_twd', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('tax_amount_twd', sa.Float(), nullable=True))
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'))
        batch_op.add_column(sa.Column('last_login_at', sa.DateTime(), nullable=True))
    op.create_index('ix_submission_user_id', 'submission', ['user_id'])
    op.create_index('ix_submission_status', 'submission', ['status'])
    op.create_index('ix_user_notification_user_id', 'user_notification', ['user_id'])
    op.create_index('ix_product_is_published', 'product', ['is_published'])


def downgrade():
    op.drop_index('ix_product_is_published', table_name='product')
    op.drop_index('ix_user_notification_user_id', table_name='user_notification')
    op.drop_index('ix_submission_status', table_name='submission')
    op.drop_index('ix_submission_user_id', table_name='submission')
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('last_login_at')
        batch_op.drop_column('is_active')
    with op.batch_alter_table('submission', schema=None) as batch_op:
        batch_op.drop_column('tax_amount_twd')
        batch_op.drop_column('labor_price_twd')
        batch_op.drop_column('taijin_price_twd')
        batch_op.drop_column('diamond_price_twd')
    op.drop_table('invite_code')
