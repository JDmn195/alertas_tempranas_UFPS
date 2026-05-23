import json
from django.test import TestCase, Client
from django.urls import reverse
from usuarios.models import Usuario

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

    def test_listar_usuarios(self):
        url = reverse('listar_usuarios')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('usuarios', data)
        self.assertEqual(len(data['usuarios']), 2)

    def test_asignar_roles_exitoso(self):
        """Escenario 1: Asignación de rol exitosa (múltiples roles)."""
        url = reverse('gestionar_usuario', kwargs={'usuario_id': self.user.id})
        payload = {
            'roles': ['DOCENTE', 'DIRECTOR']
        }
        response = self.client.put(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['usuario']['roles'], ['DOCENTE', 'DIRECTOR'])
        
        # Verificar en BD
        self.user.refresh_from_db()
        self.assertEqual(self.user.rol, 'DOCENTE,DIRECTOR')

    def test_modificar_roles_exitoso(self):
        """Escenario 2: Modificación de roles."""
        # Primero asignamos unos roles
        self.user.rol = 'DOCENTE,DIRECTOR'
        self.user.save()
        
        url = reverse('gestionar_usuario', kwargs={'usuario_id': self.user.id})
        payload = {
            'roles': ['BIENESTAR']
        }
        response = self.client.put(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['usuario']['roles'], ['BIENESTAR'])
        
        # Verificar en BD
        self.user.refresh_from_db()
        self.assertEqual(self.user.rol, 'BIENESTAR')

    def test_usuario_sin_roles_error(self):
        """Escenario 3: Intentar guardar un usuario sin roles."""
        url = reverse('gestionar_usuario', kwargs={'usuario_id': self.user.id})
        payload = {
            'roles': []
        }
        response = self.client.put(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['error'], 'Debe asignar al menos un rol.')
        
        # Verificar en BD que no cambió
        self.user.refresh_from_db()
        self.assertEqual(self.user.rol, 'DOCENTE')

    def test_crear_usuario_exitoso(self):
        url = reverse('listar_usuarios')
        payload = {
            'nombre': 'Nuevo Usuario',
            'correo': 'nuevo@ufps.edu.co',
            'contrasena': '123456',
            'roles': ['DOCENTE']
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['usuario']['nombre'], 'Nuevo Usuario')
        self.assertEqual(data['usuario']['roles'], ['DOCENTE'])

    def test_crear_usuario_sin_roles_error(self):
        url = reverse('listar_usuarios')
        payload = {
            'nombre': 'Nuevo Usuario',
            'correo': 'nuevo@ufps.edu.co',
            'contrasena': '123456',
            'roles': []
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Debe asignar al menos un rol.')
