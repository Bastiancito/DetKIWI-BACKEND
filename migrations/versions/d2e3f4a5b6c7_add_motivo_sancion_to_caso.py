"""add motivo_sancion to caso

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-05-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd2e3f4a5b6c7'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('caso', schema=None) as batch_op:
        batch_op.add_column(sa.Column('motivo_sancion', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('caso', schema=None) as batch_op:
        batch_op.drop_column('motivo_sancion')
