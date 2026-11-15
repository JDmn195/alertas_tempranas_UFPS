"""SDAT-326: intentos aislados por correo y origen, sin bloquear otras IP."""
import json

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from usuarios.models import Usuario


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
                   RENDER_EXTERNAL_HOSTNAME=None)
class BloqueoPorIpTests(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario = Usuario.objects.create(
            nombre='Docente', correo='docente.ip@ufps.edu.co', rol='DOCENTE',
        )
        self.usuario.set_password('Clave-de-prueba-2026')
        self.usuario.save()
        self.url = reverse('login')

    def login(self, ip='198.51.100.1', correcta=False, correo=None, **cabeceras):
        return self.client.post(
            self.url, data=json.dumps({
                'email': correo or self.usuario.correo,
                'password': 'Clave-de-prueba-2026' if correcta else 'incorrecta',
            }), content_type='application/json', REMOTE_ADDR=ip, **cabeceras,
        )

    def fallar_cinco_veces(self, **opciones):
        for _ in range(5):
            self.assertEqual(self.login(**opciones).status_code, 401)

    def test_el_mismo_par_se_bloquea_sin_bloquear_a_la_victima_desde_otra_ip(self):
        self.fallar_cinco_veces()
        self.assertEqual(self.login(correcta=True).status_code, 429)
        self.assertEqual(self.login(ip='203.0.113.7', correcta=True).status_code, 200)
        self.assertEqual(self.login(correcta=True).status_code, 429)

    def test_el_bloqueo_no_se_aplica_a_otro_correo_desde_la_misma_ip(self):
        self.fallar_cinco_veces(correo='inexistente@ufps.edu.co')
        self.assertEqual(self.login(correcta=True).status_code, 200)

    def test_un_login_correcto_limpia_solo_su_contador(self):
        for _ in range(4):
            self.login()
        self.assertEqual(self.login(correcta=True).status_code, 200)
        self.fallar_cinco_veces()
        self.assertEqual(self.login().status_code, 429)

    def test_cabeceras_reenviadas_no_permiten_evitar_el_limite_fuera_de_render(self):
        self.fallar_cinco_veces(HTTP_X_FORWARDED_FOR='203.0.113.1', HTTP_CF_CONNECTING_IP='203.0.113.1')
        self.assertEqual(self.login(HTTP_X_FORWARDED_FOR='203.0.113.2',
                                    HTTP_CF_CONNECTING_IP='203.0.113.2').status_code, 429)

    @override_settings(RENDER_EXTERNAL_HOSTNAME='sat-prueba.onrender.com')
    def test_en_render_se_usa_la_ip_de_cloudflare_y_no_el_x_forwarded_for(self):
        self.fallar_cinco_veces(HTTP_CF_CONNECTING_IP='198.51.100.5')
        self.assertEqual(self.login(HTTP_CF_CONNECTING_IP='198.51.100.5',
                                    HTTP_X_FORWARDED_FOR='203.0.113.88').status_code, 429)
        self.assertEqual(self.login(correcta=True, HTTP_CF_CONNECTING_IP='203.0.113.7').status_code, 200)

    def test_ipv6_equivalentes_comparten_el_contador(self):
        self.fallar_cinco_veces(ip='2001:0db8:0000:0000:0000:0000:0000:0001')
        self.assertEqual(self.login(ip='2001:db8::1').status_code, 429)
