"""
HU-41: Solicitudes de acompañamiento académico.

Reglas compartidas por el portal del estudiante y la bandeja del personal:
validación del motivo y la descripción, transiciones de estado y notificaciones.

Flujo: PENDIENTE -> EN_ATENCION -> ATENDIDA. El estudiante puede cancelar mientras
esté PENDIENTE y el personal puede cancelarla mientras siga en curso. ATENDIDA y
CANCELADA son finales. Al crearse se avisa a los usuarios BIENESTAR activos y,
cuando el personal cambia el estado o responde, se avisa al estudiante. Los envíos
se programan con transaction.on_commit para no notificar algo que no se guardó.
"""
import logging
import unicodedata

from django.db import transaction
from django.utils import timezone
from django.utils.html import escape

from usuarios.models import Usuario

from .models import SolicitudAcompanamiento
from .services import NotificationService

logger = logging.getLogger(__name__)

MOTIVOS = dict(SolicitudAcompanamiento.MOTIVO_CHOICES)
ESTADOS = dict(SolicitudAcompanamiento.ESTADO_CHOICES)
ESTADOS_FINALES = ('ATENDIDA', 'CANCELADA')

DESCRIPCION_MIN = 20
DESCRIPCION_MAX = 2000

# Roles del personal que gestionan la bandeja de solicitudes
ROLES_GESTION = ['BIENESTAR', 'DIRECTOR', 'ADMINISTRADOR']

# Estado actual -> estados a los que el personal puede llevar la solicitud
TRANSICIONES = {
    'PENDIENTE': ('EN_ATENCION', 'ATENDIDA', 'CANCELADA'),
    'EN_ATENCION': ('ATENDIDA', 'CANCELADA'),
    'ATENDIDA': (),
    'CANCELADA': (),
}


def normalizar_motivo(valor):
    """'Académico', 'academico' o 'ACADEMICO' -> 'ACADEMICO'; None si no es un motivo válido."""
    texto = unicodedata.normalize('NFKD', str(valor or '').strip())
    clave = ''.join(c for c in texto if not unicodedata.combining(c)).upper()
    return clave if clave in MOTIVOS else None


def validar_solicitud(datos):
    """Valida motivo y descripción. Retorna (limpios, errores)."""
    errores = {}
    motivo_bruto = datos.get('motivo')
    descripcion = str(datos.get('descripcion') or '').strip()

    motivo = None
    if not str(motivo_bruto or '').strip():
        errores['motivo'] = 'El motivo es obligatorio.'
    else:
        motivo = normalizar_motivo(motivo_bruto)
        if motivo is None:
            errores['motivo'] = f"Motivo no válido. Use uno de: {', '.join(MOTIVOS)}."

    if not descripcion:
        errores['descripcion'] = 'La descripción es obligatoria.'
    elif len(descripcion) < DESCRIPCION_MIN:
        errores['descripcion'] = (
            f'Cuéntanos un poco más: la descripción debe tener al menos {DESCRIPCION_MIN} caracteres.'
        )
    elif len(descripcion) > DESCRIPCION_MAX:
        errores['descripcion'] = f'La descripción no puede superar los {DESCRIPCION_MAX} caracteres.'

    return {'motivo': motivo, 'descripcion': descripcion}, errores


def solicitud_en_curso(estudiante):
    return (
        SolicitudAcompanamiento.objects
        .filter(estudiante=estudiante, estado__in=SolicitudAcompanamiento.ESTADOS_EN_CURSO)
        .order_by('-fecha_solicitud')
        .first()
    )


# ---------------------------------------------------------------------------
# Notificaciones
# ---------------------------------------------------------------------------

