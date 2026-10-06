from decimal import Decimal

from django.test import TestCase

from academico.models import Estudiante
from alertas.models import Alerta, Regla
from alertas.services import NotificationService

INYECCION = '<a href="https://phishing.example">Haz clic</a>'


class EscapadoCorreoTests(TestCase):
    """Los nombres vienen de archivos importados: no deben poder inyectar HTML en los correos."""

    def test_html_de_alerta_escapa_datos_importados(self):
        est = Estudiante.objects.create(codigo='E1', nombre=INYECCION, tipo_documento='CC',
                                        numero_documento='1', semestre=1)
        regla = Regla.objects.create(nombre='<script>x</script>', tipo='PROMEDIO', operador='<',
                                     valor_umbral=Decimal('3'), nivel='high', prioridad=1)
        alerta = Alerta.objects.create(estudiante=est, regla=regla, estado='activa')

        html = NotificationService.generar_html_basico(alerta, INYECCION)

        self.assertNotIn('<a href', html)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;a href=', html)
