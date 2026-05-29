# Cambios backend — instrucciones para Frontend

## Archivos modificados
- [app/models.py](app/models.py)
- [app/blueprints/casos.py](app/blueprints/casos.py)
- [migrations/versions/460d657e178f_add_decisiones_profes_and_comentarios_.py](migrations/versions/460d657e178f_add_decisiones_profes_and_comentarios_.py)
 - [app/blueprints/reporte.py](app/blueprints/reporte.py)

## Resumen general
- Se introduce la columna `decisiones_profes` (JSON) en `Caso` para almacenar decisiones individuales de los profesores: `{ "<user_id>": true|false }`.
- Se añade `comentarios_caso` en `CasoSancionado` para copiar el historial de `comentarios_profes` al momento de crear la sanción (trazabilidad).
 - Se añade el campo `fecha_entrega` (datetime) en `Caso`. Cuando el caso se crea desde la carga de un `Reporte`, el backend establece por defecto `fecha_entrega = ahora + 14 días`.
- Se modificó la lógica del endpoint `PUT /ActualizarEstadoCaso/<caso_id>` (función `marcar_caso_revisado`) para:
  - Buscar el caso únicamente por `caso_id` (no filtrar por usuario que solicita).
  - 1 usuario asignado: su decisión se aplica inmediatamente; el caso se cierra y `sancion` queda con su valor (`true` -> sancionar; `false` -> indultar).
  - 2 o más usuarios asignados: cada usuario puede registrar/actualizar su decisión; el caso solo se cierra cuando **todos los asignados** han votado y **todas las decisiones coinciden**.
  - Si hay desacuerdo o faltan votos, el caso permanece abierto (`closed = false`, `sancion = null`, `in_process = true`) y **solo** se cerrará cuando se alcance consenso.
- Se separó la capacidad de forzar decisiones en endpoints exclusivos para administradores (`rol_id == 1`):
  - `POST /ForzarSancion/<caso_id>` — fuerza `sancion = true` y cierra el caso.
  - `POST /ForzarIndulto/<caso_id>` — fuerza `sancion = false` y cierra el caso.

## Endpoints relevantes y uso esperado

### 1) Registrar/actualizar decisión (votos)
PUT /ActualizarEstadoCaso/<caso_id>
- Body: `{ "sancion": true|false, "descripcion_sancion": "opcional" }`
- Comportamiento:
  - Si `len(usuarios_asignados) <= 1`: la decisión se aplica y el caso queda cerrado.
  - Si `len(usuarios_asignados) >= 2`: se guarda la decisión en `caso.decisiones_profes` y el backend cierra el caso únicamente cuando todos los `usuarios_asignados` voten y coincidan.
  - Los usuarios pueden volver a llamar este endpoint para cambiar su voto; cada cambio re-evalúa el consenso.

Ejemplo request:

```json
PUT /ActualizarEstadoCaso/123
{
  "sancion": true
}
```

Ejemplo de campos de respuesta (cuando el frontend vuelva a pedir el caso):
```json
{
  "caso_id": 123,
  "closed": false,
  "sancion": null,
  "decisiones_profes": { "12": true } // usuario 12 votó, falta el otro
}
```

Cuando hay consenso:
```json
{
  "caso_id": 123,
  "closed": true,
  "sancion": true,
  "decisiones_profes": { "12": true, "34": true }
}
```

### 2) Forzar decisión (solo admin, endpoints nuevos)
POST /ForzarSancion/<caso_id>
- Requiere JWT de usuario con `rol_id == 1`.
- Forza `sancion = true`, cierra el caso, registra el voto del admin en `decisiones_profes` y crea `CasoSancionado` arrastrando `comentarios_profes`.
- Body opcional: `{ "descripcion_sancion": "texto" }`

POST /ForzarIndulto/<caso_id>
- Requiere JWT de usuario con `rol_id == 1`.
- Forza `sancion = false`, cierra el caso y registra el voto del admin en `decisiones_profes`.

Ejemplo request:
```json
POST /ForzarSancion/123
{ "descripcion_sancion": "Sanción por plagio" }
```

Respuesta esperada:
```json
{ "msg": "Sanción forzada correctamente", "caso_id": 123 }
```

## Cambios en respuestas GET que debe usar el frontend
- Los endpoints que retornan casos (p. ej. `GET /ObtenerCasosPorReporteId`, `GET /ObtenerDetalleCaso`, `GET /filtrar`) ahora incluyen la propiedad `decisiones_profes` en cada caso (puede ser `null` si no existe).
- Los endpoints que retornan casos también incluyen `in_process` para que el frontend pueda distinguir entre un caso abierto por desacuerdo/proceso de votación y un caso ya resuelto.
- Mostrar `decisiones_profes` en la UI permite visualizar qué decisión tomó cada profesor y si hay consenso.

- Los endpoints que retornan casos o reportes incluyen ahora `fecha_entrega` en el objeto `caso` (ISO string) cuando existe. Además, el objeto `evaluacion` incluido en respuestas también puede exponer su `fecha_entrega`.

## Reglas de UI recomendadas
- Si `usuarios_asignados.length > 1`, mostrar las decisiones individuales (lectura de `decisiones_profes`) y un estado global:
  - `closed = false`, `sancion = null` y `in_process = true` => mostrar "Pendiente / Desacuerdo" y las decisiones parciales.
  - `closed = true` => mostrar resultado final según `sancion`.
- Permitir a cada profesor cambiar su decisión llamando `PUT /ActualizarEstadoCaso/<caso_id>`.
- Solo usuarios con `rol_id == 1` deben mostrar opciones de "Forzar sanción" o "Forzar indulto" (llaman a los endpoints nuevos).

## Nota sobre endpoint `CambiarDecision`
- El endpoint `POST /CambiarDecision/<caso_id>` fue deshabilitado intencionalmente. Devuelve 405 y un mensaje instructivo.
- El frontend NO debe usar ese endpoint. Use siempre `PUT /ActualizarEstadoCaso/<caso_id>` para registrar o cambiar decisiones individuales.

## Notas técnicas y consideraciones
- `decisiones_profes` almacena claves como strings (ej: `"12"`) — el frontend puede parsearlas a números si necesita comparar con `user_id` numérico.
- `decisiones_profes` puede ser `null`; tratar como `{}`.
- La migración de base de datos fue generada; si replican localmente ejecutar:

```bash
flask db migrate -m "Add decisiones_profes and comentarios_caso"
flask db upgrade
```

Si al aplicar los cambios aún no están presentes las migraciones para `fecha_entrega`, ejecutar:

```bash
flask db migrate -m "Add fecha_entrega to caso"
flask db upgrade
```

### Nuevo endpoint: Aplazar plazo de un caso
POST /caso/<caso_id>/aplazar
- Autenticación: JWT.
- Permisos: usuarios asignados al caso o el creador del reporte (puedes ajustar a admin si lo prefieres).
- Body JSON: `{ "dias": 5 }` (entero positivo)
- Comportamiento: suma `dias` al `caso.fecha_entrega` si existe; si no, establece `fecha_entrega = ahora + dias`.
- Respuesta 200: `{ "caso_id": 123, "fecha_entrega": "2026-06-10T12:34:56.789" }`
- Errores: 400 si `dias` no es entero positivo; 403 si no autorizado; 404 si caso no existe.

Ejemplo fetch:

```js
fetch('/caso/123/aplazar', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer <token>' },
  body: JSON.stringify({ dias: 7 })
})
.then(r => r.json()).then(console.log)
```

---

Si quieres, genero también ejemplos `fetch`/`axios` para integrar el botón de votar y los botones de forzar (admin).