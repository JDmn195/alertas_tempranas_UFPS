"""
Prueba de carga de la API con Locust.

Simula a los usuarios del sistema haciendo las mismas llamadas que el frontend en
sus pantallas habituales, sobre la base generada por `manage.py preparar_rendimiento`.
La mezcla por rol refleja el uso esperado: sobre todo docentes, luego bienestar,
dirección y administración.

Al terminar, la corrida falla (código de salida 1) si se incumplen los umbrales:
  - p95 de cada endpoint por debajo de UMBRAL_P95_MS (por defecto 2000 ms)
  - errores por debajo de UMBRAL_ERRORES (por defecto 1 %)

Ver pruebas_rendimiento/README.md para correrla.
"""
import os
import random

from locust import HttpUser, between, events, task

CONTRASENA = 'Clave-Segura-2026'
DOCENTES = 40
UMBRAL_P95_MS = float(os.environ.get('UMBRAL_P95_MS', 2000))
UMBRAL_ERRORES = float(os.environ.get('UMBRAL_ERRORES', 0.01))
# Endpoints pesados por diseño (reportes): umbral aparte
UMBRAL_P95_REPORTES_MS = float(os.environ.get('UMBRAL_P95_REPORTES_MS', 5000))

# Token por cuenta. Se llenan antes de generar carga (ver abrir_sesiones): el login es lento a propósito
# (hash de la contraseña, ~2 s de CPU) y los usuarios reales lo hacen una vez y reutilizan su JWT. Si 50
# usuarios simulados entraran a la vez, el hash acapararía la CPU y retrasaría a todos los demás endpoints.
SESIONES: dict[str, str] = {}

ACADEMICO = '/api/academico'
ALERTAS = '/api/alertas'


def codigos_estudiantes(datos):
    """Códigos de estudiante que aparezcan en cualquier parte de una respuesta JSON."""
    encontrados = []
    if isinstance(datos, dict):
        for clave, valor in datos.items():
            if clave in ('codigo', 'codigo_estudiante', 'estudiante_codigo', 'studentCode') and isinstance(valor, str) \
                    and valor.startswith('1') and len(valor) == 8:
                encontrados.append(valor)
            else:
                encontrados.extend(codigos_estudiantes(valor))
    elif isinstance(datos, list):
        for valor in datos:
            encontrados.extend(codigos_estudiantes(valor))
    return encontrados


class UsuarioSAT(HttpUser):
    abstract = True
    wait_time = between(1, 4)  # tiempo de "lectura" entre acciones
    correos: list[str] = []

    def on_start(self):
        self.correo = random.choice(self.correos)
        token = SESIONES.get(self.correo)  # sesión abierta de antemano: el frontend reutiliza su JWT
        if token is None:
            resp = self.client.post('/api/usuarios/login/', json={'email': self.correo, 'password': CONTRASENA},
                                    name='login')
            resp.raise_for_status()
            token = SESIONES[self.correo] = resp.json()['token']
        self.client.headers['Authorization'] = f"Bearer {token}"
        self.client.get('/api/usuarios/me/', name='me')
        self.estudiantes = []

    def get(self, url, nombre, **kwargs):
        return self.client.get(url, name=nombre, **kwargs)

    def ver_ficha(self, codigo):
        """Las llamadas que hace la pantalla de la ficha del estudiante."""
        self.get(f'{ACADEMICO}/students/{codigo}/', 'ficha: detalle')
        self.get(f'{ACADEMICO}/students/{codigo}/indicators/', 'ficha: indicadores')
        self.get(f'{ACADEMICO}/students/{codigo}/history/', 'ficha: historial')
        self.get(f'{ACADEMICO}/students/{codigo}/intervenciones/', 'ficha: intervenciones')

    def ver_alertas(self, estado='activa', tipo='all'):
        resp = self.get(f'{ALERTAS}/?estado={estado}&tipo_regla={tipo}', 'alertas: listado')
        if resp.ok:
            self.estudiantes = codigos_estudiantes(resp.json()) or self.estudiantes
        return resp


class Docente(UsuarioSAT):
    weight = 6
    correos = [f'docente{i:02d}@ufps.edu.co' for i in range(1, DOCENTES + 1)]

    def on_start(self):
        super().on_start()
        self.cursos = []
        self.panel()

    @task(4)
    def panel(self):
        resp = self.get(f'{ACADEMICO}/teacher/dashboard/?page=1&page_size=100', 'docente: panel')
        if resp.ok:
            self.cursos = [c['curso_id'] for c in resp.json().get('cursos', [])] or self.cursos

    @task(3)
    def estudiantes_de_un_curso(self):
        if not self.cursos:
            return
        resp = self.get(f'{ACADEMICO}/teacher/course/{random.choice(self.cursos)}/students/?page=1&page_size=5',
                        'docente: estudiantes del curso')
        if resp.ok:
            self.estudiantes = codigos_estudiantes(resp.json()) or self.estudiantes

    @task(2)
    def tomar_asistencia(self):
        if not self.cursos:
            return
        curso = random.choice(self.cursos)
        url = f'{ACADEMICO}/cursos/{curso}/asistencia/'
        resp = self.get(f'{url}?fecha=2026-09-29', 'docente: asistencia (consulta)')
        if not resp.ok:
            return
        codigos = codigos_estudiantes(resp.json())
        if codigos:
            # Vuelve a guardar la última clase (upsert): no crece la base entre corridas
            registros = [{'codigo_estudiante': c, 'estado': random.choice(['ASISTIO'] * 9 + ['FALTA']),
                          'observacion': None} for c in codigos]
            self.client.post(url, json={'fecha': '2026-09-29', 'registros': registros},
                             name='docente: asistencia (guardar)')

    @task(3)
    def alertas(self):
        self.ver_alertas()

    @task(2)
    def ficha(self):
        if self.estudiantes:
            self.ver_ficha(random.choice(self.estudiantes))

    @task(1)
    def indicadores_cursos(self):
        self.get(f'{ACADEMICO}/courses/indicators/?page=1&page_size=10&periodo_anio=todos&periodo_semestre=1', 'cursos: indicadores')


