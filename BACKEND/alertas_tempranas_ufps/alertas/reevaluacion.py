"""
HU-29: Re-evaluación periódica del riesgo académico.

Recalcula indicadores y riesgo de los estudiantes con las reglas vigentes,
genera/actualiza/cierra alertas y registra cada ejecución en
EjecucionReevaluacion. No depende de una nueva importación de datos.

Puntos de entrada:
  - ejecutar_reevaluacion(): ejecución completa con reintentos (la usan el
    comando `reevaluar_riesgo` y los endpoints de reevaluacion_views).
  - reevaluar_estudiante(): re-evaluación de un solo estudiante.
"""
import logging
import time
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections, transaction
from django.db.models import Q
from django.utils import timezone

from academico.models import Estudiante
from alertas.evaluacion import actualizar_promedio
from alertas.models import Alerta, EjecucionReevaluacion, Regla, RiesgoEstudiante
from alertas.services import NotificationService
from usuarios.utils import registrar_auditoria

logger = logging.getLogger(__name__)

ESTADOS_ALERTA_ABIERTOS = ['activa', 'active', 'en_seguimiento', 'atendida']

# Tope de elementos guardados en las listas JSON de cada ejecución
MAX_DETALLE = 200


class ReevaluacionEnCurso(Exception):
    """Ya hay una ejecución EN_CURSO reciente; no se lanza otra en paralelo."""


class ErrorNoReintentable(Exception):
    """Error de configuración: reintentar no cambiaría el resultado."""


def estudiantes_evaluables():
    """Mismo criterio que la generación de alertas: excluye retirados, graduados y cancelados."""
    return Estudiante.objects.exclude(
        Q(estado_matricula__icontains='retirado') |
        Q(estado_matricula__icontains='graduado') |
        Q(estado_matricula__icontains='cancelado')
    )


def hay_ejecucion_en_curso():
    limite = timezone.now() - timedelta(hours=settings.REEVALUACION_BLOQUEO_HORAS)
    return EjecucionReevaluacion.objects.filter(estado='EN_CURSO', fecha_inicio__gte=limite).exists()


def recalcular_indicadores_estudiante(estudiante):
    """
    Recalcula el promedio (PPA ponderado por créditos) desde las notas registradas
    y lo persiste si cambió. Los indicadores por periodo (PPA acumulado, reprobadas,
    atraso) se recalculan en calcular_y_guardar_riesgo_por_periodos.
    """
    promedio = actualizar_promedio(estudiante)
    return {'promedio': float(promedio) if promedio is not None else None}


