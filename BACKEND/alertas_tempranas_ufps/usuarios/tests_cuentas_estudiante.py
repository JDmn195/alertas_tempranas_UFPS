"""
HU-37: Cuentas de estudiante gestionadas por el administrador y control de acceso
del portal (obtener_estudiante_autenticado y auditoría de requiere_rol).
"""
import json
from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings
from django.test import RequestFactory, TestCase
from django.urls import reverse

from academico.models import Estudiante
from usuarios.decorators import obtener_estudiante_autenticado
from usuarios.models import Auditoria, Usuario


def _auth(usuario):
    ahora = datetime.now(timezone.utc)
    token = jwt.encode({'user_id': usuario.id, 'exp': ahora + timedelta(days=1), 'iat': ahora},
                       settings.SECRET_KEY, algorithm='HS256')
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


def _cuenta_estudiante(correo):
    usuario = Usuario(nombre='Cuenta', correo=correo, rol='ESTUDIANTE')
    usuario.set_unusable_password()
    usuario.save()
    return usuario


class CuentaEstudianteAdminTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create(nombre='Admin', correo='admin@ufps.edu.co', rol='ADMINISTRADOR')
        self.estudiante = Estudiante.objects.create(
            codigo='1151001', nombre='Ana Pérez', tipo_documento='CC', numero_documento='1001',
            semestre=2, estado_matricula='ACTIVO', email_institucional='ana@ufps.edu.co',
        )
        self.url = reverse('cuenta_estudiante', args=[self.estudiante.codigo])

    def _post(self, datos=None, usuario=None):
        return self.client.post(self.url, data=json.dumps(datos or {}), content_type='application/json',
                                **_auth(usuario or self.admin))

    def test_crea_la_cuenta_con_el_correo_institucional(self):
        resp = self._post()

        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()['accion'], 'creada')
        self.assertNotIn('contrasena', json.dumps(resp.json()))
        self.estudiante.refresh_from_db()
        cuenta = self.estudiante.usuario
        self.assertEqual((cuenta.correo, cuenta.rol), ('ana@ufps.edu.co', 'ESTUDIANTE'))
        self.assertFalse(cuenta.check_password('1151001'))
        self.assertFalse(cuenta.check_password('1001'))
        registro = Auditoria.objects.get(tipo_accion='CREAR_CUENTA_ESTUDIANTE')
        self.assertEqual(registro.usuario, self.admin)
        self.assertIn('1151001', registro.detalle)

    def test_reasocia_una_cuenta_de_estudiante_libre(self):
        anterior = _cuenta_estudiante('vieja@ufps.edu.co')
        self.estudiante.usuario = anterior
        self.estudiante.save()
        libre = _cuenta_estudiante('ana.nueva@ufps.edu.co')

        resp = self._post({'correo': 'ana.nueva@ufps.edu.co'})

        self.assertEqual(resp.status_code, 200, resp.content)
        self.estudiante.refresh_from_db()
        self.assertEqual(self.estudiante.usuario, libre)
        registro = Auditoria.objects.get(tipo_accion='ASOCIAR_CUENTA_ESTUDIANTE')
        self.assertIn('vieja@ufps.edu.co', registro.detalle)

    def test_no_asocia_una_cuenta_del_personal(self):
        docente = Usuario.objects.create(nombre='Doc', correo='ana@ufps.edu.co', rol='DOCENTE')
        resp = self._post()

        self.assertEqual(resp.status_code, 409)
        docente.refresh_from_db()
        self.assertEqual(docente.rol, 'DOCENTE')
        self.estudiante.refresh_from_db()
        self.assertIsNone(self.estudiante.usuario)

    def test_no_asocia_una_cuenta_de_otro_estudiante(self):
        cuenta = _cuenta_estudiante('luis@ufps.edu.co')
        Estudiante.objects.create(codigo='1151002', nombre='Luis', tipo_documento='CC', numero_documento='1002',
                                  semestre=2, estado_matricula='ACTIVO', usuario=cuenta)
        resp = self._post({'correo': 'luis@ufps.edu.co'})

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(Estudiante.objects.get(codigo='1151002').usuario, cuenta)

    def test_rechaza_correo_no_institucional_y_estudiante_inexistente(self):
        self.assertEqual(self._post({'correo': 'ana@gmail.com'}).status_code, 409)
        resp = self.client.post(reverse('cuenta_estudiante', args=['000']), data='{}',
                                content_type='application/json', **_auth(self.admin))
        self.assertEqual(resp.status_code, 404)

    def test_solo_el_administrador(self):
        director = Usuario.objects.create(nombre='Dir', correo='dir@ufps.edu.co', rol='DIRECTOR')
        self.assertEqual(self._post(usuario=director).status_code, 403)
        self.assertEqual(self.client.post(self.url).status_code, 401)


