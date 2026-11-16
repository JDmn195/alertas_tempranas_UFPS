"""SDAT-334: la matrícula y los totales de cursos dependen del periodo, no de la suma histórica."""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from academico.models import Curso, Docente, Estudiante, Materia, Nota, Periodo
from usuarios.models import Usuario
from usuarios.tests_cuentas_estudiante import _auth


class MatriculaPorPeriodoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.p_ant = Periodo.objects.create(anio=2026, semestre=1)
        cls.p_act = Periodo.objects.create(anio=2026, semestre=2)
        cls.usuario = Usuario.objects.create(nombre='Doc', correo='doc334@ufps.edu.co', rol='DOCENTE',
                                             contrasena='!')
        cls.docente = Docente.objects.create(codigo='D334', nombre='Docente 334', tipo_vinculacion='Planta',
                                             usuario=cls.usuario)
        cls.director = Usuario.objects.create(nombre='Dir', correo='dir334@ufps.edu.co', rol='DIRECTOR',
                                              contrasena='!')
        materia = Materia.objects.create(codigo='1155334', nombre='Electronica', creditos=3, semestre=1,
                                         tipo='linea')
        otra = Materia.objects.create(codigo='1155335', nombre='Solo anterior', creditos=3, semestre=1,
                                      tipo='linea')
        cls.curso = Curso.objects.create(materia=materia, grupo='F', docente=cls.docente)
        cls.curso_antiguo = Curso.objects.create(materia=otra, grupo='A', docente=cls.docente)
        for i in range(3):
            e = Estudiante.objects.create(codigo=f'E334{i}', nombre=f'Estudiante {i}', tipo_documento='CC',
                                          numero_documento=f'334{i}', semestre=2, estado_matricula='ACTIVO')
            Nota.objects.create(estudiante=e, curso=cls.curso, periodo=cls.p_act, definitiva=Decimal('4.0'))
            # El mismo estudiante cursó el grupo el periodo anterior: no debe sumarse.
            Nota.objects.create(estudiante=e, curso=cls.curso, periodo=cls.p_ant, definitiva=Decimal('2.0'))
        Nota.objects.create(estudiante=Estudiante.objects.get(codigo='E3340'), curso=cls.curso_antiguo,
                            periodo=cls.p_ant, definitiva=Decimal('3.5'))

    def test_panel_docente_cuenta_solo_el_periodo_vigente(self):
        datos = self.client.get(reverse('teacher-dashboard'), **_auth(self.usuario)).json()
        curso = next(c for c in datos['cursos'] if c['curso_id'] == self.curso.id)
        self.assertEqual(curso['matriculados'], 3)
        self.assertEqual(curso['reprobados'], 0)

    def test_detalle_curso_no_repite_estudiantes_entre_periodos(self):
        url = reverse('course-detail', args=[self.curso.id])
        datos = self.client.get(url, **_auth(self.director)).json()
        self.assertEqual(len(datos['estudiantes']), 3)
        self.assertEqual({e['periodo'] for e in datos['estudiantes']}, {'2026-2'})
        anterior = self.client.get(url, {'periodo_anio': 2026, 'periodo_semestre': 1}, **_auth(self.director)).json()
        self.assertEqual({e['periodo'] for e in anterior['estudiantes']}, {'2026-1'})

    def test_filtro_de_periodo_cambia_el_total_de_cursos(self):
        def total(semestre):
            r = self.client.get(reverse('course-indicators'), {'periodo_anio': 2026, 'periodo_semestre': semestre},
                                **_auth(self.director))
            return r.json()['total']
        self.assertEqual(total(2), 1)
        self.assertEqual(total(1), 2)
