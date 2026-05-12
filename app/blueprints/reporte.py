import pandas as pd
import os
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models import Reporte, Caso, Estudiante, Paralelo, Sede, User, Evaluacion
from utils.excel_processor import ExcelProcessor

reportes_bp = Blueprint('reportes', __name__)

ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

USE_HARDCODED_FILE = True
HARDCODED_FILE_PATH = "utils/Similitudes T1 2025-1.xlsx"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def obtener_paralelos_faltantes(casos_validos, cache_paralelos):
    """Retorna la lista de paralelos presentes en el Excel que no están registrados en el sistema."""
    paralelos_en_excel = set()

    for case_data in casos_validos:
        paralelo_1 = (case_data.get('estudiante1', {}).get('paralelo') or '').strip()
        paralelo_2 = (case_data.get('estudiante2', {}).get('paralelo') or '').strip()

        if paralelo_1:
            paralelos_en_excel.add(paralelo_1)
        if paralelo_2:
            paralelos_en_excel.add(paralelo_2)

    return sorted([sigla for sigla in paralelos_en_excel if sigla not in cache_paralelos])

# Payload (multipart/form-data): {"file": archivo excel/csv, "titulo": "string", "evaluacion_id": int}
@reportes_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_reporte():
    if 'file' not in request.files:
        return jsonify({"msg": "No se envió el archivo"}), 400
    
    file = request.files['file']
    nombre_reporte = request.form.get('titulo', 'Reporte MOSS')
    evaluacion_id = request.form.get('evaluacion_id')

    if not evaluacion_id:
        return jsonify({"msg": "Se requiere evaluacion_id"}), 400
    
    evaluacion = Evaluacion.query.get(int(evaluacion_id))
    if not evaluacion:
        return jsonify({"msg": "Evaluación no encontrada"}), 404

    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"msg": "Archivo inválido"}), 400

    try:
        current_user_id = int(get_jwt_identity())
        
        processor = ExcelProcessor()
        
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        success, processed_data, errors = processor.procesar_archivo_excel(df)
        
        if not success:
            return jsonify({
                "msg": "Error procesando el archivo",
                "errores": errors
            }), 400
        
        casos_validos = processed_data['casos_validos']
        casos_invalidos = processed_data['casos_invalidos']
        
        if len(casos_validos) == 0:
            return jsonify({
                "msg": "No se encontraron casos válidos para procesar",
                "casos_invalidos": casos_invalidos
            }), 400
        
        nuevo_reporte = Reporte(
            titulo=nombre_reporte, 
            user_id=current_user_id,
            evaluacion_id=evaluacion_id
        )
        db.session.add(nuevo_reporte)
        db.session.flush()

        cache_paralelos = {}
        
        paralelos_existentes = Paralelo.query.options(
            db.joinedload(Paralelo.usuarios)
        ).all()
        
        for p in paralelos_existentes:
            cache_paralelos[p.sigla_paralelo] = p

        paralelos_faltantes = obtener_paralelos_faltantes(casos_validos, cache_paralelos)
        if paralelos_faltantes:
            if len(paralelos_faltantes) == 1:
                return jsonify({
                    "msg": f"El paralelo {paralelos_faltantes[0]} no está registrado. Es necesario registrarlo y asignar un encargado para procesar el archivo.",
                    "paralelos_no_registrados": paralelos_faltantes
                }), 400

            return jsonify({
                "msg": "Hay paralelos no registrados. Es necesario registrarlos y asignar un encargado para procesar el archivo.",
                "paralelos_no_registrados": paralelos_faltantes
            }), 400

        casos_creados = 0
        paralelos_creados = set()
        
        for case_data in casos_validos:
            try:
                est1 = obtener_o_crear_estudiante(
                    cache_paralelos=cache_paralelos,
                    **case_data['estudiante1']
                )
                est2 = obtener_o_crear_estudiante(
                    cache_paralelos=cache_paralelos,
                    **case_data['estudiante2']
                )
                
                usuarios_ids = determinar_usuarios_asignados(est1, est2)
                
                nuevo_caso = Caso(
                    reporte_id=nuevo_reporte.reporte_id,
                    evaluacion_id=evaluacion_id,
                    similitud=case_data['similitud'],
                    lineas=case_data['lineas'],
                    url_moss=case_data['url_moss']
                )
                
                nuevo_caso.involucrados.append(est1)
                nuevo_caso.involucrados.append(est2)
                
                for user_id in usuarios_ids:
                    usuario = User.query.get(user_id)
                    if usuario:
                        nuevo_caso.usuarios_asignados.append(usuario)
                
                db.session.add(nuevo_caso)
                casos_creados += 1
                
                if est1.paralelo:
                    paralelos_creados.add(est1.paralelo.sigla_paralelo)
                if est2.paralelo:
                    paralelos_creados.add(est2.paralelo.sigla_paralelo)
                
                
            except Exception as e:
                print(f"Error creando caso: {str(e)}")
                continue

        db.session.commit()
        
        response_data = {
            "msg": "Carga exitosa",
            "reporte_id": nuevo_reporte.reporte_id,
            "casos_creados": casos_creados,
            "total_filas_procesadas": processed_data['total_filas_procesadas'],
            "paralelos_procesados": len(paralelos_creados),
            "paralelos_unicos": list(paralelos_creados) if len(paralelos_creados) <= 10 else list(paralelos_creados)[:10]
        }
        
        if casos_invalidos:
            response_data["advertencias"] = {
                "casos_invalidos": len(casos_invalidos),
                "detalles_casos_invalidos": casos_invalidos[:5]
            }

        return jsonify(response_data), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error general: {e}")
        return jsonify({"msg": "Error procesando el archivo", "error": str(e)}), 500
    