class Bienestar(UsuarioSAT):
    weight = 2
    correos = ['bienestar1@ufps.edu.co', 'bienestar2@ufps.edu.co']

    @task(4)
    def alertas(self):
        self.ver_alertas(tipo=random.choice(['all', 'all', 'PROMEDIO', 'CORTE', 'INASISTENCIA']))

    @task(1)
    def alertas_en_seguimiento(self):
        self.ver_alertas(estado='en_seguimiento')

    @task(3)
    def ficha(self):
        if self.estudiantes:
            codigo = random.choice(self.estudiantes)
            self.ver_ficha(codigo)
            self.get(f'{ACADEMICO}/students/{codigo}/asistencia/', 'ficha: asistencia')

    @task(1)
    def notificaciones(self):
        self.get(f'{ALERTAS}/notificaciones/internas/', 'notificaciones')


class Director(UsuarioSAT):
    weight = 1
    correos = ['director@ufps.edu.co']

    @task(3)
    def directorio(self):
        params = random.choice([
            'page=1&page_size=15',
            f'page={random.randint(1, 50)}&page_size=15',
            'page=1&page_size=15&search=Estudiante 01',
            f'page=1&page_size=15&semester={random.randint(1, 10)}',
            'page=1&page_size=15&risk=high',
        ])
        resp = self.get(f'{ACADEMICO}/students/?{params}', 'estudiantes: directorio')
        if resp.ok:
            self.estudiantes = codigos_estudiantes(resp.json()) or self.estudiantes

    @task(2)
    def ficha(self):
        if self.estudiantes:
            self.ver_ficha(random.choice(self.estudiantes))

    @task(1)
    def indicadores_cursos(self):
        self.get(f'{ACADEMICO}/courses/indicators/?page=1&page_size=10&periodo_anio=todos&periodo_semestre=1', 'cursos: indicadores')

    @task(1)
    def reporte(self):
        tipo = random.choice(['riesgo-estudiantil', 'resumen-alertas', 'reprobacion-cursos'])
        self.get(f'{ALERTAS}/reportes/?tipo={tipo}', 'reportes: datos')


class Administrador(UsuarioSAT):
    weight = 1
    correos = ['admin@ufps.edu.co']

    @task(2)
    def panel_estrategico(self):
        self.get(f'{ACADEMICO}/indicadores/', 'director: indicadores')

    @task(1)
    def bitacoras(self):
        self.get(f'{ACADEMICO}/bitacora/', 'admin: bitácora importaciones')
        self.get('/api/usuarios/auditoria/', 'admin: auditoría')

    @task(1)
    def reglas_y_procesos(self):
        self.get(f'{ALERTAS}/reglas/', 'admin: reglas')
        self.get(f'{ALERTAS}/reevaluacion/ejecuciones/?limite=20', 'admin: ejecuciones')
        self.get(f'{ALERTAS}/recordatorios/casos-sin-seguimiento/', 'admin: casos sin seguimiento')

    @task(2)
    def alertas(self):
        self.ver_alertas()


@events.test_start.add_listener
def abrir_sesiones(environment, **_kwargs):
    """Inicia sesión una vez por cuenta (de a una) antes de que arranquen los usuarios simulados."""
    if not environment.host:
        return
    import requests
    cuentas = {c for clase in (Docente, Bienestar, Director, Administrador) for c in clase.correos}
    for correo in sorted(cuentas):
        try:
            resp = requests.post(f'{environment.host}/api/usuarios/login/',
                                 json={'email': correo, 'password': CONTRASENA}, timeout=120)
            if resp.ok:
                SESIONES[correo] = resp.json()['token']
        except requests.RequestException:
            pass  # on_start vuelve a intentar con login normal


@events.quitting.add_listener
def verificar_umbrales(environment, **_kwargs):
    """Marca la corrida como fallida si algún endpoint supera los umbrales."""
    stats = environment.stats
    incumplidos = []
    total = stats.total
    if total.num_requests and total.fail_ratio > UMBRAL_ERRORES:
        incumplidos.append(f'errores {total.fail_ratio:.1%} > {UMBRAL_ERRORES:.0%}')
    for entrada in stats.entries.values():
        if not entrada.num_requests or entrada.name == 'login':
            continue  # el login es lento a propósito (hash de contraseña) y se hace una vez por sesión
        umbral = UMBRAL_P95_REPORTES_MS if entrada.name.startswith('reportes') else UMBRAL_P95_MS
        p95 = entrada.get_response_time_percentile(0.95)
        if p95 > umbral:
            incumplidos.append(f'{entrada.method} {entrada.name}: p95 {p95:.0f} ms > {umbral:.0f} ms')
    if incumplidos:
        print('\nUMBRALES INCUMPLIDOS:\n  - ' + '\n  - '.join(incumplidos))
        environment.process_exit_code = 1
    else:
        print('\nTodos los endpoints cumplen los umbrales.')
