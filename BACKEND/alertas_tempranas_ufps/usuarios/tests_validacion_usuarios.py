"""SDAT-336 (B07): el alta de usuarios rechaza nombre vacío y correo incompleto."""
import json

from django.test import TestCase
from django.urls import reverse

from usuarios.models import Usuario
from usuarios.tests_cuentas_estudiante import _auth


class CrearUsuarioValidacionTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create(nombre='Admin', correo='admin.val@ufps.edu.co', rol='ADMINISTRADOR')

    def _crear(self, **datos):
        cuerpo = {'nombre': 'Martha Peñaranda', 'correo': 'martha.penaranda@ufps.edu.co', 'rol': 'DOCENTE', **datos}
        return self.client.post(reverse('crear_usuario'), data=json.dumps(cuerpo),
                                content_type='application/json', **_auth(self.admin))

    def test_usuario_valido_se_crea_con_nombre_sin_espacios_sobrantes(self):
        resp = self._crear(nombre='  Martha Peñaranda  ')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Usuario.objects.get(correo='martha.penaranda@ufps.edu.co').nombre, 'Martha Peñaranda')

    def test_nombre_de_solo_espacios_se_rechaza(self):
        for nombre in ('   ', '', None, 12):
            with self.subTest(nombre=nombre):
                self.assertEqual(self._crear(nombre=nombre).status_code, 400)
        self.assertFalse(Usuario.objects.filter(correo='martha.penaranda@ufps.edu.co').exists())

    def test_correo_sin_dominio_completo_se_rechaza(self):
        for correo in ('martha.penaranda@ufps', 'martha', '@ufps.edu.co', 'a b@ufps.edu.co', 5):
            with self.subTest(correo=correo):
                self.assertEqual(self._crear(correo=correo).status_code, 400)
        self.assertEqual(Usuario.objects.count(), 1)
