"""
HU-41: Bandeja de solicitudes de acompañamiento para el personal (Bienestar,
Dirección y Administración).
"""
import json

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from academico.models import Periodo
from alertas.models import SolicitudAcompanamiento
from alertas.solicitudes import (
    ESTADOS, ESTADOS_FINALES, ROLES_GESTION, TRANSICIONES, notificar_actualizacion_solicitud,
    programar_notificacion,
)
from usuarios.decorators import requiere_rol
from usuarios.models import Usuario
from usuarios.utils import registrar_auditoria


def _serializar(solicitud):
    estudiante = solicitud.estudiante
    alerta = solicitud.alerta
    responsable = solicitud.responsable
    return {
        'id': solicitud.id,
        'estudiante': {
            'codigo': estudiante.codigo,
            'nombre': estudiante.nombre,
            'semestre': estudiante.semestre,
            'correo': estudiante.email_institucional or estudiante.email_personal,
        },
        'motivo': solicitud.motivo,
        'motivo_texto': solicitud.get_motivo_display(),
        'descripcion': solicitud.descripcion,
        'alerta': {'id': alerta.id, 'tipo': alerta.regla.nombre, 'estado': alerta.estado} if alerta else None,
        'periodo': str(solicitud.periodo) if solicitud.periodo else None,
        'estado': solicitud.estado,
        'estado_texto': solicitud.get_estado_display(),
        'responsable': {'id': responsable.id, 'nombre': responsable.nombre} if responsable else None,
        'respuesta': solicitud.respuesta,
        'fecha_solicitud': solicitud.fecha_solicitud.isoformat(),
        'fecha_atencion': solicitud.fecha_atencion.isoformat() if solicitud.fecha_atencion else None,
        'fecha_actualizacion': solicitud.fecha_actualizacion.isoformat(),
        'transiciones': list(TRANSICIONES.get(solicitud.estado, ())),
    }


def _consulta():
    return SolicitudAcompanamiento.objects.select_related('estudiante', 'alerta__regla', 'responsable', 'periodo')


@require_http_methods(["GET"])
@requiere_rol(ROLES_GESTION)
def listar_solicitudes(request):
    """
    GET /api/alertas/solicitudes/?estado=&periodo=
    Solicitudes de acompañamiento con los datos del estudiante, de la más reciente a la
    más antigua. estado: PENDIENTE | EN_ATENCION | ATENDIDA | CANCELADA; periodo: AAAA-S.
    """
    qs = _consulta()

    estado = (request.GET.get('estado') or '').strip().upper()
    if estado:
        if estado not in ESTADOS:
            return JsonResponse({'error': f"Estado no válido. Use uno de: {', '.join(ESTADOS)}."}, status=400)
        qs = qs.filter(estado=estado)

    periodo = (request.GET.get('periodo') or '').strip()
    if periodo:
        try:
            anio, semestre = (int(p) for p in periodo.split('-'))
        except ValueError:
            return JsonResponse({'error': 'Periodo no válido. Use el formato AAAA-S (por ejemplo, 2026-1).'},
                                status=400)
        qs = qs.filter(periodo__anio=anio, periodo__semestre=semestre)

    todas = SolicitudAcompanamiento.objects.all()
    conteos = {clave: todas.filter(estado=clave).count() for clave in ESTADOS}
    conteos['total'] = todas.count()
    periodos = [
        str(p) for p in Periodo.objects.filter(solicitudacompanamiento__isnull=False)
        .distinct().order_by('-anio', '-semestre')
    ]

    return JsonResponse({
        'solicitudes': [_serializar(s) for s in qs.order_by('-fecha_solicitud', '-id')],
        'conteos': conteos,
        'periodos': periodos,
        'estados': [{'valor': valor, 'texto': texto} for valor, texto in ESTADOS.items()],
    })


