"""SDAT-336 (B09): las reglas de riesgo rechazan umbrales fuera de escala y datos incompletos."""
import json

from django.test import TestCase
from django.urls import reverse

from alertas.models import Regla
from usuarios.models import Usuario
from usuarios.tests_cuentas_estudiante import _auth


class ValidacionReglasTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create(nombre='Admin', correo='admin.reglas@ufps.edu.co', rol='ADMINISTRADOR')

    def _crear(self, **datos):
        cuerpo = {'nombre': 'Promedio bajo', 'tipo': 'PROMEDIO', 'valor_umbral': 3.0, 'operador': '<',
                  'nivel': 'high', **datos}
        return self.client.post(reverse('listar_crear_reglas'), data=json.dumps(cuerpo),
                                content_type='application/json', **_auth(self.admin))

    def test_promedio_dentro_de_la_escala_se_crea(self):
        self.assertEqual(self._crear().status_code, 201)
        self.assertEqual(self._crear(nombre='Borde', valor_umbral=5).status_code, 201)

    def test_promedio_fuera_de_la_escala_0_a_5_se_rechaza(self):
        antes = Regla.objects.count()
        for umbral in (6.0, -1, 5.01, 'abc', None):
            with self.subTest(umbral=umbral):
                self.assertEqual(self._crear(valor_umbral=umbral).status_code, 400)
        self.assertEqual(Regla.objects.count(), antes)

    def test_actualizar_promedio_fuera_de_escala_se_rechaza(self):
        regla = Regla.objects.create(nombre='P', tipo='PROMEDIO', valor_umbral=3, operador='<', nivel='low')
        resp = self.client.put(reverse('detalle_regla', args=[regla.pk]), data=json.dumps({'valor_umbral': 6}),
                               content_type='application/json', **_auth(self.admin))
        self.assertEqual(resp.status_code, 400)
        regla.refresh_from_db()
        self.assertEqual(float(regla.valor_umbral), 3.0)

    def test_nombre_vacio_operador_o_nivel_invalidos_se_rechazan(self):
        for cambio in ({'nombre': '   '}, {'nombre': None}, {'operador': '!='}, {'nivel': 'critico'}):
            with self.subTest(cambio=cambio):
                self.assertEqual(self._crear(**cambio).status_code, 400)

    def test_reprobacion_y_atraso_no_aceptan_umbral_negativo(self):
        self.assertEqual(self._crear(tipo='REPROBACION', valor_umbral=-1).status_code, 400)
        self.assertEqual(self._crear(tipo='ATRASO', valor_umbral=2, operador='>=').status_code, 201)
