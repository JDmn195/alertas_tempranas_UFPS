"""
Flujos de configuración y procesos periódicos:
reglas de riesgo (HU-15/16, HU-32), re-evaluación periódica (HU-29) y
recordatorios de casos sin seguimiento (HU-30).
"""
from datetime import timedelta
from decimal import Decimal

from django.test import override_settings
from django.utils import timezone

from academico.models import Nota
from alertas.models import Alerta, EjecucionReevaluacion, NotificacionInterna, Recordatorio, Regla, RiesgoEstudiante
from usuarios.models import Auditoria

from .base import IntegracionTestCase


class ReglasIntegracionTests(IntegracionTestCase):

    def setUp(self):
        super().setUp()
        # Estudiante con PPA 3.2: no cumple la regla base (< 2.5)
        self.importar_historial([self.fila('2025-2', '1150102', definitiva=3.2, nombre='Física I')])
        self.assertFalse(Alerta.objects.exists())

    def _crear_regla_promedio_bajo(self):
        return self.api('post', 'listar_crear_reglas', self.director, datos={
            'nombre': 'Promedio Bajo', 'tipo': 'PROMEDIO', 'operador': '<',
            'valor_umbral': 3.5, 'nivel': 'medium',
        })

    def test_crear_regla_recalcula_y_genera_alertas(self):
        resp = self._crear_regla_promedio_bajo()
        self.assertEqual(resp.status_code, 201, resp.content)
        regla = Regla.objects.get(id=resp.json()['id'])

        alerta = Alerta.objects.get(estudiante=self.estudiante, regla=regla)
        self.assertEqual(alerta.estado, 'activa')
        self.assertEqual(RiesgoEstudiante.objects.get(estudiante=self.estudiante).nivel_riesgo, 'medium')
        self.assertTrue(Auditoria.objects.filter(tipo_accion='CREAR_REGLA', usuario=self.director).exists())

        listado = self.api('get', 'listar-alertas', self.director).json()['alertas']
        self.assertEqual([a['alertType'] for a in listado], ['Promedio Bajo'])

    def test_desactivar_regla_cierra_sus_alertas(self):
        regla_id = self._crear_regla_promedio_bajo().json()['id']

        resp = self.api('put', 'detalle_regla', self.director, args=[regla_id], datos={'activo': False})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(Alerta.objects.get(regla_id=regla_id).estado, 'cerrada')
        self.assertTrue(Auditoria.objects.filter(tipo_accion='DESACTIVAR_REGLA').exists())

    def test_regla_con_alertas_no_se_puede_eliminar(self):
        regla_id = self._crear_regla_promedio_bajo().json()['id']

        resp = self.api('delete', 'detalle_regla', self.director, args=[regla_id])
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error'], 'protected_error')
        self.assertTrue(Regla.objects.filter(id=regla_id).exists())

    def test_regla_sin_alertas_se_elimina(self):
        regla = Regla.objects.create(nombre='Sin uso', tipo='ATRASO', operador='>', valor_umbral=Decimal('5'))
        resp = self.api('delete', 'detalle_regla', self.admin, args=[regla.id])
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Regla.objects.filter(id=regla.id).exists())

    def test_regla_de_corte_valida_parametros_y_clave_unica(self):
        base = {'nombre': 'Corte 3 bajo', 'tipo': 'CORTE', 'operador': '<', 'valor_umbral': 2.0, 'nivel': 'low'}

        duplicada = self.api('post', 'listar_crear_reglas', self.director,
                             datos={**base, 'parametros': {'clave': 'C1', 'evalua': 'CORTE', 'corte': 3}})
        self.assertEqual(duplicada.status_code, 400)

        corte_invalido = self.api('post', 'listar_crear_reglas', self.director,
                                  datos={**base, 'parametros': {'clave': 'C5', 'evalua': 'CORTE', 'corte': 4}})
        self.assertEqual(corte_invalido.status_code, 400)

        valida = self.api('post', 'listar_crear_reglas', self.director,
                          datos={**base, 'parametros': {'clave': 'C5', 'evalua': 'CORTE', 'corte': 3}})
        self.assertEqual(valida.status_code, 201, valida.content)

        reglas = self.api('get', 'listar_crear_reglas', self.bienestar).json()
        self.assertIn('C5', [r['parametros'].get('clave') for r in reglas])

    def test_regla_de_corte_nueva_evalua_las_notas_del_periodo_actual(self):
        self.importar_historial([
            self.fila('2025-2', '1150102', definitiva=3.2, nombre='Física I'),
            self.fila('2026-1', '1150101', c1=3.2, c2=3.1, c3=1.0, nombre='Cálculo I'),
        ])
        self.assertFalse(Alerta.objects.filter(regla__parametros__clave='C5').exists())

        resp = self.api('post', 'listar_crear_reglas', self.director, datos={
            'nombre': 'Corte 3 bajo', 'tipo': 'CORTE', 'operador': '<', 'valor_umbral': 2.0, 'nivel': 'low',
            'parametros': {'clave': 'C5', 'evalua': 'CORTE', 'corte': 3},
        })
        self.assertEqual(resp.status_code, 201)

        alerta = Alerta.objects.get(regla__parametros__clave='C5')
        self.assertEqual(alerta.metadata['corte'], 3)
        self.assertEqual(float(alerta.valor_causa), 1.0)

    def test_docente_no_administra_reglas(self):
        self.assertEqual(self._crear_regla_promedio_bajo_como(self.usuario_docente).status_code, 403)
        self.assertEqual(Regla.objects.filter(nombre='Promedio Bajo').count(), 0)

    def _crear_regla_promedio_bajo_como(self, usuario):
        return self.api('post', 'listar_crear_reglas', usuario, datos={
            'nombre': 'Promedio Bajo', 'tipo': 'PROMEDIO', 'operador': '<', 'valor_umbral': 3.5,
        })


