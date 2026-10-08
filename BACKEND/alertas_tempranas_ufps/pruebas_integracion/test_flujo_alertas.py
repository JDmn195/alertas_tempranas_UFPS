"""
Flujo principal: importación de notas → riesgo → alertas → notificaciones →
seguimiento (intervenciones) → cierre.
"""
from alertas.models import Alerta, Intervencion, NotificacionHistorial, NotificacionInterna, RiesgoEstudiante
from academico.models import BitacoraImportacion, Nota
from usuarios.models import Auditoria

from .base import IntegracionTestCase


class AutenticacionIntegracionTests(IntegracionTestCase):

    def test_login_entrega_token_valido_para_la_api(self):
        resp = self.login(self.director)
        self.assertEqual(resp.status_code, 200)
        token = resp.json()['token']

        me = self.client.get('/api/usuarios/me/', HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()['rol'], 'DIRECTOR')
        self.assertTrue(Auditoria.objects.filter(usuario=self.director, tipo_accion='LOGIN').exists())

    def test_credenciales_incorrectas_no_dan_acceso(self):
        resp = self.login(self.director, contrasena='incorrecta')
        self.assertEqual(resp.status_code, 401)
        self.assertNotIn('token', resp.json())

    def test_usuario_desactivado_pierde_el_acceso_con_su_token(self):
        token = self.token(self.bienestar)
        self.bienestar.activo = False
        self.bienestar.save()

        resp = self.client.get('/api/alertas/', HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(resp.status_code, 401)

    def test_endpoints_protegidos_sin_token(self):
        for nombre in ['listar-alertas', 'list-students', 'listar_crear_reglas']:
            self.assertEqual(self.api('get', nombre).status_code, 401, nombre)


class ImportacionGeneraAlertasTests(IntegracionTestCase):
    """HU-02 + HU-29 + HU-32: importar el historial dispara riesgo, alertas y notificaciones."""

    def test_importar_historial_genera_riesgo_alertas_y_notificaciones(self):
        resp = self.importar_historial(self.historial_en_riesgo())
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['creados'], 2)

        # Notas y promedio persistidos
        self.assertEqual(Nota.objects.filter(estudiante=self.estudiante).count(), 2)
        self.estudiante.refresh_from_db()
        self.assertEqual(float(self.estudiante.promedio), 2.0)
        self.assertTrue(BitacoraImportacion.objects.filter(tipo='HISTORIAL', exitoso=True).exists())

        # Riesgo calculado
        self.assertEqual(RiesgoEstudiante.objects.get(estudiante=self.estudiante).nivel_riesgo, 'high')

        # Alerta por promedio
        alerta_promedio = Alerta.objects.get(estudiante=self.estudiante, regla=self.regla_promedio)
        self.assertEqual(alerta_promedio.estado, 'activa')
        self.assertEqual(float(alerta_promedio.valor_causa), 2.0)

        # Alertas por corte (solo la de mayor umbral entre las de nota necesaria: C4)
        claves = set(
            Alerta.objects.filter(estudiante=self.estudiante, regla__tipo='CORTE', estado='activa')
            .values_list('regla__parametros__clave', flat=True)
        )
        self.assertEqual(claves, {'C1', 'C2A', 'C4'})
        c4 = Alerta.objects.get(estudiante=self.estudiante, regla__parametros__clave='C4')
        self.assertEqual(c4.metadata['curso_id'], self.curso_calculo.id)
        self.assertEqual(c4.metadata['periodo'], '2026-1')
        self.assertAlmostEqual(c4.metadata['nota_necesaria'], 5.33)

        # Notificaciones: correo (Brevo simulado) e internas
        self.assertTrue(self.brevo.called)
        self.assertTrue(NotificacionHistorial.objects.filter(
            alerta=alerta_promedio, destinatario='ana@ufps.edu.co', canal='EMAIL', resultado='exitoso',
        ).exists())
        # Alerta alta → director y administrador
        self.assertTrue(NotificacionInterna.objects.filter(usuario=self.director, alerta=alerta_promedio).exists())
        self.assertTrue(NotificacionInterna.objects.filter(usuario=self.admin, alerta=alerta_promedio).exists())
        # Alerta de corte → docente del curso
        self.assertTrue(NotificacionInterna.objects.filter(usuario=self.usuario_docente, alerta=c4).exists())

    def test_las_alertas_aparecen_en_la_api_segun_el_rol(self):
        self.importar_historial(self.historial_en_riesgo())

        data = self.api('get', 'listar-alertas', self.director).json()
        self.assertEqual(len(data['alertas']), 4)
        self.assertEqual(data['conteos']['activa'], 4)
        self.assertTrue(all(a['studentCode'] == '1152001' for a in data['alertas']))

        cortes = self.api('get', 'listar-alertas', self.director, query={'tipo_regla': 'CORTE'}).json()
        self.assertEqual(len(cortes['alertas']), 3)

        # El docente ve las alertas de los estudiantes de sus cursos...
        self.assertEqual(len(self.api('get', 'listar-alertas', self.usuario_docente).json()['alertas']), 4)
        # ...y otro docente no ve ninguna
        self.assertEqual(self.api('get', 'listar-alertas', self.usuario_otro_docente).json()['alertas'], [])

    def test_importar_notas_corregidas_cierra_las_alertas_de_corte(self):
        self.importar_historial(self.historial_en_riesgo())

        corregido = [
            self.fila('2025-2', '1150102', definitiva=2.0, nombre='Física I'),
            self.fila('2026-1', '1150101', c1=3.5, c2=3.5, c3=3.5, nombre='Cálculo I'),
        ]
        resp = self.importar_historial(corregido)
        self.assertEqual(resp.status_code, 200, resp.content)

        cortes = Alerta.objects.filter(estudiante=self.estudiante, regla__tipo='CORTE')
        self.assertEqual(cortes.count(), 3)
        for alerta in cortes:
            self.assertEqual(alerta.estado, 'cerrada')
            self.assertTrue(alerta.metadata['cierre_automatico'])
            self.assertEqual(alerta.metadata['motivo_cierre'], 'Nota corregida')

    def test_registrar_examen_final_cierra_la_alerta_de_nota_necesaria(self):
        self.importar_historial(self.historial_en_riesgo())

        con_examen = [
            self.fila('2025-2', '1150102', definitiva=2.0, nombre='Física I'),
            self.fila('2026-1', '1150101', c1=1.5, c2=2.0, c3=2.5, examen=4.0, nombre='Cálculo I'),
        ]
        self.importar_historial(con_examen)

        c4 = Alerta.objects.get(estudiante=self.estudiante, regla__parametros__clave='C4')
        self.assertEqual(c4.estado, 'cerrada')
        self.assertEqual(c4.metadata['motivo_cierre'], 'Examen final registrado')
        # La definitiva queda calculada: 2.0*0.7 + 4.0*0.3 = 2.6
        nota = Nota.objects.get(estudiante=self.estudiante, curso=self.curso_calculo)
        self.assertAlmostEqual(float(nota.definitiva), 2.6, places=1)

    def test_mejorar_el_promedio_cierra_la_alerta_de_promedio(self):
        self.importar_historial(self.historial_en_riesgo())

        mejorado = [
            self.fila('2025-2', '1150102', definitiva=4.5, nombre='Física I'),
            self.fila('2026-1', '1150101', c1=1.5, c2=2.0, c3=2.5, nombre='Cálculo I'),
        ]
        self.importar_historial(mejorado)

        alerta = Alerta.objects.get(estudiante=self.estudiante, regla=self.regla_promedio)
        self.assertEqual(alerta.estado, 'cerrada')
        self.assertEqual(RiesgoEstudiante.objects.get(estudiante=self.estudiante).nivel_riesgo, 'low')

    def test_archivo_con_errores_no_modifica_datos_ni_genera_alertas(self):
        filas = [self.fila('2026-1', '1150101', c1=7.0, c2=2.0, c3=2.5, nombre='Cálculo I')]
        resp = self.importar_historial(filas)

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['errores'][0]['campo'], 'Corte 1')
        self.assertFalse(Nota.objects.exists())
        self.assertFalse(Alerta.objects.exists())
        self.assertTrue(BitacoraImportacion.objects.filter(tipo='HISTORIAL', exitoso=False).exists())

    def test_solo_el_administrador_puede_importar(self):
        resp = self.importar_historial(self.historial_en_riesgo(), usuario=self.director)
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Nota.objects.exists())
        self.assertTrue(Auditoria.objects.filter(usuario=self.director, tipo_accion='ACCESO_DENEGADO').exists())


