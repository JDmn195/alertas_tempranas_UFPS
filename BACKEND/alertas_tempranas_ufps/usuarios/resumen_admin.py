"""SDAT-349 (6.7): resumen de inicio del administrador."""
from django.db.models import Count
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from academico.models import BitacoraImportacion
from alertas.models import EjecucionReevaluacion
from .decorators import requiere_rol
from .models import Usuario
from .utils import fecha_local


@csrf_exempt
@require_http_methods(["GET"])
@requiere_rol(['ADMINISTRADOR'])
def resumen_admin(request):
    """
    GET /api/usuarios/resumen/
    Conteo de usuarios por rol, últimas importaciones y últimas ejecuciones de procesos.
    """
    por_rol = {rol: 0 for rol in ('ADMINISTRADOR', 'DIRECTOR', 'DOCENTE', 'BIENESTAR', 'ESTUDIANTE')}
    for fila in Usuario.objects.filter(activo=True).values('rol').annotate(total=Count('id')):
        por_rol[fila['rol']] = fila['total']

    importaciones = [
        {
            'id': b.id,
            'tipo': b.tipo,
            'archivo': b.archivo_nombre,
            'fecha': fecha_local(b.fecha),
            'exitoso': b.exitoso,
            'procesados': b.total_procesados,
            'errores': b.total_errores,
        }
        for b in BitacoraImportacion.objects.order_by('-fecha')[:5]
    ]
    procesos = [
        {
            'id': e.id,
            'origen': e.get_origen_display(),
            'estado': e.get_estado_display(),
            'fecha': fecha_local(e.fecha_inicio),
            'alertas_generadas': e.alertas_generadas,
            'errores': e.total_errores,
        }
        for e in EjecucionReevaluacion.objects.order_by('-fecha_inicio')[:5]
    ]
    return JsonResponse({
        'usuarios': {
            'activos': sum(por_rol.values()),
            'inactivos': Usuario.objects.filter(activo=False).count(),
            'por_rol': por_rol,
        },
        'importaciones_recientes': importaciones,
        'procesos_recientes': procesos,
    })