class ReevaluacionPeriodicaIntegracionTests(IntegracionTestCase):
    """HU-29: la re-evaluación (manual o programada) recorre a todos los estudiantes."""

    def setUp(self):
        super().setUp()
        self.importar_historial(self.historial_en_riesgo())

    def _ultima_ejecucion(self):
        return EjecucionReevaluacion.objects.order_by('-id').first()

    def test_reevaluacion_manual_registra_la_ejecucion(self):
        resp = self.api('post', 'reevaluacion-manual', self.admin)
        self.assertEqual(resp.status_code, 202)

        ej = self._ultima_ejecucion()
        self.assertEqual(ej.estado, 'EXITOSA')
        self.assertEqual(ej.origen, 'MANUAL')
        self.assertEqual(ej.usuario, self.admin)
        self.assertEqual(ej.procesados, 1)

        lista = self.api('get', 'reevaluacion-ejecuciones', self.director).json()['ejecuciones']
        self.assertEqual(lista[0]['id'], ej.id)
        detalle = self.api('get', 'reevaluacion-ejecucion-detalle', self.director, args=[ej.id]).json()
        self.assertEqual(detalle['estado'], 'EXITOSA')

    def test_reevaluacion_cierra_alertas_cuando_el_estudiante_mejora(self):
        Nota.objects.filter(estudiante=self.estudiante, curso=self.curso_fisica).update(definitiva=Decimal('4.5'))

        self.api('post', 'reevaluacion-manual', self.admin)

        ej = self._ultima_ejecucion()
        self.assertEqual(ej.alertas_cerradas, 1)
        self.assertEqual(ej.cambios_riesgo, 1)
        self.assertEqual(Alerta.objects.get(regla=self.regla_promedio).estado, 'cerrada')
        self.assertEqual(RiesgoEstudiante.objects.get(estudiante=self.estudiante).nivel_riesgo, 'low')

    def test_reevaluacion_no_duplica_ni_renotifica_alertas_vigentes(self):
        notificaciones_antes = NotificacionInterna.objects.count()

        self.api('post', 'reevaluacion-manual', self.admin)

        ej = self._ultima_ejecucion()
        self.assertEqual(ej.alertas_generadas, 0)
        self.assertEqual(Alerta.objects.filter(regla=self.regla_promedio).count(), 1)
        self.assertEqual(NotificacionInterna.objects.count(), notificaciones_antes)

    def test_reevaluacion_no_cierra_las_alertas_por_corte(self):
        """Las alertas por corte tienen su propio ciclo de vida (HU-32): la re-evaluación no las toca."""
        self.api('post', 'reevaluacion-manual', self.admin)

        abiertas = Alerta.objects.filter(regla__tipo='CORTE', estado='activa').count()
        self.assertEqual(abiertas, 3)

    @override_settings(REEVALUACION_CRON_TOKEN='token-cron')
    def test_reevaluacion_programada_por_token(self):
        self.assertEqual(self.client.post('/api/alertas/reevaluacion/programada/',
                                          HTTP_X_CRON_TOKEN='otro').status_code, 401)

        resp = self.client.post('/api/alertas/reevaluacion/programada/', HTTP_X_CRON_TOKEN='token-cron')
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(self._ultima_ejecucion().origen, 'PROGRAMADA')

    def test_solo_el_administrador_ejecuta_la_reevaluacion(self):
        self.assertEqual(self.api('post', 'reevaluacion-manual', self.director).status_code, 403)
        self.assertEqual(self.api('get', 'reevaluacion-ejecuciones', self.usuario_docente).status_code, 403)
        self.assertFalse(EjecucionReevaluacion.objects.exists())


