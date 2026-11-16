"""SDAT-333: los totales del directorio no dependen de la página ni del filtro de riesgo."""
from django.test import TestCase
from django.urls import reverse

from academico.models import Estudiante
from alertas.models import Alerta, Regla, RiesgoEstudiante
from usuarios.models import Usuario
from usuarios.tests_cuentas_estudiante import _auth


class ResumenEstudiantesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.director = Usuario.objects.create(nombre='Dir', correo='dir333@ufps.edu.co', rol='DIRECTOR',
                                              contrasena='!')
        regla = Regla.objects.create(nombre='R', tipo='PROMEDIO', operador='<', valor_umbral=3, nivel='medium')
        niveles = ['high', 'high', 'medium', 'low', 'low', 'low', None]
        for i, nivel in enumerate(niveles):
            e = Estudiante.objects.create(codigo=f'R333{i}', nombre=f'Estudiante {i}', tipo_documento='CC',
                numero_documento=f'333{i}', semestre=2, estado_matricula='ACTIVO')
            if nivel:
                RiesgoEstudiante.objects.create(estudiante=e, nivel_riesgo=nivel)
            Alerta.objects.create(estudiante=e, regla=regla, estado='activa')
        Alerta.objects.create(estudiante=e, regla=regla, estado='cerrada')

    def listar(self, **params):
        return self.client.get(reverse('list-students'), params, **_auth(self.director)).json()

    def test_totales_cubren_toda_la_poblacion_aunque_la_pagina_sea_corta(self):
        datos = self.listar(page=1, page_size=2)
        self.assertEqual(len(datos['results']), 2)
        self.assertEqual(datos['resumen'], {'total': 7, 'high': 2, 'medium': 1, 'low': 3, 'sin_dato': 1,
                                            'alertas_activas': 7, 'inactivos': 0})

    def test_el_filtro_de_riesgo_no_cambia_los_totales(self):
        datos = self.listar(risk='high', page_size=1)
        self.assertEqual(datos['total'], 2)
        self.assertEqual(datos['resumen']['total'], 7)
        self.assertEqual(datos['resumen']['low'], 3)
