"""
Matriz de autorización: cada ruta de la API contra los cinco roles y sin sesión.

La tabla MATRIZ es la referencia acordada. Si se agrega una ruta y no se declara
aquí, la prueba falla: así ninguna ruta queda sin decisión de acceso.
"""
from django.test import override_settings
from django.urls import get_resolver, reverse

from usuarios.models import Auditoria, Usuario

from .base import CONTRASENA, IntegracionTestCase

ADMIN, DIRECTOR, BIENESTAR, DOCENTE, ESTUDIANTE = 'ADMINISTRADOR', 'DIRECTOR', 'BIENESTAR', 'DOCENTE', 'ESTUDIANTE'
PERSONAL = {ADMIN, DIRECTOR, BIENESTAR, DOCENTE}
ROLES = [ADMIN, DIRECTOR, BIENESTAR, DOCENTE, ESTUDIANTE]

PUBLICA = 'PUBLICA'    # no pide sesión (login y recuperación de contraseña)
CRON = 'CRON'          # solo con el encabezado X-Cron-Token
SESION = 'SESION'      # cualquier usuario con sesión

MATRIZ = {
    # usuarios
    'login': PUBLICA, 'solicitar_recuperacion': PUBLICA, 'cambiar_contrasena': PUBLICA,
    'cerrar_sesion': SESION, 'sesion_actual': SESION,
    'resumen_admin': {ADMIN}, 'listar_usuarios': {ADMIN}, 'crear_usuario': {ADMIN},
    'actualizar_usuario': {ADMIN}, 'desactivar_usuario': {ADMIN}, 'cuenta_estudiante': {ADMIN},
    'listar_auditoria': {ADMIN},
    # academico
    'list-students': PERSONAL, 'detail-student': PERSONAL, 'student-indicators': PERSONAL,
    'student-history': PERSONAL, 'student-interventions': PERSONAL, 'student-attendance': PERSONAL,
    'student-grades-by-cut': PERSONAL,
    'import-pensum': {ADMIN}, 'import-students-dirplan': {ADMIN}, 'import-history-individual': {ADMIN},
    'import-academic-offering': {ADMIN}, 'import-teachers': {ADMIN}, 'import-attendance': {ADMIN, DOCENTE},
    'course-indicators': PERSONAL, 'course-detail': PERSONAL,
    'teacher-dashboard': {DOCENTE}, 'teacher-course-students': {DOCENTE},
    'course-attendance': {ADMIN, DOCENTE}, 'course-absence': PERSONAL, 'course-absence-threshold': {ADMIN},
    'list-bitacoras': {ADMIN}, 'detail-bitacora': {ADMIN}, 'director-indicadores': {ADMIN, DIRECTOR},
    # alertas
    'listar-alertas': PERSONAL,
    'listar_crear_reglas': {ADMIN, DIRECTOR, BIENESTAR}, 'detalle_regla': {ADMIN, DIRECTOR, BIENESTAR},
    'generar-alertas': {ADMIN, DOCENTE, BIENESTAR}, 'evaluar-cortes': {ADMIN, DIRECTOR},
    'reevaluar-alertas': {ADMIN}, 'migrar-riesgo-periodos': {ADMIN},
    'reevaluacion-programada': CRON, 'reevaluacion-manual': {ADMIN},
    'reevaluacion-ejecuciones': {ADMIN, DIRECTOR}, 'reevaluacion-ejecucion-detalle': {ADMIN, DIRECTOR},
    'recordatorios-listar': {ADMIN, DIRECTOR}, 'recordatorios-configuracion': {ADMIN, DIRECTOR},
    'recordatorios-programada': CRON, 'recordatorios-manual': {ADMIN, DIRECTOR},
    'recordatorios-casos': {ADMIN, DIRECTOR},
    'solicitudes-listar': {ADMIN, DIRECTOR, BIENESTAR}, 'solicitudes-gestionar': {ADMIN, DIRECTOR, BIENESTAR},
    'recalcular-riesgo-estudiante': PERSONAL,
    'cerrar-alerta': {ADMIN, DOCENTE, BIENESTAR}, 'listar-intervenciones': PERSONAL,
    'registrar-intervencion': {ADMIN, DOCENTE, BIENESTAR},
    'gestionar-anotaciones': PERSONAL, 'eliminar-anotacion': PERSONAL,
    'concluir-intervencion': {ADMIN, DOCENTE, BIENESTAR},
    'listar-evidencias': PERSONAL, 'subir-evidencia': PERSONAL, 'eliminar-evidencia': PERSONAL,
    'exportar-reporte': PERSONAL, 'export-report-data': PERSONAL,
    'historial-notificaciones': {ADMIN}, 'notificaciones-internas': PERSONAL, 'marcar-leida': PERSONAL,
    # portal del estudiante
    'portal-riesgo': {ESTUDIANTE}, 'portal-evolucion': {ESTUDIANTE}, 'portal-alertas': {ESTUDIANTE},
    'portal-alerta-detalle': {ESTUDIANTE}, 'portal-intervenciones': {ESTUDIANTE},
    'portal-intervencion-detalle': {ESTUDIANTE}, 'portal-solicitudes': {ESTUDIANTE},
    'portal-solicitud-cancelar': {ESTUDIANTE}, 'portal-asistencia': {ESTUDIANTE},
}

