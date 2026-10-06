"""
HU-30: Recordatorios automáticos de alertas e intervenciones sin seguimiento.

Casos sin seguimiento (parámetros en ConfiguracionRecordatorio):
  - ALERTA: alerta activa sin intervenciones, generada hace más de
    `dias_inactividad_alerta` días.
  - INTERVENCION: intervención no concluida (de una alerta no cerrada) cuya
    última actividad —registro, anotación o evidencia— tiene más de
    `dias_inactividad_intervencion` días.

Por cada caso y destinatario se crea un Recordatorio. El envío usa los canales
existentes, agrupado por destinatario: una notificación interna por caso y un
único correo de resumen con todos sus casos (para no saturar al coordinador).
Si un canal falla, el recordatorio queda PENDIENTE y en la siguiente ejecución
se reintentan solo los canales fallidos, hasta `max_intentos`.

Un bloqueo en la BD (ConfiguracionRecordatorio.ejecutando_desde) impide dos
ejecuciones simultáneas aunque vengan de workers distintos.

Cuando se registra seguimiento (intervención, anotación, evidencia, conclusión o
cierre de la alerta) los recordatorios PENDIENTES del caso se cancelan (ver
alertas/signals.py). Antes de cada reintento también se revalida el caso.

Punto de entrada: procesar_recordatorios() (comando `enviar_recordatorios` y
endpoints de recordatorio_views).
"""
import logging
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Max, Q
from django.utils import timezone
from django.utils.html import escape

from alertas.models import Alerta, ConfiguracionRecordatorio, Intervencion, Recordatorio
from alertas.services import NotificationService
from usuarios.models import Usuario
from usuarios.utils import registrar_auditoria

logger = logging.getLogger(__name__)

ESTADOS_ALERTA_SIN_INTERVENCION = ['activa', 'active']
ESTADOS_ALERTA_CERRADOS = ['cerrada', 'closed']
CANALES = ['EMAIL', 'INTERNA']

# Casos listados en el correo de resumen; el resto se menciona como "y N más"
MAX_CASOS_CORREO = 100


class RecordatoriosEnCurso(Exception):
    """Ya hay un envío de recordatorios en curso (en cualquier proceso)."""


# ---------------------------------------------------------------------------
# Detección
# ---------------------------------------------------------------------------

def ultima_actividad_intervencion(intervencion, ult_anotacion=None, ult_evidencia=None):
    fechas = [intervencion.fecha, ult_anotacion, ult_evidencia]
    return max(f for f in fechas if f is not None)


def _caso(tipo, alerta, ultima_actividad, ahora, intervencion=None):
    return {
        'tipo_caso': tipo,
        'alerta': alerta,
        'intervencion': intervencion,
        'ultima_actividad': ultima_actividad,
        'dias_inactivo': (ahora - ultima_actividad).days,
    }


def detectar_casos_sin_seguimiento(config=None, ahora=None):
    """Retorna la lista de casos (dicts) que superan el tiempo de inactividad configurado."""
    config = config or ConfiguracionRecordatorio.obtener()
    ahora = ahora or timezone.now()
    casos = []

    limite_alerta = ahora - timedelta(days=config.dias_inactividad_alerta)
    alertas = (
        Alerta.objects.filter(estado__in=ESTADOS_ALERTA_SIN_INTERVENCION, fecha_generacion__lte=limite_alerta)
        .annotate(n_intervenciones=Count('intervencion'))
        .filter(n_intervenciones=0)
        .select_related('estudiante', 'regla')
    )
    for alerta in alertas:
        casos.append(_caso('ALERTA', alerta, alerta.fecha_generacion, ahora))

    limite_intervencion = ahora - timedelta(days=config.dias_inactividad_intervencion)
    intervenciones = (
        Intervencion.objects.filter(concluida=False, fecha__lte=limite_intervencion)
        .exclude(alerta__estado__in=ESTADOS_ALERTA_CERRADOS)
        .annotate(ult_anotacion=Max('anotaciones__fecha'), ult_evidencia=Max('evidencias__fecha_subida'))
        .select_related('alerta__estudiante', 'alerta__regla', 'usuario')
    )
    for intervencion in intervenciones:
        ultima = ultima_actividad_intervencion(intervencion, intervencion.ult_anotacion, intervencion.ult_evidencia)
        if ultima <= limite_intervencion:
            casos.append(_caso('INTERVENCION', intervencion.alerta, ultima, ahora, intervencion))

    return casos


