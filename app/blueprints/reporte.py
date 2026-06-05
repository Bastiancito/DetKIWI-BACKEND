import pandas as pd
import os
import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models import Reporte, Caso, Estudiante, Paralelo, Sede, User, Evaluacion
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from utils.excel_processor import ExcelProcessor
from typing import List, Dict

reportes_bp = Blueprint('reportes', __name__)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

USE_HARDCODED_FILE = True
HARDCODED_FILE_PATH = "utils/moss.xlsx"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _parse_bool_form_value(value) -> bool:
    return str(value).strip().lower() in {'1', 'true', 'yes', 'si', 'on'}

def _normalizar_texto_caso(value) -> str:
    return str(value or '').strip().lower()

def _construir_clave_caso(case_data) -> tuple:
    est1 = case_data.get('estudiante1', {})
    est2 = case_data.get('estudiante2', {})

    estudiante_a = (
        _normalizar_texto_caso(est1.get('nombre')),
        _normalizar_texto_caso(est1.get('paralelo'))
    )
    estudiante_b = (
        _normalizar_texto_caso(est2.get('nombre')),
        _normalizar_texto_caso(est2.get('paralelo'))
    )

    par_ordenado = tuple(sorted([estudiante_a, estudiante_b]))

    try:
        similitud = float(case_data.get('similitud', 0) or 0)
    except Exception:
        similitud = 0.0

    try:
        lineas = int(case_data.get('lineas', 0) or 0)
    except Exception:
        lineas = 0

    url_moss = _normalizar_texto_caso(case_data.get('url_moss'))

    return (par_ordenado, similitud, lineas, url_moss)


def _agregar_a_coleccion(relacion, item):
    if hasattr(relacion, 'add'):
        relacion.add(item)
    else:
        relacion.append(item)

def _deduplicar_casos(casos_validos):
    vistos = set()
    unicos = []
    duplicados = []

    for case_data in casos_validos:
        clave = _construir_clave_caso(case_data)
        if clave in vistos:
            duplicados.append({
                'fila_original': case_data.get('fila_original'),
                'similitud': case_data.get('similitud'),
                'lineas': case_data.get('lineas'),
                'url_moss': case_data.get('url_moss'),
                'estudiante1': case_data.get('estudiante1', {}),
                'estudiante2': case_data.get('estudiante2', {})
            })
            continue

        vistos.add(clave)
        unicos.append(case_data)

    return unicos, duplicados

def _serializar_encargados_paralelo(paralelo) -> List[Dict]:
    if not paralelo or not paralelo.usuarios:
        return []

    return [
        {
            'user_id': usuario.user_id,
            'username': usuario.username,
            'email': usuario.email
        }
        for usuario in paralelo.usuarios
    ]

def _resumir_paralelo(paralelo) -> Dict:
    encargados = _serializar_encargados_paralelo(paralelo)
    return {
        'paralelo_id': paralelo.paralelo_id,
        'sigla_paralelo': paralelo.sigla_paralelo,
        'sede_id': paralelo.sede_id,
        'sede_nombre': paralelo.sede.nombre if paralelo.sede else None,
        'tiene_encargado': len(encargados) > 0,
        'usuarios_asignados': encargados,
        'user_ids': [usuario['user_id'] for usuario in encargados],
        'estado': 'con_encargado' if encargados else 'sin_encargado'
    }

def _resumir_estudiante(estudiante, estado: str) -> Dict:
    return {
        'estudiante_id': estudiante.estudiante_id,
        'nombre': estudiante.nombre,
        'apellido': estudiante.apellido,
        'paralelo': estudiante.paralelo.sigla_paralelo if estudiante.paralelo else None,
        'sede': estudiante.paralelo.sede.nombre if estudiante.paralelo and estudiante.paralelo.sede else None,
        'estado': estado,
        'tiene_encargado_paralelo': bool(estudiante.paralelo and estudiante.paralelo.usuarios)
    }

