"""
HU-36: alertas por inasistencia sobre el umbral del curso o general.

Los correos se simulan (NotificationService.enviar_brevo) y las tareas en segundo plano
corren de forma síncrona en las pruebas (TAREAS_EN_SEGUNDO_PLANO=False); donde importa
que el disparador use el hilo, se simula ejecutar_en_segundo_plano.
"""
import json
from datetime import date
from decimal import Decimal
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from academico.models import Estudiante, Nota
from academico.tests_inasistencia import InasistenciaBaseTestCase
from alertas.alertas_inasistencia import (
    MOTIVO_CIERRE, evaluar_inasistencia, evaluar_inasistencia_curso, evaluar_inasistencia_periodo_actual,
)
from alertas.models import Alerta, NotificacionHistorial, Regla, RiesgoEstudiante, RiesgoEstudiantePeriodo
from alertas.services import NotificationService
from usuarios.models import Auditoria

SEIS_DOS_FALTAS = ['ASISTIO', 'FALTA', 'ASISTIO', 'FALTA', 'ASISTIO', 'ASISTIO']          # 33,33 %
SEIS_UNA_FALTA = ['ASISTIO', 'FALTA', 'ASISTIO', 'ASISTIO', 'ASISTIO', 'ASISTIO']         # 16,67 %
SEIS_UNA_FALTA_DOS_JUST = ['ASISTIO', 'FALTA', 'FALTA_JUSTIFICADA', 'FALTA_JUSTIFICADA', 'ASISTIO', 'ASISTIO']


