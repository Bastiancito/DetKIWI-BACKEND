# 🚀 Comandos para Actualización de Base de Datos

## ⚠️ Antes de Comenzar

**IMPORTANTE:** Estos cambios modifican la estructura de la base de datos. Se recomienda hacer un backup antes de proceder.

### Backup de PostgreSQL (Opcional pero Recomendado)
```bash
# Con Docker Compose
docker-compose exec db pg_dump -U kiwi_user kiwi_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Restaurar si algo sale mal
docker-compose exec -T db psql -U kiwi_user kiwi_db < backup_YYYYMMDD_HHMMSS.sql
```

---

## 📋 Estructura Actual de la Base de Datos

### Tablas Principales:
1. **Periodo** - Periodos académicos (semestres)
2. **Evaluacion** - Evaluaciones dentro de periodos
3. **Reporte** - Reportes MOSS por evaluación
4. **Caso** - Casos individuales de similitud
5. **Estudiante** - Estudiantes involucrados
6. **User** - Usuarios del sistema
7. **Paralelo** - Paralelos/secciones
8. **Sede** - Sedes de la universidad
9. **Rol** - Roles de usuarios

### Tablas de Relación (Many-to-Many):
1. **caso_estudiantes** - Relación Caso ↔ Estudiante
2. **caso_usuarios** - Relación Caso ↔ User (múltiples profesores por caso)
3. **user_paralelos** - Relación User ↔ Paralelo

---

## 🔄 Verificar Estado de Migraciones

```bash
# Activar entorno virtual (si no está activado)
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Ver migración actual
flask db current

# Ver historial completo de migraciones
flask db history

# Ver migraciones pendientes
flask db history --verbose
```

---

## 📝 Crear Nueva Migración (Si se modifican modelos)

```bash
# Generar migración automáticamente basada en cambios en models.py
flask db migrate -m "Descripción del cambio"

# Ejemplo:
flask db migrate -m "agregar campo nuevo_campo a tabla caso"

# Revisar el archivo de migración generado en:
# migrations/versions/XXXXX_descripcion_del_cambio.py

# Aplicar la migración
flask db upgrade
```

---

## ⬆️ Aplicar Migraciones Pendientes

```bash
# Aplicar todas las migraciones pendientes
flask db upgrade

# Aplicar hasta una migración específica
flask db upgrade <revision_id>

# Ver qué cambiará antes de aplicar (dry-run)
flask db upgrade --sql
```

---

## ⬇️ Revertir Migraciones (Rollback)

```bash
# Revertir a la migración anterior
flask db downgrade

# Revertir a una migración específica
flask db downgrade <revision_id>

# Revertir todo (CUIDADO!)
flask db downgrade base

# Ver SQL que se ejecutará sin aplicar cambios
flask db downgrade --sql
```

---

## 🆕 Estructura de Datos Actualizada

### Modelo Caso (Actualizado)
```python
class Caso(db.Model):
    caso_id: int (PK)
    reporte_id: int (FK → Reporte)
    evaluacion_id: int (FK → Evaluacion) # ⭐ CAMPO DIRECTO para eficiencia
    similitud: float
    lineas: int (nullable)
    url_moss: str
    closed: bool (default: False)
    sancion: bool (nullable)
    caso_metadata: JSON (nullable)
    
    # Relaciones Many-to-Many
    involucrados: [Estudiante] via caso_estudiantes
    usuarios_asignados: [User] via caso_usuarios
```

**Cambios Importantes:**
- ✅ `evaluacion_id` agregado como FK directo para consultas eficientes
- ✅ `closed` y `sancion` para estado de revisión
- ✅ `caso_metadata` para información adicional flexible
- ✅ `usuarios_asignados` permite múltiples profesores por caso

---

## 🔧 Comandos de Desarrollo

### Verificar Conexión a la BD
```bash
# Con Docker
docker-compose exec db psql -U kiwi_user kiwi_db

# Comandos útiles en PostgreSQL:
\dt                    # Listar tablas
\d tabla               # Ver estructura de tabla
\d+ caso               # Ver tabla 'caso' con detalles
SELECT COUNT(*) FROM caso;  # Contar registros
\q                     # Salir
```

### Reiniciar Base de Datos Completa
```bash
# CUIDADO: Borra toda la base de datos
docker-compose down -v
docker-compose up -d
flask db upgrade
```

### Poblar Datos Iniciales
```bash
# Si tienes un script de seed data
python seed_data.py

# O manualmente vía API:
# 1. Crear periodo activo
# 2. Crear evaluación
# 3. Subir reporte MOSS
```

---

## 🐛 Solución de Problemas

### Error: "Can't locate revision identified by 'XXXX'"
```bash
# La BD está desincronizada con las migraciones
# Solución: Estampar revisión actual
flask db stamp head
```

### Error: "Target database is not up to date"
```bash
# Hay migraciones pendientes
flask db upgrade
```

### Error: "FOREIGN KEY constraint failed"
```bash
# Hay datos huérfanos. Opciones:
# 1. Limpiar datos huérfanos manualmente
# 2. Recrear BD desde cero
docker-compose down -v && docker-compose up -d && flask db upgrade
```

