"""
HU-34: Consulta del porcentaje de inasistencia por estudiante, curso y periodo.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse

from academico.asistencia import (
    UMBRAL_INASISTENCIA_POR_DEFECTO, calcular_inasistencia, calcular_inasistencia_curso,
)
from academico.models import Asistencia, Curso, Estudiante, Materia, Nota
from academico.tests_asistencia import AsistenciaBaseTestCase
from usuarios.models import Usuario


class InasistenciaBaseTestCase(AsistenciaBaseTestCase):
    """Reutiliza el escenario de la HU-33: curso A del docente con 3 matriculados en 2026-2."""

    def registrar(self, estudiante, estados, curso=None, periodo=None, inicio=date(2026, 9, 1)):
        for i, estado in enumerate(estados):
            Asistencia.objects.create(
                estudiante=estudiante, curso=curso or self.curso, periodo=periodo or self.periodo,
                fecha_clase=inicio + timedelta(days=i), estado=estado,
            )

    def get(self, url, usuario=None, **params):
        return self.client.get(url, params, HTTP_AUTHORIZATION=self.auth(usuario or self.admin))


class CalculoInasistenciaTests(InasistenciaBaseTestCase):
    def test_seis_clases_dos_faltas_y_una_justificada(self):
        est = self.estudiantes[0]
        self.registrar(est, ['ASISTIO', 'FALTA', 'FALTA', 'FALTA_JUSTIFICADA', 'ASISTIO', 'ASISTIO'])

        r = calcular_inasistencia(est, self.curso, self.periodo)
        self.assertEqual(r['total_clases'], 6)
        self.assertEqual(r['asistencias'], 3)
        self.assertEqual(r['faltas'], 2)
        self.assertEqual(r['faltas_justificadas'], 1)
        self.assertEqual(r['porcentaje'], Decimal('33.33'))

        self.assertEqual(calcular_inasistencia_curso(self.curso, self.periodo)[est.codigo]['porcentaje'], Decimal('33.33'))

    def test_sin_clases_registradas_porcentaje_null(self):
        r = calcular_inasistencia(self.estudiantes[1], self.curso, self.periodo)
        self.assertEqual(r['total_clases'], 0)
        self.assertIsNone(r['porcentaje'])

        curso = calcular_inasistencia_curso(self.curso, self.periodo)
        self.assertEqual(set(curso), {e.codigo for e in self.estudiantes})
        self.assertIsNone(curso[self.estudiantes[1].codigo]['porcentaje'])

    def test_curso_solo_cuenta_registros_del_curso_y_periodo(self):
        est = self.estudiantes[0]
        self.registrar(est, ['ASISTIO', 'FALTA'])
        # Registros de otro periodo y de otro curso no deben sumar
        self.registrar(est, ['FALTA', 'FALTA'], periodo=self.periodo_anterior, inicio=date(2026, 3, 1))
        otra = Materia.objects.create(codigo="1155502", nombre="Bases de Datos", creditos=3, semestre=5)
        otro_curso = Curso.objects.create(materia=otra, grupo="A", docente=self.docente)
        Nota.objects.create(estudiante=est, curso=otro_curso, periodo=self.periodo)
        self.registrar(est, ['FALTA', 'FALTA', 'FALTA'], curso=otro_curso, inicio=date(2026, 9, 10))

        r = calcular_inasistencia_curso(self.curso, self.periodo)[est.codigo]
        self.assertEqual((r['total_clases'], r['faltas'], r['porcentaje']), (2, 1, Decimal('50.00')))

    def test_consultas_no_crecen_con_los_estudiantes(self):
        for est in self.estudiantes:
            self.registrar(est, ['ASISTIO', 'FALTA'])
        with self.assertNumQueries(1):
            calcular_inasistencia_curso(self.curso, self.periodo)

        for i in range(10, 30):
            est = Estudiante.objects.create(codigo=f"11520{i}", nombre=f"Extra {i}", semestre=5, numero_documento=f"X{i}")
            Nota.objects.create(estudiante=est, curso=self.curso, periodo=self.periodo)
            self.registrar(est, ['ASISTIO', 'FALTA', 'FALTA_JUSTIFICADA'])
        with self.assertNumQueries(1):
            resultado = calcular_inasistencia_curso(self.curso, self.periodo)
        self.assertEqual(len(resultado), 23)


class InasistenciaEstudianteTests(InasistenciaBaseTestCase):
    def setUp(self):
        super().setUp()
        self.est = self.estudiantes[0]
        self.url = reverse('student-attendance', args=[self.est.codigo])
        # Segundo curso del mismo estudiante en 2026-2, dictado por el docente ajeno
        otra = Materia.objects.create(codigo="1155502", nombre="Bases de Datos", creditos=3, semestre=5)
        self.curso_otro = Curso.objects.create(materia=otra, grupo="A", docente=self.docente_ajeno)
        Nota.objects.create(estudiante=self.est, curso=self.curso_otro, periodo=self.periodo)
        Nota.objects.create(estudiante=self.est, curso=self.curso, periodo=self.periodo_anterior)

        self.registrar(self.est, ['ASISTIO', 'FALTA', 'FALTA', 'FALTA_JUSTIFICADA', 'ASISTIO', 'ASISTIO'])
        self.registrar(self.est, ['FALTA', 'ASISTIO'], curso=self.curso_otro, inicio=date(2026, 9, 20))
        self.registrar(self.est, ['FALTA', 'FALTA', 'ASISTIO', 'ASISTIO'], periodo=self.periodo_anterior, inicio=date(2026, 3, 1))

    def test_sin_periodo_usa_el_mas_reciente_con_detalle(self):
        res = self.get(self.url)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['periodo'], '2026-2')
        self.assertEqual(data['periodos_disponibles'], ['2026-2', '2026-1'])
        self.assertEqual(data['umbral'], UMBRAL_INASISTENCIA_POR_DEFECTO)
        cursos = {c['curso_id']: c for c in data['cursos']}
        self.assertEqual(set(cursos), {self.curso.id, self.curso_otro.id})
        c = cursos[self.curso.id]
        self.assertEqual((c['total_clases'], c['faltas'], c['faltas_justificadas'], c['porcentaje']), (6, 2, 1, 33.33))
        self.assertTrue(c['supera_umbral'])
        self.assertEqual(len(c['detalle']), 6)
        self.assertEqual(c['detalle'][1], {'fecha': '2026-09-02', 'estado': 'FALTA', 'observacion': None})
        self.assertEqual(cursos[self.curso_otro.id]['porcentaje'], 50.0)

    def test_filtro_por_periodo(self):
        data = self.get(self.url, periodo='2026-1').json()
        self.assertEqual(data['periodo'], '2026-1')
        self.assertEqual(len(data['cursos']), 1)
        self.assertEqual(data['cursos'][0]['porcentaje'], 50.0)

    def test_filtro_por_curso(self):
        data = self.get(self.url, curso=self.curso_otro.id).json()
        self.assertEqual([c['curso_id'] for c in data['cursos']], [self.curso_otro.id])

    def test_periodo_invalido(self):
        self.assertEqual(self.get(self.url, periodo='2030-1').status_code, 400)
        self.assertEqual(self.get(self.url, periodo='xx').status_code, 400)

    def test_curso_matriculado_sin_registros_es_null(self):
        Asistencia.objects.filter(curso=self.curso_otro).delete()
        data = self.get(self.url, curso=self.curso_otro.id).json()
        self.assertEqual(data['cursos'][0]['total_clases'], 0)
        self.assertIsNone(data['cursos'][0]['porcentaje'])

    def test_docente_solo_ve_sus_cursos(self):
        data = self.get(self.url, self.user_docente).json()
        self.assertEqual([c['curso_id'] for c in data['cursos']], [self.curso.id])

    def test_docente_filtrando_curso_ajeno_recibe_lista_vacia(self):
        res = self.get(self.url, self.user_docente, curso=self.curso_otro.id)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['cursos'], [])

    def test_docente_sin_el_estudiante_en_sus_cursos_recibe_403(self):
        url = reverse('student-attendance', args=[self.no_matriculado.codigo])
        self.assertEqual(self.get(url, self.user_docente).status_code, 403)

    def test_roles(self):
        for rol in ['DIRECTOR', 'BIENESTAR']:
            u = Usuario.objects.create(nombre=rol, correo=f"{rol}@ufps.edu.co", rol=rol, contrasena="123", activo=True)
            self.assertEqual(self.get(self.url, u).status_code, 200)
        self.assertEqual(self.client.get(self.url).status_code, 401)


class InasistenciaCursoTests(InasistenciaBaseTestCase):
    def setUp(self):
        super().setUp()
        e1, e2, e3 = self.estudiantes
        self.registrar(e1, ['ASISTIO', 'ASISTIO', 'ASISTIO', 'ASISTIO'])
        self.registrar(e2, ['ASISTIO', 'FALTA', 'FALTA_JUSTIFICADA', 'ASISTIO'])
        # e3 sin registros en 2026-2, pero con una falta en 2026-1
        Nota.objects.create(estudiante=e3, curso=self.curso, periodo=self.periodo_anterior)
        self.registrar(e3, ['FALTA'], periodo=self.periodo_anterior, inicio=date(2026, 3, 1))
        self.url = reverse('course-absence', args=[self.curso.id])

    def porcentajes(self, data):
        return {e['codigo']: e['porcentaje'] for e in data['estudiantes']}

    def test_porcentaje_de_cada_estudiante(self):
        res = self.get(self.url, self.user_docente)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['periodo'], '2026-2')
        self.assertEqual(self.porcentajes(data), {'1152001': 0.0, '1152002': 25.0, '1152003': None})
        self.assertEqual({e['codigo']: e['supera_umbral'] for e in data['estudiantes']},
                         {'1152001': False, '1152002': True, '1152003': False})

    def test_filtro_por_periodo(self):
        data = self.get(self.url, periodo='2026-1').json()
        self.assertEqual(self.porcentajes(data), {'1152003': 100.0})

    def test_filtro_por_estado(self):
        self.assertEqual(set(self.porcentajes(self.get(self.url, estado='FALTA').json())), {'1152002'})
        self.assertEqual(set(self.porcentajes(self.get(self.url, estado='FJ').json())), {'1152002'})
        self.assertEqual(set(self.porcentajes(self.get(self.url, estado='ASISTIO').json())), {'1152001', '1152002'})
        self.assertEqual(self.get(self.url, estado='TARDE').status_code, 400)

    def test_docente_curso_ajeno_recibe_403(self):
        url = reverse('course-absence', args=[self.curso_ajeno.id])
        self.assertEqual(self.get(url, self.user_docente).status_code, 403)

    def test_curso_inexistente(self):
        self.assertEqual(self.get(reverse('course-absence', args=[9999])).status_code, 404)


class PanelDocenteInasistenciaTests(InasistenciaBaseTestCase):
    def setUp(self):
        super().setUp()
        e1, e2, e3 = self.estudiantes
        self.registrar(e1, ['ASISTIO'] * 5)
        self.registrar(e2, ['FALTA', 'FALTA', 'ASISTIO', 'ASISTIO', 'ASISTIO'])       # 40 %
        self.registrar(e3, ['FALTA', 'ASISTIO', 'ASISTIO', 'ASISTIO', 'ASISTIO'])     # 20 %, no supera

    def test_dashboard_incluye_conteo_sobre_umbral(self):
        res = self.get(reverse('teacher-dashboard'), self.user_docente)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['umbral_inasistencia'], UMBRAL_INASISTENCIA_POR_DEFECTO)
        curso = next(c for c in data['cursos'] if c['curso_id'] == self.curso.id)
        self.assertEqual(curso['inasistencia_sobre_umbral'], 1)

    def test_lista_de_estudiantes_incluye_porcentaje(self):
        url = reverse('teacher-course-students', args=[self.curso.id])
        data = self.get(url, self.user_docente, page_size=50).json()
        por_codigo = {e['codigo']: e for e in data['estudiantes']}
        self.assertEqual(por_codigo['1152001']['porcentaje_inasistencia'], 0.0)
        self.assertEqual(por_codigo['1152002']['porcentaje_inasistencia'], 40.0)
        self.assertTrue(por_codigo['1152002']['supera_umbral_inasistencia'])
        self.assertEqual(por_codigo['1152003']['porcentaje_inasistencia'], 20.0)
        self.assertFalse(por_codigo['1152003']['supera_umbral_inasistencia'])

    def test_lista_de_estudiantes_no_agrega_consultas_por_estudiante(self):
        url = reverse('teacher-course-students', args=[self.curso.id])
        self.get(url, self.user_docente)
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as antes:
            self.get(url, self.user_docente, page_size=50)
        for i in range(10, 20):
            est = Estudiante.objects.create(codigo=f"11520{i}", nombre=f"Extra {i}", semestre=5, numero_documento=f"X{i}")
            Nota.objects.create(estudiante=est, curso=self.curso, periodo=self.periodo)
            self.registrar(est, ['FALTA', 'ASISTIO'])
        with CaptureQueriesContext(connection) as despues:
            self.get(url, self.user_docente, page_size=50)
        self.assertEqual(len(antes), len(despues))


class ImportacionFormatoAsistenciaTests(InasistenciaBaseTestCase):
    """Mismos datos de formato_asistencia.xlsx (1155501A, 2026-2), importados por el endpoint de la HU-33."""

    def test_porcentajes_despues_de_importar(self):
        Estudiante.objects.create(codigo="1152004", nombre="Estudiante 4", semestre=5, numero_documento="DOC4")
        Nota.objects.create(estudiante_id="1152004", curso=self.curso, periodo=self.periodo)
        fechas = ['2026-09-01', '2026-09-03', '2026-09-08', '2026-09-10', '2026-09-15', '2026-09-17']
        estados = {
            '1152001': ['A', 'A', 'A', 'A', 'A', 'A'],
            '1152002': ['A', 'F', 'F', 'A', 'F', 'A'],
            '1152003': ['A', 'FJ', 'A', 'A', 'F', 'A'],
            '1152004': ['F', 'A', 'A', 'F', 'A', 'A'],
        }
        filas = [
            {'Periodo': '2026-2', 'Codigo Estudiante': codigo, 'Materia': '1155501A', 'Fecha': fecha, 'Estado': estado}
            for codigo, lista in estados.items() for fecha, estado in zip(fechas, lista)
        ]
        res = self.client.post(
            reverse('import-attendance'), {'file': self.excel(filas)},
            HTTP_AUTHORIZATION=self.auth(self.admin),
        )
        self.assertEqual(res.status_code, 200, res.content)

        data = self.get(reverse('course-absence', args=[self.curso.id]), periodo='2026-2').json()
        self.assertEqual(
            {e['codigo']: e['porcentaje'] for e in data['estudiantes']},
            {'1152001': 0.0, '1152002': 50.0, '1152003': 16.67, '1152004': 33.33},
        )