class AlertaInasistenciaBaseTestCase(InasistenciaBaseTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(NotificationService, 'enviar_brevo', return_value=('exitoso', None))
        self.brevo = patcher.start()
        self.addCleanup(patcher.stop)
        # Regla de la migración 0018: '>' 20 %, nivel high, min_clases 4, activa
        self.regla = Regla.objects.get(tipo='INASISTENCIA')
        self.est = self.estudiantes[0]
        Estudiante.objects.filter(pk=self.est.pk).update(email_institucional='est1@ufps.edu.co')
        self.est.refresh_from_db()

    def evaluar(self, estudiante=None, curso=None, periodo=None):
        with self.captureOnCommitCallbacks(execute=True):
            return evaluar_inasistencia(estudiante or self.est, curso or self.curso, periodo or self.periodo)

    def evaluar_curso(self, curso=None, periodo=None):
        with self.captureOnCommitCallbacks(execute=True):
            return evaluar_inasistencia_curso(curso or self.curso, periodo or self.periodo)

    def alertas(self, estudiante=None):
        return Alerta.objects.filter(regla=self.regla, estudiante=estudiante or self.est).order_by('id')

    def justificar(self, estudiante, fecha):
        estudiante.asistencias.filter(fecha_clase=fecha).update(estado='FALTA_JUSTIFICADA')


class EvaluacionInasistenciaTests(AlertaInasistenciaBaseTestCase):

    def test_supera_umbral_genera_alerta_con_metadata(self):
        self.registrar(self.est, SEIS_DOS_FALTAS)
        afectadas = self.evaluar()

        self.assertEqual(len(afectadas), 1)
        alerta = self.alertas().get()
        self.assertEqual(alerta.estado, 'activa')
        self.assertEqual(alerta.valor_causa, Decimal('33.33'))
        self.assertEqual(alerta.metadata, {
            'curso_id': self.curso.id,
            'materia_codigo': '1155501',
            'materia_nombre': 'Programacion Web',
            'grupo': 'A',
            'periodo': '2026-2',
            'porcentaje': 33.33,
            'umbral': 20.0,
            'origen_umbral': 'general',
            'total_clases': 6,
            'faltas': 2,
            'faltas_justificadas': 0,
        })
        self.assertTrue(Auditoria.objects.filter(tipo_accion='GENERAR_ALERTAS',
                                                 detalle__contains=self.est.codigo).exists())

    def test_bajo_el_umbral_no_genera_alerta(self):
        self.registrar(self.est, SEIS_UNA_FALTA)
        self.assertEqual(self.evaluar(), [])
        self.assertFalse(self.alertas().exists())

    def test_faltas_justificadas_no_cuentan(self):
        self.registrar(self.est, SEIS_UNA_FALTA_DOS_JUST)
        self.assertEqual(self.evaluar(), [])
        self.assertFalse(self.alertas().exists())

    def test_menos_clases_que_min_clases_no_se_evalua(self):
        self.registrar(self.est, ['FALTA', 'ASISTIO'])  # 50 % pero solo 2 clases (< 4)
        self.assertEqual(self.evaluar(), [])
        self.assertFalse(self.alertas().exists())

        # Tampoco cierra una alerta abierta
        abierta = Alerta.objects.create(estudiante=self.est, regla=self.regla, estado='activa',
                                        valor_causa=Decimal('50'),
                                        metadata={'curso_id': self.curso.id, 'periodo': '2026-2'})
        self.assertEqual(self.evaluar(), [])
        abierta.refresh_from_db()
        self.assertEqual(abierta.estado, 'activa')

    def test_umbral_propio_del_curso_reemplaza_al_general(self):
        self.curso.umbral_inasistencia = Decimal('40')
        self.curso.save()
        self.registrar(self.est, SEIS_DOS_FALTAS)
        self.assertEqual(self.evaluar(), [])
        self.assertFalse(self.alertas().exists())

    def test_operador_de_la_regla(self):
        # Con '>=' y umbral 33.33, el mismo porcentaje sí aplica
        Regla.objects.filter(pk=self.regla.pk).update(operador='>=', valor_umbral=Decimal('33.33'))
        self.registrar(self.est, SEIS_DOS_FALTAS)
        self.assertEqual(len(self.evaluar()), 1)

    def test_evaluar_dos_veces_deja_una_sola_alerta(self):
        self.registrar(self.est, SEIS_DOS_FALTAS)
        self.evaluar()
        self.evaluar()
        self.evaluar_curso()
        self.assertEqual(self.alertas().count(), 1)
        # Una sola notificación al estudiante
        self.assertEqual(NotificacionHistorial.objects.filter(rol_destinatario='ESTUDIANTE').count(), 1)

    def test_actualiza_la_alerta_abierta(self):
        self.registrar(self.est, SEIS_DOS_FALTAS)
        self.evaluar()
        primera = self.est.asistencias.filter(estado='ASISTIO').order_by('fecha_clase').first()
        primera.estado = 'FALTA'
        primera.save()  # 3 de 6 = 50 %
        self.evaluar()
        alerta = self.alertas().get()
        self.assertEqual(alerta.valor_causa, Decimal('50.00'))
        self.assertEqual(alerta.metadata['faltas'], 3)

    def test_cierre_automatico_y_nueva_alerta_al_recaer(self):
        self.registrar(self.est, SEIS_DOS_FALTAS)
        self.evaluar()
        faltas = list(self.est.asistencias.filter(estado='FALTA').values_list('fecha_clase', flat=True))

        self.justificar(self.est, faltas[0])  # 1 de 6 = 16,67 %
        self.evaluar()
        cerrada = self.alertas().get()
        self.assertEqual(cerrada.estado, 'cerrada')
        self.assertTrue(cerrada.metadata['cierre_automatico'])
        self.assertEqual(cerrada.metadata['motivo_cierre'], MOTIVO_CIERRE)
        self.assertTrue(Auditoria.objects.filter(tipo_accion='CERRAR_ALERTA',
                                                 detalle__contains=str(cerrada.id)).exists())

        self.est.asistencias.filter(fecha_clase=faltas[0]).update(estado='FALTA')  # vuelve a 33,33 %
        self.evaluar()
        alertas = list(self.alertas())
        self.assertEqual([a.estado for a in alertas], ['cerrada', 'activa'])

    def test_regla_desactivada_no_genera_alertas(self):
        Regla.objects.filter(pk=self.regla.pk).update(activo=False)
        self.registrar(self.est, SEIS_DOS_FALTAS)
        self.assertEqual(self.evaluar(), [])
        self.assertEqual(self.evaluar_curso(), [])
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(evaluar_inasistencia_periodo_actual(), [])
        self.assertFalse(Alerta.objects.filter(regla__tipo='INASISTENCIA').exists())

    def test_solo_periodo_mas_reciente(self):
        Nota.objects.create(estudiante=self.est, curso=self.curso, periodo=self.periodo_anterior)
        self.registrar(self.est, SEIS_DOS_FALTAS, periodo=self.periodo_anterior, inicio=date(2026, 3, 1))
        self.assertEqual(self.evaluar(periodo=self.periodo_anterior), [])
        self.assertEqual(self.evaluar_curso(periodo=self.periodo_anterior), [])
        self.assertFalse(self.alertas().exists())


class EvaluacionCursoTests(AlertaInasistenciaBaseTestCase):

    def test_evalua_a_todos_los_matriculados(self):
        self.registrar(self.estudiantes[0], SEIS_DOS_FALTAS)
        self.registrar(self.estudiantes[1], SEIS_UNA_FALTA)
        self.registrar(self.estudiantes[2], ['FALTA', 'FALTA'])
        self.evaluar_curso()
        self.assertEqual(
            list(Alerta.objects.filter(regla=self.regla).values_list('estudiante_id', flat=True)),
            [self.estudiantes[0].codigo],
        )

    def test_consultas_no_crecen_con_los_estudiantes(self):
        # 0 % de inasistencia: ni alerta ni aviso preventivo, el estado no cambia
        for est in self.estudiantes:
            self.registrar(est, ['ASISTIO'] * 6)
        with CaptureQueriesContext(connection) as antes:
            self.evaluar_curso()

        for i in range(10, 30):
            est = Estudiante.objects.create(codigo=f"11520{i}", nombre=f"Extra {i}", semestre=5,
                                            numero_documento=f"X{i}")
            Nota.objects.create(estudiante=est, curso=self.curso, periodo=self.periodo)
            self.registrar(est, ['ASISTIO'] * 6)
        with CaptureQueriesContext(connection) as despues:
            self.evaluar_curso()
        # Sin cambios de alertas, solo cambian los savepoints de la transacción por estudiante
        sin_savepoints = lambda ctx: [q for q in ctx.captured_queries if 'SAVEPOINT' not in q['sql']]
        self.assertEqual(len(sin_savepoints(antes)), len(sin_savepoints(despues)))

    def test_periodo_actual_evalua_todos_los_cursos_con_asistencia(self):
        self.registrar(self.est, SEIS_DOS_FALTAS)
        ajeno = self.no_matriculado
        self.registrar(ajeno, SEIS_DOS_FALTAS, curso=self.curso_ajeno)
        with self.captureOnCommitCallbacks(execute=True):
            evaluar_inasistencia_periodo_actual()
        self.assertEqual(
            set(Alerta.objects.filter(regla=self.regla).values_list('estudiante_id', 'metadata__curso_id')),
            {(self.est.codigo, self.curso.id), (ajeno.codigo, self.curso_ajeno.id)},
        )


class NivelRiesgoInasistenciaTests(AlertaInasistenciaBaseTestCase):

    def nivel(self):
        return RiesgoEstudiantePeriodo.objects.get(estudiante=self.est, periodo=self.periodo).nivel_riesgo

    def test_superar_el_umbral_sube_el_riesgo_a_high(self):
        self.registrar(self.est, SEIS_DOS_FALTAS)
        self.evaluar()
        self.assertEqual(self.nivel(), 'high')
        self.assertEqual(RiesgoEstudiante.objects.get(estudiante=self.est).nivel_riesgo, 'high')
        aplicadas = RiesgoEstudiantePeriodo.objects.get(estudiante=self.est, periodo=self.periodo).reglas_aplicadas
        factor = next(r for r in aplicadas if r.get('tipo') == 'INASISTENCIA')
        self.assertEqual(factor['id'], self.regla.id)
        self.assertEqual(factor['valor'], 33.33)
        self.assertEqual(factor['cursos'][0]['curso_id'], self.curso.id)

        # Al cerrarse la alerta (faltas justificadas) se recalcula y el factor desaparece
        fecha = self.est.asistencias.filter(estado='FALTA').values_list('fecha_clase', flat=True).first()
        self.justificar(self.est, fecha)
        self.evaluar()
        self.assertNotEqual(self.nivel(), 'high')

    def test_sin_superar_o_bajo_min_clases_no_cuenta(self):
        from alertas.views.alert_generation_views import calcular_y_guardar_riesgo_por_periodos

        self.registrar(self.est, ['FALTA', 'FALTA'])
        calcular_y_guardar_riesgo_por_periodos(self.est)
        self.assertNotEqual(self.nivel(), 'high')

    def test_cerrar_la_alerta_a_mano_no_quita_el_factor(self):
        from alertas.views.alert_generation_views import calcular_y_guardar_riesgo_por_periodos

        self.registrar(self.est, SEIS_DOS_FALTAS)
        self.evaluar()
        Alerta.objects.filter(regla=self.regla).update(estado='cerrada')
        calcular_y_guardar_riesgo_por_periodos(self.est)
        self.assertEqual(self.nivel(), 'high')


class NotificacionInasistenciaTests(AlertaInasistenciaBaseTestCase):

    def test_notifica_al_estudiante_al_docente_y_al_director(self):
        from usuarios.models import Usuario
        Usuario.objects.create(nombre='Director', correo='director@ufps.edu.co', rol='DIRECTOR',
                               contrasena='x', activo=True)
        self.registrar(self.est, SEIS_DOS_FALTAS)
        self.evaluar()

        roles = set(NotificacionHistorial.objects.filter(canal='EMAIL').values_list('rol_destinatario', flat=True))
        self.assertTrue({'ESTUDIANTE', 'DOCENTE', 'DIRECTOR'} <= roles)
        self.assertTrue(NotificacionHistorial.objects.filter(
            canal='INTERNA', destinatario=self.user_docente.correo).exists())

        html = next(c.args[2] for c in self.brevo.call_args_list if c.args[0] == 'est1@ufps.edu.co')
        self.assertIn('Programacion Web', html)
        self.assertIn('33.33 %', html)
        self.assertIn('20.0 %', html)
        self.assertIn('2 de 6 clases', html)

    def test_los_valores_se_escapan(self):
        self.materia.nombre = '<script>x</script>'
        self.materia.save()
        self.registrar(self.est, SEIS_DOS_FALTAS)
        self.evaluar()
        html = next(c.args[2] for c in self.brevo.call_args_list if c.args[0] == 'est1@ufps.edu.co')
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)