def reevaluar_estudiante(estudiante, reglas, solo_regla=None):
    """
    Re-evalúa un estudiante con las reglas activas:
      1. Recalcula indicadores y riesgo (por periodo + snapshot).
      2. Cierra alertas abiertas cuya regla ya no aplica o fue desactivada.
      3. Actualiza valor_causa/metadata de las alertas abiertas que siguen aplicando.
      4. Crea alertas nuevas (la regla de mayor prioridad por tipo) si no hay
         una alerta abierta de esa regla.
    Las alertas nuevas se notifican después de confirmar la transacción.

    solo_regla: si se pasa, solo se crean/actualizan/cierran alertas de esa regla
    (el riesgo se recalcula igual con todas las reglas activas).
    """
    from alertas.views.alert_generation_views import (
        calcular_y_guardar_riesgo_por_periodos,
        evaluar_reglas_estudiante,
    )

    reglas_por_id = {r.id: r for r in reglas}
    resultado = {
        'nivel_anterior': 'unknown', 'nivel_nuevo': 'unknown',
        'alertas_generadas': 0, 'alertas_actualizadas': 0, 'alertas_cerradas': 0,
    }
    nuevas = []

    with transaction.atomic():
        resultado['nivel_anterior'] = (
            RiesgoEstudiante.objects.filter(estudiante=estudiante)
            .values_list('nivel_riesgo', flat=True).first() or 'unknown'
        )

        recalcular_indicadores_estudiante(estudiante)
        resultado['nivel_nuevo'] = calcular_y_guardar_riesgo_por_periodos(estudiante, reglas)

        evaluacion = evaluar_reglas_estudiante(estudiante, reglas)

        abiertas = Alerta.objects.filter(estudiante=estudiante, estado__in=ESTADOS_ALERTA_ABIERTOS)
        if solo_regla is not None:
            abiertas = abiertas.filter(regla_id=solo_regla.id)
        reglas_con_alerta_abierta = set()
        for alerta in abiertas:
            aplica, val, metadata = evaluacion.get(alerta.regla_id, (False, None, None))
            if alerta.regla_id not in reglas_por_id or not aplica:
                alerta.estado = 'cerrada'
                alerta.save(update_fields=['estado'])
                resultado['alertas_cerradas'] += 1
            else:
                alerta.valor_causa = val
                alerta.metadata = metadata
                alerta.save(update_fields=['valor_causa', 'metadata'])
                resultado['alertas_actualizadas'] += 1
                reglas_con_alerta_abierta.add(alerta.regla_id)

        # Reglas ordenadas por -prioridad: la primera que aplica por tipo es la que genera alerta
        tipos_cubiertos = set()
        for r in reglas:
            aplica, val, metadata = evaluacion[r.id]
            if not aplica or r.tipo in tipos_cubiertos:
                continue
            tipos_cubiertos.add(r.tipo)
            if r.id in reglas_con_alerta_abierta:
                continue
            if solo_regla is not None and r.id != solo_regla.id:
                continue
            nuevas.append(Alerta.objects.create(
                estudiante=estudiante, regla=r, estado='activa',
                valor_causa=val, metadata=metadata,
            ))
            resultado['alertas_generadas'] += 1

    for alerta in nuevas:
        try:
            NotificationService.notificar_alerta(alerta)
        except Exception as e:
            # Un fallo de notificación no invalida la re-evaluación del estudiante
            logger.warning("No se pudo notificar la alerta %s: %s", alerta.id, e)

    return resultado


def _ejecutar_intento(origen, usuario, intento, codigos, reintento_de):
    ejecucion = EjecucionReevaluacion.objects.create(
        origen=origen, usuario=usuario, intento=intento, reintento_de=reintento_de,
    )
    errores = []
    cambios = []
    por_nivel = {'high': 0, 'medium': 0, 'low': 0, 'unknown': 0}

    try:
        close_old_connections()
        reglas = list(Regla.objects.filter(activo=True).order_by('-prioridad'))
        if not reglas:
            raise ErrorNoReintentable('No hay reglas activas configuradas.')

        qs = estudiantes_evaluables().order_by('codigo')
        if codigos is not None:
            qs = qs.filter(codigo__in=codigos)

        ejecucion.total_estudiantes = qs.count()
        ejecucion.alcance = {
            'tipo': 'COMPLETO' if codigos is None else 'PARCIAL',
            'criterio': 'Estudiantes excluyendo retirados, graduados y cancelados',
            'codigos': list(codigos)[:MAX_DETALLE] if codigos is not None else None,
            'reglas': [{'id': r.id, 'nombre': r.nombre, 'tipo': r.tipo, 'nivel': r.nivel} for r in reglas],
        }
        ejecucion.save(update_fields=['total_estudiantes', 'alcance'])

        for est in qs.iterator():
            try:
                res = reevaluar_estudiante(est, reglas)
            except Exception as e:
                logger.error("Re-evaluación: error con estudiante %s: %s", est.codigo, e, exc_info=True)
                errores.append({'codigo': est.codigo, 'error': str(e)[:500]})
                continue

            ejecucion.procesados += 1
            ejecucion.alertas_generadas += res['alertas_generadas']
            ejecucion.alertas_actualizadas += res['alertas_actualizadas']
            ejecucion.alertas_cerradas += res['alertas_cerradas']
            por_nivel[res['nivel_nuevo']] = por_nivel.get(res['nivel_nuevo'], 0) + 1
            if res['nivel_anterior'] != res['nivel_nuevo']:
                ejecucion.cambios_riesgo += 1
                if len(cambios) < MAX_DETALLE:
                    cambios.append({'codigo': est.codigo, 'de': res['nivel_anterior'], 'a': res['nivel_nuevo']})

        if not errores:
            ejecucion.estado = 'EXITOSA'
        elif ejecucion.procesados == 0:
            ejecucion.estado = 'FALLIDA'
            ejecucion.mensaje_error = 'Ningún estudiante pudo ser re-evaluado.'
        else:
            ejecucion.estado = 'PARCIAL'
    except ErrorNoReintentable as e:
        ejecucion.estado = 'FALLIDA'
        ejecucion.mensaje_error = str(e)
        ejecucion.alcance = {**ejecucion.alcance, 'reintentable': False}
    except Exception as e:
        logger.error("Re-evaluación: fallo general en intento %s: %s", intento, e, exc_info=True)
        ejecucion.estado = 'FALLIDA'
        ejecucion.mensaje_error = str(e)[:2000]

    ejecucion.fecha_fin = timezone.now()
    ejecucion.estudiantes_por_nivel = por_nivel
    ejecucion.detalle_cambios = cambios
    ejecucion.total_errores = len(errores)
    ejecucion.errores = errores[:MAX_DETALLE]
    # Los códigos fallidos completos se usan para el reintento aunque la lista guardada esté acotada
    ejecucion._codigos_fallidos = [e['codigo'] for e in errores]
    ejecucion.save()

    registrar_auditoria(
        usuario,
        'REEVALUACION_RIESGO',
        f"Re-evaluación {origen.lower()} #{ejecucion.id} (intento {intento}): {ejecucion.estado}. "
        f"Evaluados: {ejecucion.procesados}/{ejecucion.total_estudiantes}, "
        f"cambios de riesgo: {ejecucion.cambios_riesgo}, alertas nuevas: {ejecucion.alertas_generadas}, "
        f"cerradas: {ejecucion.alertas_cerradas}, errores: {ejecucion.total_errores}."
    )
    return ejecucion


