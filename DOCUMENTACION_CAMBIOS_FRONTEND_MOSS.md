# Documentacion de cambios para Frontend - flujo MOSS

Fecha: 2026-05-22

## Objetivo

Este documento resume los cambios funcionales del flujo de carga de reportes MOSS para que el frontend ajuste sus pantallas, validaciones y lectura de respuestas.

## Resumen de cambios

1. Un caso de plagio ahora puede crearse aunque no tenga usuarios asignados.
2. Un caso puede quedar asociado a mas de un paralelo, porque involucra a dos estudiantes de distintos cursos.
3. Si el upload detecta paralelos nuevos sin encargado, el caso igual se crea y se vincula al paralelo correspondiente.
4. Si el upload detecta casos duplicados exactos, el backend puede responder con `409` para que el frontend pida confirmacion antes de continuar.
5. El frontend ya no debe asumir que la ausencia de usuarios asignados impide la creacion del caso.

## Cambios de modelo y relacionamiento

Ahora existe una relacion directa entre `Caso` y `Paralelo` mediante una tabla interseccion.

Esto permite que:

- un mismo caso aparezca en ambos paralelos involucrados;
- ambos profesores vean el mismo caso desde su paralelo;
- el caso se conserve como una sola entidad de plagio, aunque tenga dos paralelos distintos.

### Impacto para frontend

Cuando el frontend serialice un caso, debe considerar el campo `paralelos` como la fuente oficial de paralelos asociados al caso.

Cada item de `paralelos` incluye al menos:

- `paralelo_id`
- `sigla_paralelo`
- `sede_id`
- `sede_nombre`

## Contrato del upload

Endpoint principal:

- `POST /reportes/upload`

El comportamiento esperado ahora es el siguiente:

### 1. Carga normal exitosa

Respuesta `201`.

Campos relevantes:

- `msg`
- `reporte_id`
- `casos_creados`
- `total_filas_procesadas`
- `paralelos_procesados`
- `paralelos_creados_sin_sede`
- `casos_sin_encargado_count`
- `paralelos_sin_encargado_count`
- `casos_vinculados_a_paralelo_creado_count`
- `advertencias_sin_encargado`
- `advertencias_duplicados`

### 2. Casos sin encargado

Antes esto bloqueaba la carga. Ahora no bloquea la creacion del caso.

El backend devuelve una advertencia en:

- `advertencias_sin_encargado`

Estructura esperada:

- `codigo`: `MOSS_CASES_WITHOUT_ASSIGNED_USERS`
- `msg`: mensaje legible para UI
- `casos_sin_encargado_count`
- `paralelos_sin_encargado_count`
- `casos_sin_encargado`
- `paralelos_sin_encargado`

### 3. Casos vinculados a paralelos creados

Cuando durante el upload se crea un paralelo nuevo, los casos que usan ese paralelo vienen marcados en:

- `casos_vinculados_a_paralelo_creado`

Cada registro incluye:

- `fila_original`
- `similitud`
- `lineas`
- `url_moss`
- `estudiante1`
- `estudiante2`
- `paralelos_vinculados_a_creados`
- `paralelos_sin_encargado`

### 4. Duplicados detectados

Si el backend detecta casos duplicados exactos, puede responder con:

- `409 Conflict`

Respuesta:

- `msg`: texto para mostrar en UI
- `codigo`: `MOSS_DUPLICATE_CASES_DETECTED`
- `requiere_confirmacion`: `true`
- `status_code`: `409`
- `casos_duplicados_count`
- `casos_duplicados`

Si el frontend reintenta con:

- `confirmar_duplicados=true`

el backend omite los duplicados y responde `201`.

## Campos que el frontend debe leer

### En la respuesta de `201`

- `casos_creados`
- `casos_sin_encargado_count`
- `paralelos_sin_encargado_count`
- `casos_vinculados_a_paralelo_creado_count`
- `advertencias_sin_encargado`
- `advertencias_duplicados`

### En la respuesta de `409`

- `codigo`
- `msg`
- `requiere_confirmacion`
- `casos_duplicados_count`
- `casos_duplicados`

## Recomendacion de UI

El frontend puede mostrar tres estados simultaneos en un caso:

- `Creado`: el caso fue creado correctamente.
- `Sin encargado`: el paralelo existe pero aun no tiene usuario asignado.
- `Vinculado a paralelo creado`: el caso usa un paralelo que fue creado en la misma carga.

Esto es importante porque un mismo caso puede tener dos paralelos y cada uno puede estar en una situacion distinta.

## Cambios en listado y detalle de casos

Ahora los endpoints que devuelven casos incluyen tambien la lista `paralelos`.

Esto aplica a:

- listado por reporte
- detalle de caso
- casos por sede
- casos por paralelo

### Uso esperado en frontend

En vez de inferir el paralelo solo desde los estudiantes, el frontend debe tomar `paralelos` como la relacion oficial del caso.

## Escenarios que el frontend debe contemplar

1. Caso con dos paralelos existentes y con usuarios asignados.
2. Caso con un paralelo nuevo sin encargado.
3. Caso con un paralelo existente sin encargado y otro paralelo nuevo.
4. Upload con duplicados detectados y confirmacion pendiente.
5. Upload con duplicados confirmados por el usuario.

## Archivos de referencia

- `app/models.py`
- `app/blueprints/reporte.py`
- `app/blueprints/casos.py`
- `migrations/versions/f2a3b4c5d6e7_add_caso_paralelos.py`

## Nota final

La fuente de verdad para el frontend ahora es:

- `caso.paralelos` para relacion caso-paralelo
- `usuarios_asignados` para saber si el caso ya tiene profesores asignados
- `advertencias_sin_encargado` para casos creados sin profesor
- `advertencias_duplicados` para duplicados omitidos
