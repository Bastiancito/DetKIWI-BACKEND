from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, create_access_token, create_refresh_token
from app.models import *
from app.extensions import db

paralelos_bp = Blueprint('paralelos', __name__)

@paralelos_bp.route('/ObtenerParalelos', methods=['GET'])
def get_paralelos():
    paralelos = Paralelo.query.all()
    paralelos_list = []
    for paralelo in paralelos:
        paralelo_data = {
            'paralelo_id': paralelo.paralelo_id,
            'nombre': paralelo.sigla_paralelo,
            'sede_id': paralelo.sede_id,
            'sede_nombre': paralelo.sede.nombre if paralelo.sede else None
        }
        
        if paralelo.usuarios:
            usuario = paralelo.usuarios[0]
            paralelo_data['usuario'] = {
                'user_id': usuario.user_id,
                'username': usuario.username,
                'email': usuario.email
            }
        
        paralelos_list.append(paralelo_data)
    return jsonify(paralelos_list), 200

@paralelos_bp.route('/ObtenerParaleloPorId/<int:paralelo_id>', methods=['GET'])
def get_paralelo(paralelo_id):
    paralelo = Paralelo.query.get(paralelo_id)
    if not paralelo:
        return jsonify({"error": "Paralelo no encontrado"}), 404
    paralelo_data = {
        'paralelo_id': paralelo.paralelo_id,
        'nombre': paralelo.sigla_paralelo,
        'sede_id': paralelo.sede_id,
        'sede_nombre': paralelo.sede.nombre if paralelo.sede else None
    }
    return jsonify(paralelo_data), 200

# Payload: {"nombre": "string", "sede_id": int}
@paralelos_bp.route('/CrearParalelo', methods=['POST'])
def create_paralelo():
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Se requiere JSON en el body"}), 400
    
# Payload: {"nombre": "string" (opcional), "sede_id": int (opcional)}
    nombre = data.get('nombre')
    sede_id = data.get('sede_id')
    usuario = data.get('usuario')
    
    if not nombre:
        return jsonify({"error": "Nombre es requerido"}), 400
    
    sede = Sede.query.get(sede_id)
    if not sede:
        pass
    
    existing_paralelo = Paralelo.query.filter_by(sigla_paralelo=nombre, sede_id=sede_id).first()
    if existing_paralelo:
        return jsonify({"error": "El paralelo ya existe en esta sede"}), 409
    
    new_paralelo = Paralelo(
        sigla_paralelo=nombre,
        sede_id=sede_id if sede_id else None
    )
    
    
    db.session.add(new_paralelo)
    db.session.commit()
    
    user = None
    if usuario:
        user = User.query.get(usuario)
        if not user:
            return jsonify({"error": "Usuario no encontrado para asignar al paralelo"}), 404
        new_paralelo.usuarios.append(user)
        db.session.commit()
    
    response = {
        'paralelo_id': new_paralelo.paralelo_id,
        'nombre': new_paralelo.sigla_paralelo,
        'sede_id': new_paralelo.sede_id
    }
    
    if usuario and user:
        response['usuario_id'] = user.user_id
        response['usuario_nombre'] = user.username
    
    return jsonify(response), 201


@paralelos_bp.route('/VincularSedeAParalelo/<int:paralelo_id>', methods=['POST'])
def vincular_sede_paralelo(paralelo_id):
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Se requiere JSON en el body"}), 400
    
    sede_id = data.get('sede_id')
    
    if not sede_id:
        return jsonify({"error": "sede_id es requerido"}), 400
    
    paralelo = Paralelo.query.get(paralelo_id)
    if not paralelo:
        return jsonify({"error": "Paralelo no encontrado"}), 404
    
    sede = Sede.query.get(sede_id)
    if not sede:
        return jsonify({"error": "Sede no encontrada"}), 404
    
    paralelo.sede_id = sede_id
    db.session.commit()
    
    return jsonify({
        'message': 'Sede vinculada al paralelo exitosamente',
        'paralelo_id': paralelo.paralelo_id,
        'sede_id': sede.sede_id
    }), 200


@paralelos_bp.route('/CrearListadoDeParalelos', methods=['POST'])
def create_listado_paralelos():
    data = request.get_json()
    
    if not data or not isinstance(data, list):
        return jsonify({"error": "Se requiere un JSON con una lista de paralelos"}), 400
    
    created_paralelos = []
    
    for item in data:
        nombre = item.get('nombre')
        sede_id = item.get('sede_id')
        usuario = item.get('usuario')
        
        if not nombre or not sede_id:
            return jsonify({"error": "Nombre y Sede son requeridos para cada paralelo"}), 400
        
        sede = Sede.query.get(sede_id)
        if not sede:
            return jsonify({"error": f"Sede con ID {sede_id} no encontrada"}), 404
        
        existing_paralelo = Paralelo.query.filter_by(sigla_paralelo=nombre, sede_id=sede_id).first()
        if existing_paralelo:
            return jsonify({"error": f"El paralelo '{nombre}' ya existe en la sede con ID {sede_id}"}), 409
        
        new_paralelo = Paralelo(
            sigla_paralelo=nombre,
            sede_id=sede_id
        )
        
        db.session.add(new_paralelo)
        db.session.commit()
        
        if usuario:
            user = User.query.get(usuario)
            if user:
                new_paralelo.usuarios.append(user)
                db.session.commit()
        
        created_paralelos.append({
            'paralelo_id': new_paralelo.paralelo_id,
            'nombre': new_paralelo.sigla_paralelo,
            'sede_id': new_paralelo.sede_id,
            'usuario_id': user.user_id if usuario and user else None,
            'usuario_nombre': user.username if usuario and user else None
        })
    
    return jsonify(created_paralelos), 201

