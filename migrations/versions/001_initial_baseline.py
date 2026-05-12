"""Initial baseline schema

Revision ID: 001_initial_baseline
Revises: 
Create Date: 2025-03-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '001_initial_baseline'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('rol',
    sa.Column('rol_id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=50), nullable=False),
    sa.Column('descripcion', sa.String(length=200), nullable=True),
    sa.PrimaryKeyConstraint('rol_id'),
    sa.UniqueConstraint('nombre')
    )
    
    op.create_table('sede',
    sa.Column('sede_id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=100), nullable=False),
    sa.PrimaryKeyConstraint('sede_id'),
    sa.UniqueConstraint('nombre')
    )
    
    op.create_table('periodo',
    sa.Column('periodo_id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=100), nullable=False),
    sa.Column('anio', sa.Integer(), nullable=False),
    sa.Column('semestre', sa.Integer(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=True),
    sa.Column('fecha_inicio', sa.DateTime(), nullable=True),
    sa.Column('fecha_fin', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('periodo_id'),
    sa.UniqueConstraint('nombre')
    )
    
    op.create_table('paralelo',
    sa.Column('paralelo_id', sa.Integer(), nullable=False),
    sa.Column('sigla_paralelo', sa.String(length=50), nullable=False),
    sa.Column('sede_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['sede_id'], ['sede.sede_id'], ),
    sa.PrimaryKeyConstraint('paralelo_id')
    )
    
    op.create_table('user',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=80), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=False),
    sa.Column('password_hash', sa.String(length=200), nullable=False),
    sa.Column('rol_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['rol_id'], ['rol.rol_id'], ),
    sa.PrimaryKeyConstraint('user_id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('username')
    )
    
    op.create_table('evaluacion',
    sa.Column('evaluacion_id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=200), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=True),
    sa.Column('fecha_creacion', sa.DateTime(), nullable=True),
    sa.Column('fecha_entrega', sa.DateTime(), nullable=True),
    sa.Column('periodo_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['periodo_id'], ['periodo.periodo_id'], ),
    sa.PrimaryKeyConstraint('evaluacion_id')
    )
    
    op.create_table('estudiante',
    sa.Column('estudiante_id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=100), nullable=False),
    sa.Column('apellido', sa.String(length=100), nullable=False),
    sa.Column('rol_usm', sa.String(length=20), nullable=False),
    sa.Column('paralelo_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['paralelo_id'], ['paralelo.paralelo_id'], ),
    sa.PrimaryKeyConstraint('estudiante_id'),
    sa.UniqueConstraint('rol_usm')
    )
    
    op.create_table('user_paralelos',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('paralelo_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['paralelo_id'], ['paralelo.paralelo_id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.user_id'], ),
    sa.PrimaryKeyConstraint('user_id', 'paralelo_id')
    )
    
    op.create_table('reporte',
    sa.Column('reporte_id', sa.Integer(), nullable=False),
    sa.Column('titulo', sa.String(length=200), nullable=False),
    sa.Column('fecha_creacion', sa.DateTime(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('evaluacion_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['evaluacion_id'], ['evaluacion.evaluacion_id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.user_id'], ),
    sa.PrimaryKeyConstraint('reporte_id')
    )
    
    op.create_table('caso',
    sa.Column('caso_id', sa.Integer(), nullable=False),
    sa.Column('reporte_id', sa.Integer(), nullable=True),
    sa.Column('similitud', sa.Float(), nullable=False),
    sa.Column('lineas', sa.Integer(), nullable=False),
    sa.Column('url_moss', sa.String(length=500), nullable=True),
    sa.Column('estado', sa.String(length=50), nullable=True),
    sa.ForeignKeyConstraint(['reporte_id'], ['reporte.reporte_id'], ),
    sa.PrimaryKeyConstraint('caso_id')
    )
    
    op.create_table('caso_estudiantes',
    sa.Column('caso_id', sa.Integer(), nullable=False),
    sa.Column('estudiante_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['caso_id'], ['caso.caso_id'], ),
    sa.ForeignKeyConstraint(['estudiante_id'], ['estudiante.estudiante_id'], ),
    sa.PrimaryKeyConstraint('caso_id', 'estudiante_id')
    )
    
    op.create_table('caso_usuarios',
    sa.Column('caso_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['caso_id'], ['caso.caso_id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.user_id'], ),
    sa.PrimaryKeyConstraint('caso_id', 'user_id')
    )


def downgrade():
    op.drop_table('caso_usuarios')
    op.drop_table('caso_estudiantes')
    op.drop_table('caso')
    op.drop_table('reporte')
    op.drop_table('user_paralelos')
    op.drop_table('estudiante')
    op.drop_table('evaluacion')
    op.drop_table('user')
    op.drop_table('paralelo')
    op.drop_table('periodo')
    op.drop_table('sede')
    op.drop_table('rol')
