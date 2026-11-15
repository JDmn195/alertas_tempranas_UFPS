"""SDAT-323: expiración, revocación y preservación de usuarios al migrar."""
import json
from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from usuarios.models import Auditoria, Usuario


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SesionesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario = Usuario.objects.create(
            nombre='Usuario de prueba', correo='sesion@ufps.edu.co', rol='DOCENTE',
        )
        self.usuario.set_password('Clave-de-prueba-2026')
        self.usuario.save()

    def login(self, usuario=None):
        usuario = usuario or self.usuario
        respuesta = self.client.post(reverse('login'), data=json.dumps({
            'email': usuario.correo, 'password': 'Clave-de-prueba-2026',
        }), content_type='application/json')
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.json()['token']

    def consultar(self, token):
        return self.client.get(reverse('sesion_actual'), HTTP_AUTHORIZATION=f'Bearer {token}')

    def logout(self, token):
        return self.client.post(reverse('cerrar_sesion'), HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_nuevas_sesiones_duran_ocho_horas(self):
        datos = jwt.decode(self.login(), settings.SECRET_KEY, algorithms=['HS256'])
        self.assertAlmostEqual(datos['exp'] - datos['iat'], 8 * 3600, delta=1)
        self.assertEqual(datos['version_sesion'], 0)

    def test_logout_revoca_tokens_nuevos_y_anteriores_y_permite_volver_a_entrar(self):
        primero = self.login()
        ahora = datetime.now(timezone.utc)
        anterior = jwt.encode({'user_id': self.usuario.pk, 'iat': ahora,
                               'exp': ahora + timedelta(days=1)}, settings.SECRET_KEY, algorithm='HS256')
        self.assertEqual(self.consultar(primero).status_code, 200)
        self.assertEqual(self.consultar(anterior).status_code, 200)
        self.assertEqual(self.logout(primero).status_code, 200)
        self.assertEqual(self.consultar(primero).status_code, 401)
        self.assertEqual(self.consultar(anterior).status_code, 401)
        self.assertTrue(Auditoria.objects.filter(usuario=self.usuario, tipo_accion='LOGOUT').exists())
        nuevo = self.login()
        self.assertEqual(self.consultar(nuevo).status_code, 200)
        self.assertEqual(jwt.decode(nuevo, settings.SECRET_KEY, algorithms=['HS256'])['version_sesion'], 1)

    def test_logout_disponible_para_los_cinco_roles(self):
        for rol, _ in Usuario.ROL_CHOICES:
            with self.subTest(rol=rol):
                self.usuario.rol = rol
                self.usuario.save(update_fields=['rol'])
                token = self.login()
                self.assertEqual(self.logout(token).status_code, 200)
                self.assertEqual(self.consultar(token).status_code, 401)

    def test_logout_requiere_post_y_autenticacion(self):
        self.assertEqual(self.client.get(reverse('cerrar_sesion')).status_code, 405)
        self.assertEqual(self.client.post(reverse('cerrar_sesion')).status_code, 401)


class MigracionSesionTests(TransactionTestCase):
    anterior = ('usuarios', '0014_solicitud_acompanamiento')
    actual = ('usuarios', '0015_version_sesion')

    def tearDown(self):
        MigrationExecutor(connection).migrate([self.actual])
        super().tearDown()

    def test_la_migracion_y_su_reversion_preservan_los_datos_anteriores(self):
        ejecutor = MigrationExecutor(connection)
        ejecutor.migrate([self.anterior])
        anterior = ejecutor.loader.project_state([self.anterior]).apps.get_model('usuarios', 'Usuario')
        usuario = anterior.objects.create(nombre='Registro previo', correo='previo@ufps.edu.co',
                                          rol='DIRECTOR', contrasena='!sin-contrasena-utilizable')
        ejecutor = MigrationExecutor(connection)
        ejecutor.migrate([self.actual])
        actual = ejecutor.loader.project_state([self.actual]).apps.get_model('usuarios', 'Usuario')
        conservado = actual.objects.get(pk=usuario.pk)
        self.assertEqual(conservado.version_sesion, 0)
        self.assertEqual(conservado.correo, usuario.correo)
        self.assertEqual(conservado.rol, usuario.rol)
        self.assertEqual(conservado.contrasena, usuario.contrasena)
        MigrationExecutor(connection).migrate([self.anterior])
        conservado = anterior.objects.get(pk=usuario.pk)
        self.assertEqual(conservado.nombre, usuario.nombre)
        self.assertEqual(conservado.contrasena, usuario.contrasena)