def _html(titulo, destinatario, filas, mensaje):
    """Correo con el mismo estilo que el de las alertas. Todo dato variable se escapa."""
    filas_html = ''.join(
        f'<p style="margin: 5px 0;"><strong>{escape(etiqueta)}:</strong> {escape(str(valor))}</p>'
        for etiqueta, valor in filas
    )
    return f"""
    <html>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-top: 5px solid #aa1916;">
            <div style="padding: 20px; text-align: center; background-color: #f8f9fa;">
                <h2 style="color: #aa1916; margin: 0;">{escape(titulo)}</h2>
            </div>
            <div style="padding: 30px;">
                <p>Hola, <strong>{escape(destinatario)}</strong>.</p>
                <div style="background-color: #fff8f8; padding: 15px; border-left: 4px solid #aa1916; margin: 20px 0;">
                    {filas_html}
                </div>
                <p>{escape(mensaje)}</p>
            </div>
            <div style="padding: 20px; text-align: center; font-size: 12px; color: #6c757d; background-color: #f8f9fa;">
                &copy; 2026 Universidad Francisco de Paula Santander - Alertas Tempranas
            </div>
        </div>
    </body>
    </html>
    """


def _fecha_texto(fecha):
    return timezone.localtime(fecha).strftime('%d/%m/%Y %H:%M') if fecha else ''


def notificar_nueva_solicitud(solicitud):
    """Correo y notificación interna a cada usuario BIENESTAR activo."""
    estudiante = solicitud.estudiante
    motivo = solicitud.get_motivo_display()
    fecha = _fecha_texto(solicitud.fecha_solicitud)
    mensaje = (f"Nueva solicitud de acompañamiento ({motivo}) de {estudiante.nombre} ({estudiante.codigo}), "
               f"registrada el {fecha}.")
    filas = [('Estudiante', f'{estudiante.nombre} ({estudiante.codigo})'), ('Motivo', motivo), ('Fecha', fecha)]

    for usuario in Usuario.objects.filter(rol='BIENESTAR', activo=True):
        html = _html('Nueva solicitud de acompañamiento', usuario.nombre, filas,
                     'Ingresa al sistema para revisar la solicitud y asignar un responsable.')
        NotificationService.enviar_correo(usuario.correo, f'Solicitud de acompañamiento - {estudiante.nombre}',
                                          html, solicitud.alerta, 'BIENESTAR', tipo='SOLICITUD', solicitud=solicitud)
        NotificationService.enviar_interna(usuario, solicitud.alerta, mensaje, tipo='SOLICITUD', solicitud=solicitud)


def notificar_actualizacion_solicitud(solicitud):
    """Correo al estudiante y notificación interna a su cuenta, con el estado y la respuesta."""
    estudiante = solicitud.estudiante
    estado = solicitud.get_estado_display()
    mensaje = f"Tu solicitud de acompañamiento ({solicitud.get_motivo_display()}) está: {estado}."
    if solicitud.respuesta:
        mensaje += f" Respuesta: {solicitud.respuesta}"

    correo = estudiante.email_institucional or estudiante.email_personal
    if correo:
        filas = [('Motivo', solicitud.get_motivo_display()), ('Estado', estado)]
        if solicitud.responsable:
            filas.append(('Responsable', solicitud.responsable.nombre))
        if solicitud.respuesta:
            filas.append(('Respuesta', solicitud.respuesta))
        html = _html('Actualización de tu solicitud de acompañamiento', estudiante.nombre, filas,
                     'Puedes consultar el detalle en el portal del estudiante.')
        NotificationService.enviar_correo(correo, 'Actualización de tu solicitud de acompañamiento', html,
                                          solicitud.alerta, 'ESTUDIANTE', tipo='SOLICITUD', solicitud=solicitud)

    cuenta = getattr(estudiante, 'usuario', None)
    if cuenta is not None and cuenta.activo:
        NotificationService.enviar_interna(cuenta, solicitud.alerta, mensaje, tipo='SOLICITUD', solicitud=solicitud)


def programar_notificacion(funcion, solicitud_id):
    """Envía la notificación cuando la transacción confirme; un fallo de envío no afecta la respuesta."""
    def _enviar():
        try:
            solicitud = (SolicitudAcompanamiento.objects
                         .select_related('estudiante__usuario', 'responsable', 'alerta')
                         .get(pk=solicitud_id))
            funcion(solicitud)
        except Exception:
            logger.exception("Error al notificar la solicitud de acompañamiento %s", solicitud_id)
    transaction.on_commit(_enviar)