def _detectar_casos_sin_encargado(casos_validos, cache_paralelos, paralelos_que_se_crearan=None):
    casos_sin_encargado = []
    paralelos_sin_encargado = {}
    casos_vinculados_a_paralelo_creado = []
    paralelos_que_se_crearan = {str(sigla).upper() for sigla in (paralelos_que_se_crearan or set())}

    for case_data in casos_validos:
        paralelos_del_caso = []
        paralelos_vinculados_a_creados = []

        for clave_estudiante in ('estudiante1', 'estudiante2'):
            estudiante_data = case_data.get(clave_estudiante, {})
            paralelo_sigla = (estudiante_data.get('paralelo') or '').strip()

            if not paralelo_sigla:
                continue

            paralelo_key = paralelo_sigla.upper()

            if paralelo_key in paralelos_que_se_crearan:
                if paralelo_sigla not in paralelos_vinculados_a_creados:
                    paralelos_vinculados_a_creados.append(paralelo_sigla)
                continue

            paralelo = cache_paralelos.get(paralelo_key)
            encargados = _serializar_encargados_paralelo(paralelo)

            if not paralelo or not encargados:
                paralelo_info = {
                    'sigla_paralelo': paralelo_sigla,
                    'registrado': bool(paralelo),
                    'tiene_encargado': bool(encargados),
                    'sede_id': paralelo.sede_id if paralelo else None,
                    'sede_nombre': paralelo.sede.nombre if paralelo and paralelo.sede else None,
                    'usuarios_asignados': encargados,
                    'user_ids': [usuario['user_id'] for usuario in encargados]
                }
                paralelos_del_caso.append(paralelo_info)
                paralelos_sin_encargado[paralelo_sigla] = paralelo_info

        if paralelos_vinculados_a_creados or paralelos_del_caso:
            caso_resumen = {
                'fila_original': case_data.get('fila_original'),
                'similitud': case_data.get('similitud'),
                'lineas': case_data.get('lineas'),
                'url_moss': case_data.get('url_moss'),
                'estudiante1': case_data.get('estudiante1', {}),
                'estudiante2': case_data.get('estudiante2', {}),
                'paralelos_vinculados_a_creados': paralelos_vinculados_a_creados,
                'paralelos_sin_encargado': paralelos_del_caso
            }

            casos_sin_encargado.append(caso_resumen)

            if paralelos_vinculados_a_creados:
                casos_vinculados_a_paralelo_creado.append(caso_resumen)

    return casos_sin_encargado, list(paralelos_sin_encargado.values()), casos_vinculados_a_paralelo_creado

