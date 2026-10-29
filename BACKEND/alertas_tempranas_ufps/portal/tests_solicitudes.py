"""
HU-41: Solicitud de acompañamiento desde el portal (/api/portal/solicitudes/) y su
gestión por el personal (/api/alertas/solicitudes/).
"""
import json
import os
from unittest import mock

from django.urls import reverse

from alertas.models import NotificacionHistorial, NotificacionInterna, SolicitudAcompanamiento
from usuarios.models import Auditoria, Usuario

from .tests import _auth
from .tests_alertas import AlertasPortalBase

# Conjunto exacto de claves que ve el estudiante: cualquier campo nuevo debe agregarse a propósito
CLAVES_SOLICITUD = {
    'id', 'motivo', 'motivo_texto', 'descripcion', 'alerta', 'estado', 'estado_texto', 'respuesta',
    'responsable', 'fecha_solicitud', 'fecha_atencion', 'fecha_actualizacion', 'puede_cancelar',
}
DESCRIPCION = 'Necesito apoyo para organizar mis horarios de estudio este semestre.'


class SolicitudesBase(AlertasPortalBase):
    def setUp(self):
        super().setUp()
        env = mock.patch.dict(os.environ, {'BREVO_API_KEY': 'clave-prueba'})
        env.start()
        self.addCleanup(env.stop)
        brevo = mock.patch('alertas.services.requests.post')
        self.brevo = brevo.start()
        self.brevo.return_value.status_code = 201
        self.addCleanup(brevo.stop)

        self.bienestar = Usuario.objects.create(nombre='Laura Bienestar', correo='laura.privado@ufps.edu.co',
                                                rol='BIENESTAR')
        self.director = Usuario.objects.create(nombre='Directora', correo='directora@ufps.edu.co', rol='DIRECTOR')
        self.ana.email_institucional = 'ana.estudiante@ufps.edu.co'
        self.ana.save(update_fields=['email_institucional'])

    def _json(self, metodo, url, usuario, datos=None, query=None):
        kwargs = dict(_auth(usuario)) if usuario else {}
        if datos is not None:
            kwargs.update(data=json.dumps(datos), content_type='application/json')
        elif query is not None:
            kwargs['data'] = query
        with self.captureOnCommitCallbacks(execute=True):
            return getattr(self.client, metodo)(url, **kwargs)

    def crear(self, usuario=None, **datos):
        datos = {'motivo': 'ACADEMICO', 'descripcion': DESCRIPCION, **datos}
        return self._json('post', reverse('portal-solicitudes'), usuario or self.cuenta, datos)

    def listar(self, usuario=None):
        return self._json('get', reverse('portal-solicitudes'), usuario or self.cuenta)

    def cancelar(self, solicitud_id, usuario=None):
        return self._json('patch', reverse('portal-solicitud-cancelar', args=[solicitud_id]), usuario or self.cuenta)

    def gestionar(self, solicitud_id, usuario=None, **datos):
        return self._json('patch', reverse('solicitudes-gestionar', args=[solicitud_id]),
                          usuario or self.bienestar, datos)

    def bandeja(self, usuario=None, **query):
        return self._json('get', reverse('solicitudes-listar'), usuario or self.bienestar, query=query)

    def solicitud(self, estudiante=None, estado='PENDIENTE', **campos):
        return SolicitudAcompanamiento.objects.create(
            estudiante=estudiante or self.ana, motivo='PERSONAL', descripcion=DESCRIPCION, estado=estado, **campos,
        )