def destinatarios_caso(caso, config):
    """Coordinación (roles configurados) + responsable de la intervención. Sin destinatarios → administradores."""
    usuarios = {u.id: u for u in Usuario.objects.filter(rol__in=config.roles_destinatarios or [], activo=True)}

    intervencion = caso['intervencion']
    if intervencion is not None and config.notificar_responsable and intervencion.usuario.activo:
        usuarios.setdefault(intervencion.usuario_id, intervencion.usuario)

    if not usuarios:
        usuarios = {u.id: u for u in Usuario.objects.filter(rol='ADMINISTRADOR', activo=True)}
    return list(usuarios.values())


def _filtro_caso(tipo_caso, alerta, intervencion):
    if tipo_caso == 'INTERVENCION':
        return {'tipo_caso': 'INTERVENCION', 'intervencion': intervencion}
    return {'tipo_caso': 'ALERTA', 'alerta': alerta}


def caso_sigue_sin_seguimiento(recordatorio):
    """Revalida el caso de un recordatorio. Retorna (sigue_sin_seguimiento, motivo)."""
    alerta = Alerta.objects.get(pk=recordatorio.alerta_id)
    if alerta.estado in ESTADOS_ALERTA_CERRADOS:
        return False, 'La alerta fue cerrada.'

    if recordatorio.tipo_caso == 'ALERTA':
        if Intervencion.objects.filter(alerta=alerta).exists():
            return False, 'Se registró una intervención en la alerta.'
        return True, None

    intervencion = (
        Intervencion.objects.filter(pk=recordatorio.intervencion_id)
        .annotate(ult_anotacion=Max('anotaciones__fecha'), ult_evidencia=Max('evidencias__fecha_subida'))
        .first()
    )
    if intervencion is None:
        return False, 'La intervención ya no existe.'
    if intervencion.concluida:
        return False, 'La intervención fue concluida.'
    ultima = ultima_actividad_intervencion(intervencion, intervencion.ult_anotacion, intervencion.ult_evidencia)
    if ultima > recordatorio.ultima_actividad:
        return False, 'Se registró seguimiento en la intervención.'
    return True, None


# ---------------------------------------------------------------------------
# Cancelación
# ---------------------------------------------------------------------------

def cancelar_recordatorios(motivo, alerta=None, intervencion=None, tipo_caso=None):
    """
    Cancela los recordatorios PENDIENTES de un caso. Con `alerta` cancela los de la
    alerta (filtrables por `tipo_caso`); con `intervencion`, los de esa intervención.
    Retorna cuántos se cancelaron.
    """
    qs = Recordatorio.objects.filter(estado='PENDIENTE')
    if intervencion is not None:
        qs = qs.filter(intervencion=intervencion)
    elif alerta is not None:
        qs = qs.filter(alerta=alerta)
    else:
        return 0
    if tipo_caso:
        qs = qs.filter(tipo_caso=tipo_caso)
    return qs.update(estado='CANCELADO', fecha_cancelacion=timezone.now(), motivo_cancelacion=motivo[:255])


def _cancelar(recordatorio, motivo):
    recordatorio.estado = 'CANCELADO'
    recordatorio.fecha_cancelacion = timezone.now()
    recordatorio.motivo_cancelacion = motivo[:255]
    recordatorio.save(update_fields=['estado', 'fecha_cancelacion', 'motivo_cancelacion'])


# ---------------------------------------------------------------------------
# Bloqueo entre procesos
# ---------------------------------------------------------------------------

def _limite_bloqueo():
    return timezone.now() - timedelta(hours=settings.RECORDATORIOS_BLOQUEO_HORAS)


def hay_envio_en_curso():
    return ConfiguracionRecordatorio.objects.filter(
        pk=ConfiguracionRecordatorio.obtener().pk, ejecutando_desde__gte=_limite_bloqueo()
    ).exists()


def _adquirir_bloqueo(config):
    """UPDATE atómico: solo una ejecución (de cualquier proceso/worker) toma el bloqueo.
    Un bloqueo más viejo que RECORDATORIOS_BLOQUEO_HORAS se considera abandonado."""
    tomado = ConfiguracionRecordatorio.objects.filter(pk=config.pk).filter(
        Q(ejecutando_desde__isnull=True) | Q(ejecutando_desde__lt=_limite_bloqueo())
    ).update(ejecutando_desde=timezone.now())
    return tomado == 1


def _liberar_bloqueo(config):
    ConfiguracionRecordatorio.objects.filter(pk=config.pk).update(ejecutando_desde=None)


# ---------------------------------------------------------------------------
# Envío
# ---------------------------------------------------------------------------

