"""
Utilidades para procesar archivos Excel de reportes MOSS y Aula Virtual
"""
import pandas as pd
import re
import unicodedata
from typing import Tuple, Dict, List, Optional
from urllib.request import urlopen


class ExcelProcessor:

    MOSS_MATCH_TIMEOUT_SECONDS = 20

    def _normalizar_texto(self, value) -> str:
        text = unicodedata.normalize('NFKD', str(value))
        text = ''.join(ch for ch in text if not unicodedata.combining(ch))
        text = text.lower().strip()
        text = re.sub(r'[^a-z0-9]+', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extraer_url_padre_moss(self, dataframe) -> Optional[str]:
        for _, row in dataframe.iterrows():
            for value in row.dropna():
                text_value = str(value).strip()
                if 'moss.stanford.edu/results/' in text_value:
                    return text_value.rstrip('/')

        return None

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

    def _cargar_match_entries_moss(self, url_padre: str) -> Tuple[List[Dict], Dict[str, str]]:
        if not url_padre:
            return [], {}

        url_madre = url_padre.rstrip('/') + '/'

        try:
            html = urlopen(url_madre, timeout=self.MOSS_MATCH_TIMEOUT_SECONDS).read().decode('utf-8', errors='replace')
        except Exception:
            return [], {}

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

        return match_entries, primer_paralelo_por_estudiante

    def _buscar_match_moss(self, case_data: Dict, match_entries: List[Dict]) -> Optional[Dict]:
        estudiante1 = case_data.get('estudiante1', {})
        estudiante2 = case_data.get('estudiante2', {})

        estudiante1_texto = self._normalizar_texto(estudiante1.get('nombre', ''))
        estudiante2_texto = self._normalizar_texto(estudiante2.get('nombre', ''))
        paralelo1_texto = self._normalizar_texto(estudiante1.get('paralelo', ''))
        paralelo2_texto = self._normalizar_texto(estudiante2.get('paralelo', ''))

        try:
            similitud_case = int(round(float(case_data.get('similitud', 0))))
        except Exception:
            similitud_case = 0

        for match_entry in match_entries:
            coincidencia_directa = (
                estudiante1_texto in match_entry['text1'] and
                estudiante2_texto in match_entry['text2'] and
                paralelo1_texto in match_entry['text1'] and
                paralelo2_texto in match_entry['text2']
            )
            coincidencia_inversa = (
                estudiante1_texto in match_entry['text2'] and
                estudiante2_texto in match_entry['text1'] and
                paralelo1_texto in match_entry['text2'] and
                paralelo2_texto in match_entry['text1']
            )

            if not (coincidencia_directa or coincidencia_inversa):
                continue

            if similitud_case and similitud_case not in (match_entry['pct1'], match_entry['pct2']):
                continue

            return match_entry

        return None

    def procesar_archivo_excel(self, file_path_or_dataframe) -> Tuple[bool, Dict, List[str]]:
    
        try:
            # 1. Cargar el DataFrame
            if isinstance(file_path_or_dataframe, str):
                df = pd.read_excel(file_path_or_dataframe, header=None) if file_path_or_dataframe.endswith('.xlsx') else pd.read_csv(file_path_or_dataframe, header=None)
            else:
                df = file_path_or_dataframe.copy()
                if not df.empty and df.columns[0] != 0:
                    df = pd.concat([pd.DataFrame([df.columns]), df], ignore_index=True)
                    df.columns = range(df.shape[1])

            df_raw = df.copy()

            # 2. Identificar el índice de las cabeceras
            header_idx = -1
            for idx, row in df.iterrows():
                row_lower = [str(x).strip().lower() for x in row.values]
                if 'estudiante1' in row_lower and ('estudiante2' in row_lower or 'paralelo1' in row_lower):
                    header_idx = idx
                    break

            if header_idx == -1:
                return False, {}, ["No se encontraron las cabeceras requeridas ('estudiante1', 'estudiante2') en el archivo MOSS"]

            # 3. Limpiar y estructurar el DataFrame base
            df.columns = df.iloc[header_idx].astype(str).str.strip().str.lower()
            df = df.iloc[header_idx + 1:].reset_index(drop=True)
            df = df.dropna(how='all')

            # 4. BÚSQUEDA DINÁMICA DE LA COLUMNA DE LINKS DIRECTOS
            # Buscamos una columna que contenga URLs de "match" en sus primeras filas válidas
            columna_link_directo = None
            for col in df.columns:
                muestras = df[col].dropna().astype(str).head(1) # Tomamos 1 fila de muestra
                if any('match' in val.lower() and 'http' in val.lower() for val in muestras):
                    columna_link_directo = col
                    break

            # 5. Enrutamiento automático
            if columna_link_directo:
                # Si encontramos la columna, le pasamos el nombre exacto a la función
                return self._procesar_moss_directo(df, header_idx, columna_link_directo)
            else:
                # Si no hay links directos, asumimos que necesitamos hacer scraping
                return self._procesar_moss_con_scraping(df, df_raw, header_idx)

        except Exception as e:
            return False, {}, [f"Error procesando archivo MOSS: {str(e)}"]
        
    def _procesar_moss_directo(self, df: pd.DataFrame, header_idx: int, columna_link_directo: str) -> Tuple[bool, Dict, List[str]]:
        """Procesa el archivo usando los enlaces MOSS extraídos de la columna detectada dinámicamente."""
        cases_data = []
        
        for index, row in df.iterrows():
            est1_name = str(row.get('estudiante1', '')).strip()
            est2_name = str(row.get('estudiante2', '')).strip()

            if not est1_name or est1_name == 'nan' or not est2_name or est2_name == 'nan':
                continue

            if self._normalizar_texto(est1_name) == self._normalizar_texto(est2_name):
                continue

            similitud = 0.0
            if '%' in df.columns:
                try: similitud = float(row['%'])
                except Exception: pass

            # Usamos el nombre de la columna detectada para extraer la URL
            url_match = str(row.get(columna_link_directo, '')).strip()

            caso_data = {
                'estudiante1': {'rol': '', 'nombre': est1_name, 'apellido': '', 'paralelo': str(row.get('paralelo1', '')).strip()},
                'estudiante2': {'rol': '', 'nombre': est2_name, 'apellido': '', 'paralelo': str(row.get('paralelo2', '')).strip()},
                'similitud': similitud,
                'lineas': 0,
                'url_moss': url_match, # Asignación dinámica
                'fila_original': header_idx + index + 2
            }
            cases_data.append(caso_data)

        result = {
            'casos_validos': cases_data,
            'casos_invalidos': [],
            'total_filas_procesadas': len(cases_data),
            'casos_validos_count': len(cases_data),
            'casos_invalidos_count': 0,
            'url_padre_moss': None,
            'matches_encontrados': len(cases_data),
            'primer_paralelo_por_estudiante': {}
        }
        
        return True, result, []
    
    def _procesar_moss_con_scraping(self, df: pd.DataFrame, df_raw: pd.DataFrame, header_idx: int) -> Tuple[bool, Dict, List[str]]:
        """Procesa el archivo conectándose a la URL de MOSS para enriquecer los datos de las coincidencias."""
        url_padre = self._extraer_url_padre_moss(df_raw)
        match_entries, primer_paralelo_por_estudiante = self._cargar_match_entries_moss(url_padre) if url_padre else ([], {})

        cases_data = []
        
        for index, row in df.iterrows():
            est1_name = str(row.get('estudiante1', '')).strip()
            est2_name = str(row.get('estudiante2', '')).strip()

            if not est1_name or est1_name == 'nan' or not est2_name or est2_name == 'nan':
                continue

            if self._normalizar_texto(est1_name) == self._normalizar_texto(est2_name):
                continue

            estudiante1 = {'rol': '', 'nombre': est1_name, 'apellido': '', 'paralelo': str(row.get('paralelo1', '')).strip()}
            estudiante2 = {'rol': '', 'nombre': est2_name, 'apellido': '', 'paralelo': str(row.get('paralelo2', '')).strip()}

            similitud = 0.0
            if '%' in df.columns:
                try: similitud = float(row['%'])
                except Exception: pass

            caso_data = {
                'estudiante1': estudiante1,
                'estudiante2': estudiante2,
                'similitud': similitud,
                'lineas': 0,
                'url_moss': url_padre,
                'fila_original': header_idx + index + 2
            }

            # Cruce de datos con la información web extraída
            match_entry = self._buscar_match_moss(caso_data, match_entries)
            if match_entry:
                estudiante1['paralelo'] = primer_paralelo_por_estudiante.get(match_entry['student1_key'], estudiante1['paralelo'])
                estudiante2['paralelo'] = primer_paralelo_por_estudiante.get(match_entry['student2_key'], estudiante2['paralelo'])
                caso_data['url_moss'] = match_entry['match_url']
                caso_data['lineas'] = match_entry['lines']

            cases_data.append(caso_data)

        result = {
            'casos_validos': cases_data,
            'casos_invalidos': [],
            'total_filas_procesadas': len(cases_data),
            'casos_validos_count': len(cases_data),
            'casos_invalidos_count': 0,
            'url_padre_moss': url_padre,
            'matches_encontrados': len(match_entries),
            'primer_paralelo_por_estudiante': primer_paralelo_por_estudiante
        }
        
        return True, result, []

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

