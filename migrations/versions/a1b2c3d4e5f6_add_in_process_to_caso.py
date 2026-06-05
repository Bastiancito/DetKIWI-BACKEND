"""Add in_process to caso

Revision ID: a1b2c3d4e5f6
Revises: 460d657e178f
Create Date: 2026-05-29 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '460d657e178f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('caso', schema=None) as batch_op:
        batch_op.add_column(sa.Column('in_process', sa.Boolean(), nullable=True))


def downgrade():
    with op.batch_alter_table('caso', schema=None) as batch_op:
        batch_op.drop_column('in_process')