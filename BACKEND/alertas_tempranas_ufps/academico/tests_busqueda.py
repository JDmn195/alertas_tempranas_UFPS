"""SDAT-340 (B14): la búsqueda de los listados ignora tildes y mayúsculas."""
from django.test import TestCase
from django.urls import reverse

from academico.busqueda import normalizar_texto
from academico.models import Estudiante, Materia
from academico.tests_historial_promedios import EscenarioHistorial, _auth
from alertas.models import Alerta, Regla
from usuarios.models import Usuario


class BusquedaSinTildesTests(EscenarioHistorial, TestCase):

    def setUp(self):
        self.admin = Usuario.objects.create(nombre='Admin', correo='admin.busqueda@ufps.edu.co', rol='ADMINISTRADOR')
        self.estudiante = self.crear_escenario()  # Ana Pérez, 1151001

    def test_normalizar_texto(self):
        self.assertEqual(normalizar_texto('Électrónica PÉREZ'), 'electronica perez')

    def test_estudiantes_con_y_sin_tilde(self):
        for termino in ('perez', 'PEREZ', 'Pérez', 'ana pe'):
            with self.subTest(termino=termino):
                resp = self.client.get(reverse('list-students'), {'search': termino}, **_auth(self.admin))
                self.assertEqual(resp.status_code, 200, resp.content)
                self.assertEqual([e['codigo'] for e in resp.json()['results']], ['1151001'])

    def test_alertas_buscan_por_codigo_y_sin_tildes(self):
        regla = Regla.objects.create(nombre='R', tipo='PROMEDIO', valor_umbral=3)
        Alerta.objects.create(estudiante=self.estudiante, regla=regla, estado='activa', valor_causa=2)
        for termino in ('perez', '1151001'):
            with self.subTest(termino=termino):
                resp = self.client.get(reverse('listar-alertas'), {'search': termino}, **_auth(self.admin))
                self.assertEqual(resp.status_code, 200, resp.content)
                self.assertEqual(len(resp.json()['alertas']), 1)


class OrdenEstudiantesTests(EscenarioHistorial, TestCase):
    """SDAT-340 (B40): el listado de estudiantes se ordena por columna en el servidor."""

    def test_ordena_por_nombre_y_sentido(self):
        admin = Usuario.objects.create(nombre='Admin', correo='admin.orden@ufps.edu.co', rol='ADMINISTRADOR')
        for codigo, nombre in (('1151010', 'Zoe Álvarez'), ('1151011', 'Ángela Ruiz'), ('1151012', 'Mario Díaz')):
            Estudiante.objects.create(codigo=codigo, nombre=nombre, tipo_documento='CC', numero_documento=codigo,
                                      semestre=1, estado_matricula='ACTIVO')

        def nombres(**params):
            resp = self.client.get(reverse('list-students'), params, **_auth(admin))
            return [e['nombre'] for e in resp.json()['results']]

        self.assertEqual(nombres(sort='nombre', dir='asc'), ['Ángela Ruiz', 'Mario Díaz', 'Zoe Álvarez'])
        self.assertEqual(nombres(sort='nombre', dir='desc'), ['Zoe Álvarez', 'Mario Díaz', 'Ángela Ruiz'])
        self.assertEqual(nombres(sort='columna_invalida'), nombres())


class OrdenCursosTests(EscenarioHistorial, TestCase):
    """SDAT-340 (B14, B40): cursos buscan sin tildes y se ordenan por columna."""

    def test_busqueda_sin_tildes_y_orden(self):
        admin = Usuario.objects.create(nombre='Admin', correo='admin.cursos@ufps.edu.co', rol='ADMINISTRADOR')
        self.crear_escenario()
        Materia.objects.filter(codigo='MA').update(nombre='Electrónica')
        Materia.objects.filter(codigo='MB').update(nombre='Álgebra')

        def materias(**params):
            resp = self.client.get(reverse('course-indicators'), {'periodo_anio': 'todos', **params}, **_auth(admin))
            self.assertEqual(resp.status_code, 200, resp.content)
            return [c['materia'] for c in resp.json()['results']]

        self.assertEqual(materias(search='electronica'), ['Electrónica'])
        self.assertEqual(materias(search='ELECTRÓNICA'), ['Electrónica'])
        self.assertEqual(materias(sort='materia', dir='asc')[:2], ['Álgebra', 'Electrónica'])
        self.assertEqual(materias(sort='materia', dir='desc')[-2:], ['Electrónica', 'Álgebra'])
