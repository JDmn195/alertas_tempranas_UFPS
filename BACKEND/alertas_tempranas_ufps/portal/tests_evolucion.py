"""
HU-38: Evolución histórica del promedio del estudiante (GET /api/portal/evolucion/).
"""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from academico.models import Estudiante, Nota
from academico.tests_historial_promedios import EscenarioHistorial
from usuarios.models import Auditoria, Usuario

from .tests import _auth, _cuenta_estudiante


class EvolucionPropiaTests(EscenarioHistorial, TestCase):
    def setUp(self):
        self.url = reverse('portal-evolucion')
        self.cuenta = _cuenta_estudiante('ana@ufps.edu.co')

    def _get(self, usuario=None, **params):
        return self.client.get(self.url, params, **_auth(usuario or self.cuenta))

    def test_serie_con_tres_periodos(self):
        self.crear_escenario(usuario=self.cuenta)
        resp = self._get()

        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(data['serie'], [
            {'periodo': '2024-2', 'pps': 2.86, 'ppa': 2.86, 'creditos_cursados': 7, 'creditos_aprobados': 3},
            {'periodo': '2025-1', 'pps': 3.9, 'ppa': 3.29, 'creditos_cursados': 5, 'creditos_aprobados': 5},
            {'periodo': '2025-2', 'pps': 2.5, 'ppa': 3.13, 'creditos_cursados': 3, 'creditos_aprobados': 0},
        ])
        self.assertEqual(data['promedio_actual'], 3.13)
        self.assertEqual(data['variacion'], {'valor': -0.16, 'porcentaje': 4.9})
        self.assertEqual(data['tendencia'], 'baja')
        self.assertTrue(data['historia_suficiente'])
        self.assertIsNone(data['mensaje'])

    def test_tendencia_sube(self):
        estudiante = self.crear_escenario(usuario=self.cuenta)
        # Se recupera la materia perdida de 2025-2 → PPS 4.0, el PPA sube respecto a 2025-1
        Nota.objects.filter(estudiante=estudiante, curso__materia_id='ME').update(definitiva=Decimal('5.0'))
        data = self._get().json()
        self.assertEqual(data['tendencia'], 'sube')
        self.assertGreater(data['variacion']['valor'], 0)

    def test_materias_en_curso_no_afectan_ni_agregan_periodos(self):
        self.crear_escenario(usuario=self.cuenta, en_curso=True)
        data = self._get().json()

        # 2026-1 solo tiene materias en curso: no aparece y no cambia la tendencia
        self.assertEqual([p['periodo'] for p in data['serie']], ['2024-2', '2025-1', '2025-2'])
        self.assertEqual(data['serie'][-1]['pps'], 2.5)
        self.assertEqual(data['tendencia'], 'baja')

    def test_un_solo_periodo_sin_historia_suficiente(self):
        estudiante = self.crear_escenario(usuario=self.cuenta)
        Nota.objects.filter(estudiante=estudiante).exclude(periodo__anio=2024).delete()
        data = self._get().json()

        self.assertEqual(len(data['serie']), 1)
        self.assertEqual(data['serie'][0]['periodo'], '2024-2')
        self.assertEqual(data['promedio_actual'], 2.86)
        self.assertFalse(data['historia_suficiente'])
        self.assertIsNone(data['tendencia'])
        self.assertIsNone(data['variacion'])
        self.assertIn('un solo periodo', data['mensaje'])

    def test_sin_notas_serie_vacia_y_200(self):
        Estudiante.objects.create(codigo='1151001', nombre='Ana', tipo_documento='CC', numero_documento='1',
                                  semestre=1, estado_matricula='ACTIVO', usuario=self.cuenta)
        resp = self._get()

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['serie'], [])
        self.assertIsNone(data['promedio_actual'])
        self.assertFalse(data['historia_suficiente'])
        self.assertTrue(data['mensaje'])

    def test_coherente_con_la_ficha_academica(self):
        """Mismos PPS, PPA, créditos y promedio actual que la ficha del personal (indicators e history)."""
        estudiante = self.crear_escenario(usuario=self.cuenta, en_curso=True)
        admin = Usuario.objects.create(nombre='Admin', correo='admin@ufps.edu.co', rol='ADMINISTRADOR')
        portal = self._get().json()
        ficha = self.client.get(reverse('student-indicators', args=[estudiante.codigo]), **_auth(admin)).json()
        historial = self.client.get(reverse('student-history', args=[estudiante.codigo]), **_auth(admin)).json()

        evolucion_ficha = {p['periodo']: p for p in ficha['indicadores']['evolucion']}
        historial_ficha = {p['periodo']: p for p in historial['historial']}
        for punto in portal['serie']:
            with self.subTest(periodo=punto['periodo']):
                self.assertEqual(punto['pps'], evolucion_ficha[punto['periodo']]['pps'])
                self.assertEqual(punto['ppa'], evolucion_ficha[punto['periodo']]['ppa'])
                self.assertEqual(punto['pps'], historial_ficha[punto['periodo']]['promedio_semestre'])
                self.assertEqual(punto['creditos_aprobados'], historial_ficha[punto['periodo']]['creditos_aprobados'])
                self.assertEqual(punto['creditos_cursados'], historial_ficha[punto['periodo']]['creditos_intentados'])
        self.assertEqual(portal['promedio_actual'], ficha['indicadores']['promedio_acumulado'])

    def test_solo_su_propia_evolucion(self):
        self.crear_escenario(usuario=self.cuenta)
        otra_cuenta = _cuenta_estudiante('luis@ufps.edu.co')
        Estudiante.objects.create(codigo='1151002', nombre='Luis', tipo_documento='CC', numero_documento='2',
                                  semestre=1, estado_matricula='ACTIVO', usuario=otra_cuenta)

        # Luis no tiene notas: aunque pida el código de Ana, recibe su propia serie vacía
        data = self._get(otra_cuenta, codigo='1151001').json()
        self.assertEqual(data['serie'], [])
        self.assertEqual(len(self._get().json()['serie']), 3)

    def test_sin_token_401_y_sin_estudiante_asociado_403(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
        huerfana = _cuenta_estudiante('huerfana@ufps.edu.co')
        self.assertEqual(self._get(huerfana).status_code, 403)
        self.assertTrue(Auditoria.objects.filter(usuario=huerfana, tipo_accion='ACCESO_DENEGADO').exists())

    def test_personal_recibe_403(self):
        director = Usuario.objects.create(nombre='Dir', correo='dir@ufps.edu.co', rol='DIRECTOR')
        self.assertEqual(self._get(director).status_code, 403)

    def test_respuesta_sin_datos_internos(self):
        self.crear_escenario(usuario=self.cuenta)
        data = self._get().json()
        self.assertEqual(set(data), {'serie', 'promedio_actual', 'variacion', 'tendencia', 'historia_suficiente', 'mensaje'})
        for punto in data['serie']:
            self.assertEqual(set(punto), {'periodo', 'pps', 'ppa', 'creditos_cursados', 'creditos_aprobados'})
