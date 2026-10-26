"""
Flujo del portal del estudiante (HU-37): el administrador crea la cuenta, el
estudiante define su contraseña con la recuperación, inicia sesión, consulta su
riesgo y no puede consultar la información de otro estudiante.
"""
import re

from django.core import mail
from django.urls import reverse

from academico.models import Estudiante
from usuarios.models import Auditoria, Usuario

from .base import CONTRASENA, IntegracionTestCase


class FlujoPortalEstudianteTests(IntegracionTestCase):

    def setUp(self):
        super().setUp()
        self.otro = Estudiante.objects.create(
            codigo='1152002', nombre='Luis Gómez', tipo_documento='CC', numero_documento='100200301',
            semestre=2, estado_matricula='ACTIVO', email_institucional='luis@ufps.edu.co',
        )

    def _definir_contrasena(self, correo):
        """El estudiante usa '¿Olvidaste tu contraseña?' para definir su primera contraseña."""
        resp = self.client.post(reverse('solicitar_recuperacion'), data={'email': correo},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        token = re.search(r'/reset-password/(\S+)', mail.outbox[-1].body).group(1)
        resp = self.client.post(reverse('cambiar_contrasena'), data={'token': token, 'password': CONTRASENA},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_estudiante_consulta_su_riesgo_y_no_el_de_otro(self):
        # 1. El administrador crea la cuenta del estudiante (sin contraseña utilizable)
        resp = self.api('post', 'cuenta_estudiante', self.admin, datos={}, args=[self.estudiante.codigo])
        self.assertEqual(resp.status_code, 201, resp.content)
        cuenta = Usuario.objects.get(correo='ana@ufps.edu.co')
        self.assertEqual(cuenta.rol, 'ESTUDIANTE')
        self.assertEqual(self.login(cuenta, self.estudiante.codigo).status_code, 401)
        self.assertEqual(self.login(cuenta, self.estudiante.numero_documento).status_code, 401)

        # 2. Define su contraseña e inicia sesión
        self._definir_contrasena(cuenta.correo)
        resp = self.login(cuenta)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['rol'], 'ESTUDIANTE')

        # 3. Sin cálculo todavía: nivel null con mensaje
        resp = self.api('get', 'portal-riesgo', cuenta)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()['riesgo']['nivel'])

        # 4. Se importa su historial (PPA 2.0 < 2.5) y consulta su riesgo
        resp = self.importar_historial(self.historial_en_riesgo())
        self.assertEqual(resp.status_code, 200, resp.content)
        resp = self.api('get', 'portal-riesgo', cuenta)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['estudiante']['codigo'], self.estudiante.codigo)
        self.assertEqual(data['riesgo']['nivel'], 'high')
        self.assertEqual(data['riesgo']['periodo'], '2026-1')
        causa = next(c for c in data['causas'] if c['tipo'] == 'PROMEDIO')
        self.assertEqual((causa['regla'], causa['umbral'], causa['valor']), ('Promedio Crítico', 2.5, 2.0))
        self.assertEqual(data['indicadores']['materias_reprobadas'], 1)

        # 5. Intenta consultar a otro estudiante: 403 y queda en la auditoría
        resp = self.api('get', 'detail-student', cuenta, args=[self.otro.codigo])
        self.assertEqual(resp.status_code, 403)
        self.assertNotIn('Luis', resp.content.decode())
        resp = self.api('get', 'portal-riesgo', cuenta, query={'codigo': self.otro.codigo})
        self.assertEqual(resp.json()['estudiante']['codigo'], self.estudiante.codigo)

        registro = Auditoria.objects.filter(usuario=cuenta, tipo_accion='ACCESO_DENEGADO').get()
        self.assertIn(self.otro.codigo, registro.detalle)
        self.assertTrue(Auditoria.objects.filter(tipo_accion='CREAR_CUENTA_ESTUDIANTE', usuario=self.admin).exists())