def obtener_paralelos_faltantes(casos_validos, cache_paralelos):
    paralelos_en_excel = set()

    for case_data in casos_validos:
        paralelo_1 = (case_data.get('estudiante1', {}).get('paralelo') or '').strip()
        paralelo_2 = (case_data.get('estudiante2', {}).get('paralelo') or '').strip()

        if paralelo_1:
            paralelos_en_excel.add(paralelo_1.strip().upper())
        if paralelo_2:
            paralelos_en_excel.add(paralelo_2.strip().upper())

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
    confirmar_sin_encargado = _parse_bool_form_value(request.form.get('confirmar_sin_encargado', 'false'))
    confirmar_duplicados = _parse_bool_form_value(request.form.get('confirmar_duplicados', 'false'))

    if not evaluacion_id:
        return jsonify({"msg": "Se requiere evaluacion_id"}), 400
    
    evaluacion = Evaluacion.query.get(int(evaluacion_id))
    if not evaluacion:
        return jsonify({"msg": "Evaluación no encontrada"}), 404

    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"msg": "Archivo inválido"}), 400

    try:
        current_user_id = int(get_jwt_identity())
        logger.info(
            "MOSS upload started: user_id=%s evaluacion_id=%s filename=%s confirmar_sin_encargado=%s confirmar_duplicados=%s",
            current_user_id,
            evaluacion_id,
            file.filename,
            confirmar_sin_encargado,
            confirmar_duplicados,
        )
        
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

        logger.info(
            "MOSS upload parsed: total_filas_procesadas=%s casos_validos=%s casos_invalidos=%s url_padre_moss=%s",
            processed_data.get('total_filas_procesadas'),
            len(casos_validos),
            len(casos_invalidos),
            processed_data.get('url_padre_moss'),
        )

        casos_validos, casos_duplicados = _deduplicar_casos(casos_validos)

        logger.info(
            "MOSS upload deduplicated: casos_validos_final=%s casos_duplicados=%s",
            len(casos_validos),
            len(casos_duplicados),
        )

        if casos_duplicados and not confirmar_duplicados:
            return jsonify({
                "msg": "Se detectaron casos duplicados en el archivo MOSS. Confirma para continuar omitiendo duplicados.",
                "codigo": "MOSS_DUPLICATE_CASES_DETECTED",
                "requiere_confirmacion": True,
                "status_code": 409,
                "casos_duplicados_count": len(casos_duplicados),
                "casos_duplicados": casos_duplicados[:10]
            }), 409
        
        if len(casos_validos) == 0:
            return jsonify({
                "msg": "No se encontraron casos válidos para procesar",
                "casos_invalidos": casos_invalidos
            }), 400
        
        cache_paralelos = {}
        
        paralelos_existentes = Paralelo.query.options(
            db.joinedload(Paralelo.usuarios)
        ).all()
        
        for p in paralelos_existentes:
            cache_paralelos[p.sigla_paralelo] = p

        paralelos_iniciales = set(cache_paralelos.keys())

        cache_paralelos_normalizado = {str(sigla).upper(): paralelo for sigla, paralelo in cache_paralelos.items()}
        paralelos_que_se_crearan = set(obtener_paralelos_faltantes(casos_validos, cache_paralelos_normalizado))

        casos_sin_encargado, paralelos_sin_encargado, casos_vinculados_a_paralelo_creado = _detectar_casos_sin_encargado(
            casos_validos,
            cache_paralelos,
            paralelos_que_se_crearan=paralelos_que_se_crearan
        )

        logger.info(
            "MOSS upload parallel check: paralelos_existentes=%s paralelos_a_crear=%s casos_sin_encargado=%s casos_vinculados_a_paralelo_creado=%s",
            len(paralelos_iniciales),
            sorted(list(paralelos_que_se_crearan))[:20],
            len(casos_sin_encargado),
            len(casos_vinculados_a_paralelo_creado),
        )

        if casos_sin_encargado and not confirmar_sin_encargado:
            # Se avisa al frontend, pero el caso debe crearse igualmente.
            pass

        nuevo_reporte = Reporte(
            titulo=nombre_reporte,
            user_id=current_user_id,
            evaluacion_id=evaluacion_id,
            url_moss=processed_data.get('url_padre_moss')
        )
        db.session.add(nuevo_reporte)
        db.session.flush()

        cache_estudiantes = {}

        casos_creados = 0
        casos_creados_detalle = []
        casos_fallidos_creacion = []
        paralelos_creados = set()
        estudiantes_creados = []
        estudiantes_creados_keys = set()
        paralelos_creados_detalle = []
        paralelos_creados_keys = set()
        
        for case_data in casos_validos:
            try:
                est1, est1_creado = obtener_o_crear_estudiante(
                    cache_paralelos=cache_paralelos,
                    cache_estudiantes=cache_estudiantes,
                    **case_data['estudiante1']
                )
                est2, est2_creado = obtener_o_crear_estudiante(
                    cache_paralelos=cache_paralelos,
                    cache_estudiantes=cache_estudiantes,
                    **case_data['estudiante2']
                )

                for estudiante, fue_creado in ((est1, est1_creado), (est2, est2_creado)):
                    if fue_creado:
                        estudiante_key = estudiante.estudiante_id
                        if estudiante_key not in estudiantes_creados_keys:
                            estudiantes_creados.append(_resumir_estudiante(estudiante, 'creado'))
                            estudiantes_creados_keys.add(estudiante_key)

                    if estudiante.paralelo:
                        paralelo = estudiante.paralelo
                        if paralelo.sigla_paralelo not in paralelos_iniciales and paralelo.sigla_paralelo not in paralelos_creados_keys:
                            paralelos_creados.add(paralelo.sigla_paralelo)
                            paralelos_creados_detalle.append(_resumir_paralelo(paralelo))
                            paralelos_creados_keys.add(paralelo.sigla_paralelo)
                
                usuarios_ids = determinar_usuarios_asignados(est1, est2)
                
                nuevo_caso = Caso(
                    reporte_id=nuevo_reporte.reporte_id,
                    evaluacion_id=evaluacion_id,
                    similitud=case_data['similitud'],
                    lineas=case_data['lineas'],
                    url_moss=case_data['url_moss']
                )
                
                _agregar_a_coleccion(nuevo_caso.involucrados, est1)
                if est2 is not est1:
                    _agregar_a_coleccion(nuevo_caso.involucrados, est2)

                for paralelo in (est1.paralelo, est2.paralelo):
                    if paralelo and paralelo not in nuevo_caso.paralelos:
                        _agregar_a_coleccion(nuevo_caso.paralelos, paralelo)
                
                for user_id in usuarios_ids:
                    usuario = User.query.get(user_id)
                    if usuario:
                        _agregar_a_coleccion(nuevo_caso.usuarios_asignados, usuario)
                
                db.session.add(nuevo_caso)
                db.session.flush()
                casos_creados += 1

                casos_creados_detalle.append({
                    'fila_original': case_data.get('fila_original'),
                    'caso_temp': f"{case_data.get('estudiante1', {}).get('nombre', '')} - {case_data.get('estudiante2', {}).get('nombre', '')}",
                    'similitud': case_data.get('similitud'),
                    'lineas': case_data.get('lineas'),
                    'url_moss': case_data.get('url_moss'),
                    'estudiantes': [
                        {
                            'nombre': est1.nombre,
                            'apellido': est1.apellido,
                            'paralelo': est1.paralelo.sigla_paralelo if est1.paralelo else None
                        },
                        {
                            'nombre': est2.nombre,
                            'apellido': est2.apellido,
                            'paralelo': est2.paralelo.sigla_paralelo if est2.paralelo else None
                        }
                    ],
                    'paralelos': [
                        {
                            'paralelo_id': paralelo.paralelo_id,
                            'sigla_paralelo': paralelo.sigla_paralelo,
                            'sede_id': paralelo.sede_id,
                            'sede_nombre': paralelo.sede.nombre if paralelo.sede else None
                        }
                        for paralelo in nuevo_caso.paralelos
                    ],
                    'usuarios_asignados': [
                        {
                            'user_id': usuario.user_id,
                            'username': usuario.username,
                            'email': usuario.email
                        }
                        for usuario in nuevo_caso.usuarios_asignados
                    ],
                    'tiene_encargados': len(nuevo_caso.usuarios_asignados) > 0
                })

                logger.info(
                    "MOSS case created: caso_id=%s reporte_id=%s fila_original=%s similitud=%s lineas=%s estudiantes=[%s|%s] paralelos=%s usuarios_asignados=%s",
                    nuevo_caso.caso_id,
                    nuevo_reporte.reporte_id,
                    case_data.get('fila_original'),
                    case_data.get('similitud'),
                    case_data.get('lineas'),
                    est1.nombre,
                    est2.nombre,
                    [paralelo.sigla_paralelo for paralelo in nuevo_caso.paralelos],
                    [usuario.user_id for usuario in nuevo_caso.usuarios_asignados],
                )

                if not nuevo_caso.paralelos:
                    logger.warning(
                        "MOSS case without paralelos after flush: caso_id=%s fila_original=%s estudiantes=[%s|%s]",
                        nuevo_caso.caso_id,
                        case_data.get('fila_original'),
                        est1.nombre,
                        est2.nombre,
                    )
                
                if est1.paralelo:
                    paralelos_creados.add(est1.paralelo.sigla_paralelo)
                if est2.paralelo:
                    paralelos_creados.add(est2.paralelo.sigla_paralelo)
                
                
            except Exception as e:
                logger.exception(
                    "MOSS case creation failed: fila_original=%s estudiante1=%s estudiante2=%s",
                    case_data.get('fila_original'),
                    case_data.get('estudiante1', {}).get('nombre'),
                    case_data.get('estudiante2', {}).get('nombre'),
                )
                casos_fallidos_creacion.append({
                    'fila_original': case_data.get('fila_original'),
                    'estudiante1': case_data.get('estudiante1', {}),
                    'estudiante2': case_data.get('estudiante2', {}),
                    'similitud': case_data.get('similitud'),
                    'lineas': case_data.get('lineas'),
                    'url_moss': case_data.get('url_moss'),
                    'error': str(e)
                })
                continue

        evaluacion.fecha_entrega = datetime.now(ZoneInfo("America/Santiago")) + timedelta(days=14)

        db.session.commit()

        logger.info(
            "MOSS upload committed: reporte_id=%s casos_creados=%s paralelos_creados=%s estudiantes_creados=%s",
            nuevo_reporte.reporte_id,
            casos_creados,
            len(paralelos_creados),
            len(estudiantes_creados),
        )

        paralelos_creados_sin_sede = sorted([
            sigla for sigla in cache_paralelos.keys() if sigla not in paralelos_iniciales
        ])
        
        response_data = {
            "msg": "Carga exitosa",
            "reporte_id": nuevo_reporte.reporte_id,
            "casos_creados": casos_creados,
            "casos_creados_detalle": casos_creados_detalle[:50],
            "casos_duplicados_omitidos_count": len(casos_duplicados),
            "url_global_moss": processed_data.get('url_padre_moss') or (casos_validos[0]['url_moss'] if casos_validos else None),
            "total_filas_procesadas": processed_data['total_filas_procesadas'],
            "paralelos_procesados": len(paralelos_creados),
            "paralelos_unicos": list(paralelos_creados) if len(paralelos_creados) <= 10 else list(paralelos_creados)[:10],
            "paralelos_creados_sin_sede": paralelos_creados_sin_sede,
            "casos_sin_encargado_count": len(casos_sin_encargado),
            "paralelos_sin_encargado_count": len(paralelos_sin_encargado),
            "casos_sin_encargado": casos_sin_encargado[:10],
            "paralelos_sin_encargado": paralelos_sin_encargado[:10],
            "casos_fallidos_creacion_count": len(casos_fallidos_creacion),
            "casos_fallidos_creacion": casos_fallidos_creacion[:10],
            "casos_vinculados_a_paralelo_creado_count": len(casos_vinculados_a_paralelo_creado),
            "casos_vinculados_a_paralelo_creado": casos_vinculados_a_paralelo_creado[:10],
            "alumnos_creados_count": len(estudiantes_creados),
            "alumnos_creados": estudiantes_creados[:20],
            "estudiantes_creados_count": len(estudiantes_creados),
            "estudiantes_creados": estudiantes_creados[:20],
            "paralelos_creados_count": len(paralelos_creados_detalle),
            "paralelos_creados": paralelos_creados_detalle[:20]
        }
        
        if casos_invalidos:
            response_data["advertencias"] = {
                "casos_invalidos": len(casos_invalidos),
                "detalles_casos_invalidos": casos_invalidos[:5]
            }

        if casos_sin_encargado:
            response_data["advertencias_sin_encargado"] = {
                "codigo": "MOSS_CASES_WITHOUT_ASSIGNED_USERS",
                "msg": "Se crearon casos aunque algunos paralelos no tienen usuario asignado.",
                "casos_sin_encargado_count": len(casos_sin_encargado),
                "paralelos_sin_encargado_count": len(paralelos_sin_encargado),
                "casos_sin_encargado": casos_sin_encargado[:10],
                "paralelos_sin_encargado": paralelos_sin_encargado[:10]
            }

        if casos_duplicados:
            response_data["advertencias_duplicados"] = {
                "codigo": "MOSS_DUPLICATE_CASES_SKIPPED",
                "msg": "Se detectaron y omitieron casos duplicados durante la carga.",
                "casos_duplicados_count": len(casos_duplicados),
                "detalles_casos_duplicados": casos_duplicados[:10]
            }

        return jsonify(response_data), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error general: {e}")
        return jsonify({"msg": "Error procesando el archivo", "error": str(e)}), 500

