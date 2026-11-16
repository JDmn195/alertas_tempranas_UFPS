"""
SDAT-347: pruebas con dobles de Brevo y Supabase. Nada sale a la red ni usa claves reales:
`requests.post` y `supabase.create_client` se reemplazan siempre por simulaciones.
"""
import os
from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase

from alertas.models import Evidencia
from alertas.services import NotificationService
from alertas.tests_evidencias import BaseAlertas, ENV_OK
from alertas.views import evidence_views

ENV_BREVO = {'BREVO_API_KEY': 'clave-falsa-de-prueba', 'BREVO_SENDER_EMAIL': 'remitente@ejemplo.test'}


def _respuesta(codigo, texto=''):
    r = MagicMock()
    r.status_code = codigo
    r.text = texto
    return r


class EnvioBrevoSimuladoTests(SimpleTestCase):

    def _enviar(self, **kw):
        with patch.dict(os.environ, ENV_BREVO), patch('alertas.services.requests.post', **kw) as post:
            resultado = NotificationService.enviar_brevo('estudiante@ufps.edu.co', 'Asunto', '<p>Hola</p>')
        return resultado, post

    def test_arma_la_peticion_a_la_api_de_brevo(self):
        resultado, post = self._enviar(return_value=_respuesta(201))
        self.assertEqual(resultado, ('exitoso', None))
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], 'https://api.brevo.com/v3/smtp/email')
        self.assertEqual(kwargs['headers']['api-key'], 'clave-falsa-de-prueba')
        self.assertEqual(kwargs['json']['to'], [{'email': 'estudiante@ufps.edu.co'}])
        self.assertEqual(kwargs['json']['sender']['email'], 'remitente@ejemplo.test')
        self.assertEqual(kwargs['json']['subject'], 'Asunto')
        self.assertEqual(kwargs['json']['htmlContent'], '<p>Hola</p>')
        self.assertIn('timeout', kwargs)

    def test_202_tambien_es_exitoso(self):
        self.assertEqual(self._enviar(return_value=_respuesta(202))[0], ('exitoso', None))

    def test_rechazo_de_brevo_es_fallido_con_detalle(self):
        (resultado, detalle), _ = self._enviar(return_value=_respuesta(401, 'Key not found'))
        self.assertEqual(resultado, 'fallido')
        self.assertIn('401', detalle)
        self.assertIn('Key not found', detalle)

    def test_error_de_red_queda_para_reintento(self):
        (resultado, detalle), _ = self._enviar(side_effect=requests.ConnectionError('sin red'))
        self.assertEqual(resultado, 'reintento')
        self.assertIn('sin red', detalle)

    def test_sin_clave_no_llama_a_brevo(self):
        entorno = {k: v for k, v in os.environ.items() if k != 'BREVO_API_KEY'}
        with patch.dict(os.environ, entorno, clear=True), patch('alertas.services.requests.post') as post:
            resultado = NotificationService.enviar_brevo('a@ufps.edu.co', 'x', 'y')
        self.assertEqual(resultado[0], 'fallido')
        post.assert_not_called()


class EvidenciasSupabaseSimuladoTests(BaseAlertas):

    def _cliente(self):
        cliente = MagicMock()
        cliente.storage.get_bucket.return_value.public = False
        almacen = cliente.storage.from_.return_value
        almacen.get_public_url.side_effect = lambda ruta: (
            f'https://abcdefgh.supabase.co/storage/v1/object/public/evidencias/{ruta}')
        almacen.create_signed_url.side_effect = lambda ruta, seg: {
            'signedURL': f'https://abcdefgh.supabase.co/storage/v1/object/sign/evidencias/{ruta}?token=falso'}
        return cliente, almacen

    @patch.dict(os.environ, ENV_OK)
    def test_la_subida_usa_ruta_tipo_y_url_firmada_de_corta_vigencia(self):
        cliente, almacen = self._cliente()
        with patch('supabase.create_client', return_value=cliente):
            resp = self._subir(self.interv_propia, self.director)
        self.assertEqual(resp.status_code, 201)

        kwargs = almacen.upload.call_args.kwargs
        self.assertRegex(kwargs['path'], rf'^intervencion_{self.interv_propia.id}/[0-9a-f-]{{36}}\.pdf$')
        self.assertEqual(kwargs['file_options'], {'content-type': 'application/pdf'})
        self.assertTrue(kwargs['file'].startswith(b'%PDF'))

        ruta, vigencia = almacen.create_signed_url.call_args.args
        self.assertEqual(ruta, kwargs['path'])
        self.assertEqual(vigencia, evidence_views.VIGENCIA_URL_SEGUNDOS)

        evidencia = Evidencia.objects.get()
        self.assertIn('/object/public/', evidencia.archivo_url)  # referencia estable, no la firmada
        self.assertIn('/object/sign/', resp.json()['evidencia']['url'])
        self.assertNotIn('/object/public/', resp.json()['evidencia']['url'])

    @patch.dict(os.environ, ENV_OK)
    def test_fallo_al_firmar_no_deja_evidencia_registrada(self):
        cliente, almacen = self._cliente()
        almacen.create_signed_url.side_effect = Exception('Supabase caído')
        with patch('supabase.create_client', return_value=cliente):
            resp = self._subir(self.interv_propia, self.director)
        self.assertEqual(resp.status_code, 500)
        self.assertFalse(Evidencia.objects.exists())

    @patch.dict(os.environ, ENV_OK)
    def test_ruta_de_otro_servidor_no_se_firma(self):
        self.assertIsNone(evidence_views._ruta_almacenamiento(
            'https://otro-host.example/storage/v1/object/public/evidencias/a.pdf'))
        self.assertIsNone(evidence_views._ruta_almacenamiento(
            'https://abcdefgh.supabase.co/storage/v1/object/public/evidencias/../secreto.pdf'))
        self.assertEqual(
            evidence_views._ruta_almacenamiento(
                'https://abcdefgh.supabase.co/storage/v1/object/public/evidencias/intervencion_1/a.pdf'),
            'intervencion_1/a.pdf')
        cliente, almacen = self._cliente()
        with self.assertRaises(ValueError):
            evidence_views._url_firmada(cliente, 'https://otro-host.example/storage/v1/object/public/evidencias/a.pdf')
        almacen.create_signed_url.assert_not_called()
