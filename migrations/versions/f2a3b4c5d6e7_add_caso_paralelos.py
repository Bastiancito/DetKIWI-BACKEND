"""add caso paralelos association table

Revision ID: f2a3b4c5d6e7
Revises: e0f5d05ea673
Create Date: 2026-05-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f2a3b4c5d6e7'
down_revision = 'e0f5d05ea673'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'caso_paralelos',
        sa.Column('caso_id', sa.Integer(), nullable=False),
        sa.Column('paralelo_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['caso_id'], ['caso.caso_id']),
        sa.ForeignKeyConstraint(['paralelo_id'], ['paralelo.paralelo_id']),
        sa.PrimaryKeyConstraint('caso_id', 'paralelo_id')
    )


def downgrade():
    op.drop_table('caso_paralelos')