### La migración falla a mitad de ejecución
```bash
# Revertir cambios parciales
flask db downgrade
# Corregir el archivo de migración en migrations/versions/
# Volver a aplicar
flask db upgrade
```

---

## 📊 Consultas Útiles

```sql
-- Ver todos los periodos
SELECT * FROM periodo ORDER BY anio DESC, semestre DESC;

-- Ver evaluaciones con sus periodos
SELECT e.nombre, p.nombre as periodo 
FROM evaluacion e 
JOIN periodo p ON e.periodo_id = p.periodo_id;

-- Ver casos con evaluación directa
SELECT c.caso_id, c.similitud, e.nombre as evaluacion
FROM caso c
JOIN evaluacion e ON c.evaluacion_id = e.evaluacion_id;

-- Contar casos por evaluación
SELECT e.nombre, COUNT(c.caso_id) as total_casos
FROM evaluacion e
LEFT JOIN caso c ON c.evaluacion_id = e.evaluacion_id
GROUP BY e.nombre;

-- Ver casos con múltiples profesores asignados
SELECT c.caso_id, COUNT(cu.user_id) as num_profesores
FROM caso c
JOIN caso_usuarios cu ON c.caso_id = cu.caso_id
GROUP BY c.caso_id
HAVING COUNT(cu.user_id) > 1;
```

---

## 🎯 Flujo Recomendado para Nuevos Cambios

1. **Modificar models.py**: Hacer cambios en los modelos SQLAlchemy
2. **Generar migración**: `flask db migrate -m "descripción"`
3. **Revisar migración**: Verificar archivo generado en `migrations/versions/`
4. **Probar localmente**: `flask db upgrade` en entorno de desarrollo
5. **Hacer backup**: Antes de aplicar en producción
6. **Aplicar en producción**: `flask db upgrade`
7. **Verificar**: Confirmar que todo funciona correctamente

---

## 📚 Referencias

