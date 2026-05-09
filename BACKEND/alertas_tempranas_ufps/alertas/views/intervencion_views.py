import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from alertas.models import Alerta, Intervencion
from usuarios.models import Usuario

ESTADOS_PERMITIDOS = ['activa', 'en_monitoreo', 'ACTIVA', 'EN_MONITOREO', 'active', 'monitoring']


@csrf_exempt
@require_http_methods(["POST"])
def registrar_intervencion(request, alerta_id):
    """
    POST /api/alertas/<alerta_id>/intervenciones/

    Body JSON:
        usuario_id  – id del usuario que registra (obligatorio)
        tipo        – TUTORIA | CITACION | REMISION (obligatorio)
        observaciones – texto libre (obligatorio)
        evidencia   – texto opcional
        resultado   – texto opcional

    Reglas:
        - Solo alertas activas o en monitoreo
        - Registro inmutable (no se puede editar)
    """
    try:
        alerta = Alerta.objects.get(id=alerta_id)
    except Alerta.DoesNotExist:
        return JsonResponse({'error': 'Alerta no encontrada'}, status=404)

    # Validar estado de la alerta
    if alerta.estado not in ESTADOS_PERMITIDOS:
        return JsonResponse(
            {'error': 'No se pueden registrar intervenciones en alertas cerradas.'},
            status=400
        )

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Body JSON inválido'}, status=400)

    usuario_id    = body.get('usuario_id')
    tipo          = body.get('tipo', '').strip().upper()
    observaciones = body.get('observaciones', '').strip()
    evidencia     = body.get('evidencia', '').strip() or None
    resultado     = body.get('resultado', '').strip() or None

    # Validar campos obligatorios
    if not usuario_id:
        return JsonResponse({'error': 'usuario_id es obligatorio'}, status=400)
    if not tipo:
        return JsonResponse({'error': 'tipo es obligatorio'}, status=400)
    if not observaciones:
        return JsonResponse({'error': 'observaciones es obligatorio'}, status=400)

    # Validar tipo
    tipos_validos = ['TUTORIA', 'CITACION', 'REMISION']
    if tipo not in tipos_validos:
        return JsonResponse(
            {'error': f'tipo inválido. Opciones: {", ".join(tipos_validos)}'},
            status=400
        )

    # Validar usuario
    try:
        usuario = Usuario.objects.get(id=int(usuario_id))
    except (Usuario.DoesNotExist, ValueError):
        return JsonResponse({'error': 'usuario_id inválido o no encontrado'}, status=400)

    # Crear intervención
    intervencion = Intervencion.objects.create(
        alerta=alerta,
        usuario=usuario,
        tipo=tipo,
        observaciones=observaciones,
        evidencia=evidencia,
        resultado=resultado,
    )

    return JsonResponse({
        'mensaje': 'Intervención registrada exitosamente',
        'intervencion': {
            'id':           intervencion.id,
            'alerta_id':    alerta.id,
            'usuario':      usuario.nombre,
            'tipo':         intervencion.tipo,
            'observaciones': intervencion.observaciones,
            'evidencia':    intervencion.evidencia,
            'resultado':    intervencion.resultado,
            'fecha':        intervencion.fecha.strftime('%Y-%m-%d %H:%M'),
        }
    }, status=201)


@csrf_exempt
@require_http_methods(["GET"])
def listar_intervenciones(request, alerta_id):
    """
    GET /api/alertas/<alerta_id>/intervenciones/

    Retorna el historial de intervenciones de una alerta.
    """
    try:
        alerta = Alerta.objects.get(id=alerta_id)
    except Alerta.DoesNotExist:
        return JsonResponse({'error': 'Alerta no encontrada'}, status=404)

    intervenciones = Intervencion.objects.filter(alerta=alerta).order_by('-fecha')

    results = []
    for i in intervenciones:
        results.append({
            'id':            i.id,
            'tipo':          i.tipo,
            'observaciones': i.observaciones,
            'evidencia':     i.evidencia,
            'resultado':     i.resultado,
            'fecha':         i.fecha.strftime('%Y-%m-%d %H:%M'),
            'usuario':       i.usuario.nombre,
            'usuario_rol':   i.usuario.rol,
        })

    return JsonResponse({
        'alerta_id':  alerta_id,
        'estado':     alerta.estado,
        'total':      len(results),
        'intervenciones': results,
    })