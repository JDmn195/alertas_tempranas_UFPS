"""
HU-30: Endpoints de recordatorios de alertas e intervenciones sin seguimiento.

  GET|PUT /api/alertas/recordatorios/configuracion/          ← parámetros (ADMINISTRADOR, DIRECTOR)
  POST    /api/alertas/recordatorios/programada/             ← programador externo (header X-Cron-Token)
  POST    /api/alertas/recordatorios/ejecutar/               ← ejecución manual (ADMINISTRADOR, DIRECTOR)
  GET     /api/alertas/recordatorios/                        ← recordatorios enviados, estado y reintentos
  GET     /api/alertas/recordatorios/casos-sin-seguimiento/  ← vista previa de la detección

El envío corre en segundo plano; la respuesta es 202 (o 409 si ya hay uno en
curso) y el resultado queda en los recordatorios y en la auditoría.
"""
import hmac
import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from alertas.models import ConfiguracionRecordatorio, Recordatorio
from alertas.recordatorios import (
    RecordatoriosEnCurso, detectar_casos_sin_seguimiento, hay_envio_en_curso, procesar_recordatorios,
)
from alertas.tareas import ejecutar_en_segundo_plano
from usuarios.decorators import requiere_rol
from usuarios.models import Usuario
from usuarios.utils import registrar_auditoria

ROLES_COORDINACION = ['ADMINISTRADOR', 'DIRECTOR']
ROLES_VALIDOS = [r for r, _ in Usuario.ROL_CHOICES]
CAMPOS_ENTEROS = ['dias_inactividad_alerta', 'dias_inactividad_intervencion', 'dias_entre_recordatorios', 'max_intentos']
CAMPOS_BOOLEANOS = ['activo', 'notificar_responsable']


def _procesar(origen, usuario):
    try:
        procesar_recordatorios(usuario=usuario, origen=origen)
    except RecordatoriosEnCurso:
        pass


def lanzar_en_segundo_plano(origen, usuario=None):
    ejecutar_en_segundo_plano(_procesar, origen, usuario)


def _iniciar(origen, usuario=None):
    if hay_envio_en_curso():
        return JsonResponse({'error': 'Ya hay un envío de recordatorios en curso.'}, status=409)
    lanzar_en_segundo_plano(origen, usuario)
    return JsonResponse({'mensaje': 'Envío de recordatorios iniciado. Consulte el listado de recordatorios.'},
                        status=202)


def _serializar_config(config):
    return {
        'activo': config.activo,
        'dias_inactividad_alerta': config.dias_inactividad_alerta,
        'dias_inactividad_intervencion': config.dias_inactividad_intervencion,
        'dias_entre_recordatorios': config.dias_entre_recordatorios,
        'max_intentos': config.max_intentos,
        'roles_destinatarios': config.roles_destinatarios,
        'notificar_responsable': config.notificar_responsable,
        'fecha_actualizacion': config.fecha_actualizacion.isoformat(),
        'actualizado_por': config.actualizado_por.nombre if config.actualizado_por else None,
    }


def _serializar(r):
    return {
        'id': r.id,
        'tipo_caso': r.tipo_caso,
        'alerta_id': r.alerta_id,
        'intervencion_id': r.intervencion_id,
        'estudiante': {'codigo': r.alerta.estudiante.codigo, 'nombre': r.alerta.estudiante.nombre},
        'destinatario': {'id': r.destinatario_id, 'nombre': r.destinatario.nombre, 'rol': r.destinatario.rol},
        'estado': r.estado,
        'dias_inactivo': r.dias_inactivo,
        'ultima_actividad': r.ultima_actividad.isoformat(),
        'canales': r.canales,
        'intentos': r.intentos,
        'max_intentos': r.max_intentos,
        'historial_intentos': r.historial_intentos,
        'ultimo_error': r.ultimo_error,
        'fecha_creacion': r.fecha_creacion.isoformat(),
        'fecha_ultimo_intento': r.fecha_ultimo_intento.isoformat() if r.fecha_ultimo_intento else None,
        'fecha_envio': r.fecha_envio.isoformat() if r.fecha_envio else None,
        'fecha_cancelacion': r.fecha_cancelacion.isoformat() if r.fecha_cancelacion else None,
        'motivo_cancelacion': r.motivo_cancelacion,
    }


