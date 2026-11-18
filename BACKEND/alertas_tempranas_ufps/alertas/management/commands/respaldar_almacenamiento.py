"""
Respaldo de las evidencias guardadas en Supabase Storage y prueba de restauración.

    python manage.py respaldar_almacenamiento --destino D:/respaldos/evidencias_2026-11-18
    python manage.py respaldar_almacenamiento --destino D:/respaldos/evidencias_2026-11-18 \
        --restaurar-en evidencias-prueba-restauracion

Descarga todos los archivos del bucket a `--destino` y escribe `manifiesto.json`
con la ruta, el tamaño y el SHA-256 de cada uno. Con `--restaurar-en` sube la copia
a OTRO bucket privado (lo crea si no existe), la vuelve a descargar y compara los
SHA-256: así queda probada la recuperación sin tocar el bucket de producción.

El plan gratuito de Supabase no incluye respaldos; este comando es el procedimiento.
Las evidencias tienen datos personales: `--destino` debe quedar fuera del repositorio
y la copia se borra o se guarda cifrada. Las credenciales salen de las variables de
entorno de siempre (SUPABASE_URL y SUPABASE_KEY); no se escriben en ningún archivo.
"""
import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from alertas.views.evidence_views import BUCKET, get_supabase

PAGINA = 100


def _sha256(contenido):
    return hashlib.sha256(contenido).hexdigest()


def listar_archivos(almacen, carpeta=''):
    """Rutas de todos los archivos del bucket. Una entrada sin `id` es una carpeta."""
    rutas, desde = [], 0
    while True:
        pagina = almacen.list(path=carpeta, options={'limit': PAGINA, 'offset': desde})
        for entrada in pagina:
            ruta = f"{carpeta}/{entrada['name']}" if carpeta else entrada['name']
            if entrada.get('id') is None:
                rutas.extend(listar_archivos(almacen, ruta))
            else:
                rutas.append(ruta)
        if len(pagina) < PAGINA:
            return rutas
        desde += PAGINA


class Command(BaseCommand):
    help = 'Respalda el bucket de evidencias en una carpeta local y, si se pide, prueba la restauración.'

    def add_arguments(self, parser):
        parser.add_argument('--destino', required=True, help='Carpeta local del respaldo (fuera del repositorio).')
        parser.add_argument('--restaurar-en', help='Bucket de prueba donde se restaura y se verifica la copia.')

    def handle(self, *args, **options):
        cliente = get_supabase()
        if cliente is None:
            raise CommandError('No se pudo crear el cliente de Supabase. Ejecute verificar_almacenamiento.')
        prueba = options['restaurar_en']
        if prueba == BUCKET:
            raise CommandError('La restauración de prueba no puede hacerse sobre el bucket de producción.')

        destino = Path(options['destino'])
        destino.mkdir(parents=True, exist_ok=True)
        almacen = cliente.storage.from_(BUCKET)

        archivos = []
        for ruta in listar_archivos(almacen):
            contenido = almacen.download(ruta)
            local = destino / ruta
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(contenido)
            archivos.append({'ruta': ruta, 'bytes': len(contenido), 'sha256': _sha256(contenido)})

        manifiesto = {
            'bucket': BUCKET,
            'fecha': timezone.localtime().isoformat(timespec='seconds'),
            'total_archivos': len(archivos),
            'total_bytes': sum(a['bytes'] for a in archivos),
            'archivos': archivos,
        }
        self.stdout.write(f"Respaldo: {len(archivos)} archivos, {manifiesto['total_bytes']} bytes en {destino}")

        if prueba:
            manifiesto['restauracion'] = self._restaurar(cliente, prueba, destino, archivos)

        (destino / 'manifiesto.json').write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2),
                                                 encoding='utf-8')
        if prueba and manifiesto['restauracion']['diferencias']:
            raise CommandError(f"La restauración no coincide en: {manifiesto['restauracion']['diferencias']}")
        self.stdout.write(self.style.SUCCESS('Manifiesto escrito en manifiesto.json'))

    def _restaurar(self, cliente, bucket, destino, archivos):
        try:
            if cliente.storage.get_bucket(bucket).public:
                raise CommandError(f"El bucket de prueba '{bucket}' es público. Debe ser privado.")
        except CommandError:
            raise
        except Exception:
            cliente.storage.create_bucket(bucket, options={'public': False})

        almacen = cliente.storage.from_(bucket)
        diferencias = []
        for archivo in archivos:
            almacen.upload(path=archivo['ruta'], file=(destino / archivo['ruta']).read_bytes(),
                           file_options={'upsert': 'true'})
            if _sha256(almacen.download(archivo['ruta'])) != archivo['sha256']:
                diferencias.append(archivo['ruta'])

        self.stdout.write(
            f"Restauración en '{bucket}': {len(archivos) - len(diferencias)} de {len(archivos)} archivos coinciden"
        )
        return {'bucket': bucket, 'verificados': len(archivos) - len(diferencias), 'diferencias': diferencias}
