# Guía para Frontend: sanción, indulto y cancelación trazable

## Objetivo
Documentar el comportamiento actual del backend para que el frontend maneje correctamente:
- la votación de un caso,
- el cambio de decisión de un profesor,
- la reversión de una sanción a indulto,
- y la trazabilidad histórica de sanciones sin borrar registros.

La regla principal es esta:
- **no se eliminan sanciones físicamente**,
- cuando una sanción se revierte, se marca como **cancelada**,
- y además se ajusta el contador `num_sanciones` de los estudiantes involucrados.

---

## Estado funcional actual

### 1) Casos con un solo usuario asignado

Si un caso tiene `usuarios_asignados.length <= 1`:
- la decisión se aplica de forma directa,
- el caso queda cerrado,
- `sancion = true` significa sancionado,
- `sancion = false` significa indultado,
- si luego el usuario cambia su decisión, el backend la sobrescribe.

### 2) Casos con más de un usuario asignado

Si un caso tiene `usuarios_asignados.length > 1`:
- cada usuario asignado puede votar con `PUT /ActualizarEstadoCaso/<caso_id>`,
- el backend guarda cada voto en `decisiones_profes`,
- el caso solo se cierra cuando todos los asignados han votado y todos coinciden,
- si hay desacuerdo, el caso queda abierto y `sancion = null`.

### 3) Cambio de decisión

Un mismo usuario puede cambiar su voto llamando nuevamente al mismo endpoint:
- si votó sanción, luego puede votar indulto,
- si votó indulto, luego puede votar sanción.

El backend recalcula el estado del caso con el nuevo voto.

### 4) Reversión de una sanción ya aplicada

Cuando una sanción se revierte:
- la sanción histórica no se borra,
- se marca como `cancelado = true`,
- se guarda `fecha_cancelacion`,
- se guarda `cancelado_por`,
- el caso vuelve a `sancion = false`,
- y se descuenta `num_sanciones` a los estudiantes involucrados.

---

## Campos nuevos o relevantes

### En `Caso`

- `decisiones_profes`: objeto JSON con el voto de cada usuario asignado.
- `closed`: indica si el caso está cerrado.
- `in_process`: indica si sigue en evaluación o desacuerdo.
- `sancion`: puede ser `true`, `false` o `null`.

### En `CasoSancionado`

- `cancelado`: booleano que indica si la sanción fue revertida.
- `fecha_cancelacion`: fecha/hora en que se canceló.
- `cancelado_por`: `user_id` del usuario que ejecutó la cancelación.
- `comentarios_caso`: copia del historial de comentarios del caso al momento de sancionar.

---

## Endpoints relevantes

### 1) Registrar o actualizar voto del caso

`PUT /ActualizarEstadoCaso/<caso_id>`

Body esperado:

```json
{
  "sancion": true,
  "descripcion_sancion": "opcional",
  "reason": "opcional"
}
```

Comportamiento:
- `sancion: true` => votar a favor de sancionar.
- `sancion: false` => votar a favor de indultar.
- El usuario autenticado siempre reemplaza su voto anterior.

Resultado posible en la respuesta del caso:

```json
{
  "closed": false,
  "in_process": true,
  "sancion": null,
  "decisiones_profes": {
    "12": true,
    "34": false
  }
}
```

### 2) Forzar sanción

`POST /ForzarSancion/<caso_id>`

Uso:
- solo coordinadores o administradores,
- fuerza `sancion = true`,
- cierra el caso,
- crea o reactiva una sanción activa.

Body opcional:

```json
{
  "reason": "texto",
  "descripcion_sancion": "Amonestación por plagio"
}
```

### 3) Forzar indulto

`POST /ForzarIndulto/<caso_id>`

Uso:
- solo coordinadores o administradores,
- fuerza `sancion = false`,
- cierra el caso,
- cancela sanciones activas relacionadas con ese caso.

### 4) Obtener sanciones

`GET /casos_sancionados/ObtenerCasosSancionados`

Opcionalmente:
- `?caso_id=<id>`
- `?solo_activas=true`

La respuesta ahora incluye:
- `cancelado`
- `fecha_cancelacion`
- `cancelado_por`

### 5) Cancelar sanción de forma explícita

`DELETE /casos_sancionados/EliminarCasoSancionado/<sancion_id>`

Importante:
- ya no debe tratarse como un borrado físico desde la UI,
- el backend la convierte en una cancelación trazable,
- conserva el registro histórico.

---

## Reglas de UI recomendadas

### Para casos con un solo usuario asignado

- Permitir votar sanción o indulto normalmente.
- Si ya hay sanción, mostrar opción para revertir a indulto.
- Si cambia a indulto, el frontend debe refrescar el detalle del caso y la lista de sanciones.

### Para casos con varios usuarios asignados

- Mostrar el estado de cada usuario en `decisiones_profes`.
- Permitir que cada usuario cambie su propia decisión.
- Si hay desacuerdo, mostrar estado "En proceso" o "Pendiente de consenso".
- Si todos coinciden, mostrar el resultado final.

### Para sanciones revertidas

- Mostrar claramente que la sanción está `cancelado = true`.
- No ocultar el registro.
- Diferenciar entre:
  - sanción activa,
  - sanción cancelada,
  - caso indultado sin sanción activa.

---

## Efecto sobre `num_sanciones`

Cuando una sanción se cancela:
- el contador de sanciones de los estudiantes involucrados se descuenta en 1,
- nunca debe quedar por debajo de 0.

Esto aplica tanto si:
- el cambio ocurre por votación del usuario,
- como si ocurre por forzado desde un rol administrativo.

---

## Recomendación para el frontend

Después de cualquier acción de voto o cambio de estado:
- volver a pedir el detalle del caso,
- volver a pedir las sanciones relacionadas,
- y refrescar el contador visible de sanciones si la vista lo muestra.

Así se evita mostrar un estado intermedio desfasado respecto del backend.

---

## Resumen corto para integración

- Un profesor puede cambiar su voto.
- Un caso con varios revisores requiere consenso.
- Una sanción revertida no se elimina: se marca como cancelada.
- Al cancelar una sanción, también se descuenta el contador de sanciones del estudiante.
- El frontend debe mostrar `cancelado`, `fecha_cancelacion` y `cancelado_por` cuando consulte sanciones.

---

Si quieres, este documento se puede complementar con ejemplos de `fetch`/`axios` para los botones de:
- votar sanción,
- votar indulto,
- cancelar sanción,
- y refrescar la vista luego del cambio.