@csrf_exempt
@require_http_methods(["GET", "PUT"])
@requiere_rol(ROLES_COORDINACION)
def configuracion_recordatorios(request):
    config = ConfiguracionRecordatorio.obtener()
    if request.method == 'GET':
        return JsonResponse(_serializar_config(config))

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Body JSON inválido'}, status=400)

    cambios = {}
    for campo in CAMPOS_ENTEROS:
        if campo in body:
            valor = body[campo]
            if isinstance(valor, bool) or not isinstance(valor, int) or not 1 <= valor <= 365:
                return JsonResponse({'error': f'{campo} debe ser un entero entre 1 y 365.'}, status=400)
            cambios[campo] = valor
    if 'max_intentos' in cambios and cambios['max_intentos'] > 10:
        return JsonResponse({'error': 'max_intentos debe estar entre 1 y 10.'}, status=400)
    for campo in CAMPOS_BOOLEANOS:
        if campo in body:
            if not isinstance(body[campo], bool):
                return JsonResponse({'error': f'{campo} debe ser booleano.'}, status=400)
            cambios[campo] = body[campo]
    if 'roles_destinatarios' in body:
        roles = body['roles_destinatarios']
        if not isinstance(roles, list) or not all(isinstance(r, str) for r in roles):
            return JsonResponse({'error': 'roles_destinatarios debe ser una lista de roles.'}, status=400)
        roles = sorted({r.strip().upper() for r in roles})
        invalidos = [r for r in roles if r not in ROLES_VALIDOS]
        if invalidos:
            return JsonResponse({'error': f'Roles inválidos: {", ".join(invalidos)}. '
                                          f'Opciones: {", ".join(ROLES_VALIDOS)}'}, status=400)
        cambios['roles_destinatarios'] = roles

    if not cambios:
        return JsonResponse({'error': 'No se enviaron parámetros para actualizar.'}, status=400)

    for campo, valor in cambios.items():
        setattr(config, campo, valor)
    config.actualizado_por = request.usuario
    # update_fields: no sobrescribir `ejecutando_desde` si hay un envío en curso
    config.save(update_fields=[*cambios, 'actualizado_por', 'fecha_actualizacion'])

    registrar_auditoria(
        request.usuario,
        'CONFIGURAR_RECORDATORIOS',
        'Parámetros de recordatorios actualizados: ' + ', '.join(f'{k}={v}' for k, v in cambios.items()),
    )
    return JsonResponse(_serializar_config(config))


@csrf_exempt
@require_http_methods(["POST"])
def recordatorios_programada(request):
    token_esperado = settings.RECORDATORIOS_CRON_TOKEN
    if not token_esperado:
        return JsonResponse({'error': 'Recordatorios programados no configurados.'}, status=503)
    token = request.headers.get('X-Cron-Token', '')
    if not hmac.compare_digest(token, token_esperado):
        return JsonResponse({'error': 'No autorizado.'}, status=401)
    return _iniciar('PROGRAMADA')


@csrf_exempt
@require_http_methods(["POST"])
@requiere_rol(ROLES_COORDINACION)
def recordatorios_manual(request):
    return _iniciar('MANUAL', request.usuario)


@require_http_methods(["GET"])
@requiere_rol(ROLES_COORDINACION)
def listar_recordatorios(request):
    try:
        limite = min(int(request.GET.get('limite', 100)), 500)
    except ValueError:
        limite = 100

    qs = Recordatorio.objects.select_related('alerta__estudiante', 'destinatario')
    filtros = {
        'estado': ('estado', str.upper),
        'tipo_caso': ('tipo_caso', str.upper),
        'alerta_id': ('alerta_id', str),
        'intervencion_id': ('intervencion_id', str),
        'destinatario_id': ('destinatario_id', str),
    }
    for param, (campo, normalizar) in filtros.items():
        valor = request.GET.get(param)
        if valor:
            qs = qs.filter(**{campo: normalizar(valor)})

    return JsonResponse({'recordatorios': [_serializar(r) for r in qs[:limite]]})


@require_http_methods(["GET"])
@requiere_rol(ROLES_COORDINACION)
def casos_sin_seguimiento(request):
    config = ConfiguracionRecordatorio.obtener()
    casos = detectar_casos_sin_seguimiento(config)
    return JsonResponse({
        'total': len(casos),
        'casos': [{
            'tipo_caso': c['tipo_caso'],
            'alerta_id': c['alerta'].id,
            'intervencion_id': c['intervencion'].id if c['intervencion'] else None,
            'estudiante': {'codigo': c['alerta'].estudiante.codigo, 'nombre': c['alerta'].estudiante.nombre},
            'regla': c['alerta'].regla.nombre,
            'nivel': c['alerta'].regla.nivel,
            'responsable': c['intervencion'].usuario.nombre if c['intervencion'] else None,
            'ultima_actividad': c['ultima_actividad'].isoformat(),
            'dias_inactivo': c['dias_inactivo'],
        } for c in sorted(casos, key=lambda c: -c['dias_inactivo'])],
    })
