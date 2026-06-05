"""merge heads

Revision ID: 20260602_merge_heads
Revises: 20260602_add_url_moss_to_reporte, 20260602_drop_descripcion_sancion
Create Date: 2026-06-02 13:59:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge20260602'
down_revision = ('20260602_add_url_moss_to_reporte','ddesc2026')
branch_labels = None
depends_on = None


def upgrade():
    # merge-only revision: no DB changes
    pass


def downgrade():
    # no-op
    pass