@reportes_bp.route('/debug_upload_moss', methods=['GET', 'POST'])
def debug_upload_moss():
    """Endpoint para probar cómo se procesaría el archivo de MOSS sin guardar en BD."""
    try:
        from utils.excel_processor import ExcelProcessor
        import pandas as pd
        processor = ExcelProcessor()

        if request.method == 'POST' and 'file' in request.files:
            file = request.files['file']

            if file.filename == '' or not allowed_file(file.filename):
                return jsonify({"msg": "Archivo inválido"}), 400

            filename = file.filename
            if filename.endswith('.csv'):
                df = pd.read_csv(file, header=None)
            else:
                df = pd.read_excel(file, header=None)

            ruta_archivo = "Subido por POST"
        else:
            file_path = "utils/moss.xlsx"
            if not os.path.exists(file_path):
                return jsonify({"msg": f"No se encontró el archivo en {file_path}"}), 404

            filename = os.path.basename(file_path)
            ruta_archivo = file_path
            df = pd.read_excel(file_path, header=None)

        success, processed_data, errors = processor.procesar_archivo_excel(df)
        
        if not success:
            return jsonify({
                "msg": "Error procesando el archivo",
                "errores": errors
            }), 400

        resumen_casos = []
        for caso in processed_data.get('casos_validos', [])[:10]:
            resumen_casos.append({
                "fila_original_excel": caso.get('fila_original', 'N/A'),
                "similitud": caso.get('similitud'),
                "lineas": caso.get('lineas'),
                "url_moss": caso.get('url_moss'),
                "estudiante1": {
                    "nombre": caso.get('estudiante1', {}).get('nombre'),
                    "paralelo": caso.get('estudiante1', {}).get('paralelo')
                },
                "estudiante2": {
                    "nombre": caso.get('estudiante2', {}).get('nombre'),
                    "paralelo": caso.get('estudiante2', {}).get('paralelo')
                }
            })

        return jsonify({
            "archivo_procesado": filename,
            "ruta_archivo": ruta_archivo,
            "procesamiento_exitoso": success,
            "errores_procesamiento": errors,
            "url_padre_moss": processed_data.get('url_padre_moss'),
            "matches_encontrados": processed_data.get('matches_encontrados'),
            "primer_paralelo_por_estudiante": processed_data.get('primer_paralelo_por_estudiante'),
            "resumen_casos": resumen_casos,
            "datos_procesados": processed_data
        }), 200
    except Exception as e:
        return jsonify({"msg": "Error procesando el archivo", "error": str(e)}), 500

