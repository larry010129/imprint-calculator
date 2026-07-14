"""invite grants_admin

Revision ID: g8c3d5e2f4a1
Revises: f7b2c4d8e1a3
Create Date: 2026-07-14

"""
from alembic import op
import sqlalchemy as sa


revision = 'g8c3d5e2f4a1'
down_revision = 'f7b2c4d8e1a3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('invite_code', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('grants_admin', sa.Boolean(), nullable=False, server_default='0')
        )


def downgrade():
    with op.batch_alter_table('invite_code', schema=None) as batch_op:
        batch_op.drop_column('grants_admin')
