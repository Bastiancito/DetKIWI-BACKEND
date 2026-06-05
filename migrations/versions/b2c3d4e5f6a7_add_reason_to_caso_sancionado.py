"""Add reason to caso_sancionado

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-29 12:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('caso_sancionado', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reason', sa.String(length=200), nullable=True))


def downgrade():
    with op.batch_alter_table('caso_sancionado', schema=None) as batch_op:
        batch_op.drop_column('reason')