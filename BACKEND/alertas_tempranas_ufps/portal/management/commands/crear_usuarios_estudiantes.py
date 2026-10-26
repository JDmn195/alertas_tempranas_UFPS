from django.core.management.base import BaseCommand
from django.db import transaction

from academico.models import Estudiante
from portal.cuentas import CORREO_EN_USO, CREADA, SIN_CORREO, crear_cuenta_estudiante
from usuarios.utils import registrar_auditoria


class Command(BaseCommand):
    help = (
        'HU-37: Crea la cuenta con rol ESTUDIANTE de cada estudiante con correo institucional '
        'y sin cuenta, y la asocia. Las cuentas quedan sin contraseña: el estudiante la define '
        'con "¿Olvidaste tu contraseña?". No modifica cuentas existentes.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--codigos', nargs='+', help='Limita la creación a estos códigos de estudiante.')
        parser.add_argument('--dry-run', action='store_true', help='Muestra lo que haría sin guardar nada.')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        qs = Estudiante.objects.filter(usuario__isnull=True).order_by('codigo')
        if options['codigos']:
            qs = qs.filter(codigo__in=options['codigos'])
            no_encontrados = set(options['codigos']) - set(
                Estudiante.objects.filter(codigo__in=options['codigos']).values_list('codigo', flat=True)
            )
            for codigo in sorted(no_encontrados):
                self.stdout.write(self.style.WARNING(f'  {codigo}: no existe el estudiante.'))

        if dry_run:
            self.stdout.write(self.style.WARNING('Modo --dry-run: no se guardará ningún cambio.'))

        creadas, sin_correo, en_uso = [], [], []
        with transaction.atomic():
            for estudiante in qs:
                resultado, usuario = crear_cuenta_estudiante(estudiante)
                if resultado == CREADA:
                    creadas.append(estudiante.codigo)
                    self.stdout.write(f'  {estudiante.codigo}: cuenta creada ({usuario.correo}).')
                elif resultado == SIN_CORREO:
                    sin_correo.append(estudiante.codigo)
                elif resultado == CORREO_EN_USO:
                    en_uso.append(estudiante.codigo)
                    self.stdout.write(self.style.WARNING(
                        f'  {estudiante.codigo}: el correo {usuario.correo} ya pertenece a otra cuenta '
                        f'({usuario.rol}); no se modificó.'
                    ))

            if creadas and not dry_run:
                registrar_auditoria(
                    None, 'CREAR_CUENTA_ESTUDIANTE',
                    f"Comando crear_usuarios_estudiantes: {len(creadas)} cuentas creadas y asociadas "
                    f"({_resumir(creadas)}). Correos ya en uso: {len(en_uso)}. Sin correo institucional: {len(sin_correo)}.",
                )
            if dry_run:
                transaction.set_rollback(True)

        prefijo = 'Se crearían' if dry_run else 'Se crearon'
        self.stdout.write(self.style.SUCCESS(f'{prefijo} {len(creadas)} cuentas de estudiante.'))
        if en_uso:
            self.stdout.write(self.style.WARNING(
                f'{len(en_uso)} estudiantes con el correo ya usado por otra cuenta: {_resumir(en_uso)}.'
            ))
        if sin_correo:
            self.stdout.write(self.style.WARNING(
                f'{len(sin_correo)} estudiantes sin correo institucional: {_resumir(sin_correo)}.'
            ))


def _resumir(codigos, maximo=20):
    texto = ', '.join(codigos[:maximo])
    return texto + (f' y {len(codigos) - maximo} más' if len(codigos) > maximo else '')
