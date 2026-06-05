"""add cancelacion fields to caso_sancionado

Revision ID: c1d2e3f4a5b6
Revises: b2c3d4e5f6a7
Create Date: 2026-05-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1d2e3f4a5b6'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('caso_sancionado', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cancelado', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('fecha_cancelacion', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('cancelado_por', sa.Integer(), nullable=True))

    op.execute("UPDATE caso_sancionado SET cancelado = false WHERE cancelado IS NULL")


def downgrade():
    with op.batch_alter_table('caso_sancionado', schema=None) as batch_op:
        batch_op.drop_column('cancelado_por')
        batch_op.drop_column('fecha_cancelacion')
        batch_op.drop_column('cancelado')
