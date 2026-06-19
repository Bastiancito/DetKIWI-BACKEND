from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.models import *
from app.extensions import db

users_bp = Blueprint('users', __name__)
@users_bp.route('/ObtenerUsuarios', methods=['GET'])
def get_users():
    users = User.query.all()
    users_list = [{'user_id': user.user_id, 'username': user.username, 'email': user.email, 'paralelos': [{
        'paralelo_id': p.paralelo_id,
        'nombre': p.sigla_paralelo,
        'sede_id': p.sede_id,
        'sede_nombre': p.sede.nombre if p.sede else None
    } for p in user.paralelos]} for user in users]
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
        'paralelos': paralelos,
        'password': user.password
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

ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@users_bp.route('/upload_participantes', methods=['POST'])
@jwt_required()
def upload_participantes():
    if 'file' not in request.files:
        return jsonify({"msg": "No se envió el archivo"}), 400
    
    file = request.files['file']

    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"msg": "Archivo inválido"}), 400

    try:
        from utils.excel_processor import ExcelProcessor
        import pandas as pd
        processor = ExcelProcessor()
        
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
            
        success, processed_data, errors = processor.procesar_aula_virtual(df)
        if not success:
            return jsonify({
                "msg": "Error procesando el archivo",
                "errores": errors
            }), 400
            
        participantes = processed_data.get('participantes', [])
        
        rol_id =  2 # fallback to 2 or existing
        
        cache_paralelos = {}
        for p in Paralelo.query.all():
            cache_paralelos[p.sigla_paralelo] = p
            
        creados = 0
        actualizados = 0
        for p_data in participantes:
            objs_paralelos = []
            for paralelo_sigla in p_data.get('paralelos', []):
                if paralelo_sigla not in cache_paralelos:
                    nuevo_paralelo = Paralelo(sigla_paralelo=paralelo_sigla)
                    db.session.add(nuevo_paralelo)
                    db.session.flush() # get ID
                    cache_paralelos[paralelo_sigla] = nuevo_paralelo
                objs_paralelos.append(cache_paralelos[paralelo_sigla])
                
            if not objs_paralelos:
                continue
                
            paralelo_principal = objs_paralelos[0]
            
        
                
            # Create/Update User account
            #diego.bahamondes@usm.cl
            username = p_data['correo'].split('@')[0] if p_data['correo'] else f"user{p_data['numero_id']}"
                
            user = User.query.filter_by(email=p_data['correo']).first() if p_data['correo'] else None
            if not user:
                user = User(
                    username=username,
                    email=p_data['correo'] if p_data['correo'] else f"{username}@usm.cl",
                    rol_id=rol_id
                )
                
                # Password = numero_id sin dígito verificador
                raw_password = p_data['numero_id'].split('-')[0]
                user.set_password(raw_password)
                
                for p_obj in objs_paralelos:
                    user.paralelos.append(p_obj)
                    
                db.session.add(user)
                creados += 1
            else:
                for p_obj in objs_paralelos:
                    if p_obj not in user.paralelos:
                        user.paralelos.append(p_obj)
                actualizados += 1
                
        db.session.commit()
        return jsonify({
            "msg": "Participantes procesados correctamente",
            "total_procesados": len(participantes),
            "usuarios_creados": creados,
            "usuarios_actualizados": actualizados
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": f"Error interno: {str(e)}"}), 500

@users_bp.route('/debug_upload_participantes', methods=['GET', 'POST'])
def debug_upload_participantes():
    """Endpoint para probar cómo se procesaría el archivo de Aula Virtual sin guardar en BD."""
    try:
        import os
        from utils.excel_processor import ExcelProcessor
        import pandas as pd
        processor = ExcelProcessor()
        
        file_path = "utils/courseid_57985_participants.xlsx"
        if not os.path.exists(file_path):
            return jsonify({"msg": f"No se encontró el archivo en {file_path}"}), 404
            
        df = pd.read_excel(file_path)
            
        success, processed_data, errors = processor.procesar_aula_virtual(df)
        if not success:
            return jsonify({
                "msg": "Error procesando el archivo",
                "errores": errors
            }), 400
            
        return jsonify(processed_data), 200

    except Exception as e:
        return jsonify({"msg": f"Error interno: {str(e)}"}), 500
    
@users_bp.route('/SeedUsuariosUnicaVez', methods=['GET'])
def seed_usuarios_unica_vez():
    """
    Ruta de un solo uso para poblar la base de datos de producción.
    IMPORTANTE: Borrar este código después de ejecutarlo.
    """
    nuevos_usuarios_data = [
      { "username": "felipe.dumont", "email": "felipe.dumont@usm.cl", "password": "felipe123", "rol_id": 2, "paralelo_ids": ["INF129_1L", "INF129_7L"] },
      { "username": "gustavo.ulloa", "email": "gustavo.ulloau@usm.cl", "password": "gustavo123", "rol_id": 2, "paralelo_ids": ["INF129_2L", "INF129_5L", "INF129_11L", "INF129_22L", "IWI131_6L"] },
      { "username": "paulina.gonzalez", "email": "paulina.gonzalezp@usm.cl", "password": "paulina123", "rol_id": 2, "paralelo_ids": ["INF129_3L", "INF129_17L", "EIN413B_300", "EIN413B_301"] },
      { "username": "alvaro.salinas", "email": "alvaro.salinas@usm.cl", "password": "alvaro123", "rol_id": 2, "paralelo_ids": ["INF129_4L", "INF129_16L"] },
      { "username": "juan.zamora", "email": "juan.zamora@usm.cl", "password": "juan123", "rol_id": 2, "paralelo_ids": ["INF129_6L"] },
      { "username": "pablo.cruz", "email": "pablo.cruz@usm.cl", "password": "pablo123", "rol_id": 2, "paralelo_ids": ["INF129_8L", "INF129_18L"] },
      { "username": "diego.vicencio", "email": "diego.vicencio@usm.cl", "password": "diego123", "rol_id": 2, "paralelo_ids": ["INF129_9L"] },
      { "username": "jean-pierre.villacura", "email": "jean-pierre.villacura@usm.cl", "password": "jean-pierre123", "rol_id": 2, "paralelo_ids": ["INF129_10L"] },
      { "username": "andrea.freire", "email": "andrea.freire@usm.cl", "password": "andrea123", "rol_id": 2, "paralelo_ids": ["INF129_12L", "INF129_14L"] },
      { "username": "andres.navarro", "email": "andres.navarro@usm.cl", "password": "andres123", "rol_id": 2, "paralelo_ids": ["INF129_13L", "INF129_15L", "INF129_20L"] },
      { "username": "miguel.guevara", "email": "miguel.guevara@usm.cl", "password": "miguel123", "rol_id": 2, "paralelo_ids": ["INF129_19L", "INF129_21L"] },
      { "username": "juan.jerez", "email": "juan.jerez@usm.cl", "password": "juan123", "rol_id": 2, "paralelo_ids": ["INF129_100L", "IWI131_101L", "IWI131_102L"] },
      { "username": "ricardo.von", "email": "ricardo.vonkretschma@usm.cl", "password": "ricardo123", "rol_id": 2, "paralelo_ids": ["INF129_101L", "IWI131_100L"] },
      { "username": "cristobal.loyola", "email": "cristobal.loyolam@usm.cl", "password": "cristobal123", "rol_id": 2, "paralelo_ids": ["INF129_200L", "INF129_203L", "INF129_205L", "INF129_208L", "INF129_211L", "IWI131_203L"] },
      { "username": "viktor.tapia", "email": "viktor.tapia@usm.cl", "password": "viktor123", "rol_id": 2, "paralelo_ids": ["INF129_201L", "INF129_202L", "INF129_214L", "INF129_217L"] },
      { "username": "rodrigo.caviedes", "email": "rodrigo.caviedes@usm.cl", "password": "rodrigo123", "rol_id": 2, "paralelo_ids": ["INF129_204L", "INF129_209L", "IWI131_202L"] },
      { "username": "luis.ramirez", "email": "luis.ramirez@usm.cl", "password": "luis123", "rol_id": 2, "paralelo_ids": ["INF129_206L", "INF129_210L", "INF129_213L", "IWI131_200L", "IWI131_204L"] },
      { "username": "pedro.toledo", "email": "pedro.toledo.12@usm.cl", "password": "pedro123", "rol_id": 2, "paralelo_ids": ["INF129_207L", "IWI131_201L"] },
      { "username": "anibal.silva", "email": "anibal.silvao@usm.cl", "password": "anibal123", "rol_id": 2, "paralelo_ids": ["INF129_212L", "INF129_215L", "INF129_216L", "INF129_218L"] },
      { "username": "alejandro.veloz", "email": "alejandro.veloz@usm.cl", "password": "alejandro123", "rol_id": 2, "paralelo_ids": ["IWI131_1L", "IWI131_5L"] },
      { "username": "claudio.jara", "email": "claudio.jarac@usm.cl", "password": "claudio123", "rol_id": 2, "paralelo_ids": ["IWI131_2L", "IWI131_3L"] },
      { "username": "andrea.vasquez", "email": "andrea.vasquezg@usm.cl", "password": "andrea123", "rol_id": 2, "paralelo_ids": ["IWI131_4L"] },
      { "username": "pamela.gatica", "email": "pamela.gatica@usm.cl", "password": "pamela123", "rol_id": 2, "paralelo_ids": ["EIN413B_302"] },
      { "username": "cristian.lara", "email": "cristian.lara@usm.cl", "password": "cristian123", "rol_id": 2, "paralelo_ids": ["EIN413B_701"] },
      { "username": "juan.gonzalez", "email": "juan.gonzalezga@usm.cl", "password": "juan123", "rol_id": 2, "paralelo_ids": ["EIN413B_702"] },
      { "username": "ana.rojas", "email": "ana.rojasc@usm.cl", "password": "ana123", "rol_id": 2, "paralelo_ids": ["ELI109A_300", "ELI109A_301"] },
      { "username": "claudio.velquen", "email": "claudio.velquen@usm.cl", "password": "claudio123", "rol_id": 2, "paralelo_ids": ["ELI109A_701"] }
    ]

    usuarios_creados = 0
    usuarios_saltados = 0
    detalles = []

    try:
        # Cacheamos paralelos existentes para no saturar la BD
        cache_paralelos = {p.sigla_paralelo: p for p in Paralelo.query.all()}

        for user_data in nuevos_usuarios_data:
            username = user_data['username']
            email = user_data['email']

            # 1. Verificar si ya existe en la BD
            existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
            if existing_user:
                detalles.append({"usuario": username, "status": "Omitido - Ya existe"})
                usuarios_saltados += 1
                continue

            # 2. Instanciar nuevo usuario
            new_user = User(
                username=username,
                email=email,
                rol_id=user_data['rol_id']
            )
            new_user.set_password(user_data['password'])

            # 3. Validar e instanciar paralelos
            for sigla in user_data.get('paralelo_ids', []):
                if sigla not in cache_paralelos:
                    nuevo_paralelo = Paralelo(sigla_paralelo=sigla)
                    db.session.add(nuevo_paralelo)
                    db.session.flush() 
                    cache_paralelos[sigla] = nuevo_paralelo
                
                paralelo_obj = cache_paralelos[sigla]
                if paralelo_obj not in new_user.paralelos:
                    new_user.paralelos.append(paralelo_obj)

            # 4. Preparar usuario para guardado
            db.session.add(new_user)
            usuarios_creados += 1
            detalles.append({"usuario": username, "status": "Creado exitosamente"})

        # Confirmar todos los guardados
        db.session.commit()

        return jsonify({
            "status": "Finalizado",
            "resumen": {
                "usuarios_creados": usuarios_creados,
                "usuarios_omitidos": usuarios_saltados
            },
            "detalles": detalles
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
