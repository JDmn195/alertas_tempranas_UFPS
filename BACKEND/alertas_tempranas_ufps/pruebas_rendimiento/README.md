# Pruebas de rendimiento

Dos mediciones complementarias, siempre sobre una base aislada (`E2E=True`: no se carga el `.env`, así que nunca se toca la base real ni se envían correos):

1. **Procesos por lotes** (`manage.py preparar_rendimiento`): genera una carrera completa con datos deterministas y mide la re-evaluación nocturna (HU-29), las alertas por corte (HU-32) y por inasistencia (HU-36) sobre toda la población.
2. **Carga concurrente de la API** (`locustfile.py` + `ejecutar.py`): usuarios simulados por rol (docentes, bienestar, dirección, administración) recorren las mismas llamadas que el frontend. La corrida falla si algún endpoint supera los umbrales.

## Requisitos

```bash
cd BACKEND/alertas_tempranas_ufps
pip install -r pruebas_rendimiento/requirements.txt
```

Para que los números se parezcan a producción conviene un Postgres local desechable (con SQLite funciona, pero no representa la concurrencia):

```bash
docker run -d --name sat-rendimiento-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=sat -p 5433:5432 postgres:16.4
export E2E_DATABASE_URL=postgres://postgres:postgres@localhost:5433/sat
```

`preparar_rendimiento` borra por completo esa base, y por seguridad solo acepta un Postgres en `localhost`.

## 1. Generar la base y medir los procesos por lotes

```bash
E2E=True SECRET_KEY=x ALLOWED_HOSTS=localhost \
  python manage.py preparar_rendimiento --estudiantes 2000 --salida pruebas_rendimiento/resultados/procesos_lotes.json
```

Escenario generado (semilla fija, siempre igual):

| Dato | Volumen (2 000 estudiantes) |
|---|---|
| Estudiantes | 2 000, repartidos en 10 semestres |
| Materias / cursos | 50 materias, 100 cursos (grupos A y B), 40 docentes |
| Notas | ~52 000 (hasta 7 periodos anteriores + el actual con cortes 1 y 2) |
| Asistencia | ~90 000 registros (9 clases del periodo actual) |
| Perfiles | ~15 % con bajo rendimiento, ~10 % con muchas faltas |
| Usuarios | `admin@`, `director@`, `bienestar1@`, `bienestar2@`, `docente01@`…`docente40@` (`@ufps.edu.co`), contraseña `Clave-Segura-2026` |

## 2. Prueba de carga de la API

Con la base ya generada:

```bash
python pruebas_rendimiento/ejecutar.py --usuarios 50 --duracion 3m --escenario carga
python pruebas_rendimiento/ejecutar.py --usuarios 150 --tasa 10 --duracion 3m --escenario estres
```

`ejecutar.py` levanta la API con waitress (gunicorn no corre en Windows) con `DEBUG=False`, corre Locust sin interfaz y deja en `resultados/` el reporte HTML (`<escenario>.html`) y los CSV. Para verla en vivo: levantar el servidor a mano y correr `locust -f pruebas_rendimiento/locustfile.py --host http://127.0.0.1:8002`.

Umbrales (variables de entorno): `UMBRAL_P95_MS` (2000), `UMBRAL_P95_REPORTES_MS` (5000), `UMBRAL_ERRORES` (0.01). El login no se evalúa: es lento a propósito (hash de la contraseña) y ocurre una vez por sesión.

## Resultados

El informe de la última corrida está en [RESULTADOS.md](RESULTADOS.md).
