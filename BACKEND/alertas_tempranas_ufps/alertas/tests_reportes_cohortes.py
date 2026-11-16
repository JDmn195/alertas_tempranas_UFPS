"""SDAT-334 (B19): cohortes sin promedio inventado, alertas por semestre y ceros visibles."""
from datetime import datetime, timezone as tz
from decimal import Decimal

from django.test import TestCase

from academico.models import Curso, Docente, Estudiante, Materia, Nota, Periodo
from alertas.models import Alerta, Regla
from alertas.views.report_views import _get_report_data, _texto_celda
from usuarios.models import Usuario


class ReporteCohortesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        usuario = Usuario.objects.create(nombre='Doc', correo='doc.coh@ufps.edu.co', rol='DOCENTE',
                                         contrasena='!')
        docente = Docente.objects.create(codigo='DC1', nombre='Doc', tipo_vinculacion='Planta', usuario=usuario)
        materia = Materia.objects.create(codigo='1155900', nombre='Mat', creditos=3, semestre=1, tipo='linea')
        curso = Curso.objects.create(materia=materia, grupo='A', docente=docente)
        cls.estudiante = Estudiante.objects.create(codigo='C9001', nombre='Est', tipo_documento='CC',
            numero_documento='9001', semestre=2, estado_matricula='ACTIVO')
        p1 = Periodo.objects.create(anio=2026, semestre=1)
        p2 = Periodo.objects.create(anio=2026, semestre=2)
        Nota.objects.create(estudiante=cls.estudiante, curso=curso, periodo=p1, definitiva=Decimal('3.5'))
        # Matrícula del periodo vigente aún sin notas: no hay promedio.
        Nota.objects.create(estudiante=cls.estudiante, curso=curso, periodo=p2, definitiva=None)
        regla = Regla.objects.create(nombre='R', tipo='PROMEDIO', operador='<', valor_umbral=3, nivel='medium')
        alerta = Alerta.objects.create(estudiante=cls.estudiante, regla=regla, estado='activa')
        Alerta.objects.filter(pk=alerta.pk).update(fecha_generacion=datetime(2026, 9, 1, tzinfo=tz.utc))

    def test_periodo_sin_definitivas_no_tiene_promedio_cero(self):
        filas = {f['cohort']: f for f in _get_report_data('analisis-cohortes')}
        self.assertEqual(filas['Periodo 2026-1']['averageGpa'], 3.5)
        self.assertIsNone(filas['Periodo 2026-2']['averageGpa'])

    def test_las_alertas_se_cuentan_por_semestre(self):
        filas = {f['cohort']: f for f in _get_report_data('analisis-cohortes')}
        self.assertEqual(filas['Periodo 2026-1']['totalAlerts'], 0)
        self.assertEqual(filas['Periodo 2026-2']['totalAlerts'], 1)

    def test_el_cero_no_sale_como_celda_vacia(self):
        self.assertEqual(_texto_celda(0), '0')
        self.assertEqual(_texto_celda(0.0), '0.0')
        self.assertEqual(_texto_celda(None), '')
