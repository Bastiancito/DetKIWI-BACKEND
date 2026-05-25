from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token
from app.models import *
from app.extensions import db

estudiante_bp = Blueprint('estudiante', __name__)


def _serializar_sancion(sancion):
    return {
        'sancion_id': sancion.sancion_id,
        'caso_id': sancion.caso_id,
        'estudiantes_involucrados': sancion.estudiantes_involucrados,
        'profesores_involucrados': sancion.profesores_involucrados,
        'descripcion_sancion': sancion.descripcion_sancion,
        'fecha_sancion': sancion.fecha_sancion.isoformat() if sancion.fecha_sancion else None
    }


@estudiante_bp.route('/ObtenerEstudiantes', methods=['GET'])
def get_estudiantes():
    estudiantes = Estudiante.query.all()
    estudiantes_list = [{
        'estudiante_id': estudiante.estudiante_id,
        'nombre': estudiante.nombre,
        'apellido': estudiante.apellido,
        'paralelo_id': estudiante.paralelo_id,
        'paralelo_sigla': estudiante.paralelo.sigla_paralelo if estudiante.paralelo else None,
        'sanciones': [_serializar_sancion(sancion) for sancion in estudiante.sanciones]
    } for estudiante in estudiantes]
    return jsonify(estudiantes_list), 200

@estudiante_bp.route('/ObtenerEstudiantePorEstudianteId/<int:estudiante_id>', methods=['GET'])
def get_estudiante(estudiante_id):
    estudiante = Estudiante.query.get(estudiante_id)
    if not estudiante:
        return jsonify({"error": "Estudiante no encontrado"}), 404
    estudiante_data = {
        'estudiante_id': estudiante.estudiante_id,
        'nombre': estudiante.nombre,
        'apellido': estudiante.apellido,
        'paralelo_id': estudiante.paralelo_id if estudiante.paralelo_id is not None else None,
        'paralelo_sigla': estudiante.paralelo.sigla_paralelo if estudiante.paralelo else None,
        
    }
    return jsonify(estudiante_data), 200

# Payload: {"nombre": "string", "apellido": "string"}
@estudiante_bp.route('/CrearEstudiante', methods=['POST'])
def create_estudiante():
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Se requiere JSON en el body"}), 400
    
    nombre = data.get('nombre')
    apellido = data.get('apellido')
    paralelo_id = data.get('paralelo_id')

    if not nombre or not apellido:
        return jsonify({"error": "Nombre y apellido son requeridos"}), 400
    
    existing_estudiante = Estudiante.query.filter_by(nombre=nombre, apellido=apellido).first()
    if existing_estudiante:
        return jsonify({"error": "El estudiante ya existe"}), 409
    
    new_estudiante = Estudiante(
        nombre=nombre,
        apellido=apellido,
        paralelo_id = paralelo_id if paralelo_id is not None else None
    )
    
    db.session.add(new_estudiante)
    db.session.commit()
    
    return jsonify({
        'estudiante_id': new_estudiante.estudiante_id,
        'nombre': new_estudiante.nombre,
        'apellido': new_estudiante.apellido,
        'paralelo_id': new_estudiante.paralelo_id,
        'paralelo_sigla': new_estudiante.paralelo.sigla_paralelo if new_estudiante.paralelo else None
    }), 201

# Payload: {"nombre": "string" (opcional), "apellido": "string" (opcional)}
@estudiante_bp.route('/ActualizarEstudiantePorEstudianteId/<int:estudiante_id>', methods=['PUT'])
def update_estudiante(estudiante_id):
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Se requiere JSON en el body"}), 400
    
    estudiante = Estudiante.query.get(estudiante_id)
    
    if not estudiante:
        return jsonify({"error": "Estudiante no encontrado"}), 404
    
    nombre = data.get('nombre')
    apellido = data.get('apellido')
    paralelo_id = data.get('paralelo_id')
    
    if nombre:
        estudiante.nombre = nombre
    if apellido:
        estudiante.apellido = apellido
    
    if paralelo_id is not None:
        estudiante.paralelo_id = paralelo_id

    
    
    db.session.commit()
    
    return jsonify({
        'estudiante_id': estudiante.estudiante_id,
        'nombre': estudiante.nombre,
        'apellido': estudiante.apellido,
        'paralelo_id': estudiante.paralelo_id,
        'paralelo_sigla': estudiante.paralelo.sigla_paralelo if estudiante.paralelo else None
    }), 200

@estudiante_bp.route('/EliminarEstudiantePorEstudianteId/<int:estudiante_id>', methods=['DELETE'])
def delete_estudiante(estudiante_id):
    estudiante = Estudiante.query.get(estudiante_id)
    
    if not estudiante:
        return jsonify({"error": "Estudiante no encontrado"}), 404
    
    db.session.delete(estudiante)
    db.session.commit()
    
    return jsonify({"message": "Estudiante eliminado exitosamente"}), 200