class DisparadoresInasistenciaTests(AlertaInasistenciaBaseTestCase):

    def test_registro_manual_dispara_en_segundo_plano(self):
        with mock.patch('alertas.tareas.ejecutar_en_segundo_plano') as hilo:
            with self.captureOnCommitCallbacks(execute=True):
                res = self.client.post(
                    reverse('course-attendance', args=[self.curso.id]),
                    json.dumps({'fecha': '2026-09-01', 'registros': [
                        {'codigo_estudiante': self.est.codigo, 'estado': 'FALTA'}]}),
                    content_type='application/json', HTTP_AUTHORIZATION=self.auth(self.user_docente),
                )
        self.assertEqual(res.status_code, 200, res.content)
        hilo.assert_called_once()
        self.assertIs(hilo.call_args.args[0], evaluar_inasistencia_curso)
        self.assertEqual(hilo.call_args.args[1], self.curso)

    def test_registro_manual_genera_la_alerta(self):
        self.registrar(self.est, SEIS_UNA_FALTA)
        fecha = self.est.asistencias.filter(estado='ASISTIO').values_list('fecha_clase', flat=True).first()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse('course-attendance', args=[self.curso.id]),
                json.dumps({'fecha': fecha.isoformat(), 'registros': [
                    {'codigo_estudiante': self.est.codigo, 'estado': 'FALTA'}]}),
                content_type='application/json', HTTP_AUTHORIZATION=self.auth(self.user_docente),
            )
        self.assertEqual(self.alertas().get().valor_causa, Decimal('33.33'))

    def test_cambio_de_umbral_del_curso(self):
        self.registrar(self.est, SEIS_DOS_FALTAS)
        self.evaluar()
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.patch(
                reverse('course-absence-threshold', args=[self.curso.id]), json.dumps({'umbral': 40}),
                content_type='application/json', HTTP_AUTHORIZATION=self.auth(self.admin),
            )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.alertas().get().estado, 'cerrada')

    def test_cambio_de_umbral_usa_el_hilo(self):
        with mock.patch('alertas.tareas.ejecutar_en_segundo_plano') as hilo:
            self.client.patch(
                reverse('course-absence-threshold', args=[self.curso.id]), json.dumps({'umbral': 40}),
                content_type='application/json', HTTP_AUTHORIZATION=self.auth(self.admin),
            )
        hilo.assert_called_once()
        self.assertIs(hilo.call_args.args[0], evaluar_inasistencia_curso)

    def test_editar_la_regla_reevalua_el_periodo_actual(self):
        self.registrar(self.est, SEIS_UNA_FALTA)  # 16,67 %
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.put(
                reverse('detalle_regla', args=[self.regla.id]), json.dumps({'valor_umbral': 10}),
                content_type='application/json', HTTP_AUTHORIZATION=self.auth(self.admin),
            )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(self.alertas().get().metadata['umbral'], 10.0)

    def test_desactivar_la_regla_no_genera_alertas(self):
        self.registrar(self.est, SEIS_DOS_FALTAS)
        with mock.patch('alertas.alertas_inasistencia.evaluar_inasistencia_periodo_actual',
                        wraps=evaluar_inasistencia_periodo_actual) as evaluar:
            self.client.put(
                reverse('detalle_regla', args=[self.regla.id]), json.dumps({'activo': False}),
                content_type='application/json', HTTP_AUTHORIZATION=self.auth(self.admin),
            )
        evaluar.assert_called_once()
        self.assertFalse(self.alertas().exists())

    def test_comando_de_reevaluacion(self):
        self.registrar(self.est, SEIS_DOS_FALTAS)
        with mock.patch('alertas.management.commands.reevaluar_riesgo.ejecutar_reevaluacion', return_value=[]):
            with self.assertRaises(CommandError):  # sin ejecuciones del motor general
                call_command('reevaluar_riesgo', stdout=mock.MagicMock())
        self.assertEqual(self.alertas().count(), 1)


