# Sistema de Alertas Tempranas Académicas (UFPS)

Plataforma web institucional para la detección oportuna, seguimiento y gestión de intervenciones a estudiantes en condición de vulnerabilidad o riesgo académico en la **Universidad Francisco de Paula Santander (UFPS)**.

* **Repositorio:** [https://github.com/JDmn195/alertas_tempranas_UFPS](https://github.com/JDmn195/alertas_tempranas_UFPS)
* **Despliegue Frontend:** [Vercel](https://alertas-tempranas-ufps.vercel.app/) *(Configurado mediante `FRONTEND/vercel.json`)*
* **Despliegue Backend:** Render / Neon PostgreSQL

---

## Objetivo del Proyecto

Centralizar la información académica institucional proveniente de DIRPLAN para calcular niveles de riesgo estudiantil a través de un motor de reglas dinámicas, facilitando la toma de decisiones, la asignación de tutorías/citaciones/remisiones y el seguimiento a través de evidencias y reportes analíticos.

---

## Stack Tecnológico

### Backend
* **Lenguaje y Framework:** Python 3.10+, Django 6.0.4
* **Base de Datos:** PostgreSQL en **Neon DB** (Serverless)
* **Almacenamiento de Archivos:** **Supabase Storage** (Gestión de evidencias digitales)
* **Procesamiento de Datos y Reportes:** `pandas` (3.0.2), `openpyxl` (3.1.5), `ReportLab` (4.2.5)
* **Servidor y Seguridad:** `gunicorn`, `whitenoise`, `dj-database-url`, `django-cors-headers`, JWT Auth & RBAC

### Frontend
* **Entorno y Framework:** React 18.3, Vite 6.3, TypeScript
* **Enrutamiento:** React Router 7
* **Estilos y Componentes:** TailwindCSS 4, Radix UI / Shadcn UI, Lucide Icons
* **Gráficas y Analítica:** Recharts 2.15, Motion
* **Utilidades:** Sonner, Date-fns

---

## Estructura del Repositorio

```text
alertas_tempranas_UFPS/
│
├── BACKEND/alertas_tempranas_ufps/      # Backend Django REST
│   ├── academico/                      # Modelos y vistas de estudiantes, docentes, notas, materias, cursos e importación DIRPLAN
│   │   ├── migrations/                 # Migraciones de base de datos
│   │   ├── tests.py                    # Pruebas unitarias de modelos académicos
│   │   ├── tests_import_helpers.py     # 38 pruebas unitarias para helpers de importación
│   │   ├── views/                      # Vistas de importación, bitácora, indicadores y perfil
│   │   └── models.py                   # Esquema relacional académico
│   ├── alertas/                        # Motor de reglas dinámicas, cálculo de riesgo, alertas, intervenciones, evidencias y reportes
│   │   ├── views/                      # Vistas de reglas, generación de alertas, evidencias y reportes PDF/Excel
│   │   ├── services.py                 # Lógica de cálculo de riesgo y aplicación de reglas
│   │   └── models.py                   # Modelos de Regla, Alerta, Intervención, Evidencia y Notificación
│   ├── usuarios/                       # Módulo de autenticación, control de roles (RBAC) y bitácora de auditoría
│   │   ├── views.py                    # Endpoints de login, registro, gestión de usuarios y auditoría
│   │   ├── decorators.py               # Decoradores @token_requerido y @rol_requerido
│   │   └── models.py                   # Modelo de Usuario y Auditoria
│   ├── alertas_tempranas_ufps/         # Configuración del proyecto Django (settings.py, urls.py, wsgi.py)
│   ├── requirements.txt                # Dependencias Python
│   ├── manage.py                       # CLI de Django
│   └── SETUP.md                        # Guía de configuración local del backend
│
├── FRONTEND/                           # Aplicación cliente SPA (React + Vite)
│   ├── src/
│   │   ├── app/
│   │   │   ├── components/             # Componentes reutilizables (Layouts, ProtectedRoute, UI)
│   │   │   ├── screens/                # Pantallas principales (Admin, Docente, Director, Estudiantes, Alertas, Reportes, Auditoría)
│   │   │   └── routes.tsx              # Definición de rutas y permisos por rol
│   │   ├── services/                   # Servicios HTTP (apiFetch, evidenceService, ruleService)
│   │   ├── styles/                     # Estilos globales y tokens CSS
│   │   └── main.tsx                    # Punto de entrada de la aplicación
│   ├── package.json                    # Dependencias y scripts de frontend
│   ├── vite.config.ts                  # Configuración de Vite
│   ├── tsconfig.json                   # Configuración de TypeScript
│   └── vercel.json                     # Configuración de despliegue para Vercel
│
└── SPRINT-0-CLOSURE.md                 # Documento de cierre de línea base
```

---

## Ejecución Local

### 1. Backend

1. Ingresar a la carpeta del backend:
   ```bash
   cd BACKEND/alertas_tempranas_ufps
   ```
2. Crear y activar entorno virtual:
   ```bash
   python -m venv venv
   # En Windows:
   venv\Scripts\activate
   # En Linux/Mac:
   source venv/bin/activate
   ```
3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
4. Configurar variables de entorno (`.env` basado en `.env.example` con la cadena de conexión a PostgreSQL de Neon).
5. Aplicar migraciones y levantar el servidor:
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```
   *Servidor disponible en: `http://127.0.0.1:8000`*

### 2. Frontend

1. Ingresar a la carpeta del frontend:
   ```bash
   cd FRONTEND
   ```
2. Instalar dependencias:
   ```bash
   npm install
   ```
3. Iniciar el entorno de desarrollo:
   ```bash
   npm run dev
   ```
   *Aplicación disponible en: `http://localhost:5173`*

---

## Pruebas Automatizadas

Para ejecutar la suite de pruebas unitarias del backend:

```bash
cd BACKEND/alertas_tempranas_ufps
python manage.py test academico.tests_import_helpers
python manage.py test usuarios
```
