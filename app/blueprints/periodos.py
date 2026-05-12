from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models import Periodo, Evaluacion

periodos_bp = Blueprint('periodos', __name__)

# Payload: {"nombre": "string", "anio": int, "semestre": int (1 o 2), "activo": bool (opcional, default false)}
@periodos_bp.route('/CrearPeriodo', methods=['POST'])
@jwt_required()
def crear_periodo():
    try:
        data = request.get_json()
        
        nombre = data.get('nombre')
        anio = data.get('anio')
        semestre = data.get('semestre')
        activo = data.get('activo', False)
        
        if not nombre or not anio or not semestre:
            return jsonify({"msg": "nombre, anio y semestre son requeridos"}), 400
        
        if semestre not in [1, 2]:
            return jsonify({"msg": "semestre debe ser 1 o 2"}), 400
        
        if activo:
            Periodo.query.update({Periodo.activo: False})
        
        nuevo_periodo = Periodo(
            nombre="{}-{}".format(anio, semestre),
            anio=anio,
            semestre=semestre,
            activo=activo
        )
        
        
        db.session.add(nuevo_periodo)
        db.session.commit()
        
        return jsonify({
            "msg": "Periodo creado exitosamente",
            "periodo": {
                "periodo_id": nuevo_periodo.periodo_id,
                "nombre": nuevo_periodo.nombre,
                "anio": nuevo_periodo.anio,
                "semestre": nuevo_periodo.semestre,
                "activo": nuevo_periodo.activo
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al crear periodo", "error": str(e)}), 500

@periodos_bp.route('/listar', methods=['GET'])
@jwt_required()
def listar_periodos():
    try:
        periodos = Periodo.query.order_by(Periodo.anio.desc(), Periodo.semestre.desc()).all()
        
        result = []
        for periodo in periodos:
            result.append({
                "periodo_id": periodo.periodo_id,
                "nombre": periodo.nombre,
                "anio": periodo.anio,
                "semestre": periodo.semestre,
                "activo": periodo.activo,
                "total_evaluaciones": len(periodo.evaluaciones),
                "total_reportes": sum(len(e.reportes) for e in periodo.evaluaciones),
                "total_casos": sum(len(r.casos) for e in periodo.evaluaciones for r in e.reportes)
            })
        
        return jsonify({
            "total": len(result),
            "periodos": result
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error al listar periodos", "error": str(e)}), 500

@periodos_bp.route('/ObtenerPeriodoActivo', methods=['GET'])
@jwt_required()
def obtener_periodo_activo():
    try:
        periodo = Periodo.query.filter_by(activo=True).first()
        
        if not periodo:
            return jsonify({"msg": "No hay periodo activo", "periodo": None}), 200
        
        return jsonify({
            "periodo_id": periodo.periodo_id,
            "nombre": periodo.nombre,
            "anio": periodo.anio,
            "semestre": periodo.semestre,
            "activo": periodo.activo
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener periodo activo", "error": str(e)}), 500

@periodos_bp.route('/ToggleActivarPeriodo/<int:periodo_id>', methods=['PUT'])
@jwt_required()
def activar_periodo(periodo_id):
    try:
        periodo = Periodo.query.get(periodo_id)
        
        if not periodo:
            return jsonify({"msg": "Periodo no encontrado"}), 404

        nuevo_estado = not periodo.activo

        if nuevo_estado:
            Periodo.query.filter(
                Periodo.periodo_id != periodo_id,
                Periodo.activo == True
            ).update({Periodo.activo: False}, synchronize_session=False)

        periodo.activo = nuevo_estado
        db.session.commit()
        
        return jsonify({
            "msg": "Periodo activado exitosamente" if periodo.activo else "Periodo desactivado exitosamente",
            "periodo": {
                "periodo_id": periodo.periodo_id,
                "nombre": periodo.nombre,
                "activo": periodo.activo
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al actualizar estado del periodo", "error": str(e)}), 500

@periodos_bp.route('/ObtenerPeriodo/<int:periodo_id>', methods=['GET'])
@jwt_required()
def obtener_periodo(periodo_id):
    try:
        periodo = Periodo.query.get(periodo_id)
        
        if not periodo:
            return jsonify({"msg": "Periodo no encontrado"}), 404
        
        evaluaciones = []
        for evaluacion in periodo.evaluaciones:
            evaluaciones.append({
                "evaluacion_id": evaluacion.evaluacion_id,
                "nombre": evaluacion.nombre,
                "descripcion": evaluacion.descripcion,
                "fecha_entrega": evaluacion.fecha_entrega.isoformat() if evaluacion.fecha_entrega else None,
                "total_reportes": len(evaluacion.reportes),
                "total_casos": sum(len(r.casos) for r in evaluacion.reportes)
            })
        
        return jsonify({
            "periodo_id": periodo.periodo_id,
            "nombre": periodo.nombre,
            "anio": periodo.anio,
            "semestre": periodo.semestre,
            "activo": periodo.activo,
            "evaluaciones": evaluaciones
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener periodo", "error": str(e)}), 500

# Payload: {"nombre": "string" (opcional), "anio": int (opcional), "semestre": int (opcional)}
@periodos_bp.route('/ActualizarPeriodo/<int:periodo_id>', methods=['PUT'])
@jwt_required()
def actualizar_periodo(periodo_id):
    try:
        periodo = Periodo.query.get(periodo_id)
        
        if not periodo:
            return jsonify({"msg": "Periodo no encontrado"}), 404
        
        data = request.get_json()
        
        if 'nombre' in data:
            periodo.nombre = data['nombre']
        if 'anio' in data:
            periodo.anio = data['anio']
        if 'semestre' in data and data['semestre'] in [1, 2]:
            periodo.semestre = data['semestre']
        
        db.session.commit()
        
        return jsonify({"msg": "Periodo actualizado exitosamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al actualizar periodo", "error": str(e)}), 500

@periodos_bp.route('/EliminarPeriodo/<int:periodo_id>', methods=['DELETE'])
@jwt_required()
def eliminar_periodo(periodo_id):
    try:
        periodo = Periodo.query.get(periodo_id)
        
        if not periodo:
            return jsonify({"msg": "Periodo no encontrado"}), 404
        
        if len(periodo.evaluaciones) > 0:
            return jsonify({
                "msg": "No se puede eliminar un periodo con evaluaciones asociadas",
                "total_evaluaciones": len(periodo.evaluaciones)
            }), 400
        
        db.session.delete(periodo)
        db.session.commit()
        
        return jsonify({"msg": "Periodo eliminado exitosamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al eliminar periodo", "error": str(e)}), 500
