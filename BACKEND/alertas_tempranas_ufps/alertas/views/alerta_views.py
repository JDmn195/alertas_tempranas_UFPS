from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from alertas.models import Alerta

@csrf_exempt
@require_http_methods(["GET"])
def listar_alertas(request):
    """
    GET /api/alertas/
    Retorna la lista de todas las alertas con la información del estudiante y regla.
    """
    alertas = Alerta.objects.select_related('estudiante', 'regla').all().order_by('-fecha_generacion')
    
    results = []
    for a in alertas:
        estado_raw = a.estado.strip().lower()
        if estado_raw in ['activa', 'active']:
            status = 'active'
        elif estado_raw in ['en_monitoreo', 'en monitoreo', 'monitoring', 'en seguimiento', 'en_seguimiento']:
            status = 'monitoring'
        elif estado_raw in ['atendida', 'attended']:
            status = 'attended'
        elif estado_raw in ['cerrada', 'closed']:
            status = 'closed'
        else:
            status = estado_raw

        results.append({
            'id': str(a.id),
            'studentName': a.estudiante.nombre if a.estudiante else 'Estudiante Desconocido',
            'studentCode': a.estudiante.codigo if a.estudiante else 'N/A',
            'riskLevel': a.regla.nivel if a.regla else 'medium',
            'alertType': a.regla.nombre if a.regla else 'Alerta de Riesgo',
            'generatedDate': a.fecha_generacion.strftime('%Y-%m-%d'),
            'assignedTeacher': 'Director de Programa',
            'status': status,
        })
        
    return JsonResponse({'alertas': results})
