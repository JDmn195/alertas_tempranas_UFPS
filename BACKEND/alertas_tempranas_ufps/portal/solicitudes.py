"""
HU-41: Solicitudes de acompañamiento del estudiante en el portal.

Serializador propio con lista blanca de campos: del responsable solo se muestra el
nombre y nunca se exponen su correo, su rol ni datos de auditoría.
"""
from .intervenciones import resumen_alerta


def serializar_solicitud(solicitud):
    return {
        'id': solicitud.id,
        'motivo': solicitud.motivo,
        'motivo_texto': solicitud.get_motivo_display(),
        'descripcion': solicitud.descripcion,
        'alerta': resumen_alerta(solicitud.alerta) if solicitud.alerta_id else None,
        'estado': solicitud.estado,
        'estado_texto': solicitud.get_estado_display(),
        'respuesta': solicitud.respuesta or None,
        'responsable': solicitud.responsable.nombre if solicitud.responsable_id else None,
        'fecha_solicitud': solicitud.fecha_solicitud.isoformat(),
        'fecha_atencion': solicitud.fecha_atencion.isoformat() if solicitud.fecha_atencion else None,
        'fecha_actualizacion': solicitud.fecha_actualizacion.isoformat(),
        'puede_cancelar': solicitud.estado == 'PENDIENTE',
    }
