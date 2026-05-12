"""
Utilidades para procesar archivos Excel de reportes MOSS
"""
import pandas as pd
import re
from typing import Tuple, Dict, List, Optional

class ExcelProcessor:
    
    def __init__(self):
        self.required_columns_base = ['ROL', 'Nombres', 'Apellidos', 'Paralelo', '% de Copia']
        self.required_columns_duplicate = [col + '.1' for col in self.required_columns_base]
        
    def validar_estructura_archivo(self, df: pd.DataFrame) -> Tuple[bool, List[str], List[str]]:

        available_columns = df.columns.tolist()
        missing_columns = []
        
        all_required = self.required_columns_base + self.required_columns_duplicate
        
        for col in all_required:
            if col not in available_columns:
                missing_columns.append(col)
        
        is_valid = len(missing_columns) == 0
        return is_valid, missing_columns, available_columns
    
    def normalizar_nombres_columnas(self, df: pd.DataFrame) -> pd.DataFrame:
        df_copy = df.copy()
        
        column_mapping = {}
        
        for col in df_copy.columns:
            col_lower = col.lower().strip()
            
            if any(pattern in col_lower for pattern in ['lineas sim', 'líneas sim', 'lineas similares', 'líneas similares']):
                column_mapping[col] = 'Lineas_Similares'
            
            elif any(pattern in col_lower for pattern in ['moss file', 'moss url', 'url moss', 'archivo moss']):
                column_mapping[col] = 'MOSS_File'
            
            elif 'copia' in col_lower and '%' in col_lower:
                if '.1' in col:
                    column_mapping[col] = '% de Copia.1'
                else:
                    column_mapping[col] = '% de Copia'
        
        if column_mapping:
            df_copy = df_copy.rename(columns=column_mapping)
            
        return df_copy
    
    def limpiar_datos(self, df: pd.DataFrame) -> pd.DataFrame:
        df_clean = df.copy()
        
        df_clean = df_clean.dropna(how='all')
        
        df_clean = df_clean.dropna(subset=['ROL', 'ROL.1'], how='all')
        
        string_columns = df_clean.select_dtypes(include=['object']).columns
        for col in string_columns:
            df_clean[col] = df_clean[col].astype(str).str.strip()
        
        df_clean = df_clean.replace('nan', None)
        
        return df_clean
    
    def extraer_datos_casos(self, df: pd.DataFrame) -> List[Dict]:
        cases_data = []
        
        for index, row in df.iterrows():
            try:
                if pd.isna(row.get('ROL')) or pd.isna(row.get('ROL.1')):
                    continue
                
                estudiante1 = {
                    'rol': str(row['ROL']).strip(),
                    'nombre': str(row.get('Nombres', '')).strip(),
                    'apellido': str(row.get('Apellidos', '')).strip(),
                    'paralelo': str(row.get('Paralelo', '')).strip()
                }
                
                estudiante2 = {
                    'rol': str(row['ROL.1']).strip(),
                    'nombre': str(row.get('Nombres.1', '')).strip(),
                    'apellido': str(row.get('Apellidos.1', '')).strip(),
                    'paralelo': str(row.get('Paralelo.1', '')).strip()
                }
                
                try:
                    similitud1 = float(row.get('% de Copia', 0))
                    similitud2 = float(row.get('% de Copia.1', 0))
                    similitud = max(similitud1, similitud2)
                except (ValueError, TypeError):
                    similitud = 0.0
                
                lineas = 0
                lineas_col = None
                for col_name in ['Lineas_Similares', 'Lineas Sim', 'Lineas Similares']:
                    if col_name in df.columns and pd.notna(row.get(col_name)):
                        try:
                            lineas = int(float(row[col_name]))
                            break
                        except (ValueError, TypeError):
                            continue
                
                url_moss = None
                for col_name in ['MOSS_File', 'MOSS File', 'URL MOSS']:
                    if col_name in df.columns and pd.notna(row.get(col_name)):
                        url_moss = str(row[col_name]).strip()
                        if url_moss.lower() != 'nan' and url_moss:
                            break
                        else:
                            url_moss = None
                
                case_data = {
                    'estudiante1': estudiante1,
                    'estudiante2': estudiante2,
                    'similitud': similitud,
                    'lineas': lineas,
                    'url_moss': url_moss,
                    'fila_original': index + 1
                }
                
                cases_data.append(case_data)
                
            except Exception as e:
                print(f"Error procesando fila {index + 1}: {str(e)}")
                continue
        
        return cases_data
    
    def validar_datos_caso(self, case_data: Dict) -> Tuple[bool, List[str]]:
        errors = []
        
        if not case_data['estudiante1']['rol'] or case_data['estudiante1']['rol'] == 'nan':
            errors.append("ROL del primer estudiante es requerido")
        
        if not case_data['estudiante2']['rol'] or case_data['estudiante2']['rol'] == 'nan':
            errors.append("ROL del segundo estudiante es requerido")
        
        if not isinstance(case_data['similitud'], (int, float)) or case_data['similitud'] < 0 or case_data['similitud'] > 100:
            errors.append("Porcentaje de similitud debe estar entre 0 y 100")
        
        if case_data['estudiante1']['rol'] == case_data['estudiante2']['rol']:
            errors.append("No puede haber un caso entre el mismo estudiante")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def procesar_archivo_excel(self, file_path_or_dataframe) -> Tuple[bool, Dict, List[str]]:
        try:
            if isinstance(file_path_or_dataframe, str):
                if file_path_or_dataframe.endswith('.csv'):
                    df = pd.read_csv(file_path_or_dataframe)
                else:
                    df = pd.read_excel(file_path_or_dataframe)
            else:
                df = file_path_or_dataframe
            
            is_valid, missing_cols, available_cols = self.validar_estructura_archivo(df)
            if not is_valid:
                return False, {}, [f"Columnas faltantes: {missing_cols}", f"Columnas disponibles: {available_cols}"]
            
            df = self.normalizar_nombres_columnas(df)
            
            df = self.limpiar_datos(df)
            
            cases_data = self.extraer_datos_casos(df)
            
            valid_cases = []
            invalid_cases = []
            
            for case in cases_data:
                is_case_valid, case_errors = self.validar_datos_caso(case)
                if is_case_valid:
                    valid_cases.append(case)
                else:
                    invalid_cases.append({
                        'fila': case.get('fila_original', 'N/A'),
                        'errores': case_errors
                    })
            
            result = {
                'casos_validos': valid_cases,
                'casos_invalidos': invalid_cases,
                'total_filas_procesadas': len(df),
                'casos_validos_count': len(valid_cases),
                'casos_invalidos_count': len(invalid_cases)
            }
            
            return True, result, []
            
        except Exception as e:
            return False, {}, [f"Error procesando archivo: {str(e)}"]