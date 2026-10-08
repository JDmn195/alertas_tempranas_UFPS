"""
Utilidades de los comandos que preparan las bases de pruebas (preparar_e2e,
preparar_rendimiento). Solo funcionan con E2E=True, que nunca carga el .env.
"""
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

CONTRASENA = 'Clave-Segura-2026'
HOSTS_LOCALES = {'localhost', '127.0.0.1', '::1', ''}


def recrear_base():
    """Borra la base de pruebas y aplica las migraciones (que crean las reglas CORTE e INASISTENCIA)."""
    if not getattr(settings, 'EJECUTANDO_E2E', False):
        raise CommandError('Este comando borra la base: solo corre con la variable E2E=True.')

    db = settings.DATABASES['default']
    if db['ENGINE'].endswith('sqlite3'):
        ruta = Path(db['NAME'])
        connection.close()
        for sufijo in ('', '-journal', '-wal', '-shm'):
            archivo = ruta.with_name(ruta.name + sufijo)
            if archivo.exists():
                archivo.unlink()
    elif db['ENGINE'].endswith('postgresql'):
        # Segunda barrera: solo un Postgres local y desechable
        if db.get('HOST', '') not in HOSTS_LOCALES:
            raise CommandError(f"Solo se recrea un Postgres local, no '{db.get('HOST')}'.")
        with connection.cursor() as cursor:
            cursor.execute('DROP SCHEMA public CASCADE; CREATE SCHEMA public;')
    else:
        raise CommandError(f"Motor de base no soportado: {db['ENGINE']}")

    call_command('migrate', interactive=False, verbosity=0)


def crear_usuario(nombre, correo, rol):
    from usuarios.models import Usuario

    usuario = Usuario(nombre=nombre, correo=correo, rol=rol)
    usuario.set_password(CONTRASENA)
    usuario.save()
    return usuario
