from .models import Auditoria

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
        # Aquí se podría usar un logger para no fallar el request si falla la auditoría
        print(f"Error al registrar auditoría: {e}")
