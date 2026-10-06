"""HU-30: Recordatorios automáticos de alertas e intervenciones sin seguimiento."""
import json
import os
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from io import StringIO
from unittest.mock import MagicMock, patch

import jwt
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from academico.models import Estudiante
from alertas import recordatorios
from alertas.models import (
    Alerta, AnotacionIntervencion, ConfiguracionRecordatorio, Evidencia, Intervencion,
    NotificacionHistorial, NotificacionInterna, Recordatorio, Regla,
)
from usuarios.models import Auditoria, Usuario


def _make_token(usuario):
    payload = {
        'user_id': usuario.id,
        'exp': datetime.now(dt_timezone.utc) + timedelta(days=1),
        'iat': datetime.now(dt_timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


def _respuesta(status):
    resp = MagicMock()
    resp.status_code = status
    resp.text = 'error' if status >= 400 else ''
    return resp


class RecordatoriosBaseTestCase(TestCase):
    """Alerta sin intervenciones (10 días) e intervención sin seguimiento (20 días)."""

    def setUp(self):
        env = patch.dict(os.environ, {'BREVO_API_KEY': 'clave-prueba'})
        env.start()
        self.addCleanup(env.stop)
        brevo = patch('alertas.services.requests.post', return_value=_respuesta(201))
        self.brevo = brevo.start()
        self.addCleanup(brevo.stop)

        self.director = Usuario.objects.create(nombre='Directora', correo='dir@ufps.edu.co', rol='DIRECTOR', contrasena='x')
        self.admin = Usuario.objects.create(nombre='Admin', correo='admin@ufps.edu.co', rol='ADMINISTRADOR', contrasena='x')
        self.bienestar = Usuario.objects.create(nombre='Bienestar', correo='bien@ufps.edu.co', rol='BIENESTAR', contrasena='x')
        self.docente = Usuario.objects.create(nombre='Docente', correo='doc@ufps.edu.co', rol='DOCENTE', contrasena='x')

        self.regla = Regla.objects.create(
            nombre='Promedio Crítico', tipo='PROMEDIO', operador='<', valor_umbral=Decimal('2.5'), nivel='high',
        )
        self.est1 = self._estudiante('E1')
        self.est2 = self._estudiante('E2')

        # Caso ALERTA: alerta activa, sin intervenciones, generada hace 10 días
        self.alerta_sin_interv = self._alerta(self.est1, dias=10)
        # Caso INTERVENCION: intervención abierta registrada hace 20 días
        self.alerta_con_interv = self._alerta(self.est2, dias=25, estado='en_seguimiento')
        self.intervencion = self._intervencion(self.alerta_con_interv, dias=20)

    def _estudiante(self, codigo):
        return Estudiante.objects.create(
            codigo=codigo, nombre=f'Estudiante {codigo}', tipo_documento='CC',
            numero_documento=f'doc-{codigo}', semestre=1, estado_matricula='ACTIVO',
        )

    def _alerta(self, estudiante, dias, estado='activa'):
        alerta = Alerta.objects.create(estudiante=estudiante, regla=self.regla, estado=estado, valor_causa=Decimal('2.1'))
        Alerta.objects.filter(pk=alerta.pk).update(fecha_generacion=timezone.now() - timedelta(days=dias))
        alerta.refresh_from_db()
        return alerta

    def _intervencion(self, alerta, dias, usuario=None):
        intervencion = Intervencion.objects.create(
            alerta=alerta, usuario=usuario or self.bienestar, tipo='TUTORIA', observaciones='Tutoría inicial',
        )
        Intervencion.objects.filter(pk=intervencion.pk).update(fecha=timezone.now() - timedelta(days=dias))
        intervencion.refresh_from_db()
        return intervencion

    def _procesar(self, **kwargs):
        return recordatorios.procesar_recordatorios(**kwargs)

    def _auth(self, usuario):
        return {'HTTP_AUTHORIZATION': f'Bearer {_make_token(usuario)}'}


class ConfiguracionTests(RecordatoriosBaseTestCase):

    @override_settings(RECORDATORIOS_DIAS_INACTIVIDAD_ALERTA=4, RECORDATORIOS_ROLES_DESTINATARIOS=['DIRECTOR', 'BIENESTAR'])
    def test_valores_iniciales_desde_settings(self):
        config = ConfiguracionRecordatorio.obtener()
        self.assertEqual(config.dias_inactividad_alerta, 4)
        self.assertEqual(config.dias_inactividad_intervencion, settings.RECORDATORIOS_DIAS_INACTIVIDAD_INTERVENCION)
        self.assertEqual(config.roles_destinatarios, ['DIRECTOR', 'BIENESTAR'])
        self.assertEqual(ConfiguracionRecordatorio.obtener().pk, config.pk)

    def test_get_y_put_configuracion(self):
        url = reverse('recordatorios-configuracion')
        data = self.client.get(url, **self._auth(self.director)).json()
        self.assertEqual(data['dias_inactividad_alerta'], 7)

        resp = self.client.put(url, data=json.dumps({
            'dias_inactividad_alerta': 3, 'dias_inactividad_intervencion': 10,
            'max_intentos': 5, 'roles_destinatarios': ['director', 'BIENESTAR'], 'notificar_responsable': False,
        }), content_type='application/json', **self._auth(self.director))
        self.assertEqual(resp.status_code, 200)

        config = ConfiguracionRecordatorio.obtener()
        self.assertEqual(config.dias_inactividad_alerta, 3)
        self.assertEqual(config.dias_inactividad_intervencion, 10)
        self.assertEqual(config.max_intentos, 5)
        self.assertEqual(config.roles_destinatarios, ['BIENESTAR', 'DIRECTOR'])
        self.assertFalse(config.notificar_responsable)
        self.assertEqual(config.actualizado_por, self.director)
        self.assertTrue(Auditoria.objects.filter(tipo_accion='CONFIGURAR_RECORDATORIOS').exists())

    def test_put_valida_parametros(self):
        url = reverse('recordatorios-configuracion')
        for body in ({'dias_inactividad_alerta': 0}, {'dias_inactividad_alerta': '7'},
                     {'max_intentos': 20}, {'roles_destinatarios': ['COORDINADOR']},
                     {'activo': 'si'}, {}):
            resp = self.client.put(url, data=json.dumps(body), content_type='application/json',
                                   **self._auth(self.admin))
            self.assertEqual(resp.status_code, 400, body)

    def test_configuracion_requiere_rol_de_coordinacion(self):
        url = reverse('recordatorios-configuracion')
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.get(url, **self._auth(self.docente)).status_code, 403)

    def test_tiempo_de_inactividad_parametrizado_cambia_la_deteccion(self):
        config = ConfiguracionRecordatorio.obtener()
        config.dias_inactividad_alerta = 15
        config.dias_inactividad_intervencion = 30
        config.save()
        self.assertEqual(recordatorios.detectar_casos_sin_seguimiento(), [])

        config.dias_inactividad_alerta = 10
        config.dias_inactividad_intervencion = 20
        config.save()
        self.assertEqual(len(recordatorios.detectar_casos_sin_seguimiento()), 2)

    def test_recordatorios_desactivados_no_envian(self):
        config = ConfiguracionRecordatorio.obtener()
        config.activo = False
        config.save()
        resumen = self._procesar()
        self.assertFalse(resumen['activo'])
        self.assertFalse(Recordatorio.objects.exists())


class DeteccionTests(RecordatoriosBaseTestCase):

    def _casos(self):
        return {(c['tipo_caso'], c['alerta'].id) for c in recordatorios.detectar_casos_sin_seguimiento()}

    def test_detecta_alerta_e_intervencion_sin_seguimiento(self):
        casos = recordatorios.detectar_casos_sin_seguimiento()
        self.assertEqual(self._casos(), {
            ('ALERTA', self.alerta_sin_interv.id), ('INTERVENCION', self.alerta_con_interv.id),
        })
        caso_interv = next(c for c in casos if c['tipo_caso'] == 'INTERVENCION')
        self.assertEqual(caso_interv['intervencion'], self.intervencion)
        self.assertEqual(caso_interv['dias_inactivo'], 20)

    def test_alerta_reciente_no_es_caso(self):
        self._alerta(self._estudiante('E3'), dias=2)
        self.assertEqual(len(self._casos()), 2)

    def test_alerta_cerrada_o_atendida_no_es_caso(self):
        Alerta.objects.filter(pk=self.alerta_sin_interv.pk).update(estado='cerrada')
        Alerta.objects.filter(pk=self.alerta_con_interv.pk).update(estado='cerrada')
        self.assertEqual(self._casos(), set())

    def test_intervencion_concluida_no_es_caso(self):
        Intervencion.objects.filter(pk=self.intervencion.pk).update(concluida=True)
        self.assertEqual(self._casos(), {('ALERTA', self.alerta_sin_interv.id)})

    def test_anotacion_reciente_cuenta_como_seguimiento(self):
        AnotacionIntervencion.objects.create(intervencion=self.intervencion, usuario=self.bienestar, texto='Llamada')
        self.assertEqual(self._casos(), {('ALERTA', self.alerta_sin_interv.id)})

    def test_evidencia_reciente_cuenta_como_seguimiento(self):
        Evidencia.objects.create(intervencion=self.intervencion, archivo_url='https://x.co/a.pdf', nombre_archivo='a.pdf')
        self.assertEqual(self._casos(), {('ALERTA', self.alerta_sin_interv.id)})

    def test_anotacion_antigua_no_evita_el_recordatorio(self):
        anotacion = AnotacionIntervencion.objects.create(intervencion=self.intervencion, usuario=self.bienestar, texto='x')
        AnotacionIntervencion.objects.filter(pk=anotacion.pk).update(fecha=timezone.now() - timedelta(days=16))
        casos = [c for c in recordatorios.detectar_casos_sin_seguimiento() if c['tipo_caso'] == 'INTERVENCION']
        self.assertEqual(len(casos), 1)
        self.assertEqual(casos[0]['dias_inactivo'], 16)

    def test_endpoint_casos_sin_seguimiento(self):
        data = self.client.get(reverse('recordatorios-casos'), **self._auth(self.director)).json()
        self.assertEqual(data['total'], 2)
        self.assertEqual(data['casos'][0]['tipo_caso'], 'INTERVENCION')  # ordenado por días sin seguimiento
        self.assertEqual(data['casos'][0]['responsable'], 'Bienestar')


class EnvioTests(RecordatoriosBaseTestCase):

    def test_envia_por_correo_y_notificacion_interna(self):
        resumen = self._procesar()
        self.assertEqual(resumen['casos_detectados'], 2)
        # Alerta → directora; intervención → directora + responsable (bienestar)
        self.assertEqual(resumen['creados'], 3)
        self.assertEqual(resumen['enviado'], 3)

        r = Recordatorio.objects.get(tipo_caso='ALERTA', destinatario=self.director)
        self.assertEqual(r.estado, 'ENVIADO')
        self.assertEqual(r.canales, {'EMAIL': 'exitoso', 'INTERNA': 'exitoso'})
        self.assertEqual(r.intentos, 1)
        self.assertIsNotNone(r.fecha_envio)
        self.assertEqual(r.dias_inactivo, 10)

        # Un correo de resumen por destinatario (directora con 2 casos, bienestar con 1)
        self.assertEqual(self.brevo.call_count, 2)
        self.assertEqual(resumen['correos_enviados'], 2)
        # El historial registra el correo en cada alerta incluida + una interna por caso
        self.assertEqual(NotificacionHistorial.objects.filter(tipo='RECORDATORIO').count(), 6)
        interna = NotificacionInterna.objects.get(usuario=self.bienestar)
        self.assertIn('Recordatorio', interna.mensaje)
        self.assertIn('20 días sin seguimiento', interna.mensaje)
        self.assertTrue(Auditoria.objects.filter(tipo_accion='ENVIO_RECORDATORIOS').exists())

    def test_destinatarios_segun_configuracion(self):
        config = ConfiguracionRecordatorio.obtener()
        config.roles_destinatarios = ['ADMINISTRADOR']
        config.notificar_responsable = False
        config.save()
        self._procesar()
        self.assertEqual(set(Recordatorio.objects.values_list('destinatario', flat=True)), {self.admin.id})

    def test_sin_destinatarios_de_coordinacion_se_notifica_a_administradores(self):
        Usuario.objects.filter(rol='DIRECTOR').update(activo=False)
        self._procesar()
        r = Recordatorio.objects.get(tipo_caso='ALERTA')
        self.assertEqual(r.destinatario, self.admin)

    def test_no_duplica_recordatorios_en_ejecuciones_seguidas(self):
        self._procesar()
        resumen = self._procesar()
        self.assertEqual(resumen['creados'], 0)
        self.assertEqual(resumen['omitidos'], 3)
        self.assertEqual(Recordatorio.objects.count(), 3)

    def test_vuelve_a_recordar_tras_dias_entre_recordatorios(self):
        self._procesar()
        Recordatorio.objects.update(fecha_creacion=timezone.now() - timedelta(days=8))
        resumen = self._procesar()
        self.assertEqual(resumen['creados'], 3)
        self.assertEqual(Recordatorio.objects.count(), 6)

    def test_historial_de_notificaciones_expone_el_tipo(self):
        self._procesar()
        data = self.client.get(reverse('historial-notificaciones') + '?tipo=recordatorio').json()
        self.assertEqual(len(data['historial']), 6)
        self.assertTrue(all(n['tipo'] == 'RECORDATORIO' for n in data['historial']))


class ReintentosTests(RecordatoriosBaseTestCase):

    def setUp(self):
        super().setUp()
        Usuario.objects.filter(rol='DIRECTOR').update(activo=False)
        Intervencion.objects.filter(pk=self.intervencion.pk).update(concluida=True)
        # Un solo recordatorio: alerta sin intervenciones → admin
        self.brevo.return_value = _respuesta(500)

    def _recordatorio(self):
        return Recordatorio.objects.get()

    def test_fallo_de_correo_queda_pendiente_de_reintento(self):
        resumen = self._procesar()
        self.assertEqual(resumen['pendiente'], 1)
        r = self._recordatorio()
        self.assertEqual(r.estado, 'PENDIENTE')
        self.assertEqual(r.intentos, 1)
        self.assertEqual(r.canales, {'EMAIL': 'fallido', 'INTERNA': 'exitoso'})
        self.assertIn('Error API Brevo: 500', r.ultimo_error)
        self.assertEqual(len(r.historial_intentos), 1)

    def test_reintento_exitoso_solo_repite_el_canal_fallido(self):
        self._procesar()
        self.brevo.return_value = _respuesta(201)
        resumen = self._procesar()
        self.assertEqual(resumen['reintentados'], 1)

        r = self._recordatorio()
        self.assertEqual(r.estado, 'ENVIADO')
        self.assertEqual(r.intentos, 2)
        self.assertIsNone(r.ultimo_error)
        self.assertEqual(r.historial_intentos[1]['canales'], {'EMAIL': 'exitoso'})
        self.assertEqual(NotificacionInterna.objects.count(), 1)  # no se duplica la interna

    def test_agota_reintentos_y_queda_parcial(self):
        for _ in range(3):
            self._procesar()
        r = self._recordatorio()
        self.assertEqual(r.estado, 'PARCIAL')
        self.assertEqual(r.intentos, 3)
        self.assertEqual([i['intento'] for i in r.historial_intentos], [1, 2, 3])

        self._procesar()  # ya no se reintenta ni se crea otro (misma inactividad, reciente)
        self.assertEqual(self._recordatorio().intentos, 3)

    def test_agota_reintentos_sin_ningun_canal_exitoso_queda_fallido(self):
        config = ConfiguracionRecordatorio.obtener()
        config.max_intentos = 2
        config.save()
        with patch('alertas.recordatorios.NotificationService.enviar_interna', side_effect=Exception('BD caída')):
            self._procesar()
            self._procesar()
        r = self._recordatorio()
        self.assertEqual(r.estado, 'FALLIDO')
        self.assertIn('BD caída', r.ultimo_error)

    def test_excepcion_de_red_se_registra_y_se_reintenta(self):
        self.brevo.side_effect = ConnectionError('timeout')
        self._procesar()
        r = self._recordatorio()
        self.assertEqual(r.estado, 'PENDIENTE')
        self.assertIn('timeout', r.ultimo_error)
        self.assertTrue(NotificacionHistorial.objects.filter(tipo='RECORDATORIO', resultado='reintento').exists())


class CancelacionTests(RecordatoriosBaseTestCase):
    """Los recordatorios pendientes se cancelan al registrar seguimiento."""

    def setUp(self):
        super().setUp()
        self.brevo.return_value = _respuesta(500)  # deja los recordatorios PENDIENTES
        self._procesar()
        self.assertEqual(Recordatorio.objects.filter(estado='PENDIENTE').count(), 3)

    def _estados(self, **filtro):
        return set(Recordatorio.objects.filter(**filtro).values_list('estado', flat=True))

    def test_registrar_intervencion_cancela_recordatorio_de_alerta(self):
        resp = self.client.post(
            reverse('registrar-intervencion', args=[self.alerta_sin_interv.id]),
            data=json.dumps({'usuario_id': self.bienestar.id, 'tipo': 'CITACION', 'observaciones': 'Citado'}),
            content_type='application/json', **self._auth(self.bienestar),
        )
        self.assertEqual(resp.status_code, 201)
        r = Recordatorio.objects.get(tipo_caso='ALERTA')
        self.assertEqual(r.estado, 'CANCELADO')
        self.assertEqual(r.motivo_cancelacion, 'Se registró una intervención en la alerta.')
        self.assertIsNotNone(r.fecha_cancelacion)
        self.assertEqual(self._estados(tipo_caso='INTERVENCION'), {'PENDIENTE'})

    def test_anotacion_cancela_recordatorios_de_la_intervencion(self):
        resp = self.client.post(
            reverse('gestionar-anotaciones', args=[self.intervencion.id]),
            data=json.dumps({'usuario_id': self.bienestar.id, 'texto': 'Se contactó al estudiante'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(self._estados(tipo_caso='INTERVENCION'), {'CANCELADO'})
        self.assertEqual(self._estados(tipo_caso='ALERTA'), {'PENDIENTE'})

    def test_evidencia_cancela_recordatorios_de_la_intervencion(self):
        Evidencia.objects.create(intervencion=self.intervencion, archivo_url='https://x.co/a.pdf', nombre_archivo='a.pdf')
        self.assertEqual(self._estados(tipo_caso='INTERVENCION'), {'CANCELADO'})

    def test_concluir_intervencion_cancela_recordatorios(self):
        resp = self.client.post(
            reverse('concluir-intervencion', args=[self.intervencion.id]),
            data=json.dumps({'resultado': 'Caso resuelto'}),
            content_type='application/json', **self._auth(self.bienestar),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._estados(tipo_caso='INTERVENCION'), {'CANCELADO'})

    def test_cerrar_alerta_cancela_recordatorios(self):
        resp = self.client.post(reverse('cerrar-alerta', args=[self.alerta_sin_interv.id]), **self._auth(self.director))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._estados(alerta=self.alerta_sin_interv), {'CANCELADO'})

    def test_cancelados_no_se_reintentan_ni_se_vuelven_a_crear(self):
        AnotacionIntervencion.objects.create(intervencion=self.intervencion, usuario=self.bienestar, texto='Seguimiento')
        self.brevo.return_value = _respuesta(201)
        resumen = self._procesar()
        self.assertEqual(resumen['reintentados'], 1)  # solo el de la alerta
        self.assertEqual(resumen['creados'], 0)        # la intervención ya tiene actividad reciente
        self.assertEqual(self._estados(tipo_caso='INTERVENCION'), {'CANCELADO'})
        self.assertEqual(self._estados(tipo_caso='ALERTA'), {'ENVIADO'})

    def test_recordatorio_enviado_no_cambia_al_registrar_seguimiento(self):
        r = Recordatorio.objects.get(tipo_caso='ALERTA')
        Recordatorio.objects.filter(pk=r.pk).update(estado='ENVIADO')
        self._intervencion(self.alerta_sin_interv, dias=0)
        r.refresh_from_db()
        self.assertEqual(r.estado, 'ENVIADO')

    def test_reintento_revalida_y_cancela_si_hubo_seguimiento_sin_senal(self):
        # bulk_create no dispara post_save: la revalidación previa al reintento lo detecta
        AnotacionIntervencion.objects.bulk_create([
            AnotacionIntervencion(intervencion=self.intervencion, usuario=self.bienestar, texto='Seguimiento'),
        ])
        Intervencion.objects.bulk_create([
            Intervencion(alerta=self.alerta_sin_interv, usuario=self.bienestar, tipo='TUTORIA', observaciones='x'),
        ])
        brevo_llamadas = self.brevo.call_count
        resumen = self._procesar()
        self.assertEqual(resumen['cancelados'], 3)
        self.assertEqual(self._estados(), {'CANCELADO'})
        self.assertEqual(self.brevo.call_count, brevo_llamadas)

    def test_destinatario_desactivado_cancela_su_recordatorio(self):
        Usuario.objects.filter(pk=self.bienestar.pk).update(activo=False)
        self._procesar()
        r = Recordatorio.objects.get(destinatario=self.bienestar)
        self.assertEqual(r.estado, 'CANCELADO')


@override_settings(RECORDATORIOS_CRON_TOKEN='secreto-cron')
class EndpointsYComandoTests(RecordatoriosBaseTestCase):

    def test_programada_valida_token(self):
        url = reverse('recordatorios-programada')
        self.assertEqual(self.client.post(url, HTTP_X_CRON_TOKEN='otro').status_code, 401)
        with patch('alertas.views.recordatorio_views.lanzar_en_segundo_plano') as lanzar:
            self.assertEqual(self.client.post(url, HTTP_X_CRON_TOKEN='secreto-cron').status_code, 202)
            lanzar.assert_called_once_with('PROGRAMADA', None)

    @override_settings(RECORDATORIOS_CRON_TOKEN='')
    def test_programada_deshabilitada_sin_token(self):
        resp = self.client.post(reverse('recordatorios-programada'), HTTP_X_CRON_TOKEN='')
        self.assertEqual(resp.status_code, 503)

    def test_manual_ejecuta_y_requiere_coordinacion(self):
        url = reverse('recordatorios-manual')
        self.assertEqual(self.client.post(url, **self._auth(self.docente)).status_code, 403)
        # En tests la tarea en segundo plano corre síncrona
        resp = self.client.post(url, **self._auth(self.director))
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(Recordatorio.objects.count(), 3)
        self.assertEqual(Auditoria.objects.filter(tipo_accion='ENVIO_RECORDATORIOS').first().usuario, self.director)

    def test_listar_recordatorios_con_filtros(self):
        self._procesar()
        url = reverse('recordatorios-listar')
        data = self.client.get(url, **self._auth(self.director)).json()
        self.assertEqual(len(data['recordatorios']), 3)

        data = self.client.get(url + '?tipo_caso=alerta&estado=enviado', **self._auth(self.director)).json()
        self.assertEqual(len(data['recordatorios']), 1)
        r = data['recordatorios'][0]
        self.assertEqual(r['alerta_id'], self.alerta_sin_interv.id)
        self.assertEqual(r['estudiante']['codigo'], 'E1')
        self.assertEqual(r['intentos'], 1)
        self.assertEqual(len(r['historial_intentos']), 1)

    def test_comando_enviar_recordatorios(self):
        out = StringIO()
        call_command('enviar_recordatorios', stdout=out)
        self.assertIn('2 casos sin seguimiento', out.getvalue())
        self.assertIn('3 recordatorios nuevos', out.getvalue())

    def test_programada_responde_409_si_hay_un_envio_en_curso(self):
        ConfiguracionRecordatorio.obtener()
        ConfiguracionRecordatorio.objects.update(ejecutando_desde=timezone.now())
        with patch('alertas.views.recordatorio_views.lanzar_en_segundo_plano') as lanzar:
            resp = self.client.post(reverse('recordatorios-programada'), HTTP_X_CRON_TOKEN='secreto-cron')
            self.assertEqual(resp.status_code, 409)
            resp = self.client.post(reverse('recordatorios-manual'), **self._auth(self.director))
            self.assertEqual(resp.status_code, 409)
            lanzar.assert_not_called()


class BloqueoTests(RecordatoriosBaseTestCase):
    """El bloqueo vive en la BD, así que aplica entre workers/procesos distintos."""

    def _marca(self):
        return ConfiguracionRecordatorio.objects.values_list('ejecutando_desde', flat=True).get()

    def test_no_permite_ejecuciones_simultaneas(self):
        ConfiguracionRecordatorio.obtener()
        ConfiguracionRecordatorio.objects.update(ejecutando_desde=timezone.now())
        with self.assertRaises(recordatorios.RecordatoriosEnCurso):
            self._procesar()
        self.assertFalse(Recordatorio.objects.exists())

    def test_bloqueo_abandonado_no_impide_ejecutar(self):
        ConfiguracionRecordatorio.obtener()
        ConfiguracionRecordatorio.objects.update(ejecutando_desde=timezone.now() - timedelta(hours=3))
        self._procesar()
        self.assertEqual(Recordatorio.objects.count(), 3)
        self.assertIsNone(self._marca())

    def test_libera_el_bloqueo_al_terminar_y_ante_errores(self):
        self._procesar()
        self.assertIsNone(self._marca())
        with patch('alertas.recordatorios.detectar_casos_sin_seguimiento', side_effect=RuntimeError('falla')):
            with self.assertRaises(RuntimeError):
                self._procesar()
        self.assertIsNone(self._marca())
        self.assertFalse(recordatorios.hay_envio_en_curso())

    def test_actualizar_configuracion_no_libera_un_bloqueo_activo(self):
        ConfiguracionRecordatorio.obtener()
        inicio = timezone.now()
        ConfiguracionRecordatorio.objects.update(ejecutando_desde=inicio)
        resp = self.client.put(reverse('recordatorios-configuracion'), data=json.dumps({'max_intentos': 4}),
                               content_type='application/json', **self._auth(self.director))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._marca(), inicio)


class CorreoResumenTests(RecordatoriosBaseTestCase):
    """Un solo correo por destinatario con todos sus casos."""

    def _correos(self):
        return {c.kwargs['json']['to'][0]['email']: c.kwargs['json'] for c in self.brevo.call_args_list}

    def test_un_correo_por_destinatario_con_todos_sus_casos(self):
        for i in range(3, 6):
            self._alerta(self._estudiante(f'E{i}'), dias=8 + i)
        self._procesar()

        correos = self._correos()
        self.assertEqual(set(correos), {'dir@ufps.edu.co', 'bien@ufps.edu.co'})
        correo_dir = correos['dir@ufps.edu.co']
        self.assertEqual(correo_dir['subject'], 'Recordatorio: 5 casos sin seguimiento')
        for codigo in ['E1', 'E2', 'E3', 'E4', 'E5']:
            self.assertIn(codigo, correo_dir['htmlContent'])
        # Ordenado por días sin seguimiento: la intervención (20 días) va primero
        html = correo_dir['htmlContent']
        self.assertLess(html.index('E2'), html.index('E1'))
        # Pero la bandeja interna sigue teniendo una notificación por caso
        self.assertEqual(NotificacionInterna.objects.filter(usuario=self.director).count(), 5)

    def test_asunto_con_un_solo_caso_nombra_al_estudiante(self):
        self._procesar()
        self.assertEqual(self._correos()['bien@ufps.edu.co']['subject'],
                         'Recordatorio: caso sin seguimiento - Estudiante E2')

    def test_correo_limita_los_casos_listados(self):
        with patch('alertas.recordatorios.MAX_CASOS_CORREO', 1):
            self._procesar()
        self.assertIn('y 1 casos más', self._correos()['dir@ufps.edu.co']['htmlContent'])

    def test_reintento_reenvia_un_solo_correo_con_los_casos_fallidos(self):
        self.brevo.return_value = _respuesta(500)
        self._procesar()
        self.brevo.reset_mock()
        self.brevo.return_value = _respuesta(201)
        self._alerta(self._estudiante('E9'), dias=30)  # caso nuevo para la directora
        resumen = self._procesar()

        self.assertEqual(resumen['reintentados'], 3)
        self.assertEqual(resumen['creados'], 1)
        correos = self._correos()
        self.assertEqual(len(self.brevo.call_args_list), 2)
        self.assertEqual(correos['dir@ufps.edu.co']['subject'], 'Recordatorio: 3 casos sin seguimiento')
        self.assertEqual(set(Recordatorio.objects.values_list('estado', flat=True)), {'ENVIADO'})

    def test_destinatario_sin_correo_no_bloquea_la_notificacion_interna(self):
        Usuario.objects.filter(pk=self.bienestar.pk).update(correo='')
        self._procesar()
        r = Recordatorio.objects.get(destinatario=self.bienestar)
        self.assertEqual(r.canales, {'INTERNA': 'exitoso', 'EMAIL': 'fallido'})
        self.assertIn('no tiene correo', r.ultimo_error)
        self.assertNotIn('', self._correos())
