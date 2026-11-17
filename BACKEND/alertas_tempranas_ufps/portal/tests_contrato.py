"""
Prueba de contrato: las respuestas reales de la sesión y del portal del estudiante
cumplen docs/openapi.yaml (código HTTP documentado y esquema de la respuesta).
"""
from datetime import date, timedelta
from pathlib import Path

import yaml
from django.conf import settings
from django.urls import reverse

from academico.models import Asistencia, Periodo
from alertas.models import Alerta
from pruebas_integracion.base import CONTRASENA, IntegracionTestCase
from usuarios.models import Usuario

RUTA_CONTRATO = Path(settings.BASE_DIR).parent.parent / 'docs' / 'openapi.yaml'
TIPOS = {
    'string': str, 'integer': int, 'number': (int, float), 'boolean': bool, 'object': dict, 'array': list,
}


class ContratoTests(IntegracionTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.contrato = yaml.safe_load(RUTA_CONTRATO.read_text(encoding='utf-8'))

    def setUp(self):
        super().setUp()
        self.api('post', 'cuenta_estudiante', self.admin, datos={}, args=[self.estudiante.codigo])
        self.cuenta = Usuario.objects.get(correo=self.estudiante.email_institucional)
        self.cuenta.set_password(CONTRASENA)
        self.cuenta.save()
        self.importar_historial(self.historial_en_riesgo())
        periodo = Periodo.objects.order_by('-anio', '-semestre').first()
        for dia, estado in enumerate(['ASISTIO', 'FALTA', 'ASISTIO', 'FALTA_JUSTIFICADA']):
            Asistencia.objects.create(
                estudiante=self.estudiante, curso=self.curso_calculo, periodo=periodo,
                fecha_clase=date(2026, 2, 2) + timedelta(days=dia), estado=estado,
            )
        self.alerta = Alerta.objects.filter(estudiante=self.estudiante).first()
        resp = self.api('post', 'registrar-intervencion', self.bienestar, args=[self.alerta.id], datos={
            'tipo': 'TUTORIA', 'observaciones': 'Se acuerda un plan de estudio con el estudiante.',
        })
        self.assertEqual(resp.status_code, 201, resp.content)

    # ------------------------------------------------------------------
    # Validación mínima de esquemas OpenAPI 3.0 (los rasgos que usa el contrato)
    # ------------------------------------------------------------------

    def _resolver(self, esquema):
        while '$ref' in esquema:
            nodo = self.contrato
            for parte in esquema['$ref'].lstrip('#/').split('/'):
                nodo = nodo[parte]
            esquema = nodo
        return esquema

    def _validar(self, valor, esquema, ruta):
        esquema = self._resolver(esquema)
        if valor is None:
            self.assertTrue(esquema.get('nullable'), f'{ruta}: llegó null y el contrato no lo permite')
            return
        for parte in esquema.get('allOf', []):
            self._validar(valor, parte, ruta)
        tipo = esquema.get('type')
        if tipo:
            self.assertIsInstance(valor, TIPOS[tipo], f'{ruta}: se esperaba {tipo}')
            if tipo in ('integer', 'number'):
                self.assertNotIsInstance(valor, bool, f'{ruta}: se esperaba {tipo}')
        if 'enum' in esquema:
            self.assertIn(valor, esquema['enum'], ruta)
        if isinstance(valor, dict):
            for campo in esquema.get('required', []):
                self.assertIn(campo, valor, f'{ruta}: falta el campo obligatorio «{campo}»')
            for campo, sub in esquema.get('properties', {}).items():
                if campo in valor:
                    self._validar(valor[campo], sub, f'{ruta}.{campo}')
        if isinstance(valor, list) and 'items' in esquema:
            for i, elemento in enumerate(valor):
                self._validar(elemento, esquema['items'], f'{ruta}[{i}]')

    def _cumple(self, resp, ruta, metodo):
        """El código está documentado para esa operación y el cuerpo cumple su esquema."""
        respuestas = self.contrato['paths'][ruta][metodo]['responses']
        self.assertIn(str(resp.status_code), respuestas, f'{metodo.upper()} {ruta}: código no documentado')
        respuesta = self._resolver(respuestas[str(resp.status_code)])
        self._validar(resp.json(), respuesta['content']['application/json']['schema'], f'{metodo.upper()} {ruta}')
        return resp.json()

    def _portal(self, metodo, nombre, ruta, **kwargs):
        return self._cumple(self.api(metodo, nombre, self.cuenta, **kwargs), ruta, metodo)

    # ------------------------------------------------------------------

    def test_todas_las_rutas_del_portal_estan_en_el_contrato(self):
        from portal.urls import urlpatterns
        documentadas = {ruta.replace('{', '<int:').replace('}', '>') for ruta in self.contrato['paths']}
        for patron in urlpatterns:
            self.assertIn(f'/api/portal/{patron.pattern}', documentadas)

    def test_sesion(self):
        self._cumple(self.login(self.cuenta), '/api/usuarios/login/', 'post')
        self._cumple(self.login(self.cuenta, 'incorrecta'), '/api/usuarios/login/', 'post')
        self._cumple(self.api('get', 'sesion_actual', self.cuenta), '/api/usuarios/me/', 'get')
        self._cumple(self.client.get(reverse('sesion_actual')), '/api/usuarios/me/', 'get')
        self._cumple(self.api('post', 'solicitar_recuperacion', datos={'email': 'nadie@ufps.edu.co'}),
                     '/api/usuarios/recuperar-password/', 'post')
        self._cumple(self.api('post', 'cambiar_contrasena', datos={'token': 'x', 'password': CONTRASENA}),
                     '/api/usuarios/cambiar-password/', 'post')
        self._cumple(self.api('post', 'cerrar_sesion', self.cuenta), '/api/usuarios/logout/', 'post')

    def test_consultas_del_portal(self):
        self._portal('get', 'portal-riesgo', '/api/portal/riesgo/')
        self._portal('get', 'portal-evolucion', '/api/portal/evolucion/')
        self._portal('get', 'portal-alertas', '/api/portal/alertas/')
        self._portal('get', 'portal-alertas', '/api/portal/alertas/', query={'estado': 'no-existe'})
        self._portal('get', 'portal-alerta-detalle', '/api/portal/alertas/{alerta_id}/', args=[self.alerta.id])
        self._portal('get', 'portal-alerta-detalle', '/api/portal/alertas/{alerta_id}/', args=[999999])
        lista = self._portal('get', 'portal-intervenciones', '/api/portal/intervenciones/')
        self.assertEqual(lista['conteos']['total'], 1)
        self._portal('get', 'portal-intervencion-detalle', '/api/portal/intervenciones/{intervencion_id}/',
                     args=[lista['intervenciones'][0]['id']])
        self._portal('get', 'portal-intervencion-detalle', '/api/portal/intervenciones/{intervencion_id}/',
                     args=[999999])
        asistencia = self._portal('get', 'portal-asistencia', '/api/portal/asistencia/')
        self.assertTrue(asistencia['hay_registros'])
        self._portal('get', 'portal-asistencia', '/api/portal/asistencia/', query={'periodo': 'no-existe'})

    def test_solicitudes_del_portal(self):
        ruta = '/api/portal/solicitudes/'
        datos = {'motivo': 'ACADEMICO', 'descripcion': 'Necesito apoyo para preparar el examen de Cálculo I.',
                 'alerta': self.alerta.id}
        self._portal('post', 'portal-solicitudes', ruta, datos={'motivo': 'x'})          # 400
        self._portal('post', 'portal-solicitudes', ruta, datos={**datos, 'alerta': 999999})  # 404
        creada = self._portal('post', 'portal-solicitudes', ruta, datos=datos)           # 201
        self._portal('post', 'portal-solicitudes', ruta, datos=datos)                    # 409: no se duplica
        lista = self._portal('get', 'portal-solicitudes', ruta)
        self.assertEqual(len(lista['solicitudes']), 1)
        cancelar = '/api/portal/solicitudes/{solicitud_id}/cancelar/'
        self._portal('patch', 'portal-solicitud-cancelar', cancelar, args=[creada['id']], datos={})
        self._portal('patch', 'portal-solicitud-cancelar', cancelar, args=[creada['id']], datos={})  # ya cancelada
        self._portal('patch', 'portal-solicitud-cancelar', cancelar, args=[999999], datos={})

    def test_otro_rol_recibe_el_error_documentado(self):
        self._cumple(self.api('get', 'portal-riesgo', self.usuario_docente), '/api/portal/riesgo/', 'get')
        self._cumple(self.client.get(reverse('portal-riesgo')), '/api/portal/riesgo/', 'get')