METODOS = ['get', 'post', 'put', 'patch', 'delete']
INEXISTENTE = 999999  # los objetos no existen: solo se prueba la decisión de acceso


def rutas_api():
    """(nombre, ruta de ejemplo) de cada patrón bajo /api/."""
    rutas = []
    for prefijo in get_resolver().url_patterns:
        if not str(prefijo.pattern).startswith('api/'):
            continue
        for patron in prefijo.url_patterns:
            args = [INEXISTENTE] * len(patron.pattern.converters)
            rutas.append((patron.name, reverse(patron.name, args=args)))
    return rutas


class MatrizRolesTests(IntegracionTestCase):

    def setUp(self):
        super().setUp()
        self.api('post', 'cuenta_estudiante', self.admin, datos={}, args=[self.estudiante.codigo])
        cuenta = Usuario.objects.get(correo=self.estudiante.email_institucional)
        cuenta.set_password(CONTRASENA)
        cuenta.save()
        self.usuarios = {
            ADMIN: self.admin, DIRECTOR: self.director, BIENESTAR: self.bienestar,
            DOCENTE: self.usuario_docente, ESTUDIANTE: cuenta,
        }

    def _llamar(self, ruta, usuario=None):
        """Primera respuesta que no sea 405: prueba los métodos en orden, GET primero."""
        extra = {'HTTP_AUTHORIZATION': f'Bearer {self.token(usuario)}'} if usuario else {}
        for metodo in METODOS:
            cuerpo = {} if metodo == 'get' else {'data': '{}', 'content_type': 'application/json'}
            resp = getattr(self.client, metodo)(ruta, **cuerpo, **extra)
            if resp.status_code != 405:
                return resp
        return resp

    def test_toda_ruta_tiene_decision_de_acceso(self):
        nombres = {nombre for nombre, _ in rutas_api()}
        self.assertEqual(nombres - set(MATRIZ), set(), 'Rutas sin fila en MATRIZ')
        self.assertEqual(set(MATRIZ) - nombres, set(), 'Filas de MATRIZ sin ruta')

    def test_sin_sesion_responde_401(self):
        for nombre, ruta in rutas_api():
            if MATRIZ[nombre] in (PUBLICA, CRON):
                continue
            with self.subTest(ruta=nombre):
                self.assertEqual(self._llamar(ruta).status_code, 401)

    @override_settings(REEVALUACION_CRON_TOKEN='token-del-cron', RECORDATORIOS_CRON_TOKEN='token-del-cron')
    def test_rutas_programadas_exigen_el_token_del_cron(self):
        for nombre, ruta in rutas_api():
            if MATRIZ[nombre] != CRON:
                continue
            for rol, usuario in [(None, None)] + list(self.usuarios.items()):
                with self.subTest(ruta=nombre, rol=rol):
                    self.assertIn(self._llamar(ruta, usuario).status_code, (401, 403))

    def test_cada_rol_solo_entra_a_sus_rutas(self):
        for nombre, ruta in rutas_api():
            permitidos = MATRIZ[nombre]
            if permitidos in (PUBLICA, CRON) or nombre == 'cerrar_sesion':
                continue
            if permitidos == SESION:
                permitidos = set(ROLES)
            for rol, usuario in self.usuarios.items():
                with self.subTest(ruta=nombre, rol=rol):
                    denegados_antes = Auditoria.objects.filter(usuario=usuario, tipo_accion='ACCESO_DENEGADO').count()
                    codigo = self._llamar(ruta, usuario).status_code
                    if rol in permitidos:
                        self.assertNotIn(codigo, (401, 403))
                        self.assertLess(codigo, 500)
                    else:
                        self.assertEqual(codigo, 403)
                        self.assertEqual(
                            Auditoria.objects.filter(usuario=usuario, tipo_accion='ACCESO_DENEGADO').count(),
                            denegados_antes + 1, 'El acceso denegado no quedó en auditoría',
                        )

    def test_cerrar_sesion_esta_abierto_a_los_cinco_roles(self):
        for rol, usuario in self.usuarios.items():
            with self.subTest(rol=rol):
                self.assertNotIn(self._llamar(reverse('cerrar_sesion'), usuario).status_code, (401, 403))
