**Integración Frontend — Sanciones y Motivos (Trazabilidad)**

Este documento explica cómo el frontend debe interactuar con el backend para:
- permitir que cada usuario deje su propia razón de sanción (mapping por usuario),
- crear/reactivar/cancelar sanciones sin perder trazabilidad,
- prellenar el modal de detalles con la razón pendiente o la sanción activa.

**Endpoints principales**

- Obtener detalle de caso (prefill)
  - GET /casos/ObtenerDetalleCaso/<casoId>
  - Response (relevante):
    - `motivo_sancion`: objeto JSON pendiente en `Caso` (mapping por usuario) or null
    - `reason`: el mapping efectivo (objeto) si hay sanción activa o motivo pendiente
    - `descripcion_sancion`: string sintetizado (primera descripción encontrada)
    - `in_process`, `sancion`, `decisiones_profes`, etc.

- Sancionar (nuevo endpoint)
  - POST /casos/SancionarCaso/<casoId>
  - Body examples (preferible mapping):
    - Enviar mapping por usuario:
      {
        "reason": { "123": { "motivo": "Copia parcial", "descripcion": "Texto copiado sin citación" } }
      }
    - Forma legacy (scalar + descripcion):
      {
        "reason": "Copia parcial",
        "descripcion_sancion": "Texto copiado sin citación"
      }
  - Behavior: para 1 asignado o consenso crea/reactiva `CasoSancionado` y almacena/mezcla el mapping; devuelve 200 con mensaje.

- Indultar (nuevo endpoint)
  - POST /casos/IndultarCaso/<casoId>
  - Body: igual estructura que `SancionarCaso`.
  - Behavior: registra voto de indulto; si aplica cancela sanciones activas y decrementa `Estudiante.num_sanciones`.

- Cambiar opinión (nuevo endpoint)
  - POST /casos/CambiarOpinion/<casoId>
  - Body:
    {
      "sancion": true|false,
      "reason": {...} (optional),
      "descripcion_sancion": "..." (optional)
    }
  - Nota: solo válido mientras `caso.in_process` === true. Si el usuario cambia a `false` (indulto) y existe una sanción activa, ésta se cancela inmediatamente.

- (Legacy) Actualizar estado
  - PUT /casos/ActualizarEstadoCaso/<casoId>
  - Sigue existiendo; hemos mantenido compatibilidad, pero preferimos usar los endpoints nuevos por claridad.

**Formato `reason` (recomendado)**
- `reason` es un objeto donde la clave es `userId` (como string) y el valor es:
  { "motivo": string, "descripcion": string }
- Ejemplo completo:
  {
    "reason": {
      "123": { "motivo": "Copia parcial", "descripcion": "Se detectó 30% de coincidencia" },
      "456": { "motivo": "Copia completa", "descripcion": "Coincidencia exacta" }
    }
  }
- Si el frontend sólo permite que el usuario actual escriba su razón, enviar el mapping con la clave de ese usuario.
- También se acepta la forma legacy (scalar `reason` + `descripcion_sancion`) para compatibilidad.

**Prefill del modal DetallesCaso**
1. Llamar `GET /casos/ObtenerDetalleCaso/<id>` al abrir el modal.
2. Si `response.data.reason` es un objeto:
   - Si existe `response.data.reason[myUserId]`, prefill `motivo` y `descripcion` con los campos `motivo`/`descripcion`.
   - Si no existe clave para `myUserId`, el campo público puede quedar vacío (pero mostrar `descripcion_sancion` como hint si existe).
3. Si `response.data.descripcion_sancion` existe y `reason` no contiene entrada para el usuario, usarla como `descripcion` prefill.
4. Si `response.data.motivo_sancion` existe (campo pendiente en `Caso`), también puede contener un mapping; úsalo preferentemente como `reason` cuando no haya sanción activa.

**Flujos UI sugeridos**
- Votar sanción:
  1. Usuario rellena motivo/descripcion en modal.
  2. Llamar `POST /casos/SancionarCaso/<casoId>` con `reason` mapping para el usuario actual.
  3. Al recibir 200: refrescar detalle del caso (GET) y actualizar lista/UI.

- Votar indulto:
  1. (Opcional) permitir explicación; llamar `POST /casos/IndultarCaso/<casoId>`.
  2. Al recibir 200: refrescar detalle del caso.

- Cambiar opinión mientras `in_process`:
  1. Llamar `POST /casos/CambiarOpinion/<casoId>` con `sancion` boolean y `reason` si se desea actualizar la explicación.
  2. Si la acción canceló una sanción activa, el backend responderá con 200 y la UI debe refrescar.

**Ejemplos con axios (frontend)**

- Prefill:

```javascript
const { data } = await axios.get(`/casos/ObtenerDetalleCaso/${casoId}`)
const reason = data.reason || data.motivo_sancion
const descripcion = data.descripcion_sancion || ''
const myEntry = reason && reason[String(myUserId)]
const prefillMotivo = myEntry ? myEntry.motivo : ''
const prefillDescripcion = myEntry ? myEntry.descripcion : descripcion
```

- Enviar sanción (usuario actual sólo):

```javascript
const payload = {
  reason: {
    [String(myUserId)]: { motivo: selectedMotivo, descripcion: descripcionText }
  }
}
await axios.post(`/casos/SancionarCaso/${casoId}`, payload)
// luego refrescar detalle
```

- Enviar indulto:

```javascript
await axios.post(`/casos/IndultarCaso/${casoId}`, { reason: { [String(myUserId)]: { motivo: 'Indulto', descripcion: '...' } } })
```

- Cambiar opinión mientras en proceso:

```javascript
await axios.post(`/casos/CambiarOpinion/${casoId}`, { sancion: false, descripcion_sancion: 'Cambio de opinión', reason: 'Creo que es indulto' })
```

**Respuestas y errores**
- Éxitos: HTTP 200 (mensajes de confirmación). Algunos endpoints usan 201 en creación de sanción directa en otros archivos; en nuestros endpoints nuevos se usa 200.
- Bad request: 400 (payload mal formado), 403 (sin permisos), 404 (caso no encontrado), 500 (error servidor).
- Recomendación: mostrar mensajes de user-friendly con `error.response.data.msg` y loggear `error.response.data.error` para debugging.

**Notas de implementación y compatibilidad**
- El backend guarda `CasoSancionado.reason` como JSON mapping por usuario. Evitar enviar sólo strings cuando se requiere conservación por usuario.
- Cuando el frontend manda una razón, el backend fusiona esa razón con cualquier `caso.motivo_sancion` pendiente y con `CasoSancionado.reason` existente.
- Al cancelar (indulto), los contadores `Estudiante.num_sanciones` se decrementan automáticamente en backend; refrescar la vista de estudiante si se muestra ese dato.
- Si tu UI usa listas que no requieren `motivo_sancion`, no es necesario cambiarlas; pero para el modal de detalle usa `reason`/`descripcion_sancion` para prefill.

---
Archivo creado: DELIVERABLES/frontend_integration_sanciones.md

Si quieres, actualizo `DetallesCaso.tsx` ahora con el código de prefill y los llamados a los endpoints nuevos.