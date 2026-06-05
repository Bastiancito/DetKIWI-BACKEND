"""drop descripcion_sancion from caso_sancionado

Revision ID: 20260602_drop_descripcion_sancion
Revises: 20260602_make_descripcion_nullable
Create Date: 2026-06-02 00:05:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ddesc2026'
down_revision = 'mdesca2026'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('caso_sancionado', schema=None) as batch_op:
        batch_op.drop_column('descripcion_sancion')


def downgrade():
    with op.batch_alter_table('caso_sancionado', schema=None) as batch_op:
        batch_op.add_column(sa.Column('descripcion_sancion', sa.String(length=200), nullable=True))
