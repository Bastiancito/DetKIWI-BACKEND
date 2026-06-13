import sys
from urllib.request import urlopen

import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from typing import Optional, Tuple, Dict, List, Any
import logging

# 1. Obtenemos el logger de este archivo
logger = logging.getLogger(__name__)

# 2. Forzamos el nivel a INFO (para que escuche los logger.info)
logger.setLevel(logging.INFO)

# 3. Limpiamos configuraciones viejas que puedan estar bloqueándolo
if logger.hasHandlers():
    logger.handlers.clear()

# 4. Le decimos explícitamente que escupa los datos a la consola estándar de Docker (sys.stdout)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)

# 5. Le damos un formato fácil de leer
formatter = logging.Formatter('👉 [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# 6. Forzamos a Python a no retener los logs en memoria (Flush automático)
sys.stdout.reconfigure(line_buffering=True)

class ExcelProcessor:
    def _normalizar_texto(self, texto: Any) -> str:
        """Convierte texto a minúsculas y elimina espacios muertos. Maneja nulos."""
        if pd.isna(texto) or str(texto).strip().lower() == 'nan':
            return ""
        return str(texto).strip().lower()

    def _limpiar_nombre_columna(self, col: Any) -> str:
        """Limpia las cabeceras: quita espacios, guiones y pasa a minúsculas para coincidencia perfecta."""
        return str(col).strip().lower().replace(' ', '').replace('_', '')
    
    def _parsear_texto_match_moss(self, raw_text: str) -> Dict[str, str]:
        text = str(raw_text).strip()
        if text.startswith('./'):
            text = text[2:]

        parallel = ''
        file_text = text
        if '/' in text:
            parallel, file_text = text.split('/', 1)

        file_text = file_text.split(' (', 1)[0]
        file_text = re.sub(r'_assignsubmission_file_.*$', '', file_text)
        file_text = re.sub(r'_\d+$', '', file_text)
        file_text = re.sub(r'\.[A-Za-z0-9]{1,5}$', '', file_text)

        return {
            'raw_text': text,
            'parallel_raw': parallel.strip(),
            'parallel_normalized': self._normalizar_texto(parallel),
            'student_key': self._normalizar_texto(file_text.replace('_', ' ')),
            'full_text': self._normalizar_texto(text),
        }

    def procesar_archivo_excel(self, file_path_or_dataframe) -> Tuple[bool, Dict, List[str]]:
        try:
            # 1. Carga nativa enfocada en Excel
            if isinstance(file_path_or_dataframe, str):
                df = pd.read_excel(file_path_or_dataframe, header=None)
            else:
                df = file_path_or_dataframe.copy()
                
                # Si el DataFrame viene con los títulos atrapados en las cabeceras, los bajamos como fila
                if not all(isinstance(c, int) for c in df.columns):
                    df.loc[-1] = df.columns
                    df.index = df.index + 1
                    df = df.sort_index()

            # 2. LA ASPIRADORA DE EXCEL: Elimina todas las columnas fantasma que estén 100% vacías
            df = df.dropna(axis=1, how='all')
            df.columns = range(df.shape[1]) # Reseteamos los números de las columnas (0, 1, 2...)

            df_raw = df.copy()

            # 3. Buscar la fila de cabeceras verdaderas
            header_idx = -1
            for idx, row in df.iterrows():
                row_clean = [str(x).strip().lower().replace(' ', '').replace('_', '') for x in row.values]
                if 'estudiante1' in row_clean and ('estudiante2' in row_clean or 'paralelo1' in row_clean):
                    header_idx = idx
                    df.columns = row_clean # Bautizamos las columnas con los nombres limpios
                    break

            if header_idx == -1:
                return False, {}, ["No se encontraron las cabeceras ('estudiante1', 'estudiante2') en el Excel."]

            # 4. Limpiar los datos debajo de la cabecera
            df = df.iloc[header_idx + 1:].reset_index(drop=True)
            df = df.dropna(how='all') # Elimina filas 100% vacías

            # 5. Escáner de Links (Sin importar cómo se llame la columna)
            columna_link_directo = None
            print(f"--- DEBUG MOSS --- Columnas limpias detectadas: {list(df.columns)}")
            
            for idx, row in df.head(15).iterrows():
                for col_name, val in row.items():
                    val_str = str(val).lower().strip()
                    
                    if val_str == 'nan' or not val_str:
                        continue 
                        
                    if 'match' in val_str and ('moss' in val_str or 'http' in val_str or 'html' in val_str):
                        columna_link_directo = col_name
                        print(f"--- DEBUG MOSS --- ¡Link atrapado en la columna '{col_name}'!")
                        break
                        
                if columna_link_directo:
                    break

            # 6. Enrutamiento Inteligente
            if columna_link_directo:
                print("--- DEBUG MOSS --- Ruta elegida: PROCESAMIENTO DIRECTO (Sin Scraping)")
                return self._procesar_moss_directo(df, header_idx, columna_link_directo)
            else:
                print("--- DEBUG MOSS --- Ruta elegida: WEB SCRAPING (No se detectaron links directos)")
                return self._procesar_moss_con_scraping(df, df_raw, header_idx)

        except Exception as e:
            return False, {}, [f"Error general procesando archivo Excel MOSS: {str(e)}"]

    def _procesar_moss_directo(self, df: pd.DataFrame, header_idx: int, columna_link_directo: str) -> Tuple[bool, Dict, List[str]]:
        """Procesa archivos que ya tienen el link directo de coincidencia."""
        cases_data = []
        invalid_cases = []

        for index, row in df.iterrows():
            fila_excel = header_idx + index + 2
            
            # Usar la función de normalización que creamos
            est1_name = self._normalizar_texto(row.get('estudiante1'))
            est2_name = self._normalizar_texto(row.get('estudiante2'))

            if not est1_name or not est2_name:
                invalid_cases.append({"fila": fila_excel, "motivo": "Faltan nombres de estudiantes", "celdas_vistas": [str(row.get('estudiante1')), str(row.get('estudiante2'))]})
                continue

            if est1_name == est2_name:
                invalid_cases.append({"fila": fila_excel, "motivo": "Estudiante 1 y 2 son la misma persona"})
                continue

            # Extracción segura de la similitud (por si viene como "85%")
            similitud = 0.0
            try:
                val_similitud = str(row.values[0]).replace('%', '').strip()
                if val_similitud.lower() != 'nan' and val_similitud:
                    similitud = float(val_similitud)
            except Exception as e:
                logger.warning(f"No se pudo convertir el porcentaje en la fila {fila_excel}: {e}")

            url_match = str(row.get(columna_link_directo, '')).strip()

            caso_data = {
                'estudiante1': {'rol': '', 'nombre': str(row.get('estudiante1', '')).strip(), 'apellido': '', 'paralelo': str(row.get('paralelo1', '')).strip()},
                'estudiante2': {'rol': '', 'nombre': str(row.get('estudiante2', '')).strip(), 'apellido': '', 'paralelo': str(row.get('paralelo2', '')).strip()},
                'similitud': similitud,
                'lineas': 0,
                'url_moss': url_match,
                'fila_original': fila_excel
            }
            cases_data.append(caso_data)

        result = self._empaquetar_resultados(cases_data, invalid_cases, None, len(cases_data), {})
        return True, result, []
    
    def limpiar_para_cruce(texto):
                        # 1. Cambiamos puntos, guiones y barras de carpeta por espacios
                        texto_espacios = re.sub(r'[._/\\-]', ' ', str(texto).lower())
                        # 2. Eliminamos números y caracteres raros (dejamos solo letras y espacios)
                        texto_puro = re.sub(r'[^a-záéíóúñ\s]', '', texto_espacios)
                        # 3. Devolvemos el set de palabras sueltas
                        return set(texto_puro.split())

    def _procesar_moss_con_scraping(self, df: pd.DataFrame, df_raw: pd.DataFrame, header_idx: int) -> Tuple[bool, Dict, List[str]]:
        """Procesa archivos usando web scraping basado en la URL padre."""
        url_padre = self._extraer_url_padre_moss(df_raw)
        
        logger.info(f"[SCRAPING] Iniciando procesamiento. URL Padre encontrada: {url_padre}")
        
        match_entries = []
        primer_paralelo_por_estudiante = {}
        
        if url_padre:
            logger.info(f"[SCRAPING] Llamando a MOSS en: {url_padre}")
            try:
                resultado_scraping = self._cargar_match_entries_moss(url_padre)
                
                if isinstance(resultado_scraping, tuple) and len(resultado_scraping) == 2:
                    match_entries, primer_paralelo_por_estudiante = resultado_scraping
                else:
                    logger.warning(f"[SCRAPING] Formato inesperado. Se esperaba tupla, llegó: {type(resultado_scraping)}")
            except Exception as e:
                logger.error(f"[SCRAPING] Excepción crítica al intentar hacer scraping: {str(e)}", exc_info=True)
        else:
            logger.warning("[SCRAPING] No se encontró ninguna URL padre válida en el archivo.")

        cases_data = []
        invalid_cases = []

        for index, row in df.iterrows():
            fila_excel = header_idx + index + 2
            
            est1_name = self._normalizar_texto(row.get('estudiante1'))
            est2_name = self._normalizar_texto(row.get('estudiante2'))

            if not est1_name or not est2_name:
                invalid_cases.append({"fila": fila_excel, "motivo": "Faltan nombres de estudiantes"})
                continue

            if est1_name == est2_name:
                invalid_cases.append({"fila": fila_excel, "motivo": "Estudiante 1 y 2 son la misma persona"})
                continue

            similitud = 0.0
            try:
                # Extraemos el valor directamente de la celda 0 de la fila
                val_similitud = str(row.values[0]).replace('%', '').strip()
                if val_similitud.lower() != 'nan' and val_similitud:
                    similitud = float(val_similitud)
            except Exception as e:
                logger.warning(f"No se pudo convertir el porcentaje en la fila {fila_excel}: {e}")

            estudiante1 = {'rol': '', 'nombre': str(row.get('estudiante1', '')).strip(), 'apellido': '', 'paralelo': str(row.get('paralelo1', '')).strip()}
            estudiante2 = {'rol': '', 'nombre': str(row.get('estudiante2', '')).strip(), 'apellido': '', 'paralelo': str(row.get('paralelo2', '')).strip()}

            caso_data = {
                'estudiante1': estudiante1,
                'estudiante2': estudiante2,
                'similitud': similitud,
                'lineas': 0,
                'url_moss': url_padre,
                'fila_original': fila_excel
            }

            match_entry = self._buscar_match_moss(caso_data, match_entries)
            if match_entry:
                estudiante1['paralelo'] = primer_paralelo_por_estudiante.get(match_entry['student1_key'], estudiante1['paralelo'])
                estudiante2['paralelo'] = primer_paralelo_por_estudiante.get(match_entry['student2_key'], estudiante2['paralelo'])
                caso_data['url_moss'] = match_entry['match_url']
                caso_data['lineas'] = match_entry['lines']

            cases_data.append(caso_data)

        result = self._empaquetar_resultados(cases_data, invalid_cases, url_padre, len(match_entries), primer_paralelo_por_estudiante)
        return True, result, []

    def _empaquetar_resultados(self, cases_data, invalid_cases, url_padre, matches_count, paralelo_dict):
        """Función auxiliar para estandarizar el diccionario de respuesta"""
        return {
            'casos_validos': cases_data,
            'casos_invalidos': invalid_cases,
            'total_filas_procesadas': len(cases_data) + len(invalid_cases),
            'casos_validos_count': len(cases_data),
            'casos_invalidos_count': len(invalid_cases),
            'url_padre_moss': url_padre,
            'matches_encontrados': matches_count,
            'primer_paralelo_por_estudiante': paralelo_dict
        }

    # =====================================================================
    # MÉTODOS DE SCRAPING (Mantén los que ya tenías funcionales)
    # =====================================================================
    def _extraer_url_padre_moss(self, df: pd.DataFrame) -> str:
        # Aquí va tu lógica actual para encontrar http://moss.stanford.edu...
        for _, row in df.head(15).iterrows():
            for val in row.values:
                val_str = str(val).strip()
                if 'moss.stanford.edu/results' in val_str:
                    return val_str
        return ""

    def _cargar_match_entries_moss(self, url_padre: str) -> Tuple[List[Dict], Dict[str, str]]:
        if not url_padre:
            return [], {}

        # 1. LIMPIEZA EXTREMA DE LA URL: Quitamos espacios, saltos de línea y caracteres invisibles
        url_limpia = str(url_padre).strip().replace('\u200b', '').replace('\u2060', '').replace('\n', '')
        url_madre = url_limpia.rstrip('/') + '/'

        logger.info(f"--- DEBUG SCRAPER --- Intentando GET a: '{url_madre}'")

        try:
            # 2. DISFRAZ: Usamos requests en lugar de urlopen y nos hacemos pasar por navegador
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(url_madre, headers=headers, timeout=10)
            
            logger.info(f"--- DEBUG SCRAPER --- Status Code: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"--- DEBUG SCRAPER --- MOSS devolvió error {response.status_code}")
                return [], {}
                
            html = response.text

            # 3. Tu lógica original (intacta)
            pattern = re.compile(
                r'<TR><TD><A HREF="(?P<url1>[^"]+)">(?P<text1>.*?)</A>\s*'
                r'<TD><A HREF="(?P<url2>[^"]+)">(?P<text2>.*?)</A>\s*'
                r'<TD[^>]*>(?P<lines>\d+)',
                re.S | re.I
            )

            match_entries = []
            primer_paralelo_por_estudiante = {}

            for match in pattern.finditer(html):
                file1 = self._parsear_texto_match_moss(match.group('text1'))
                file2 = self._parsear_texto_match_moss(match.group('text2'))

                porcentaje1 = int(re.search(r'\((\d+)%\)', match.group('text1')).group(1))
                porcentaje2 = int(re.search(r'\((\d+)%\)', match.group('text2')).group(1))

                for parsed_file in (file1, file2):
                    student_key = parsed_file['student_key']
                    parallel_raw = parsed_file['parallel_raw']
                    if student_key and parallel_raw and student_key not in primer_paralelo_por_estudiante:
                        primer_paralelo_por_estudiante[student_key] = parallel_raw

                match_entries.append({
                    'match_url': match.group('url1'),
                    'text1': file1['full_text'],
                    'text2': file2['full_text'],
                    'student1_key': file1['student_key'],
                    'student2_key': file2['student_key'],
                    'parallel1_raw': file1['parallel_raw'],
                    'parallel2_raw': file2['parallel_raw'],
                    'pct1': porcentaje1,
                    'pct2': porcentaje2,
                    'lines': int(match.group('lines')),
                })

            logger.info(f"--- DEBUG SCRAPER --- ¡Éxito! Se procesaron {len(match_entries)} links.")
            return match_entries, primer_paralelo_por_estudiante

        except Exception as e:
            # Ahora sí veremos el error si ocurre algo malo
            logger.error(f"--- DEBUG SCRAPER --- ERROR CRÍTICO DE RED: {e}", exc_info=True)
            return [], {}

    def _buscar_match_moss(self, case_data: Dict, match_entries: List[Dict]) -> Optional[Dict]:
        import re

        estudiante1 = case_data.get('estudiante1', {})
        estudiante2 = case_data.get('estudiante2', {})

        nombre_e1 = self._normalizar_texto(estudiante1.get('nombre', ''))
        nombre_e2 = self._normalizar_texto(estudiante2.get('nombre', ''))
        
        # Limpiamos los paralelos para dejar SOLO letras y números
        paralelo1 = re.sub(r'[^a-z0-9]', '', self._normalizar_texto(estudiante1.get('paralelo', '')))
        paralelo2 = re.sub(r'[^a-z0-9]', '', self._normalizar_texto(estudiante2.get('paralelo', '')))

        try:
            similitud_case = int(round(float(case_data.get('similitud', 0))))
        except Exception:
            similitud_case = 0

        # --- LOG INICIAL: Mostramos qué estamos buscando ---
        logger.info(f"--- DEBUG MATCH --- BUSCANDO EXCEL: E1='{nombre_e1}' (Para: '{paralelo1}') | E2='{nombre_e2}' (Para: '{paralelo2}') | Pct: {similitud_case}")

        def es_match_parcial(nombre_excel, texto_moss):
            tokens_excel = re.sub(r'[._/\\-]', ' ', str(nombre_excel).lower()).split()
            tokens_moss = re.sub(r'[._/\\-]', ' ', str(texto_moss).lower()).split()

            if not tokens_excel: 
                return False

            coincidencias = 0
            for token_ex in tokens_excel:
                for token_moss in tokens_moss:
                    if token_ex in token_moss:
                        coincidencias += 1
                        break 
            
            return coincidencias == len(tokens_excel)

        for match_entry in match_entries:
            text1 = self._normalizar_texto(match_entry['text1'])
            text2 = self._normalizar_texto(match_entry['text2'])
            
            text1_limpio = re.sub(r'[^a-z0-9]', '', text1)
            text2_limpio = re.sub(r'[^a-z0-9]', '', text2)

            match_nombre_e1_en_t1 = es_match_parcial(nombre_e1, text1)
            match_para_e1_en_t1 = paralelo1 in text1_limpio
            match_e1_en_t1 = match_nombre_e1_en_t1 and match_para_e1_en_t1

            match_nombre_e2_en_t2 = es_match_parcial(nombre_e2, text2)
            match_para_e2_en_t2 = paralelo2 in text2_limpio
            match_e2_en_t2 = match_nombre_e2_en_t2 and match_para_e2_en_t2
            
            match_nombre_e1_en_t2 = es_match_parcial(nombre_e1, text2)
            match_para_e1_en_t2 = paralelo1 in text2_limpio
            match_e1_en_t2 = match_nombre_e1_en_t2 and match_para_e1_en_t2

            match_nombre_e2_en_t1 = es_match_parcial(nombre_e2, text1)
            match_para_e2_en_t1 = paralelo2 in text1_limpio
            match_e2_en_t1 = match_nombre_e2_en_t1 and match_para_e2_en_t1

            coincidencia_directa = match_e1_en_t1 and match_e2_en_t2
            coincidencia_inversa = match_e1_en_t2 and match_e2_en_t1

            if coincidencia_directa or coincidencia_inversa:
                # Si pasamos los nombres y paralelos, verificamos el porcentaje
                if similitud_case and similitud_case not in (match_entry['pct1'], match_entry['pct2']):
                    logger.info(f"     [X] Falla % -> Nombres/Paralelos OK, pero % Excel ({similitud_case}) no coincide con MOSS ({match_entry['pct1']}, {match_entry['pct2']}) en URL {match_entry['match_url']}")
                    continue
                
                # ¡TODO EXCELENTE!
                logger.info(f"     [✔] ¡MATCH EXITOSO! -> Asignando URL individual: {match_entry['match_url']}")
                return match_entry

            # --- LOG DE FALLA: Nos dice exactamente por qué este entry de MOSS fue descartado ---
            # Descomenta las siguientes 3 líneas SOLO si necesitas ver el detalle por cada uno de los 250 links de MOSS (hará el log muy largo)
            # if match_nombre_e1_en_t1 or match_nombre_e1_en_t2: 
            #     logger.info(f"     [-] Falla parcial: Nombres1_T1={match_nombre_e1_en_t1}, Para1_T1={match_para_e1_en_t1} | Nombres2_T2={match_nombre_e2_en_t2}, Para2_T2={match_para_e2_en_t2}")
            continue

        logger.info("--- DEBUG MATCH --- [!] ADVERTENCIA: Termina el ciclo sin matches. Asignando URL padre por defecto.")
        return None
    
    def procesar_aula_virtual(self, file_path_or_dataframe) -> Tuple[bool, Dict, List[str]]:
        try:
            if isinstance(file_path_or_dataframe, str):
                df = pd.read_excel(file_path_or_dataframe) if file_path_or_dataframe.endswith('.xlsx') else pd.read_csv(file_path_or_dataframe)
            else:
                df = file_path_or_dataframe.copy()

            cols = [str(c).lower().strip() for c in df.columns]
            df.columns = cols

            id_col = 'número de id' if 'número de id' in cols else 'numero de id'
            if id_col not in cols:
                return False, {}, [f"No se encontró la columna requerida: Número de ID"]

            if 'grupos' not in cols:
                return False, {}, [f"No se encontró la columna requerida: Grupos"]

            participantes = []
            for index, row in df.iterrows():
                grupos_str = str(row.get('grupos', ''))
                # Se ajusta regex: XXXYYY_ZL donde XXX pueden ser letras o numeros (e.g. EIN413B). L es obligatorio al final.
                matches = re.findall(r'[A-Za-z0-9]+_\d+L', grupos_str)
                if not matches:
                    continue # No pertenece a un paralelo de laboratorio

                paralelos = list(set([m.strip() for m in matches]))

                numero_id = str(row.get(id_col, '')).strip()
                if not numero_id or numero_id == 'nan':
                    continue

                apellido = str(row.get('apellido(s)', '')).strip()
                if not apellido or apellido == 'nan':
                    apellido = str(row.get('apellidos', '')).strip()

                participantes.append({
                    'nombre': str(row.get('nombre', '')).strip(),
                    'apellido': apellido,
                    'numero_id': numero_id,
                    'correo': str(row.get('dirección de correo', '')).strip(),
                    'paralelos': paralelos
                })

            return True, {'participantes': participantes}, []
        except Exception as e:
            return False, {}, [f"Error procesando archivo aula virtual: {str(e)}"]