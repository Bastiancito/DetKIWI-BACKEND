from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models import Rol, User, Sede, Paralelo, Reporte, Caso, Estudiante, Periodo, Evaluacion

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/limpiar-tabla/<string:tabla>', methods=['DELETE'])
@jwt_required()
def limpiar_tabla(tabla):
    try:
        tablas_disponibles = {
            'caso': Caso,
            'estudiante': Estudiante,
            'reporte': Reporte,
            'evaluacion': Evaluacion,
            'periodo': Periodo,
            'paralelo': Paralelo,
            'sede': Sede,
            'user': User,
            'rol': Rol
        }
        
        if tabla not in tablas_disponibles:
            return jsonify({
                "error": f"Tabla '{tabla}' no encontrada",
                "tablas_disponibles": list(tablas_disponibles.keys())
            }), 404
        
        modelo = tablas_disponibles[tabla]
        registros_eliminados = modelo.query.delete()
        db.session.commit()
        
        return jsonify({
            "message": f"Tabla '{tabla}' limpiada exitosamente",
            "registros_eliminados": registros_eliminados
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": "Error al limpiar tabla",
            "detalle": str(e)
        }), 500

@admin_bp.route('/limpiar-todo', methods=['DELETE'])
@jwt_required()
def limpiar_todo():
    try:
        resultado = {}
        
        casos = Caso.query.delete()
        resultado['casos'] = casos
        
        reportes = Reporte.query.delete()
        resultado['reportes'] = reportes
        
        evaluaciones = Evaluacion.query.delete()
        resultado['evaluaciones'] = evaluaciones
        
        periodos = Periodo.query.delete()
        resultado['periodos'] = periodos
        
        estudiantes = Estudiante.query.delete()
        resultado['estudiantes'] = estudiantes
        
        db.session.execute(db.text('DELETE FROM user_paralelos'))
        resultado['user_paralelos'] = 'limpiado'
        
        db.session.execute(db.text('DELETE FROM caso_usuarios'))
        resultado['caso_usuarios'] = 'limpiado'
        
        users = User.query.delete()
        resultado['users'] = users
        
        paralelos = Paralelo.query.delete()
        resultado['paralelos'] = paralelos
        
        sedes = Sede.query.delete()
        resultado['sedes'] = sedes
        
        roles = Rol.query.delete()
        resultado['roles'] = roles
        
        db.session.commit()
        
        return jsonify({
            "message": "✅ Base de datos limpiada exitosamente",
            "registros_eliminados": resultado
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": "Error al limpiar base de datos",
            "detalle": str(e)
        }), 500

@admin_bp.route('/limpiar-casos-reportes', methods=['DELETE'])
@jwt_required()
def limpiar_casos_reportes():
    try:
        resultado = {}
        
        casos = Caso.query.delete()
        resultado['casos'] = casos
        
        reportes = Reporte.query.delete()
        resultado['reportes'] = reportes
        
        db.session.commit()
        
        return jsonify({
            "message": "✅ Casos y reportes eliminados exitosamente",
            "registros_eliminados": resultado
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": "Error al limpiar casos y reportes",
            "detalle": str(e)
        }), 500

@admin_bp.route('/reset-secuencias', methods=['POST'])
@jwt_required()
def reset_secuencias():
    try:
        tablas = ['caso', 'estudiante', 'reporte', 'paralelo', 'sede', 'user', 'rol']
        
        for tabla in tablas:
            try:
                db.session.execute(db.text(f"ALTER SEQUENCE {tabla}_{tabla}_id_seq RESTART WITH 1"))
            except Exception:
                pass
        
        db.session.commit()
        
        return jsonify({
            "message": "✅ Secuencias reseteadas exitosamente",
            "nota": "Funcionalidad específica de PostgreSQL"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": "Error al resetear secuencias",
            "detalle": str(e)
        }), 500

@admin_bp.route('/estadisticas', methods=['GET'])
@jwt_required()
def estadisticas_db():
    try:
        estadisticas = {
            'casos': Caso.query.count(),
            'reportes': Reporte.query.count(),
            'evaluaciones': Evaluacion.query.count(),
            'periodos': Periodo.query.count(),
            'estudiantes': Estudiante.query.count(),
            'users': User.query.count(),
            'paralelos': Paralelo.query.count(),
            'sedes': Sede.query.count(),
            'roles': Rol.query.count()
        }
        
        result = db.session.execute(db.text('SELECT COUNT(*) FROM user_paralelos')).scalar()
        estadisticas['user_paralelos'] = result
        
        result_casos_est = db.session.execute(db.text('SELECT COUNT(*) FROM caso_estudiantes')).scalar()
        estadisticas['caso_estudiantes'] = result_casos_est
        
        result_casos_usr = db.session.execute(db.text('SELECT COUNT(*) FROM caso_usuarios')).scalar()
        estadisticas['caso_usuarios'] = result_casos_usr
        
        return jsonify({
            "estadisticas": estadisticas,
            "total_registros": sum(estadisticas.values())
        }), 200
        
    except Exception as e:
        return jsonify({
            "error": "Error al obtener estadísticas",
            "detalle": str(e)
        }), 500

@admin_bp.route('/info', methods=['GET'])
def info_admin():
    return jsonify({
        "mensaje": "⚠️ Blueprint Admin - Solo para desarrollo",
        "endpoints": {
            "DELETE /admin/limpiar-tabla/<tabla>": "Elimina todos los registros de una tabla específica",
            "DELETE /admin/limpiar-todo": "Elimina todos los registros de todas las tablas",
            "DELETE /admin/limpiar-casos-reportes": "Elimina solo casos y reportes",
            "POST /admin/reset-secuencias": "Resetea las secuencias de auto-incremento (PostgreSQL)",
            "GET /admin/estadisticas": "Muestra cantidad de registros por tabla",
            "GET /admin/info": "Esta ayuda"
        },
        "tablas_disponibles": ["caso", "estudiante", "reporte", "evaluacion", "periodo", "paralelo", "sede", "user", "rol"],
        "advertencia": "Todos los endpoints (excepto /info) requieren JWT token"
    }), 200