class FlujoImportacionInasistenciaTests(AlertaInasistenciaBaseTestCase):
    """Caso de formato_asistencia.xlsx (1155501A, 2026-2)."""

    def test_importar_genera_alertas_y_justificar_cierra(self):
        Estudiante.objects.create(codigo="1152004", nombre="Estudiante 4", semestre=5, numero_documento="DOC4",
                                  email_institucional='est4@ufps.edu.co')
        Nota.objects.create(estudiante_id="1152004", curso=self.curso, periodo=self.periodo)
        fechas = ['2026-09-01', '2026-09-03', '2026-09-08', '2026-09-10', '2026-09-15', '2026-09-17']
        estados = {
            '1152001': ['A', 'A', 'A', 'A', 'A', 'A'],
            '1152002': ['A', 'F', 'F', 'A', 'F', 'A'],
            '1152003': ['A', 'FJ', 'A', 'A', 'F', 'A'],
            '1152004': ['F', 'A', 'A', 'F', 'A', 'A'],
        }
        filas = [
            {'Periodo': '2026-2', 'Codigo Estudiante': codigo, 'Materia': '1155501A', 'Fecha': fecha, 'Estado': estado}
            for codigo, lista in estados.items() for fecha, estado in zip(fechas, lista)
        ]
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(reverse('import-attendance'), {'file': self.excel(filas)},
                                   HTTP_AUTHORIZATION=self.auth(self.admin))
        self.assertEqual(res.status_code, 200, res.content)

        alertas = {a.estudiante_id: a for a in Alerta.objects.filter(regla=self.regla)}
        self.assertEqual(set(alertas), {'1152002', '1152004'})
        self.assertEqual(alertas['1152002'].valor_causa, Decimal('50.00'))
        self.assertEqual(alertas['1152004'].valor_causa, Decimal('33.33'))
        self.assertTrue(NotificacionHistorial.objects.filter(alerta=alertas['1152004'], canal='EMAIL').exists())

        # Justificar una de las dos faltas de 1152004: 16,67 %, la alerta se cierra sola
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(
                reverse('course-attendance', args=[self.curso.id]),
                json.dumps({'fecha': '2026-09-01', 'registros': [
                    {'codigo_estudiante': '1152004', 'estado': 'FALTA_JUSTIFICADA'}]}),
                content_type='application/json', HTTP_AUTHORIZATION=self.auth(self.user_docente),
            )
        self.assertEqual(res.status_code, 200, res.content)
        alertas['1152004'].refresh_from_db()
        self.assertEqual(alertas['1152004'].estado, 'cerrada')
        self.assertTrue(alertas['1152004'].metadata['cierre_automatico'])
        alertas['1152002'].refresh_from_db()
        self.assertEqual(alertas['1152002'].estado, 'activa')
