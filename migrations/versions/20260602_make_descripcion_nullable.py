"""make descripcion_sancion nullable

Revision ID: 20260602_make_descripcion_nullable
Revises: 85ac37daac05
Create Date: 2026-06-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'mdesca2026'
down_revision = '85ac37daac05'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('caso_sancionado', schema=None) as batch_op:
        batch_op.alter_column('descripcion_sancion', existing_type=sa.String(length=200), nullable=True)


def downgrade():
    with op.batch_alter_table('caso_sancionado', schema=None) as batch_op:
        batch_op.alter_column('descripcion_sancion', existing_type=sa.String(length=200), nullable=False)
