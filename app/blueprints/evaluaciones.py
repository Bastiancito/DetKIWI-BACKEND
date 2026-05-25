from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models import Evaluacion, Reporte, Periodo, Paralelo
from datetime import datetime

evaluaciones_bp = Blueprint('evaluaciones', __name__)

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

# Payload: {"nombre": "string", "descripcion": "string" (opcional), "fecha_entrega": "string" (opcional ISO format), "periodo_id": int}
@evaluaciones_bp.route('/CrearEvaluacion', methods=['POST'])
@jwt_required()
def crear_evaluacion():
    try:
        data = request.get_json()
        
        nombre = data.get('nombre')
        descripcion = data.get('descripcion')
        fecha_entrega = data.get('fecha_entrega')
        periodo_id = data.get('periodo_id')
        
        if not nombre:
            return jsonify({"msg": "El nombre es requerido"}), 400
        
        if not periodo_id:
            return jsonify({"msg": "El periodo_id es requerido"}), 400
        
        periodo = Periodo.query.get(periodo_id)
        if not periodo:
            return jsonify({"msg": "Periodo no encontrado"}), 404
        
        nueva_evaluacion = Evaluacion(
            nombre=nombre,
            descripcion=descripcion,
            periodo_id=periodo_id
        )
        
        if fecha_entrega:
            try:
                nueva_evaluacion.fecha_entrega = datetime.fromisoformat(fecha_entrega.replace('Z', '+00:00'))
            except:
                pass
        
        db.session.add(nueva_evaluacion)
        db.session.commit()
        
        return jsonify({
            "msg": "Evaluación creada exitosamente",
            "evaluacion": {
                "evaluacion_id": nueva_evaluacion.evaluacion_id,
                "nombre": nueva_evaluacion.nombre,
                "descripcion": nueva_evaluacion.descripcion,
                "fecha_creacion": nueva_evaluacion.fecha_creacion.isoformat(),
                "fecha_entrega": nueva_evaluacion.fecha_entrega.isoformat() if nueva_evaluacion.fecha_entrega else None,
                "periodo": {
                    "periodo_id": periodo.periodo_id,
                    "nombre": periodo.nombre
                }
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al crear evaluación", "error": str(e)}), 500

@evaluaciones_bp.route('/listar', methods=['GET'])
@jwt_required()
def listar_evaluaciones():
    try:
        periodo_id = request.args.get('periodo_id', type=int)
        solo_activo = request.args.get('solo_activo', 'false').lower() == 'true'
        
        query = Evaluacion.query
        
        if solo_activo:
            periodo_activo = Periodo.query.filter_by(activo=True).first()
            if periodo_activo:
                query = query.filter_by(periodo_id=periodo_activo.periodo_id)
        elif periodo_id:
            query = query.filter_by(periodo_id=periodo_id)
        
        evaluaciones = query.order_by(Evaluacion.fecha_creacion.desc()).all()
        
        result = []
        for evaluacion in evaluaciones:
            result.append({
                "evaluacion_id": evaluacion.evaluacion_id,
                "nombre": evaluacion.nombre,
                "descripcion": evaluacion.descripcion,
                "fecha_creacion": evaluacion.fecha_creacion.isoformat(),
                "fecha_entrega": evaluacion.fecha_entrega.isoformat() if evaluacion.fecha_entrega else None,
                "activo": evaluacion.activo,
                "periodo": {
                    "periodo_id": evaluacion.periodo.periodo_id,
                    "nombre": evaluacion.periodo.nombre,
                    "activo": evaluacion.periodo.activo
                },
                "total_reportes": len(evaluacion.reportes),
                "total_casos": sum(len(r.casos) for r in evaluacion.reportes)
            })
        
        return jsonify({
            "total": len(result),
            "evaluaciones": result
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error al listar evaluaciones", "error": str(e)}), 500

@evaluaciones_bp.route('/ObtenerEvaluacionPorEvaluacionId/<int:evaluacion_id>', methods=['GET'])
@jwt_required()
def obtener_evaluacion(evaluacion_id):
    try:
        evaluacion = Evaluacion.query.get(evaluacion_id)
        
        if not evaluacion:
            return jsonify({"msg": "Evaluación no encontrada"}), 404
        
        reportes = []
        for reporte in evaluacion.reportes:
            reportes.append({
                "reporte_id": reporte.reporte_id,
                "titulo": reporte.titulo,
                "fecha_creacion": reporte.fecha_creacion.isoformat(),
                "total_casos": len(reporte.casos),
                "casos_abiertos": len([c for c in reporte.casos if not c.closed])
            })
        
        return jsonify({
            "evaluacion_id": evaluacion.evaluacion_id,
            "nombre": evaluacion.nombre,
            "descripcion": evaluacion.descripcion,
            "fecha_creacion": evaluacion.fecha_creacion.isoformat(),
            "fecha_entrega": evaluacion.fecha_entrega.isoformat() if evaluacion.fecha_entrega else None,
            "total_reportes": len(reportes),
            "reportes": reportes
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener evaluación", "error": str(e)}), 500

# Payload: {"nombre": "string" (opcional), "descripcion": "string" (opcional), "fecha_entrega": "string" (opcional ISO format)}
@evaluaciones_bp.route('/ActualizarEvaluacionPorEvaluacionId/<int:evaluacion_id>', methods=['PUT'])
@jwt_required()
def actualizar_evaluacion(evaluacion_id):
    try:
        evaluacion = Evaluacion.query.get(evaluacion_id)
        
        if not evaluacion:
            return jsonify({"msg": "Evaluación no encontrada"}), 404
        
        data = request.get_json()
        
        if 'nombre' in data:
            evaluacion.nombre = data['nombre']
        if 'descripcion' in data:
            evaluacion.descripcion = data['descripcion']
        if 'fecha_entrega' in data:
            try:
                evaluacion.fecha_entrega = datetime.fromisoformat(data['fecha_entrega'].replace('Z', '+00:00'))
            except:
                pass
        
        db.session.commit()
        
        return jsonify({
            "msg": "Evaluación actualizada exitosamente",
            "evaluacion": {
                "evaluacion_id": evaluacion.evaluacion_id,
                "nombre": evaluacion.nombre,
                "descripcion": evaluacion.descripcion,
                "fecha_entrega": evaluacion.fecha_entrega.isoformat() if evaluacion.fecha_entrega else None
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al actualizar evaluación", "error": str(e)}), 500

@evaluaciones_bp.route('/EliminarEvaluacionPorEvaluacionId/<int:evaluacion_id>', methods=['DELETE'])
@jwt_required()
def eliminar_evaluacion(evaluacion_id):
    try:
        evaluacion = Evaluacion.query.get(evaluacion_id)
        
        if not evaluacion:
            return jsonify({"msg": "Evaluación no encontrada"}), 404
        
        if len(evaluacion.reportes) > 0:
            return jsonify({
                "msg": "No se puede eliminar una evaluación con reportes asociados",
                "total_reportes": len(evaluacion.reportes)
            }), 400
        
        db.session.delete(evaluacion)
        db.session.commit()
        
        return jsonify({"msg": "Evaluación eliminada exitosamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al eliminar evaluación", "error": str(e)}), 500

@evaluaciones_bp.route('/ObtenerEstadisticasPorEvaluacionId/<int:evaluacion_id>', methods=['GET'])
@jwt_required()
def estadisticas_evaluacion(evaluacion_id):
    try:
        evaluacion = Evaluacion.query.get(evaluacion_id)
        
        if not evaluacion:
            return jsonify({"msg": "Evaluación no encontrada"}), 404
        
        total_casos = 0
        casos_cerrados = 0
        casos_con_sancion = 0
        similitudes = []
        
        for reporte in evaluacion.reportes:
            for caso in reporte.casos:
                total_casos += 1
                if caso.closed:
                    casos_cerrados += 1
                if caso.sancion:
                    casos_con_sancion += 1
                similitudes.append(caso.similitud)
        
        return jsonify({
            "evaluacion_id": evaluacion.evaluacion_id,
            "nombre": evaluacion.nombre,
            "total_reportes": len(evaluacion.reportes),
            "total_casos": total_casos,
            "estadisticas_casos": {
                "cerrados": casos_cerrados,
                "abiertos": total_casos - casos_cerrados,
                "con_sancion": casos_con_sancion
            },
            "similitud_promedio": round(sum(similitudes) / len(similitudes), 2) if similitudes else 0,
            "similitud_maxima": max(similitudes) if similitudes else 0,
            "casos_criticos": len([s for s in similitudes if s >= 90])
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener estadísticas", "error": str(e)}), 500

@evaluaciones_bp.route('/ObtenerCasosPorEvaluacionId/<int:evaluacion_id>', methods=['GET'])
@jwt_required()
def obtener_casos_evaluacion(evaluacion_id):
    try:
        evaluacion = Evaluacion.query.get(evaluacion_id)
        
        if not evaluacion:
            return jsonify({"msg": "Evaluación no encontrada"}), 404
        
        min_similitud = request.args.get('min_similitud', type=float)
        max_similitud = request.args.get('max_similitud', type=float)
        closed = request.args.get('closed')  # 'true' o 'false'
        
        casos_result = []
        for reporte in evaluacion.reportes:
            for caso in reporte.casos:
                if closed is not None:
                    closed_bool = closed.lower() == 'true'
                    if caso.closed != closed_bool:
                        continue
                if min_similitud is not None and caso.similitud < min_similitud:
                    continue
                if max_similitud is not None and caso.similitud > max_similitud:
                    continue
                
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
                
                casos_result.append({
                    'caso_id': caso.caso_id,
                    'similitud': caso.similitud,
                    'lineas': caso.lineas,
                    'url_moss': caso.url_moss,
                    'closed': caso.closed,
                    'sancion': caso.sancion,
                    'caso_metadata': caso.caso_metadata,
                    'paralelos': _serializar_paralelos_caso(caso),
                    'estudiantes': estudiantes,
                    'usuarios_asignados': usuarios_asignados,
                    'reporte': {
                        'reporte_id': reporte.reporte_id,
                        'titulo': reporte.titulo,
                        'fecha_creacion': reporte.fecha_creacion.isoformat()
                    }
                })
        
        casos_result.sort(key=lambda x: x['similitud'], reverse=True)
        
        return jsonify({
            "evaluacion": {
                "evaluacion_id": evaluacion.evaluacion_id,
                "nombre": evaluacion.nombre,
                "descripcion": evaluacion.descripcion,
                "periodo": {
                    "periodo_id": evaluacion.periodo.periodo_id,
                    "nombre": evaluacion.periodo.nombre
                }
            },
            "total_casos": len(casos_result),
            "casos": casos_result
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener casos de la evaluación", "error": str(e)}), 500

@evaluaciones_bp.route('/ToggleActivoByEvaluacionId/<int:evaluacion_id>', methods=['GET'])
@jwt_required()
def toggle_activar_evaluacion(evaluacion_id):
    try:
        evaluacion = Evaluacion.query.get(evaluacion_id)
        
        if not evaluacion:
            return jsonify({"msg": "Evaluación no encontrada"}), 404
        
        evaluacion.activo = not evaluacion.activo
        db.session.commit()
        
        return jsonify({
            "msg": f"Evaluación {'activada' if evaluacion.activo else 'desactivada'} exitosamente",
            "evaluacion": {
                "evaluacion_id": evaluacion.evaluacion_id,
                "nombre": evaluacion.nombre,
                "activo": evaluacion.activo
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al cambiar estado de la evaluación", "error": str(e)}), 500
