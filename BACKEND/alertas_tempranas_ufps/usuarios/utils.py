import logging

from django.utils import timezone

from .models import Auditoria

logger = logging.getLogger(__name__)


def fecha_local(fecha, formato='%Y-%m-%d %H:%M'):
    """Presenta un datetime almacenado en UTC en la zona del proyecto (America/Bogota)."""
    return timezone.localtime(fecha).strftime(formato) if fecha else None


def registrar_auditoria(usuario, tipo_accion, detalle=""):
    """
    Registra una acción en la bitácora de auditoría.
    """
    try:
        Auditoria.objects.create(
            usuario=usuario,
            tipo_accion=tipo_accion,
            detalle=detalle
        )
    except Exception as e:
        logger.error("Error al registrar auditoría (tipo=%s, usuario=%s): %s",
                     tipo_accion, getattr(usuario, 'id', None), e, exc_info=True)
