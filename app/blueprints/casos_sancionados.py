from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models import CasoSancionado, Caso, Reporte, User


casos_sancionados_bp = Blueprint('casos_sancionados', __name__)


def _serializar_sancion(sancion):
    return {
        "sancion_id": sancion.sancion_id,
        "caso_id": sancion.caso_id,
        "estudiantes_involucrados": sancion.estudiantes_involucrados,
        "profesores_involucrados": sancion.profesores_involucrados,
        "comments": sancion.comentarios_caso,
        "reason": sancion.reason,
        # backward-compat: expose a synthesized descripcion_sancion (first provided description)
        "descripcion_sancion": (lambda r: (next(iter(r.values())).get('descripcion') if isinstance(r, dict) and len(r) > 0 else None))(sancion.reason),
        "fecha_sancion": sancion.fecha_sancion.isoformat() if sancion.fecha_sancion else None,
        "cancelado": sancion.cancelado,
        "fecha_cancelacion": sancion.fecha_cancelacion.isoformat() if sancion.fecha_cancelacion else None,
        "cancelado_por": sancion.cancelado_por
    }


def _usuario_tiene_acceso_al_caso(caso_id, user_id):
    return Caso.query.join(Reporte).filter(
        Caso.caso_id == caso_id,
        db.or_(
            Reporte.user_id == user_id,
            Caso.usuarios_asignados.any(User.user_id == user_id)
        )
    ).first()