def obtener_o_crear_paralelo(sigla, cache_paralelos):
    key = sigla.strip().upper() if sigla else sigla
    if key in cache_paralelos:
        return cache_paralelos[key]

    paralelo = Paralelo.query.filter_by(sigla_paralelo=key).first()

    if not paralelo:
        paralelo = Paralelo(sigla_paralelo=key, sede_id=None)
        db.session.add(paralelo)
        db.session.flush()

    cache_paralelos[key] = paralelo
    return paralelo

def determinar_usuarios_asignados(estudiante1, estudiante2):
    usuarios_asignados = set()
    
    for estudiante in [estudiante1, estudiante2]:
        if estudiante is None:
            continue

        if estudiante.paralelo and estudiante.paralelo.usuarios:
            for usuario in estudiante.paralelo.usuarios:
                usuarios_asignados.add(usuario.user_id)
        elif getattr(estudiante, 'paralelo_id', None):
            # Fallback: consultar explícitamente por usuarios del paralelo
            usuarios = User.query.join(User.paralelos).filter(Paralelo.paralelo_id == estudiante.paralelo_id).all()
            for usuario in usuarios:
                usuarios_asignados.add(usuario.user_id)
    
    return list(usuarios_asignados)

def obtener_o_crear_estudiante(rol, nombre, apellido, paralelo, cache_paralelos, cache_estudiantes=None):
    cache_key = None
    if nombre:
        nombre_clave = str(nombre).strip().lower()
        apellido_clave = str(apellido).strip().lower() if apellido else ''
        cache_key = f"nombre:{nombre_clave}|apellido:{apellido_clave}"

    if cache_key and cache_estudiantes is not None and cache_key in cache_estudiantes:
        return cache_estudiantes[cache_key], False

    # Buscar por nombre + apellido
    est = None
    creado = False
    if nombre:
        from sqlalchemy import func
        est = Estudiante.query.filter(
            func.concat(Estudiante.nombre, ' ', Estudiante.apellido) == nombre
        ).first()
        if not est:
            est = Estudiante.query.filter_by(nombre=nombre).first()
    
    paralelo_obj = None
    paralelo_norm = paralelo.strip().upper() if paralelo else None
    if paralelo_norm:
        if paralelo_norm in cache_paralelos:
            paralelo_obj = cache_paralelos[paralelo_norm]
        else:
            paralelo_obj = obtener_o_crear_paralelo(paralelo_norm, cache_paralelos)
    
    if not est:
        est = Estudiante(
            nombre=nombre, 
            apellido=apellido
        )
        if paralelo_obj:
            est.paralelo = paralelo_obj
        db.session.add(est)
        db.session.flush()
        creado = True
    else:
        est.paralelo = paralelo_obj if paralelo_obj else None

    if cache_key and cache_estudiantes is not None:
        cache_estudiantes[cache_key] = est
    
    return est, creado

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
                        'nombre': reporte.evaluacion.nombre,
                        'fecha_entrega': reporte.evaluacion.fecha_entrega.isoformat() if reporte.evaluacion and reporte.evaluacion.fecha_entrega else None
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
                    'fecha_entrega': caso.evaluacion.fecha_entrega.isoformat() if caso.evaluacion and caso.evaluacion.fecha_entrega else None,
                'sancion': caso.sancion,
                'caso_metadata': caso.caso_metadata,
                'estudiantes': estudiantes
            })
        
        return jsonify({
            'reporte': {
                'reporte_id': reporte.reporte_id,
                'titulo': reporte.titulo,
                'url_moss': reporte.url_moss,
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
            'url_moss': reporte.url_moss,
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
            'url_moss': reporte.url_moss,
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
                'fecha_entrega': caso.evaluacion.fecha_entrega.isoformat() if caso.evaluacion and caso.evaluacion.fecha_entrega else None,
                'sancion': caso.sancion,
                'caso_metadata': caso.caso_metadata,
                'estudiantes': estudiantes
            })
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"msg": "Error al filtrar casos", "error": str(e)}), 500