class CrearSolicitudTests(SolicitudesBase):

    def test_creacion_valida(self):
        resp = self.crear(motivo='SALUD')
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertEqual(set(data), CLAVES_SOLICITUD)
        self.assertEqual((data['motivo'], data['motivo_texto']), ('SALUD', 'Salud'))
        self.assertEqual((data['estado'], data['estado_texto']), ('PENDIENTE', 'Pendiente'))
        self.assertEqual(data['descripcion'], DESCRIPCION)
        self.assertIsNone(data['alerta'])
        self.assertIsNone(data['responsable'])
        self.assertTrue(data['puede_cancelar'])

        solicitud = SolicitudAcompanamiento.objects.get()
        self.assertEqual(solicitud.estudiante, self.ana)
        self.assertEqual(solicitud.periodo, self.periodo)  # el más reciente
        registro = Auditoria.objects.get(tipo_accion='SOLICITAR_ACOMPANAMIENTO')
        self.assertEqual(registro.usuario, self.cuenta)
        self.assertIn(f'solicitud ID {solicitud.id}', registro.detalle)

    def test_acepta_el_motivo_con_tilde_o_en_minusculas(self):
        self.assertEqual(self.crear(motivo='Académico').json()['motivo'], 'ACADEMICO')
        SolicitudAcompanamiento.objects.update(estado='CANCELADA')
        self.assertEqual(self.crear(motivo='económico').json()['motivo'], 'ECONOMICO')

    def test_con_alerta_propia(self):
        alerta = self.alerta_inasistencia()
        data = self.crear(alerta=alerta.id).json()
        self.assertEqual(data['alerta'], {'id': alerta.id, 'tipo': self.regla_inasistencia.nombre,
                                          'materia': 'Física I', 'periodo': '2026-1'})

    def test_campos_obligatorios(self):
        resp = self._json('post', reverse('portal-solicitudes'), self.cuenta, {})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(set(resp.json()['detalle']), {'motivo', 'descripcion'})
        resp = self.crear(motivo='  ', descripcion='   ')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(set(resp.json()['detalle']), {'motivo', 'descripcion'})
        self.assertFalse(SolicitudAcompanamiento.objects.exists())

    def test_motivo_invalido(self):
        resp = self.crear(motivo='DEPORTIVO')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('motivo', resp.json()['detalle'])
        self.assertFalse(SolicitudAcompanamiento.objects.exists())

    def test_descripcion_demasiado_corta(self):
        resp = self.crear(descripcion='Ayuda')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('20 caracteres', resp.json()['detalle']['descripcion'])

    def test_body_invalido(self):
        resp = self.client.post(reverse('portal-solicitudes'), data='{no es json', content_type='application/json',
                                **_auth(self.cuenta))
        self.assertEqual(resp.status_code, 400)

    def test_segunda_solicitud_con_una_en_curso(self):
        self.assertEqual(self.crear().status_code, 201)
        resp = self.crear(motivo='OTRO')
        self.assertEqual(resp.status_code, 409)
        self.assertIn('solicitud de acompañamiento en curso', resp.json()['error'])

        SolicitudAcompanamiento.objects.update(estado='EN_ATENCION')
        self.assertEqual(self.crear().status_code, 409)

        # Atendida la anterior, puede solicitar de nuevo
        SolicitudAcompanamiento.objects.update(estado='ATENDIDA')
        self.assertEqual(self.crear().status_code, 201)
        self.assertEqual(SolicitudAcompanamiento.objects.count(), 2)

    def test_la_solicitud_en_curso_de_otro_estudiante_no_bloquea(self):
        self.solicitud(estudiante=self.luis)
        self.assertEqual(self.crear().status_code, 201)

    def test_alerta_de_otro_estudiante(self):
        ajena = self.alerta_inasistencia(estudiante=self.luis)
        resp = self.crear(alerta=ajena.id)
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn('Luis', resp.content.decode())
        self.assertFalse(SolicitudAcompanamiento.objects.exists())
        registro = Auditoria.objects.get(usuario=self.cuenta, tipo_accion='ACCESO_DENEGADO')
        self.assertIn(f'alerta ID {ajena.id}', registro.detalle)

        self.assertEqual(self.crear(alerta=999999).status_code, 404)
        self.assertEqual(self.crear(alerta='abc').status_code, 400)

    def test_sin_token_y_roles_no_estudiante(self):
        resp = self.client.post(reverse('portal-solicitudes'), data=json.dumps({'motivo': 'OTRO'}),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(self.crear(usuario=self.bienestar).status_code, 403)
        self.assertFalse(SolicitudAcompanamiento.objects.exists())


class ConsultarYCancelarTests(SolicitudesBase):

    def test_solo_ve_sus_solicitudes_de_la_mas_reciente(self):
        antigua = self.solicitud(estado='ATENDIDA', responsable=self.bienestar, respuesta='Te esperamos el lunes.')
        reciente = self.solicitud()
        self.solicitud(estudiante=self.luis)

        data = self.listar().json()
        self.assertEqual([s['id'] for s in data['solicitudes']], [reciente.id, antigua.id])
        self.assertEqual(data['en_curso'], reciente.id)
        self.assertFalse(data['puede_solicitar'])
        self.assertIn('en curso', data['mensaje_bloqueo'])
        self.assertEqual({m['valor'] for m in data['motivos']},
                         {'ACADEMICO', 'PERSONAL', 'ECONOMICO', 'SALUD', 'OTRO'})

        atendida = data['solicitudes'][1]
        self.assertEqual(set(atendida), CLAVES_SOLICITUD)
        self.assertEqual(atendida['respuesta'], 'Te esperamos el lunes.')
        # Del responsable solo el nombre
        self.assertEqual(atendida['responsable'], 'Laura Bienestar')
        self.assertNotIn('laura.privado', self.listar().content.decode())

        # Luis solo ve la suya, aunque pida el código de Ana
        resp = self._json('get', reverse('portal-solicitudes'), self.otra_cuenta, query={'codigo': self.ana.codigo})
        self.assertEqual(len(resp.json()['solicitudes']), 1)

    def test_sin_solicitudes(self):
        data = self.listar().json()
        self.assertEqual(data['solicitudes'], [])
        self.assertTrue(data['puede_solicitar'])
        self.assertIsNone(data['en_curso'])

    def test_cancelar_una_pendiente(self):
        solicitud = self.solicitud()
        resp = self.cancelar(solicitud.id)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['estado'], 'CANCELADA')
        self.assertFalse(resp.json()['puede_cancelar'])
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'CANCELADA')
        self.assertTrue(Auditoria.objects.filter(usuario=self.cuenta, tipo_accion='CANCELAR_SOLICITUD').exists())
        # Ya puede enviar otra
        self.assertEqual(self.crear().status_code, 201)

    def test_no_cancela_una_atendida_ni_en_atencion(self):
        for estado in ('ATENDIDA', 'EN_ATENCION', 'CANCELADA'):
            solicitud = self.solicitud(estado=estado)
            resp = self.cancelar(solicitud.id)
            self.assertEqual(resp.status_code, 409, estado)
            solicitud.refresh_from_db()
            self.assertEqual(solicitud.estado, estado)

    def test_no_cancela_la_de_otro_estudiante(self):
        ajena = self.solicitud(estudiante=self.luis)
        resp = self.cancelar(ajena.id)
        self.assertEqual(resp.status_code, 404)
        ajena.refresh_from_db()
        self.assertEqual(ajena.estado, 'PENDIENTE')
        self.assertIn(f'ID {ajena.id}', Auditoria.objects.get(tipo_accion='ACCESO_DENEGADO').detalle)

    def test_cancelar_exige_patch(self):
        solicitud = self.solicitud()
        resp = self.client.post(reverse('portal-solicitud-cancelar', args=[solicitud.id]), **_auth(self.cuenta))
        self.assertEqual(resp.status_code, 405)


