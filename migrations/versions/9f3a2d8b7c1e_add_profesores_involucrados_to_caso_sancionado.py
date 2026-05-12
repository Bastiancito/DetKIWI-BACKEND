"""add profesores_involucrados to caso_sancionado

Revision ID: 9f3a2d8b7c1e
Revises: 785915a11ad4
Create Date: 2026-04-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9f3a2d8b7c1e'
down_revision = '785915a11ad4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('caso_sancionado', schema=None) as batch_op:
        batch_op.add_column(sa.Column('profesores_involucrados', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('caso_sancionado', schema=None) as batch_op:
        batch_op.drop_column('profesores_involucrados')
