"""SDAT-337: reportes con niveles en español, rango de fechas válido y PDF legible."""
from io import BytesIO
from unittest.mock import patch

import openpyxl
from django.test import TestCase
from django.urls import reverse

from alertas.views import report_views
from usuarios.models import Usuario
from usuarios.tests_cuentas_estudiante import _auth

FILAS = [{
    'code': '1151001', 'name': 'Ana Prueba', 'semester': 3, 'gpa': 2.5, 'alerts': 1,
    'risk': 'HIGH', 'program': 'systems', 'date': '2026-09-10',
}]


class ReportesTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create(
            nombre='Administrador', correo='admin.reportes@ufps.edu.co', rol='ADMINISTRADOR',
        )
        parche = patch(
            'alertas.views.report_views._get_report_data',
            side_effect=lambda *a, **k: [dict(f) for f in FILAS],
        )
        parche.start()
        self.addCleanup(parche.stop)

    def _exportar(self, **params):
        return self.client.get(reverse('exportar-reporte'), params, **_auth(self.admin))

    def test_exportar_exige_ambas_fechas(self):
        self.assertEqual(self._exportar(formato='excel').status_code, 400)
        self.assertEqual(self._exportar(formato='excel', fecha_desde='2026-07-01').status_code, 400)

    def test_exportar_rechaza_rango_invertido(self):
        r = self._exportar(formato='excel', fecha_desde='2026-12-31', fecha_hasta='2026-07-01')
        self.assertEqual(r.status_code, 400)

    def test_exportar_rechaza_fecha_mal_formada(self):
        r = self._exportar(formato='excel', fecha_desde='ayer', fecha_hasta='2026-07-01')
        self.assertEqual(r.status_code, 400)

    def test_exportacion_traduce_niveles_y_nombre_lleva_ambas_fechas(self):
        r = self._exportar(
            formato='excel', fecha_desde='2026-07-01', fecha_hasta='2026-12-31', riesgo='high',
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn('2026-07-01_2026-12-31', r['Content-Disposition'])
        hoja = openpyxl.load_workbook(BytesIO(r.content)).active
        texto = ' '.join(str(c.value) for fila in hoja.iter_rows() for c in fila if c.value)
        self.assertIn('ALTO', texto)
        self.assertNotIn('HIGH', texto)
        self.assertNotIn('Riesgo: high', texto)

    def test_vista_previa_devuelve_niveles_en_espanol(self):
        r = self.client.get(reverse('export-report-data'), **_auth(self.admin))
        self.assertEqual(r.json()['data'][0]['risk'], 'ALTO')

    def test_pdf_se_genera_con_rango_valido(self):
        r = self._exportar(formato='pdf', fecha_desde='2026-07-01', fecha_hasta='2026-12-31')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_anchos_pdf_no_dejan_columnas_cortas_ilegibles(self):
        encabezados = ['Fecha', 'Tipo', 'Observaciones']
        filas = [{'a': '2026-09-10', 'b': 'Tutoría', 'c': 'x' * 900}]
        anchos = report_views._anchos_columnas(encabezados, ['a', 'b', 'c'], filas, 700)
        self.assertAlmostEqual(sum(anchos), 700)
        self.assertGreaterEqual(anchos[0], 60)
        self.assertGreaterEqual(anchos[1], 60)
