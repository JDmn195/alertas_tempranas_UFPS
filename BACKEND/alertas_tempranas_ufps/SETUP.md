#  Guía de configuración — Backend Alertas Tempranas UFPS

Sigue estos pasos **en orden** después de clonar el repositorio.

---

## Requisitos previos

Asegúrate de tener instalado en tu máquina:

- [Python 3.10+](https://www.python.org/downloads/) 
- [Git](https://git-scm.com/) 
- El **connection string** de Neon (pídeselo a Juan David por WhatsApp/Discord, **nunca está en el repo**)

---

## Paso 1 — Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/alertas_tempranas_UFPS.git
cd alertas_tempranas_UFPS
```

---

## Paso 2 — Entrar a la carpeta del backend

```bash
cd BACKEND/alertas_tempranas_ufps
```

---

## Paso 3 — Crear y activar un entorno virtual *(recomendado)*

Esto evita conflictos entre paquetes de otros proyectos.

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Mac / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

> Sabrás que está activo porque verás `(venv)` al inicio de la línea en tu terminal.

---

## Paso 4 — Instalar las dependencias

```bash
pip install -r requirements.txt
```

Esto instala automáticamente:
- `Django` — el framework del backend
- `psycopg2-binary` — el conector con PostgreSQL (Neon)
- `python-dotenv` — para leer el archivo `.env`

---

## Paso 5 — Crear el archivo `.env`

El archivo `.env` contiene las credenciales de la base de datos. **No está en el repo por seguridad.**

Copia la plantilla incluida:

**Windows:**
```bash
copy .env.example .env
```

**Mac / Linux:**
```bash
cp .env.example .env
```

Luego abre el `.env` y rellena los valores con el connection string que te compartió Juan David:

```
postgresql://  neondb_owner  :  npg_xxxxx  @  ep-xxxx.neon.tech  /  neondb
               ↓                 ↓              ↓                    ↓
            DB_USER           DB_PASSWORD     DB_HOST             DB_NAME
```

El `.env` debe quedar así (con los valores reales):

```env
DB_NAME=neondb
DB_USER=neondb_owner
DB_PASSWORD=la_password_que_te_dieron
DB_HOST=ep-xxxx.neon.tech
DB_PORT=5432

SECRET_KEY=django-insecure-om79t4&_8=o0^c--314xy+nbzy%8=wz^qi5m^6lubf-o22qes&
DEBUG=True
```

---

## Paso 6 — Aplicar las migraciones

Esto crea las tablas en la base de datos de Neon:

```bash
python manage.py migrate
```

Si ves algo como esto, todo está bien:

```
Operations to perform:
  Apply all migrations: admin, auth, contenttypes, sessions
Running migrations:
  Applying contenttypes.0001_initial... OK
  ...
```

---

## Paso 7 — Correr el servidor

```bash
python manage.py runserver
```

Abre tu navegador en: **http://127.0.0.1:8000/**

Si ves la página de bienvenida de Django, ¡el backend está funcionando! 🎉

---

## ❗ Errores comunes

| Error | Causa probable | Solución |
|---|---|---|
| `No module named 'django'` | No activaste el entorno virtual | Ejecuta `venv\Scripts\activate` |
| `could not connect to server` | Credenciales incorrectas en `.env` | Revisa el `.env` con el connection string |
| `ModuleNotFoundError: dotenv` | No instalaste dependencias | Ejecuta `pip install -r requirements.txt` |
| `.env` no encontrado | No copiaste el archivo | Ejecuta `copy .env.example .env` |

---

## Estructura del proyecto

```
alertas_tempranas_UFPS/
├── BACKEND/
│   └── alertas_tempranas_ufps/
│       ├── .env.example        ← plantilla pública (cópiate esto como .env)
│       ├── .env                ← TUS credenciales reales (NO está en Git)
│       ├── requirements.txt    ← dependencias del proyecto
│       ├── manage.py
│       └── alertas_tempranas_ufps/
│           └── settings.py
└── FRONTEND/
```

---

> **¿Tienes problemas?** Escríbele a Carlos Avendaño.
