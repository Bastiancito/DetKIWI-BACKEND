from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token
from app.models import *
from app.extensions import db

roles_bp = Blueprint('roles', __name__)

@roles_bp.route('/GetAllRoles', methods=['GET'])
def get_roles():
    roles = Rol.query.all()
    roles_list = [{'rol_id': rol.rol_id, 'nombre': rol.nombre, 'descripcion': rol.descripcion} for rol in roles]
    return jsonify(roles_list), 200

# Payload: {"nombre": "string", "descripcion": "string" (opcional)}
@roles_bp.route('/CreateRol', methods=['POST'])
def create_rol():
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Se requiere JSON en el body"}), 400
    
    nombre = data.get('nombre')
    descripcion = data.get('descripcion')
    
    if not nombre:
        return jsonify({"error": "El nombre del rol es requerido"}), 400
    
    existing_rol = Rol.query.filter_by(nombre=nombre).first()
    if existing_rol:
        return jsonify({"error": "El rol ya existe"}), 409
    
    new_rol = Rol(
        nombre=nombre,
        descripcion=descripcion
    )
    
    db.session.add(new_rol)
    db.session.commit()
    
    return jsonify({
        'rol_id': new_rol.rol_id,
        'nombre': new_rol.nombre,
        'descripcion': new_rol.descripcion
    }), 201

@roles_bp.route('/DeleteRol/<int:rol_id>', methods=['DELETE'])
def delete_rol(rol_id):
    rol = Rol.query.get(rol_id)
    
    if not rol:
        return jsonify({"error": "Rol no encontrado"}), 404
    
    db.session.delete(rol)
    db.session.commit()
    
    return jsonify({"message": "Rol eliminado exitosamente"}), 200

# Payload: {"nombre": "string" (opcional), "descripcion": "string" (opcional)}
@roles_bp.route('/UpdateRol/<int:rol_id>', methods=['PUT'])
def update_rol(rol_id):
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Se requiere JSON en el body"}), 400
    
    rol = Rol.query.get(rol_id)
    
    if not rol:
        return jsonify({"error": "Rol no encontrado"}), 404
    
    nombre = data.get('nombre')
    descripcion = data.get('descripcion')
    
    if nombre:
        rol.nombre = nombre
    if descripcion:
        rol.descripcion = descripcion
    
    db.session.commit()
    
    return jsonify({
        'rol_id': rol.rol_id,
        'nombre': rol.nombre,
        'descripcion': rol.descripcion
    }), 200