# Payload: {"nombre": "string" (opcional), "sede_id": int (opcional)}
@paralelos_bp.route('/ActualizarParaleloPorParaleloId/<int:paralelo_id>', methods=['PUT'])
def update_paralelo(paralelo_id):
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Se requiere JSON en el body"}), 400
    
    paralelo = Paralelo.query.get(paralelo_id)
    if not paralelo:
        return jsonify({"error": "Paralelo no encontrado"}), 404
    
    nombre = data.get('nombre')
    sede_id = data.get('sede_id')
    
    if nombre:
        paralelo.sigla_paralelo = nombre
    if sede_id:
        sede = Sede.query.get(sede_id)
        if not sede:
            return jsonify({"error": "Sede no encontrada"}), 404
        paralelo.sede_id = sede_id
    
    db.session.commit()
    
    return jsonify({
        'paralelo_id': paralelo.paralelo_id,
        'nombre': paralelo.sigla_paralelo,
        'sede_id': paralelo.sede_id
    }), 200

@paralelos_bp.route('/EliminarParaleloPorParaleloId/<int:paralelo_id>', methods=['DELETE'])
def delete_paralelo(paralelo_id):
    paralelo = Paralelo.query.get(paralelo_id)
    
    if not paralelo:
        return jsonify({"error": "Paralelo no encontrado"}), 404
    
    db.session.delete(paralelo)
    db.session.commit()
    
    return jsonify({"message": "Paralelo eliminado exitosamente"}), 200



# Payload: {"user_id": int}
@paralelos_bp.route('/AsignarUsuarioPorParaleloId/<int:paralelo_id>', methods=['POST'])
@jwt_required()
def asignar_usuario_paralelo(paralelo_id):
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Se requiere JSON en el body"}), 400
    
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({"error": "user_id es requerido"}), 400
    
    paralelo = Paralelo.query.get(paralelo_id)
    if not paralelo:
        return jsonify({"error": "Paralelo no encontrado"}), 404
    
    usuario = User.query.get(user_id)
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404
    
    if usuario in paralelo.usuarios:
        return jsonify({"error": "El usuario ya está asignado a este paralelo"}), 409
    
    paralelo.usuarios.append(usuario)
    db.session.commit()
    
    return jsonify({
        "message": "Usuario asignado correctamente",
        "paralelo_id": paralelo.paralelo_id,
        "user_id": usuario.user_id
    }), 200

# Payload: {"user_id": int}
@paralelos_bp.route('/RemoverUsuarioPorParaleloId/<int:paralelo_id>', methods=['DELETE'])
@jwt_required()
def remover_usuario_paralelo(paralelo_id):
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Se requiere JSON en el body"}), 400
    
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({"error": "user_id es requerido"}), 400
    
    paralelo = Paralelo.query.get(paralelo_id)
    if not paralelo:
        return jsonify({"error": "Paralelo no encontrado"}), 404
    
    usuario = User.query.get(user_id)
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404
    
    if usuario not in paralelo.usuarios:
        return jsonify({"error": "El usuario no está asignado a este paralelo"}), 404
    
    paralelo.usuarios.remove(usuario)
    db.session.commit()
    
    return jsonify({
        "message": "Usuario removido correctamente",
        "paralelo_id": paralelo.paralelo_id,
        "user_id": usuario.user_id
    }), 200

@paralelos_bp.route('/ObtenerTodosLosUsuariosPorParaleloId/<int:paralelo_id>', methods=['GET'])
def get_usuarios_paralelo(paralelo_id):
    paralelo = Paralelo.query.get(paralelo_id)
    if not paralelo:
        return jsonify({"error": "Paralelo no encontrado"}), 404
    
    usuarios_list = [
        {
            'user_id': usuario.user_id,
            'username': usuario.username,
            'email': usuario.email
        }
        for usuario in paralelo.usuarios
    ]
    
    return jsonify({
        'paralelo_id': paralelo.paralelo_id,
        'nombre': paralelo.sigla_paralelo,
        'usuarios': usuarios_list
    }), 200

@paralelos_bp.route('/ObtenerParalelosPorUserId/<int:user_id>', methods=['GET'])
def get_paralelos_usuario(user_id):
    usuario = User.query.get(user_id)
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404
    
    paralelos_list = [
        {
            'paralelo_id': paralelo.paralelo_id,
            'nombre': paralelo.sigla_paralelo,
            'sede_id': paralelo.sede_id,
            'sede_nombre': paralelo.sede.nombre if paralelo.sede else None
        }
        for paralelo in usuario.paralelos
    ]
    
    return jsonify({
        'user_id': usuario.user_id,
        'username': usuario.username,
        'paralelos': paralelos_list
    }), 200

