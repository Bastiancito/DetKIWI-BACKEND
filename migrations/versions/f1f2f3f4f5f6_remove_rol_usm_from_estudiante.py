"""remove rol_usm from estudiante

Revision ID: f1f2f3f4f5f6
Revises: e1a2b3c4d5e6
Create Date: 2026-05-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1f2f3f4f5f6'
down_revision = '9f3a2d8b7c1e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('estudiante', schema=None) as batch_op:
        batch_op.drop_column('rol_usm')


def downgrade():
    with op.batch_alter_table('estudiante', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rol_usm', sa.String(length=20), nullable=False))
        batch_op.create_unique_constraint('uq_estudiante_rol_usm', ['rol_usm'])