class CrudUsuariosRolEstudianteTests(TestCase):
    """El CRUD general es solo para el personal: no crea cuentas ESTUDIANTE ni cambia su rol."""

    def setUp(self):
        self.admin = Usuario.objects.create(nombre='Admin', correo='admin@ufps.edu.co', rol='ADMINISTRADOR')
        self.cuenta = _cuenta_estudiante('ana@ufps.edu.co')
        self.docente = Usuario.objects.create(nombre='Doc', correo='doc@ufps.edu.co', rol='DOCENTE')

    def _put(self, usuario, datos):
        return self.client.put(reverse('actualizar_usuario', args=[usuario.id]), data=json.dumps(datos),
                               content_type='application/json', **_auth(self.admin))

    def test_no_crea_usuarios_estudiante(self):
        resp = self.client.post(reverse('crear_usuario'), data=json.dumps(
            {'nombre': 'X', 'correo': 'x@ufps.edu.co', 'rol': 'ESTUDIANTE'}), content_type='application/json',
            **_auth(self.admin))
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Usuario.objects.filter(correo='x@ufps.edu.co').exists())

    def test_no_convierte_personal_en_estudiante_ni_al_reves(self):
        self.assertEqual(self._put(self.docente, {'rol': 'ESTUDIANTE'}).status_code, 400)
        self.assertEqual(self._put(self.cuenta, {'rol': 'ADMINISTRADOR'}).status_code, 400)
        self.docente.refresh_from_db()
        self.cuenta.refresh_from_db()
        self.assertEqual((self.docente.rol, self.cuenta.rol), ('DOCENTE', 'ESTUDIANTE'))

    def test_edita_el_nombre_de_una_cuenta_de_estudiante(self):
        resp = self._put(self.cuenta, {'nombre': 'Ana María', 'rol': 'ESTUDIANTE'})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.nombre, 'Ana María')


class ObtenerEstudianteAutenticadoTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.cuenta = _cuenta_estudiante('ana@ufps.edu.co')
        self.estudiante = Estudiante.objects.create(
            codigo='1151001', nombre='Ana', tipo_documento='CC', numero_documento='1001',
            semestre=2, estado_matricula='ACTIVO', usuario=self.cuenta,
        )

    def _request(self, usuario=None, **params):
        extra = _auth(usuario) if usuario else {}
        return self.factory.get('/api/portal/riesgo/', params, **extra)

    def test_devuelve_el_estudiante_del_token_aunque_se_envie_otro_codigo(self):
        estudiante, error = obtener_estudiante_autenticado(self._request(self.cuenta, codigo='999'))
        self.assertIsNone(error)
        self.assertEqual(estudiante, self.estudiante)

    def test_sin_token_401(self):
        estudiante, error = obtener_estudiante_autenticado(self._request())
        self.assertIsNone(estudiante)
        self.assertEqual(error.status_code, 401)

    def test_rol_distinto_403_auditado(self):
        bienestar = Usuario.objects.create(nombre='B', correo='b@ufps.edu.co', rol='BIENESTAR')
        estudiante, error = obtener_estudiante_autenticado(self._request(bienestar))
        self.assertIsNone(estudiante)
        self.assertEqual(error.status_code, 403)
        self.assertTrue(Auditoria.objects.filter(usuario=bienestar, tipo_accion='ACCESO_DENEGADO').exists())

    def test_cuenta_sin_estudiante_403_auditado(self):
        huerfana = _cuenta_estudiante('h@ufps.edu.co')
        estudiante, error = obtener_estudiante_autenticado(self._request(huerfana))
        self.assertIsNone(estudiante)
        self.assertEqual(error.status_code, 403)
        self.assertEqual(Auditoria.objects.filter(usuario=huerfana, tipo_accion='ACCESO_DENEGADO').count(), 1)

    def test_cuenta_desactivada_401(self):
        self.cuenta.activo = False
        self.cuenta.save()
        _, error = obtener_estudiante_autenticado(self._request(self.cuenta))
        self.assertEqual(error.status_code, 401)


