"""
Criterio 7 del Sprint 5: la vista de asistencia advierte cuando el estudiante se aproxima
al umbral de inasistencia, y el estudiante recibe un aviso preventivo una sola vez por curso.
"""
from decimal import Decimal

from django.urls import reverse

from academico.asistencia import cerca_umbral, umbral_aviso
from academico.models import Curso
from alertas.models import Alerta, AvisoPreventivoInasistencia
from alertas.tests_alertas_inasistencia import (
    SEIS_DOS_FALTAS, SEIS_UNA_FALTA, AlertaInasistenciaBaseTestCase,
)


class CercaUmbralTests(AlertaInasistenciaBaseTestCase):
    def test_umbral_de_aviso_es_el_80_por_ciento_del_umbral(self):
        self.assertEqual(umbral_aviso(Decimal('20')), Decimal('16.00'))
        self.assertEqual(umbral_aviso(Decimal('25.5')), Decimal('20.40'))
        self.assertIsNone(umbral_aviso(None))

    def test_cerca_umbral(self):
        umbral = Decimal('20')
        self.assertTrue(cerca_umbral(Decimal('16.67'), umbral))
        self.assertTrue(cerca_umbral(Decimal('20'), umbral))       # igual al umbral no lo supera
        self.assertFalse(cerca_umbral(Decimal('15.99'), umbral))
        self.assertFalse(cerca_umbral(Decimal('33.33'), umbral))   # ya lo supera
        self.assertFalse(cerca_umbral(Decimal('0'), Decimal('0')))
        self.assertFalse(cerca_umbral(None, umbral))
        self.assertIsNone(cerca_umbral(Decimal('16.67'), None))


class VistaAsistenciaAvisoTests(AlertaInasistenciaBaseTestCase):
    def test_estudiante_marca_cerca_umbral_y_umbral_de_aviso(self):
        self.registrar(self.est, SEIS_UNA_FALTA)  # 16,67 %
        r = self.get(reverse('student-attendance', args=[self.est.codigo]))
        curso = r.json()['cursos'][0]
        self.assertEqual((curso['supera_umbral'], curso['cerca_umbral']), (False, True))
        self.assertEqual(curso['umbral_aviso'], 16.0)

    def test_curso_cuenta_estudiantes_cerca_del_umbral(self):
        self.registrar(self.estudiantes[0], SEIS_UNA_FALTA)   # cerca
        self.registrar(self.estudiantes[1], SEIS_DOS_FALTAS)  # supera
        self.registrar(self.estudiantes[2], ['ASISTIO'] * 6)  # normal
        data = self.get(reverse('course-absence', args=[self.curso.id])).json()
        cerca = {e['codigo']: e['cerca_umbral'] for e in data['estudiantes']}
        self.assertEqual(cerca, {
            self.estudiantes[0].codigo: True, self.estudiantes[1].codigo: False, self.estudiantes[2].codigo: False,
        })
        self.assertEqual((data['total_cerca_umbral'], data['total_sobre_umbral'], data['umbral_aviso']), (1, 1, 16.0))

    def test_sin_umbral_cerca_es_null(self):
        self.regla.activo = False
        self.regla.save()
        self.registrar(self.est, SEIS_UNA_FALTA)
        curso = self.get(reverse('student-attendance', args=[self.est.codigo])).json()['cursos'][0]
        self.assertIsNone(curso['cerca_umbral'])
        self.assertIsNone(curso['umbral_aviso'])

    def test_panel_docente_marca_cerca_umbral(self):
        self.registrar(self.est, SEIS_UNA_FALTA)
        r = self.get(reverse('teacher-course-students', args=[self.curso.id]), usuario=self.user_docente)
        fila = next(e for e in r.json()['estudiantes'] if e['codigo'] == self.est.codigo)
        self.assertTrue(fila['cerca_umbral_inasistencia'])
        self.assertFalse(fila['supera_umbral_inasistencia'])

        panel = self.get(reverse('teacher-dashboard'), usuario=self.user_docente).json()
        curso = next(c for c in panel['cursos'] if c['curso_id'] == self.curso.id)
        self.assertEqual((curso['inasistencia_cerca_umbral'], curso['inasistencia_sobre_umbral']), (1, 0))


