# Documentacion de cambios para el flujo MOSS

Fecha: 2026-05-20

## Objetivo

Este documento resume de forma completa los cambios hechos para que el procesamiento de reportes MOSS deje de usar solo el link padre del Excel y, en su lugar, asigne a cada caso su URL de match real dentro de la pagina madre de MOSS.

Tambien deja registro de los ajustes hechos al endpoint de debug para que sea util tanto con el archivo local `utils/moss.xlsx` como con un archivo subido por `POST`.

## Contexto del problema

Antes del cambio, el flujo trabajaba de esta forma:

- El Excel traia un link padre de MOSS, pero ese link ya estaba expirado.
- El procesador guardaba el link padre en todos los casos, sin separar el match individual de cada fila.
- Cuando un estudiante aparecia en mas de un paralelo, el flujo podia terminar reescribiendo el paralelo del estudiante o descartando casos que en realidad debian conservarse.
- El endpoint de debug servia para inspeccionar el archivo local, pero no devolvia un resumen practico por caso y no aceptaba un archivo externo de forma clara.

## Cambios realizados por archivo

### 1. `utils/excel_processor.py`

Se hizo el cambio principal del flujo de parsing y cruce con MOSS.

Cambios agregados:

- Se agrego normalizacion de texto para comparar nombres y paralelos sin depender de mayusculas, acentos o simbolos raros.
- Se agrego la extraccion del link padre de MOSS desde el archivo Excel.
- Se agrego la descarga y parseo del HTML de la pagina madre de MOSS.
- Se agrego la lectura de cada fila de match para obtener su URL real `matchN.html`.
- Se agrego la logica de cruce entre cada caso del Excel y el match correcto de la pagina madre.
- Se agrego la asignacion de `lineas` desde el match real cuando se logra identificar el caso.
- Se agrego una tabla de primeros paralelos vistos por estudiante para resolver casos en que un alumno aparece repetido en mas de un paralelo.
- Se ajusto el procesamiento para conservar esos casos repetidos en vez de descartarlos.
- Se reemplazo el uso de una operacion obsoleta de pandas por una combinacion compatible con el entorno actual.

Comportamiento nuevo del procesador:

- Sigue detectando el URL padre del workbook.
- Ahora construye una lista de matches leyendo la pagina madre de MOSS.
- Cada fila del Excel intenta encontrar su coincidencia exacta en la pagina madre usando nombre del estudiante, paralelo y similitud.
- Si encuentra el match, el campo `url_moss` del caso deja de apuntar al padre y pasa a apuntar al `matchN.html` correcto.
- Si no puede resolver un match especifico, mantiene como respaldo el link padre.
- Para alumnos repetidos, se conserva el primer paralelo encontrado en la pagina madre y se reutiliza ese valor.

Datos nuevos que devuelve el procesador:

- `url_padre_moss`: link padre original del reporte.
- `matches_encontrados`: total de filas de match leidas desde la pagina madre.
- `primer_paralelo_por_estudiante`: mapa con el primer paralelo detectado para cada alumno.

### 2. `app/blueprints/reporte.py`

Se ajusto el endpoint de carga normal y el endpoint de debug para trabajar con el nuevo procesador.

Cambios en la carga de reportes:

- Se agrego una cache de estudiantes para que un mismo alumno no se vuelva a crear o reasignar innecesariamente.
- La funcion `obtener_o_crear_estudiante` ahora usa una cache por rol o por nombre completo para evitar sobrescrituras entre casos repetidos.
- Si el mismo estudiante aparece dos veces en un caso, no se vuelve a agregar dos veces al mismo caso.
- `url_global_moss` ahora sale del link padre real extraido por el procesador, no del primer caso procesado.

Cambios en el endpoint de debug:

- El endpoint `debug_upload_moss` ahora puede trabajar de dos maneras:
  - con `GET`, usando el archivo local `utils/moss.xlsx`
  - con `POST`, recibiendo un archivo subido en el campo `file`
- El debug lee el archivo en modo crudo para que el procesador pueda detectar correctamente la fila de encabezados.
- La respuesta ahora incluye un resumen practico por caso, no solo el objeto completo de salida.
- Se agregaron campos de inspeccion para revisar rapidamente el comportamiento del parser.

Campos que devuelve el debug ahora:

- `archivo_procesado`
- `ruta_archivo`
- `procesamiento_exitoso`
- `errores_procesamiento`
- `url_padre_moss`
- `matches_encontrados`
- `primer_paralelo_por_estudiante`
- `resumen_casos`
- `datos_procesados`

## Flujo nuevo de procesamiento MOSS

1. Se lee el workbook de MOSS.
2. Se detecta el URL padre del reporte.
3. Se descarga la pagina madre de MOSS.
4. Se parsean todas las filas de match y se extraen sus URLs `matchN.html`.
5. Se normalizan nombres y paralelos del Excel y de la pagina madre.
6. Cada caso del Excel se cruza contra la fila correcta de la pagina madre.
7. El caso guarda la URL real del match en `url_moss`.
8. Si el alumno aparece repetido en otro paralelo, se conserva el primer paralelo encontrado en la pagina madre.

## Validaciones ejecutadas

Se realizaron estas validaciones despues del cambio:

- Revision de errores en `utils/excel_processor.py` y `app/blueprints/reporte.py`: sin errores.
- Prueba directa sobre `utils/moss.xlsx` con el procesador: 42 casos procesados correctamente.
- Verificacion de que el primer caso ya no apunta al link padre, sino a su match especifico `match57.html`.
- Prueba del endpoint de debug con `GET`: respuesta 200 y resumen correcto.
- Prueba del endpoint de debug con `POST` subiendo el mismo archivo: respuesta 200 y mismo resultado.

## Resultado funcional

Despues de estos cambios:

- Cada caso de plagio queda asociado a su match real dentro de MOSS.
- El link padre sigue disponible como referencia global.
- Los casos repetidos por alumno en mas de un paralelo se resuelven con el primer paralelo observado.
- El endpoint de debug ahora sirve para inspeccion operativa y para pruebas manuales con archivo subido.

## Archivos tocados

- `utils/excel_processor.py`
- `app/blueprints/reporte.py`

## Notas finales

- El workbook `utils/moss.xlsx` ya contiene el link padre actualizado y fue usado como base para validar el cruce.
- La logica nueva esta pensada para ser tolerante a diferencias menores de formato en nombres, paralelos y caracteres especiales.
- Si en el futuro cambia el formato de salida de MOSS, el punto de ajuste principal sera la funcion de parseo de la pagina madre.