**Cambios para Frontend**

- **Archivos modificados**: 
  - [app/models.py](app/models.py)
  - [app/blueprints/casos.py](app/blueprints/casos.py)
  - [migrations/versions/460d657e178f_add_decisiones_profes_and_comentarios_.py](migrations/versions/460d657e178f_add_decisiones_profes_and_comentarios_.py)

- **Resumen de cambios**:
  - **`app/models.py`**: se agregaron dos columnas:
    - `decisiones_profes` (JSON) en `Caso`: almacena un mapa {"<user_id>": true|false} con la decisión individual de cada profesor.
    - `comentarios_caso` (JSON) en `CasoSancionado`: guarda todo el historial de `comentarios_profes` del caso al momento de sancionar para trazabilidad.
  - **`app/blueprints/casos.py`**:
    - Se extienden las respuestas de los endpoints para incluir `decisiones_profes` en la serialización de casos (p. ej. en `ObtenerCasosPorReporteId`, `ObtenerDetalleCaso`, `filtrar`).
    - Se actualiza la lógica de `ActualizarEstadoCaso` (endpoint `/ActualizarEstadoCaso/<caso_id>`) para soportar:
      - Votación por usuario: cada usuario asignado puede registrar su decisión (True = sancionar, False = indultar) y actualizarla posteriormente.
      - Consenso: si hay más de un `usuarios_asignados`, el caso solo se cierra cuando todos los asignados han votado y todas las decisiones coinciden (todos True = sancionar; todos False = indultar).
      - Desacuerdo: si las decisiones difieren, el caso permanece abierto/pending (`caso.closed` = False y `caso.sancion` = null/None) y el frontend debe mostrar el estado de desacuerdo y las decisiones individuales.
      - Cuando el caso se cierra con sanción (consenso True), se crea un `CasoSancionado` que arrastra `comentarios_profes` del caso a `comentarios_caso` dentro de la sanción para asegurar trazabilidad completa.

- **Formato esperado por el frontend**:
  - `decisiones_profes`: objeto JSON con keys como `"<user_id>"` (string) y valores booleanos. Ejemplo:

```json
"decisiones_profes": {
  "12": true,
  "34": true
}
```

  - Estado del caso:
    - `closed`: boolean
    - `sancion`: true|false|null (null cuando hay desacuerdo)

- **Comportamiento UI recomendado**:
  - Si `usuarios_asignados.length > 1` mostrar las decisiones individuales (leer `decisiones_profes`) y un indicador de consenso/ desacuerdo.
  - Botón de votación para cada profesor asignado que llame a `PUT /ActualizarEstadoCaso/<caso_id>` enviando `{ "sancion": true|false }`. El backend actualizará `decisiones_profes` y retornará el estado actualizado del caso.
  - Cuando `closed = true` y `sancion = true`, mostrar los detalles de la sanción y el historial de comentarios (usar `CasoSancionado.comentarios_caso`).

- **Notas de backend / operaciones de despliegue**:
  - Se generó y aplicó una migración Alembic. Para replicarlo localmente ejecutar:

```bash
flask db migrate -m "Add decisiones_profes and comentarios_caso"
flask db upgrade
```

- **Puntos importantes para el frontend**:
  - `decisiones_profes` puede no existir (null) — tratar como `{}`.
  - Las keys en `decisiones_profes` vienen como strings; conviértalas a números si necesita compararlas con `user_id` numéricos.
  - Mostrar claramente cuando hay "Desacuerdo" y permitir a los usuarios cambiar su propia decisión.

Si quieres, puedo:
- Ejecutar pruebas rápidas del endpoint y mostrar ejemplos de respuestas JSON.
- Preparar snippets de llamadas `fetch`/`axios` para el frontend.
