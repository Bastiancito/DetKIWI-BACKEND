# Guía para Frontend: selección de endpoints por rol

## Objetivo
Optimizar la carga de datos en el frontend evitando llamadas globales innecesarias para usuarios con `rol_id = 2`.

La idea es simple:
- primero el frontend identifica el `rol_id` del usuario autenticado,
- luego elige si debe llamar un endpoint global o un endpoint filtrado por los recursos que realmente le pertenecen.

Esto reduce cantidad de datos transferidos y evita consultas que el usuario no necesita ver.

## Regla de decisión

- Si `rol_id = 2`:
  - usar endpoints filtrados por el usuario autenticado;
  - no llamar endpoints globales cuando exista una variante equivalente.
- Si `rol_id != 2`:
  - seguir usando los endpoints globales o los que ya existan en la vista actual.

## Endpoints nuevos o variantes pensadas para `rol_id = 2`

### 1) Paralelos del usuario autenticado

`GET /ObtenerParalelosPorUserId`

Devuelve la misma estructura que `GET /ObtenerParalelos`, pero solo con los paralelos en los que está asignado el usuario que hizo la petición.

Respuesta esperada por item:

```json
{
  "paralelo_id": 10,
  "nombre": "INF129_205L",
  "sede_id": 3,
  "sede_nombre": "Sede Central",
  "usuario": {
    "user_id": 353,
    "username": "pedro.toledo",
    "email": "pedro@example.com"
  }
}
```

### 2) Stats de casos por paralelos, filtrado por los paralelos del usuario autenticado

`GET /ObtenerStatsCasosPorParalelosAndEvaluacionIdMisParalelos/<evaluacion_id>`

Devuelve la misma forma de respuesta que el endpoint global de stats por paralelos, pero solo con los paralelos asociados al usuario autenticado.

Ejemplo de salida:

```json
[
  {
    "paralelo": "INF129_205L",
    "paralelo_id": 10,
    "total_casos": 7,
    "total_casos_pendientes": 2,
    "total_casos_resueltos": 5,
    "usuarios_asignados": [
      {
        "user_id": 353,
        "username": "pedro.toledo",
        "email": "pedro@example.com"
      }
    ]
  }
]
```

## Endpoints globales que se deben conservar

Los endpoints globales no se eliminaron; siguen siendo útiles para otros roles o pantallas administrativas.

- `GET /ObtenerParalelos`
- `GET /ObtenerStatsCasosPorParalelosAndEvaluacionId/<evaluacion_id>`

## Lógica recomendada en el frontend

1. Obtener el perfil del usuario autenticado.
2. Leer `rol_id`.
3. Elegir el endpoint según el rol:
   - `rol_id = 2` -> usar las variantes filtradas por el usuario.
   - otro rol -> usar los endpoints globales si la vista lo requiere.
4. Mantener el mismo renderizado de UI, porque las respuestas filtradas conservan la misma forma que las globales.

## Beneficio esperado

- Menos datos transferidos al frontend.
- Menos trabajo de agregación en pantallas que solo necesitan información del usuario.
- Menor dependencia de endpoints globales para usuarios operativos.

## Resumen práctico para implementación

### Si el usuario es `rol_id = 2`
- Paralelos: `GET /ObtenerParalelosPorUserId`
- Stats: `GET /ObtenerStatsCasosPorParalelosAndEvaluacionIdMisParalelos/<evaluacion_id>`

### Si el usuario no es `rol_id = 2`
- Paralelos: `GET /ObtenerParalelos`
- Stats: `GET /ObtenerStatsCasosPorParalelosAndEvaluacionId/<evaluacion_id>`

## Nota importante

El frontend debe decidir la ruta antes de disparar la consulta. La selección por rol debe hacerse una sola vez en la capa de estado o en el servicio API para no duplicar lógica en múltiples componentes.