class RecordatoriosIntegracionTests(IntegracionTestCase):
    """HU-30: casos sin seguimiento → recordatorio → seguimiento lo saca de la lista."""

    def setUp(self):
        super().setUp()
        self.importar_historial(self.historial_en_riesgo())
        self.alerta = Alerta.objects.get(regla=self.regla_promedio)
        # Solo la alerta de promedio queda vieja (10 días sin intervenciones)
        Alerta.objects.filter(pk=self.alerta.pk).update(fecha_generacion=timezone.now() - timedelta(days=10))

    def _casos(self):
        return self.api('get', 'recordatorios-casos', self.director).json()['casos']

    def test_alerta_sin_seguimiento_genera_recordatorio_al_director(self):
        casos = self._casos()
        self.assertEqual([c['alerta_id'] for c in casos], [self.alerta.id])
        self.assertEqual(casos[0]['tipo_caso'], 'ALERTA')
        self.assertGreaterEqual(casos[0]['dias_inactivo'], 10)

        resp = self.api('post', 'recordatorios-manual', self.director)
        self.assertEqual(resp.status_code, 202)

        recordatorio = Recordatorio.objects.get(alerta=self.alerta, destinatario=self.director)
        self.assertEqual(recordatorio.estado, 'ENVIADO')
        self.assertEqual(recordatorio.canales.get('EMAIL'), 'exitoso')

        listado = self.api('get', 'recordatorios-listar', self.director, query={'alerta_id': self.alerta.id}).json()
        self.assertEqual(len(listado['recordatorios']), 1)
        self.assertTrue(Auditoria.objects.filter(tipo_accion='ENVIO_RECORDATORIOS').exists())

    def test_registrar_intervencion_saca_el_caso_de_los_pendientes(self):
        self.api('post', 'registrar-intervencion', self.bienestar, args=[self.alerta.id],
                 datos={'tipo': 'TUTORIA', 'observaciones': 'Primera tutoría'})

        self.assertEqual(self._casos(), [])
        self.api('post', 'recordatorios-manual', self.director)
        self.assertFalse(Recordatorio.objects.filter(alerta=self.alerta).exists())

    def test_no_se_repite_el_recordatorio_antes_del_intervalo(self):
        self.api('post', 'recordatorios-manual', self.director)
        self.api('post', 'recordatorios-manual', self.director)
        self.assertEqual(Recordatorio.objects.filter(alerta=self.alerta, destinatario=self.director).count(), 1)

    def test_configuracion_cambia_la_deteccion(self):
        resp = self.api('put', 'recordatorios-configuracion', self.admin, datos={'dias_inactividad_alerta': 30})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._casos(), [])

        invalida = self.api('put', 'recordatorios-configuracion', self.admin, datos={'dias_inactividad_alerta': 0})
        self.assertEqual(invalida.status_code, 400)

    def test_recordatorios_solo_para_coordinacion(self):
        self.assertEqual(self.api('post', 'recordatorios-manual', self.bienestar).status_code, 403)
        self.assertEqual(self.api('get', 'recordatorios-casos', self.usuario_docente).status_code, 403)
