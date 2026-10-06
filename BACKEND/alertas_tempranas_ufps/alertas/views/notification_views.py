from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from ..models import NotificacionHistorial, NotificacionInterna
from usuarios.decorators import requiere_rol

@require_http_methods(["GET"])
@requiere_rol(['ADMINISTRADOR'])
def listar_historial_notificaciones(request):
    """
    GET /api/alertas/notificaciones/historial/
    Filtros: alerta_id, resultado, canal, tipo (ALERTA | RECORDATORIO), fecha_inicio, fecha_fin
    """
    qs = NotificacionHistorial.objects.select_related('alerta__estudiante').all()
    
    alerta_id = request.GET.get('alerta_id')
    resultado = request.GET.get('resultado')
    canal = request.GET.get('canal')
    tipo = request.GET.get('tipo')
    
    if alerta_id:
        qs = qs.filter(alerta_id=alerta_id)
    if resultado:
        qs = qs.filter(resultado=resultado)
    if canal:
        qs = qs.filter(canal=canal)
    if tipo:
        qs = qs.filter(tipo=tipo.upper())

    # Rango de fechas (YYYY-MM-DD), ambos extremos inclusive
    for param, lookup in (('fecha_inicio', 'fecha_envio__date__gte'), ('fecha_fin', 'fecha_envio__date__lte')):
        valor = request.GET.get(param)
        if not valor:
            continue
        try:
            fecha = parse_date(valor)
        except ValueError:
            fecha = None
        if fecha is None:
            return JsonResponse({'error': f'{param} inválida; usa el formato YYYY-MM-DD.'}, status=400)
        qs = qs.filter(**{lookup: fecha})

    data = []
    for n in qs:
        data.append({
            'id': n.id,
            'alerta_id': n.alerta_id,
            'estudiante': n.alerta.estudiante.nombre,
            'destinatario': n.destinatario,
            'rol_destinatario': n.rol_destinatario,
            'canal': n.canal,
            'tipo': n.tipo,
            'fecha_envio': n.fecha_envio.isoformat(),
            'resultado': n.resultado,
            'detalle_error': n.detalle_error
        })
        
    return JsonResponse({'historial': data})

@require_http_methods(["GET"])
@requiere_rol(['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR', 'DIRECTOR'])
def listar_notificaciones_internas(request):
    """
    GET /api/alertas/notificaciones/internas/
    Notificaciones del usuario autenticado.
    """
    qs = NotificacionInterna.objects.filter(usuario=request.usuario).select_related('alerta__regla')
    
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
@requiere_rol(['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR', 'DIRECTOR'])
def marcar_notificacion_leida(request, notificacion_id):
    """
    POST /api/alertas/notificaciones/internas/<id>/leer/
    Solo sobre notificaciones propias.
    """
    notificacion = get_object_or_404(NotificacionInterna, id=notificacion_id, usuario=request.usuario)
    notificacion.leida = True
    notificacion.save()
    return JsonResponse({'mensaje': 'Notificación marcada como leída'})