def _descripcion_caso(recordatorio):
    alerta = recordatorio.alerta
    estudiante = alerta.estudiante
    if recordatorio.tipo_caso == 'INTERVENCION':
        intervencion = recordatorio.intervencion
        return (
            f"La intervención {intervencion.get_tipo_display()} (ID {intervencion.id}) de la alerta "
            f"'{alerta.regla.nombre}' del estudiante {estudiante.nombre} ({estudiante.codigo}) "
            f"lleva {recordatorio.dias_inactivo} días sin seguimiento."
        )
    return (
        f"La alerta '{alerta.regla.nombre}' ({alerta.regla.get_nivel_display()}) del estudiante "
        f"{estudiante.nombre} ({estudiante.codigo}) lleva {recordatorio.dias_inactivo} días sin intervenciones."
    )


def asunto_resumen(recordatorios_correo):
    if len(recordatorios_correo) == 1:
        return f"Recordatorio: caso sin seguimiento - {recordatorios_correo[0].alerta.estudiante.nombre}"
    return f"Recordatorio: {len(recordatorios_correo)} casos sin seguimiento"


def generar_html_resumen(destinatario, recordatorios_correo):
    """Un solo correo por destinatario con todos sus casos sin seguimiento."""
    ordenados = sorted(recordatorios_correo, key=lambda r: -r.dias_inactivo)
    visibles = ordenados[:MAX_CASOS_CORREO]
    celda = 'padding: 8px; border-bottom: 1px solid #eee; text-align: left;'
    filas = []
    for r in visibles:
        alerta = r.alerta
        if r.tipo_caso == 'INTERVENCION':
            caso = escape(f"Intervención {r.intervencion.get_tipo_display()} (responsable: {r.intervencion.usuario.nombre})")
        else:
            caso = 'Alerta sin intervenciones'
        filas.append(
            f'<tr><td style="{celda}">{escape(alerta.estudiante.nombre)}<br><small>{escape(alerta.estudiante.codigo)}</small></td>'
            f'<td style="{celda}">{caso}</td>'
            f'<td style="{celda}">{escape(alerta.regla.nombre)}<br><small>{escape(alerta.regla.get_nivel_display())}</small></td>'
            f'<td style="{celda} text-align: center;"><strong>{r.dias_inactivo}</strong></td></tr>'
        )
    filas_html = ''.join(filas)
    restantes = len(ordenados) - len(visibles)
    nota_restantes = (
        f'<p style="font-size: 13px; color: #6c757d;">… y {restantes} casos más. Consúltalos en el sistema.</p>'
        if restantes > 0 else ''
    )
    if len(ordenados) == 1:
        intro = 'Hay un caso que lleva tiempo sin seguimiento:'
    else:
        intro = f'Hay <strong>{len(ordenados)} casos</strong> que llevan tiempo sin seguimiento:'

    return f"""
        <html>
        <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; padding: 20px;">
            <div style="max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-top: 5px solid #d97706;">
                <div style="padding: 20px; text-align: center; background-color: #f8f9fa;">
                    <h2 style="color: #d97706; margin: 0;">Recordatorio: casos sin seguimiento</h2>
                </div>
                <div style="padding: 30px;">
                    <p>Hola, <strong>{escape(destinatario.nombre)}</strong>.</p>
                    <p>{intro}</p>
                    <table style="width: 100%; border-collapse: collapse; font-size: 14px; margin: 20px 0;">
                        <thead>
                            <tr style="background-color: #fffbeb;">
                                <th style="{celda}">Estudiante</th>
                                <th style="{celda}">Caso</th>
                                <th style="{celda}">Alerta</th>
                                <th style="{celda} text-align: center;">Días sin seguimiento</th>
                            </tr>
                        </thead>
                        <tbody>{filas_html}</tbody>
                    </table>
                    {nota_restantes}
                    <p>Por favor, revisa el sistema y registra el seguimiento correspondiente para que los casos no queden desatendidos.</p>
                </div>
                <div style="padding: 20px; text-align: center; font-size: 12px; color: #6c757d; background-color: #f8f9fa;">
                    &copy; 2026 Universidad Francisco de Paula Santander - Alertas Tempranas
                </div>
            </div>
        </body>
        </html>
        """


def _enviar_internas(recordatorios_dest, resultados, errores):
    """Una notificación interna por caso (cada una enlaza su alerta en la bandeja)."""
    for r in recordatorios_dest:
        if r.canales.get('INTERNA') == 'exitoso':
            continue
        try:
            historial = NotificationService.enviar_interna(
                r.destinatario, r.alerta, f"Recordatorio: {_descripcion_caso(r)}", tipo='RECORDATORIO',
            )
            ok, error = historial.resultado == 'exitoso', historial.detalle_error
        except Exception as e:
            logger.error("Recordatorio %s: error en canal INTERNA: %s", r.id, e, exc_info=True)
            ok, error = False, str(e)
        resultados[r.id]['INTERNA'] = 'exitoso' if ok else 'fallido'
        if not ok:
            errores[r.id].append(f"INTERNA: {error}")


