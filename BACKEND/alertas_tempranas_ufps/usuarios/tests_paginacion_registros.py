"""SDAT-341: auditoría, historial de notificaciones y bitácora paginados en servidor."""
from django.test import TestCase
from django.urls import reverse

from academico.models import BitacoraImportacion
from alertas.models import NotificacionHistorial
from usuarios.models import Auditoria, Usuario
from usuarios.tests_cuentas_estudiante import _auth


class PaginacionRegistrosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create(nombre='Admin', correo='admin.reg@ufps.edu.co',
                                           rol='ADMINISTRADOR', contrasena='!')
        cls.docente = Usuario.objects.create(nombre='Docente', correo='doc.reg@ufps.edu.co',
                                             rol='DOCENTE', contrasena='!')
        for i in range(5):
            Auditoria.objects.create(usuario=cls.admin, tipo_accion='CREAR_USUARIO', detalle=f'a{i}')
            NotificacionHistorial.objects.create(destinatario=f'x{i}@ufps.edu.co', canal='EMAIL',
                                                 tipo='ALERTA', resultado='exitoso')
            BitacoraImportacion.objects.create(usuario=cls.admin, archivo_nombre=f'f{i}.xlsx', tipo='pensum')

    def get(self, nombre, params=None, usuario=None):
        return self.client.get(reverse(nombre), params or {}, **_auth(usuario or self.admin))

    def test_cada_listado_devuelve_solo_la_pagina_con_total(self):
        casos = [('listar_auditoria', 'registros'), ('historial-notificaciones', 'historial'),
                 ('list-bitacoras', 'data')]
        for nombre, clave in casos:
            with self.subTest(nombre):
                datos = self.get(nombre, {'page': 2, 'page_size': 2}).json()
                self.assertEqual(len(datos[clave]), 2)
                self.assertEqual((datos['page'], datos['pages'], datos['total']), (2, 3, 5))

    def test_sin_parametros_se_conserva_la_respuesta_completa(self):
        self.assertEqual(len(self.get('listar_auditoria').json()['registros']), 5)

    def test_el_filtro_se_conserva_al_paginar(self):
        Auditoria.objects.create(usuario=self.admin, tipo_accion='CREAR_REGLA', detalle='r')
        datos = self.get('listar_auditoria', {'page': 1, 'page_size': 2, 'tipo_accion': 'CREAR_REGLA'}).json()
        self.assertEqual(datos['total'], 1)

    def test_docente_sigue_denegado(self):
        for nombre in ('listar_auditoria', 'historial-notificaciones', 'list-bitacoras'):
            self.assertEqual(self.get(nombre, {'page': 1}, self.docente).status_code, 403)
