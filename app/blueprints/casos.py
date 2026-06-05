from datetime import datetime
from unittest import case
from functools import wraps
import time

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, DBAPIError
from app.extensions import db
from app.models import Caso, CasoSancionado, Reporte, Estudiante, User, Paralelo, Sede, Evaluacion, Periodo, caso_usuarios, caso_estudiantes

casos_bp = Blueprint('casos', __name__)


def retry_db(max_attempts=3, delay=0.1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except (OperationalError, DBAPIError) as e:
                    msg = str(e).lower()
                    attempts += 1
                    if attempts >= max_attempts or ("deadlock detected" not in msg and "could not serialize" not in msg and "serialization" not in msg):
                        raise
                    time.sleep(delay)
        return wrapper
    return decorator

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


def _obtener_sancion_activa(caso_id):
    return CasoSancionado.query.filter_by(caso_id=caso_id, cancelado=False).order_by(CasoSancionado.fecha_sancion.desc()).first()


def _cancelar_sanciones_activas(caso_id, cancelado_por):
    caso = Caso.query.get(caso_id)
    sanciones_activas = CasoSancionado.query.filter_by(caso_id=caso_id, cancelado=False).all()
    fecha_cancelacion = datetime.utcnow()

    for sancion in sanciones_activas:
        if caso:
            for est in caso.involucrados:
                est.num_sanciones = max((est.num_sanciones or 0) - 1, 0)
        sancion.cancelado = True
        sancion.fecha_cancelacion = fecha_cancelacion
        sancion.cancelado_por = cancelado_por

    # Al cancelar sanciones, limpiar los votos de los profesores para permitir nueva deliberación
    if caso:
        caso.decisiones_profes = {}

    return sanciones_activas


def _normalizar_motivo_sancion(raw_reason, descripcion_sancion, user_id):
    if isinstance(raw_reason, dict):
        return raw_reason

    if raw_reason or descripcion_sancion:
        return {
            str(user_id): {
                'motivo': raw_reason or descripcion_sancion,
                'descripcion': descripcion_sancion or raw_reason or ''
            }
        }

    return None


def _acumular_motivo_sancion_pendiente(caso, reason_mapping):
    if not reason_mapping:
        return

    existente = caso.motivo_sancion or {}
    if not isinstance(existente, dict):
        existente = {}

    existente.update(reason_mapping)
    caso.motivo_sancion = existente


def _extraer_descripcion_desde_reason(reason_value):
    if isinstance(reason_value, dict) and reason_value:
        first = next(iter(reason_value.values()))
        if isinstance(first, dict):
            return first.get('descripcion') or first.get('motivo')
    if isinstance(reason_value, str):
        return reason_value
    return None

def to_dict(caso):
    return {
        'caso_id': caso.caso_id,
        'reporte_id': caso.reporte_id,
        'similitud': caso.similitud,
        'lineas': caso.lineas,
        'url_moss': caso.url_moss,
        'closed': caso.closed,
        'in_process': caso.in_process,
        'sancion': caso.sancion,
        'caso_metadata': caso.caso_metadata,
        'motivo_sancion': caso.motivo_sancion,
        'evaluacion_id': caso.evaluacion_id,
        'comentarios_profes': caso.comentarios_profes,
        'decisiones_profes': caso.decisiones_profes,
        'paralelos': _serializar_paralelos_caso(caso),
        'estudiantes': [
            {
                'estudiante_id': est.estudiante_id,
                'nombre': est.nombre,
                'apellido': est.apellido,
                'paralelo': est.paralelo.sigla_paralelo if est.paralelo else None
            }
            for est in caso.involucrados
        ],
        'usuarios_asignados': [
            {
                'user_id': user.user_id,
                'username': user.username,
                'email': user.email
            }
            for user in caso.usuarios_asignados
        ]
    }


def _crear_o_reactivar_sancion(caso, reason_mapping, comentarios_caso):
    """
    Crear o reactivar una sanción. `reason_mapping` es un dict opcional con claves user_id (string)
    y valores {'motivo': str, 'descripcion': str}.
    """
    sancion_activa = _obtener_sancion_activa(caso.caso_id)

    estudiantes_involucrados = {
        est.estudiante_id: {
            'nombre': est.nombre,
            'apellido': est.apellido,
            'paralelo': est.paralelo.sigla_paralelo if est.paralelo else None
        }
        for est in caso.involucrados
    }

    usuarios_involucrados = {
        usuario.user_id: {'nombre': usuario.username}
        for usuario in caso.usuarios_asignados
    }

    # Build a merged reason mapping: start with any pending case motivo, then overlay the provided reason_mapping
    merged_reason = {}
    existente = caso.motivo_sancion or {}
    if isinstance(existente, dict):
        merged_reason.update(existente)
    if isinstance(reason_mapping, dict):
        merged_reason.update(reason_mapping)

    reason_to_persist = merged_reason if merged_reason else None

    # synthesize a short description string from the merged reason for backward-compat DB column
    descripcion_para_persistir = _extraer_descripcion_desde_reason(reason_to_persist) or ''

    if sancion_activa:
        sancion_activa.estudiantes_involucrados = estudiantes_involucrados
        sancion_activa.profesores_involucrados = usuarios_involucrados
        # merge reason mappings if provided (preserve existing keys)
        existing = sancion_activa.reason or {}
        if not isinstance(existing, dict):
            existing = {}
        if reason_to_persist:
            existing.update(reason_to_persist)
        sancion_activa.reason = existing
        sancion_activa.comentarios_caso = comentarios_caso
        sancion_activa.cancelado = False
        sancion_activa.fecha_cancelacion = None
        sancion_activa.cancelado_por = None
        caso.motivo_sancion = None
        return sancion_activa, False

    sancion = CasoSancionado(
        caso_id=caso.caso_id,
        estudiantes_involucrados=estudiantes_involucrados,
        profesores_involucrados=usuarios_involucrados,
        reason=reason_to_persist,
        comentarios_caso=comentarios_caso,
    )
    db.session.add(sancion)
    caso.motivo_sancion = None
    return sancion, True



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
                'in_process': caso.in_process,
                'sancion': caso.sancion,
                'caso_metadata': caso.caso_metadata,
                'paralelos': _serializar_paralelos_caso(caso),
                'estudiantes': estudiantes,
                'usuarios_asignados': usuarios_asignados,
                'decisiones_profes': caso.decisiones_profes
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
        # obtain row-level lock so concurrent requests serialize on this case
        caso = db.session.execute(
            select(Caso).where(Caso.caso_id == caso_id).with_for_update()
        ).scalar_one_or_none()
        sancion_activa = CasoSancionado.query.filter_by(caso_id=caso_id, cancelado=False).order_by(CasoSancionado.fecha_sancion.desc()).first()
        
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

        reason_value = None
        descripcion_sancion = None
        if sancion_activa:
            reason_value = sancion_activa.reason
            descripcion_sancion = _extraer_descripcion_desde_reason(sancion_activa.reason)
        elif caso.motivo_sancion:
            reason_value = caso.motivo_sancion
            descripcion_sancion = _extraer_descripcion_desde_reason(caso.motivo_sancion)
        
        return jsonify({
            'caso_id': caso.caso_id,
            'reporte_id': caso.reporte_id,
            'similitud': caso.similitud,
            'lineas': caso.lineas,
            'url_moss': caso.url_moss,
            'closed': caso.closed,
            'in_process': caso.in_process,
            'sancion': caso.sancion,
            'caso_metadata': caso.caso_metadata,
            'motivo_sancion': caso.motivo_sancion,
            'reason': reason_value,
            'descripcion_sancion': descripcion_sancion,
            'comentarios_profes': caso.comentarios_profes if caso.comentarios_profes else [],
            'paralelos': _serializar_paralelos_caso(caso),
            'estudiantes': estudiantes,
            'usuarios_asignados': usuarios_asignados,
            'decisiones_profes': caso.decisiones_profes
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
                'reporte_id': caso.reporte_id,
                'similitud': caso.similitud,
                'lineas': caso.lineas,
                'url_moss': caso.url_moss,
                'closed': caso.closed,
                'in_process': caso.in_process,
                'sancion': caso.sancion,
                'caso_metadata': caso.caso_metadata,
                'paralelos': _serializar_paralelos_caso(caso),
                'estudiantes': estudiantes,
                'usuarios_asignados': usuarios_asignados
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
                'in_process': caso.in_process,
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


@casos_bp.route('/ObtenerStatsCasosPorParalelosAndEvaluacionIdMisParalelos/<int:evaluacion_id>', methods=['GET'])
@jwt_required()
def obtener_stats_casos_por_paralelos_evaluacion_mis_paralelos(evaluacion_id):
    try:
        current_user_id = int(get_jwt_identity())
        usuario = User.query.get(current_user_id)

        if not usuario:
            return jsonify({"msg": "Usuario no encontrado"}), 404

        paralelo_ids = [paralelo.paralelo_id for paralelo in usuario.paralelos]
        if not paralelo_ids:
            return jsonify([]), 200

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
            Caso.evaluacion_id == evaluacion_id,
            Paralelo.paralelo_id.in_(paralelo_ids)
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
                'in_process': caso.in_process,
                'sancion': caso.sancion,
                'caso_metadata': caso.caso_metadata,
                'estudiantes': estudiantes,
                'usuarios_asignados': usuarios_asignados,
                'decisiones_profes': caso.decisiones_profes
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
@retry_db()
def marcar_caso_revisado(caso_id):
    try:
        current_user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        
        # Buscar caso por id solamente (sin filtrar por usuario) y bloquear fila
        caso = db.session.execute(
            select(Caso).where(Caso.caso_id == caso_id).with_for_update()
        ).scalar_one_or_none()
        accion = data.get('sancion')
        descripcion_sancion = data.get('descripcion_sancion')
        if not caso:
            return jsonify({"msg": "Caso no encontrado"}), 404

        # validar campo sancion
        if accion is None:
            return jsonify({"msg": "Se requiere el campo 'sancion' (true|false)"}), 400

        decisiones = caso.decisiones_profes or {}
        assigned_ids = [u.user_id for u in caso.usuarios_asignados]
        es_asignado = current_user_id in assigned_ids

        # Caso: 1 usuario asignado o ninguno (decisión directa)
        if len(assigned_ids) <= 1:
            decisiones[str(current_user_id)] = bool(accion)
            caso.decisiones_profes = decisiones
            caso.sancion = bool(accion)
            caso.closed = True
            caso.in_process = False

            if caso.sancion:
                # Use centralized helpers to normalize, accumulate and create/reactivate sancion
                raw_reason = data.get('reason')
                reason_mapping = _normalizar_motivo_sancion(raw_reason, descripcion_sancion, current_user_id)

                # Accumulate pending motivo in `caso` if provided
                _acumular_motivo_sancion_pendiente(caso, reason_mapping)

                # Create or reactivate sanction using helper (handles merging with caso.motivo_sancion)
                sancion_obj, sancion_creada = _crear_o_reactivar_sancion(caso, reason_mapping, caso.comentarios_profes)

                if sancion_creada:
                    for est in caso.involucrados:
                        est.num_sanciones = (est.num_sanciones or 0) + 1
            else:
                # Inline cancelar sanciones activas
                sanciones_activas = CasoSancionado.query.filter_by(caso_id=caso.caso_id, cancelado=False).all()
                fecha_cancelacion = datetime.utcnow()
                for sancion in sanciones_activas:
                    for est in caso.involucrados:
                        est.num_sanciones = max((est.num_sanciones or 0) - 1, 0)
                    sancion.cancelado = True
                    sancion.fecha_cancelacion = fecha_cancelacion
                    sancion.cancelado_por = current_user_id
                caso.decisiones_profes = {}

        # Caso: 2 o más usuarios asignados -> requiere consenso entre los asignados
        else:
            # Registrar/eliminar voto del usuario actual
            decisiones[str(current_user_id)] = bool(accion)
            caso.decisiones_profes = decisiones

            # Revisar si el otro asignado ya votó y si hay consenso
            claves = set(int(k) for k in decisiones.keys())
            asignados = set(assigned_ids)

            if not claves.issuperset(asignados):
                # No todos han votado aún -> no cerrar
                caso.closed = False
                caso.sancion = None
                caso.in_process = True
                # Inline acumular motivo pendiente
                raw_reason = data.get('reason')
                if isinstance(raw_reason, dict):
                    reason_mapping = raw_reason
                else:
                    if raw_reason or descripcion_sancion:
                        reason_mapping = {
                            str(current_user_id): {
                                'motivo': raw_reason or descripcion_sancion,
                                'descripcion': descripcion_sancion or raw_reason or ''
                            }
                        }
                    else:
                        reason_mapping = None

                if reason_mapping:
                    existente = caso.motivo_sancion or {}
                    if not isinstance(existente, dict):
                        existente = {}
                    existente.update(reason_mapping)
                    caso.motivo_sancion = existente
                # Si existe una sanción activa pero el usuario votó en contra (indulto),
                # cancelar la sanción activa inmediatamente para revertir efectos previos.
                sancion_activa = _obtener_sancion_activa(caso.caso_id)
                if sancion_activa and not bool(accion):
                    _cancelar_sanciones_activas(caso.caso_id, current_user_id)
            else:
                valores = set(decisiones.get(str(uid)) for uid in assigned_ids)
                if len(valores) == 1:
                    # Todos coincidieron -> cerrar con la decisión común
                    decision_comun = list(valores)[0]
                    caso.sancion = decision_comun
                    caso.closed = True
                    caso.in_process = False

                    if caso.sancion:
                        reason_mapping = _normalizar_motivo_sancion(data.get('reason'), descripcion_sancion, current_user_id)
                        _acumular_motivo_sancion_pendiente(caso, reason_mapping)

                        _, sancion_creada = _crear_o_reactivar_sancion(
                            caso=caso,
                            reason_mapping=reason_mapping,
                            comentarios_caso=caso.comentarios_profes,
                        )
                        if sancion_creada:
                            for est in caso.involucrados:
                                est.num_sanciones = (est.num_sanciones or 0) + 1
                    else:
                        _cancelar_sanciones_activas(caso.caso_id, current_user_id)
                else:
                    # Desacuerdo -> mantener abierto
                    caso.sancion = None
                    caso.closed = False
                    caso.in_process = True

                    # Inline acumular motivo pendiente
                    raw_reason = data.get('reason')
                    if isinstance(raw_reason, dict):
                        reason_mapping = raw_reason
                    else:
                        if raw_reason or descripcion_sancion:
                            reason_mapping = {
                                str(current_user_id): {
                                    'motivo': raw_reason or descripcion_sancion,
                                    'descripcion': descripcion_sancion or raw_reason or ''
                                }
                            }
                        else:
                            reason_mapping = None

                    if reason_mapping:
                        existente = caso.motivo_sancion or {}
                        if not isinstance(existente, dict):
                            existente = {}
                        existente.update(reason_mapping)
                        caso.motivo_sancion = existente

                    # Inline cancelar sanciones activas
                    sanciones_activas = CasoSancionado.query.filter_by(caso_id=caso.caso_id, cancelado=False).all()
                    fecha_cancelacion = datetime.utcnow()
                    for sancion in sanciones_activas:
                        for est in caso.involucrados:
                            est.num_sanciones = max((est.num_sanciones or 0) - 1, 0)
                        sancion.cancelado = True
                        sancion.fecha_cancelacion = fecha_cancelacion
                        sancion.cancelado_por = current_user_id
                    caso.decisiones_profes = {}

        db.session.commit()
        
        return jsonify({"msg": "Decisión registrada", "caso_id": caso.caso_id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al marcar caso como revisado", "error": str(e)}), 500


@casos_bp.route('/SancionarCaso/<int:caso_id>', methods=['POST'])
@jwt_required()
@retry_db()
def sancionar_caso(caso_id):
    try:
        current_user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        descripcion_sancion = data.get('descripcion_sancion')

        caso = db.session.execute(
            select(Caso).where(Caso.caso_id == caso_id).with_for_update()
        ).scalar_one_or_none()
        if not caso:
            return jsonify({"msg": "Caso no encontrado"}), 404

        assigned_ids = [u.user_id for u in caso.usuarios_asignados]
        decisiones = caso.decisiones_profes or {}

        raw_reason = data.get('reason')
        if isinstance(raw_reason, dict):
            reason_mapping = raw_reason
        else:
            if raw_reason or descripcion_sancion:
                reason_mapping = {
                    str(current_user_id): {
                        'motivo': raw_reason or descripcion_sancion,
                        'descripcion': descripcion_sancion or raw_reason or ''
                    }
                }
            else:
                reason_mapping = None

        # Single assignee -> immediate sanction
        if len(assigned_ids) <= 1:
            decisiones[str(current_user_id)] = True
            caso.decisiones_profes = decisiones
            caso.sancion = True
            caso.closed = True
            caso.in_process = False

            # Inline acumular motivo pendiente
            if reason_mapping:
                existente = caso.motivo_sancion or {}
                if not isinstance(existente, dict):
                    existente = {}
                existente.update(reason_mapping)
                caso.motivo_sancion = existente

            # Inline crear/reactivar sancion
            sancion_activa = CasoSancionado.query.filter_by(caso_id=caso.caso_id, cancelado=False).order_by(CasoSancionado.fecha_sancion.desc()).first()

            estudiantes_involucrados = {
                est.estudiante_id: {
                    'nombre': est.nombre,
                    'apellido': est.apellido,
                    'paralelo': est.paralelo.sigla_paralelo if est.paralelo else None
                }
                for est in caso.involucrados
            }

            usuarios_involucrados = {
                usuario.user_id: {'nombre': usuario.username}
                for usuario in caso.usuarios_asignados
            }

            merged_reason = {}
            existente = caso.motivo_sancion or {}
            if isinstance(existente, dict):
                merged_reason.update(existente)
            if isinstance(reason_mapping, dict):
                merged_reason.update(reason_mapping)

            reason_to_persist = merged_reason if merged_reason else None
            descripcion_para_persistir = _extraer_descripcion_desde_reason(reason_to_persist) or ''

            sancion_creada = False
            if sancion_activa:
                existing = sancion_activa.reason or {}
                if not isinstance(existing, dict):
                    existing = {}
                if reason_to_persist:
                    existing.update(reason_to_persist)
                sancion_activa.reason = existing
                sancion_activa.estudiantes_involucrados = estudiantes_involucrados
                sancion_activa.profesores_involucrados = usuarios_involucrados
                sancion_activa.comentarios_caso = caso.comentarios_profes
                sancion_activa.cancelado = False
                sancion_activa.fecha_cancelacion = None
                sancion_activa.cancelado_por = None
                caso.motivo_sancion = None
            else:
                sancion = CasoSancionado(
                    caso_id=caso.caso_id,
                    estudiantes_involucrados=estudiantes_involucrados,
                    profesores_involucrados=usuarios_involucrados,
                    reason=reason_to_persist,
                    comentarios_caso=caso.comentarios_profes,
                )
                db.session.add(sancion)
                caso.motivo_sancion = None
                sancion_creada = True

            if sancion_creada:
                for est in caso.involucrados:
                    est.num_sanciones = (est.num_sanciones or 0) + 1

            # flush pending changes and build payload from in-memory object to avoid extra SELECT
            db.session.flush()
            caso_payload = to_dict(caso)
            db.session.commit()
            return jsonify({"msg": "Sanción aplicada", "caso": caso_payload}), 200

        # Multi-assigned -> register vote and check consensus
        decisiones[str(current_user_id)] = True
        caso.decisiones_profes = decisiones
        _acumular_motivo_sancion_pendiente(caso, reason_mapping)

        claves = set(int(k) for k in decisiones.keys())
        asignados = set(assigned_ids)

        if claves.issuperset(asignados):
            valores = set(decisiones.get(str(uid)) for uid in assigned_ids)
            if len(valores) == 1 and list(valores)[0] is True:
                caso.sancion = True
                caso.closed = True
                caso.in_process = False
                sancion, creada = _crear_o_reactivar_sancion(caso=caso, reason_mapping=reason_mapping, comentarios_caso=caso.comentarios_profes)
                if creada:
                    for est in caso.involucrados:
                        est.num_sanciones = (est.num_sanciones or 0) + 1
        else:
            caso.closed = False
            caso.sancion = None
            caso.in_process = True

        db.session.flush()
        caso_payload = to_dict(caso)
        db.session.commit()
        return jsonify({"msg": "Voto registrado", "caso": caso_payload}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al sancionar caso", "error": str(e)}), 500


@casos_bp.route('/IndultarCaso/<int:caso_id>', methods=['POST'])
@jwt_required()
@retry_db()
def indultar_caso(caso_id):
    try:
        current_user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        descripcion_sancion = data.get('descripcion_sancion')

        caso = db.session.execute(
            select(Caso).where(Caso.caso_id == caso_id).with_for_update()
        ).scalar_one_or_none()
        if not caso:
            return jsonify({"msg": "Caso no encontrado"}), 404

        assigned_ids = [u.user_id for u in caso.usuarios_asignados]
        decisiones = caso.decisiones_profes or {}

        reason_mapping = _normalizar_motivo_sancion(data.get('reason'), descripcion_sancion, current_user_id)

        # Single assignee -> immediate indulto (cancel active sanctions)
        if len(assigned_ids) <= 1:
            decisiones[str(current_user_id)] = False
            caso.decisiones_profes = decisiones
            caso.sancion = False
            caso.closed = True
            caso.in_process = False

            # Inline acumular motivo pendiente
            if reason_mapping:
                existente = caso.motivo_sancion or {}
                if not isinstance(existente, dict):
                    existente = {}
                existente.update(reason_mapping)
                caso.motivo_sancion = existente

            # Inline cancelar sanciones activas
            sanciones_activas = CasoSancionado.query.filter_by(caso_id=caso.caso_id, cancelado=False).all()
            fecha_cancelacion = datetime.utcnow()
            for sancion in sanciones_activas:
                for est in caso.involucrados:
                    est.num_sanciones = max((est.num_sanciones or 0) - 1, 0)
                sancion.cancelado = True
                sancion.fecha_cancelacion = fecha_cancelacion
                sancion.cancelado_por = current_user_id
            caso.decisiones_profes = {}

            db.session.flush()
            caso_payload = to_dict(caso)
            db.session.commit()
            return jsonify({"msg": "Indulto aplicado", "caso": caso_payload}), 200

        # Multi-assigned -> register vote and check consensus
        decisiones[str(current_user_id)] = False
        caso.decisiones_profes = dict(decisiones)
        flag_modified(caso, 'decisiones_profes')
        _acumular_motivo_sancion_pendiente(caso, reason_mapping)
        flag_modified(caso, 'motivo_sancion')

        claves = set(int(k) for k in decisiones.keys())
        asignados = set(assigned_ids)

        if claves.issuperset(asignados):
            valores = set(decisiones.get(str(uid)) for uid in assigned_ids)
            if len(valores) == 1 and list(valores)[0] is False:
                caso.sancion = False
                caso.closed = True
                caso.in_process = False
                _cancelar_sanciones_activas(caso.caso_id, current_user_id)
        else:
            caso.closed = False
            caso.sancion = None
            caso.in_process = True

        db.session.flush()
        caso_payload = to_dict(caso)
        db.session.commit()
        return jsonify({"msg": "Voto registrado (indulto)", "caso": caso_payload}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al indultar caso", "error": str(e)}), 500


@casos_bp.route('/CambiarOpinion/<int:caso_id>', methods=['POST'])
@jwt_required()
@retry_db()
def cambiar_opinion(caso_id):
    try:
        current_user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        sancion = data.get('sancion')
        descripcion_sancion = data.get('descripcion_sancion')
        reason_mapping = _normalizar_motivo_sancion(data.get('reason'), descripcion_sancion, current_user_id)
        caso = Caso.query.get(caso_id)
        if not caso:
            return jsonify({"msg": "Caso no encontrado"}), 404
        if caso.in_process == False:
            return jsonify({"msg": "No se puede cambiar opinión de un caso cerrado"}), 400

        assigned_ids = [u.user_id for u in caso.usuarios_asignados]

        # Defensive normalization
        decisiones = caso.decisiones_profes or {}
        motivos = caso.motivo_sancion or {}
        metadata = caso.caso_metadata or {}
        if not isinstance(metadata, dict):
            metadata = {}

        key = str(current_user_id)
        current_vote = decisiones.get(key)
        new_vote = bool(sancion)

        if current_vote == new_vote:
            return jsonify({"msg": "La opinión es la misma que ya había registrado"}), 400

        motivo_anterior = None
        if isinstance(motivos, dict):
            motivo_previo = motivos.get(key)
            if isinstance(motivo_previo, dict):
                motivo_anterior = {
                    'motivo': motivo_previo.get('motivo'),
                    'descripcion': motivo_previo.get('descripcion')
                }
            elif motivo_previo is not None:
                motivo_anterior = {
                    'motivo': motivo_previo,
                    'descripcion': motivo_previo
                }

        historial = metadata.get('historial_cambios_opinion')
        if not isinstance(historial, list):
            historial = []

        historial.append({
            'user_id': current_user_id,
            'desde': current_vote,
            'hacia': new_vote,
            'motivo_anterior': motivo_anterior,
            'timestamp': datetime.utcnow().isoformat()
        })
        metadata['historial_cambios_opinion'] = historial

        # Apply new vote and clear any pending motivo for this user
        decisiones[key] = new_vote
        # Assign a new dict so SQLAlchemy JSON change is detected
        caso.decisiones_profes = dict(decisiones)
        flag_modified(caso, 'decisiones_profes')

        if isinstance(motivos, dict):
            if new_vote is False:
                motivos.pop(key, None)
            else:
                if reason_mapping:
                    motivos.update(reason_mapping)
                else:
                    motivos[key] = motivos.get(key)

            caso.motivo_sancion = dict(motivos) if motivos else None
            flag_modified(caso, 'motivo_sancion')

        caso.caso_metadata = metadata
        flag_modified(caso, 'caso_metadata')

        if len(assigned_ids) <= 1:
            caso.sancion = new_vote
            caso.closed = True
            caso.in_process = False

            if new_vote:
                _acumular_motivo_sancion_pendiente(caso, reason_mapping)
                flag_modified(caso, 'motivo_sancion')

                _, sancion_creada = _crear_o_reactivar_sancion(
                    caso=caso,
                    reason_mapping=reason_mapping,
                    comentarios_caso=caso.comentarios_profes,
                )
                if sancion_creada:
                    for est in caso.involucrados:
                        est.num_sanciones = (est.num_sanciones or 0) + 1
            else:
                _cancelar_sanciones_activas(caso.caso_id, current_user_id)
        else:
            valores = set(decisiones.get(str(uid)) for uid in assigned_ids)

            if len(valores) == 1:
                decision_comun = list(valores)[0]
                caso.sancion = decision_comun
                caso.closed = True
                caso.in_process = False

                if decision_comun:
                    _acumular_motivo_sancion_pendiente(caso, reason_mapping)
                    flag_modified(caso, 'motivo_sancion')

                    _, sancion_creada = _crear_o_reactivar_sancion(
                        caso=caso,
                        reason_mapping=reason_mapping,
                        comentarios_caso=caso.comentarios_profes,
                    )
                    if sancion_creada:
                        for est in caso.involucrados:
                            est.num_sanciones = (est.num_sanciones or 0) + 1
                else:
                    _cancelar_sanciones_activas(caso.caso_id, current_user_id)
            else:
                caso.closed = False
                caso.sancion = None
                caso.in_process = True

                if not new_vote:
                    sancion_activa = _obtener_sancion_activa(caso.caso_id)
                    if sancion_activa:
                        _cancelar_sanciones_activas(caso.caso_id, current_user_id)

        db.session.commit()
        # reload to ensure freshest DB state
        caso = Caso.query.get(caso.caso_id)
        # Rebuild the caso payload to ensure it contains the freshly-applied JSON fields
        caso_payload = to_dict(caso)
        caso_payload['decisiones_profes'] = dict(decisiones)
        caso_payload['motivo_sancion'] = dict(motivos) if isinstance(motivos, dict) and motivos else None

        # Return the applied vote explicitly for client-side verification
        return jsonify({"msg": "Opinión cambiada", "caso": caso_payload, "applied_vote": decisiones.get(key)}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al cambiar opinión", "error": str(e)}), 500
    
@casos_bp.route('/ForzarSancion/<int:caso_id>', methods=['POST'])
@jwt_required()
def forzar_sancion(caso_id):

    try:
        current_user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        usuario_actual = User.query.get(current_user_id)
        if not usuario_actual or usuario_actual.rol_id != 1:
            return jsonify({"msg": "No tiene permisos para forzar sanción"}), 403

        caso = Caso.query.get(caso_id)
        if not caso:
            return jsonify({"msg": "Caso no encontrado"}), 404

        caso.sancion = True
        caso.closed = True
        caso.in_process = False
        decisiones = caso.decisiones_profes or {}
        decisiones[str(current_user_id)] = True
        caso.decisiones_profes = decisiones

        descripcion = data.get('descripcion_sancion', 'Amonestación por plagio')
        reason_mapping = _normalizar_motivo_sancion(data.get('reason'), descripcion, current_user_id)
        _acumular_motivo_sancion_pendiente(caso, reason_mapping)

        _, sancion_creada = _crear_o_reactivar_sancion(
            caso=caso,
            reason_mapping=reason_mapping,
            comentarios_caso=caso.comentarios_profes,
        )
        if sancion_creada:
            for est in caso.involucrados:
                est.num_sanciones = (est.num_sanciones or 0) + 1
        db.session.flush()
        caso_payload = to_dict(caso)
        db.session.commit()

        return jsonify({"msg": "Sanción forzada correctamente", "caso": caso_payload}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al forzar sanción", "error": str(e)}), 500


@casos_bp.route('/ForzarIndulto/<int:caso_id>', methods=['POST'])
@jwt_required()
def forzar_indulto(caso_id):
    try:
        current_user_id = int(get_jwt_identity())
        usuario_actual = User.query.get(current_user_id)
        if not usuario_actual or usuario_actual.rol_id != 1:
            return jsonify({"msg": "No tiene permisos para forzar indulto"}), 403

        caso = Caso.query.get(caso_id)
        if not caso:
            return jsonify({"msg": "Caso no encontrado"}), 404

        caso.sancion = False
        caso.closed = True
        caso.in_process = False
        decisiones = caso.decisiones_profes or {}
        decisiones[str(current_user_id)] = False
        caso.decisiones_profes = decisiones

        _cancelar_sanciones_activas(caso.caso_id, current_user_id)

        db.session.flush()
        caso_payload = to_dict(caso)
        db.session.commit()
        return jsonify({"msg": "Indulto forzado correctamente", "caso": caso_payload}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al forzar indulto", "error": str(e)}), 500


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
    
@casos_bp.route('/ActualizarCasoPorCasoId/<int:caso_id>', methods=['PUT'])
@jwt_required()
def actualizar_caso_por_id(caso_id):
    try:
        current_user_id = int(get_jwt_identity())
        if not request.is_json:
            return jsonify({"msg": "Se requiere un body JSON válido"}), 400

        data = request.get_json(silent=False) or {}
        
        caso = Caso.query.get(caso_id)
        
        if not caso:
            return jsonify({"msg": "Caso no encontrado o no tiene permisos"}), 404
        
        # Solo permitir actualizar ciertos campos
        allowed_fields = {'similitud', 'lineas', 'url_moss', 'caso_metadata', 'motivo_sancion', 'in_process', 'closed', 'sancion'}
        fields_updated = []
        for field in allowed_fields:
            if field in data:
                value = data[field]
                if field in {'in_process', 'closed', 'sancion'} and value is not None:
                    if isinstance(value, str):
                        value = value.strip().lower() in {'1', 'true', 'yes', 'si', 'on'}
                    else:
                        value = bool(value)
                setattr(caso, field, value)
                fields_updated.append(field)
        
        db.session.commit()
        
        return jsonify({
            "msg": "Caso actualizado correctamente",
            "caso_id": caso.caso_id,
            "fields_actualizadas": fields_updated,
            "estado_actual": {
                "in_process": caso.in_process,
                "closed": caso.closed,
                "sancion": caso.sancion
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al actualizar caso", "error": str(e)}), 500