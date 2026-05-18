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

    # Automatización de estados: Si está activa, pasar a en_monitoreo
    if alerta.estado.lower() in ['activa', 'active']:
        alerta.estado = 'en_monitoreo'
        alerta.save()

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


from alertas.models import AnotacionIntervencion

@csrf_exempt
@require_http_methods(["GET", "POST"])
def gestionar_anotaciones(request, intervencion_id):
    """
    GET: Lista las anotaciones de una intervención.
    POST: Crea una nueva anotación (requiere usuario_id y texto).
    """
    try:
        intervencion = Intervencion.objects.get(id=intervencion_id)
    except Intervencion.DoesNotExist:
        return JsonResponse({'error': 'Intervención no encontrada'}, status=404)

    if request.method == "GET":
        anotaciones = AnotacionIntervencion.objects.filter(intervencion=intervencion).order_by('-fecha')
        results = []
        for a in anotaciones:
            results.append({
                'id': a.id,
                'texto': a.texto,
                'fecha': a.fecha.strftime('%Y-%m-%d %H:%M'),
                'usuario': a.usuario.nombre,
                'usuario_rol': a.usuario.rol
            })
        return JsonResponse({'anotaciones': results})

    elif request.method == "POST":
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Body JSON inválido'}, status=400)

        usuario_id = body.get('usuario_id')
        texto = body.get('texto', '').strip()

        if not usuario_id or not texto:
            return JsonResponse({'error': 'usuario_id y texto son obligatorios'}, status=400)

        try:
            usuario = Usuario.objects.get(id=int(usuario_id))
        except (Usuario.DoesNotExist, ValueError):
            return JsonResponse({'error': 'usuario_id inválido o no encontrado'}, status=400)

        anotacion = AnotacionIntervencion.objects.create(
            intervencion=intervencion,
            usuario=usuario,
            texto=texto
        )

        return JsonResponse({
            'mensaje': 'Anotación creada exitosamente',
            'anotacion': {
                'id': anotacion.id,
                'texto': anotacion.texto,
                'fecha': anotacion.fecha.strftime('%Y-%m-%d %H:%M'),
                'usuario': usuario.nombre,
                'usuario_rol': usuario.rol
            }
        }, status=201)

@csrf_exempt
@require_http_methods(["DELETE"])
def eliminar_anotacion(request, anotacion_id):
    """
    DELETE /api/alertas/anotaciones/<id>/
    Elimina una anotación específica.
    """
    try:
        anotacion = AnotacionIntervencion.objects.get(id=anotacion_id)
        anotacion.delete()
        return JsonResponse({'mensaje': 'Anotación eliminada correctamente'})
    except AnotacionIntervencion.DoesNotExist:
        return JsonResponse({'error': 'Anotación no encontrada'}, status=404)

@csrf_exempt
@require_http_methods(["POST"])
def concluir_intervencion(request, intervencion_id):
    """
    POST /api/alertas/intervenciones/<id>/concluir/
    Recibe un 'resultado' (resumen), actualiza la intervención y cierra la alerta.
    """
    try:
        intervencion = Intervencion.objects.get(id=intervencion_id)
    except Intervencion.DoesNotExist:
        return JsonResponse({'error': 'Intervención no encontrada'}, status=404)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Body JSON inválido'}, status=400)

    resultado = body.get('resultado', '').strip()
    if not resultado:
        return JsonResponse({'error': 'El resumen final (resultado) es obligatorio'}, status=400)

    # Actualizar intervención
    intervencion.resultado = resultado
    intervencion.save()

    # Cambiar estado de la alerta a 'atendida'
    alerta = intervencion.alerta
    alerta.estado = 'atendida'
    alerta.save()

    return JsonResponse({'mensaje': 'Intervención concluida y alerta marcada como atendida'})
