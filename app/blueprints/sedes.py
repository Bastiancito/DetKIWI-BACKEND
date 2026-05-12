from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token
from app.models import *
from app.extensions import db

sedes_bp = Blueprint('sedes', __name__)

@sedes_bp.route('/ObtenerSedes', methods=['GET'])
def get_sedes():
    sedes = Sede.query.all()
    sedes_list = [{'sede_id': sede.sede_id, 'nombre': sede.nombre} for sede in sedes]
    return jsonify(sedes_list), 200

@sedes_bp.route('/ObtenerSedePorId/<int:sede_id>', methods=['GET'])
def get_sede(sede_id):
    sede = Sede.query.get(sede_id)
    if not sede:
        return jsonify({"error": "Sede no encontrada"}), 404
    sede_data = {
        'sede_id': sede.sede_id,
        'nombre': sede.nombre,
        'paralelos': [{'paralelo_id': p.paralelo_id, 'nombre': p.sigla_paralelo} for p in sede.paralelos]
    }
    return jsonify(sede_data), 200

# Payload: {"nombre": "string"}
@sedes_bp.route('/CrearSede', methods=['POST'])
def create_sede():
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Se requiere JSON en el body"}), 400
    
    nombre = data.get('nombre')
    
    if not nombre:
        return jsonify({"error": "Nombre es requerido"}), 400
    
    existing_sede = Sede.query.filter_by(nombre=nombre).first()
    if existing_sede:
        return jsonify({"error": "La sede ya existe"}), 409
    
    new_sede = Sede(nombre=nombre)
    
    db.session.add(new_sede)
    db.session.commit()
    
    return jsonify({
        'sede_id': new_sede.sede_id,
        'nombre': new_sede.nombre
    }), 201

# Payload: {"nombre": "string"}
@sedes_bp.route('/ActualizarSede/<int:sede_id>', methods=['PUT'])
def update_sede(sede_id):
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Se requiere JSON en el body"}), 400
    
    sede = Sede.query.get(sede_id)
    if not sede:
        return jsonify({"error": "Sede no encontrada"}), 404
    
    nombre = data.get('nombre')
    
    if nombre:
        sede.nombre = nombre
    
    db.session.commit()
    
    return jsonify({
        'sede_id': sede.sede_id,
        'nombre': sede.nombre
    }), 200

@sedes_bp.route('/EliminarSede/<int:sede_id>', methods=['DELETE'])
def delete_sede(sede_id):
    sede = Sede.query.get(sede_id)
    
    if not sede:
        return jsonify({"error": "Sede no encontrada"}), 404
    
    db.session.delete(sede)
    db.session.commit()
    
    return jsonify({"message": "Sede eliminada exitosamente"}), 200


@sedes_bp.route('/ObtenerParalelosPorSede/<int:sede_id>', methods=['GET'])
def get_estudiantes_by_sede(sede_id):
    paralelos = Paralelo.query.filter_by(sede_id=sede_id).all()
    paralelos_list = [{'paralelo_id': paralelo.paralelo_id, 'nombre': paralelo.sigla_paralelo, 'sede_id': paralelo.sede_id} for paralelo in paralelos]
    return jsonify(paralelos_list), 200