@csrf_exempt
@require_http_methods(["PATCH"])
@requiere_rol(ROLES_GESTION)
def gestionar_solicitud(request, solicitud_id):
    """
    PATCH /api/alertas/solicitudes/<id>/

    Body JSON (todos opcionales, al menos uno):
        estado          – EN_ATENCION | ATENDIDA | CANCELADA
        responsable_id  – usuario Bienestar, Director o Administrador activo
                          (por defecto, quien toma la solicitud)
        respuesta       – texto para el estudiante (obligatorio al pasar a ATENDIDA)

    Reglas:
        - PENDIENTE -> EN_ATENCION | ATENDIDA | CANCELADA; EN_ATENCION -> ATENDIDA | CANCELADA
        - ATENDIDA y CANCELADA son finales (409)
        - Al pasar a EN_ATENCION o ATENDIDA sin responsable se asigna el usuario autenticado
        - Al pasar a ATENDIDA se guarda fecha_atencion
        - Se avisa al estudiante cuando cambia el estado o la respuesta
    """
    try:
        body = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Body JSON inválido'}, status=400)
    if not isinstance(body, dict):
        return JsonResponse({'error': 'Body JSON inválido'}, status=400)

    nuevo_estado = (body.get('estado') or '').strip().upper() or None
    respuesta = body.get('respuesta')
    respuesta = str(respuesta).strip() if respuesta is not None else None
    responsable_id = body.get('responsable_id')

    if nuevo_estado is None and respuesta is None and responsable_id is None:
        return JsonResponse({'error': 'Indique el estado, el responsable o la respuesta.'}, status=400)
    if nuevo_estado is not None and nuevo_estado not in ESTADOS:
        return JsonResponse({'error': f"Estado no válido. Use uno de: {', '.join(ESTADOS)}."}, status=400)

    responsable = None
    if responsable_id is not None:
        responsable = Usuario.objects.filter(id=responsable_id, rol__in=ROLES_GESTION, activo=True).first() \
            if str(responsable_id).isdigit() else None
        if responsable is None:
            return JsonResponse(
                {'error': 'El responsable debe ser un usuario activo de Bienestar, Dirección o Administración.'},
                status=400,
            )

    with transaction.atomic():
        solicitud = _consulta().select_for_update(of=('self',)).filter(id=solicitud_id).first()
        if solicitud is None:
            return JsonResponse({'error': 'Solicitud no encontrada'}, status=404)

        anterior = solicitud.estado
        if anterior in ESTADOS_FINALES:
            return JsonResponse(
                {'error': f'La solicitud ya está {solicitud.get_estado_display().lower()} y no admite cambios.'},
                status=409,
            )
        if nuevo_estado == anterior:
            nuevo_estado = None
        if nuevo_estado is not None and nuevo_estado not in TRANSICIONES[anterior]:
            return JsonResponse({
                'error': f'No se puede pasar de {ESTADOS[anterior].lower()} a {ESTADOS[nuevo_estado].lower()}.',
            }, status=409)

        if nuevo_estado == 'ATENDIDA' and not (respuesta if respuesta is not None else solicitud.respuesta):
            return JsonResponse({'error': 'Registre la respuesta para el estudiante antes de marcarla como atendida.'},
                                status=400)

        cambios = []
        if responsable is not None and responsable.id != solicitud.responsable_id:
            solicitud.responsable = responsable
            cambios.append(f'responsable {responsable.nombre}')
        if nuevo_estado in ('EN_ATENCION', 'ATENDIDA') and solicitud.responsable_id is None:
            solicitud.responsable = request.usuario
            cambios.append(f'responsable {request.usuario.nombre}')
        respuesta_cambio = respuesta is not None and respuesta != (solicitud.respuesta or '')
        if respuesta_cambio:
            solicitud.respuesta = respuesta or None
            cambios.append('respuesta registrada')
        if nuevo_estado is not None:
            solicitud.estado = nuevo_estado
            if nuevo_estado == 'ATENDIDA':
                solicitud.fecha_atencion = timezone.now()
            cambios.insert(0, f'estado {anterior} -> {nuevo_estado}')

        if not cambios:
            return JsonResponse(_serializar(solicitud))

        solicitud.save()
        registrar_auditoria(
            request.usuario, 'GESTIONAR_SOLICITUD',
            f"Solicitud de acompañamiento ID {solicitud.id} del estudiante {solicitud.estudiante_id}: "
            f"{', '.join(cambios)}",
        )
        if nuevo_estado is not None or respuesta_cambio:
            programar_notificacion(notificar_actualizacion_solicitud, solicitud.id)

    return JsonResponse(_serializar(_consulta().get(pk=solicitud.pk)))