class NotificacionSolicitudTests(SolicitudesBase):

    def test_notifica_a_bienestar_al_crearla(self):
        docente_antes = NotificacionInterna.objects.filter(usuario=self.docente_usuario).count()
        solicitud_id = self.crear(motivo='ECONOMICO').json()['id']

        historial = NotificacionHistorial.objects.filter(solicitud_id=solicitud_id, tipo='SOLICITUD')
        self.assertEqual(set(historial.values_list('canal', 'destinatario', 'rol_destinatario')), {
            ('EMAIL', 'laura.privado@ufps.edu.co', 'BIENESTAR'),
            ('INTERNA', 'laura.privado@ufps.edu.co', 'BIENESTAR'),
        })
        self.assertEqual(set(historial.values_list('resultado', flat=True)), {'exitoso'})
        interna = NotificacionInterna.objects.get(usuario=self.bienestar)
        self.assertEqual(interna.solicitud_id, solicitud_id)
        self.assertIsNone(interna.alerta)
        self.assertIn('Económico', interna.mensaje)
        self.assertIn('Ana Pérez', interna.mensaje)
        # El correo lleva motivo, nombre y fecha
        html = self.brevo.call_args.kwargs['json']['htmlContent']
        self.assertIn('Ana Pérez', html)
        self.assertIn('Económico', html)
        # Solo Bienestar
        self.assertFalse(NotificacionInterna.objects.filter(usuario=self.director).exists())
        self.assertEqual(NotificacionInterna.objects.filter(usuario=self.docente_usuario).count(), docente_antes)

    def test_no_notifica_si_no_se_confirma(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.client.post(reverse('portal-solicitudes'),
                             data=json.dumps({'motivo': 'OTRO', 'descripcion': DESCRIPCION}),
                             content_type='application/json', **_auth(self.cuenta))
        self.assertEqual(len(callbacks), 1)
        self.assertFalse(NotificacionHistorial.objects.filter(tipo='SOLICITUD').exists())

    def test_un_error_de_envio_no_afecta_la_solicitud(self):
        self.brevo.side_effect = RuntimeError('Brevo caído')
        resp = self.crear()
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(NotificacionHistorial.objects.get(canal='EMAIL').resultado, 'reintento')

    def test_notifica_al_estudiante_cuando_responde_el_personal(self):
        solicitud = self.solicitud()
        self.gestionar(solicitud.id, estado='EN_ATENCION')
        self.gestionar(solicitud.id, estado='ATENDIDA', respuesta='Agendamos una cita el lunes a las 10 a. m.')

        correos = NotificacionHistorial.objects.filter(solicitud=solicitud, canal='EMAIL', rol_destinatario='ESTUDIANTE')
        self.assertEqual(correos.count(), 2)
        self.assertEqual(set(correos.values_list('destinatario', flat=True)), {'ana.estudiante@ufps.edu.co'})
        internas = NotificacionInterna.objects.filter(usuario=self.cuenta, solicitud=solicitud)
        self.assertEqual(internas.count(), 2)
        self.assertIn('Agendamos una cita', internas.first().mensaje)

    def test_bandeja_de_notificaciones_internas_sin_alerta(self):
        self.crear()
        resp = self.client.get(reverse('notificaciones-internas'), **_auth(self.bienestar))
        self.assertEqual(resp.status_code, 200)
        [notificacion] = resp.json()['notificaciones']
        self.assertIsNone(notificacion['alerta'])
        self.assertIsNotNone(notificacion['solicitud_id'])

        admin = Usuario.objects.create(nombre='Admin', correo='admin@ufps.edu.co', rol='ADMINISTRADOR')
        resp = self.client.get(reverse('historial-notificaciones'), {'tipo': 'SOLICITUD'}, **_auth(admin))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual({n['estudiante'] for n in resp.json()['historial']}, {'Ana Pérez'})


class GestionSolicitudesPersonalTests(SolicitudesBase):

    def test_bandeja_con_datos_del_estudiante_y_filtros(self):
        pendiente = self.solicitud(periodo=self.periodo, alerta=self.alerta_inasistencia())
        atendida = self.solicitud(estudiante=self.luis, estado='ATENDIDA', periodo=self.periodo_anterior)

        data = self.bandeja().json()
        self.assertEqual([s['id'] for s in data['solicitudes']], [atendida.id, pendiente.id])
        self.assertEqual(data['conteos'], {'PENDIENTE': 1, 'EN_ATENCION': 0, 'ATENDIDA': 1, 'CANCELADA': 0,
                                           'total': 2})
        self.assertEqual(data['periodos'], ['2026-1', '2025-2'])
        item = next(s for s in data['solicitudes'] if s['id'] == pendiente.id)
        self.assertEqual(item['estudiante']['codigo'], self.ana.codigo)
        self.assertEqual(item['estudiante']['nombre'], 'Ana Pérez')
        self.assertEqual(item['alerta']['tipo'], self.regla_inasistencia.nombre)
        self.assertEqual(item['transiciones'], ['EN_ATENCION', 'ATENDIDA', 'CANCELADA'])

        self.assertEqual([s['id'] for s in self.bandeja(estado='pendiente').json()['solicitudes']], [pendiente.id])
        self.assertEqual([s['id'] for s in self.bandeja(periodo='2025-2').json()['solicitudes']], [atendida.id])
        self.assertEqual(self.bandeja(estado='ABIERTA').status_code, 400)
        self.assertEqual(self.bandeja(periodo='2026').status_code, 400)
        # Dirección también gestiona la bandeja
        self.assertEqual(self.bandeja(usuario=self.director).status_code, 200)

    def test_tomar_asigna_responsable_y_queda_en_auditoria(self):
        solicitud = self.solicitud()
        resp = self.gestionar(solicitud.id, estado='EN_ATENCION')
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(data['estado'], 'EN_ATENCION')
        self.assertEqual(data['responsable'], {'id': self.bienestar.id, 'nombre': 'Laura Bienestar'})
        self.assertEqual(data['transiciones'], ['ATENDIDA', 'CANCELADA'])

        registro = Auditoria.objects.get(tipo_accion='GESTIONAR_SOLICITUD')
        self.assertEqual(registro.usuario, self.bienestar)
        self.assertIn('PENDIENTE -> EN_ATENCION', registro.detalle)
        self.assertIn(self.ana.codigo, registro.detalle)

        # El estudiante ve el cambio y ya no puede cancelarla
        [propia] = self.listar().json()['solicitudes']
        self.assertEqual((propia['estado'], propia['responsable'], propia['puede_cancelar']),
                         ('EN_ATENCION', 'Laura Bienestar', False))

    def test_asigna_otro_responsable(self):
        solicitud = self.solicitud()
        resp = self.gestionar(solicitud.id, estado='EN_ATENCION', responsable_id=self.director.id)
        self.assertEqual(resp.json()['responsable']['nombre'], 'Directora')
        # Un docente o un estudiante no pueden ser responsables
        for usuario in (self.docente_usuario, self.cuenta):
            self.assertEqual(self.gestionar(solicitud.id, responsable_id=usuario.id).status_code, 400)

    def test_atendida_exige_respuesta_y_guarda_fecha_de_atencion(self):
        solicitud = self.solicitud(estado='EN_ATENCION', responsable=self.bienestar)
        resp = self.gestionar(solicitud.id, estado='ATENDIDA')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('respuesta', resp.json()['error'])
        self.assertEqual(self.gestionar(solicitud.id, estado='ATENDIDA', respuesta='   ').status_code, 400)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'EN_ATENCION')
        self.assertIsNone(solicitud.fecha_atencion)

        resp = self.gestionar(solicitud.id, estado='ATENDIDA', respuesta='Te remitimos a tutoría de Cálculo.')
        self.assertEqual(resp.status_code, 200, resp.content)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'ATENDIDA')
        self.assertIsNotNone(solicitud.fecha_atencion)
        self.assertEqual(self.listar().json()['solicitudes'][0]['respuesta'], 'Te remitimos a tutoría de Cálculo.')

    def test_responder_antes_de_cerrar(self):
        solicitud = self.solicitud(estado='EN_ATENCION', responsable=self.bienestar)
        self.assertEqual(self.gestionar(solicitud.id, respuesta='Te escribimos al correo.').status_code, 200)
        resp = self.gestionar(solicitud.id, estado='ATENDIDA')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['respuesta'], 'Te escribimos al correo.')

    def test_estados_finales_y_transiciones_invalidas(self):
        atendida = self.solicitud(estado='ATENDIDA', respuesta='Listo')
        self.assertEqual(self.gestionar(atendida.id, estado='EN_ATENCION').status_code, 409)
        self.assertEqual(self.gestionar(atendida.id, respuesta='Otra').status_code, 409)
        en_atencion = self.solicitud(estudiante=self.luis, estado='EN_ATENCION')
        self.assertEqual(self.gestionar(en_atencion.id, estado='PENDIENTE').status_code, 409)
        self.assertEqual(self.gestionar(en_atencion.id, estado='OTRO').status_code, 400)
        self.assertEqual(self.gestionar(en_atencion.id).status_code, 400)
        self.assertEqual(self.gestionar(999999, estado='EN_ATENCION').status_code, 404)

    def test_cancelacion_por_el_personal(self):
        solicitud = self.solicitud()
        resp = self.gestionar(solicitud.id, estado='CANCELADA', respuesta='Solicitud duplicada por otro canal.')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['estado'], 'CANCELADA')

    def test_roles_sin_permiso_reciben_403(self):
        solicitud = self.solicitud()
        for usuario in (self.cuenta, self.docente_usuario):
            self.assertEqual(self.bandeja(usuario=usuario).status_code, 403)
            self.assertEqual(self.gestionar(solicitud.id, usuario=usuario, estado='EN_ATENCION').status_code, 403)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'PENDIENTE')
        self.assertEqual(Auditoria.objects.filter(tipo_accion='ACCESO_DENEGADO').count(), 4)
        self.assertEqual(self._json('get', reverse('solicitudes-listar'), None).status_code, 401)
