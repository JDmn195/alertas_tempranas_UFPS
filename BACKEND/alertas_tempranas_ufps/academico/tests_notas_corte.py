"""
HU-31: historial de notas desglosado por corte y consulta de notas por corte.
"""
from decimal import Decimal

from django.urls import reverse

from academico.models import Materia, Curso, Nota
from academico.tests_asistencia import AsistenciaBaseTestCase
from alertas.alertas_corte import evaluar_cortes_nota


class NotasCorteBaseTestCase(AsistenciaBaseTestCase):
    def setUp(self):
        super().setUp()
        self.est = self.estudiantes[0]
        # Periodo en curso: tres cortes, sin examen (nota necesaria 3.0 - 2.1*0.7 / 0.3 = 5.1)
        self.nota = Nota.objects.get(estudiante=self.est, curso=self.curso, periodo=self.periodo)
        self.nota.corte1, self.nota.corte2, self.nota.corte3 = Decimal('1.5'), Decimal('2.4'), Decimal('2.4')
        self.nota.save()
        # Periodo anterior cerrado y aprobado
        materia = Materia.objects.create(codigo="1155401", nombre="Estructuras", creditos=4, semestre=4)
        curso = Curso.objects.create(materia=materia, grupo="A", docente=self.docente)
        Nota.objects.create(
            estudiante=self.est, curso=curso, periodo=self.periodo_anterior,
            corte1=Decimal('4.0'), corte2=Decimal('3.5'), corte3=Decimal('3.0'),
            examen_final=Decimal('4.0'), definitiva=Decimal('3.7'),
        )

    def get(self, nombre, usuario=None, **params):
        return self.client.get(
            reverse(nombre, args=[self.est.codigo]), params,
            HTTP_AUTHORIZATION=self.auth(usuario or self.admin),
        )


class HistorialDesglosadoTests(NotasCorteBaseTestCase):
    def test_historial_incluye_cortes_y_examen(self):
        r = self.get('student-history')
        self.assertEqual(r.status_code, 200)
        periodos = {p['periodo']: p for p in r.json()['historial']}

        cerrada = periodos['2026-1']['materias'][0]
        self.assertEqual(
            (cerrada['corte1'], cerrada['corte2'], cerrada['corte3'], cerrada['examen_final']),
            (4.0, 3.5, 3.0, 4.0),
        )
        self.assertEqual((cerrada['nota_final'], cerrada['estado']), (3.7, 'Aprobado'))
        self.assertIsNone(cerrada['nota_necesaria_examen'])

    def test_materia_sin_definitiva_queda_en_curso_y_fuera_del_promedio(self):
        periodos = {p['periodo']: p for p in self.get('student-history').json()['historial']}
        actual = periodos['2026-2']
        materia = actual['materias'][0]
        self.assertEqual(materia['estado'], 'En curso')
        self.assertIsNone(materia['nota_final'])
        self.assertEqual((materia['corte1'], materia['corte2'], materia['corte3']), (1.5, 2.4, 2.4))
        self.assertEqual(materia['nota_necesaria_examen'], 5.1)
        # Antes contaba como 0.0 reprobada y hundía el promedio del semestre
        self.assertEqual((actual['promedio_semestre'], actual['creditos_intentados']), (0, 0))

    def test_historial_muestra_alertas_por_corte_abiertas(self):
        evaluar_cortes_nota(self.nota)
        materia = self.get('student-history').json()['historial'][-1]['materias'][0]
        claves = {a['clave'] for a in materia['alertas_corte']}
        self.assertIn('C1', claves)
        c1 = next(a for a in materia['alertas_corte'] if a['clave'] == 'C1')
        self.assertEqual((c1['corte'], c1['valor_causa']), (1, 1.5))


class ConsultaNotasCorteTests(NotasCorteBaseTestCase):
    def test_sin_periodo_usa_el_mas_reciente(self):
        r = self.get('student-grades-by-cut')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['periodo'], '2026-2')
        self.assertEqual(data['periodos_disponibles'], ['2026-2', '2026-1'])
        self.assertEqual(len(data['materias']), 1)
        self.assertEqual(data['materias'][0]['codigo'], '1155501')
        self.assertEqual(data['materias'][0]['estado'], 'En curso')

    def test_filtro_por_periodo_y_materia(self):
        data = self.get('student-grades-by-cut', periodo='2026-1', materia='1155401').json()
        self.assertEqual([m['codigo'] for m in data['materias']], ['1155401'])
        self.assertEqual(data['materias'][0]['examen_final'], 4.0)

        self.assertEqual(self.get('student-grades-by-cut', periodo='2026-1', materia='999').json()['materias'], [])

    def test_alertas_por_corte_y_cierre_al_corregir(self):
        evaluar_cortes_nota(self.nota)
        materia = self.get('student-grades-by-cut').json()['materias'][0]
        self.assertIn('C1', {a['clave'] for a in materia['alertas_corte']})

        self.nota.corte1 = Decimal('3.5')
        self.nota.save()
        evaluar_cortes_nota(self.nota)
        materia = self.get('student-grades-by-cut').json()['materias'][0]
        self.assertNotIn('C1', {a['clave'] for a in materia['alertas_corte']})

    def test_periodo_invalido_400_y_estudiante_inexistente_404(self):
        self.assertEqual(self.get('student-grades-by-cut', periodo='2026').status_code, 400)
        self.assertEqual(self.get('student-grades-by-cut', periodo='2030-1').status_code, 400)
        r = self.client.get(reverse('student-grades-by-cut', args=['000']), HTTP_AUTHORIZATION=self.auth(self.admin))
        self.assertEqual(r.status_code, 404)

    def test_docente_sin_el_estudiante_recibe_403(self):
        self.assertEqual(self.get('student-grades-by-cut', usuario=self.user_ajeno).status_code, 403)
        self.assertEqual(self.get('student-grades-by-cut', usuario=self.user_docente).status_code, 200)

    def test_sin_token_401(self):
        r = self.client.get(reverse('student-grades-by-cut', args=[self.est.codigo]))
        self.assertIn(r.status_code, (401, 403))
