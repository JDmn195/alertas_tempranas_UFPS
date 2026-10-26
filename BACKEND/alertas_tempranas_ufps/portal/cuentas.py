"""
HU-37: Cuentas con rol ESTUDIANTE para el portal de autoconsulta.

Las cuentas se crean sin contraseña utilizable: el estudiante la define con el
enlace de recuperación (o un administrador con `establecer_contrasena`). Nunca
se usa el código ni el documento del estudiante como contraseña.
"""
from django.db import transaction

from usuarios.models import Usuario

DOMINIO_INSTITUCIONAL = '@ufps.edu.co'

# Resultados de crear_cuenta_estudiante
CREADA = 'creada'
YA_ASOCIADA = 'ya_asociada'
SIN_CORREO = 'sin_correo'
CORREO_EN_USO = 'correo_en_uso'


class ErrorCuentaEstudiante(Exception):
    """La cuenta no se puede crear o asociar; el mensaje se muestra tal cual al administrador."""


def correo_institucional(estudiante):
    """Correo institucional normalizado del estudiante, o None si no tiene uno válido."""
    correo = (estudiante.email_institucional or '').strip().lower()
    if not correo.endswith(DOMINIO_INSTITUCIONAL) or len(correo) <= len(DOMINIO_INSTITUCIONAL):
        return None
    return correo


def crear_cuenta_estudiante(estudiante):
    """
    Crea la cuenta ESTUDIANTE del estudiante y la asocia. No modifica cuentas existentes.
    Retorna (resultado, usuario): usuario es la cuenta creada, la ya asociada o la que
    ya usa el correo (CORREO_EN_USO); None si el estudiante no tiene correo institucional.
    """
    if estudiante.usuario_id:
        return YA_ASOCIADA, estudiante.usuario

    correo = correo_institucional(estudiante)
    if correo is None:
        return SIN_CORREO, None

    existente = Usuario.objects.filter(correo__iexact=correo).first()
    if existente is not None:
        return CORREO_EN_USO, existente

    with transaction.atomic():
        usuario = Usuario(nombre=estudiante.nombre, correo=correo, rol='ESTUDIANTE', activo=True)
        usuario.set_unusable_password()
        usuario.save()
        estudiante.usuario = usuario
        estudiante.save(update_fields=['usuario'])
    return CREADA, usuario


@transaction.atomic
def asociar_cuenta_estudiante(estudiante, correo=None):
    """
    Crea o reasocia la cuenta de un estudiante (acción del administrador).

    - Sin cuenta con ese correo: la crea con rol ESTUDIANTE y sin contraseña utilizable.
    - Con una cuenta ESTUDIANTE libre (o ya de este estudiante): la asocia.
    - Si la cuenta es del personal o ya pertenece a otro estudiante, no se toca.

    `correo` por defecto es el institucional del estudiante. Si el estudiante tenía
    otra cuenta asociada, queda desvinculada (y sin acceso al portal).
    Retorna (accion, usuario, cuenta_anterior) con accion 'creada' o 'asociada'.
    """
    correo = (correo or '').strip().lower() or correo_institucional(estudiante)
    if not correo:
        raise ErrorCuentaEstudiante(
            'El estudiante no tiene correo institucional. Indique el correo de la cuenta.'
        )
    if not correo.endswith(DOMINIO_INSTITUCIONAL):
        raise ErrorCuentaEstudiante(f'El correo debe ser institucional ({DOMINIO_INSTITUCIONAL}).')

    anterior = estudiante.usuario
    usuario = Usuario.objects.select_for_update().filter(correo__iexact=correo).first()

    if usuario is None:
        usuario = Usuario(nombre=estudiante.nombre, correo=correo, rol='ESTUDIANTE', activo=True)
        usuario.set_unusable_password()
        usuario.save()
        accion = 'creada'
    else:
        if usuario.rol != 'ESTUDIANTE':
            raise ErrorCuentaEstudiante(
                f'El correo {correo} pertenece a una cuenta del personal ({usuario.rol}); no se puede asociar.'
            )
        otro = getattr(usuario, 'estudiante', None)
        if otro is not None and otro.pk != estudiante.pk:
            raise ErrorCuentaEstudiante(
                f'La cuenta {correo} ya está asociada al estudiante {otro.codigo}.'
            )
        accion = 'asociada'

    if anterior is not None and anterior.pk == usuario.pk:
        return accion, usuario, None

    estudiante.usuario = usuario
    estudiante.save(update_fields=['usuario'])
    return accion, usuario, anterior