def ejecutar_reevaluacion(origen='PROGRAMADA', usuario=None, codigos=None,
                          max_intentos=None, espera_segundos=None, dormir=time.sleep):
    """
    Ejecuta la re-evaluación con reintentos y espera exponencial.
      - FALLIDA (p. ej. se cayó la conexión a la BD): se reintenta el mismo alcance.
      - PARCIAL: se reintentan solo los estudiantes que fallaron.
      - Errores de configuración (sin reglas activas) no se reintentan.
    Retorna la lista de ejecuciones (una por intento).
    """
    if max_intentos is None:
        max_intentos = settings.REEVALUACION_MAX_INTENTOS
    if espera_segundos is None:
        espera_segundos = settings.REEVALUACION_ESPERA_SEGUNDOS
    max_intentos = max(1, max_intentos)

    if hay_ejecucion_en_curso():
        raise ReevaluacionEnCurso('Ya hay una re-evaluación en curso.')

    ejecuciones = []
    anterior = None
    for intento in range(1, max_intentos + 1):
        try:
            ejecucion = _ejecutar_intento(origen, usuario, intento, codigos, anterior)
        except Exception as e:
            # Ni siquiera se pudo registrar el intento (p. ej. BD inaccesible)
            logger.error("Re-evaluación: no se pudo registrar el intento %s: %s", intento, e, exc_info=True)
            if intento == max_intentos:
                raise
            dormir(espera_segundos * (2 ** (intento - 1)))
            continue
        ejecuciones.append(ejecucion)

        if ejecucion.estado == 'EXITOSA' or ejecucion.alcance.get('reintentable') is False:
            break
        if intento == max_intentos:
            break
        if ejecucion.estado == 'PARCIAL':
            codigos = ejecucion._codigos_fallidos

        espera = espera_segundos * (2 ** (intento - 1))
        logger.warning(
            "Re-evaluación #%s terminó %s; reintento %s/%s en %ss.",
            ejecucion.id, ejecucion.estado, intento + 1, max_intentos, espera,
        )
        dormir(espera)
        anterior = ejecucion

    return ejecuciones
