"""
HU-40: Acompañamiento del estudiante (GET /api/portal/intervenciones/ y detalle).
"""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from alertas.models import AnotacionIntervencion, Evidencia, Intervencion
from usuarios.models import Auditoria, Usuario

from .intervenciones import serializar_intervencion
from .tests import _auth, _cuenta_estudiante
from .tests_alertas import AlertasPortalBase

# Conjunto exacto de claves que ve el estudiante: cualquier campo nuevo debe agregarse a propósito
CLAVES_INTERVENCION = {'id', 'tipo', 'tipo_texto', 'fecha', 'estado', 'estado_texto', 'resultado', 'responsable', 'alerta'}
CLAVES_ALERTA = {'id', 'tipo', 'materia', 'periodo'}


class IntervencionesPortalBase(AlertasPortalBase):
    def setUp(self):
        super().setUp()
        self.bienestar = Usuario.objects.create(nombre='Laura Bienestar', correo='laura.privado@ufps.edu.co',
                                                rol='BIENESTAR')

    def intervencion(self, alerta, usuario=None, tipo='TUTORIA', concluida=False, resultado=None, dias=0):
        intervencion = Intervencion.objects.create(
            alerta=alerta, usuario=usuario or self.docente_usuario, tipo=tipo, concluida=concluida,
            observaciones='OBSERVACION-INTERNA', evidencia='EVIDENCIA-TEXTO-INTERNA', resultado=resultado,
        )
        if dias:
            Intervencion.objects.filter(pk=intervencion.pk).update(fecha=timezone.now() - timedelta(days=dias))
        return intervencion

    def listar_intervenciones(self, usuario=None, **params):
        return self.client.get(reverse('portal-intervenciones'), params, **_auth(usuario or self.cuenta))

    def detalle_intervencion(self, intervencion_id, usuario=None):
        return self.client.get(reverse('portal-intervencion-detalle', args=[intervencion_id]),
                               **_auth(usuario or self.cuenta))

    def ids_intervenciones(self, resp):
        self.assertEqual(resp.status_code, 200, resp.content)
        return [i['id'] for i in resp.json()['intervenciones']]


class ListadoIntervencionesTests(IntervencionesPortalBase):

    def test_solo_ve_las_de_sus_alertas_de_la_mas_reciente(self):
        alerta = self.alerta_inasistencia()
        antigua = self.intervencion(alerta, dias=5)
        reciente = self.intervencion(self.alerta_general(self.regla_promedio), dias=1)
        hoy = self.intervencion(alerta, usuario=self.bienestar, tipo='REMISION')
        ajena = self.intervencion(self.alerta_inasistencia(estudiante=self.luis))

        self.assertEqual(self.ids_intervenciones(self.listar_intervenciones()), [hoy.id, reciente.id, antigua.id])
        # Luis solo ve la suya, aunque pida el código de Ana
        self.assertEqual(self.ids_intervenciones(self.listar_intervenciones(self.otra_cuenta, codigo=self.ana.codigo)),
                         [ajena.id])

    def test_muestra_resultado_responsable_y_alerta(self):
        alerta = self.alerta_inasistencia()
        self.intervencion(alerta, usuario=self.bienestar, tipo='CITACION', concluida=True,
                          resultado='Se acordó un plan de asistencia')
        [item] = self.listar_intervenciones().json()['intervenciones']
        self.assertEqual(item['responsable'], 'Laura Bienestar')
        self.assertEqual(item['resultado'], 'Se acordó un plan de asistencia')
        self.assertEqual((item['tipo'], item['tipo_texto']), ('CITACION', 'Citación'))
        self.assertEqual((item['estado'], item['estado_texto']), ('concluida', 'Concluida'))
        self.assertEqual(item['alerta'], {'id': alerta.id, 'tipo': self.regla_inasistencia.nombre,
                                          'materia': 'Física I', 'periodo': '2026-1'})

    def test_alerta_general_sin_materia_ni_periodo(self):
        self.intervencion(self.alerta_general(self.regla_promedio))
        [item] = self.listar_intervenciones().json()['intervenciones']
        self.assertEqual((item['alerta']['tipo'], item['alerta']['materia'], item['alerta']['periodo']),
                         ('Promedio Crítico', None, None))
        self.assertEqual((item['estado'], item['resultado']), ('en_curso', None))

    def test_conteos_y_periodos(self):
        self.intervencion(self.alerta_inasistencia(periodo='2026-1'), concluida=True)
        self.intervencion(self.alerta_inasistencia(periodo='2025-2'))
        self.intervencion(self.alerta_general(self.regla_promedio))
        self.intervencion(self.alerta_inasistencia(estudiante=self.luis, periodo='2024-1'))

        data = self.listar_intervenciones(estado='concluida').json()
        self.assertEqual(data['conteos'], {'en_curso': 2, 'concluida': 1, 'total': 3})
        self.assertEqual(data['periodos'], ['2026-1', '2025-2'])

    def test_sin_intervenciones_lista_vacia_y_200(self):
        self.alerta_general(self.regla_promedio)
        resp = self.listar_intervenciones()
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['intervenciones'], [])
        self.assertEqual(data['conteos']['total'], 0)
        self.assertIn('Aún no hay acompañamientos', data['mensaje'])

    def test_filtros_sin_resultados_mensaje_distinto(self):
        self.intervencion(self.alerta_general(self.regla_promedio))
        data = self.listar_intervenciones(estado='concluida').json()
        self.assertEqual(data['intervenciones'], [])
        self.assertIn('filtros', data['mensaje'])


