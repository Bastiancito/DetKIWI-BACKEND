# Estado del trabajo MOSS y pendientes

Fecha: 2026-05-22

## Resumen rapido

Se trabajo el flujo de carga de reportes MOSS para que:

- el caso se cree aunque no tenga usuarios asignados;
- el caso quede asociado a los paralelos de los dos estudiantes involucrados;
- un mismo caso pueda aparecer en mas de un paralelo;
- los paralelos nuevos puedan quedar sin encargado, pero el caso nunca quede huérfano de paralelo;
- el frontend reciba mas contexto en los responses para poder mostrar estados y advertencias.

Ademas, se agregaron logs en el endpoint de upload para rastrear la creacion de cada caso y sus relaciones.

## Lo que ya quedo implementado

### 1. Relacion Caso-Paralelo

En `app/models.py` se agrego una tabla interseccion nueva:

- `caso_paralelos`

Y se dejo la relacion bidireccional:

- `Caso.paralelos`
- `Paralelo.casos_asociados`

Esto permite que un caso se vea desde ambos paralelos involucrados.

### 2. Migracion nueva

Se creo la migracion:

- `migrations/versions/f2a3b4c5d6e7_add_caso_paralelos.py`

Esta crea la tabla `caso_paralelos`.

### 3. Upload de MOSS

En `app/blueprints/reporte.py` se ajusto el flujo de carga para que:

- se creen los casos aunque no tengan usuarios asignados;
- cada caso se vincule a los paralelos de `estudiante1` y `estudiante2`;
- se sigan creando estudiantes y paralelos nuevos cuando haga falta;
- se detecten y reporten casos duplicados;
- se reporten casos sin encargado sin bloquear la creacion;
- se devuelva un detalle de casos creados en `casos_creados_detalle`;
- se agreguen logs de trazabilidad.

### 4. Logs en upload

Se agregaron logs en el upload para poder revisar:

- inicio de la carga;
- resultado del parseo;
- deduplicacion;
- paralelos existentes y paralelos a crear;
- cada caso creado con su `caso_id`, estudiantes, paralelos y usuarios asignados;
- commit final.

### 5. Endpoints de consulta

Se actualizo `app/blueprints/casos.py` para que los endpoints devuelvan tambien `paralelos`.

Se actualizo `app/blueprints/evaluaciones.py` para que:

- `GET /api/evaluaciones/ObtenerCasosPorEvaluacionId/<id>` devuelva `paralelos` por caso;
- el frontend no dependa solo de `estudiantes` o `usuarios_asignados`.

### 6. Limpieza de datos

En `app/blueprints/admin.py` se ajustaron los endpoints de limpieza para contemplar:

- `caso_paralelos`
- `caso_estudiantes`
- `caso_usuarios`
- `user_paralelos`

Esto evita errores de FK al limpiar casos o paralelos.

### 7. Documentacion para frontend

Se creo el archivo:

- `DOCUMENTACION_CAMBIOS_FRONTEND_MOSS.md`

Ese documento resume el contrato que frontend debe considerar.

## Estado actual del problema

El endpoint `GET /api/evaluaciones/ObtenerCasosPorEvaluacionId/2` ya fue ajustado para devolver `paralelos`, pero todavia hay que confirmar en ejecucion real que:

- los casos de Angel Liz y similares efectivamente se persisten en BD;
- el frontend esta leyendo el campo `paralelos` y no solo `estudiantes`;
- el frontend esta mostrando el response completo del endpoint correcto.

## Pendientes

### Backend

- Verificar en logs reales del container que el upload esta creando cada caso y vinculando ambos paralelos.
- Confirmar que `casos_creados_detalle` contiene los casos esperados.
- Revisar si hace falta un campo extra de estado por caso en el response del upload para simplificar la UI.

### Base de datos

- Ejecutar la migracion nueva en el entorno real con `flask db upgrade`.
- Confirmar que la tabla `caso_paralelos` existe en la base de datos real.

### Frontend

- Ajustar la vista de "Casos sin encargado" para que no sea la unica fuente de verdad.
- Leer `paralelos` desde los endpoints de casos y evaluaciones.
- Leer `casos_creados_detalle` si se quiere mostrar el resultado completo del upload.
- Mostrar correctamente el estado combinado:
  - caso creado
  - paralelo creado
  - paralelo sin encargado

### Validacion funcional

- Hacer un upload real con el archivo MOSS que contiene Angel Liz.
- Confirmar en BD que existe el caso con sus paralelos asociados.
- Confirmar en la respuesta de `ObtenerCasosPorEvaluacionId` que aparece el caso con `paralelos`.
- Confirmar que no se repiten casos por duplicados del mismo par.

## Archivos clave

- `app/models.py`
- `app/blueprints/reporte.py`
- `app/blueprints/casos.py`
- `app/blueprints/evaluaciones.py`
- `app/blueprints/admin.py`
- `migrations/versions/f2a3b4c5d6e7_add_caso_paralelos.py`
- `DOCUMENTACION_CAMBIOS_FRONTEND_MOSS.md`

## Comando util para retomar

```bash
docker-compose exec web flask db upgrade
```

## Nota de contexto

El objetivo funcional final es este:

- un caso de plagio siempre debe existir si fue detectado;
- el caso debe quedar asociado a los paralelos correspondientes;
- si un paralelo queda sin encargado, eso se resuelve despues asignando un usuario a ese paralelo;
- el frontend debe mostrar el caso aunque el paralelo no tenga profesor asignado.
