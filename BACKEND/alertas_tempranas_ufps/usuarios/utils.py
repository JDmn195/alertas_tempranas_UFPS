import logging
from .models import Auditoria

logger = logging.getLogger(__name__)

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
