import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from alertas.models import Alerta, Intervencion
from usuarios.models import Usuario
from usuarios.decorators import requiere_rol
from usuarios.utils import registrar_auditoria

# Alertas cerradas no permiten nuevas intervenciones
ESTADOS_NO_PERMITIDOS = ['cerrada', 'closed']


def recalcular_estado_alerta(alerta):
    """
    Recalcula y guarda el estado de la alerta según sus intervenciones:
    - Sin intervenciones           → 'activa'
    - Al menos una sin concluir    → 'en_seguimiento'
    - Todas concluidas (≥1)        → 'atendida'
    - Cerrada manualmente          → 'cerrada'  (no se toca)
    """
    if alerta.estado == 'cerrada':
        return alerta.estado

    intervenciones = Intervencion.objects.filter(alerta=alerta)
    total = intervenciones.count()

    if total == 0:
        nuevo_estado = 'activa'
    elif intervenciones.filter(concluida=False).exists():
        nuevo_estado = 'en_seguimiento'
    else:
        nuevo_estado = 'atendida'

    alerta.estado = nuevo_estado
    alerta.save()
    return nuevo_estado


@csrf_exempt
@require_http_methods(["POST"])
@requiere_rol(['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR', 'DIRECTOR'])
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

    # Validar estado de la alerta — solo las cerradas bloquean nuevas intervenciones
    if alerta.estado.lower() in ESTADOS_NO_PERMITIDOS:
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

    # Registrar auditoría de la intervención
    registrar_auditoria(
        usuario,
        'REGISTRAR_INTERVENCION',
        f"Registrada intervención '{tipo}' para la alerta ID {alerta.id} del estudiante {alerta.estudiante.codigo}."
    )

    # Recalcular estado de la alerta
    recalcular_estado_alerta(alerta)

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
            'concluida':    intervencion.concluida,
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
            'concluida':     i.concluida,
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
@requiere_rol(['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR', 'DIRECTOR'])
def concluir_intervencion(request, intervencion_id):
    """
    POST /api/alertas/intervenciones/<id>/concluir/
    Marca la intervención como concluida y recalcula el estado de la alerta:
    - Si quedan intervenciones sin concluir → 'en_seguimiento'
    - Si todas están concluidas             → 'atendida'
    """
    try:
        intervencion = Intervencion.objects.get(id=intervencion_id)
    except Intervencion.DoesNotExist:
        return JsonResponse({'error': 'Intervención no encontrada'}, status=404)

    if intervencion.concluida:
        return JsonResponse({'error': 'Esta intervención ya fue concluida'}, status=400)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Body JSON inválido'}, status=400)

    resultado = body.get('resultado', '').strip()
    if not resultado:
        return JsonResponse({'error': 'El resumen final (resultado) es obligatorio'}, status=400)

    # Marcar intervención como concluida
    intervencion.resultado = resultado
    intervencion.concluida = True
    intervencion.save()

    # Recalcular estado de la alerta
    alerta = intervencion.alerta
    nuevo_estado = recalcular_estado_alerta(alerta)

    # Registrar auditoría
    registrar_auditoria(
        request.usuario,
        'CONCLUIR_INTERVENCION',
        f"Concluida intervención ID {intervencion.id} de tipo '{intervencion.tipo}' para alerta ID {alerta.id}. Estado alerta: {nuevo_estado}."
    )

    return JsonResponse({
        'mensaje': 'Intervención concluida correctamente',
        'estado_alerta': nuevo_estado,
    })

