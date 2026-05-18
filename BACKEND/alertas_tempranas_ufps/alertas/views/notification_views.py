from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from ..models import NotificacionHistorial, NotificacionInterna

@require_http_methods(["GET"])
def listar_historial_notificaciones(request):
    """
    GET /api/alertas/notificaciones/historial/
    Filtros: alerta_id, resultado, canal, fecha_inicio, fecha_fin
    """
    qs = NotificacionHistorial.objects.select_related('alerta__estudiante').all()
    
    alerta_id = request.GET.get('alerta_id')
    resultado = request.GET.get('resultado')
    canal = request.GET.get('canal')
    
    if alerta_id:
        qs = qs.filter(alerta_id=alerta_id)
    if resultado:
        qs = qs.filter(resultado=resultado)
    if canal:
        qs = qs.filter(canal=canal)
        
    data = []
    for n in qs:
        data.append({
            'id': n.id,
            'alerta_id': n.alerta_id,
            'estudiante': n.alerta.estudiante.nombre,
            'destinatario': n.destinatario,
            'rol_destinatario': n.rol_destinatario,
            'canal': n.canal,
            'fecha_envio': n.fecha_envio.isoformat(),
            'resultado': n.resultado,
            'detalle_error': n.detalle_error
        })
        
    return JsonResponse({'historial': data})

@require_http_methods(["GET"])
def listar_notificaciones_internas(request):
    """
    GET /api/alertas/notificaciones/internas/?usuario_id=123
    """
    usuario_id = request.GET.get('usuario_id')
    if not usuario_id:
        return JsonResponse({'error': 'Falta usuario_id'}, status=400)
        
    qs = NotificacionInterna.objects.filter(usuario_id=usuario_id).select_related('alerta__regla')
    
    data = []
    for n in qs:
        data.append({
            'id': n.id,
            'mensaje': n.mensaje,
            'leida': n.leida,
            'fecha': n.fecha_creacion.isoformat(),
            'alerta': {
                'id': n.alerta.id,
                'nivel': n.alerta.regla.nivel,
                'tipo': n.alerta.regla.nombre
            }
        })
        
    return JsonResponse({'notificaciones': data})

@csrf_exempt
@require_http_methods(["POST"])
def marcar_notificacion_leida(request, notificacion_id):
    """
    POST /api/alertas/notificaciones/internas/<id>/leer/
    """
    notificacion = get_object_or_404(NotificacionInterna, id=notificacion_id)
    notificacion.leida = True
    notificacion.save()
    return JsonResponse({'mensaje': 'Notificación marcada como leída'})