def obtener_o_crear_paralelo(sigla, cache_paralelos):
    if sigla in cache_paralelos:
        return cache_paralelos[sigla]
    
    paralelo = Paralelo.query.filter_by(sigla_paralelo=sigla).first()
    
    if not paralelo:
        paralelo = Paralelo(sigla_paralelo=sigla, sede_id=None)
        db.session.add(paralelo)
        db.session.flush()
    
    cache_paralelos[sigla] = paralelo
    return paralelo

def determinar_usuarios_asignados(estudiante1, estudiante2):
    usuarios_asignados = set()
    
    for estudiante in [estudiante1, estudiante2]:
        if estudiante.paralelo and estudiante.paralelo.usuarios:
            for usuario in estudiante.paralelo.usuarios:
                usuarios_asignados.add(usuario.user_id)
    
    return list(usuarios_asignados)

def obtener_o_crear_estudiante(rol, nombre, apellido, paralelo, cache_paralelos):
    est = Estudiante.query.filter_by(rol_usm=rol).first()
    
    paralelo_obj = None
    if paralelo:
        if paralelo in cache_paralelos:
            paralelo_obj = cache_paralelos[paralelo]
        else:
            paralelo_obj = Paralelo.query.filter_by(sigla_paralelo=paralelo).first()
            
            if not paralelo_obj:
                raise ValueError(
                    f"El paralelo {paralelo} no está registrado. Es necesario registrarlo y asignar un encargado para procesar el archivo."
                )
            
            cache_paralelos[paralelo] = paralelo_obj
    
    if not est:
        est = Estudiante(
            rol_usm=rol, 
            nombre=nombre, 
            apellido=apellido, 
            paralelo_id=paralelo_obj.paralelo_id if paralelo_obj else None
        )
        db.session.add(est)
    else:
        est.paralelo_id = paralelo_obj.paralelo_id if paralelo_obj else None
    
    return est

@reportes_bp.route('/reportes', methods=['GET'])
@jwt_required()
def obtener_reportes():
    try:
        current_user_id = int(get_jwt_identity())
        reportes = Reporte.query.filter_by(user_id=current_user_id).order_by(Reporte.fecha_creacion.desc()).all()
        
        result = []
        for reporte in reportes:
            result.append({
                'reporte_id': reporte.reporte_id,
                'titulo': reporte.titulo,
                'fecha_creacion': reporte.fecha_creacion.isoformat(),
                'total_casos': len(reporte.casos),
                'casos_abiertos': len([c for c in reporte.casos if not c.closed]),
                'evaluacion': {
                    'evaluacion_id': reporte.evaluacion.evaluacion_id,
                    'nombre': reporte.evaluacion.nombre
                } if reporte.evaluacion else None
            })
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener reportes", "error": str(e)}), 500

