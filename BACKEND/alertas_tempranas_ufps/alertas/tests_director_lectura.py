"""SDAT-349: el director consulta y exporta alertas sin editarlas; filtros, paginación y resumen."""
from django.test import TestCase
from django.urls import reverse

from academico.models import Estudiante, Nota, Periodo
from alertas.models import Alerta, Intervencion, Regla, RiesgoEstudiantePeriodo
from usuarios.models import Auditoria, Usuario
from usuarios.tests_cuentas_estudiante import _auth


def _estudiante(codigo, semestre):
    return Estudiante.objects.create(
        codigo=codigo, nombre=f'Estudiante {codigo}', tipo_documento='CC', numero_documento=codigo,
        semestre=semestre, estado_matricula='ACTIVO',
    )


class DirectorSoloLecturaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.director = Usuario.objects.create(nombre='Dir', correo='dir349@ufps.edu.co', rol='DIRECTOR', contrasena='!')
        cls.bienestar = Usuario.objects.create(nombre='Bien', correo='bien349@ufps.edu.co', rol='BIENESTAR', contrasena='!')
        cls.estudiante_user = Usuario.objects.create(nombre='Est', correo='est349@ufps.edu.co', rol='ESTUDIANTE', contrasena='!')
        cls.alto = Regla.objects.create(nombre='Promedio bajo', tipo='PROMEDIO', operador='<', valor_umbral=3, nivel='high')
        cls.bajo = Regla.objects.create(nombre='Atraso', tipo='ATRASO', operador='>', valor_umbral=1, nivel='low')
        est = _estudiante('S3490', 3)
        cls.alerta_alta = Alerta.objects.create(estudiante=est, regla=cls.alto, estado='activa')
        cls.alerta_baja = Alerta.objects.create(estudiante=est, regla=cls.bajo, estado='activa')
        cls.intervencion = Intervencion.objects.create(
            alerta=cls.alerta_alta, usuario=cls.bienestar, tipo='TUTORIA', observaciones='x')

    def test_director_lista_alertas_y_queda_auditado(self):
        resp = self.client.get(reverse('listar-alertas'), **_auth(self.director))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['alertas']), 2)
        self.assertTrue(Auditoria.objects.filter(usuario=self.director, tipo_accion='CONSULTA_ALERTAS').exists())

    def test_director_no_puede_cerrar_ni_editar(self):
        for nombre, args in [('cerrar-alerta', [self.alerta_alta.id]),
                             ('registrar-intervencion', [self.alerta_alta.id]),
                             ('concluir-intervencion', [self.intervencion.id]),
                             ('generar-alertas', []), ('reevaluar-alertas', [])]:
            with self.subTest(nombre):
                resp = self.client.post(reverse(nombre, args=args), **_auth(self.director))
                self.assertEqual(resp.status_code, 403)
        self.alerta_alta.refresh_from_db()
        self.assertEqual(self.alerta_alta.estado, 'activa')
        self.assertTrue(Auditoria.objects.filter(usuario=self.director, tipo_accion='ACCESO_DENEGADO').exists())

    def test_director_exporta_reporte_y_queda_auditado(self):
        resp = self.client.get(reverse('exportar-reporte'), {
            'tipo': 'riesgo-estudiantil', 'formato': 'excel', 'fecha_desde': '2020-01-01', 'fecha_hasta': '2099-12-31',
        }, **_auth(self.director))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Auditoria.objects.filter(usuario=self.director, tipo_accion='EXPORTAR_REPORTE').exists())

    def test_bienestar_si_cierra_alertas(self):
        resp = self.client.post(reverse('cerrar-alerta', args=[self.alerta_alta.id]), **_auth(self.bienestar))
        self.assertEqual(resp.status_code, 200)

    def test_estudiante_no_ve_alertas_ni_anotaciones(self):
        for nombre, args in [('listar-alertas', []), ('gestionar-anotaciones', [self.intervencion.id])]:
            with self.subTest(nombre):
                self.assertEqual(self.client.get(reverse(nombre, args=args), **_auth(self.estudiante_user)).status_code, 403)

    def test_filtro_por_nivel_estudiante_y_todas(self):
        url = reverse('listar-alertas')
        niveles = self.client.get(url, {'nivel': 'high'}, **_auth(self.director)).json()['alertas']
        self.assertEqual([a['riskLevel'] for a in niveles], ['high'])
        Alerta.objects.filter(pk=self.alerta_baja.pk).update(estado='cerrada')
        todas = self.client.get(url, {'estado': 'todas', 'estudiante': 'S3490'}, **_auth(self.director)).json()['alertas']
        self.assertEqual(len(todas), 2)
        otro = self.client.get(url, {'estado': 'todas', 'estudiante': 'NOEXISTE'}, **_auth(self.director)).json()['alertas']
        self.assertEqual(otro, [])

    def test_paginacion_conserva_respuesta_anterior_y_cuenta(self):
        url = reverse('listar-alertas')
        self.assertNotIn('pages', self.client.get(url, **_auth(self.director)).json())
        pagina = self.client.get(url, {'page': 2, 'page_size': 1}, **_auth(self.director)).json()
        self.assertEqual((pagina['page'], pagina['pages'], pagina['total']), (2, 2, 2))
        self.assertEqual(len(pagina['alertas']), 1)


class DirectorFiltrosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.director = Usuario.objects.create(nombre='Dir', correo='dirf349@ufps.edu.co', rol='DIRECTOR', contrasena='!')
        cls.p1 = Periodo.objects.create(anio=2026, semestre=1)
        cls.p2 = Periodo.objects.create(anio=2026, semestre=2)
        cls.e3 = _estudiante('F3490', 3)
        cls.e5 = _estudiante('F5490', 5)
        regla = Regla.objects.create(nombre='Promedio bajo', tipo='PROMEDIO', operador='<', valor_umbral=3, nivel='high')
        Alerta.objects.create(estudiante=cls.e3, regla=regla, estado='activa')
        RiesgoEstudiantePeriodo.objects.create(estudiante=cls.e3, periodo=cls.p1, nivel_riesgo='high')
        RiesgoEstudiantePeriodo.objects.create(estudiante=cls.e5, periodo=cls.p2, nivel_riesgo='low')

    def consultar(self, **parametros):
        return self.client.get(reverse('director-indicadores'), parametros, **_auth(self.director))

    def test_sin_filtros_cuenta_todo_y_ofrece_opciones(self):
        datos = self.consultar().json()
        self.assertEqual(datos['total_estudiantes_activos'], 2)
        self.assertEqual(datos['filtros']['periodos'], ['2026-2', '2026-1'])
        self.assertEqual(datos['filtros']['semestres'], [3, 5])

    def test_filtro_por_semestre(self):
        datos = self.consultar(semestre='3').json()
        self.assertEqual(datos['total_estudiantes_activos'], 1)
        self.assertEqual(datos['alertas_activas'], 1)
        self.assertEqual([d['semester'] for d in datos['distribucion_riesgo']], ['Sem 3'])

    def test_filtro_por_periodo_usa_el_riesgo_de_ese_periodo(self):
        datos = self.consultar(periodo='2026-1').json()
        self.assertEqual(datos['total_estudiantes_activos'], 1)
        self.assertEqual(datos['porcentaje_riesgo'], 100.0)
        datos = self.consultar(periodo='2026-2').json()
        self.assertEqual(datos['porcentaje_riesgo'], 0.0)

    def test_filtros_invalidos_responden_400(self):
        self.assertEqual(self.consultar(periodo='2099-9').status_code, 400)
        self.assertEqual(self.consultar(semestre='abc').status_code, 400)


class ResumenAdminTests(TestCase):
    def test_solo_el_administrador_lo_consulta(self):
        admin = Usuario.objects.create(nombre='Adm', correo='adm349@ufps.edu.co', rol='ADMINISTRADOR', contrasena='!')
        director = Usuario.objects.create(nombre='Dir', correo='dirr349@ufps.edu.co', rol='DIRECTOR', contrasena='!')
        self.assertEqual(self.client.get(reverse('resumen_admin'), **_auth(director)).status_code, 403)
        resp = self.client.get(reverse('resumen_admin'), **_auth(admin))
        self.assertEqual(resp.status_code, 200)
        datos = resp.json()
        self.assertEqual(datos['usuarios']['por_rol']['ADMINISTRADOR'], 1)
        self.assertEqual(datos['usuarios']['activos'], 2)
        self.assertEqual(datos['importaciones_recientes'], [])
        self.assertEqual(datos['procesos_recientes'], [])
