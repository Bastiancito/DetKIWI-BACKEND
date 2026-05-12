from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.models import *
from app.extensions import db

users_bp = Blueprint('users', __name__)
@users_bp.route('/ObtenerUsuarios', methods=['GET'])
def get_users():
    users = User.query.all()
    users_list = [{'user_id': user.user_id, 'username': user.username, 'email': user.email} for user in users]
    return jsonify(users_list), 200

@users_bp.route('/ObtenerUsuarioPorId/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    
    paralelos = [{
        'paralelo_id': p.paralelo_id,
        'nombre': p.sigla_paralelo,
        'sede_id': p.sede_id,
        'sede_nombre': p.sede.nombre if p.sede else None
    } for p in user.paralelos]
    
    user_data = {
        'user_id': user.user_id,
        'username': user.username,
        'email': user.email,
        'rol_id': user.rol_id,
        'paralelos': paralelos
    }
    return jsonify(user_data), 200

@users_bp.route('/ObtenerUsuarioPorEmail/<string:email>', methods=['GET'])
def get_user_by_email(email):
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    
    paralelos = [{
        'paralelo_id': p.paralelo_id,
        'nombre': p.sigla_paralelo,
        'sede_id': p.sede_id,
        'sede_nombre': p.sede.nombre if p.sede else None
    } for p in user.paralelos]
    
    user_data = {
        'user_id': user.user_id,
        'username': user.username,
        'email': user.email,
        'rol_id': user.rol_id,
        'paralelos': paralelos
    }
    return jsonify(user_data), 200

@users_bp.route('/ObtenerUsuariosPorRolId/<int:rol_id>', methods=['GET'])
def get_users_by_rol(rol_id):
    users = User.query.filter_by(rol_id=rol_id).all()
    users_list = [{'user_id': user.user_id, 'username': user.username, 'email': user.email} for user in users]
    return jsonify(users_list), 200

@users_bp.route('/ObtenerUsuariosPorSedeId/<int:sede_id>', methods=['GET'])
def get_users_by_sede(sede_id):
    sede = Sede.query.get(sede_id)
    if not sede:
        return jsonify({"error": "Sede no encontrada"}), 404
    
    users_set = set()
    for paralelo in sede.paralelos:
        for usuario in paralelo.usuarios:
            users_set.add(usuario)
    
    users_list = [{
        'user_id': user.user_id,
        'username': user.username,
        'email': user.email,
        'rol_id': user.rol_id
    } for user in users_set]
    
    return jsonify(users_list), 200

@users_bp.route('/ObtenerUsuariosPorParaleloId/<int:paralelo_id>', methods=['GET'])
def get_users_by_paralelo(paralelo_id):
    paralelo = Paralelo.query.get(paralelo_id)
    if not paralelo:
        return jsonify({"error": "Paralelo no encontrado"}), 404
    
    users_list = [{
        'user_id': user.user_id,
        'username': user.username,
        'email': user.email,
        'rol_id': user.rol_id
    } for user in paralelo.usuarios]
    
    return jsonify(users_list), 200

# Payload: {"username": "string", "email": "string", "password": "string", "rol_id": int, "paralelo_ids": [int, ...] (opcional)}
@users_bp.route('/CrearUsuario', methods=['POST'])
@jwt_required()
def create_user():
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Se requiere JSON en el body"}), 400
    
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    rol_id = data.get('rol_id')
    paralelo_ids = data.get('paralelo_ids', [])
    
    if not username or not email or not password or not rol_id:
        return jsonify({"error": "Faltan campos requeridos"}), 400

    if paralelo_ids is None:
        paralelo_ids = []

    if not isinstance(paralelo_ids, list):
        return jsonify({"error": "paralelo_ids debe ser una lista de IDs"}), 400

    if paralelo_ids:
        paralelos = Paralelo.query.filter(Paralelo.paralelo_id.in_(paralelo_ids)).all()
        found_ids = {p.paralelo_id for p in paralelos}
        missing_ids = [pid for pid in paralelo_ids if pid not in found_ids]
        if missing_ids:
            return jsonify({"error": f"Paralelos no encontrados: {missing_ids}"}), 404
    else:
        paralelos = []
    
    existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
    if existing_user:
        return jsonify({"error": "El usuario o email ya existe"}), 409

    try:
        new_user = User(
            username=username,
            email=email,
            rol_id=rol_id
        )
        new_user.set_password(password)
        new_user.paralelos = paralelos

        db.session.add(new_user)
        db.session.commit()

        return jsonify({
            'user_id': new_user.user_id,
            'username': new_user.username,
            'email': new_user.email,
            'paralelo_ids': [p.paralelo_id for p in new_user.paralelos]
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error creando usuario: {str(e)}"}), 500

@users_bp.route('/EliminarUsuario/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({"message": "Usuario eliminado exitosamente"}), 200

# Payload: {"username": "string" (opcional), "email": "string" (opcional), "password": "string" (opcional), "rol_id": int (opcional), "paralelo_ids": [int, ...] (opcional)}
@users_bp.route('/ActualizarUsuario/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Se requiere JSON en el body"}), 400
    
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    rol_id = data.get('rol_id')
    paralelo_ids = data.get('paralelo_ids')
    
    if username:
        user.username = username
    if email:
        user.email = email
    if password:
        user.set_password(password)
    if rol_id:
        user.rol_id = rol_id

    if paralelo_ids is not None:
        if not isinstance(paralelo_ids, list):
            return jsonify({"error": "paralelo_ids debe ser una lista de IDs"}), 400

        if paralelo_ids:
            paralelos = Paralelo.query.filter(Paralelo.paralelo_id.in_(paralelo_ids)).all()
            found_ids = {p.paralelo_id for p in paralelos}
            missing_ids = [pid for pid in paralelo_ids if pid not in found_ids]
            if missing_ids:
                return jsonify({"error": f"Paralelos no encontrados: {missing_ids}"}), 404
            user.paralelos = paralelos
        else:
            user.paralelos = []
    
    db.session.commit()
    
    return jsonify({
        'user_id': user.user_id,
        'username': user.username,
        'email': user.email,
        'paralelo_ids': [p.paralelo_id for p in user.paralelos]
    }), 200