@reportes_bp.route('/casos-reporte/<int:reporte_id>', methods=['GET'])
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
                    'rol_usm': est.rol_usm,
                    'paralelo': est.paralelo.sigla_paralelo if est.paralelo else None
                }
                for est in caso.involucrados
            ]
            
            result.append({
                'caso_id': caso.caso_id,
                'similitud': caso.similitud,
                'lineas': caso.lineas,
                'url_moss': caso.url_moss,
                'closed': caso.closed,
                'sancion': caso.sancion,
                'caso_metadata': caso.caso_metadata,
                'estudiantes': estudiantes
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

@reportes_bp.route('/estadisticas-reporte/<int:reporte_id>', methods=['GET'])
@jwt_required()
def obtener_estadisticas_reporte(reporte_id):
    try:
        current_user_id = int(get_jwt_identity())
        reporte = Reporte.query.filter_by(reporte_id=reporte_id, user_id=current_user_id).first()
        
        if not reporte:
            return jsonify({"msg": "Reporte no encontrado"}), 404
        
        casos = reporte.casos
        total_casos = len(casos)
        
        casos_cerrados = len([c for c in casos if c.closed])
        casos_abiertos = total_casos - casos_cerrados
        casos_con_sancion = len([c for c in casos if c.sancion])
        casos_sin_sancion = len([c for c in casos if c.sancion == False])
        
        similitudes = [caso.similitud for caso in casos]
        similitud_promedio = sum(similitudes) / len(similitudes) if similitudes else 0
        similitud_maxima = max(similitudes) if similitudes else 0
        similitud_minima = min(similitudes) if similitudes else 0
        
        rangos_similitud = {
            '90-100%': len([s for s in similitudes if s >= 90]),
            '80-89%': len([s for s in similitudes if 80 <= s < 90]),
            '70-79%': len([s for s in similitudes if 70 <= s < 80]),
            '60-69%': len([s for s in similitudes if 60 <= s < 70]),
            '<60%': len([s for s in similitudes if s < 60])
        }
        
        return jsonify({
            'reporte_id': reporte.reporte_id,
            'titulo': reporte.titulo,
            'total_casos': total_casos,
            'estadisticas_casos': {
                'cerrados': casos_cerrados,
                'abiertos': casos_abiertos,
                'con_sancion': casos_con_sancion,
                'sin_sancion': casos_sin_sancion
            },
            'estadisticas_similitud': {
                'promedio': round(similitud_promedio, 2),
                'maxima': similitud_maxima,
                'minima': similitud_minima,
                'por_rango': rangos_similitud
            }
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener estadísticas", "error": str(e)}), 500

@reportes_bp.route('/detalle-reporte/<int:reporte_id>', methods=['GET'])
@jwt_required()
def obtener_reporte_detalle(reporte_id):
    try:
        current_user_id = int(get_jwt_identity())
        reporte = Reporte.query.filter_by(reporte_id=reporte_id, user_id=current_user_id).first()
        
        if not reporte:
            return jsonify({"msg": "Reporte no encontrado"}), 404
        
        return jsonify({
            'reporte_id': reporte.reporte_id,
            'titulo': reporte.titulo,
            'fecha_creacion': reporte.fecha_creacion.isoformat(),
            'total_casos': len(reporte.casos),
            'casos_alta_similitud': len([c for c in reporte.casos if c.similitud >= 80])
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener reporte", "error": str(e)}), 500

@reportes_bp.route('/eliminar-reporte/<int:reporte_id>', methods=['DELETE'])
@jwt_required()
def eliminar_reporte(reporte_id):
    try:
        current_user_id = int(get_jwt_identity())
        reporte = Reporte.query.filter_by(reporte_id=reporte_id, user_id=current_user_id).first()
        
        if not reporte:
            return jsonify({"msg": "Reporte no encontrado"}), 404
        
        db.session.delete(reporte)
        db.session.commit()
        
        return jsonify({"msg": "Reporte eliminado correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error al eliminar reporte", "error": str(e)}), 500

@reportes_bp.route('/casos-filtrados-reporte/<int:reporte_id>', methods=['GET'])
@jwt_required()
def obtener_casos_filtrados(reporte_id):
    try:
        current_user_id = int(get_jwt_identity())
        min_similitud = request.args.get('min_similitud', 0, type=float)
        
        reporte = Reporte.query.filter_by(reporte_id=reporte_id, user_id=current_user_id).first()
        
        if not reporte:
            return jsonify({"msg": "Reporte no encontrado"}), 404
        
        casos_filtrados = [caso for caso in reporte.casos if caso.similitud >= min_similitud]
        
        result = []
        for caso in casos_filtrados:
            estudiantes = [
                {
                    'estudiante_id': est.estudiante_id,
                    'nombre': est.nombre,
                    'apellido': est.apellido,
                    'rol_usm': est.rol_usm,
                    'paralelo': est.paralelo.sigla_paralelo if est.paralelo else None
                }
                for est in caso.involucrados
            ]
            
            result.append({
                'caso_id': caso.caso_id,
                'similitud': caso.similitud,
                'lineas': caso.lineas,
                'url_moss': caso.url_moss,
                'closed': caso.closed,
                'sancion': caso.sancion,
                'caso_metadata': caso.caso_metadata,
                'estudiantes': estudiantes
            })
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"msg": "Error al filtrar casos", "error": str(e)}), 500

@reportes_bp.route('/paralelos-reporte/<int:reporte_id>', methods=['GET'])
@jwt_required()
def obtener_paralelos_reporte(reporte_id):
    try:
        current_user_id = int(get_jwt_identity())
        reporte = Reporte.query.filter_by(reporte_id=reporte_id, user_id=current_user_id).first()
        
        if not reporte:
            return jsonify({"msg": "Reporte no encontrado"}), 404
        
        paralelos_stats = {}
        
        for caso in reporte.casos:
            for estudiante in caso.involucrados:
                paralelo = estudiante.paralelo.sigla_paralelo if estudiante.paralelo else None
                if paralelo:
                    if paralelo not in paralelos_stats:
                        paralelos_stats[paralelo] = {
                            'nombre': paralelo,
                            'total_casos': 0,
                            'estudiantes_involucrados': set(),
                            'similitud_promedio': []
                        }
                    
                    paralelos_stats[paralelo]['total_casos'] += 1
                    paralelos_stats[paralelo]['estudiantes_involucrados'].add(estudiante.rol_usm)
                    paralelos_stats[paralelo]['similitud_promedio'].append(caso.similitud)
        
        result = []
        for paralelo, stats in paralelos_stats.items():
            similitudes = stats['similitud_promedio']
            result.append({
                'paralelo': paralelo,
                'total_casos': stats['total_casos'],
                'estudiantes_involucrados': len(stats['estudiantes_involucrados']),
                'similitud_promedio': round(sum(similitudes) / len(similitudes), 2) if similitudes else 0,
                'similitud_maxima': max(similitudes) if similitudes else 0
            })
        
        result.sort(key=lambda x: x['total_casos'], reverse=True)
        
        return jsonify({
            'reporte_id': reporte.reporte_id,
            'total_paralelos': len(result),
            'paralelos': result
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error al obtener paralelos del reporte", "error": str(e)}), 500

@reportes_bp.route('/validate', methods=['POST'])  
@jwt_required()
def validate_excel():
    if 'file' not in request.files:
        return jsonify({"msg": "No se envió el archivo"}), 400
    
    file = request.files['file']
    
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"msg": "Archivo inválido"}), 400

    try:
        processor = ExcelProcessor()
        
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file, nrows=10)
        else:
            df = pd.read_excel(file, nrows=10)
        
        is_valid, missing_cols, available_cols = processor.validar_estructura_archivo(df)
        
        if not is_valid:
            return jsonify({
                "valido": False,
                "columnas_faltantes": missing_cols,
                "columnas_disponibles": available_cols,
                "sugerencias": [
                    "Verifica que tu archivo tenga las columnas duplicadas para ambos estudiantes",
                    "Las columnas del segundo estudiante deben tener el sufijo '.1'",
                    "Ejemplo: ROL, ROL.1, Nombres, Nombres.1, etc."
                ]
            }), 400
        
        df_normalized = processor.normalizar_nombres_columnas(df)
        df_clean = processor.limpiar_datos(df_normalized)
        sample_cases = processor.extraer_datos_casos(df_clean)
        
        valid_cases_sample = []
        invalid_cases_sample = []
        
        for case in sample_cases:
            is_case_valid, case_errors = processor.validar_datos_caso(case)
            if is_case_valid:
                valid_cases_sample.append(case)
            else:
                invalid_cases_sample.append({
                    'fila': case.get('fila_original', 'N/A'),
                    'errores': case_errors
                })
        
        return jsonify({
            "valido": True,
            "estructura_correcta": True,
            "columnas_detectadas": available_cols,
            "muestra_casos_validos": len(valid_cases_sample),
            "muestra_casos_invalidos": len(invalid_cases_sample), 
            "casos_invalidos_detalle": invalid_cases_sample,
            "msg": "Archivo válido y listo para procesar"
        }), 200
        
    except Exception as e:
        return jsonify({
            "valido": False,
            "error": str(e),
            "msg": "Error validando archivo"
        }), 500

@reportes_bp.route('/debug/preview', methods=['POST', 'GET'])
@jwt_required()
def preview_excel_json():
    if USE_HARDCODED_FILE:
        try:
            if not os.path.exists(HARDCODED_FILE_PATH):
                return jsonify({
                    "msg": f"Archivo hardcodeado no encontrado: {HARDCODED_FILE_PATH}",
                    "tip": "Coloca tu archivo Excel en la carpeta utils/ o cambia USE_HARDCODED_FILE=False"
                }), 404
            
            filename = os.path.basename(HARDCODED_FILE_PATH)
            
            df = pd.read_excel(HARDCODED_FILE_PATH)
            
        except Exception as e:
            return jsonify({
                "msg": "Error leyendo archivo hardcodeado",
                "archivo": HARDCODED_FILE_PATH,
                "error": str(e)
            }), 500
    
    else:
        if 'file' not in request.files:
            return jsonify({"msg": "No se envió el archivo"}), 400
        
        file = request.files['file']
        
        if file.filename == '' or not allowed_file(file.filename):
            return jsonify({"msg": "Archivo inválido"}), 400

        try:
            filename = file.filename
            
            if filename.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
                
        except Exception as e:
            return jsonify({
                "msg": "Error leyendo archivo subido",
                "error": str(e)
            }), 500

    try:
        processor = ExcelProcessor()
        
        success, processed_data, errors = processor.procesar_archivo_excel(df)
        
        df_normalized = processor.normalizar_nombres_columnas(df)
        df_clean = processor.limpiar_datos(df_normalized)
        
        response_data = {
            "modo_desarrollo": USE_HARDCODED_FILE,
            "archivo_procesado": filename,
            "ruta_archivo": HARDCODED_FILE_PATH if USE_HARDCODED_FILE else "Subido por POST",
            "procesamiento_exitoso": success,
            "errores_procesamiento": errors,
            
            "dataframe_original": {
                "total_filas": len(df),
                "total_columnas": len(df.columns),
                "columnas_detectadas": df.columns.tolist(),
                "primeras_3_filas": df.head(3).to_dict('records') if len(df) > 0 else []
            },
            
            "dataframe_procesado": {
                "total_filas": len(df_clean),
                "columnas_normalizadas": df_clean.columns.tolist(),
                "filas_vacias_eliminadas": len(df) - len(df_clean)
            },
            
            "datos_procesados": processed_data if success else {},
            
            "vista_detallada_primeros_casos": []
        }
        
        if success and processed_data.get('casos_validos'):
            for i, caso in enumerate(processed_data['casos_validos'][:5]):
                response_data["vista_detallada_primeros_casos"].append({
                    "caso_numero": i + 1,
                    "fila_original_excel": caso.get('fila_original', 'N/A'),
                    "estudiante_1": {
                        "rol": caso['estudiante1']['rol'],
                        "nombre_completo": f"{caso['estudiante1']['nombre']} {caso['estudiante1']['apellido']}",
                        "paralelo": caso['estudiante1']['paralelo']
                    },
                    "estudiante_2": {
                        "rol": caso['estudiante2']['rol'], 
                        "nombre_completo": f"{caso['estudiante2']['nombre']} {caso['estudiante2']['apellido']}",
                        "paralelo": caso['estudiante2']['paralelo']
                    },
                    "similitud_porcentaje": caso['similitud'],
                    "lineas_similares": caso['lineas'],
                    "url_moss": caso['url_moss'],
                    "datos_raw_fila": df_clean.iloc[caso.get('fila_original', 1) - 1].to_dict() if caso.get('fila_original') and caso.get('fila_original') <= len(df_clean) else {}
                })
        
        if success and processed_data.get('casos_invalidos'):
            response_data["casos_invalidos_detalle"] = processed_data['casos_invalidos']
        
        return jsonify(response_data), 200
        
    except Exception as e:
        return jsonify({
            "modo_desarrollo": USE_HARDCODED_FILE,
            "archivo_procesado": filename,
            "procesamiento_exitoso": False,
            "error_detallado": str(e),
            "tipo_error": type(e).__name__,
            "msg": "Error procesando archivo para preview"
        }), 500
