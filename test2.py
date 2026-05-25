import pandas as pd
class TestM:
    def procesar(self, filename):
        df_raw = pd.read_excel(filename, header=None)
        
        # 1. Encontrar la URL padre
        url_padre = None
        header_idx = -1
        
        for idx, row in df_raw.iterrows():
            for val in row.dropna():
                str_val = str(val).strip().lower()
                if 'moss.stanford.edu' in str_val or str_val.startswith('http'):
                    url_padre = str(val).strip()
                
            # 2. Encontrar la fila de cabeceras
            row_lower = [str(x).strip().lower() for x in row.values]
            if 'estudiante1' in row_lower and '%' in row_lower:
                header_idx = idx
                break
                
        print(f"URL Padre: {url_padre}")
        print(f"Index Cabecera: {header_idx}")
        return url_padre, header_idx

