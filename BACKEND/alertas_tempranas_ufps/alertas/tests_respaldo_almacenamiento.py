"""Respaldo y restauración de prueba del almacenamiento de evidencias, con Supabase simulado."""
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from alertas.views.evidence_views import BUCKET


class _Almacen:
    def __init__(self, archivos, corromper=False):
        self.archivos, self.corromper = archivos, corromper

    def list(self, path='', options=None):
        prefijo = f'{path}/' if path else ''
        nombres = {}
        for ruta in self.archivos:
            if ruta.startswith(prefijo):
                nombre, _, resto = ruta[len(prefijo):].partition('/')
                nombres[nombre] = None if resto else 'id-archivo'
        return [{'name': nombre, 'id': ident} for nombre, ident in sorted(nombres.items())]

    def download(self, ruta):
        return self.archivos[ruta]

    def upload(self, path, file, file_options=None):
        self.archivos[path] = b'otro contenido' if self.corromper else file


class _Bucket:
    public = False


class _Storage:
    def __init__(self, corromper=False):
        self.buckets = {BUCKET: _Almacen({
            'intervencion_1/acta.pdf': b'%PDF acta',
            'intervencion_1/foto.png': b'PNG foto',
            'intervencion_2/remision.pdf': b'%PDF remision',
        })}
        self.corromper = corromper

    def from_(self, bucket):
        return self.buckets[bucket]

    def get_bucket(self, bucket):
        if bucket not in self.buckets:
            raise Exception('Bucket not found')
        return _Bucket()

    def create_bucket(self, bucket, options=None):
        assert options == {'public': False}
        self.buckets[bucket] = _Almacen({}, self.corromper)


class _Cliente:
    def __init__(self, corromper=False):
        self.storage = _Storage(corromper)


class RespaldarAlmacenamientoTests(SimpleTestCase):

    def _ejecutar(self, cliente, *args):
        self.destino = Path(self.enterContext(tempfile.TemporaryDirectory()))
        with patch('alertas.management.commands.respaldar_almacenamiento.get_supabase', return_value=cliente):
            call_command('respaldar_almacenamiento', '--destino', str(self.destino), *args, verbosity=0)
        return json.loads((self.destino / 'manifiesto.json').read_text(encoding='utf-8'))

    def test_descarga_todas_las_carpetas_y_escribe_el_manifiesto(self):
        manifiesto = self._ejecutar(_Cliente())

        self.assertEqual(manifiesto['total_archivos'], 3)
        self.assertEqual((self.destino / 'intervencion_2' / 'remision.pdf').read_bytes(), b'%PDF remision')
        acta = next(a for a in manifiesto['archivos'] if a['ruta'] == 'intervencion_1/acta.pdf')
        self.assertEqual(acta, {'ruta': 'intervencion_1/acta.pdf', 'bytes': 9,
                                'sha256': hashlib.sha256(b'%PDF acta').hexdigest()})
        self.assertNotIn('restauracion', manifiesto)

    def test_restaura_en_un_bucket_de_prueba_privado_y_verifica(self):
        cliente = _Cliente()
        manifiesto = self._ejecutar(cliente, '--restaurar-en', 'prueba')

        self.assertEqual(manifiesto['restauracion'], {'bucket': 'prueba', 'verificados': 3, 'diferencias': []})
        self.assertEqual(cliente.storage.buckets['prueba'].archivos, cliente.storage.buckets[BUCKET].archivos)

    def test_falla_si_la_copia_restaurada_no_coincide(self):
        with self.assertRaisesMessage(CommandError, 'La restauración no coincide'):
            self._ejecutar(_Cliente(corromper=True), '--restaurar-en', 'prueba')

    def test_no_restaura_sobre_el_bucket_de_produccion(self):
        with self.assertRaisesMessage(CommandError, 'bucket de producción'):
            self._ejecutar(_Cliente(), '--restaurar-en', BUCKET)

    def test_sin_configuracion_de_supabase_no_hace_nada(self):
        with self.assertRaisesMessage(CommandError, 'No se pudo crear el cliente'):
            self._ejecutar(None)
