import pandas as pd
import re
from typing import Tuple, Dict, List, Optional

class ExcelProcessor:
    
    def procesar_archivo_excel(self, file_path_or_dataframe) -> Tuple[bool, Dict, List[str]]:
        try:
            if isinstance(file_path_or_dataframe, str):
                df = pd.read_excel(file_path_or_dataframe, header=None) if file_path_or_dataframe.endswith('.xlsx') else pd.read_csv(file_path_or_dataframe, header=None)
            else:
                df = file_path_or_dataframe.copy()
                if not df.empty and df.columns[0] != 0:
                    df = pd.DataFrame([df.columns])._append(df, ignore_index=True)
                    df.columns = range(df.shape[1])
            
            url_padre = None
            header_idx = -1
            
            for idx, row in df.iterrows():
                for val in row.dropna():
                    str_val = str(val).strip()
                    if 'moss.stanford.edu/results' in str_val or str_val.startswith('http'):
                        url_padre = str_val
                
                row_lower = [str(x).strip().lower() for x in row.values]
                if 'estudiante1' in row_lower and 'estudiante2' in row_lower:
                    header_idx = idx
                    break
            
            if header_idx == -1:
                return False, {}, ["No se encontraron las cabeceras requeridas ('estudiante1', 'estudiante2') en el archivo MOSS"]
            
            df.columns = df.iloc[header_idx].astype(str).str.strip().str.lower()
            df = df.iloc[header_idx+1:].reset_index(drop=True)
            df = df.dropna(how='all')
            
            cases_data = []
            for index, row in df.iterrows():
                est1_name = str(row.get('estudiante1', '')).strip()
                est2_name = str(row.get('estudiante2', '')).strip()
                
                if not est1_name or est1_name == 'nan' or not est2_name or est2_name == 'nan':
                    continue
                    
                estudiante1 = {
                    'rol': '',
                    'nombre': est1_name,
                    'apellido': '',
                    'paralelo': str(row.get('paralelo1', '')).strip()
                }
                
                estudiante2 = {
                    'rol': '',
                    'nombre': est2_name,
                    'apellido': '',
                    'paralelo': str(row.get('paralelo2', '')).strip()
                }
                
                similitud = 0.0
                if '%' in df.columns:
                    try:
                        similitud = float(row['%'])
                    except:
                        pass
                
                cases_data.append({
                    'estudiante1': estudiante1,
                    'estudiante2': estudiante2,
                    'similitud': similitud,
                    'lineas': 0,
                    'url_moss': url_padre,
                    'fila_original': header_idx + index + 2
                })
            
            result = {
                'casos_validos': cases_data,
                'casos_invalidos': [],
                'total_filas_procesadas': len(cases_data),
                'casos_validos_count': len(cases_data),
                'casos_invalidos_count': 0
            }
            
            return True, result, []
            
        except Exception as e:
            return False, {}, [f"Error procesando archivo: {str(e)}"]

    def procesar_aula_virtual(self, file_path_or_dataframe) -> Tuple[bool, Dict, List[str]]:
        try:
            if isinstance(file_path_or_dataframe, str):
                df = pd.read_excel(file_path_or_dataframe) if file_path_or_dataframe.endswith('.xlsx') else pd.read_csv(file_path_or_dataframe)
            else:
                df = file_path_or_dataframe.copy()
                
            cols = [str(c).lower().strip() for c in df.columns]
            df.columns = cols
            
            expected_cols = ['nombre', 'apellido(s)', 'número de id', 'dirección de correo', 'grupos']
            for c in ['número de id', 'grupos']:
                if c not in cols:
                    # fallback
                    return False, {}, [f"No se encontró la columna requerida: {c}"]
            
            participantes = []
            for index, row in df.iterrows():
                grupos_str = str(row.get('grupos', ''))
                # XXXYYY_ZL
                matches = re.findall(r'[A-Za-z]+[0-9]+_\d+L', grupos_str)
                if not matches:
                    continue # No pertenece a un paralelo de laboratorio
                
                # Para evitar duplicados en la lista del mismo estudiante, tomamos el primer match
                paralelo = matches[0].strip()
                
                numero_id = str(row.get('número de id', '')).strip()
                if not numero_id or numero_id == 'nan':
                    continue
                
                participantes.append({
                    'nombre': str(row.get('nombre', '')).strip(),
                    'apellido': str(row.get('apellido(s)', '')).strip(),
                    'numero_id': numero_id,
                    'correo': str(row.get('dirección de correo', '')).strip(),
                    'paralelo': paralelo
                })
                
            return True, {'participantes': participantes}, []
        except Exception as e:
            return False, {}, [f"Error procesando archivo aula virtual: {str(e)}"]