@casos_sancionados_bp.route('/ObtenerCasosSancionados', methods=['GET'])
@jwt_required()
def obtener_casos_sancionados():
    try:
        current_user_id = int(get_jwt_identity())

        query = CasoSancionado.query.join(Caso).join(Reporte).filter(
            db.or_(
                Reporte.user_id == current_user_id,
                Caso.usuarios_asignados.any(User.user_id == current_user_id)
            )
        )

        caso_id = request.args.get('caso_id', type=int)
        if caso_id is not None:
            query = query.filter(CasoSancionado.caso_id == caso_id)

        solo_activas = request.args.get('solo_activas', 'false').lower() == 'true'
        if solo_activas:
            query = query.filter(CasoSancionado.cancelado.is_(False))

        sanciones = query.order_by(CasoSancionado.fecha_sancion.desc()).all()

        return jsonify({
            "total": len(sanciones),
            "sanciones": [_serializar_sancion(s) for s in sanciones]
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener casos sancionados", "error": str(e)}), 500


@casos_sancionados_bp.route('/ObtenerCasoSancionadoPorId/<int:sancion_id>', methods=['GET'])
@jwt_required()
def obtener_caso_sancionado_por_id(sancion_id):
    try:
        current_user_id = int(get_jwt_identity())

        sancion = CasoSancionado.query.get(sancion_id)
        if not sancion:
            return jsonify({"msg": "Caso sancionado no encontrado"}), 404

        caso = _usuario_tiene_acceso_al_caso(sancion.caso_id, current_user_id)
        if not caso:
            return jsonify({"msg": "No tiene permisos para ver esta sancion"}), 403

        return jsonify(_serializar_sancion(sancion)), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener caso sancionado", "error": str(e)}), 500


# Payload: {"caso_id": int, "reason": object|string (opcional), "descripcion_sancion": string (opcional for backward compat), "estudiantes_involucrados": object (opcional), "profesores_involucrados": object (opcional)}
@casos_sancionados_bp.route('/CrearCasoSancionado', methods=['POST'])
@jwt_required()
def crear_caso_sancionado():
    try:
        current_user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}

        caso_id = data.get('caso_id')
        descripcion_sancion = data.get('descripcion_sancion')
        reason = data.get('reason')
        estudiantes_involucrados = data.get('estudiantes_involucrados')
        profesores_involucrados = data.get('profesores_involucrados')

        if not caso_id:
            return jsonify({"msg": "El campo caso_id es requerido"}), 400

        # Accept either a per-user `reason` mapping or a single reason + descripcion (legacy).
        reason_mapping = None
        if isinstance(reason, dict):
            reason_mapping = reason
        else:
            # Build mapping from current user if a scalar reason or descripcion provided
            if reason or descripcion_sancion:
                reason_mapping = {
                    str(current_user_id): {
                        'motivo': reason or descripcion_sancion,
                        'descripcion': descripcion_sancion or reason or ''
                    }
                }

        # If no reason mapping and none provided, allow creation but reason will be null

        caso = _usuario_tiene_acceso_al_caso(caso_id, current_user_id)
        if not caso:
            return jsonify({"msg": "Caso no encontrado o no tiene permisos"}), 404

        if reason_mapping is None:
            reason_mapping = caso.motivo_sancion

        if estudiantes_involucrados is None:
            estudiantes_involucrados = {
                est.estudiante_id: {
                    'nombre': est.nombre,
                    'apellido': est.apellido,
                    'paralelo': est.paralelo.sigla_paralelo if est.paralelo else None
                }
                for est in caso.involucrados
            }

        if profesores_involucrados is None:
            profesores_involucrados = {}
            if caso.reporte and caso.reporte.user_id:
                profesor_reporte = User.query.get(caso.reporte.user_id)
                if profesor_reporte:
                    profesores_involucrados[profesor_reporte.user_id] = {
                        'username': profesor_reporte.username,
                        'email': profesor_reporte.email
                    }

            for profesor in caso.usuarios_asignados:
                profesores_involucrados[profesor.user_id] = {
                    'username': profesor.username,
                    'email': profesor.email
                }

        sancion_activa = CasoSancionado.query.filter_by(caso_id=caso.caso_id, cancelado=False).first()
        if sancion_activa:
            sancion_activa.estudiantes_involucrados = estudiantes_involucrados
            sancion_activa.profesores_involucrados = profesores_involucrados
            # merge reason mappings if provided
            if reason_mapping:
                existing = sancion_activa.reason or {}
                existing.update(reason_mapping)
                sancion_activa.reason = existing
            sancion_activa.cancelado = False
            sancion_activa.fecha_cancelacion = None
            sancion_activa.cancelado_por = None
            caso.motivo_sancion = None

            caso.sancion = True
            caso.closed = True

            db.session.commit()

            return jsonify({
                "msg": "Caso sancionado actualizado exitosamente",
                "sancion": _serializar_sancion(sancion_activa)
            }), 200

        nueva_sancion = CasoSancionado(
            caso_id=caso.caso_id,
            estudiantes_involucrados=estudiantes_involucrados,
            profesores_involucrados=profesores_involucrados,
            reason=reason_mapping,
            cancelado=False,
            fecha_cancelacion=None,
            cancelado_por=None
        )

        caso.sancion = True
        caso.closed = True
        caso.motivo_sancion = None

        db.session.add(nueva_sancion)
        db.session.commit()

        return jsonify({
            "msg": "Caso sancionado creado exitosamente",
            "sancion": _serializar_sancion(nueva_sancion)
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al crear caso sancionado", "error": str(e)}), 500


# Payload: {"reason": object|string (opcional), "descripcion_sancion": string (optional legacy), "estudiantes_involucrados": object (opcional), "profesores_involucrados": object (opcional)}
@casos_sancionados_bp.route('/ActualizarCasoSancionado/<int:sancion_id>', methods=['PUT'])
@jwt_required()
def actualizar_caso_sancionado(sancion_id):
    try:
        current_user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}

        sancion = CasoSancionado.query.get(sancion_id)
        if not sancion:
            return jsonify({"msg": "Caso sancionado no encontrado"}), 404

        caso = _usuario_tiene_acceso_al_caso(sancion.caso_id, current_user_id)
        if not caso:
            return jsonify({"msg": "No tiene permisos para actualizar esta sancion"}), 403

        # Support updating reason as mapping or legacy scalar+descripcion
        if 'descripcion_sancion' in data:
            # legacy field: set as description for current user in reason mapping
            desc = data['descripcion_sancion']
            if not desc:
                return jsonify({"msg": "descripcion_sancion no puede estar vacio"}), 400
            existing = sancion.reason or {}
            existing[str(current_user_id)] = existing.get(str(current_user_id), {})
            existing[str(current_user_id)]['descripcion'] = desc
            sancion.reason = existing

        if 'reason' in data:
            r = data['reason']
            if isinstance(r, dict):
                existing = sancion.reason or {}
                existing.update(r)
                sancion.reason = existing
            else:
                # scalar reason -> set for current user
                existing = sancion.reason or {}
                existing[str(current_user_id)] = {'motivo': r, 'descripcion': existing.get(str(current_user_id), {}).get('descripcion', r)}
                sancion.reason = existing

        if 'estudiantes_involucrados' in data:
            sancion.estudiantes_involucrados = data['estudiantes_involucrados']

        if 'profesores_involucrados' in data:
            sancion.profesores_involucrados = data['profesores_involucrados']

        db.session.commit()

        return jsonify({
            "msg": "Caso sancionado actualizado exitosamente",
            "sancion": _serializar_sancion(sancion)
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al actualizar caso sancionado", "error": str(e)}), 500


@casos_sancionados_bp.route('/EliminarCasoSancionado/<int:sancion_id>', methods=['DELETE'])
@jwt_required()
def eliminar_caso_sancionado(sancion_id):
    try:
        current_user_id = int(get_jwt_identity())

        sancion = CasoSancionado.query.get(sancion_id)
        if not sancion:
            return jsonify({"msg": "Caso sancionado no encontrado"}), 404

        caso = _usuario_tiene_acceso_al_caso(sancion.caso_id, current_user_id)
        if not caso:
            return jsonify({"msg": "No tiene permisos para eliminar esta sancion"}), 403

        if sancion.cancelado:
            return jsonify({"msg": "Caso sancionado ya estaba cancelado", "sancion": _serializar_sancion(sancion)}), 200

        for estudiante in caso.involucrados:
            estudiante.num_sanciones = max((estudiante.num_sanciones or 0) - 1, 0)

        sancion.cancelado = True
        sancion.fecha_cancelacion = datetime.utcnow()
        sancion.cancelado_por = current_user_id
        caso.sancion = False
        caso.closed = True
        # Limpiar votos de profesores al cancelar la sanción para que puedan volver a deliberar
        caso.decisiones_profes = {}

        db.session.commit()

        return jsonify({"msg": "Caso sancionado cancelado exitosamente", "sancion": _serializar_sancion(sancion)}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al eliminar caso sancionado", "error": str(e)}), 500
