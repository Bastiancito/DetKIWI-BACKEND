from datetime import datetime
from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

caso_estudiantes = db.Table('caso_estudiantes',
    db.Column('caso_id', db.Integer, db.ForeignKey('caso.caso_id'), primary_key=True),
    db.Column('estudiante_id', db.Integer, db.ForeignKey('estudiante.estudiante_id'), primary_key=True)
)

user_paralelos = db.Table('user_paralelos',
    db.Column('user_id', db.Integer, db.ForeignKey('user.user_id'), primary_key=True),
    db.Column('paralelo_id', db.Integer, db.ForeignKey('paralelo.paralelo_id'), primary_key=True)
)

caso_usuarios = db.Table('caso_usuarios',
    db.Column('caso_id', db.Integer, db.ForeignKey('caso.caso_id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.user_id'), primary_key=True)
)


class Rol(db.Model):
    rol_id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    descripcion = db.Column(db.String(200))

class Sede(db.Model):
    sede_id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    paralelos = db.relationship('Paralelo', backref='sede', lazy=True)

class Paralelo(db.Model):
    paralelo_id = db.Column(db.Integer, primary_key=True)
    sigla_paralelo = db.Column(db.String(200), nullable=False)
    sede_id = db.Column(db.Integer, db.ForeignKey('sede.sede_id'), nullable=True)
    
    usuarios = db.relationship('User', secondary=user_paralelos, backref='paralelos')

class User(db.Model, UserMixin):
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    rol_id = db.Column(db.Integer, db.ForeignKey('rol.rol_id'), nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password, password)
    
    def get_id(self):
        return str(self.user_id)

class Periodo(db.Model):
    """
    Representa un periodo académico (semestre).
    Ej: "2025-1", "2025-2", "2026-1"
    """
    periodo_id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    semestre = db.Column(db.Integer, nullable=False)
    
    activo = db.Column(db.Boolean, default=False)
    
    evaluaciones = db.relationship('Evaluacion', backref='periodo', lazy=True)

class Evaluacion(db.Model):
    """
    Representa una evaluación académica (Tarea, Proyecto, Examen, etc.)
    Cada evaluación pertenece a un periodo específico.
    """
    evaluacion_id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.String(500), nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_entrega = db.Column(db.DateTime, nullable=True)
    periodo_id = db.Column(db.Integer, db.ForeignKey('periodo.periodo_id'), nullable=False)
    activo = db.Column(db.Boolean, default=True)
    
    reportes = db.relationship('Reporte', backref='evaluacion', lazy=True)

class Reporte(db.Model):
    reporte_id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    evaluacion_id = db.Column(db.Integer, db.ForeignKey('evaluacion.evaluacion_id'), nullable=False)
    activo = db.Column(db.Boolean, default=True)
    casos = db.relationship('Caso', backref='reporte', lazy=True)

class Caso(db.Model):
    caso_id = db.Column(db.Integer, primary_key=True)
    reporte_id = db.Column(db.Integer, db.ForeignKey('reporte.reporte_id'), nullable=False)
    
    similitud = db.Column(db.Float, nullable=False)   
    lineas = db.Column(db.Integer, nullable=True)     
    url_moss = db.Column(db.String(500), nullable=True) 
    
    
    involucrados = db.relationship('Estudiante', secondary=caso_estudiantes, backref='casos')
    
    usuarios_asignados = db.relationship('User', secondary=caso_usuarios, backref='casos_asignados')
    closed = db.Column(db.Boolean, default=False)
    sancion = db.Column(db.Boolean, nullable=True)
    caso_metadata = db.Column(db.JSON, nullable=True)
    evaluacion_id = db.Column(db.Integer, db.ForeignKey('evaluacion.evaluacion_id'), nullable=True)
    comentarios_profes = db.Column(db.JSON, nullable=True)
    @property
    def evaluacion(self):
        """Acceso directo a la evaluación del caso via reporte"""
        return self.reporte.evaluacion if self.reporte else None
    
class CasoSancionado(db.Model):
    sancion_id = db.Column(db.Integer, primary_key=True)
    caso_id = db.Column(db.Integer, db.ForeignKey('caso.caso_id'), nullable=False)
    estudiantes_involucrados = db.Column(db.JSON, nullable=False)
    profesores_involucrados = db.Column(db.JSON, nullable=True)

    descripcion_sancion = db.Column(db.String(200), nullable=False)
    fecha_sancion = db.Column(db.DateTime, default=datetime.utcnow)

class Estudiante(db.Model):
    estudiante_id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)    
    apellido = db.Column(db.String(150), nullable=True)   
    rol_usm = db.Column(db.String(20), unique=True, nullable=False) 
    paralelo_id = db.Column(db.Integer, db.ForeignKey('paralelo.paralelo_id'), nullable=True)
    sanciones = db.relationship(
        'CasoSancionado',
        secondary=caso_estudiantes,
        primaryjoin='Estudiante.estudiante_id == caso_estudiantes.c.estudiante_id',
        secondaryjoin='CasoSancionado.caso_id == caso_estudiantes.c.caso_id',
        backref=db.backref('estudiantes', viewonly=True, lazy=True),
        viewonly=True,
        lazy=True
    )
    num_sanciones = db.Column(db.Integer, default=0)
    paralelo = db.relationship('Paralelo', backref='estudiantes')

class Permisos_Aplicacion(db.Model):
    permiso_id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    descripcion = db.Column(db.String(200), nullable=True)

