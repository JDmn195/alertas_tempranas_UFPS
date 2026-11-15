"""SDAT-300: configuración y caché de producción sobre una base de pruebas."""
import io
import os
import runpy
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.cache.backends.db import DatabaseCache
from django.core.checks import run_checks
from django.core.management import call_command
from django.http import HttpResponse
from django.middleware.security import SecurityMiddleware
from django.test import RequestFactory, SimpleTestCase, TransactionTestCase, override_settings


class SeguridadProduccionTests(SimpleTestCase):
    def configuracion(self, modo='produccion'):
        # Entorno simulado dentro del proceso de prueba; no cambia el del equipo.
        entorno = {
            'SECRET_KEY': 'clave-simulada-exclusiva-de-pruebas-de-configuracion-sin-uso-real',
            'ALLOWED_HOSTS': 'sat.example.org',
            'DEBUG': 'True' if modo == 'desarrollo' else 'False',
        }
        if modo == 'e2e':
            entorno['E2E'] = 'True'
        argumentos = ['manage.py', 'test' if modo == 'pruebas' else 'check']
        ruta = Path(settings.BASE_DIR) / 'alertas_tempranas_ufps' / 'settings.py'
        with patch.object(os, 'environ', entorno), patch('sys.argv', argumentos), patch('dotenv.load_dotenv'):
            return runpy.run_path(str(ruta))

    def test_produccion_supera_los_cuatro_controles_de_despliegue(self):
        configuracion = self.configuracion()
        claves = ['DEBUG', 'SECURE_SSL_REDIRECT', 'SECURE_PROXY_SSL_HEADER',
                  'SECURE_HSTS_SECONDS', 'SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE']
        with override_settings(**{clave: configuracion[clave] for clave in claves}):
            errores = run_checks(tags=['security'], include_deployment_checks=True)
        self.assertFalse({'security.W004', 'security.W008', 'security.W012', 'security.W016'}
                         & {error.id for error in errores})
        self.assertEqual(configuracion['CACHES']['default']['BACKEND'],
                         'django.core.cache.backends.db.DatabaseCache')
        self.assertNotEqual(configuracion['ADMIN_URL'], 'admin/')

    def test_https_del_proxy_no_provoca_un_bucle_y_http_se_redirige(self):
        configuracion = self.configuracion()
        claves = ['SECURE_SSL_REDIRECT', 'SECURE_PROXY_SSL_HEADER', 'SECURE_HSTS_SECONDS', 'ALLOWED_HOSTS']
        with override_settings(**{clave: configuracion[clave] for clave in claves}):
            middleware = SecurityMiddleware(lambda solicitud: HttpResponse('Correcto'))
            fabrica = RequestFactory()
            respuesta_https = middleware(fabrica.get('/', HTTP_HOST='sat.example.org',
                                                     HTTP_X_FORWARDED_PROTO='https'))
            respuesta_http = middleware(fabrica.get('/', HTTP_HOST='sat.example.org'))
        self.assertEqual(respuesta_https.status_code, 200)
        self.assertIn('max-age=31536000', respuesta_https['Strict-Transport-Security'])
        self.assertEqual(respuesta_http.status_code, 301)
        self.assertEqual(respuesta_http['Location'], 'https://sat.example.org/')

    def test_desarrollo_pruebas_y_e2e_conservan_http_y_admin(self):
        for modo in ['desarrollo', 'pruebas', 'e2e']:
            with self.subTest(modo=modo):
                configuracion = self.configuracion(modo)
                self.assertFalse(configuracion['SECURE_SSL_REDIRECT'])
                self.assertEqual(configuracion['ADMIN_URL'], 'admin/')


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
    'LOCATION': 'sat_cache_prueba_300',
}})
class CacheCompartidaTests(TransactionTestCase):
    def test_dos_instancias_comparten_el_mismo_contador(self):
        call_command('createcachetable', verbosity=0, stdout=io.StringIO())
        primera = DatabaseCache('sat_cache_prueba_300', {})
        segunda = DatabaseCache('sat_cache_prueba_300', {})
        primera.set('contador-prueba', 1)
        self.assertEqual(segunda.get('contador-prueba'), 1)
        segunda.incr('contador-prueba')
        self.assertEqual(primera.get('contador-prueba'), 2)