class AvisoPreventivoTests(AlertaInasistenciaBaseTestCase):
    def test_aviso_al_estudiante_una_sola_vez(self):
        self.registrar(self.est, SEIS_UNA_FALTA)
        self.evaluar()
        self.evaluar()

        aviso = AvisoPreventivoInasistencia.objects.get(estudiante=self.est, curso=self.curso, periodo=self.periodo)
        self.assertEqual((aviso.porcentaje, aviso.umbral, aviso.resultado), (Decimal('16.67'), Decimal('20.00'), 'exitoso'))
        self.assertEqual(aviso.destinatario, 'est1@ufps.edu.co')
        correos = [c for c in self.brevo.call_args_list if c.args[0] == 'est1@ufps.edu.co']
        self.assertEqual(len(correos), 1)
        self.assertIn('Aviso de inasistencia', correos[0].args[1])
        self.assertIn('16.67', correos[0].args[2])
        self.assertFalse(self.alertas().exists())

    def test_sin_aviso_bajo_el_80_por_ciento_ni_con_pocas_clases(self):
        self.registrar(self.est, ['ASISTIO'] * 6)
        self.evaluar()
        otro = self.estudiantes[1]
        self.registrar(otro, ['ASISTIO', 'ASISTIO', 'FALTA'])  # 33 %, pero menos de min_clases (4)
        self.evaluar(estudiante=otro)
        self.assertFalse(AvisoPreventivoInasistencia.objects.exists())
        self.brevo.assert_not_called()

    def test_al_superar_no_hay_aviso_sino_alerta(self):
        self.registrar(self.est, SEIS_DOS_FALTAS)
        self.evaluar()
        self.assertFalse(AvisoPreventivoInasistencia.objects.exists())
        self.assertEqual(self.alertas().count(), 1)

    def test_estudiante_sin_correo_queda_registrado_sin_envio(self):
        otro = self.estudiantes[1]
        self.registrar(otro, SEIS_UNA_FALTA)
        self.evaluar(estudiante=otro)
        aviso = AvisoPreventivoInasistencia.objects.get(estudiante=otro)
        self.assertEqual(aviso.resultado, 'sin_correo')
        self.brevo.assert_not_called()

    def test_umbral_propio_del_curso(self):
        Curso.objects.filter(pk=self.curso.pk).update(umbral_inasistencia=Decimal('40'))
        self.curso.refresh_from_db()
        lejos, cerca = self.estudiantes[1], self.est
        self.registrar(lejos, SEIS_UNA_FALTA)   # 16,67 % < 32 % (80 % de 40)
        self.registrar(cerca, SEIS_DOS_FALTAS)  # 33,33 %: cerca de 40, sin superarlo
        self.evaluar_curso()
        self.assertEqual(
            list(AvisoPreventivoInasistencia.objects.values_list('estudiante_id', 'umbral')),
            [(cerca.codigo, Decimal('40.00'))],
        )
        self.assertFalse(self.alertas().exists())


class ResetReglasTests(AlertaInasistenciaBaseTestCase):
    def test_reset_reglas_conserva_reglas_corte_e_inasistencia(self):
        from django.core.management import call_command
        from io import StringIO
        from alertas.models import Regla

        self.registrar(self.est, SEIS_DOS_FALTAS)
        self.evaluar()
        antes = set(Regla.objects.filter(tipo__in=['CORTE', 'INASISTENCIA']).values_list('id', flat=True))
        self.assertTrue(antes)

        call_command('reset_reglas', stdout=StringIO())

        self.assertEqual(set(Regla.objects.filter(tipo__in=['CORTE', 'INASISTENCIA']).values_list('id', flat=True)), antes)
        self.assertEqual(Regla.objects.filter(tipo__in=['PROMEDIO', 'REPROBACION', 'ATRASO']).count(), 9)
        self.assertEqual(self.alertas().count(), 1)
