import json
import jwt
from datetime import datetime, timedelta, timezone
from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings
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
