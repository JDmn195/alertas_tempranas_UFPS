"""
HU-37: El rol ESTUDIANTE no accede a ningún endpoint del personal, y los intentos
de consultar a otro estudiante se rechazan y quedan en la auditoría. El personal
sigue accediendo como antes a los endpoints de estudiantes.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import jwt
from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from academico.models import Curso, Docente, Estudiante, Materia, Nota, Periodo
from alertas.models import Alerta, Regla
from usuarios.models import Auditoria, Usuario

ENDPOINTS_ESTUDIANTE = [
    'detail-student', 'student-indicators', 'student-history', 'student-interventions',
    'student-attendance', 'student-grades-by-cut',
]


def _auth(usuario):
    ahora = datetime.now(timezone.utc)
    token = jwt.encode({'user_id': usuario.id, 'exp': ahora + timedelta(days=1), 'iat': ahora},
                       settings.SECRET_KEY, algorithm='HS256')
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


class AccesoRolEstudianteTests(TestCase):
    def setUp(self):
        self.cuenta = Usuario(nombre='Ana', correo='ana@ufps.edu.co', rol='ESTUDIANTE')
        self.cuenta.set_unusable_password()
        self.cuenta.save()
        self.propio = Estudiante.objects.create(
            codigo='1151001', nombre='Ana', tipo_documento='CC', numero_documento='1001',
            semestre=2, estado_matricula='ACTIVO', usuario=self.cuenta,
        )
        self.otro = Estudiante.objects.create(
            codigo='1151002', nombre='Luis', tipo_documento='CC', numero_documento='1002',
            semestre=2, estado_matricula='ACTIVO',
        )

        self.admin = Usuario.objects.create(nombre='Admin', correo='admin@ufps.edu.co', rol='ADMINISTRADOR')
        self.director = Usuario.objects.create(nombre='Dir', correo='dir@ufps.edu.co', rol='DIRECTOR')
        self.bienestar = Usuario.objects.create(nombre='Bien', correo='bien@ufps.edu.co', rol='BIENESTAR')
        self.usuario_docente = Usuario.objects.create(nombre='Doc', correo='doc@ufps.edu.co', rol='DOCENTE')
        docente = Docente.objects.create(codigo='D1', nombre='Doc', tipo_vinculacion='Planta', usuario=self.usuario_docente)
        materia = Materia.objects.create(codigo='1150101', nombre='Cálculo I', creditos=3, semestre=1)
        curso = Curso.objects.create(materia=materia, grupo='A', docente=docente)
        periodo = Periodo.objects.create(anio=2025, semestre=2)
        Nota.objects.create(estudiante=self.otro, curso=curso, periodo=periodo, definitiva=Decimal('3.5'))

    def _denegados(self):
        return Auditoria.objects.filter(usuario=self.cuenta, tipo_accion='ACCESO_DENEGADO')

    def test_endpoints_de_otro_estudiante_responden_403_y_quedan_en_auditoria(self):
        for nombre in ENDPOINTS_ESTUDIANTE:
            with self.subTest(endpoint=nombre):
                antes = self._denegados().count()
                resp = self.client.get(reverse(nombre, args=[self.otro.codigo]), **_auth(self.cuenta))
                self.assertEqual(resp.status_code, 403)
                self.assertNotIn(self.otro.nombre, resp.content.decode())
                self.assertEqual(self._denegados().count(), antes + 1)
                self.assertIn(f'estudiante {self.otro.codigo}', self._denegados().order_by('-id').first().detalle)

    def test_endpoints_del_personal_con_su_propio_codigo_tambien_responden_403(self):
        """El estudiante consulta su información solo por el portal, no por los endpoints del personal."""
        for nombre in ENDPOINTS_ESTUDIANTE:
            with self.subTest(endpoint=nombre):
                resp = self.client.get(reverse(nombre, args=[self.propio.codigo]), **_auth(self.cuenta))
                self.assertEqual(resp.status_code, 403)
        # Con su propio código no se reporta un intento contra otro estudiante
        self.assertFalse(self._denegados().filter(detalle__contains='Intentó consultar').exists())
        self.assertEqual(self._denegados().count(), len(ENDPOINTS_ESTUDIANTE))

    def test_listado_de_estudiantes_responde_403(self):
        resp = self.client.get(reverse('list-students'), **_auth(self.cuenta))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self._denegados().count(), 1)

    def test_endpoints_del_personal_responden_403(self):
        regla = Regla.objects.create(nombre='Promedio', tipo='PROMEDIO', operador='<',
                                     valor_umbral=Decimal('3.0'), nivel='medium')
        alerta = Alerta.objects.create(estudiante=self.otro, regla=regla, estado='activa')
        llamadas = [
            ('get', reverse('listar-alertas')),
            ('post', reverse('generar-alertas')),
            ('post', reverse('cerrar-alerta', args=[alerta.id])),
            ('get', reverse('listar-intervenciones', args=[alerta.id])),
            ('get', reverse('listar_crear_reglas')),
            ('get', reverse('detalle_regla', args=[regla.id])),
            ('post', reverse('recalcular-riesgo-estudiante', args=[self.otro.codigo])),
            ('get', reverse('export-report-data')),
            ('get', reverse('notificaciones-internas')),
            ('post', reverse('import-students-dirplan')),
            ('post', reverse('import-history-individual')),
            ('post', reverse('import-pensum')),
            ('post', reverse('import-attendance')),
            ('get', reverse('list-bitacoras')),
            ('get', reverse('course-indicators')),
            ('get', reverse('director-indicadores')),
            ('get', reverse('teacher-dashboard')),
            ('get', reverse('listar_usuarios')),
            ('post', reverse('crear_usuario')),
            ('get', reverse('listar_auditoria')),
            ('post', reverse('cuenta_estudiante', args=[self.propio.codigo])),
        ]
        for metodo, url in llamadas:
            with self.subTest(url=url):
                resp = getattr(self.client, metodo)(url, **_auth(self.cuenta))
                self.assertEqual(resp.status_code, 403)
        self.assertEqual(self._denegados().count(), len(llamadas))
        alerta.refresh_from_db()
        self.assertEqual(alerta.estado, 'activa')

    def test_personal_sigue_accediendo_a_los_endpoints_de_estudiantes(self):
        for usuario in (self.admin, self.director, self.bienestar, self.usuario_docente):
            with self.subTest(rol=usuario.rol):
                resp = self.client.get(reverse('list-students'), **_auth(usuario))
                self.assertEqual(resp.status_code, 200)
                for nombre in ENDPOINTS_ESTUDIANTE:
                    resp = self.client.get(reverse(nombre, args=[self.otro.codigo]), **_auth(usuario))
                    self.assertEqual(resp.status_code, 200, f'{nombre}: {resp.content[:200]}')

    def test_docente_sigue_limitado_a_sus_cursos(self):
        resp = self.client.get(reverse('detail-student', args=[self.propio.codigo]), **_auth(self.usuario_docente))
        self.assertEqual(resp.status_code, 403)
