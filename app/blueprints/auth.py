from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token
from app.models import User
from app.extensions import db

auth_bp = Blueprint('auth', __name__)

# Payload: {"email": "string", "password": "string"}
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Se requiere JSON en el body"}), 400
    
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({"error": "Email y contraseña son requeridos"}), 400
    
    user = User.query.filter_by(email=email).first()
    
    if not user or not user.check_password(password):
        return jsonify({"error": "Credenciales inválidas"}), 401
    
    access_token = create_access_token(
        identity=str(user.user_id),
        additional_claims={"username": user.username}
    )
    refresh_token = create_refresh_token(identity=str(user.user_id))
    
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user.user_id,
            "username": user.username,
            "email": user.email,
            "rol_id": user.rol_id,
            "paralelos": [{"paralelo_id": p.paralelo_id, "sigla_paralelo": p.sigla_paralelo} for p in user.paralelos]
        }
    }), 200

# Payload: {"email": "string", "username": "string", "password": "string"}
@auth_bp.route('/register', methods=['POST'])
def register():
    if not current_app.config.get('ALLOW_PUBLIC_REGISTER', False):
        return jsonify({"error": "Registro público deshabilitado"}), 403

    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Se requiere JSON en el body"}), 400
    
    email = data.get('email')
    username = data.get('username')
    password = data.get('password')
    
    if not email or not username or not password:
        return jsonify({"error": "Email, username y contraseña son requeridos"}), 400
    
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "El email ya está registrado"}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "El username ya está en uso"}), 400
    
    try:
        nuevo_usuario = User(
            email=email,
            username=username,
            rol_id=1
        )
        nuevo_usuario.set_password(password)
        
        db.session.add(nuevo_usuario)
        db.session.commit()
        
        return jsonify({
            "msg": "Usuario creado exitosamente",
            "user": {
                "id": nuevo_usuario.user_id,
                "username": nuevo_usuario.username,
                "email": nuevo_usuario.email

            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error creando usuario: {str(e)}"}), 500 

