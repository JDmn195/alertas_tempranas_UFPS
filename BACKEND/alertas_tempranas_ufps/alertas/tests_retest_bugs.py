"""SDAT-312: re-test de hallazgos QA (B24, B30)."""
import json

from django.urls import reverse

from alertas.models import Alerta, NotificacionHistorial
from alertas.tests_alertas_inasistencia import AlertaInasistenciaBaseTestCase, SEIS_DOS_FALTAS


class HistorialNotificacionesTests(AlertaInasistenciaBaseTestCase):
    """B24: el historial no muestra la respuesta cruda de Brevo."""

    def _fallido(self, detalle):
        self.registrar(self.est, SEIS_DOS_FALTAS)
        self.evaluar()
        alerta = self.alertas().get()
        NotificacionHistorial.objects.all().delete()
        NotificacionHistorial.objects.create(
            alerta=alerta, destinatario='x@ufps.edu.co', rol_destinatario='DOCENTE', canal='EMAIL',
            resultado='fallido', detalle_error=detalle,
        )
        res = self.get(reverse('historial-notificaciones'), resultado='fallido')
        self.assertEqual(res.status_code, 200, res.content)
        return res.json()['historial'][0]['detalle_error']

    def test_error_401_de_brevo_se_muestra_legible(self):
        crudo = 'Error API Brevo: 401 - {"message":"Key not found","code":"unauthorized"}'
        texto = self._fallido(crudo)
        self.assertNotIn('Brevo: 401', texto)
        self.assertNotIn('Key not found', texto)
        self.assertIn('credenciales', texto)

    def test_otro_error_de_brevo_no_expone_la_respuesta(self):
        texto = self._fallido('Error API Brevo: 400 - {"message":"sender not valid"}')
        self.assertNotIn('sender not valid', texto)

    def test_el_detalle_tecnico_sigue_guardado_en_la_base(self):
        crudo = 'Error API Brevo: 401 - {"message":"Key not found"}'
        self._fallido(crudo)
        self.assertEqual(NotificacionHistorial.objects.get().detalle_error, crudo)


class AlertaInasistenciaSeActualizaTests(AlertaInasistenciaBaseTestCase):
    """B30: el porcentaje de la alerta abierta sigue al de Asistencia al registrar otra clase."""

    def test_nueva_clase_actualiza_porcentaje_de_la_alerta_abierta(self):
        self.registrar(self.est, SEIS_DOS_FALTAS)  # 2 de 6 = 33,33 %
        self.evaluar()
        self.assertEqual(str(self.alertas().get().valor_causa), '33.33')
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(
                reverse('course-attendance', args=[self.curso.id]),
                json.dumps({'fecha': '2026-10-20', 'registros': [
                    {'codigo_estudiante': self.est.codigo, 'estado': 'ASISTIO'}]}),
                content_type='application/json', HTTP_AUTHORIZATION=self.auth(self.user_docente),
            )
        self.assertEqual(res.status_code, 200, res.content)
        alerta = Alerta.objects.get(pk=self.alertas().get().pk)
        self.assertEqual(str(alerta.valor_causa), '28.57')  # 2 de 7
        self.assertEqual(float(alerta.metadata['porcentaje']), 28.57)
        self.assertEqual(alerta.metadata['total_clases'], 7)
