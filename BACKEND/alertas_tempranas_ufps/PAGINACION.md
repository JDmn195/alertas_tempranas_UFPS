# Paginación compatible de listados · SDAT-302

Los listados de usuarios (`/api/usuarios/`), solicitudes (`/api/alertas/solicitudes/`) y datos de reportes (`/api/alertas/reportes/`) aceptan `page` y `page_size`. Al enviar cualquiera de ellos se devuelve una página y los campos `page`, `page_size`, `pages` y `total`. El tamaño predeterminado es 20 y el máximo es 100; los valores no numéricos usan los predeterminados. Una página fuera de rango se ajusta a la última disponible.

Sin estos parámetros se conserva la respuesta previa completa, para mantener los consumidores existentes. No se modifica el exportador PDF/Excel. Los reportes conservan el cálculo completo de sus agregados antes de paginar su presentación; esta modificación limita lo que se envía, no acredita una reducción del costo de calcularlos. Los conteos y filtros de solicitudes no se restringen a la página visible.

El listado de estudiantes ya tenía paginación con máximo de 100 y se conserva. Usuarios se ordena por nombre e id; solicitudes por fecha e id. La consulta de solicitudes ya incluía `select_related` para estudiante, regla de la alerta, responsable y periodo; se mantiene y se comprueba que el número de consultas no crece por cada fila.

Revisión de índices en modelos y migraciones:

| Elemento | Cobertura existente |
|---|---|
| Estudiante | Código como clave primaria y documento único |
| Usuario | Id como clave primaria y correo único |
| Nota | Restricción única estudiante/curso/periodo e índices de claves foráneas |
| Solicitud | Índices de claves foráneas y compuesto `solicitud_est_estado_idx` sobre estudiante/estado |
| Periodo | Restricción única año/semestre |

No se duplican estos índices ni se añaden índices sin una consulta y una medición que los justifique. La revisión estática y las pruebas SQLite no sustituyen el escenario PostgreSQL de SDAT-303; no se declara una mejora de p95 en Neon sin medirla.