class SeguimientoAlertaTests(IntegracionTestCase):
    """HU-19/HU-20: ciclo de vida de una alerta a través de intervenciones."""

    def setUp(self):
        super().setUp()
        self.importar_historial(self.historial_en_riesgo())
        self.alerta = Alerta.objects.get(estudiante=self.estudiante, regla=self.regla_promedio)

    def _registrar(self, usuario, tipo='TUTORIA'):
        return self.api('post', 'registrar-intervencion', usuario, args=[self.alerta.id],
                        datos={'tipo': tipo, 'observaciones': 'Se cita al estudiante'})

    def test_ciclo_completo_activa_seguimiento_atendida_cerrada(self):
        # 1. Intervención → en_seguimiento
        resp = self._registrar(self.bienestar)
        self.assertEqual(resp.status_code, 201, resp.content)
        intervencion_id = resp.json()['intervencion']['id']
        self.alerta.refresh_from_db()
        self.assertEqual(self.alerta.estado, 'en_seguimiento')

        # 2. Anotación sobre la intervención
        resp = self.api('post', 'gestionar-anotaciones', self.bienestar, args=[intervencion_id],
                        datos={'texto': 'El estudiante asistió a la tutoría'})
        self.assertEqual(resp.status_code, 201)
        anotaciones = self.api('get', 'gestionar-anotaciones', self.director, args=[intervencion_id]).json()
        self.assertEqual(len(anotaciones['anotaciones']), 1)

        # 3. Concluir → atendida
        resp = self.api('post', 'concluir-intervencion', self.bienestar, args=[intervencion_id],
                        datos={'resultado': 'Plan de estudio acordado'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['estado_alerta'], 'atendida')

        # 4. El historial muestra la intervención concluida y su autor
        historial = self.api('get', 'listar-intervenciones', self.director, args=[self.alerta.id]).json()
        self.assertEqual(historial['estado'], 'atendida')
        self.assertEqual(historial['total'], 1)
        self.assertTrue(historial['intervenciones'][0]['concluida'])
        self.assertEqual(historial['intervenciones'][0]['usuario'], 'Bienestar')

        # 5. Cerrar → cerrada, y ya no admite intervenciones
        self.assertEqual(self.api('post', 'cerrar-alerta', self.director, args=[self.alerta.id]).status_code, 200)
        self.alerta.refresh_from_db()
        self.assertEqual(self.alerta.estado, 'cerrada')
        self.assertEqual(self._registrar(self.bienestar).status_code, 400)

        # 6. Todo quedó en la auditoría
        acciones = set(Auditoria.objects.values_list('tipo_accion', flat=True))
        self.assertTrue({'REGISTRAR_INTERVENCION', 'CONCLUIR_INTERVENCION', 'CERRAR_ALERTA'} <= acciones)

    def test_nueva_intervencion_abierta_devuelve_la_alerta_a_seguimiento(self):
        primera = self._registrar(self.bienestar).json()['intervencion']['id']
        self.api('post', 'concluir-intervencion', self.bienestar, args=[primera], datos={'resultado': 'OK'})
        self.alerta.refresh_from_db()
        self.assertEqual(self.alerta.estado, 'atendida')

        self._registrar(self.director, tipo='CITACION')
        self.alerta.refresh_from_db()
        self.assertEqual(self.alerta.estado, 'en_seguimiento')

    def test_docente_solo_gestiona_alertas_de_sus_estudiantes(self):
        self.assertEqual(self._registrar(self.usuario_docente).status_code, 201)
        self.assertEqual(self._registrar(self.usuario_otro_docente).status_code, 403)
        self.assertEqual(
            self.api('post', 'cerrar-alerta', self.usuario_otro_docente, args=[self.alerta.id]).status_code, 403
        )
        self.assertEqual(Intervencion.objects.filter(alerta=self.alerta).count(), 1)

    def test_intervencion_invalida_no_cambia_el_estado(self):
        resp = self.api('post', 'registrar-intervencion', self.bienestar, args=[self.alerta.id],
                        datos={'tipo': 'LLAMADA', 'observaciones': 'x'})
        self.assertEqual(resp.status_code, 400)
        self.alerta.refresh_from_db()
        self.assertEqual(self.alerta.estado, 'activa')
        self.assertFalse(Intervencion.objects.exists())
