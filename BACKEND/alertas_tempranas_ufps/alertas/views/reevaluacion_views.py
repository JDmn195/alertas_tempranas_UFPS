"""
HU-29: Endpoints de la re-evaluación periódica del riesgo.

  POST /api/alertas/reevaluacion/programada/          ← programador externo (header X-Cron-Token)
  POST /api/alertas/reevaluacion/ejecutar/            ← ejecución manual (ADMINISTRADOR)
  GET  /api/alertas/reevaluacion/ejecuciones/         ← bitácora de ejecuciones
  GET  /api/alertas/reevaluacion/ejecuciones/<id>/    ← detalle (errores y cambios de riesgo)

La re-evaluación corre en un hilo para no exceder el timeout de gunicorn;
la respuesta es 202 y el resultado queda en la bitácora.
"""
import hmac

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from alertas.models import EjecucionReevaluacion
from alertas.reevaluacion import ReevaluacionEnCurso, ejecutar_reevaluacion, hay_ejecucion_en_curso
from alertas.tareas import ejecutar_en_segundo_plano
from usuarios.decorators import requiere_rol


def _reevaluar(origen, usuario):
    try:
        ejecutar_reevaluacion(origen=origen, usuario=usuario)
    except ReevaluacionEnCurso:
        pass


def lanzar_en_segundo_plano(origen, usuario=None):
    ejecutar_en_segundo_plano(_reevaluar, origen, usuario)


def _iniciar(origen, usuario=None):
    if hay_ejecucion_en_curso():
        return JsonResponse({'error': 'Ya hay una re-evaluación en curso.'}, status=409)
    lanzar_en_segundo_plano(origen, usuario)
    return JsonResponse({'mensaje': 'Re-evaluación iniciada. Consulte la bitácora de ejecuciones.'}, status=202)


def _serializar(ej, detalle=False):
    data = {
        'id': ej.id,
        'origen': ej.origen,
        'estado': ej.estado,
        'intento': ej.intento,
        'reintento_de': ej.reintento_de_id,
        'usuario': ej.usuario.nombre if ej.usuario else None,
        'fecha_inicio': ej.fecha_inicio.isoformat(),
        'fecha_fin': ej.fecha_fin.isoformat() if ej.fecha_fin else None,
        'total_estudiantes': ej.total_estudiantes,
        'procesados': ej.procesados,
        'total_errores': ej.total_errores,
        'cambios_riesgo': ej.cambios_riesgo,
        'alertas_generadas': ej.alertas_generadas,
        'alertas_actualizadas': ej.alertas_actualizadas,
        'alertas_cerradas': ej.alertas_cerradas,
        'estudiantes_por_nivel': ej.estudiantes_por_nivel,
        'mensaje_error': ej.mensaje_error,
    }
    if detalle:
        data.update({
            'alcance': ej.alcance,
            'detalle_cambios': ej.detalle_cambios,
            'errores': ej.errores,
        })
    return data


@csrf_exempt
@require_http_methods(["POST"])
def reevaluacion_programada(request):
    token_esperado = settings.REEVALUACION_CRON_TOKEN
    if not token_esperado:
        return JsonResponse({'error': 'Re-evaluación programada no configurada.'}, status=503)
    token = request.headers.get('X-Cron-Token', '')
    if not hmac.compare_digest(token, token_esperado):
        return JsonResponse({'error': 'No autorizado.'}, status=401)
    return _iniciar('PROGRAMADA')


@csrf_exempt
@require_http_methods(["POST"])
@requiere_rol(['ADMINISTRADOR'])
def reevaluacion_manual(request):
    return _iniciar('MANUAL', request.usuario)


@require_http_methods(["GET"])
@requiere_rol(['ADMINISTRADOR', 'DIRECTOR'])
def listar_ejecuciones(request):
    try:
        limite = min(int(request.GET.get('limite', 50)), 200)
    except ValueError:
        limite = 50
    qs = EjecucionReevaluacion.objects.select_related('usuario')
    estado = request.GET.get('estado')
    if estado:
        qs = qs.filter(estado=estado.upper())
    return JsonResponse({'ejecuciones': [_serializar(ej) for ej in qs[:limite]]})


@require_http_methods(["GET"])
@requiere_rol(['ADMINISTRADOR', 'DIRECTOR'])
def detalle_ejecucion(request, ejecucion_id):
    ej = get_object_or_404(EjecucionReevaluacion.objects.select_related('usuario'), id=ejecucion_id)
    return JsonResponse(_serializar(ej, detalle=True))