def _enviar_correo_resumen(destinatario, recordatorios_dest, resultados, errores):
    """Un solo correo con todos los casos cuyo canal EMAIL sigue pendiente o fallido."""
    para_correo = [r for r in recordatorios_dest if r.canales.get('EMAIL') != 'exitoso']
    if not para_correo:
        return False

    if not destinatario.correo:
        resultado, error = 'fallido', 'El destinatario no tiene correo registrado.'
    else:
        try:
            resultado, error = NotificationService.enviar_brevo(
                destinatario.correo, asunto_resumen(para_correo), generar_html_resumen(destinatario, para_correo),
            )
        except Exception as e:
            logger.error("Recordatorios: error al enviar correo a %s: %s", destinatario.id, e, exc_info=True)
            resultado, error = 'fallido', str(e)

    for r in para_correo:
        # Se registra en el historial de cada alerta incluida en el correo
        NotificationService.registrar_historial(
            r.alerta, destinatario.correo, destinatario.rol, 'EMAIL', resultado, error, tipo='RECORDATORIO',
        )
        resultados[r.id]['EMAIL'] = 'exitoso' if resultado == 'exitoso' else 'fallido'
        if resultado != 'exitoso':
            errores[r.id].append(f"EMAIL: {error}")
    return resultado == 'exitoso'


def _cerrar_intento(recordatorio, resultados, errores, ahora):
    """Registra el intento y actualiza el estado: ENVIADO (todos los canales ok),
    PENDIENTE (quedan reintentos), PARCIAL o FALLIDO (sin reintentos)."""
    error = '; '.join(errores)
    recordatorio.intentos += 1
    recordatorio.fecha_ultimo_intento = ahora
    recordatorio.canales = {**recordatorio.canales, **resultados}
    recordatorio.historial_intentos = recordatorio.historial_intentos + [{
        'intento': recordatorio.intentos,
        'fecha': ahora.isoformat(),
        'canales': resultados,
        'error': error[:1000] or None,
    }]
    recordatorio.ultimo_error = error[:2000] or None

    if all(recordatorio.canales.get(c) == 'exitoso' for c in CANALES):
        recordatorio.estado = 'ENVIADO'
        recordatorio.fecha_envio = ahora
    elif recordatorio.intentos < recordatorio.max_intentos:
        recordatorio.estado = 'PENDIENTE'
    elif any(recordatorio.canales.get(c) == 'exitoso' for c in CANALES):
        recordatorio.estado = 'PARCIAL'
        recordatorio.fecha_envio = ahora
    else:
        recordatorio.estado = 'FALLIDO'
    recordatorio.save()


def enviar_a_destinatario(destinatario, recordatorios_dest):
    """
    Envía los recordatorios de un destinatario: una notificación interna por caso
    y un único correo de resumen. Solo se repiten los canales que no fueron exitosos.
    Retorna True si se envió el correo de resumen.
    """
    ahora = timezone.now()
    resultados = {r.id: {} for r in recordatorios_dest}
    errores = {r.id: [] for r in recordatorios_dest}

    _enviar_internas(recordatorios_dest, resultados, errores)
    correo_enviado = _enviar_correo_resumen(destinatario, recordatorios_dest, resultados, errores)

    for r in recordatorios_dest:
        _cerrar_intento(r, resultados[r.id], errores[r.id], ahora)
    return correo_enviado


def _ya_recordado(caso, destinatario, config, ahora):
    """True si el destinatario ya tiene un recordatorio vigente para esta misma inactividad."""
    ultimo = (
        Recordatorio.objects.filter(destinatario=destinatario,
                                    **_filtro_caso(caso['tipo_caso'], caso['alerta'], caso['intervencion']))
        .exclude(estado='CANCELADO')
        .order_by('-fecha_creacion')
        .first()
    )
    if ultimo is None:
        return False
    if ultimo.estado == 'PENDIENTE':
        return True  # lo atiende la fase de reintentos
    misma_inactividad = ultimo.ultima_actividad >= caso['ultima_actividad']
    reciente = ultimo.fecha_creacion > ahora - timedelta(days=config.dias_entre_recordatorios)
    return misma_inactividad and reciente