class ActivacionCuentaEstudianteTests(TestCase):
    """
    HU-37: el estudiante registrado (DIRPLAN) obtiene su cuenta solo, desde
    «¿Olvidaste tu contraseña?», con su correo institucional. Sin BREVO_API_KEY
    el enlace sale por send_mail (mail.outbox).
    """

    def setUp(self):
        self.estudiante = Estudiante.objects.create(
            codigo='1151001', nombre='Ana Pérez', tipo_documento='CC', numero_documento='1001',
            semestre=2, estado_matricula='ACTIVO', email_institucional='Ana.Perez@ufps.edu.co',
        )

    def _solicitar(self, correo):
        import os
        from unittest.mock import patch
        entorno = {k: v for k, v in os.environ.items() if k != 'BREVO_API_KEY'}
        with patch.dict('os.environ', entorno, clear=True):
            return self.client.post(reverse('solicitar_recuperacion'), data=json.dumps({'email': correo}),
                                    content_type='application/json')

    def _token_del_correo(self):
        import re
        from django.core import mail
        return re.search(r'/reset-password/(\S+)', mail.outbox[-1].body).group(1)

    def test_estudiante_sin_cuenta_la_activa_y_define_su_contrasena(self):
        from django.core import mail
        resp = self._solicitar('ana.perez@ufps.edu.co')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['mensaje'], 'Si el correo existe, se enviarán instrucciones.')

        self.estudiante.refresh_from_db()
        cuenta = self.estudiante.usuario
        self.assertIsNotNone(cuenta)
        self.assertEqual((cuenta.rol, cuenta.correo), ('ESTUDIANTE', 'ana.perez@ufps.edu.co'))
        self.assertTrue(cuenta.contrasena.startswith('!'))  # sin contraseña utilizable
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ana.perez@ufps.edu.co'])
        self.assertTrue(Auditoria.objects.filter(tipo_accion='CREAR_CUENTA_ESTUDIANTE',
                                                 detalle__contains='1151001').exists())

        resp = self.client.post(reverse('cambiar_contrasena'),
                                data=json.dumps({'token': self._token_del_correo(), 'password': 'Clave-nueva-2026'}),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        resp = self.client.post(reverse('login'),
                                data=json.dumps({'email': 'ana.perez@ufps.edu.co', 'password': 'Clave-nueva-2026'}),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['rol'], 'ESTUDIANTE')

    def test_segunda_solicitud_no_crea_otra_cuenta(self):
        from django.core import mail
        self._solicitar('ana.perez@ufps.edu.co')
        self._solicitar('ana.perez@ufps.edu.co')
        self.assertEqual(Usuario.objects.filter(rol='ESTUDIANTE').count(), 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_correo_que_no_es_de_un_estudiante_no_crea_nada(self):
        from django.core import mail
        for correo in ('otro@ufps.edu.co', 'ana.perez@gmail.com', ''):
            resp = self._solicitar(correo)
            self.assertIn(resp.status_code, (200,))
        self.assertFalse(Usuario.objects.filter(rol='ESTUDIANTE').exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_correo_institucional_externo_al_dominio_no_activa(self):
        Estudiante.objects.filter(pk=self.estudiante.pk).update(email_institucional='ana@gmail.com')
        self._solicitar('ana@gmail.com')
        self.assertFalse(Usuario.objects.filter(rol='ESTUDIANTE').exists())

    def test_correo_compartido_por_dos_estudiantes_no_activa(self):
        Estudiante.objects.create(
            codigo='1151002', nombre='Otra', tipo_documento='CC', numero_documento='1002',
            semestre=2, estado_matricula='ACTIVO', email_institucional='ana.perez@ufps.edu.co',
        )
        self._solicitar('ana.perez@ufps.edu.co')
        self.assertFalse(Usuario.objects.filter(rol='ESTUDIANTE').exists())

    def test_cuenta_desactivada_no_se_reactiva_ni_se_duplica(self):
        from django.core import mail
        cuenta = _cuenta_estudiante('ana.perez@ufps.edu.co')
        cuenta.activo = False
        cuenta.save()
        self.estudiante.usuario = cuenta
        self.estudiante.save()
        self._solicitar('ana.perez@ufps.edu.co')
        cuenta.refresh_from_db()
        self.assertFalse(cuenta.activo)
        self.assertEqual(Usuario.objects.filter(rol='ESTUDIANTE').count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_correo_de_una_cuenta_del_personal_inactiva_no_se_convierte_en_estudiante(self):
        personal = Usuario.objects.create(nombre='Docente', correo='ana.perez@ufps.edu.co', rol='DOCENTE', activo=False)
        self._solicitar('ana.perez@ufps.edu.co')
        personal.refresh_from_db()
        self.assertEqual(personal.rol, 'DOCENTE')
        self.estudiante.refresh_from_db()
        self.assertIsNone(self.estudiante.usuario)
