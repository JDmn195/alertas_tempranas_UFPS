# Cierre de Sprint 0 — Sistema de Alertas Tempranas Académicas (UFPS)

**Proyecto:** Sistema de Alertas Tempranas Académicas  
**Institución:** Universidad Francisco de Paula Santander (UFPS)  
**Repositorio:** [JDmn195/alertas_tempranas_UFPS](https://github.com/JDmn195/alertas_tempranas_UFPS)  
**Versión / Tag de Línea Base:** `v0.1.0-sprint0`  
**Despliegue Frontend:** Vercel  
**Despliegue Backend:** Render / Neon PostgreSQL  

---

## 1. Qué se encontró (Hallazgos del Sprint)

Durante la fase de exploración técnica y estructuración inicial del proyecto (Sprint 0), se identificaron hallazgos clave sobre los datos de origen, restricciones de infraestructura y decisiones de diseño arquitectónico:

### A. Exploración y Calidad de Datos de DIRPLAN
* **Heterogeneidad de formatos de entrada:** Los archivos Excel provenientes de DIRPLAN y sistemas de soporte académico presentan variaciones estructurales (archivos `.xls`/`.xlsx` con encabezados combinados, tipos numéricos en columnas de identificación y registros con espacios en blanco o comillas).
* **Códigos de docentes y estudiantes:** Se detectaron inconsistencias en la representación de los códigos de docentes (pérdida de ceros a la izquierda al leerse como numéricos, e.g., `1713` vs `01713`, o floats como `1713.0`), lo cual requirió desarrollar un pipeline de sanitización y normalización estricta a 5 dígitos (`_normalizar_codigo_docente`).
* **Dependencia de homologaciones y pensum:** Para calcular con precisión el atraso curricular fue necesario incorporar una estructura de `EquivalenciaMateria`, permitiendo que materias cursadas en planes anteriores o con códigos equivalentes satisfagan los requisitos del pensum vigente.

### B. Decisiones de Stack y Arquitectura
* **Backend:** Django 6.0.4 junto con Python 3.10+, aprovechando su robusto ORM relacional y capacidades transaccionales (`transaction.atomic`) para garantizar la integridad en operaciones masivas de importación.
* **Base de Datos:** PostgreSQL alojado en **Neon** (Database Serverless), optimizando el almacenamiento y escalabilidad en la nube.
* **Almacenamiento de Archivos y Evidencias:** Integración con **Supabase Storage** para la persistencia segura de adjuntos y soportes de intervenciones académicas.
* **Procesamiento de Datos y Reportes:** Uso de `pandas` y `openpyxl` para el parsing y validación en memoria de hojas de cálculo, y `ReportLab` para la generación programática de reportes oficiales en formato PDF.
* **Frontend:** Aplicación SPA moderna con **React 18**, **Vite**, **TypeScript**, **TailwindCSS 4**, componentes accesibles basados en **Radix UI / Shadcn UI**, **Recharts** para visualización analítica de tendencias y **React Router 7** con control de navegación protegida.
* **Seguridad y Control de Acceso:** Arquitectura basada en tokens JWT con control de acceso basado en roles (RBAC: `ADMINISTRADOR`, `DIRECTOR`, `DOCENTE`, `BIENESTAR`), decoradores de autorización y registro de auditoría (`Auditoria`).

### C. Restricciones Técnicas y Obstáculos Superados
* **Compatibilidad de compilación en PaaS (Render):** Se solventaron problemas de build al pinear dependencias específicas (e.g. `supabase==2.30.0` y compatibilidad con `pydantic-core`) evitando fallos de compilación nativa en entornos Linux sin herramientas de build C.
* **Límites de carga y timeouts:** Al importar grandes volúmenes de notas y recalcular alertas simultáneamente, se implementaron validaciones de tamaño máximo de archivo (`MAX_IMPORT_FILE_SIZE = 15MB`), lectura por lotes (`bulk_create`, `bulk_update`) y límites en el reprocesamiento síncrono para evitar timeouts en HTTP requests.

---

## 2. Qué se actualizó (Cambios de Rumbo y Alcance)

A partir de las pruebas de concepto iniciales y los primeros refinamientos con la lógica del negocio, se realizaron ajustes sustanciales respecto al diseño preliminar:

1. **Evolución del Esquema Relacional Académico:**
   * Se pasó de un esquema plano inicial a una estructura relacional normalizada compuesta por `Periodo`, `Materia`, `Docente`, `Curso`, `Estudiante`, `Nota` y `EquivalenciaMateria`.
   * Se integró la entidad `BitacoraImportacion` para garantizar la trazabilidad de cada archivo subido (usuario responsable, fecha, nombre original y estado del procesamiento).

2. **Refactorización del Motor de Alertas (Reglas Dinámicas):**
   * Inicialmente se contemplaron umbrales de riesgo fijos en código. Se refactorizó hacia un modelo dinámico `Regla` con umbrales configurables (`valor_umbral`), operadores relacionales (`<`, `>`, `<=`, `>=`, `==`), tipo de métrica (`PROMEDIO`, `REPROBACION`, `ATRASO`) y nivel (`Alto`, `Medio`, `Bajo`).
   * Se crearon modelos para registrar el historial temporal de riesgo: `RiesgoEstudiante` y `RiesgoEstudiantePeriodo`, permitiendo ver la evolución del estudiante a lo largo de los semestres.

3. **Reestructuración de Intervenciones y Evidencias:**
   * Se expandió el flujo de seguimiento pasando de un estado binario a un ciclo de vida completo: registro de intervenciones (`Tutoría`, `Citación`, `Remisión`), subida de evidencias digitales (`Evidencia`) conectadas a Supabase y módulo de anotaciones colaborativas (`AnotacionIntervencion`).

4. **Hardening de Seguridad, Manejo de Errores y Logging:**
   * Reemplazo de salidas por consola (`print`/`traceback`) por logging estructurado de Django.
   * Manejo granular de excepciones HTTP (400, 403, 404, 500) y protección CSRF/CORS.
   * Centralización de validadores en helpers reutilizables y suite de 38 pruebas unitarias automatizadas (`tests_import_helpers.py` y `usuarios/tests.py`).

---

## 3. Principales Riesgos y Plan de Mitigación

| # | Riesgo Identificado | Probabilidad | Impacto | Estrategia de Mitigación Propuesta |
|---|---|:---:|:---:|---|
| **R1** | **Calidad y variabilidad en la estructura de archivos DIRPLAN:** Cambios en los encabezados, formatos de celda o campos faltantes en las hojas de cálculo enviadas por dependencias académicas que provoquen errores en la importación. | Media | Alto | **Mitigación:** Capa de validación previa (`_validar_columnas`, `_leer_dataframe`) que verifica la presencia de columnas obligatorias, realiza coerción segura de tipos de datos y genera mensajes de error descriptivos con la fila y columna exacta del fallo sin corromper la BD. |
| **R2** | **Dependencia de la periodicidad de los cortes de notas:** Retraso en la carga institucional de notas de corte por parte de los docentes en los sistemas centrales, reduciendo la efectividad del carácter "temprano" de la alerta. | Alta | Alto | **Mitigación:** Soporte para importación incremental por periodos y sub-cortes, permitiendo generar alertas preventivas previas al cierre de semestre; además de habilitar alertas basadas en historial acumulado y semestres cursados. |
| **R3** | **Degradación del rendimiento en procesamiento masivo:** Tiempos de respuesta elevados o saturación de memoria durante la importación y cálculo masivo de alertas para miles de estudiantes en servidores cloud estándar. | Media | Medio | **Mitigación:** Optimización de consultas ORM con `select_related`/`prefetch_related`, operaciones por lote (`bulk_create(ignore_conflicts=True)`), validación de tamaño máximo de archivo (15 MB) y modularización para migrar el cálculo pesado a tareas asíncronas en caso de crecimiento de la cohorte. |
| **R4** | **Baja adopción y falta de registro oportuno de intervenciones:** Que docentes o bienestar atiendan a los estudiantes pero no registren las intervenciones ni adjunten evidencias en la plataforma. | Media | Alto | **Mitigación:** Interfaz intuitiva y ágil para registro de intervenciones (con flujos guiados en menos de 3 clics), notificaciones automáticas y panel de control para directores que visibilice el porcentaje de alertas atendidas vs. desatendidas. |

---

## 4. Línea Base Aprobada / Propuesta

La línea base técnica consolidada al cierre del **Sprint 0** (`v0.1.0-sprint0`) congela el siguiente alcance:

### Componentes y Funcionalidades Incluidas en la Línea Base:
* **Módulo de Autenticación y Usuarios (RBAC):** Login, recuperación de contraseña, cambio de credenciales, gestión de usuarios y asignación de roles (`ADMINISTRADOR`, `DIRECTOR`, `DOCENTE`, `BIENESTAR`).
* **Módulo de Auditoría y Trazabilidad:** Registro en bitácora de eventos críticos (logins, modificaciones de roles, subida de archivos, ejecución de reglas).
* **Módulo de Ingesta Académica:** Importación masiva de estudiantes, docentes, oferta de cursos y notas desde archivos Excel de DIRPLAN, con normalización y bitácora de importación.
* **Motor de Alertas y Riesgo Académico:** Definición de reglas configurables (promedio, materias reprobadas, atraso curricular) y asignación automática de niveles de riesgo.
* **Perfiles Académicos y Dashboards:**
  * Vista de lista y filtrado de estudiantes por nivel de riesgo y promedio.
  * Perfil detallado del estudiante con historial de calificaciones, asignaturas repetidas y evolución temporal.
  * Dashboards especializados para Docente y Director con métricas agregadas por curso.
* **Gestión de Intervenciones y Evidencias:** Registro de tutorías, citaciones y remisiones con soporte de archivos adjuntos (Supabase Storage) y anotaciones de seguimiento.
* **Generación de Reportes:** Exportación de reportes tabulares en Excel y resúmenes ejecutivos en PDF.
* **Despliegues Activos:** Frontend en producción en Vercel y Backend conectado a base de datos Neon PostgreSQL.

### Elementos Fuera de la Línea Base (Excluidos de esta fase):
* Sincronización bidireccional automática mediante API directa con el sistema académico central SIA/DIRPLAN (la ingesta se mantiene por carga de archivos estructurados).
* Modelos predictivos avanzados basados en Machine Learning supervisado o redes neuronales (se mantiene el motor heurístico por reglas configurables).
* Notificaciones masivas por WhatsApp o SMS (se mantienen notificaciones internas y canales de correo institucional).

---

## 5. Próximos Pasos (Sprint 1)

Durante el **Sprint 1** se priorizarán las siguientes actividades técnicas y operativas:

1. **Validación en Entorno Real / Piloto:** Carga y validación integral con el conjunto de datos históricos y vigentes del programa académico para calibrar las reglas de riesgo.
2. **Ajuste Fino de Heurísticas y Umbrales:** Sesión de calibración con directores de programa y comité curricular para definir los umbrales estándar de promedio y número de reprobaciones.
3. **Optimización y Pruebas de Carga:** Evaluación de tiempos de respuesta en la visualización de listas de más de 1.000 estudiantes y ajuste de índices en PostgreSQL (`db_table`).
4. **Pruebas de Aceptación de Usuario (UAT):** Sesiones guiadas de validación funcional con usuarios con roles de Docente y Bienestar Universitario para retroalimentar la experiencia de usuario (UX/UI).
5. **Robustecimiento del Pipeline de CI/CD:** Integración de ejecución automática de pruebas unitarias en GitHub Actions previo al merge a `main`.

---

## 6. Compromiso del Siguiente Sprint (Sprint 1)

### Objetivo General del Sprint 1:
> **"Validar y estabilizar la plataforma en un entorno piloto con datos académicos reales de la cohorte UFPS, calibrando el motor de reglas de riesgo con los directores de programa y garantizando la cobertura de pruebas y tiempos de respuesta óptimos para el ciclo de atención temprana."**

### Historias de Usuario / Funcionalidades Comprometidas:

| ID | Funcionalidad / Historia de Usuario | Criterio de Aceptación Medible |
|---|---|---|
| **HU-PILOT-01** | **Calibración y Validación de Reglas con Comité** | Configurar y validar al menos 3 conjuntos de reglas institucionales acordadas con la dirección (Riesgo Alto, Medio, Bajo) aplicadas a la cohorte real. |
| **HU-PERF-02** | **Optimización de Consultas y Paginación** | Tiempos de carga del listado de estudiantes y dashboard del director menores a 1.5 segundos para conjuntos de datos de más de 2.000 registros. |
| **HU-TEST-03** | **Ampliación de Cobertura de Pruebas Automatizadas** | Implementación de pruebas de integración para el ciclo completo: Importación $\rightarrow$ Cálculo de Alertas $\rightarrow$ Registro de Intervención $\rightarrow$ Exportación de Reporte, alcanzando >80% de cobertura en lógica crítica. |
| **HU-UX-04** | **Retroalimentación UAT y Ajustes de Usabilidad** | Implementar ajustes prioritarios de interfaz derivados de las pruebas de usuario con docentes y bienestar (flujo de carga de evidencias y filtros avanzados). |
| **HU-CI-05** | **Integración Continua con GitHub Actions** | Pipeline configurado para ejecutar linter y suite de tests (`pytest`/`django test`) en cada Pull Request a `main`. |

---
*Documento aprobado como base de referencia técnica para el desarrollo y seguimiento del ciclo de vida del software.*