class FiltrosIntervencionesTests(IntervencionesPortalBase):
    def setUp(self):
        super().setUp()
        self.alerta_actual = self.alerta_inasistencia(periodo='2026-1')
        self.alerta_anterior = self.alerta_inasistencia(periodo='2025-2', estado='atendida')
        self.alerta_promedio = self.alerta_general(self.regla_promedio)
        self.actual_curso = self.intervencion(self.alerta_actual)
        self.actual_concluida = self.intervencion(self.alerta_actual, concluida=True)
        self.anterior_concluida = self.intervencion(self.alerta_anterior, concluida=True)
        self.promedio_curso = self.intervencion(self.alerta_promedio)
        self.ajena_alerta = self.alerta_inasistencia(estudiante=self.luis, periodo='2026-1')
        self.ajena = self.intervencion(self.ajena_alerta)

    def assertIds(self, resp, esperadas):
        self.assertEqual(sorted(self.ids_intervenciones(resp)), sorted(i.id for i in esperadas))

    def test_filtro_por_estado(self):
        self.assertIds(self.listar_intervenciones(estado='en_curso'), [self.actual_curso, self.promedio_curso])
        self.assertIds(self.listar_intervenciones(estado='CONCLUIDA'), [self.actual_concluida, self.anterior_concluida])

    def test_filtro_por_periodo(self):
        self.assertIds(self.listar_intervenciones(periodo='2026-1'), [self.actual_curso, self.actual_concluida])
        self.assertIds(self.listar_intervenciones(periodo='2025-2'), [self.anterior_concluida])
        self.assertIds(self.listar_intervenciones(periodo='2024-2'), [])

    def test_filtro_por_alerta(self):
        self.assertIds(self.listar_intervenciones(alerta=self.alerta_actual.id),
                       [self.actual_curso, self.actual_concluida])
        self.assertIds(self.listar_intervenciones(alerta=self.alerta_promedio.id), [self.promedio_curso])

    def test_filtros_combinados(self):
        self.assertIds(self.listar_intervenciones(estado='concluida', periodo='2026-1'), [self.actual_concluida])
        self.assertIds(self.listar_intervenciones(estado='en_curso', alerta=self.alerta_actual.id), [self.actual_curso])
        self.assertIds(self.listar_intervenciones(estado='concluida', periodo='2025-2', alerta=self.alerta_anterior.id),
                       [self.anterior_concluida])
        self.assertIds(self.listar_intervenciones(estado='en_curso', periodo='2025-2'), [])
        self.assertEqual(self.listar_intervenciones(estado='concluida', alerta=self.alerta_actual.id).json()['filtros'],
                         {'estado': 'concluida', 'alerta': self.alerta_actual.id})

    def test_filtros_invalidos_400(self):
        casos = [
            ({'estado': 'pendiente'}, 'estado'),
            ({'periodo': '2026'}, 'periodo'),
            ({'periodo': '2026-5'}, 'periodo'),
            ({'alerta': 'abc'}, 'alerta'),
            ({'alerta': '-1'}, 'alerta'),
            ({'alerta': str(self.ajena_alerta.id)}, 'alerta'),  # alerta de otro estudiante
            ({'alerta': '999999'}, 'alerta'),  # alerta inexistente
            ({'estado': 'en_curso', 'periodo': 'x'}, 'periodo'),
        ]
        for params, campo in casos:
            with self.subTest(params=params):
                resp = self.listar_intervenciones(**params)
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(set(resp.json()['detalle']), {campo})

        # Ajena e inexistente reciben el mismo mensaje: no se revela si la alerta existe
        ajena = self.listar_intervenciones(alerta=self.ajena_alerta.id).json()
        inexistente = self.listar_intervenciones(alerta=999999).json()
        self.assertEqual(ajena, inexistente)


