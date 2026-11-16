"""SDAT-303: las optimizaciones de rendimiento no cambian los resultados de los endpoints."""
from django.test import TestCase
from django.urls import reverse

from academico.tests_historial_promedios import EscenarioHistorial, _auth
from academico.models import Periodo
from alertas import cache_listado
from alertas.models import Alerta, Regla, RiesgoEstudiante, RiesgoEstudiantePeriodo
from alertas.riesgo_actual import ultimo_riesgo_por_estudiante
from usuarios.models import Usuario


class ListadoAlertasTests(EscenarioHistorial, TestCase):

    def setUp(self):
        cache_listado.invalidar()
        self.admin = Usuario.objects.create(nombre='Admin', correo='admin.sdat303@ufps.edu.co', rol='ADMINISTRADOR')
        self.estudiante = self.crear_escenario()
        self.regla = Regla.objects.create(nombre='Promedio bajo', tipo='PROMEDIO', valor_umbral=3, nivel='high')
        self.alerta = Alerta.objects.create(estudiante=self.estudiante, regla=self.regla, estado='activa',
                                            valor_causa=2.5, metadata={'a': 1})
        RiesgoEstudiante.objects.update_or_create(estudiante=self.estudiante, defaults={'nivel_riesgo': 'medium'})

    def listar(self, **params):
        resp = self.client.get(reverse('listar-alertas'), params, **_auth(self.admin))
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp

    def test_campos_de_cada_alerta(self):
        alerta = self.listar().json()['alertas'][0]
        self.assertEqual(alerta['id'], self.alerta.id)
        self.assertEqual(alerta['studentCode'], self.estudiante.codigo)
        self.assertEqual(alerta['studentName'], self.estudiante.nombre)
        self.assertEqual(alerta['riskLevel'], 'high')
        self.assertEqual(alerta['studentRiskLevel'], 'medium')
        self.assertEqual(alerta['alertType'], 'Promedio bajo')
        self.assertEqual(alerta['tipo_regla'], 'PROMEDIO')
        self.assertEqual(alerta['valor_causa'], 2.5)
        self.assertEqual(alerta['metadata'], {'a': 1})
        self.assertEqual(alerta['status'], 'activa')

    def test_segunda_lectura_sale_del_cache_y_es_igual(self):
        primera = self.listar()
        self.assertEqual(self.listar().content, primera.content)

    def test_cerrar_alerta_invalida_el_cache(self):
        self.assertEqual(len(self.listar().json()['alertas']), 1)
        resp = self.client.post(reverse('cerrar-alerta', args=[self.alerta.id]), **_auth(self.admin))
        self.assertEqual(resp.status_code, 200, resp.content)
        datos = self.listar().json()
        self.assertEqual(datos['alertas'], [])
        self.assertEqual(datos['conteos']['activa'], 0)
        self.assertEqual(datos['conteos']['cerrada'], 1)

    def test_el_cache_distingue_filtros(self):
        self.assertEqual(len(self.listar(estado='activa').json()['alertas']), 1)
        self.assertEqual(len(self.listar(estado='cerrada').json()['alertas']), 0)
        self.assertEqual(len(self.listar(estado='activa', search='inexistente').json()['alertas']), 0)


class UltimoRiesgoTests(EscenarioHistorial, TestCase):

    def test_toma_el_periodo_mas_reciente_de_cada_estudiante(self):
        estudiante = self.crear_escenario()
        antiguo, reciente = Periodo.objects.get(anio=2024, semestre=2), Periodo.objects.get(anio=2025, semestre=1)
        RiesgoEstudiantePeriodo.objects.create(estudiante=estudiante, periodo=reciente, nivel_riesgo='low')
        RiesgoEstudiantePeriodo.objects.create(estudiante=estudiante, periodo=antiguo, nivel_riesgo='high')
        self.assertEqual(ultimo_riesgo_por_estudiante(), {estudiante.codigo: 'low'})
        self.assertEqual(ultimo_riesgo_por_estudiante([estudiante.codigo]), {estudiante.codigo: 'low'})
        self.assertEqual(ultimo_riesgo_por_estudiante(['0']), {})


class PanelDocenteTests(EscenarioHistorial, TestCase):
    """El panel del docente informa el curso de cada estudiante en riesgo y los conteos por curso."""

    def test_panel_con_estudiante_en_riesgo(self):
        estudiante = self.crear_escenario()
        docente = Usuario.objects.get(correo='doc.historial@ufps.edu.co')
        RiesgoEstudiantePeriodo.objects.create(
            estudiante=estudiante, periodo=Periodo.objects.get(anio=2025, semestre=2), nivel_riesgo='high')
        RiesgoEstudiantePeriodo.objects.create(
            estudiante=estudiante, periodo=Periodo.objects.get(anio=2024, semestre=2), nivel_riesgo='low')
        regla = Regla.objects.create(nombre='R', tipo='PROMEDIO', valor_umbral=3)
        Alerta.objects.create(estudiante=estudiante, regla=regla, estado='activa', valor_causa=2)
        resp = self.client.get(reverse('teacher-dashboard'), {'page_size': 10}, **_auth(docente))
        self.assertEqual(resp.status_code, 200, resp.content)
        datos = resp.json()
        self.assertEqual(datos['total_en_riesgo'], 1)
        self.assertEqual(datos['total_alertas_activas'], 1)
        self.assertEqual(datos['distribucion_riesgo']['high'], 1)
        self.assertEqual(datos['distribucion_riesgo']['low'], 0)
        self.assertEqual(len(datos['estudiantes_en_riesgo']), 1)
        fila = datos['estudiantes_en_riesgo'][0]
        self.assertEqual((fila['codigo'], fila['nivel_riesgo'], fila['alertas_activas']), (estudiante.codigo, 'high', 1))
        self.assertTrue(fila['curso'].startswith('Materia M'))
