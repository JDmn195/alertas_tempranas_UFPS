# Resultados de las pruebas de rendimiento

Corrida del 7 de octubre de 2026, rama `test/rendimiento`.

## Entorno

| | |
|---|---|
| Base de datos | PostgreSQL 16.4 local en Docker (sin latencia de red) |
| Servidor | waitress, 1 proceso con 8 hilos, `DEBUG=False`, tareas en segundo plano como en producción |
| Volumen | 2 000 estudiantes, 52 000 notas, 90 000 registros de asistencia, 100 cursos, 40 docentes, ~8 500 alertas abiertas |
| Mezcla de usuarios | 6 docentes : 2 bienestar : 1 dirección : 1 administración, con 1 a 4 s entre acciones |

Producción (Render + Supabase) agrega latencia de red en cada consulta a la base, así que los tiempos reales serán **mayores** en los endpoints con muchas consultas. Los números sirven para comparar endpoints y detectar cuellos de botella, no como tiempos absolutos de producción.

## 1. Procesos por lotes (2 000 estudiantes)

| Proceso | Tiempo | Por estudiante | Correos intentados |
|---|---|---|---|
| Re-evaluación completa, primera vez (HU-29) | 4 min 10 s | 125 ms | 16 976 |
| Alertas por corte (HU-32) | 2 min 46 s | 83 ms | 16 421 |
| Alertas por inasistencia (HU-36) | 2 min 40 s | 80 ms | 10 752 |
| Re-evaluación diaria sin cambios | 2 min 55 s | 88 ms | 0 |

## 2. Carga concurrente de la API

| Escenario | Usuarios | Peticiones/s | p50 | p95 | p99 | Errores | Umbrales |
|---|---|---|---|---|---|---|---|
| Línea base | 4 | 2,6 | 16 ms | 550 ms | 930 ms | 0 | ✅ cumple |
| Carga | 25 | 12,4 | 300 ms | 2,1 s | 3,0 s | 0 | ❌ 2 endpoints |
| Estrés | 75 | 10,7 | 5,0 s | 8,7 s | 11 s | 0 | ❌ todos |

Tiempos de servicio sin concurrencia (línea base, p50) de los endpoints más pesados:

| Endpoint | p50 | Consultas SQL |
|---|---|---|
| Panel del docente | 500 ms | 72 |
| Listado de alertas | 250 ms | 7 (respuesta de 3,9 MB) |
| Estudiantes de un curso (docente) | 180 ms | 11 |
| Ficha del estudiante (cada llamada) | 7–16 ms | — |
| Guardar asistencia | 66 ms | — |

**Lectura:** el sistema no da errores ni siquiera con 75 usuarios, pero un proceso se satura en ~12 peticiones/s. Con 25 usuarios la mayoría de endpoints responde bien y solo incumplen el panel del docente y el listado de alertas. Con 75 todo queda en cola detrás de esos dos endpoints: hasta `me` (20 ms sin carga) sube a 7 s.

## Hallazgos

### 1. El listado de alertas no está paginado (prioridad alta)
`GET /api/alertas/` devuelve **todas** las alertas del estado pedido: con 8 500 alertas activas son **3,9 MB** por cada visita a "Gestión de Alertas" (y en cada "Actualizar"). Crece sin límite con cada alerta nueva y es el endpoint que más tiempo de servidor consume bajo carga (p95 3 s con 25 usuarios). Con búsqueda la respuesta baja a 21 KB.
**Recomendación:** paginar por estudiante en el backend (la pantalla ya agrupa por estudiante) y cargar las alertas de un estudiante al expandir su tarjeta.

### 2. Correos síncronos dentro de los procesos por lotes (prioridad alta)
Cada alerta nueva llama a `NotificationService.notificar_alerta`, que envía por Brevo un correo por destinatario (estudiante, docente, director y cada administrador) **dentro del mismo proceso**, con timeout de 10 s. En esta prueba no hay clave de Brevo y cada intento falla al instante; en producción la primera pasada sobre 2 000 estudiantes intentaría **44 149 correos** y, a ~300 ms por llamada, el proceso tardaría del orden de **3–4 horas**. Lo mismo ocurre al importar historiales o activar una regla nueva sobre muchos estudiantes.
**Recomendación:** encolar los correos (tabla de pendientes + envío por lotes con la API de Brevo) en vez de enviarlos en línea, y agrupar en un resumen los correos a director y administradores.

### 3. Panel del docente con N+1 (prioridad media)
`GET /api/academico/teacher/dashboard/` hace 72 consultas: una por cada estudiante en riesgo de la página (hasta 50) para obtener el nombre de su curso, y una por curso para contar los estudiantes en riesgo. Es la pantalla de inicio de los docentes, el rol más numeroso.
**Recomendación:** traer el curso de cada estudiante con una sola consulta (`Nota.objects.filter(estudiante__in=..., curso__in=...)` agrupada) y calcular los en riesgo por curso desde `todos_estudiantes_ids` en memoria. El frontend pide `page_size=100` pero el backend lo limita a 50.

### 4. Re-evaluación: ~35 consultas por estudiante (prioridad media)
La re-evaluación hace ~35 consultas por estudiante (PPA y riesgo recalculados periodo por periodo). En local son ~90 ms por estudiante; contra Supabase cada consulta paga la latencia de red (5–20 ms), lo que puede llevar la ejecución nocturna de 3 a **10–25 minutos** con 2 000 estudiantes.
**Recomendación:** precargar las notas del estudiante una vez y calcular los indicadores de todos sus periodos en memoria.

### 5. Capacidad de un proceso (a revisar en Render)
Un proceso de Python sirve ~12 peticiones/s con esta mezcla. Conviene confirmar cuántos workers de gunicorn tiene el servicio en Render (el comando de arranque no está en el repositorio): con 1 worker, ~25 usuarios activos a la vez ya son el límite.

## Cómo repetirlo

Ver [README.md](README.md). Los reportes HTML y CSV de cada corrida quedan en `resultados/` (ignorado por git).
