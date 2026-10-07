"""
INC-03: diagnostica la conexión con Supabase Storage (evidencias).

    python manage.py verificar_almacenamiento

Revisa en orden: variables de entorno, resolución DNS del host, y acceso al
bucket con la clave configurada. Así se distingue un problema de ambiente
("[Errno -2] Name or service not known" = el host no resuelve) de uno de código.
"""
import socket
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError

from alertas.views.evidence_views import BUCKET, configuracion_supabase, get_supabase


class Command(BaseCommand):
    help = 'Verifica la configuración y la conexión con el almacenamiento de evidencias (Supabase).'

    def handle(self, *args, **options):
        url, _, problema = configuracion_supabase()
        if problema:
            raise CommandError(problema)
        host = urlparse(url).hostname
        self.stdout.write(f'1. Configuración: SUPABASE_URL={url}, bucket={BUCKET}')

        try:
            ip = socket.gethostbyname(host)
        except socket.gaierror as e:
            raise CommandError(
                f"2. El host '{host}' no resuelve por DNS ({e}). Revisa que SUPABASE_URL sea la URL "
                f"real del proyecto (Supabase > Project Settings > API) y que el servidor tenga salida a internet."
            )
        self.stdout.write(f'2. DNS: {host} -> {ip}')

        cliente = get_supabase()
        if cliente is None:
            raise CommandError('3. No se pudo crear el cliente de Supabase (revisa el log).')
        try:
            cliente.storage.from_(BUCKET).list(path='', options={'limit': 1})
        except Exception as e:
            raise CommandError(
                f"3. Hay conexión, pero no se pudo acceder al bucket '{BUCKET}': {e}. Revisa que el bucket "
                f"exista (SUPABASE_BUCKET_NAME) y que SUPABASE_KEY sea la service role key."
            )
        self.stdout.write(self.style.SUCCESS(f"3. Bucket '{BUCKET}' accesible. El almacenamiento está listo."))
