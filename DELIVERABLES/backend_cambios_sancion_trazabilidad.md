# Cambios de backend: persistencia previa del motivo y trazabilidad de sanciones

## Objetivo
Documentar los cambios necesarios en el backend para que:
- el motivo y la descripción de una posible sanción queden persistidos en `Caso` mientras el caso sigue en deliberación,
- esa información sobreviva hasta que se cree el objeto `CasoSancionado`,
- y las sanciones puedan cancelarse sin perder trazabilidad histórica.

---

## Resumen de la solución

Se incorporó un campo temporal de trabajo en `Caso`:

- `motivo_sancion` (`JSON`)

Este campo guarda la propuesta de sanción mientras el caso todavía no genera un registro formal en `CasoSancionado`.

Cuando finalmente se crea o reactiva una sanción:
- el backend consume el valor de `Caso.motivo_sancion`,
- lo persiste en `CasoSancionado.reason`,
- y limpia `Caso.motivo_sancion` para evitar duplicidad.

Además:
- las sanciones ya no se eliminan físicamente,
- se cancelan con metadatos trazables,
- y el contador `num_sanciones` de los estudiantes involucrados se descuenta al revertir la sanción.

---

## Cambios en el modelo

### `Caso`

Se agrega:

- `motivo_sancion = db.Column(db.JSON, nullable=True)`

Uso esperado:
- guardar el motivo/descripcion propuesto antes de crear `CasoSancionado`,
- mantener la información mientras el caso está en proceso,
- limpiar el campo cuando la sanción ya quedó formalmente creada.

### `CasoSancionado`

Se mantiene `reason` como `JSON`, con una estructura por usuario, por ejemplo:

```json
{
  "12": {
    "motivo": "Se detectó uso de inteligencia artificial",
    "descripcion": "Se detectó uso de inteligencia artificial"
  }
}
```

Además se conservan los campos de trazabilidad:
- `cancelado`
- `fecha_cancelacion`
- `cancelado_por`

---

## Flujo funcional esperado

### 1) Un usuario vota sanción o indulto

`PUT /ActualizarEstadoCaso/<caso_id>`

Body esperado:

```json
{
  "sancion": true,
  "reason": "Se detectó uso de inteligencia artificial",
  "descripcion_sancion": "Se detectó uso de inteligencia artificial"
}
```

El backend:
- guarda el voto en `decisiones_profes`,
- si el caso aún no genera `CasoSancionado`, almacena el motivo en `Caso.motivo_sancion`,
- si más tarde se crea la sanción, ese valor se copia a `CasoSancionado.reason`.

### 2) El caso alcanza consenso y se crea la sanción

Cuando todos los revisores coinciden:
- `Caso.sancion` se establece en `true` o `false`,
- si es `true`, se crea o reactiva `CasoSancionado`,
- `Caso.motivo_sancion` se consume y se limpia.

### 3) Un usuario cambia su voto a indulto

Si un caso con sanción activa pasa a indulto:
- la sanción se marca como `cancelado = true`,
- se registran `fecha_cancelacion` y `cancelado_por`,
- se descuenta `num_sanciones` a los estudiantes involucrados,
- `Caso.decisiones_profes` se limpia para permitir una nueva deliberación.

---

## Endpoints que deben considerar este comportamiento

### `PUT /ActualizarEstadoCaso/<caso_id>`

Debe:
- aceptar `reason` como string o como objeto JSON,
- aceptar `descripcion_sancion` como compatibilidad hacia atrás,
- persistir la propuesta en `Caso.motivo_sancion` mientras no exista sanción formal,
- consumir ese valor al crear `CasoSancionado`.

### `POST /ForzarSancion/<caso_id>`

Debe:
- crear o reactivar la sanción,
- usar `Caso.motivo_sancion` si ya existe un motivo pendiente,
- limpiar `Caso.motivo_sancion` al finalizar.

### `POST /ForzarIndulto/<caso_id>`

Debe:
- cancelar sanciones activas,
- limpiar el estado de deliberación del caso,
- descontar el contador de sanciones cuando corresponda.

### `POST /casos_sancionados/CrearCasoSancionado`

Debe:
- aceptar `reason` como mapping o como valor legacy,
- si no llega `reason`, tomar `Caso.motivo_sancion` como respaldo,
- limpiar `Caso.motivo_sancion` después de crear la sanción.

### `PUT /casos_sancionados/ActualizarCasoSancionado/<sancion_id>`

Debe:
- permitir mantener compatibilidad con payloads antiguos,
- seguir exponiendo `descripcion_sancion` de forma sintetizada cuando el frontend la necesite.

### `DELETE /casos_sancionados/EliminarCasoSancionado/<sancion_id>`

Importante:
- no se recomienda borrado físico,
- debe tratarse como cancelación trazable,
- el historial debe permanecer disponible para auditoría.

---

## Migraciones requeridas

### 1) Agregar `motivo_sancion` a `caso`

Ejemplo Alembic:

```py
with op.batch_alter_table('caso', schema=None) as batch_op:
    batch_op.add_column(sa.Column('motivo_sancion', sa.JSON(), nullable=True))
```

### 2) Asegurar compatibilidad con sanciones existentes

Si hay sanciones históricas, verificar que:
- `CasoSancionado.reason` siga siendo compatible con registros previos,
- los valores antiguos puedan serializarse sin romper el frontend.

### 3) Si se usa una migración de cancelación

Asegurar que la tabla `caso_sancionado` tenga:
- `cancelado`
- `fecha_cancelacion`
- `cancelado_por`

---

## Consideraciones de implementación

### Persistencia previa del motivo

La clave del cambio es que el motivo ya no debe vivir solo en el request o en el objeto sancionado final.

Mientras el caso sigue abierto o en desacuerdo:
- `Caso.motivo_sancion` guarda la información temporal,
- el frontend puede volver a consultarla para prellenar el modal,
- y no se pierde si la sanción aún no se materializa.

### Compatibilidad hacia atrás

Para no romper consumidores antiguos:
- seguir aceptando `descripcion_sancion` como campo legacy,
- aceptar `reason` como string o como objeto JSON,
- y, si es necesario, seguir exponiendo `descripcion_sancion` en las respuestas como valor sintetizado.

### Trazabilidad

No borrar sanciones es importante para:
- auditoría,
- historial de revisiones,
- seguimiento de cambios de decisión,
- y conteo correcto de sanciones por estudiante.

---

## Reglas funcionales esperadas

- Un caso puede tener motivo pendiente antes de generar sanción formal.
- Ese motivo debe persistir en `Caso`.
- Una vez creada la sanción, el motivo se traspasa a `CasoSancionado`.
- Si se cancela una sanción, no se elimina el registro.
- Al cancelar, se revierte también el impacto en `num_sanciones`.

---

## Orden recomendado de despliegue

1. Aplicar migraciones de base de datos.
2. Desplegar el backend con los cambios de modelo y endpoints.
3. Ajustar el frontend para leer `motivo_sancion`, `cancelado` y la serialización nueva de `reason`.

---

## Resultado esperado

Con este flujo:
- el motivo y la descripción de la sanción quedan persistidos hasta que exista `CasoSancionado`,
- el historial no se pierde,
- y las reversions quedan registradas de forma consistente.