@reportes_bp.route('/caso/<int:caso_id>/aplazar', methods=['POST'])
@jwt_required()
def aplazar_plazo_caso(caso_id):
    try:
        data = request.get_json() or {}
        dias = int(data.get('dias', 0))
        if dias <= 0:
            return jsonify({"msg": "El campo 'dias' debe ser un entero positivo"}), 400

        current_user_id = int(get_jwt_identity())
        caso = Caso.query.get(caso_id)
        if not caso:
            return jsonify({"msg": "Caso no encontrado"}), 404

        # Permitir solo usuarios asignados o el creador del reporte
        assigned_ids = [u.user_id for u in caso.usuarios_asignados]
        if current_user_id not in assigned_ids and current_user_id != caso.reporte.user_id:
            return jsonify({"msg": "No autorizado para aplazar el plazo"}), 403

        evaluacion_obj = caso.evaluacion
        if not evaluacion_obj:
            return jsonify({"msg": "Evaluación asociada no encontrada para este caso"}), 400

        if evaluacion_obj.fecha_entrega:
            evaluacion_obj.fecha_entrega = evaluacion_obj.fecha_entrega + timedelta(days=dias)
        else:
            evaluacion_obj.fecha_entrega = datetime.now(ZoneInfo("America/Santiago")) + timedelta(days=dias)

        db.session.commit()
        return jsonify({"caso_id": caso.caso_id, "fecha_entrega": evaluacion_obj.fecha_entrega.isoformat()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Error aplazando el plazo", "error": str(e)}), 500

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
                    paralelos_stats[paralelo]['estudiantes_involucrados'].add(estudiante.estudiante_id)
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
