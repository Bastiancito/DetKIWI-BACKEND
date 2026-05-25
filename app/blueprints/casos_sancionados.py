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
        "descripcion_sancion": sancion.descripcion_sancion,
        "fecha_sancion": sancion.fecha_sancion.isoformat() if sancion.fecha_sancion else None
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


# Payload: {"caso_id": int, "descripcion_sancion": "string", "estudiantes_involucrados": object (opcional), "profesores_involucrados": object (opcional)}
@casos_sancionados_bp.route('/CrearCasoSancionado', methods=['POST'])
@jwt_required()
def crear_caso_sancionado():
    try:
        current_user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}

        caso_id = data.get('caso_id')
        descripcion_sancion = data.get('descripcion_sancion')
        estudiantes_involucrados = data.get('estudiantes_involucrados')
        profesores_involucrados = data.get('profesores_involucrados')

        if not caso_id:
            return jsonify({"msg": "El campo caso_id es requerido"}), 400

        if not descripcion_sancion:
            return jsonify({"msg": "El campo descripcion_sancion es requerido"}), 400

        caso = _usuario_tiene_acceso_al_caso(caso_id, current_user_id)
        if not caso:
            return jsonify({"msg": "Caso no encontrado o no tiene permisos"}), 404

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

        nueva_sancion = CasoSancionado(
            caso_id=caso.caso_id,
            estudiantes_involucrados=estudiantes_involucrados,
            profesores_involucrados=profesores_involucrados,
            descripcion_sancion=descripcion_sancion
        )

        caso.sancion = True
        caso.closed = True

        db.session.add(nueva_sancion)
        db.session.commit()

        return jsonify({
            "msg": "Caso sancionado creado exitosamente",
            "sancion": _serializar_sancion(nueva_sancion)
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al crear caso sancionado", "error": str(e)}), 500


# Payload: {"descripcion_sancion": "string" (opcional), "estudiantes_involucrados": object (opcional), "profesores_involucrados": object (opcional)}
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

        if 'descripcion_sancion' in data:
            if not data['descripcion_sancion']:
                return jsonify({"msg": "descripcion_sancion no puede estar vacio"}), 400
            sancion.descripcion_sancion = data['descripcion_sancion']

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

        db.session.delete(sancion)

        sanciones_restantes = CasoSancionado.query.filter_by(caso_id=caso.caso_id).count()
        if sanciones_restantes <= 1:
            caso.sancion = False

        db.session.commit()

        return jsonify({"msg": "Caso sancionado eliminado exitosamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al eliminar caso sancionado", "error": str(e)}), 500
