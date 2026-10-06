from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from usuarios.models import Usuario


class Command(BaseCommand):
    help = (
        "Define la contraseña de un usuario desde la consola. Útil si una cuenta "
        "quedó sin contraseña utilizable y el correo de recuperación no está disponible."
    )

    def add_arguments(self, parser):
        parser.add_argument('correo')

    def handle(self, *args, **options):
        try:
            usuario = Usuario.objects.get(correo=options['correo'])
        except Usuario.DoesNotExist:
            raise CommandError(f"No existe un usuario con el correo {options['correo']}.")

        contrasena = getpass('Nueva contraseña: ')
        if contrasena != getpass('Repite la contraseña: '):
            raise CommandError('Las contraseñas no coinciden.')
        try:
            validate_password(contrasena, user=usuario)
        except ValidationError as e:
            raise CommandError(' '.join(e.messages))

        usuario.set_password(contrasena)
        usuario.debe_cambiar_contrasena = False
        usuario.save(update_fields=['contrasena', 'debe_cambiar_contrasena'])
        self.stdout.write(self.style.SUCCESS(f'Contraseña actualizada para {usuario.correo}.'))
