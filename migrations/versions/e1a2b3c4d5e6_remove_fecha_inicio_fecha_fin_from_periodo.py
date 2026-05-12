"""remove fecha_inicio y fecha_fin de periodo

Revision ID: e1a2b3c4d5e6
Revises: d4059e76e6da
Create Date: 2026-03-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1a2b3c4d5e6'
down_revision = 'd4059e76e6da'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('periodo', schema=None) as batch_op:
        batch_op.drop_column('fecha_inicio')
        batch_op.drop_column('fecha_fin')


def downgrade():
    with op.batch_alter_table('periodo', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fecha_fin', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('fecha_inicio', sa.DateTime(), nullable=True))
