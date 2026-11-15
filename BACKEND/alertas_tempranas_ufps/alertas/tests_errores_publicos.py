"""SDAT-327: los detalles de excepciones solo se escriben en el registro interno."""
import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from academico.models import Estudiante
from alertas.models import Regla
from portal.cuentas import ErrorCuentaEstudiante
from usuarios.models import Usuario
from usuarios.tests_cuentas_estudiante import _auth


class ErroresPublicosTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create(
            nombre='Administrador', correo='admin.errores@ufps.edu.co', rol='ADMINISTRADOR',
        )
        self.regla = Regla.objects.create(
            nombre='Promedio', tipo='PROMEDIO', valor_umbral=3, operador='<', nivel='medium',
        )
        self.detalle = 'detalle-interno-simulado-conexion-base-datos'

    def test_fallos_internos_al_crear_modificar_y_eliminar_reglas_no_se_exponen(self):
        operaciones = [
            ('post', reverse('listar_crear_reglas'), 'objects.create'),
            ('put', reverse('detalle_regla', args=[self.regla.pk]), 'save'),
            ('delete', reverse('detalle_regla', args=[self.regla.pk]), 'delete'),
        ]
        for metodo, url, operacion in operaciones:
            with self.subTest(metodo=metodo), patch(
                f'alertas.views.rule_views.Regla.{operacion}', side_effect=RuntimeError(self.detalle),
            ), self.assertLogs('alertas.views.rule_views', level='ERROR') as registro:
                respuesta = getattr(self.client, metodo)(
                    url, data=json.dumps({'nombre': 'Prueba'}),
                    content_type='application/json', **_auth(self.admin),
                )
            self.assertEqual(respuesta.status_code, 400)
            self.assertNotIn(self.detalle, respuesta.content.decode())
            self.assertIn(self.detalle, '\n'.join(registro.output))

    def test_validacion_de_negocio_de_regla_conserva_un_mensaje_util(self):
        with self.assertLogs('alertas.views.rule_views', level='WARNING'):
            respuesta = self.client.post(
                reverse('listar_crear_reglas'),
                data=json.dumps({'tipo': 'INASISTENCIA', 'valor_umbral': 200}),
                content_type='application/json', **_auth(self.admin),
            )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('umbral', respuesta.json()['error'])
        self.assertNotIn('200', respuesta.json()['error'])

    def test_fallos_de_valor_en_vista_previa_y_exportacion_no_se_exponen(self):
        for nombre in ['export-report-data', 'exportar-reporte']:
            with self.subTest(vista=nombre), patch(
                'alertas.views.report_views._get_report_data', side_effect=ValueError(self.detalle),
            ), self.assertLogs('alertas.views.report_views', level='WARNING') as registro:
                respuesta = self.client.get(reverse(nombre), **_auth(self.admin))
            self.assertEqual(respuesta.status_code, 400)
            self.assertEqual(respuesta.json(), {'error': 'Tipo de reporte no válido.'})
            self.assertIn(self.detalle, '\n'.join(registro.output))

    def test_conflicto_de_cuenta_no_expone_el_detalle_interno(self):
        estudiante = Estudiante.objects.create(
            codigo='1151999', nombre='Estudiante de prueba', tipo_documento='CC',
            numero_documento='1999', semestre=2, estado_matricula='ACTIVO',
            email_institucional='estudiante.prueba@ufps.edu.co',
        )
        with patch(
            'portal.cuentas.asociar_cuenta_estudiante', side_effect=ErrorCuentaEstudiante(self.detalle),
        ), self.assertLogs('usuarios.views', level='WARNING') as registro:
            respuesta = self.client.post(
                reverse('cuenta_estudiante', args=[estudiante.codigo]), data='{}',
                content_type='application/json', **_auth(self.admin),
            )
        self.assertEqual(respuesta.status_code, 409)
        self.assertNotIn(self.detalle, respuesta.content.decode())
        self.assertIn(self.detalle, '\n'.join(registro.output))
