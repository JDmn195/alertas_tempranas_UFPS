"""
INC-03 (subida de evidencias sin conexión al almacenamiento) y alcance del
docente sobre las alertas de sus estudiantes.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import httpx
import jwt
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from academico.models import Curso, Docente, Estudiante, Materia, Nota, Periodo
from alertas.models import Alerta, AnotacionIntervencion, Evidencia, Intervencion, Regla
from alertas.views import evidence_views
from usuarios.models import Usuario


def _auth(usuario):
    payload = {
        'user_id': usuario.id,
        'exp': datetime.now(timezone.utc) + timedelta(days=1),
        'iat': datetime.now(timezone.utc),
    }
    return {'HTTP_AUTHORIZATION': f"Bearer {jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')}"}


class BaseAlertas(TestCase):
    def setUp(self):
        evidence_views._supabase_client = None
        self.addCleanup(setattr, evidence_views, '_supabase_client', None)

        self.director = Usuario.objects.create(nombre='Directora', correo='dir@ufps.edu.co', rol='DIRECTOR')
        self.usuario_docente = Usuario.objects.create(nombre='Docente', correo='doc@ufps.edu.co', rol='DOCENTE')
        docente = Docente.objects.create(codigo='01713', nombre='Docente', tipo_vinculacion='Planta',
                                         usuario=self.usuario_docente)
        regla = Regla.objects.create(nombre='Promedio Crítico', tipo='PROMEDIO', operador='<',
                                     valor_umbral=Decimal('2.5'), nivel='high')

        self.propio = self._estudiante('E1')
        self.ajeno = self._estudiante('E2')
        curso = Curso.objects.create(materia=Materia.objects.create(codigo='M1', nombre='Cálculo'),
                                     docente=docente, grupo='A', cantidad_matriculados=1)
        Nota.objects.create(estudiante=self.propio, curso=curso, periodo=Periodo.objects.create(anio=2026, semestre=1),
                            definitiva=2.0)

        self.alerta_propia = Alerta.objects.create(estudiante=self.propio, regla=regla, estado='activa')
        self.alerta_ajena = Alerta.objects.create(estudiante=self.ajeno, regla=regla, estado='activa')
        self.interv_propia = Intervencion.objects.create(alerta=self.alerta_propia, usuario=self.director, tipo='TUTORIA')
        self.interv_ajena = Intervencion.objects.create(alerta=self.alerta_ajena, usuario=self.director, tipo='TUTORIA')

    def _estudiante(self, codigo):
        return Estudiante.objects.create(codigo=codigo, nombre=f'Estudiante {codigo}', tipo_documento='CC',
                                         numero_documento=f'doc-{codigo}', semestre=1, estado_matricula='ACTIVO')

    def _subir(self, intervencion, usuario, nombre='acta.pdf'):
        archivo = SimpleUploadedFile(nombre, b'%PDF-1.4 contenido', content_type='application/pdf')
        url = reverse('subir-evidencia', kwargs={'intervencion_id': intervencion.id})
        return self.client.post(url, {'file': archivo}, **_auth(usuario))


ENV_OK = {'SUPABASE_URL': 'https://abcdefgh.supabase.co', 'SUPABASE_KEY': 'clave-real'}


class SubidaEvidenciasTests(BaseAlertas):

    @patch.dict(os.environ, {'SUPABASE_URL': 'https://tu-proyecto.supabase.co', 'SUPABASE_KEY': 'tu-service-role-key-aqui'})
    def test_configuracion_de_ejemplo_da_mensaje_claro(self):
        resp = self._subir(self.interv_propia, self.director)
        self.assertEqual(resp.status_code, 503)
        self.assertIn('no está configurado', resp.json()['error'])

    @patch.dict(os.environ, ENV_OK)
    def test_fallo_dns_responde_503_sin_detalle_tecnico(self):
        cliente = MagicMock()
        cliente.storage.get_bucket.return_value.public = False
        cliente.storage.from_.return_value.upload.side_effect = httpx.ConnectError(
            '[Errno -2] Name or service not known')
        with patch('supabase.create_client', return_value=cliente):
            resp = self._subir(self.interv_propia, self.director)
        self.assertEqual(resp.status_code, 503)
        self.assertIn('No se pudo conectar con el servicio de almacenamiento', resp.json()['error'])
        self.assertNotIn('Errno', resp.json()['error'])
        self.assertFalse(Evidencia.objects.exists())

    @patch.dict(os.environ, ENV_OK)
    def test_formato_no_permitido(self):
        resp = self._subir(self.interv_propia, self.director, nombre='virus.exe')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Formato no permitido', resp.json()['error'])

    @patch.dict(os.environ, ENV_OK)
    def test_subida_exitosa(self):
        cliente = MagicMock()
        cliente.storage.get_bucket.return_value.public = False
        cliente.storage.from_.return_value.get_public_url.return_value = (
            'https://abcdefgh.supabase.co/storage/v1/object/public/evidencias/intervencion_1/acta.pdf'
        )
        cliente.storage.from_.return_value.create_signed_url.return_value = {
            'signedURL': 'https://abcdefgh.supabase.co/storage/v1/object/sign/evidencias/intervencion_1/acta.pdf'
        }
        with patch('supabase.create_client', return_value=cliente):
            resp = self._subir(self.interv_propia, self.director)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Evidencia.objects.get().intervencion, self.interv_propia)
        self.assertIn('/object/sign/', resp.json()['evidencia']['url'])
        cliente.storage.from_.return_value.create_signed_url.assert_called_once()

    @patch.dict(os.environ, ENV_OK)
    def test_bucket_publico_rechaza_nuevas_evidencias(self):
        cliente = MagicMock()
        cliente.storage.get_bucket.return_value.public = True
        with patch('supabase.create_client', return_value=cliente):
            resp = self._subir(self.interv_propia, self.director)
        self.assertEqual(resp.status_code, 503)
        cliente.storage.from_.return_value.upload.assert_not_called()
        self.assertFalse(Evidencia.objects.exists())

    @patch.dict(os.environ, ENV_OK)
    def test_pdf_falso_no_se_sube(self):
        archivo = SimpleUploadedFile('acta.pdf', b'<script>contenido</script>', content_type='application/pdf')
        url = reverse('subir-evidencia', kwargs={'intervencion_id': self.interv_propia.id})
        resp = self.client.post(url, {'file': archivo}, **_auth(self.director))
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Evidencia.objects.exists())

    @patch.dict(os.environ, ENV_OK)
    def test_listado_firma_url_guardada(self):
        Evidencia.objects.create(
            intervencion=self.interv_propia,
            archivo_url='https://abcdefgh.supabase.co/storage/v1/object/public/evidencias/intervencion_1/acta.pdf',
            nombre_archivo='acta.pdf',
        )
        cliente = MagicMock()
        cliente.storage.from_.return_value.create_signed_url.return_value = {
            'signedURL': 'https://abcdefgh.supabase.co/storage/v1/object/sign/evidencias/intervencion_1/acta.pdf'
        }
        with patch('supabase.create_client', return_value=cliente):
            resp = self.client.get(reverse('listar-evidencias', kwargs={'intervencion_id': self.interv_propia.id}),
                                   **_auth(self.director))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('/object/sign/', resp.json()['evidencias'][0]['url'])


class AlcanceDocenteTests(BaseAlertas):

    def test_docente_ve_intervenciones_de_su_estudiante(self):
        url = reverse('listar-intervenciones', kwargs={'alerta_id': self.alerta_propia.id})
        self.assertEqual(self.client.get(url, **_auth(self.usuario_docente)).status_code, 200)

    def test_docente_no_accede_a_alertas_de_otros_estudiantes(self):
        doc = _auth(self.usuario_docente)
        casos = [
            ('get', reverse('listar-intervenciones', kwargs={'alerta_id': self.alerta_ajena.id})),
            ('post', reverse('registrar-intervencion', kwargs={'alerta_id': self.alerta_ajena.id})),
            ('post', reverse('cerrar-alerta', kwargs={'alerta_id': self.alerta_ajena.id})),
            ('get', reverse('gestionar-anotaciones', kwargs={'intervencion_id': self.interv_ajena.id})),
            ('post', reverse('concluir-intervencion', kwargs={'intervencion_id': self.interv_ajena.id})),
            ('get', reverse('listar-evidencias', kwargs={'intervencion_id': self.interv_ajena.id})),
        ]
        for metodo, url in casos:
            with self.subTest(url=url):
                resp = getattr(self.client, metodo)(url, data='{}', content_type='application/json', **doc) \
                    if metodo == 'post' else self.client.get(url, **doc)
                self.assertEqual(resp.status_code, 403)
        self.alerta_ajena.refresh_from_db()
        self.assertEqual(self.alerta_ajena.estado, 'activa')

    def test_director_accede_a_todas(self):
        url = reverse('listar-intervenciones', kwargs={'alerta_id': self.alerta_ajena.id})
        self.assertEqual(self.client.get(url, **_auth(self.director)).status_code, 200)


class FechasBogotaTests(BaseAlertas):
    """SDAT-335: el instante se guarda en UTC y se presenta en America/Bogota."""

    def setUp(self):
        super().setUp()
        self.utc = datetime(2026, 11, 16, 7, 47, tzinfo=timezone.utc)
        Intervencion.objects.filter(id=self.interv_propia.id).update(fecha=self.utc)
        self.anot = AnotacionIntervencion.objects.create(intervencion=self.interv_propia, usuario=self.director,
                                                         texto='n')
        AnotacionIntervencion.objects.filter(id=self.anot.id).update(fecha=self.utc)

    def test_historial_muestra_hora_local(self):
        url = reverse('listar-intervenciones', kwargs={'alerta_id': self.alerta_propia.id})
        fecha = self.client.get(url, **_auth(self.director)).json()['intervenciones'][0]['fecha']
        self.assertEqual(fecha, '2026-11-16 02:47')

    def test_anotaciones_muestran_hora_local(self):
        url = reverse('gestionar-anotaciones', kwargs={'intervencion_id': self.interv_propia.id})
        fecha = self.client.get(url, **_auth(self.director)).json()['anotaciones'][0]['fecha']
        self.assertEqual(fecha, '2026-11-16 02:47')

    def test_instante_almacenado_se_conserva(self):
        self.interv_propia.refresh_from_db()
        self.assertEqual(self.interv_propia.fecha, self.utc)

    def test_ficha_del_estudiante_muestra_hora_local(self):
        url = reverse('student-interventions', kwargs={'codigo': self.propio.codigo})
        fecha = self.client.get(url, **_auth(self.director)).json()['intervenciones'][0]['fecha']
        self.assertEqual(fecha, '2026-11-16 02:47')


class AnotacionesYResultadoTests(BaseAlertas):
    """SDAT-332: anotaciones con tipos inválidos y longitud del resumen final."""

    def _post(self, nombre_url, kwargs, cuerpo):
        # SDAT-349: el director solo consulta; quien escribe es un administrador
        admin, _ = Usuario.objects.get_or_create(correo='admin349@ufps.edu.co', defaults={'nombre': 'Admin', 'rol': 'ADMINISTRADOR'})
        return self.client.post(reverse(nombre_url, kwargs=kwargs), data=json.dumps(cuerpo),
                                content_type='application/json', **_auth(admin))

    def test_anotacion_valida_se_guarda(self):
        resp = self._post('gestionar-anotaciones', {'intervencion_id': self.interv_propia.id},
                          {'texto': 'Se llamó al estudiante'})
        self.assertEqual(resp.status_code, 201)

    def test_anotacion_con_tipo_invalido_devuelve_400(self):
        for valor in (5, None, ['x'], {'a': 1}):
            with self.subTest(valor=valor):
                resp = self._post('gestionar-anotaciones', {'intervencion_id': self.interv_propia.id},
                                  {'texto': valor})
                self.assertEqual(resp.status_code, 400)

    def test_concluir_con_tipo_invalido_devuelve_400(self):
        resp = self._post('concluir-intervencion', {'intervencion_id': self.interv_propia.id}, {'resultado': 7})
        self.assertEqual(resp.status_code, 400)

    def test_concluir_acepta_100_y_rechaza_101_caracteres(self):
        url = {'intervencion_id': self.interv_propia.id}
        resp = self._post('concluir-intervencion', url, {'resultado': 'x' * 101})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('100', resp.json()['error'])
        self.interv_propia.refresh_from_db()
        self.assertFalse(self.interv_propia.concluida)
        resp = self._post('concluir-intervencion', url, {'resultado': 'x' * 100})
        self.assertEqual(resp.status_code, 200)

    def test_registrar_intervencion_resultado_largo_devuelve_400(self):
        resp = self._post('registrar-intervencion', {'alerta_id': self.alerta_propia.id},
                          {'tipo': 'TUTORIA', 'observaciones': 'obs', 'resultado': 'x' * 101})
        self.assertEqual(resp.status_code, 400)
