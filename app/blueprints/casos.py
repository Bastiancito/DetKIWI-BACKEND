from datetime import datetime
from unittest import case

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.extensions import db
from app.models import Caso, CasoSancionado, Reporte, Estudiante, User, Paralelo, Sede, Evaluacion, Periodo, caso_usuarios, caso_estudiantes

casos_bp = Blueprint('casos', __name__)

def _serializar_paralelos_caso(caso):
    return [
        {
            'paralelo_id': paralelo.paralelo_id,
            'sigla_paralelo': paralelo.sigla_paralelo,
            'sede_id': paralelo.sede_id,
            'sede_nombre': paralelo.sede.nombre if paralelo.sede else None
        }
        for paralelo in caso.paralelos
    ]

@casos_bp.route('/ObtenerCasosPorReporteId/<int:reporte_id>', methods=['GET'])
@jwt_required()
def obtener_casos_reporte(reporte_id):
    try:
        current_user_id = int(get_jwt_identity())
        reporte = Reporte.query.filter_by(reporte_id=reporte_id, user_id=current_user_id).first()
        
        if not reporte:
            return jsonify({"msg": "Reporte no encontrado"}), 404
        
        result = []
        for caso in reporte.casos:
            estudiantes = [
                {
                    'estudiante_id': est.estudiante_id,
                    'nombre': est.nombre,
                    'apellido': est.apellido,
                    'paralelo': est.paralelo.sigla_paralelo if est.paralelo else None
                }
                for est in caso.involucrados
            ]
            
            usuarios_asignados = [
                {
                    'user_id': user.user_id,
                    'username': user.username,
                    'email': user.email
                }
                for user in caso.usuarios_asignados
            ]
            
            result.append({
                'caso_id': caso.caso_id,
                'similitud': caso.similitud,
                'lineas': caso.lineas,
                'url_moss': caso.url_moss,
                'closed': caso.closed,
                'sancion': caso.sancion,
                'caso_metadata': caso.caso_metadata,
                'paralelos': _serializar_paralelos_caso(caso),
                'estudiantes': estudiantes,
                'usuarios_asignados': usuarios_asignados
            })
        
        return jsonify({
            'reporte': {
                'reporte_id': reporte.reporte_id,
                'titulo': reporte.titulo,
                'fecha_creacion': reporte.fecha_creacion.isoformat()
            },
            'casos': result
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener casos", "error": str(e)}), 500

@casos_bp.route('/ObtenerDetalleCaso/<int:caso_id>', methods=['GET'])
@jwt_required()
def obtener_caso_detalle(caso_id):
    try:
        current_user_id = int(get_jwt_identity())
        
        caso = Caso.query.join(Reporte).filter(
            Caso.caso_id == caso_id,
            Reporte.user_id == current_user_id
        ).first()
        
        if not caso:
            return jsonify({"msg": "Caso no encontrado"}), 404
        
        estudiantes = [
            {
                'estudiante_id': est.estudiante_id,
                'nombre': est.nombre,
                'apellido': est.apellido,
                'paralelo': est.paralelo.sigla_paralelo if est.paralelo else None
            }
            for est in caso.involucrados
        ]
        
        usuarios_asignados = [
            {
                'user_id': user.user_id,
                'username': user.username,
                'email': user.email
            }
            for user in caso.usuarios_asignados
        ]
        
        return jsonify({
            'caso_id': caso.caso_id,
            'reporte_id': caso.reporte_id,
            'similitud': caso.similitud,
            'lineas': caso.lineas,
            'url_moss': caso.url_moss,
            'closed': caso.closed,
            'sancion': caso.sancion,
            'caso_metadata': caso.caso_metadata,
            'comentarios_profes': caso.comentarios_profes if caso.comentarios_profes else [],
            'paralelos': _serializar_paralelos_caso(caso),
            'estudiantes': estudiantes,
            'usuarios_asignados': usuarios_asignados
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener caso", "error": str(e)}), 500

# Payload: {"user_ids": [int, int, ...]}
@casos_bp.route('/AsignarCaso/<int:caso_id>', methods=['PUT'])
@jwt_required()
def asignar_usuario_caso(caso_id):
    try:
        current_user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        user_ids = data.get('user_ids', [])
        
        if not user_ids or not isinstance(user_ids, list):
            return jsonify({"msg": "Se requiere user_ids como lista"}), 400
        
        caso = Caso.query.join(Reporte).filter(
            Caso.caso_id == caso_id,
            Reporte.user_id == current_user_id
        ).first()
        
        if not caso:
            return jsonify({"msg": "Caso no encontrado"}), 404
        
        caso.usuarios_asignados.clear()
        
        usuarios_asignados = []
        for user_id in user_ids:
            usuario = User.query.get(user_id)
            if usuario:
                caso.usuarios_asignados.append(usuario)
                usuarios_asignados.append({
                    'user_id': usuario.user_id,
                    'username': usuario.username,
                    'email': usuario.email
                })
        
        db.session.commit()
        
        return jsonify({
            "msg": "Usuarios asignados correctamente",
            "caso_id": caso.caso_id,
            "usuarios_asignados": usuarios_asignados
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al asignar usuarios", "error": str(e)}), 500


@casos_bp.route('/ObtenerMisCasosPorEvaluacionId/<int:evaluacion_id>', methods=['GET'])
@jwt_required()
def obtener_mis_casos(evaluacion_id=None):
    try:
        current_user_id = int(get_jwt_identity())
        evaluacion_id = evaluacion_id or request.args.get('evaluacion_id', type=int)
        
        usuario = User.query.get(current_user_id)
        if not usuario:
            return jsonify({"msg": "Usuario no encontrado"}), 404
        
        query = Caso.query.join(caso_usuarios).filter(
            caso_usuarios.c.user_id == current_user_id
        )

        if evaluacion_id is not None:
            query = query.filter(Caso.evaluacion_id == evaluacion_id)

        casos = query.all()

        result = []
        for caso in casos:
            estudiantes = [
                {
                    'estudiante_id': est.estudiante_id,
                    'nombre': est.nombre,
                    'apellido': est.apellido,
                    'paralelo': est.paralelo.sigla_paralelo if est.paralelo else None
                }
                for est in caso.involucrados
            ]
            
            result.append({
                'caso_id': caso.caso_id,
                'reporte_id': caso.reporte_id,
                'similitud': caso.similitud,
                'lineas': caso.lineas,
                'url_moss': caso.url_moss,
                'closed': caso.closed,
                'sancion': caso.sancion,
                'caso_metadata': caso.caso_metadata,
                'paralelos': _serializar_paralelos_caso(caso),
                'estudiantes': estudiantes
            })
        
        return jsonify({
            'total_casos': len(result),
            'casos': result
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener casos asignados", "error": str(e)}), 500

@casos_bp.route('/ObtenerCasosPorSedeIdAndEvaluacionId/<int:sede_id>/<int:evaluacion_id>', methods=['GET'])
@jwt_required()
def obtener_casos_por_sede_evaluacion(sede_id, evaluacion_id):
    try:
        casos = Caso.query.filter(
            Caso.evaluacion_id == evaluacion_id,
            Caso.paralelos.any(Paralelo.sede_id == sede_id)
        ).all()

        result = []
        for caso in casos:
            estudiantes = [
                {
                    'estudiante_id': est.estudiante_id,
                    'nombre': est.nombre,
                    'apellido': est.apellido,
                    'paralelo': est.paralelo.sigla_paralelo if est.paralelo else None
                }
                for est in caso.involucrados
            ]
            
            result.append({
                'caso_id': caso.caso_id,
                'reporte_id': caso.reporte_id,
                'similitud': caso.similitud,
                'lineas': caso.lineas,
                'url_moss': caso.url_moss,
                'closed': caso.closed,
                'sancion': caso.sancion,
                'caso_metadata': caso.caso_metadata,
                'paralelos': _serializar_paralelos_caso(caso),
                'estudiantes': estudiantes
            })
        
        return jsonify({
            'total_casos': len(result),
            'casos': result
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener casos por sede y evaluación", "error": str(e)}), 500
    
@casos_bp.route('/ObtenerCasosPorParaleloIdAndEvaluacionId/<int:paralelo_id>/<int:evaluacion_id>', methods=['GET'])
@jwt_required()
def obtener_casos_por_paralelo_evaluacion(paralelo_id, evaluacion_id):
    try:
        casos = Caso.query.filter(
            Caso.evaluacion_id == evaluacion_id,
            Caso.paralelos.any(Paralelo.paralelo_id == paralelo_id)
        ).all()

        result = []
        for caso in casos:
            estudiantes = [
                {
                    'estudiante_id': est.estudiante_id,
                    'nombre': est.nombre,
                    'apellido': est.apellido,
                    'paralelo': est.paralelo.sigla_paralelo if est.paralelo else None
                }
                for est in caso.involucrados
            ]
            
            result.append({
                'caso_id': caso.caso_id,
                'reporte_id': caso.reporte_id,
                'similitud': caso.similitud,
                'lineas': caso.lineas,
                'url_moss': caso.url_moss,
                'closed': caso.closed,
                'sancion': caso.sancion,
                'caso_metadata': caso.caso_metadata,
                'paralelos': _serializar_paralelos_caso(caso),
                'estudiantes': estudiantes,
                'usuarios_asignados': [
                    {
                        'user_id': user.user_id,
                        'username': user.username
                    }
                    for user in caso.usuarios_asignados
                ]
            })
        
        
        return jsonify({
            'total_casos': len(result),
            'casos': result
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener casos por paralelo y evaluación", "error": str(e)}), 500
    
@casos_bp.route('/ObtenerStatsCasosPorSedeIdAndEvaluacionId/<int:sede_id>/<int:evaluacion_id>', methods=['GET'])
@jwt_required()
def obtener_stats_casos_por_sede_evaluacion(sede_id, evaluacion_id):
    try:
        stats = db.session.query(
            db.func.count(db.distinct(Caso.caso_id)).label('total_casos'),
            db.func.count(
                db.distinct(
                    db.case((Caso.closed.is_(False), Caso.caso_id), else_=None)
                )
            ).label('total_casos_pendientes')
        ).select_from(Caso).join(
            caso_estudiantes,
            caso_estudiantes.c.caso_id == Caso.caso_id
        ).join(
            Estudiante,
            Estudiante.estudiante_id == caso_estudiantes.c.estudiante_id
        ).join(
            Paralelo,
            Paralelo.paralelo_id == Estudiante.paralelo_id
        ).join(
            Sede,
            Sede.sede_id == Paralelo.sede_id
        ).filter(
            Sede.sede_id == sede_id,
            Caso.evaluacion_id == evaluacion_id
        ).first()

        if not stats or stats.total_casos == 0:
            return jsonify([]), 200

        return jsonify({
            'total_casos': stats.total_casos,
            'total_casos_pendientes': stats.total_casos_pendientes,
            'total_casos_resueltos': stats.total_casos - stats.total_casos_pendientes
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener estadísticas de casos por sede y evaluación", "error": str(e)}), 500   

@casos_bp.route('/ObtenerStatsCasosPorParalelosPorEvaluacionIdAndSedeId/<int:evaluacion_id>/<int:sede_id>', methods=['GET']  )
@jwt_required()
def obtener_stats_casos_por_paralelos_evaluacion_sede(evaluacion_id, sede_id):  
    try:
        stats = db.session.query(
            Paralelo.paralelo_id,
            Paralelo.sigla_paralelo,
            db.func.count(db.distinct(Caso.caso_id)).label('total_casos'),
            db.func.count(
                db.distinct(
                    db.case((Caso.closed.is_(False), Caso.caso_id), else_=None)
                )
            ).label('total_casos_pendientes')
        ).select_from(Paralelo).join(
            Estudiante,
            Estudiante.paralelo_id == Paralelo.paralelo_id
        ).join(
            caso_estudiantes,
            caso_estudiantes.c.estudiante_id == Estudiante.estudiante_id
        ).join(
            Caso,
            Caso.caso_id == caso_estudiantes.c.caso_id
        ).filter(
            Paralelo.sede_id == sede_id,
            Caso.evaluacion_id == evaluacion_id
        ).group_by(Paralelo.paralelo_id, Paralelo.sigla_paralelo).all()

        result = []
        for paralelo_id, sigla_paralelo, total_casos, total_casos_pendientes in stats:
            # Obtener el encargado del paralelo (primer usuario asignado al paralelo)
            paralelo_obj = Paralelo.query.get(paralelo_id)
            usuario_encargado = None
            if paralelo_obj and paralelo_obj.usuarios:
                u = paralelo_obj.usuarios[0]
                usuario_encargado = {
                    'user_id': u.user_id,
                    'username': u.username,
                    'email': u.email
                }

            # También mantener la lista de usuarios asignados a casos como fallback
            usuarios_asignados = db.session.query(User).select_from(User).join(
                caso_usuarios,
                caso_usuarios.c.user_id == User.user_id
            ).join(
                Caso,
                Caso.caso_id == caso_usuarios.c.caso_id
            ).join(
                caso_estudiantes,
                caso_estudiantes.c.caso_id == Caso.caso_id
            ).join(
                Estudiante,
                Estudiante.estudiante_id == caso_estudiantes.c.estudiante_id
            ).filter(
                Estudiante.paralelo_id == paralelo_id,
                Caso.evaluacion_id == evaluacion_id
            ).distinct().all()

            usuarios_list = [
                {
                    'user_id': user.user_id,
                    'username': user.username,
                    'email': user.email
                }
                for user in usuarios_asignados
            ]

            entry = {
                'paralelo': sigla_paralelo,
                'paralelo_id': paralelo_id,
                'total_casos': total_casos,
                'total_casos_pendientes': total_casos_pendientes,
                'total_casos_resueltos': total_casos - total_casos_pendientes
            }

            if usuario_encargado:
                entry['usuario'] = usuario_encargado

            # mantener por compatibilidad
            entry['usuarios_asignados'] = usuarios_list

            result.append(entry)

        return jsonify(result), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener estadísticas de casos por paralelos, evaluación y sede", "error": str(e)}), 500

@casos_bp.route('/ObtenerStatsCasosPorParalelosAndEvaluacionId/<int:evaluacion_id>', methods=['GET'])
@jwt_required()
def obtener_stats_casos_por_paralelos_evaluacion(evaluacion_id):
    try:
        stats = db.session.query(
            Paralelo.paralelo_id,
            Paralelo.sigla_paralelo,
            db.func.count(db.distinct(Caso.caso_id)).label('total_casos'),
            db.func.count(
                db.distinct(
                    db.case((Caso.closed.is_(False), Caso.caso_id), else_=None)
                )
            ).label('total_casos_pendientes')
        ).select_from(Paralelo).join(
            Estudiante,
            Estudiante.paralelo_id == Paralelo.paralelo_id
        ).join(
            caso_estudiantes,
            caso_estudiantes.c.estudiante_id == Estudiante.estudiante_id
        ).join(
            Caso,
            Caso.caso_id == caso_estudiantes.c.caso_id
        ).filter(
            Caso.evaluacion_id == evaluacion_id
        ).group_by(Paralelo.paralelo_id, Paralelo.sigla_paralelo).all()

        result = []
        for paralelo_id, sigla_paralelo, total_casos, total_casos_pendientes in stats:
            usuarios_asignados = db.session.query(User).select_from(User).join(
                caso_usuarios,
                caso_usuarios.c.user_id == User.user_id
            ).join(
                Caso,
                Caso.caso_id == caso_usuarios.c.caso_id
            ).join(
                caso_estudiantes,
                caso_estudiantes.c.caso_id == Caso.caso_id
            ).join(
                Estudiante,
                Estudiante.estudiante_id == caso_estudiantes.c.estudiante_id
            ).filter(
                Estudiante.paralelo_id == paralelo_id,
                Caso.evaluacion_id == evaluacion_id
            ).distinct().all()

            usuarios_list = [
                {
                    'user_id': user.user_id,
                    'username': user.username,
                    'email': user.email
                }
                for user in usuarios_asignados
            ]

            result.append({
                'paralelo': sigla_paralelo,
                'paralelo_id': paralelo_id,
                'total_casos': total_casos,
                'total_casos_pendientes': total_casos_pendientes,
                'total_casos_resueltos': total_casos - total_casos_pendientes,
                'usuarios_asignados': usuarios_list
            })

        return jsonify(result), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener estadísticas de casos por paralelos y evaluación", "error": str(e)}), 500


@casos_bp.route('/ObtenerStatsCasosPorSedesAndEvaluacionId/<int:evaluacion_id>', methods=['GET'])
@jwt_required()
def obtener_stats_casos_por_sedes_evaluacion(evaluacion_id):
    try:
        # Agrega estadísticas agregadas por sede para una evaluación (batch)
        stats = db.session.query(
            Sede.sede_id,
            Sede.nombre,
            db.func.count(db.distinct(Caso.caso_id)).label('total_casos'),
            db.func.count(
                db.distinct(
                    db.case((Caso.closed.is_(False), Caso.caso_id), else_=None)
                )
            ).label('total_casos_pendientes')
        ).select_from(Sede).join(
            Paralelo,
            Paralelo.sede_id == Sede.sede_id
        ).join(
            Estudiante,
            Estudiante.paralelo_id == Paralelo.paralelo_id
        ).join(
            caso_estudiantes,
            caso_estudiantes.c.estudiante_id == Estudiante.estudiante_id
        ).join(
            Caso,
            Caso.caso_id == caso_estudiantes.c.caso_id
        ).filter(
            Caso.evaluacion_id == evaluacion_id
        ).group_by(Sede.sede_id, Sede.nombre).all()

        result = []
        for sede_id, nombre, total_casos, total_casos_pendientes in stats:
            result.append({
                'sede_id': sede_id,
                'nombre': nombre,
                'total_casos': total_casos,
                'total_casos_pendientes': total_casos_pendientes,
                'total_casos_resueltos': (total_casos - total_casos_pendientes) if total_casos is not None else 0
            })

        return jsonify(result), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener estadísticas de casos por sedes y evaluación", "error": str(e)}), 500

@casos_bp.route('/AgregarComentario/<int:caso_id>', methods=['POST'])
@jwt_required()
def agregar_comentario_caso(caso_id):
    try:
        current_user_id = int(get_jwt_identity())
        jwt_data = get_jwt()
        username = jwt_data.get('username', '')
        data = request.get_json(silent=True) or {}
        comentario = data.get('comentario')
        
        if not comentario:
            return jsonify({"msg": "Se requiere el campo 'comentario'"}), 400
        
        caso = Caso.query.join(Reporte).filter(
            Caso.caso_id == caso_id,
            db.or_(
                Reporte.user_id == current_user_id,
                Caso.usuarios_asignados.any(User.user_id == current_user_id)
            )
        ).first()
        
        if not caso:
            return jsonify({"msg": "Caso no encontrado"}), 404
        
        comentarios = list(caso.comentarios_profes or [])

        comentarios.append({
            'user_id': current_user_id,
            'username': username,
            'comentario': comentario,
            'timestamp': datetime.utcnow().isoformat()
        })

        caso.comentarios_profes = comentarios
        
        db.session.commit()
        
        return jsonify({
            "msg": "Comentario agregado correctamente",
            "caso_id": caso.caso_id,
            "comentarios_profes": caso.comentarios_profes
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al agregar comentario", "error": str(e)}), 500


@casos_bp.route('/CambiarDecision/<int:caso_id>', methods=['POST'])
@jwt_required()
def cambiar_decision(caso_id):
    try:
        
        caso = Caso.query.get(caso_id)
        if not caso:
            return jsonify({"msg": "Caso no encontrado"}), 404
        if caso.closed != True:
            return jsonify({"msg": "Solo se pueden cambiar decisiones de casos cerrados"}), 400
        match caso.sancion:
            case True:
                caso.sancion = False
            case False:
                caso.sancion = True

        
        db.session.commit()
        
        return jsonify({
            "msg": "Decisión cambiada correctamente",
            "caso_id": caso.caso_id
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al cambiar decisión", "error": str(e)}), 500

@casos_bp.route('/filtrar', methods=['GET'])
@jwt_required()
def filtrar_casos():
    try:
        current_user_id = int(get_jwt_identity())
        
        min_similitud = request.args.get('min_similitud', type=float)
        max_similitud = request.args.get('max_similitud', type=float)
        reporte_id = request.args.get('reporte_id', type=int)
        
        query = Caso.query.join(Reporte).filter(Reporte.user_id == current_user_id)
        
        if min_similitud is not None:
            query = query.filter(Caso.similitud >= min_similitud)
        if max_similitud is not None:
            query = query.filter(Caso.similitud <= max_similitud)
        if reporte_id:
            query = query.filter(Caso.reporte_id == reporte_id)
        
        casos = query.all()
        
        result = []
        for caso in casos:
            estudiantes = [
                {
                    'estudiante_id': est.estudiante_id,
                    'nombre': est.nombre,
                    'apellido': est.apellido,
                    'paralelo': est.paralelo.sigla_paralelo if est.paralelo else None
                }
                for est in caso.involucrados
            ]
            
            usuarios_asignados = [
                {
                    'user_id': user.user_id,
                    'username': user.username
                }
                for user in caso.usuarios_asignados
            ]
            
            result.append({
                'caso_id': caso.caso_id,
                'reporte_id': caso.reporte_id,
                'similitud': caso.similitud,
                'lineas': caso.lineas,
                'url_moss': caso.url_moss,
                'closed': caso.closed,
                'sancion': caso.sancion,
                'caso_metadata': caso.caso_metadata,
                'estudiantes': estudiantes,
                'usuarios_asignados': usuarios_asignados
            })
        
        return jsonify({
            'total_casos': len(result),
            'casos': result
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error al filtrar casos", "error": str(e)}), 500

# Payload: {"caso_metadata": {objeto JSON}}
@casos_bp.route('/ActualizarMetadata/<int:caso_id>', methods=['PUT'])
@jwt_required()
def actualizar_metadata_caso(caso_id):
    """
    Actualiza solo el metadata de un caso.
    Body: {
        "caso_metadata": {...}
    }
    """
    try:
        current_user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        
        caso_metadata = data.get('caso_metadata')
        if caso_metadata is None:
            return jsonify({"msg": "Se requiere el campo 'caso_metadata'"}), 400
        
        caso = Caso.query.join(Reporte).filter(
            Caso.caso_id == caso_id,
            db.or_(
                Reporte.user_id == current_user_id,
                Caso.usuarios_asignados.any(User.user_id == current_user_id)
            )
        ).first()
        
        if not caso:
            return jsonify({"msg": "Caso no encontrado o no tiene permisos"}), 404
        
        caso.caso_metadata = caso_metadata
        db.session.commit()
        
        return jsonify({
            "msg": "Metadata actualizado correctamente",
            "caso_id": caso.caso_id,
            "caso_metadata": caso.caso_metadata
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al actualizar metadata", "error": str(e)}), 500

# Payload: {"sancion": bool}
@casos_bp.route('/ActualizarEstadoCaso/<int:caso_id>', methods=['PUT'])
@jwt_required()
def marcar_caso_revisado(caso_id):
    try:
        current_user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        
        caso = Caso.query.join(Reporte).filter(
            Caso.caso_id == caso_id,
            db.or_(
                Reporte.user_id == current_user_id,
                Caso.usuarios_asignados.any(User.user_id == current_user_id)
            )
        ).first()
        accion = data.get('sancion')
        descripcion_sancion = data.get('descripcion_sancion', 'Amonestación por plagio')
        if not caso:
            return jsonify({"msg": "Caso no encontrado"}), 404
        
        caso.closed = True
        if accion == True:
            caso.sancion = True
            estudiantes_involucrados = {}
            usuarios_involucrados = {}
            for est in caso.involucrados:
                estudiantes_involucrados[est.estudiante_id] = {
                    'nombre': est.nombre,
                    'apellido': est.apellido,
                    'paralelo': est.paralelo.sigla_paralelo if est.paralelo else None
                }
                est.num_sanciones = (est.num_sanciones or 0) + 1
            for usuario in caso.usuarios_asignados:
                usuarios_involucrados[usuario.user_id] = {
                    'nombre': usuario.username,
                }

            sancion = CasoSancionado(
                caso_id=caso.caso_id,
                estudiantes_involucrados=estudiantes_involucrados,
                profesores_involucrados=usuarios_involucrados,
                descripcion_sancion=descripcion_sancion
            )
            db.session.add(sancion)
            
        else:
            caso.sancion = False
        db.session.commit()
        
        return jsonify({"msg": "Caso marcado como revisado", "caso_id": caso.caso_id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al marcar caso como revisado", "error": str(e)}), 500
    
@casos_bp.route('/AsignarCasosAParalelo/<int:paralelo_id>', methods=['POST'])
@jwt_required()
def asignar_casos_a_paralelo(paralelo_id):
    try:
        current_user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        caso_ids = data.get('caso_ids', [])
        
        if not caso_ids or not isinstance(caso_ids, list):
            return jsonify({"msg": "Se requiere caso_ids como lista"}), 400
        
        paralelo = Paralelo.query.get(paralelo_id)
        if not paralelo:
            return jsonify({"msg": "Paralelo no encontrado"}), 404
        
        casos = Caso.query.filter(Caso.caso_id.in_(caso_ids)).all()
        
        for caso in casos:
            for est in caso.involucrados:
                est.paralelo_id = paralelo_id
        
        db.session.commit()
        
        return jsonify({
            "msg": f"Casos asignados al paralelo {paralelo.sigla_paralelo} correctamente",
            "paralelo_id": paralelo.paralelo_id,
            "caso_ids_asignados": [caso.caso_id for caso in casos]
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al asignar casos a paralelo", "error": str(e)}), 500