- [Flask-Migrate Documentation](https://flask-migrate.readthedocs.io/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
8. Migra `user_id` de `caso` a `caso_usuarios` (si existía)
9. Elimina columna `user_id` de tabla `caso`

---

## 3️⃣ Verificación Post-Migración

### Verificar tablas creadas
```bash
# Ingresar a PostgreSQL
docker-compose exec db psql -U kiwi_user kiwi_db

# Dentro de psql:
\dt                          # Listar todas las tablas
\d periodo                   # Ver estructura de tabla periodo
\d evaluacion                # Ver estructura de tabla evaluacion
\d caso_usuarios             # Ver estructura de tabla caso_usuarios

SELECT * FROM periodo;       # Ver periodos existentes
SELECT * FROM evaluacion;    # Ver evaluaciones existentes

\q                           # Salir de psql
```

### Verificar datos migrados
```bash
# API debe estar corriendo
flask run

# En otra terminal u con curl/Postman:

# Ver periodo activo
curl http://localhost:5000/api/periodos/activo

# Ver evaluaciones disponibles
curl -H "Authorization: Bearer <tu_token>" \
     http://localhost:5000/api/evaluaciones/listar

# Ver reportes (deben mostrar evaluacion_id)
curl -H "Authorization: Bearer <tu_token>" \
     http://localhost:5000/api/reportes/reportes
```

---

## 4️⃣ Inicio de Operaciones

### Crear Periodo Actual
```bash
# Ejemplo: Crear periodo 2026-1
curl -X POST http://localhost:5000/api/periodos/crear \
  -H "Authorization: Bearer <tu_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "2026-1",
    "anio": 2026,
    "semestre": 1,
    "fecha_inicio": "2026-03-01T00:00:00",
    "fecha_fin": "2026-07-31T23:59:59",
    "activo": true
  }'
```

### Crear Evaluaciones del Semestre
```bash
# Obtener periodo_id del periodo activo
curl http://localhost:5000/api/periodos/activo

# Crear evaluación "Tarea 1"
curl -X POST http://localhost:5000/api/evaluaciones/crear \
  -H "Authorization: Bearer <tu_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Tarea 1",
    "descripcion": "Primera tarea del semestre 2026-1",
    "fecha_entrega": "2026-03-15T23:59:00",
    "periodo_id": 5
  }'

# Crear más evaluaciones
curl -X POST http://localhost:5000/api/evaluaciones/crear \
  -H "Authorization: Bearer <tu_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Tarea 2",
    "periodo_id": 5
  }'
```

### Subir Reportes
```bash
# Ahora al subir un reporte, debes especificar evaluacion_id
curl -X POST http://localhost:5000/api/reportes/upload \
  -H "Authorization: Bearer <tu_token>" \
  -F "file=@Similitudes_T1.xlsx" \
  -F "titulo=Reporte MOSS - Sección 202" \
  -F "evaluacion_id=10"
```

---

## ❌ Rollback (Si algo sale mal)

### Revertir migración
```bash
# Ver revisión actual
flask db current

# Ver historial para encontrar revisión anterior
flask db history

# Revertir a revisión anterior
flask db downgrade <revision_id_anterior>

# O revertir un paso atrás
flask db downgrade -1
```

### Restaurar desde backup
```bash
# Detener contenedores
docker-compose down

# Recrear base de datos y restaurar
docker-compose up -d db
docker-compose exec -T db psql -U kiwi_user kiwi_db < backup_antes_migracion.sql

# Reiniciar todo
docker-compose up -d
```

---

## 📊 Comandos Útiles Post-Migración

### Ver estadísticas
```bash
curl -H "Authorization: Bearer <tu_token>" \
     http://localhost:5000/api/admin/estadisticas
```

Respuesta esperada incluirá:
```json
{
  "estadisticas": {
    "casos": 234,
    "reportes": 12,
    "evaluaciones": 5,
    "periodos": 2,
    "estudiantes": 450,
    "users": 8,
    "paralelos": 6,
    "sedes": 2,
    "roles": 3,
    "user_paralelos": 8,
    "caso_estudiantes": 468,
    "caso_usuarios": 234
  }
}
```

### Ver casos de una evaluación completa
```bash
# Ver TODOS los casos de "Tarea 1" (agrega de todos sus reportes)
curl -H "Authorization: Bearer <tu_token>" \
     http://localhost:5000/api/evaluaciones/casos/10

# Con filtros
curl -H "Authorization: Bearer <tu_token>" \
     "http://localhost:5000/api/evaluaciones/casos/10?min_similitud=85&estado=Pendiente"
```

### Filtrar evaluaciones por periodo
```bash
# Solo evaluaciones del periodo activo
curl http://localhost:5000/api/evaluaciones/listar?solo_activo=true

# Evaluaciones de un periodo específico
curl http://localhost:5000/api/evaluaciones/listar?periodo_id=5
```

---

## 🔍 Solución de Problemas

### Error: "No module named 'app'"
```bash
# Asegúrate de estar en el directorio correcto
cd c:\Users\bastian\TT\DetKIWI-BACKEND

# Verifica que FLASK_APP esté configurado
echo $env:FLASK_APP
# Debe mostrar: run.py

# Si no está configurado:
$env:FLASK_APP="run.py"
```

### Error: "Target database is not up to date"
```bash
# Alguien más aplicó migraciones, sincroniza:
flask db upgrade
```

### Error: "Can't locate revision identified by..."
```bash
# Regenerar migraciones desde cero (CUIDADO: solo en desarrollo)
# Eliminar carpeta migrations/versions/
# Recrear migraciones:
flask db init
flask db migrate -m "Recrear esquema completo"
flask db upgrade
```

### Error: "relation 'periodo' already exists"
```bash
# La migración ya se aplicó parcialmente
# Ver estado:
flask db current

# Si está incompleta, hacer rollback y reintentarRevertir: flask db downgrade -1
# Aplicar: flask db upgrade
```

---

## ✅ Checklist Post-Migración

- [ ] `flask db upgrade` ejecutado sin errores
- [ ] Tabla `periodo` existe y tiene periodo por defecto
- [ ] Tabla `evaluacion` existe y tiene evaluación por defecto
- [ ] Tabla `caso_usuarios` existe
- [ ] Columna `evaluacion_id` agregada a `reporte`
- [ ] Columna `user_id` eliminada de `caso`
- [ ] Reportes existentes migrados a evaluación por defecto
- [ ] API se levanta sin errores: `flask run`
- [ ] Endpoint `/api/periodos/activo` responde
- [ ] Endpoint `/api/evaluaciones/listar` responde
- [ ] Endpoint `/api/admin/estadisticas` muestra periodos y evaluaciones
- [ ] Nuevos reportes requieren `evaluacion_id` (probar con Postman/cURL)

---

## 📚 Documentación de Referencia

- [DOCUMENTACION_PERIODOS.md](DOCUMENTACION_PERIODOS.md) - Guía completa del sistema de periodos
- [DOCUMENTACION_EVALUACIONES.md](DOCUMENTACION_EVALUACIONES.md) - Documentación de evaluaciones
- [DOCUMENTACION_CASOS_MULTIPLES_USUARIOS.md](DOCUMENTACION_CASOS_MULTIPLES_USUARIOS.md) - Casos con múltiples usuarios
- [README_COMPLETO.md](README_COMPLETO.md) - API completa actualizada

---

## 🎉 ¡Listo!

Si todos los pasos se completaron exitosamente, tu sistema ahora tiene:
- ✅ Gestión de periodos académicos (semestres)
- ✅ Evaluaciones organizadas por periodo
- ✅ Múltiples profesores por caso (plagio cross-paralelo)
- ✅ Filtrado de casos por evaluación completa
- ✅ Vista limpia por periodo activo

**Próximo paso:** Integrar en el frontend los selectores de:
1. Periodo (combo box: 2025-1, 2025-2, 2026-1...)
2. Evaluación (filtrado por periodo seleccionado)
3. Ver casos agregados de evaluación completa
