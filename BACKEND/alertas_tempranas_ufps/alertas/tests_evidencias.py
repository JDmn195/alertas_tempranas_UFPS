"""
INC-03 (subida de evidencias sin conexión al almacenamiento) y alcance del
docente sobre las alertas de sus estudiantes.
"""
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
from alertas.models import Alerta, Evidencia, Intervencion, Regla
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
        cliente.storage.from_.return_value.get_public_url.return_value = 'https://abcdefgh.supabase.co/x/acta.pdf'
        with patch('supabase.create_client', return_value=cliente):
            resp = self._subir(self.interv_propia, self.director)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Evidencia.objects.get().intervencion, self.interv_propia)


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
