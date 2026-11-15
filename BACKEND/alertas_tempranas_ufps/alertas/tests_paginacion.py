"""SDAT-302: páginas acotadas, respuestas previas y permisos preservados."""
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from academico.models import Estudiante, Periodo
from alertas.models import Alerta, Regla, SolicitudAcompanamiento
from usuarios.models import Usuario
from usuarios.tests_cuentas_estudiante import _auth


class PaginacionListadosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create(nombre='Administrador', correo='admin.paginas@ufps.edu.co',
                                           rol='ADMINISTRADOR', contrasena='!')
        for i in range(3):
            Usuario.objects.create(nombre=f'Persona {i}', correo=f'persona{i}@ufps.edu.co',
                                   rol='BIENESTAR', contrasena='!')
        periodo = Periodo.objects.create(anio=2026, semestre=2)
        regla = Regla.objects.create(nombre='Promedio', tipo='PROMEDIO', operador='<',
                                    valor_umbral=3, nivel='medium')
        for i, estado in enumerate(['PENDIENTE', 'EN_ATENCION', 'ATENDIDA']):
            estudiante = Estudiante.objects.create(codigo=f'P302{i}', nombre=f'Estudiante {i}',
                tipo_documento='CC', numero_documento=f'P302{i}', semestre=2, estado_matricula='ACTIVO')
            alerta = Alerta.objects.create(estudiante=estudiante, regla=regla, estado='activa')
            SolicitudAcompanamiento.objects.create(estudiante=estudiante, alerta=alerta,
                responsable=cls.admin, periodo=periodo, motivo='ACADEMICO', descripcion='Apoyo de prueba',
                estado=estado, respuesta='Atendida' if estado == 'ATENDIDA' else None,
                fecha_atencion=timezone.now() if estado == 'ATENDIDA' else None)

    def consultar(self, nombre, parametros=None, usuario=None):
        return self.client.get(reverse(nombre), parametros or {}, **_auth(usuario or self.admin))

    def test_sin_parametros_se_conservan_las_respuestas_anteriores(self):
        usuarios = self.consultar('listar_usuarios').json()
        self.assertEqual(set(usuarios), {'usuarios'})
        self.assertEqual(len(usuarios['usuarios']), 4)
        solicitudes = self.consultar('solicitudes-listar').json()
        self.assertEqual(set(solicitudes), {'solicitudes', 'conteos', 'periodos', 'estados'})
        self.assertEqual(len(solicitudes['solicitudes']), 3)
        with patch('alertas.views.report_views._get_report_data', return_value=[{'valor': 1}]):
            self.assertEqual(self.consultar('export-report-data').json(), {'data': [{'valor': 1}]})

    def test_usuarios_respeta_pagina_y_orden_estable(self):
        datos = self.consultar('listar_usuarios', {'page': 2, 'page_size': 2}).json()
        esperados = list(Usuario.objects.order_by('nombre', 'id').values_list('id', flat=True))[2:4]
        self.assertEqual([u['id'] for u in datos['usuarios']], esperados)
        self.assertEqual((datos['page'], datos['pages'], datos['page_size'], datos['total']), (2, 2, 2, 4))

    def test_el_tamano_no_puede_superar_cien(self):
        Usuario.objects.bulk_create([
            Usuario(nombre=f'Masivo {i}', correo=f'masivo{i}@ufps.edu.co', contrasena='!') for i in range(105)
        ])
        datos = self.consultar('listar_usuarios', {'page_size': 10000}).json()
        self.assertEqual(datos['page_size'], 100)
        self.assertEqual(len(datos['usuarios']), 100)
        self.assertEqual(datos['total'], 109)

    def test_parametros_invalidos_se_normalizan_sin_error_interno(self):
        for entrada in [{'page': 'abc'}, {'page': 0, 'page_size': 0}, {'page': 99999}]:
            with self.subTest(entrada=entrada):
                respuesta = self.consultar('listar_usuarios', entrada)
                self.assertEqual(respuesta.status_code, 200)
                self.assertGreaterEqual(respuesta.json()['page'], 1)
                self.assertGreaterEqual(respuesta.json()['page_size'], 1)
                self.assertLessEqual(respuesta.json()['page_size'], 100)

    def test_solicitudes_conserva_conteos_y_filtros_al_paginar(self):
        completo = self.consultar('solicitudes-listar').json()
        pagina = self.consultar('solicitudes-listar', {'page_size': 1}).json()
        self.assertEqual(len(pagina['solicitudes']), 1)
        self.assertEqual(pagina['total'], 3)
        for clave in ['conteos', 'periodos', 'estados']:
            self.assertEqual(pagina[clave], completo[clave])
        filtrado = self.consultar('solicitudes-listar', {'estado': 'ATENDIDA', 'page_size': 1}).json()
        self.assertEqual(filtrado['total'], 1)
        self.assertEqual(filtrado['solicitudes'][0]['estado'], 'ATENDIDA')

    def test_solicitudes_no_agrega_consultas_por_cada_fila(self):
        with CaptureQueriesContext(connection) as una:
            self.consultar('solicitudes-listar', {'page_size': 1})
        with CaptureQueriesContext(connection) as tres:
            self.consultar('solicitudes-listar', {'page_size': 3})
        self.assertEqual(len(una), len(tres))

    def test_reporte_pagina_los_datos_sin_cambiar_el_exportador(self):
        filas = [{'valor': i} for i in range(5)]
        with patch('alertas.views.report_views._get_report_data', return_value=filas):
            datos = self.consultar('export-report-data', {'page': 2, 'page_size': 2}).json()
        self.assertEqual(datos['data'], filas[2:4])
        self.assertEqual(datos['total'], 5)

    def test_reporte_vacio_tiene_metadatos_validos(self):
        with patch('alertas.views.report_views._get_report_data', return_value=[]):
            datos = self.consultar('export-report-data', {'page': 1}).json()
        self.assertEqual(datos['data'], [])
        self.assertEqual((datos['total'], datos['pages']), (0, 1))

    def test_el_estudiante_sigue_sin_acceso_a_los_listados_del_personal(self):
        estudiante = Usuario.objects.create(nombre='Cuenta estudiante', correo='est.paginas@ufps.edu.co',
                                            rol='ESTUDIANTE', contrasena='!')
        for nombre in ['listar_usuarios', 'solicitudes-listar', 'export-report-data']:
            with self.subTest(nombre=nombre):
                self.assertEqual(self.consultar(nombre, {'page': 1}, estudiante).status_code, 403)
