"""
HU-42: Consulta de la asistencia propia en el portal (GET /api/portal/asistencia/).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse

from academico.models import Asistencia, Nota
from alertas.models import Regla
from usuarios.models import Auditoria, Usuario

from .tests import _auth, _cuenta_estudiante
from .tests_alertas import AlertasPortalBase

CLAVES_CURSO = {
    'curso_id', 'materia', 'codigo_materia', 'grupo', 'total_clases', 'asistencias', 'faltas',
    'faltas_justificadas', 'porcentaje', 'umbral', 'umbral_aviso', 'cerca_del_limite', 'supera_umbral', 'detalle',
}
INICIO = date(2026, 2, 2)


class AsistenciaPortalTests(AlertasPortalBase):
    def setUp(self):
        super().setUp()
        for curso in (self.calculo, self.fisica):
            Nota.objects.create(estudiante=self.ana, curso=curso, periodo=self.periodo)
        Nota.objects.create(estudiante=self.luis, curso=self.fisica, periodo=self.periodo)
        self.admin = Usuario.objects.create(nombre='Admin', correo='admin.privado@ufps.edu.co', rol='ADMINISTRADOR')

    def registrar(self, estados, curso=None, estudiante=None, periodo=None):
        """Una clase por día con los estados dados ('A', 'F', 'FJ')."""
        codigos = {'A': 'ASISTIO', 'F': 'FALTA', 'FJ': 'FALTA_JUSTIFICADA'}
        for i, estado in enumerate(estados):
            Asistencia.objects.create(
                estudiante=estudiante or self.ana, curso=curso or self.fisica, periodo=periodo or self.periodo,
                fecha_clase=INICIO + timedelta(days=i), estado=codigos[estado],
                observacion='OBSERVACION-DEL-DOCENTE', registrado_por=self.docente_usuario,
            )

    def consultar(self, usuario=None, **params):
        return self.client.get(reverse('portal-asistencia'), params, **_auth(usuario or self.cuenta))

    def curso(self, resp, curso):
        self.assertEqual(resp.status_code, 200, resp.content)
        return next(c for c in resp.json()['cursos'] if c['curso_id'] == curso.id)

    def test_dos_faltas_de_seis_superan_el_umbral(self):
        self.registrar(['A', 'F', 'A', 'F', 'A', 'A'])
        fisica = self.curso(self.consultar(), self.fisica)
        self.assertEqual(set(fisica), CLAVES_CURSO)
        self.assertEqual((fisica['materia'], fisica['codigo_materia'], fisica['grupo']), ('Física I', '1150102', 'B'))
        self.assertEqual((fisica['total_clases'], fisica['asistencias'], fisica['faltas'], fisica['faltas_justificadas']),
                         (6, 4, 2, 0))
        self.assertEqual(fisica['porcentaje'], 33.33)
        self.assertEqual((fisica['umbral'], fisica['umbral_aviso']), (20.0, 16.0))
        self.assertTrue(fisica['supera_umbral'])
        self.assertFalse(fisica['cerca_del_limite'])

    def test_una_falta_de_seis_queda_cerca_del_limite(self):
        self.registrar(['A', 'A', 'F', 'A', 'A', 'A'])
        fisica = self.curso(self.consultar(), self.fisica)
        self.assertEqual(fisica['porcentaje'], 16.67)
        self.assertFalse(fisica['supera_umbral'])
        self.assertTrue(fisica['cerca_del_limite'])

    def test_lejos_del_limite(self):
        self.registrar(['A'] * 9 + ['F'])
        fisica = self.curso(self.consultar(), self.fisica)
        self.assertEqual(fisica['porcentaje'], 10.0)
        self.assertFalse(fisica['supera_umbral'])
        self.assertFalse(fisica['cerca_del_limite'])

    def test_las_faltas_justificadas_no_cuentan_como_falta(self):
        self.registrar(['A', 'FJ', 'FJ', 'A', 'FJ', 'A'])
        fisica = self.curso(self.consultar(), self.fisica)
        self.assertEqual((fisica['total_clases'], fisica['faltas'], fisica['faltas_justificadas']), (6, 0, 3))
        self.assertEqual(fisica['porcentaje'], 0.0)
        self.assertFalse(fisica['supera_umbral'])
        self.assertFalse(fisica['cerca_del_limite'])

    def test_curso_sin_clases_devuelve_null_sin_fallar(self):
        self.registrar(['A', 'F'])
        calculo = self.curso(self.consultar(), self.calculo)
        self.assertEqual(calculo['total_clases'], 0)
        self.assertIsNone(calculo['porcentaje'])
        self.assertEqual(calculo['detalle'], [])
        self.assertFalse(calculo['supera_umbral'])
        self.assertFalse(calculo['cerca_del_limite'])

    def test_sin_umbral_configurado_las_banderas_son_false(self):
        Regla.objects.filter(tipo='INASISTENCIA').update(activo=False)
        self.registrar(['F', 'F', 'F', 'A'])
        fisica = self.curso(self.consultar(), self.fisica)
        self.assertEqual(fisica['porcentaje'], 75.0)
        self.assertIsNone(fisica['umbral'])
        self.assertIsNone(fisica['umbral_aviso'])
        self.assertFalse(fisica['supera_umbral'])
        self.assertFalse(fisica['cerca_del_limite'])

    def test_usa_el_umbral_propio_del_curso(self):
        self.fisica.umbral_inasistencia = Decimal('40')
        self.fisica.save(update_fields=['umbral_inasistencia'])
        self.registrar(['A', 'F', 'A', 'F', 'A', 'A'])
        fisica = self.curso(self.consultar(), self.fisica)
        self.assertEqual((fisica['umbral'], fisica['umbral_aviso']), (40.0, 32.0))
        self.assertFalse(fisica['supera_umbral'])
        self.assertTrue(fisica['cerca_del_limite'])
        # El otro curso sigue con el general
        self.assertEqual(self.curso(self.consultar(), self.calculo)['umbral'], 20.0)

    def test_detalle_por_fecha_sin_observaciones_ni_quien_registro(self):
        self.registrar(['A', 'F', 'FJ'])
        resp = self.consultar()
        fisica = self.curso(resp, self.fisica)
        self.assertEqual(fisica['detalle'], [
            {'fecha': '2026-02-02', 'estado': 'ASISTIO', 'estado_texto': 'Asistió'},
            {'fecha': '2026-02-03', 'estado': 'FALTA', 'estado_texto': 'Falta'},
            {'fecha': '2026-02-04', 'estado': 'FALTA_JUSTIFICADA', 'estado_texto': 'Falta justificada'},
        ])
        contenido = resp.content.decode()
        for prohibido in ('OBSERVACION-DEL-DOCENTE', 'observacion', 'registrado_por', 'Docente Prueba',
                          'docente@ufps.edu.co'):
            self.assertNotIn(prohibido, contenido)

    def test_periodo_por_defecto_y_filtro(self):
        Nota.objects.create(estudiante=self.ana, curso=self.calculo, periodo=self.periodo_anterior)
        self.registrar(['F', 'A'], curso=self.calculo, periodo=self.periodo_anterior)

        data = self.consultar().json()
        self.assertEqual(data['periodo'], '2026-1')
        self.assertEqual(data['periodos'], ['2026-1', '2025-2'])
        self.assertEqual(len(data['cursos']), 2)

        data = self.consultar(periodo='2025-2').json()
        self.assertEqual([c['materia'] for c in data['cursos']], ['Cálculo I'])
        self.assertEqual(data['cursos'][0]['porcentaje'], 50.0)

        self.assertEqual(self.consultar(periodo='2026').status_code, 400)
        self.assertEqual(self.consultar(periodo='2020-1').status_code, 400)

    def test_estado_vacio(self):
        data = self.consultar().json()
        self.assertFalse(data['hay_registros'])
        self.assertIn('Aún no hay registros de asistencia', data['mensaje'])
        self.assertEqual(len(data['cursos']), 2)

        # Sin ninguna matrícula
        Nota.objects.filter(estudiante=self.luis).delete()
        data = self.consultar(self.otra_cuenta).json()
        self.assertEqual((data['periodo'], data['cursos']), (None, []))
        self.assertIn('matriculadas', data['mensaje'])

    def test_solo_ve_su_propia_asistencia(self):
        self.registrar(['A', 'F', 'A', 'F', 'A', 'A'])
        self.registrar(['F', 'F', 'F'], estudiante=self.luis)

        data = self.consultar(self.otra_cuenta, codigo=self.ana.codigo).json()
        self.assertEqual([c['curso_id'] for c in data['cursos']], [self.fisica.id])
        self.assertEqual((data['cursos'][0]['total_clases'], data['cursos'][0]['porcentaje']), (3, 100.0))
        self.assertEqual(self.curso(self.consultar(), self.fisica)['total_clases'], 6)

    def test_sin_token_401_y_sin_estudiante_asociado_403(self):
        self.assertEqual(self.client.get(reverse('portal-asistencia')).status_code, 401)

        huerfana = _cuenta_estudiante('sin.estudiante@ufps.edu.co')
        resp = self.consultar(huerfana)
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Auditoria.objects.filter(usuario=huerfana, tipo_accion='ACCESO_DENEGADO').exists())

        resp = self.consultar(self.docente_usuario)
        self.assertEqual(resp.status_code, 403)

    def test_coincide_con_la_consulta_del_personal(self):
        self.fisica.umbral_inasistencia = Decimal('25')
        self.fisica.save(update_fields=['umbral_inasistencia'])
        self.registrar(['A', 'F', 'FJ', 'F', 'A', 'A', 'A'])
        self.registrar(['A', 'A', 'A', 'F', 'A'], curso=self.calculo)

        portal = {c['curso_id']: c for c in self.consultar().json()['cursos']}
        personal = self.client.get(reverse('student-attendance', args=[self.ana.codigo]), **_auth(self.admin)).json()
        self.assertEqual(len(personal['cursos']), len(portal))
        for curso in personal['cursos']:
            propio = portal[curso['curso_id']]
            for campo in ('total_clases', 'asistencias', 'faltas', 'faltas_justificadas', 'porcentaje', 'umbral',
                          'umbral_aviso', 'supera_umbral', 'grupo'):
                self.assertEqual(propio[campo], curso[campo], campo)
            self.assertEqual(propio['cerca_del_limite'], curso['cerca_umbral'])
            self.assertEqual([(d['fecha'], d['estado']) for d in propio['detalle']],
                             [(d['fecha'], d['estado']) for d in curso['detalle']])