class DetalleIntervencionTests(IntervencionesPortalBase):

    def test_detalle_propio(self):
        intervencion = self.intervencion(self.alerta_inasistencia(), resultado='Asistió a la tutoría')
        resp = self.detalle_intervencion(intervencion.id)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(set(data), CLAVES_INTERVENCION)
        self.assertEqual((data['id'], data['resultado'], data['responsable']),
                         (intervencion.id, 'Asistió a la tutoría', 'Docente Prueba'))

    def test_detalle_ajeno_404_y_auditoria(self):
        ajena = self.intervencion(self.alerta_inasistencia(estudiante=self.luis), resultado='Resultado de Luis')
        resp = self.detalle_intervencion(ajena.id)
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn('Resultado de Luis', resp.content.decode())

        registro = Auditoria.objects.get(usuario=self.cuenta, tipo_accion='ACCESO_DENEGADO')
        self.assertIn(f'intervención ID {ajena.id}', registro.detalle)
        self.assertIn(self.luis.codigo, registro.detalle)

    def test_inexistente_misma_respuesta_404(self):
        ajena = self.intervencion(self.alerta_inasistencia(estudiante=self.luis))
        inexistente = self.detalle_intervencion(ajena.id + 1000)
        self.assertEqual(inexistente.status_code, 404)
        self.assertEqual(inexistente.json(), self.detalle_intervencion(ajena.id).json())
        self.assertEqual(Auditoria.objects.filter(usuario=self.cuenta, tipo_accion='ACCESO_DENEGADO').count(), 2)

    def test_detalle_de_alerta_incluye_sus_intervenciones(self):
        alerta = self.alerta_inasistencia()
        primera = self.intervencion(alerta, dias=2)
        segunda = self.intervencion(alerta, concluida=True)
        self.intervencion(self.alerta_general(self.regla_promedio))  # de otra alerta: no aparece

        data = self.detalle(alerta.id).json()
        self.assertEqual([i['id'] for i in data['intervenciones']], [segunda.id, primera.id])
        for item in data['intervenciones']:
            self.assertEqual(set(item), CLAVES_INTERVENCION)
        self.assertEqual(self.detalle_intervencion(segunda.id).json(), data['intervenciones'][0])


class PrivacidadIntervencionesTests(IntervencionesPortalBase):

    def test_claves_exactas_sin_datos_internos(self):
        """Una intervención con anotaciones y evidencias se devuelve sin ellas y con las claves exactas."""
        alerta = self.alerta_inasistencia()
        intervencion = self.intervencion(alerta, usuario=self.bienestar, resultado='Remitida a Bienestar')
        AnotacionIntervencion.objects.create(intervencion=intervencion, usuario=self.docente_usuario,
                                             texto='ANOTACION-INTERNA')
        Evidencia.objects.create(intervencion=intervencion, archivo_url='https://almacen.test/acta-interna.pdf',
                                 nombre_archivo='acta-interna.pdf', tipo_archivo='application/pdf')

        listado = self.listar_intervenciones()
        detalle = self.detalle_intervencion(intervencion.id)
        detalle_alerta = self.detalle(alerta.id)

        self.assertEqual(set(listado.json()), {'intervenciones', 'conteos', 'periodos', 'filtros', 'mensaje'})
        items = listado.json()['intervenciones'] + [detalle.json()] + detalle_alerta.json()['intervenciones']
        self.assertEqual(len(items), 3)
        for item in items:
            self.assertEqual(set(item), CLAVES_INTERVENCION)
            self.assertEqual(set(item['alerta']), CLAVES_ALERTA)
            self.assertIsInstance(item['responsable'], str)  # solo el nombre, no un objeto con más datos
            self.assertEqual(item['responsable'], 'Laura Bienestar')

        for resp in (listado, detalle, detalle_alerta):
            contenido = resp.content.decode()
            for privado in ('OBSERVACION-INTERNA', 'EVIDENCIA-TEXTO-INTERNA', 'ANOTACION-INTERNA', 'acta-interna',
                            'almacen.test', 'laura.privado', 'BIENESTAR', 'observaciones', 'anotaciones',
                            'evidencia', 'usuario', 'correo', 'rol'):
                self.assertNotIn(privado, contenido)
            self.assertNotIn('"usuario_id"', contenido)

    def test_sin_responsable_no_falla(self):
        # El modelo exige responsable; el serializador del portal no debe fallar si faltara
        alerta = self.alerta_inasistencia()
        sin_responsable = Intervencion(alerta=alerta, tipo='TUTORIA', concluida=False, resultado='En revisión',
                                       fecha=timezone.now())
        data = serializar_intervencion(sin_responsable)
        self.assertIsNone(data['responsable'])
        self.assertEqual(data['resultado'], 'En revisión')
        self.assertEqual(set(data), CLAVES_INTERVENCION)

    def test_sin_token_401(self):
        intervencion = self.intervencion(self.alerta_inasistencia())
        self.assertEqual(self.client.get(reverse('portal-intervenciones')).status_code, 401)
        self.assertEqual(
            self.client.get(reverse('portal-intervencion-detalle', args=[intervencion.id])).status_code, 401)

    def test_cuenta_sin_estudiante_asociado_403(self):
        intervencion = self.intervencion(self.alerta_inasistencia())
        huerfana = _cuenta_estudiante('huerfana@ufps.edu.co')
        self.assertEqual(self.listar_intervenciones(huerfana).status_code, 403)
        self.assertEqual(self.detalle_intervencion(intervencion.id, huerfana).status_code, 403)
        self.assertTrue(Auditoria.objects.filter(usuario=huerfana, tipo_accion='ACCESO_DENEGADO').exists())

    def test_personal_recibe_403(self):
        intervencion = self.intervencion(self.alerta_inasistencia())
        self.assertEqual(self.listar_intervenciones(self.docente_usuario).status_code, 403)
        self.assertEqual(self.detalle_intervencion(intervencion.id, self.bienestar).status_code, 403)
