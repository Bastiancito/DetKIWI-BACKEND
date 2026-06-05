"""add url_moss to reporte

Revision ID: 20260602_add_url_moss_to_reporte
Revises: d4059e76e6da
Create Date: 2026-06-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260602_add_url_moss_to_reporte'
down_revision = ('20260529_reason_motivo', 'd4059e76e6da')
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('reporte', schema=None) as batch_op:
        batch_op.add_column(sa.Column('url_moss', sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table('reporte', schema=None) as batch_op:
        batch_op.drop_column('url_moss')