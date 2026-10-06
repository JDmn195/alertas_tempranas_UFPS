from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import jwt
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.urls import reverse

from academico.models import Curso, Docente, Estudiante, Materia, Nota, Periodo
from alertas import reevaluacion
from alertas.models import (
    Alerta, AnotacionIntervencion, EjecucionReevaluacion, Intervencion, NotificacionInterna, Regla,
    RiesgoEstudiante,
)
from alertas.views.alert_generation_views import reprocesar_alertas_completas
from usuarios.models import Usuario


def _make_token(usuario):
    payload = {
        'user_id': usuario.id,
        'exp': datetime.now(dt_timezone.utc) + timedelta(days=1),
        'iat': datetime.now(dt_timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


class ReevaluacionBaseTestCase(TestCase):
    """HU-29: datos base con dos estudiantes activos y uno retirado."""

    def setUp(self):
        notif_patcher = patch('alertas.reevaluacion.NotificationService.notificar_alerta')
        self.notif = notif_patcher.start()
        self.addCleanup(notif_patcher.stop)

        self.periodo = Periodo.objects.create(anio=2026, semestre=1)
        usuario_doc = Usuario.objects.create(
            nombre='Docente', correo='doc@ufps.edu.co', rol='DOCENTE', contrasena='x'
        )
        docente = Docente.objects.create(codigo='D1', nombre='Docente', tipo_vinculacion='Planta', usuario=usuario_doc)
        self.cursos = []
        for i in range(1, 4):
            materia = Materia.objects.create(codigo=f'M{i}', nombre=f'Materia {i}', semestre=1)
            self.cursos.append(Curso.objects.create(materia=materia, grupo='A', docente=docente))

        self.regla_critico = Regla.objects.create(
            nombre='Promedio Crítico', tipo='PROMEDIO', operador='<', valor_umbral=Decimal('2.5'),
            nivel='high', prioridad=30,
        )
        self.regla_bajo = Regla.objects.create(
            nombre='Promedio Bajo', tipo='PROMEDIO', operador='<', valor_umbral=Decimal('3.0'),
            nivel='medium', prioridad=20,
        )

        self.est_bueno = self._estudiante('E1', notas=[4.0, 4.2, 3.8])
        self.est_malo = self._estudiante('E2', notas=[2.0, 2.2, 2.4])
        self.est_retirado = self._estudiante('E3', notas=[1.0, 1.0, 1.0], estado='RETIRADO')

    def _estudiante(self, codigo, notas, estado='ACTIVO'):
        est = Estudiante.objects.create(
            codigo=codigo, nombre=f'Estudiante {codigo}', tipo_documento='CC',
            numero_documento=f'doc-{codigo}', semestre=1, estado_matricula=estado,
        )
        for curso, definitiva in zip(self.cursos, notas):
            Nota.objects.create(periodo=self.periodo, estudiante=est, curso=curso, definitiva=Decimal(str(definitiva)))
        return est

    def _ejecutar(self, **kwargs):
        kwargs.setdefault('max_intentos', 1)
        kwargs.setdefault('dormir', lambda s: None)
        return reevaluacion.ejecutar_reevaluacion(**kwargs)


class ReevaluacionServicioTests(ReevaluacionBaseTestCase):

    def test_recalcula_indicadores_y_riesgo(self):
        ej = self._ejecutar()[-1]

        self.assertEqual(ej.estado, 'EXITOSA')
        self.est_malo.refresh_from_db()
        self.assertEqual(self.est_malo.promedio, Decimal('2.20'))
        self.assertEqual(RiesgoEstudiante.objects.get(estudiante=self.est_malo).nivel_riesgo, 'high')
        self.assertEqual(RiesgoEstudiante.objects.get(estudiante=self.est_bueno).nivel_riesgo, 'low')

    def test_excluye_estudiantes_retirados(self):
        ej = self._ejecutar()[-1]

        self.assertEqual(ej.total_estudiantes, 2)
        self.assertFalse(RiesgoEstudiante.objects.filter(estudiante=self.est_retirado).exists())
        self.assertFalse(Alerta.objects.filter(estudiante=self.est_retirado).exists())

    def test_genera_una_alerta_por_tipo_con_la_regla_de_mayor_prioridad(self):
        notif = self.notif
        ej = self._ejecutar()[-1]

        alertas = Alerta.objects.filter(estudiante=self.est_malo)
        self.assertEqual(alertas.count(), 1)
        self.assertEqual(alertas.first().regla, self.regla_critico)
        self.assertEqual(ej.alertas_generadas, 1)
        notif.assert_called_once()

    def test_detecta_cambio_de_riesgo_sin_nueva_importacion(self):
        self._ejecutar()
        # Cambian las notas del estudiante bueno (corrección de notas, sin importación)
        Nota.objects.filter(estudiante=self.est_bueno).update(definitiva=Decimal('2.0'))

        ej = self._ejecutar()[-1]

        self.assertEqual(ej.cambios_riesgo, 1)
        self.assertEqual(ej.detalle_cambios, [{'codigo': 'E1', 'de': 'low', 'a': 'high'}])
        self.assertEqual(RiesgoEstudiante.objects.get(estudiante=self.est_bueno).nivel_riesgo, 'high')
        self.assertTrue(Alerta.objects.filter(estudiante=self.est_bueno, regla=self.regla_critico, estado='activa').exists())

    def test_no_duplica_alertas_abiertas_y_actualiza_valor(self):
        self._ejecutar()
        Nota.objects.filter(estudiante=self.est_malo, curso=self.cursos[0]).update(definitiva=Decimal('1.1'))

        ej = self._ejecutar()[-1]

        alerta = Alerta.objects.get(estudiante=self.est_malo)
        self.assertEqual(ej.alertas_generadas, 0)
        self.assertEqual(ej.alertas_actualizadas, 1)
        self.assertEqual(alerta.valor_causa, Decimal('1.90'))

    def test_cierra_alerta_cuando_el_estudiante_mejora(self):
        self._ejecutar()
        alerta = Alerta.objects.get(estudiante=self.est_malo)
        alerta.estado = 'en_seguimiento'
        alerta.save()
        Nota.objects.filter(estudiante=self.est_malo).update(definitiva=Decimal('4.5'))

        ej = self._ejecutar()[-1]

        alerta.refresh_from_db()
        self.assertEqual(alerta.estado, 'cerrada')
        self.assertEqual(ej.alertas_cerradas, 1)
        self.assertEqual(RiesgoEstudiante.objects.get(estudiante=self.est_malo).nivel_riesgo, 'low')

    def test_aplica_reglas_vigentes_y_cierra_alertas_de_reglas_desactivadas(self):
        self._ejecutar()
        self.regla_critico.activo = False
        self.regla_critico.save()

        ej = self._ejecutar()[-1]

        self.assertEqual(Alerta.objects.get(regla=self.regla_critico).estado, 'cerrada')
        nueva = Alerta.objects.get(estudiante=self.est_malo, estado='activa')
        self.assertEqual(nueva.regla, self.regla_bajo)
        self.assertEqual(RiesgoEstudiante.objects.get(estudiante=self.est_malo).nivel_riesgo, 'medium')
        self.assertEqual([r['id'] for r in ej.alcance['reglas']], [self.regla_bajo.id])

    def test_reactiva_con_alerta_nueva_si_recae_tras_cierre(self):
        self._ejecutar()
        Nota.objects.filter(estudiante=self.est_malo).update(definitiva=Decimal('4.5'))
        self._ejecutar()
        Nota.objects.filter(estudiante=self.est_malo).update(definitiva=Decimal('2.0'))

        ej = self._ejecutar()[-1]

        self.assertEqual(ej.alertas_generadas, 1)
        self.assertEqual(Alerta.objects.filter(estudiante=self.est_malo, estado='activa').count(), 1)
        self.assertEqual(Alerta.objects.filter(estudiante=self.est_malo, estado='cerrada').count(), 1)

    def test_fallo_de_notificacion_no_invalida_la_ejecucion(self):
        notif = self.notif
        notif.side_effect = RuntimeError('Brevo caído')

        ej = self._ejecutar()[-1]

        self.assertEqual(ej.estado, 'EXITOSA')
        self.assertEqual(Alerta.objects.filter(estudiante=self.est_malo).count(), 1)


class RegistroEjecucionTests(ReevaluacionBaseTestCase):

    def test_registra_alcance_totales_y_fechas(self):
        ej = self._ejecutar(origen='PROGRAMADA')[-1]

        self.assertEqual(ej.origen, 'PROGRAMADA')
        self.assertEqual(ej.intento, 1)
        self.assertIsNotNone(ej.fecha_fin)
        self.assertEqual(ej.alcance['tipo'], 'COMPLETO')
        self.assertEqual(len(ej.alcance['reglas']), 2)
        self.assertEqual((ej.total_estudiantes, ej.procesados, ej.total_errores), (2, 2, 0))
        self.assertEqual(ej.estudiantes_por_nivel, {'high': 1, 'medium': 0, 'low': 1, 'unknown': 0})
        self.assertEqual(ej.cambios_riesgo, 2)  # unknown → nivel calculado

    def test_registra_auditoria(self):
        from usuarios.models import Auditoria
        self._ejecutar()
        self.assertTrue(Auditoria.objects.filter(tipo_accion='REEVALUACION_RIESGO').exists())

    def test_alcance_parcial_por_codigos(self):
        ej = self._ejecutar(codigos=['E2'])[-1]

        self.assertEqual(ej.alcance['tipo'], 'PARCIAL')
        self.assertEqual(ej.alcance['codigos'], ['E2'])
        self.assertEqual(ej.total_estudiantes, 1)

    def test_error_de_un_estudiante_queda_registrado_y_no_detiene_a_los_demas(self):
        original = reevaluacion.reevaluar_estudiante

        def falla_e1(est, reglas):
            if est.codigo == 'E1':
                raise ValueError('dato corrupto')
            return original(est, reglas)

        with patch('alertas.reevaluacion.reevaluar_estudiante', side_effect=falla_e1):
            ej = self._ejecutar()[-1]

        self.assertEqual(ej.estado, 'PARCIAL')
        self.assertEqual((ej.procesados, ej.total_errores), (1, 1))
        self.assertEqual(ej.errores, [{'codigo': 'E1', 'error': 'dato corrupto'}])
        self.assertEqual(RiesgoEstudiante.objects.get(estudiante=self.est_malo).nivel_riesgo, 'high')

    def test_error_de_un_estudiante_revierte_sus_cambios_parciales(self):
        with patch('alertas.views.alert_generation_views._evaluar_regla_para_estudiante',
                   side_effect=RuntimeError('boom')):
            ej = self._ejecutar()[-1]

        self.assertEqual(ej.estado, 'FALLIDA')
        # El riesgo se había calculado antes del error, pero la transacción se revirtió
        self.assertFalse(RiesgoEstudiante.objects.exists())


class ReintentosTests(ReevaluacionBaseTestCase):

    def test_reintenta_solo_estudiantes_fallidos_con_espera_exponencial(self):
        original = reevaluacion.reevaluar_estudiante
        fallos = {'E1': 2}  # falla en los dos primeros intentos

        def falla_temporal(est, reglas):
            if fallos.get(est.codigo, 0) > 0:
                fallos[est.codigo] -= 1
                raise OperationalError('conexión perdida')
            return original(est, reglas)

        esperas = []
        with patch('alertas.reevaluacion.reevaluar_estudiante', side_effect=falla_temporal):
            ejecuciones = self._ejecutar(max_intentos=3, espera_segundos=10, dormir=esperas.append)

        # El 2.º intento solo incluye a E1 y vuelve a fallar → FALLIDA (mismo alcance en el 3.º)
        self.assertEqual([e.estado for e in ejecuciones], ['PARCIAL', 'FALLIDA', 'EXITOSA'])
        self.assertEqual([e.intento for e in ejecuciones], [1, 2, 3])
        self.assertEqual(ejecuciones[1].reintento_de, ejecuciones[0])
        self.assertEqual(ejecuciones[2].reintento_de, ejecuciones[1])
        self.assertEqual(ejecuciones[1].alcance['codigos'], ['E1'])
        self.assertEqual(ejecuciones[2].alcance['codigos'], ['E1'])
        self.assertEqual(ejecuciones[2].total_estudiantes, 1)
        self.assertEqual(esperas, [10, 20])
        self.assertEqual(RiesgoEstudiante.objects.get(estudiante=self.est_bueno).nivel_riesgo, 'low')

    def test_fallo_general_reintenta_hasta_el_maximo(self):
        esperas = []
        with patch('alertas.reevaluacion.estudiantes_evaluables', side_effect=OperationalError('BD caída')):
            ejecuciones = self._ejecutar(max_intentos=3, espera_segundos=5, dormir=esperas.append)

        self.assertEqual([e.estado for e in ejecuciones], ['FALLIDA'] * 3)
        self.assertEqual(ejecuciones[-1].mensaje_error, 'BD caída')
        self.assertEqual(esperas, [5, 10])

    def test_fallo_general_se_recupera_en_el_reintento(self):
        original = reevaluacion.estudiantes_evaluables
        llamadas = {'n': 0}

        def falla_una_vez():
            llamadas['n'] += 1
            if llamadas['n'] == 1:
                raise OperationalError('BD caída')
            return original()

        with patch('alertas.reevaluacion.estudiantes_evaluables', side_effect=falla_una_vez):
            ejecuciones = self._ejecutar(max_intentos=3)

        self.assertEqual([e.estado for e in ejecuciones], ['FALLIDA', 'EXITOSA'])
        self.assertEqual(ejecuciones[1].alcance['tipo'], 'COMPLETO')

    def test_reintenta_si_no_se_puede_registrar_el_intento(self):
        original = reevaluacion._ejecutar_intento
        llamadas = {'n': 0}

        def falla_registro(*args):
            llamadas['n'] += 1
            if llamadas['n'] == 1:
                raise OperationalError('BD inaccesible')
            return original(*args)

        with patch('alertas.reevaluacion._ejecutar_intento', side_effect=falla_registro):
            ejecuciones = self._ejecutar(max_intentos=2)

        self.assertEqual(len(ejecuciones), 1)
        self.assertEqual(ejecuciones[0].estado, 'EXITOSA')

    def test_sin_reglas_activas_no_reintenta(self):
        Regla.objects.update(activo=False)
        esperas = []

        ejecuciones = self._ejecutar(max_intentos=3, dormir=esperas.append)

        self.assertEqual(len(ejecuciones), 1)
        self.assertEqual(ejecuciones[0].estado, 'FALLIDA')
        self.assertIn('reglas activas', ejecuciones[0].mensaje_error)
        self.assertEqual(esperas, [])

    def test_no_lanza_si_hay_una_ejecucion_en_curso(self):
        EjecucionReevaluacion.objects.create(estado='EN_CURSO')
        with self.assertRaises(reevaluacion.ReevaluacionEnCurso):
            self._ejecutar()

    @override_settings(REEVALUACION_BLOQUEO_HORAS=2)
    def test_ejecucion_en_curso_abandonada_no_bloquea(self):
        vieja = EjecucionReevaluacion.objects.create(estado='EN_CURSO')
        EjecucionReevaluacion.objects.filter(id=vieja.id).update(
            fecha_inicio=datetime.now(dt_timezone.utc) - timedelta(hours=3)
        )
        self.assertEqual(self._ejecutar()[-1].estado, 'EXITOSA')


class ComandoReevaluarRiesgoTests(ReevaluacionBaseTestCase):

    def test_comando_ejecuta_y_registra(self):
        out = StringIO()
        call_command('reevaluar_riesgo', '--max-intentos', '1', stdout=out)

        ej = EjecucionReevaluacion.objects.get()
        self.assertEqual((ej.origen, ej.estado), ('PROGRAMADA', 'EXITOSA'))
        self.assertIn('EXITOSA', out.getvalue())

    def test_comando_falla_con_codigo_de_salida_si_la_ejecucion_falla(self):
        Regla.objects.update(activo=False)
        with self.assertRaises(CommandError):
            call_command('reevaluar_riesgo', '--max-intentos', '1', stdout=StringIO())


@override_settings(REEVALUACION_CRON_TOKEN='secreto-cron')
class ReevaluacionEndpointsTests(ReevaluacionBaseTestCase):

    def setUp(self):
        super().setUp()
        self.admin = Usuario.objects.create(
            nombre='Admin', correo='admin@ufps.edu.co', rol='ADMINISTRADOR', contrasena='x'
        )
        self.url_programada = reverse('reevaluacion-programada')

    def test_programada_rechaza_token_invalido(self):
        resp = self.client.post(self.url_programada, HTTP_X_CRON_TOKEN='otro')
        self.assertEqual(resp.status_code, 401)

    @override_settings(REEVALUACION_CRON_TOKEN='')
    def test_programada_deshabilitada_sin_token_configurado(self):
        resp = self.client.post(self.url_programada, HTTP_X_CRON_TOKEN='')
        self.assertEqual(resp.status_code, 503)

    @patch('alertas.views.reevaluacion_views.lanzar_en_segundo_plano')
    def test_programada_con_token_inicia_ejecucion(self, lanzar):
        resp = self.client.post(self.url_programada, HTTP_X_CRON_TOKEN='secreto-cron')
        self.assertEqual(resp.status_code, 202)
        lanzar.assert_called_once_with('PROGRAMADA', None)

    @patch('alertas.views.reevaluacion_views.lanzar_en_segundo_plano')
    def test_programada_responde_409_si_hay_una_en_curso(self, lanzar):
        EjecucionReevaluacion.objects.create(estado='EN_CURSO')
        resp = self.client.post(self.url_programada, HTTP_X_CRON_TOKEN='secreto-cron')
        self.assertEqual(resp.status_code, 409)
        lanzar.assert_not_called()

    @patch('alertas.views.reevaluacion_views.lanzar_en_segundo_plano')
    def test_manual_requiere_administrador(self, lanzar):
        resp = self.client.post(reverse('reevaluacion-manual'))
        self.assertEqual(resp.status_code, 401)

        resp = self.client.post(reverse('reevaluacion-manual'),
                                HTTP_AUTHORIZATION=f'Bearer {_make_token(self.admin)}')
        self.assertEqual(resp.status_code, 202)
        lanzar.assert_called_once_with('MANUAL', self.admin)

    def test_lista_y_detalle_de_ejecuciones(self):
        ej = self._ejecutar()[-1]
        headers = {'HTTP_AUTHORIZATION': f'Bearer {_make_token(self.admin)}'}

        lista = self.client.get(reverse('reevaluacion-ejecuciones'), **headers).json()
        self.assertEqual(lista['ejecuciones'][0]['id'], ej.id)
        self.assertEqual(lista['ejecuciones'][0]['procesados'], 2)

        detalle = self.client.get(reverse('reevaluacion-ejecucion-detalle', args=[ej.id]), **headers).json()
        self.assertEqual(detalle['alcance']['tipo'], 'COMPLETO')
        self.assertEqual(len(detalle['detalle_cambios']), 2)


class ReprocesarAlertasTests(ReevaluacionBaseTestCase):
    """Reprocesar tras una importación no debe recrear ni renotificar alertas vigentes."""

    def setUp(self):
        super().setUp()
        Estudiante.objects.filter(pk=self.est_bueno.pk).update(promedio=Decimal('4.0'))
        Estudiante.objects.filter(pk=self.est_malo.pk).update(promedio=Decimal('2.2'))

    def test_no_recrea_ni_renotifica_alertas_que_siguen_aplicando(self):
        reprocesar_alertas_completas()
        alerta = Alerta.objects.get(estudiante=self.est_malo)
        self.assertEqual(self.notif.call_count, 1)

        Estudiante.objects.filter(pk=self.est_malo.pk).update(promedio=Decimal('2.0'))
        reprocesar_alertas_completas()

        self.assertEqual(self.notif.call_count, 1)
        actual = Alerta.objects.get(estudiante=self.est_malo)
        self.assertEqual(actual.id, alerta.id)
        self.assertEqual(actual.fecha_generacion, alerta.fecha_generacion)
        self.assertEqual(float(actual.valor_causa), 2.0)

    def test_borra_alerta_activa_sin_intervenciones_si_la_regla_ya_no_aplica(self):
        reprocesar_alertas_completas()
        Estudiante.objects.filter(pk=self.est_malo.pk).update(promedio=Decimal('4.5'))
        reprocesar_alertas_completas()
        self.assertFalse(Alerta.objects.filter(estudiante=self.est_malo).exists())


class ProteccionEndpointsTests(ReevaluacionBaseTestCase):
    """Endpoints que antes no exigían token o confiaban en un usuario_id del cliente."""

    def setUp(self):
        super().setUp()
        self.admin = Usuario.objects.create(nombre='Admin', correo='admin@ufps.edu.co', rol='ADMINISTRADOR', contrasena='x')
        self.director = Usuario.objects.create(nombre='Dir', correo='dir@ufps.edu.co', rol='DIRECTOR', contrasena='x')
        self.bienestar = Usuario.objects.create(nombre='Bien', correo='bien@ufps.edu.co', rol='BIENESTAR', contrasena='x')
        self.docente_ajeno = Usuario.objects.create(nombre='Otro', correo='otro@ufps.edu.co', rol='DOCENTE', contrasena='x')
        Docente.objects.create(codigo='D2', nombre='Otro', tipo_vinculacion='Planta', usuario=self.docente_ajeno)

        self.alerta = Alerta.objects.create(estudiante=self.est_malo, regla=self.regla_bajo, estado='activa')
        self.intervencion = Intervencion.objects.create(
            alerta=self.alerta, usuario=self.bienestar, tipo='TUTORIA', observaciones='x'
        )

    def _auth(self, usuario):
        return {'HTTP_AUTHORIZATION': f'Bearer {_make_token(usuario)}'}

    def test_endpoints_sin_token_responden_401(self):
        e = self.est_malo.codigo
        endpoints = [
            ('get', reverse('list-bitacoras')),
            ('get', reverse('detail-bitacora', args=[1])),
            ('post', reverse('subir-evidencia', args=[self.intervencion.id])),
            ('get', reverse('listar-evidencias', args=[self.intervencion.id])),
            ('delete', reverse('eliminar-evidencia', args=[1])),
            ('get', reverse('listar-intervenciones', args=[self.alerta.id])),
            ('get', reverse('gestionar-anotaciones', args=[self.intervencion.id])),
            ('post', reverse('gestionar-anotaciones', args=[self.intervencion.id])),
            ('delete', reverse('eliminar-anotacion', args=[1])),
            ('get', reverse('historial-notificaciones')),
            ('get', reverse('notificaciones-internas')),
            ('post', reverse('marcar-leida', args=[1])),
            ('get', reverse('student-indicators', args=[e])),
            ('get', reverse('student-history', args=[e])),
            ('get', reverse('student-interventions', args=[e])),
            ('get', reverse('course-indicators')),
            ('get', reverse('director-indicadores')),
        ]
        for metodo, url in endpoints:
            with self.subTest(url=url, metodo=metodo):
                self.assertEqual(getattr(self.client, metodo)(url).status_code, 401)

    def test_roles_sin_permiso_reciben_403(self):
        self.assertEqual(self.client.get(reverse('list-bitacoras'), **self._auth(self.bienestar)).status_code, 403)
        self.assertEqual(self.client.get(reverse('historial-notificaciones'), **self._auth(self.director)).status_code, 403)
        self.assertEqual(self.client.get(reverse('director-indicadores'), **self._auth(self.bienestar)).status_code, 403)

    def test_notificaciones_internas_solo_del_usuario_autenticado(self):
        propia = NotificacionInterna.objects.create(usuario=self.director, alerta=self.alerta, mensaje='mia')
        ajena = NotificacionInterna.objects.create(usuario=self.admin, alerta=self.alerta, mensaje='ajena')

        url = reverse('notificaciones-internas') + f'?usuario_id={self.admin.id}'
        data = self.client.get(url, **self._auth(self.director)).json()
        self.assertEqual([n['id'] for n in data['notificaciones']], [propia.id])

        resp = self.client.post(reverse('marcar-leida', args=[ajena.id]), **self._auth(self.director))
        self.assertEqual(resp.status_code, 404)
        ajena.refresh_from_db()
        self.assertFalse(ajena.leida)

    def test_anotacion_se_firma_con_el_usuario_autenticado(self):
        resp = self.client.post(
            reverse('gestionar-anotaciones', args=[self.intervencion.id]),
            data={'usuario_id': self.admin.id, 'texto': 'hola'},
            content_type='application/json',
            **self._auth(self.bienestar),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(AnotacionIntervencion.objects.get().usuario, self.bienestar)

    def test_solo_el_autor_o_un_admin_eliminan_anotaciones(self):
        anotacion = AnotacionIntervencion.objects.create(intervencion=self.intervencion, usuario=self.bienestar, texto='x')
        url = reverse('eliminar-anotacion', args=[anotacion.id])
        self.assertEqual(self.client.delete(url, **self._auth(self.director)).status_code, 403)
        self.assertEqual(self.client.delete(url, **self._auth(self.admin)).status_code, 200)

    def test_docente_no_ve_cursos_ajenos_aunque_envie_usuario_id_de_director(self):
        url = reverse('course-indicators') + f'?usuario_id={self.director.id}&periodo_anio=todos'
        data = self.client.get(url, **self._auth(self.docente_ajeno)).json()
        self.assertEqual(data['total'], 0)

        data = self.client.get(url, **self._auth(self.director)).json()
        self.assertEqual(data['total'], len(self.cursos))

    def test_docente_no_ve_datos_de_estudiantes_ajenos(self):
        for nombre in ('student-indicators', 'student-history', 'student-interventions'):
            with self.subTest(endpoint=nombre):
                url = reverse(nombre, args=[self.est_malo.codigo])
                self.assertEqual(self.client.get(url, **self._auth(self.docente_ajeno)).status_code, 403)
                self.assertEqual(self.client.get(url, **self._auth(self.bienestar)).status_code, 200)
