# Sprint 0 - Línea base del proyecto

Estado general y verificable del repositorio correspondiente al cierre de la línea base del proyecto **Sistema de Alertas Tempranas Académicas (UFPS)**.

---

### Métricas y Datos Generales de Git
* **Fecha de cierre Sprint 0:** 9 de septiembre de 2026
* **Rango de fechas de commits:** 9 de abril de 2026 – 9 de septiembre de 2026
* **Total de commits incluidos:** 137 commits
* **Rama base:** `main`
* **Tag oficial:** `v0.1.0-sprint0`
* **Despliegue Frontend:** Configurado en Vercel
* **Despliegue Backend:** Render / Neon PostgreSQL

---

### Stack Tecnológico

* **Backend:** Python 3.10+, Django 6.0.4, PostgreSQL (Neon DB Serverless), Supabase Storage, Pandas 3.0.2, OpenPyXL 3.1.5, ReportLab 4.2.5, Gunicorn, WhiteNoise.
* **Frontend:** React 18.3, Vite 6.3, TypeScript, TailwindCSS 4, React Router 7, Radix UI / Shadcn UI, Recharts 2.15, Lucide Icons.

---

### Estructura del Repositorio

* `BACKEND/alertas_tempranas_ufps/`
  * `academico/`: Modelos, vistas y pruebas unitarias de estudiantes, docentes, materias, cursos, notas e importación DIRPLAN.
  * `alertas/`: Motor de reglas dinámicas, cálculo de niveles de riesgo, alertas, intervenciones, evidencias (Supabase) y reportes en PDF/Excel.
  * `usuarios/`: Autenticación JWT, control de roles (RBAC: Administrador, Director, Docente, Bienestar) y bitácora de auditoría.
* `FRONTEND/`
  * `src/app/screens/`: Vistas de usuario (AdminDashboard, StudentList, StudentProfile, RiskRules, AlertManagement, EvidenceManagement, TeacherDashboard, DirectorDashboard, ExportReports, UserManagement, AuditLog, NotificationInbox).
  * `src/app/components/`: Componentes UI y layout protegido por roles.
  * `src/services/`: Clientes y servicios HTTP.

---

### Resumen de Commits Principales

#### Backend
* `5dbab109` (2026-04-13): Estructura base del backend, modelos relacionales y plantillas de importación.
* `f6f76a9f` (2026-04-15): HU-01: Ingesta de estudiantes con validación de Excel y creación de usuarios.
* `0027758c` (2026-04-15): HU-02: Importación de notas con validación estricta y control de errores.
* `132aa613` (2026-04-19): HU-03: Importación general de docentes.
* `f5781187` (2026-04-20): HU-04: Ingesta de cursos y oferta académica.
* `686fe713` (2026-04-22): Implementación de control de acceso basado en roles (RBAC).
* `d9a8dd0a` (2026-04-27): HU-06: Módulo de bitácora de importación.
* `52973dfe` (2026-04-29): HU-08: Historial académico de estudiantes.
* `8be9adc9` (2026-04-29): HU-11: Indicadores por curso (reprobación, promedios, zonas de riesgo).
* `d48add07` (2026-05-06): HU-13: Reglas dinámicas de riesgo y motor de cálculo.
* `a9bf0239` (2026-05-08): HU-19: Registro de intervenciones asociadas a alertas.
* `6b3690b3` (2026-05-24): HU-23: Integración de reportes dinámicos con base de datos Neon.
* `6d0bbeeb` (2026-05-28): HU-26/27/28: Módulo de administración de usuarios y bitácora de auditoría.
* `83d7020c` / `02099457` (2026-05-29): Seguridad CORS/CSRF y validación de tamaño máximo de archivo.
* `15f0a7f3` / `a9a0bf34` (2026-05-29): Refactorización de helpers de importación y suite de 38 pruebas unitarias.

#### Frontend
* `9711529e` (2026-04-09): Mockups iniciales de la plataforma académica.
* `fac1220c` (2026-04-20): Flujo de autenticación e inicio de sesión.
* `1d46ff05` (2026-04-22): HU-09: Lista y filtrado de estudiantes con semaforización de riesgo.
* `7fe05815` (2026-04-22): Configuración de rutas SPA mediante `vercel.json`.
* `5491aaf0` (2026-04-23): HU-07: Perfil de estudiante con datos reales y asignaturas cursadas.
* `e580b681` (2026-04-23): Gráficas analíticas de evolución y promedio acumulado con Recharts.
* `2cf57c1c` (2026-04-29): HU-12: Matriz de inactivos e indicadores en dashboard.
* `ae3f0bc2` (2026-05-09): Parametrización de variables de entorno para API backend.
* `02a1a282` (2026-05-28): Refactorización de paneles para Director y Docente, modales de cursos y módulo de auditoría.
* `f70d3baa` / `6b570862` (2026-06-01 - 2026-06-03): Pantallas de reportes, gestión de evidencias y correcciones de integración.

---

> **Nota:** No ha habido actividad de desarrollo posterior a este tag. Este release representa el estado estático de la línea base del Sprint 0.
