# Sprint 0 — Sistema de Alertas Tempranas Académicas (UFPS)

**Proyecto:** Sistema de Alertas Tempranas Académicas  
**Institución:** Universidad Francisco de Paula Santander (UFPS)  
**Repositorio:** [JDmn195/alertas_tempranas_UFPS](https://github.com/JDmn195/alertas_tempranas_UFPS)  
**Versión / Línea Base:** `v0.1.0-sprint0`  
**Despliegue Frontend:** Vercel  
**Despliegue Backend:** Render / Neon PostgreSQL  

---

## 1. Hallazgos y Exploración Técnica

Durante el Sprint 0 se consolidó la exploración de las fuentes de información académica y la arquitectura técnica del sistema:

### Ingesta y Calidad de Datos Institucionales (DIRPLAN)
* **Estructura de planillas:** La información provista por DIRPLAN se distribuye en reportes estructurados de estudiantes, docentes, notas por periodo y asignaturas cursadas.
* **Normalización de identificadores:** Se evidenció la necesidad de sanitizar códigos numéricos de docentes y estudiantes para conservar ceros a la izquierda (formato estándar de 5 dígitos en docentes mediante `_normalizar_codigo_docente`).
* **Equivalencias curriculares:** Para el seguimiento preciso del atraso curricular frente al pensum oficial, se integró el modelo de `EquivalenciaMateria`, permitiendo homologar asignaturas cursadas bajo códigos o planes alternos.

### Definición del Stack Tecnológico
* **Backend:** Django 6.0.4 en Python 3.10+, utilizando su ORM relacional y transacciones atómicas para operaciones de carga masiva de datos.
* **Base de Datos:** PostgreSQL en entorno serverless con **Neon DB**, garantizando persistencia relacional.
* **Almacenamiento de Evidencias:** Integración con **Supabase Storage** para resguardar documentos y soportes adjuntos a las intervenciones.
* **Generación de Reportes y Analítica:** Librerías `pandas` y `openpyxl` para lectura y validación de archivos Excel, y `ReportLab` para la emisión de consolidados en formato PDF.
* **Frontend:** Single Page Application (SPA) construida con **React 18**, **Vite**, **TypeScript**, **TailwindCSS 4**, componentes basados en **Radix UI / Shadcn UI**, **Recharts** para visualización gráfica y **React Router 7**.
* **Control de Acceso y Seguridad:** Autenticación JWT con esquema de roles (RBAC: `ADMINISTRADOR`, `DIRECTOR`, `DOCENTE`, `BIENESTAR`) y trazabilidad de eventos mediante la entidad `Auditoria`.

---

## 2. Decisiones de Arquitectura y Evolución del Diseño

A lo largo del sprint se implementaron optimizaciones estructurales sobre el diseño inicial:

1. **Normalización del Modelo Relacional Académico:**
   * Esquema estructurado en torno a las entidades `Periodo`, `Materia`, `Docente`, `Curso`, `Estudiante`, `Nota` y `BitacoraImportacion`, garantizando la integridad referencial de los históricos de notas.

2. **Motor de Reglas y Cálculo Dinámico de Riesgo:**
   * Sustitución de umbrales fijos por la entidad configurable `Regla` (criterios de Promedio, Reprobación y Atraso Curricular) y persistencia del historial de riesgo por estudiante y por periodo (`RiesgoEstudiante`, `RiesgoEstudiantePeriodo`).

3. **Ciclo Integral de Intervenciones y Evidencias:**
   * Registro y seguimiento de intervenciones académicas (`Tutoría`, `Citación`, `Remisión`), complementado con anexos digitales en Supabase (`Evidencia`) y bitácora de anotaciones (`AnotacionIntervencion`).

4. **Estabilidad y Cobertura de Pruebas:**
   * Adición de validaciones de carga con límite de archivo (15 MB), configuración de dependencias estables para despliegue en Render y suite de 38 pruebas unitarias automatizadas para los módulos de importación y gestión de usuarios.

---

## 3. Matriz de Riesgos Técnicos y Operativos

| Código | Riesgo Identificado | Nivel | Plan de Mitigación Implementado / Propuesto |
|:---:|---|:---:|---|
| **R-01** | **Variabilidad en formatos de planillas DIRPLAN:** Cambios imprevistos en columnas, tipos de celdas o encabezados en las exportaciones institucionales. | Alto | Validación de esquema previa a la inserción (`_validar_columnas`, `_leer_dataframe`) con reporte detallado de filas con inconsistencias sin afectar la base de datos. |
| **R-02** | **Desfase temporal en el reporte de notas:** Registro tardío de calificaciones en los cortes académicos institucionales. | Alto | Habilitación de importaciones incrementales por corte y evaluación sobre el historial académico acumulado de periodos previos. |
| **R-03** | **Sobrecarga en procesamiento masivo de datos:** Consumo elevado de memoria o tiempos de respuesta altos al recalcular alertas de cohortes completas. | Medio | Ejecución en lotes (`bulk_create`), optimización de consultas con `select_related` y limitación de tamaño en peticiones síncronas. |
| **R-04** | **Adopción y registro de intervenciones:** Ocurrencia de intervenciones académicas que no sean registradas formalmente por los docentes o bienestar. | Medio | Interfaz simplificada para registro rápido, notificaciones internas y panel de seguimiento para directores de programa. |

---

## 4. Línea Base del Sistema (`v0.1.0-sprint0`)

El alcance congelado y validado para la versión `v0.1.0-sprint0` comprende:

* **Módulo de Usuarios y Seguridad:** Control de acceso basado en roles (RBAC), login, recuperación de contraseñas y auditoría del sistema.
* **Módulo de Ingesta de Datos:** Carga masiva de estudiantes, docentes, asignaturas y calificaciones con trazabilidad en bitácora.
* **Módulo de Detección de Riesgo:** Motor de reglas configurable y cálculo de nivel de riesgo (Alto, Medio, Bajo) histórico y por periodo.
* **Módulo de Consulta y Seguimiento:**
  * Listado general y filtrado de estudiantes por nivel de riesgo y promedio.
  * Perfil detallado del estudiante con historial académico y materias reprobadas.
  * Paneles para Docente y Director con métricas agregadas por asignatura.
* **Módulo de Intervenciones:** Creación de tutorías, citaciones y remisiones con adjunto de evidencias y notas de seguimiento.
* **Módulo de Reportes:** Exportación de listados en Excel y reportes consolidados en PDF.
* **Infraestructura:** Frontend activo en Vercel y Backend conectado a Neon PostgreSQL.

---

## 5. Hoja de Ruta y Próximos Pasos (Sprint 1)

1. **Piloto con Cohorte Real:** Ingesta y validación integral con el conjunto de datos completo del programa académico.
2. **Calibración de Heurísticas:** Ajuste de los umbrales de riesgo en conjunto con la dirección de programa y comité curricular.
3. **Optimización de Rendimiento:** Indexación y afinamiento de consultas para listados de alta concurrencia.
4. **Validación de Usabilidad (UAT):** Sesiones guiadas de retroalimentación con docentes y personal de Bienestar Universitario.
5. **Automatización CI/CD:** Configuración de GitHub Actions para ejecución continua de pruebas unitarias.

---

## 6. Compromisos y Objetivos para el Sprint 1

### Objetivo General:
> **Desplegar la fase piloto con datos reales de la cohorte institucional, calibrar las reglas de riesgo con la dirección del programa y optimizar la experiencia de usuario y tiempos de respuesta del sistema.**

### Historias de Usuario / Metas Comprometidas:

| ID | Módulo / Funcionalidad | Resultado Esperado |
|:---:|---|---|
| **HU-PILOT-01** | **Calibración de Reglas Institucionales** | Configuración y validación de reglas de riesgo aprobadas por el comité del programa. |
| **HU-PERF-02** | **Optimización de Consultas** | Tiempos de carga menores a 1.5 segundos en listados superiores a 2.000 registros. |
| **HU-TEST-03** | **Pruebas de Integración E2E** | Suite automatizada que cubra el flujo de importación, detección de alertas y emisión de reportes. |
| **HU-UX-04** | **Ajustes de Interfaz UAT** | Incorporación de mejoras de usabilidad en el flujo de intervenciones y evidencias. |
| **HU-CI-05** | **Pipeline de Integración Continua** | Ejecución automática de tests y linter en cada Pull Request a `main`. |
