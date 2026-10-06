import json
import jwt
from datetime import datetime, timedelta, timezone
from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings
from django.core.cache import cache
from usuarios.models import Usuario


def _make_token(usuario):
    """Genera un JWT válido para el usuario dado."""
    payload = {
        'user_id': usuario.id,
        'exp': datetime.now(timezone.utc) + timedelta(days=1),
        'iat': datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


class UserManagementTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = Usuario.objects.create(
            nombre="Admin",
            correo="admin@ufps.edu.co",
            rol="ADMINISTRADOR",
            contrasena="123"
        )
        self.user = Usuario.objects.create(
            nombre="Juan Docente",
            correo="juan.docente@ufps.edu.co",
            rol="DOCENTE",
            contrasena="123"
        )
        self.admin_token = _make_token(self.admin)

    def _auth_headers(self):
        return {'HTTP_AUTHORIZATION': f'Bearer {self.admin_token}'}

    def test_listar_usuarios(self):
        url = reverse('listar_usuarios')
        response = self.client.get(url, **self._auth_headers())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('usuarios', data)
        self.assertEqual(len(data['usuarios']), 2)

    def test_asignar_roles_exitoso(self):
        """Escenario 1: Asignación de rol exitosa."""
        url = reverse('actualizar_usuario', kwargs={'usuario_id': self.user.id})
        payload = {'rol': 'DIRECTOR'}
        response = self.client.put(
            url,
            data=json.dumps(payload),
            content_type='application/json',
            **self._auth_headers()
        )
        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.assertEqual(self.user.rol, 'DIRECTOR')

    def test_modificar_roles_exitoso(self):
        """Escenario 2: Modificación de rol."""
        self.user.rol = 'DIRECTOR'
        self.user.save()

        url = reverse('actualizar_usuario', kwargs={'usuario_id': self.user.id})
        payload = {'rol': 'BIENESTAR'}
        response = self.client.put(
            url,
            data=json.dumps(payload),
            content_type='application/json',
            **self._auth_headers()
        )
        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.assertEqual(self.user.rol, 'BIENESTAR')

    def test_usuario_no_encontrado(self):
        """Actualizar un usuario inexistente retorna 404."""
        url = reverse('actualizar_usuario', kwargs={'usuario_id': 99999})
        payload = {'rol': 'DOCENTE'}
        response = self.client.put(
            url,
            data=json.dumps(payload),
            content_type='application/json',
            **self._auth_headers()
        )
        self.assertEqual(response.status_code, 404)

    def test_crear_usuario_exitoso(self):
        url = reverse('crear_usuario')
        payload = {
            'nombre': 'Nuevo Usuario',
            'correo': 'nuevo@ufps.edu.co',
            'rol': 'DOCENTE',
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
            **self._auth_headers()
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn('id', data)

    def test_crear_usuario_sin_campos_error(self):
        """Crear usuario sin campos obligatorios retorna 400."""
        url = reverse('crear_usuario')
        payload = {
            'nombre': 'Sin Correo',
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
            **self._auth_headers()
        )
        self.assertEqual(response.status_code, 400)


class AutenticacionTestCase(TestCase):
    """Contraseñas hasheadas, cambio obligatorio y enlaces de un solo uso."""

    CONTRASENA = 'Clave-segura-2026'

    def setUp(self):
        cache.clear()  # contador de intentos fallidos de login
        self.admin = Usuario(nombre='Admin', correo='admin@ufps.edu.co', rol='ADMINISTRADOR')
        self.admin.set_password(self.CONTRASENA)
        self.admin.save()

    def _login(self, correo, contrasena):
        return self.client.post(reverse('login'), data=json.dumps({'email': correo, 'password': contrasena}),
                                content_type='application/json')

    def _cambiar(self, **payload):
        return self.client.post(reverse('cambiar_contrasena'), data=json.dumps(payload),
                                content_type='application/json')

    def _token_recuperacion(self, usuario):
        from usuarios.views import _generar_token_cambio
        return _generar_token_cambio(usuario)

    def test_contrasena_se_guarda_hasheada(self):
        self.admin.refresh_from_db()
        self.assertNotEqual(self.admin.contrasena, self.CONTRASENA)
        self.assertTrue(self.admin.contrasena.startswith('pbkdf2_sha256$'))

    def test_login_valida_contra_el_hash(self):
        self.assertEqual(self._login('admin@ufps.edu.co', self.CONTRASENA).status_code, 200)
        self.assertEqual(self._login('admin@ufps.edu.co', 'otra').status_code, 401)
        self.assertEqual(self._login('noexiste@ufps.edu.co', self.CONTRASENA).status_code, 401)

    def test_no_se_puede_cambiar_contrasena_solo_con_user_id(self):
        resp = self._cambiar(user_id=self.admin.id, password='Tomada-la-cuenta-1')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self._login('admin@ufps.edu.co', 'Tomada-la-cuenta-1').status_code, 401)

    def test_enlace_de_recuperacion_solo_sirve_una_vez(self):
        token = self._token_recuperacion(self.admin)
        self.assertEqual(self._cambiar(token=token, password='Nueva-clave-2026').status_code, 200)
        resp = self._cambiar(token=token, password='Otra-clave-2026')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self._login('admin@ufps.edu.co', 'Nueva-clave-2026').status_code, 200)

    def test_rechaza_contrasenas_debiles(self):
        resp = self._cambiar(token=self._token_recuperacion(self.admin), password='123')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self._login('admin@ufps.edu.co', self.CONTRASENA).status_code, 200)

    def test_usuario_creado_recibe_temporal_y_debe_cambiarla(self):
        resp = self.client.post(
            reverse('crear_usuario'),
            data=json.dumps({'nombre': 'Nuevo', 'correo': 'nuevo@ufps.edu.co', 'rol': 'DOCENTE'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {_make_token(self.admin)}',
        )
        temporal = resp.json()['contrasena_temporal']
        self.assertNotEqual(temporal, 'nuevo@ufps.edu.co')
        self.assertEqual(self._login('nuevo@ufps.edu.co', 'nuevo@ufps.edu.co').status_code, 401)

        # Con la temporal no hay sesión, solo un token para cambiarla
        data = self._login('nuevo@ufps.edu.co', temporal).json()
        self.assertTrue(data['cambio_obligatorio'])
        self.assertNotIn('token', data)

        self.assertEqual(self._cambiar(token=data['token_cambio'], password='Mi-clave-propia-1').status_code, 200)
        data = self._login('nuevo@ufps.edu.co', 'Mi-clave-propia-1').json()
        self.assertFalse(data['cambio_obligatorio'])
        self.assertIn('token', data)

    def test_migracion_hashea_y_anula_contrasenas_predecibles(self):
        import importlib
        from django.apps import apps
        from academico.models import Docente
        migracion = importlib.import_module('usuarios.migrations.0009_hashear_contrasenas')

        propia = Usuario.objects.create(nombre='A', correo='a@ufps.edu.co', contrasena='Clave-propia-9')
        con_correo = Usuario.objects.create(nombre='B', correo='b@ufps.edu.co', contrasena='b@ufps.edu.co')
        docente = Usuario.objects.create(nombre='C', correo='c@ufps.edu.co', contrasena='D123')
        Docente.objects.create(codigo='D123', nombre='C', tipo_vinculacion='DOCENTE PLANTA', usuario=docente)

        migracion.hashear_contrasenas(apps, None)

        for u in (propia, con_correo, docente):
            u.refresh_from_db()
        self.assertTrue(propia.check_password('Clave-propia-9'))
        self.assertFalse(con_correo.check_password('b@ufps.edu.co'))
        self.assertFalse(docente.check_password('D123'))


class SesionActualTestCase(TestCase):

    def test_devuelve_el_rol_del_token(self):
        usuario = Usuario.objects.create(nombre='Doc', correo='doc@ufps.edu.co', rol='DOCENTE', contrasena='x')
        resp = self.client.get(reverse('sesion_actual'), HTTP_AUTHORIZATION=f'Bearer {_make_token(usuario)}')
        self.assertEqual(resp.json(), {'id': usuario.id, 'nombre': 'Doc', 'correo': 'doc@ufps.edu.co', 'rol': 'DOCENTE'})

    def test_sin_token_responde_401(self):
        self.assertEqual(self.client.get(reverse('sesion_actual')).status_code, 401)


class ValidacionRolTestCase(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create(nombre='Admin', correo='admin@ufps.edu.co', rol='ADMINISTRADOR')
        self.otro = Usuario.objects.create(nombre='Otro', correo='otro@ufps.edu.co', rol='DOCENTE')
        self.headers = {'HTTP_AUTHORIZATION': f'Bearer {_make_token(self.admin)}'}

    def test_crear_con_rol_inexistente_falla(self):
        resp = self.client.post(reverse('crear_usuario'), data=json.dumps(
            {'nombre': 'X', 'correo': 'x@ufps.edu.co', 'rol': 'ADMINISTRADORR'}),
            content_type='application/json', **self.headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Rol inválido', resp.json()['error'])
        self.assertFalse(Usuario.objects.filter(correo='x@ufps.edu.co').exists())

    def test_actualizar_con_rol_inexistente_falla(self):
        url = reverse('actualizar_usuario', kwargs={'usuario_id': self.otro.id})
        resp = self.client.put(url, data=json.dumps({'rol': 'SUPERUSUARIO'}),
                               content_type='application/json', **self.headers)
        self.assertEqual(resp.status_code, 400)
        self.otro.refresh_from_db()
        self.assertEqual(self.otro.rol, 'DOCENTE')

    def test_admin_no_puede_quitarse_su_propio_rol(self):
        url = reverse('actualizar_usuario', kwargs={'usuario_id': self.admin.id})
        resp = self.client.put(url, data=json.dumps({'rol': 'DOCENTE'}),
                               content_type='application/json', **self.headers)
        self.assertEqual(resp.status_code, 400)


class SeguridadSesionTestCase(TestCase):
    CONTRASENA = 'Clave-segura-2026'

    def setUp(self):
        cache.clear()
        self.usuario = Usuario(nombre='Ana', correo='ana@ufps.edu.co', rol='DIRECTOR')
        self.usuario.set_password(self.CONTRASENA)
        self.usuario.save()

    def _login(self, contrasena):
        return self.client.post(reverse('login'), data=json.dumps(
            {'email': 'ana@ufps.edu.co', 'password': contrasena}), content_type='application/json')

    def test_bloquea_tras_varios_intentos_fallidos(self):
        for _ in range(5):
            self.assertEqual(self._login('incorrecta').status_code, 401)
        # Bloqueado aunque ahora la contraseña sea la correcta
        self.assertEqual(self._login(self.CONTRASENA).status_code, 429)
        cache.clear()  # pasa la ventana de bloqueo
        self.assertEqual(self._login(self.CONTRASENA).status_code, 200)

    def test_login_exitoso_reinicia_el_contador(self):
        for _ in range(4):
            self._login('incorrecta')
        self.assertEqual(self._login(self.CONTRASENA).status_code, 200)
        for _ in range(4):
            self._login('incorrecta')
        self.assertEqual(self._login(self.CONTRASENA).status_code, 200)

    def test_cambiar_contrasena_invalida_tokens_anteriores(self):
        payload = {
            'user_id': self.usuario.id,
            'exp': datetime.now(timezone.utc) + timedelta(days=1),
            'iat': datetime.now(timezone.utc) - timedelta(minutes=5),
        }
        token_viejo = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
        me = lambda t: self.client.get(reverse('sesion_actual'), HTTP_AUTHORIZATION=f'Bearer {t}')
        self.assertEqual(me(token_viejo).status_code, 200)

        self.usuario.cambiar_contrasena('Otra-clave-segura-2026')

        self.assertEqual(me(token_viejo).status_code, 401)
        token_nuevo = self._login('Otra-clave-segura-2026').json()['token']
        self.assertEqual(me(token_nuevo).status_code, 200)