def _pendientes_a_reintentar(resumen):
    """Revalida los PENDIENTES: cancela los que ya tienen seguimiento y retorna el resto."""
    a_enviar = []
    pendientes = Recordatorio.objects.filter(estado='PENDIENTE').select_related(
        'alerta__estudiante', 'alerta__regla', 'intervencion__usuario', 'destinatario'
    )
    for recordatorio in pendientes:
        try:
            sigue, motivo = caso_sigue_sin_seguimiento(recordatorio)
            if sigue and not recordatorio.destinatario.activo:
                sigue, motivo = False, 'El destinatario fue desactivado.'
            if not sigue:
                _cancelar(recordatorio, motivo)
                resumen['cancelados'] += 1
                continue
            a_enviar.append(recordatorio)
            resumen['reintentados'] += 1
        except Exception as e:
            logger.error("Recordatorio %s: error al revalidar: %s", recordatorio.id, e, exc_info=True)
            resumen['errores'] += 1
    return a_enviar


def _crear_nuevos(config, ahora, resumen):
    nuevos = []
    casos = detectar_casos_sin_seguimiento(config, ahora)
    resumen['casos_detectados'] = len(casos)
    for caso in casos:
        for destinatario in destinatarios_caso(caso, config):
            try:
                if _ya_recordado(caso, destinatario, config, ahora):
                    resumen['omitidos'] += 1
                    continue
                nuevos.append(Recordatorio.objects.create(
                    tipo_caso=caso['tipo_caso'],
                    alerta=caso['alerta'],
                    intervencion=caso['intervencion'],
                    destinatario=destinatario,
                    ultima_actividad=caso['ultima_actividad'],
                    dias_inactivo=caso['dias_inactivo'],
                    max_intentos=max(1, config.max_intentos),
                    canales={c: 'pendiente' for c in CANALES},
                ))
                resumen['creados'] += 1
            except Exception as e:
                logger.error("Recordatorios: error con caso %s alerta %s: %s",
                             caso['tipo_caso'], caso['alerta'].id, e, exc_info=True)
                resumen['errores'] += 1
    return nuevos


def _enviar_agrupados(a_enviar, resumen):
    por_destinatario = defaultdict(list)
    for r in a_enviar:
        por_destinatario[r.destinatario_id].append(r)

    for recordatorios_dest in por_destinatario.values():
        destinatario = recordatorios_dest[0].destinatario
        try:
            if enviar_a_destinatario(destinatario, recordatorios_dest):
                resumen['correos_enviados'] += 1
        except Exception as e:
            logger.error("Recordatorios: error al enviar a %s: %s", destinatario.id, e, exc_info=True)
            resumen['errores'] += len(recordatorios_dest)
            continue
        for r in recordatorios_dest:
            resumen[r.estado.lower()] += 1


def procesar_recordatorios(usuario=None, origen='PROGRAMADA', ahora=None):
    """
    1. Revalida los recordatorios PENDIENTES (cancela los que ya tienen seguimiento).
    2. Detecta casos sin seguimiento y crea los recordatorios nuevos.
    3. Envía todo agrupado por destinatario: un correo de resumen y una
       notificación interna por caso.
    Retorna un resumen con los totales.
    """
    config = ConfiguracionRecordatorio.obtener()
    if not _adquirir_bloqueo(config):
        raise RecordatoriosEnCurso('Ya hay un envío de recordatorios en curso.')
    try:
        ahora = ahora or timezone.now()
        resumen = {
            'activo': config.activo, 'casos_detectados': 0, 'creados': 0, 'reintentados': 0,
            'omitidos': 0, 'cancelados': 0, 'correos_enviados': 0, 'enviado': 0, 'pendiente': 0,
            'parcial': 0, 'fallido': 0, 'errores': 0,
        }
        if not config.activo:
            return resumen

        a_enviar = _pendientes_a_reintentar(resumen)
        a_enviar += _crear_nuevos(config, ahora, resumen)
        _enviar_agrupados(a_enviar, resumen)

        registrar_auditoria(
            usuario,
            'ENVIO_RECORDATORIOS',
            f"Recordatorios ({origen.lower()}): {resumen['casos_detectados']} casos sin seguimiento, "
            f"{resumen['creados']} nuevos, {resumen['reintentados']} reintentos, "
            f"{resumen['correos_enviados']} correos de resumen, "
            f"{resumen['enviado']} enviados, {resumen['pendiente']} pendientes de reintento, "
            f"{resumen['parcial']} parciales, {resumen['fallido']} fallidos, "
            f"{resumen['cancelados']} cancelados, {resumen['errores']} errores."
        )
        return resumen
    finally:
        _liberar_bloqueo(config)
