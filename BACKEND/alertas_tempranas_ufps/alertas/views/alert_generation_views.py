import logging
from django.http import JsonResponse
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404

from academico.models import Estudiante, Nota, Curso, Periodo
from alertas.alertas_inasistencia import factor_inasistencia, obtener_regla_inasistencia, periodos_con_asistencia
from alertas.evaluacion import ORDEN_NIVELES, actualizar_promedio, calcular_indicadores, evaluar_regla, nivel_de_riesgo
from alertas.permisos import denegar_acceso_alerta, puede_acceder_alerta
from alertas.models import TIPOS_FUERA_DEL_MOTOR_GENERAL, Regla, Alerta, RiesgoEstudiante, RiesgoEstudiantePeriodo

from usuarios.decorators import requiere_rol
from usuarios.utils import registrar_auditoria

logger = logging.getLogger(__name__)


def _calcular_nivel_para_periodo(estudiante, periodo, reglas, semestre_en_periodo=None, regla_inasistencia=None):
    """
    Nivel de riesgo del estudiante con sus notas hasta el periodo indicado.

    semestre_en_periodo: semestre que cursaba el estudiante en ese periodo
    (posición ordinal desde su primer periodo con notas). Si no se pasa,
    se usa estudiante.semestre (snapshot actual).

    HU-36: si se pasa regla_inasistencia, cuenta como una regla aplicable más cuando
    el estudiante supera el umbral de inasistencia en al menos un curso del periodo.
    """
    indicadores = calcular_indicadores(estudiante, periodo=periodo, semestre_ref=semestre_en_periodo)
    nivel, reglas_aplicadas = nivel_de_riesgo(reglas, indicadores)
    if regla_inasistencia is not None:
        factor = factor_inasistencia(estudiante, periodo, regla_inasistencia)
        if factor:
            reglas_aplicadas.append(factor)
            if ORDEN_NIVELES.get(factor['nivel'], 0) > ORDEN_NIVELES.get(nivel, 0):
                nivel = factor['nivel']
    return nivel, reglas_aplicadas, indicadores['ppa']


def calcular_y_guardar_riesgo_por_periodos(estudiante, reglas=None):
    """
    Para un estudiante, calcula y persiste RiesgoEstudiantePeriodo
    para cada periodo en el que tiene notas registradas.
    También actualiza RiesgoEstudiante (snapshot actual = último periodo).

    Si el estudiante no tiene notas se evalúa con su promedio importado
    (solo aplican las reglas de PROMEDIO; sin promedio queda en 'unknown').

    Retorna el nivel del periodo más reciente (o calculado desde promedio).
    """
    if reglas is None:
        reglas = list(Regla.objects.filter(activo=True).exclude(tipo__in=TIPOS_FUERA_DEL_MOTOR_GENERAL).order_by('-prioridad'))

    # Periodos en los que el estudiante tiene notas, ordenados cronológicamente
    periodos = (
        Periodo.objects
        .filter(nota__estudiante=estudiante)
        .distinct()
        .order_by('anio', 'semestre')
    )

    nivel_actual = None
    reglas_actuales = []

    # HU-36: la inasistencia es un factor más en los periodos con asistencia registrada
    regla_inasistencia = obtener_regla_inasistencia()
    con_asistencia = periodos_con_asistencia(estudiante) if regla_inasistencia else set()

    for idx, periodo in enumerate(periodos):
        # Semestre que cursaba el estudiante en este periodo:
        # el primer periodo con notas = semestre 1, el siguiente = 2, etc.
        nivel, reglas_ap, _ = _calcular_nivel_para_periodo(
            estudiante, periodo, reglas, semestre_en_periodo=idx + 1,
            regla_inasistencia=regla_inasistencia if periodo.pk in con_asistencia else None,
        )
        RiesgoEstudiantePeriodo.objects.update_or_create(
            estudiante=estudiante,
            periodo=periodo,
            defaults={'nivel_riesgo': nivel, 'reglas_aplicadas': reglas_ap}
        )
        nivel_actual = nivel
        reglas_actuales = reglas_ap

    if nivel_actual is None:
        nivel_actual, reglas_actuales = nivel_de_riesgo(reglas, calcular_indicadores(estudiante))

    # Snapshot actual
    RiesgoEstudiante.objects.update_or_create(
        estudiante=estudiante,
        defaults={'nivel_riesgo': nivel_actual, 'reglas_aplicadas': reglas_actuales}
    )
    return nivel_actual


def evaluar_reglas_estudiante(est, reglas):
    """
    Evalúa las reglas con el estado académico actual del estudiante.
    Retorna {regla.id: (aplica, valor, metadata)}.
    """
    indicadores = calcular_indicadores(est)
    return {r.id: evaluar_regla(r, indicadores) for r in reglas}


def reprocesar_alertas_completas(estudiantes_qs=None, usuario=None, regla_especifica=None):
    """
    (Re)genera riesgo y alertas de los estudiantes indicados (por defecto, todos
    los evaluables) con la misma lógica de la re-evaluación periódica (HU-29):

    - Las alertas abiertas que siguen aplicando se conservan (solo se actualiza
      su valor): no se recrean ni se vuelven a notificar.
    - Las abiertas cuya regla ya no aplica se cierran.
    - Si no hay una alerta abierta de la regla, se crea una nueva, aunque haya
      una cerrada de antes (el estudiante recayó).
    - Cada estudiante va en su propia transacción y los correos salen después
      de confirmarla.

    Fix 3.3: si se pasa regla_especifica (Regla), solo crea/actualiza/cierra
    alertas de esa regla, sin tocar las demás.
    """
    from alertas.reevaluacion import estudiantes_evaluables, reevaluar_estudiante

    reglas = list(Regla.objects.filter(activo=True).exclude(tipo__in=TIPOS_FUERA_DEL_MOTOR_GENERAL).order_by('-prioridad'))
    if estudiantes_qs is None:
        estudiantes_qs = estudiantes_evaluables()

    evaluados = 0
    nuevas_alertas = 0
    errores = 0
    por_nivel = {'high': 0, 'medium': 0, 'low': 0, 'unknown': 0}

    for est in estudiantes_qs:
        evaluados += 1
        try:
            res = reevaluar_estudiante(est, reglas, solo_regla=regla_especifica)
        except Exception as e:
            # Un estudiante con datos problemáticos no detiene a los demás
            logger.error("Error al generar alertas del estudiante %s: %s", est.codigo, e, exc_info=True)
            errores += 1
            continue
        por_nivel[res['nivel_nuevo']] = por_nivel.get(res['nivel_nuevo'], 0) + 1
        nuevas_alertas += res['alertas_generadas']

    resultado = {
        'total_evaluados': evaluados,
        'actualizados': evaluados - errores,
        'nuevas_alertas': nuevas_alertas,
        'errores': errores,
        'estudiantes_por_nivel': por_nivel
    }

    if usuario:
        origen = f"usuario '{usuario.nombre}' (ejecución manual)"
    else:
        origen = "Sistema (disparado automáticamente por importación de datos)"

    registrar_auditoria(
        usuario,
        'GENERAR_ALERTAS',
        f"Generación de alertas ejecutada por {origen}. "
        f"Evaluados: {resultado['total_evaluados']}, "
        f"nuevas alertas: {resultado['nuevas_alertas']}, errores: {errores}."
    )

    return resultado


def reevaluar_alertas_activas(usuario=None):
    """
    Fix 3.5/3.7: Recorre todas las alertas activas/en_seguimiento/atendidas y
    verifica si el estudiante sigue cumpliendo la regla.
    Si ya no la cumple → cierra la alerta automáticamente.
    Excluye alertas de reglas CORTE e INASISTENCIA (tienen su propio ciclo de vida).
    Retorna un resumen del proceso.
    """
    estados_abiertos = ['activa', 'active', 'en_seguimiento', 'atendida']
    alertas = (
        Alerta.objects
        .filter(estado__in=estados_abiertos)
        .exclude(regla__tipo__in=TIPOS_FUERA_DEL_MOTOR_GENERAL)
        .select_related('estudiante', 'regla', 'estudiante__riesgo')
    )

    cerradas = 0
    evaluadas = 0
    indicadores_por_estudiante = {}

    with transaction.atomic():
        for alerta in alertas:
            est = alerta.estudiante
            r = alerta.regla
            if not r or not r.activo:
                # Regla desactivada → cerrar la alerta
                alerta.estado = 'cerrada'
                alerta.save(update_fields=['estado'])
                cerradas += 1
                evaluadas += 1
                continue

            if est.pk not in indicadores_por_estudiante:
                indicadores_por_estudiante[est.pk] = calcular_indicadores(est)
            aplica, val, metadata_regla = evaluar_regla(r, indicadores_por_estudiante[est.pk])
            evaluadas += 1

            if not aplica:
                # El estudiante mejoró: ya no cumple la condición → cerrar alerta
                alerta.estado = 'cerrada'
                alerta.save(update_fields=['estado'])
                cerradas += 1
            else:
                # Actualizar el valor_causa y metadata con los datos actuales
                alerta.valor_causa = val
                alerta.metadata = metadata_regla
                alerta.save(update_fields=['valor_causa', 'metadata'])

    registrar_auditoria(
        usuario,
        'REEVALUAR_ALERTAS',
        f"Reevaluación de alertas: {evaluadas} evaluadas, {cerradas} cerradas automáticamente."
    )

    return {'evaluadas': evaluadas, 'cerradas_automaticamente': cerradas}

@csrf_exempt
@require_http_methods(["POST"])
@requiere_rol(['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR', 'DIRECTOR'])
def recalcular_riesgo_estudiante(request, codigo):
    """
    POST /api/alertas/estudiantes/<codigo>/recalcular/
    Recalcula el promedio desde las notas reales, luego recalcula el riesgo
    por periodo y el snapshot de RiesgoEstudiante para un estudiante específico.
    """
    try:
        estudiante = Estudiante.objects.get(codigo=codigo)
    except Estudiante.DoesNotExist:
        return JsonResponse({'error': f'Estudiante {codigo} no encontrado'}, status=404)

    try:
        # 1. Recalcular promedio (PPA) desde notas reales si tiene notas
        actualizar_promedio(estudiante)

        # 2. Recalcular riesgo por periodo + snapshot
        nivel = calcular_y_guardar_riesgo_por_periodos(estudiante)

        registrar_auditoria(
            request.usuario,
            'RECALCULAR_RIESGO',
            f"Recálculo manual de riesgo para estudiante {codigo}. Nuevo nivel: {nivel}."
        )

        return JsonResponse({
            'mensaje': 'Riesgo recalculado correctamente',
            'codigo': codigo,
            'nivel_riesgo': nivel,
            'promedio': float(estudiante.promedio) if estudiante.promedio is not None else None,
        })
    except Exception:
        logger.exception("Error al recalcular el riesgo del estudiante %s", codigo)
        return JsonResponse({'error': 'Error al recalcular el riesgo.'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@requiere_rol(['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR', 'DIRECTOR'])
def generar_alertas(request):
    """
    POST /api/alertas/generar/
    """
    try:
        resultado = reprocesar_alertas_completas(usuario=request.usuario)

        return JsonResponse({
            'mensaje': 'Proceso de generación completado',
            **resultado
        })
    except Exception as e:
        logger.error("Error inesperado en generar_alertas: %s", e, exc_info=True)
        return JsonResponse({'error': 'Error al generar las alertas.'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@requiere_rol(['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR', 'DIRECTOR'])
def reevaluar_alertas(request):
    """
    POST /api/alertas/reevaluar/
    Fix 3.5/3.6/3.7: Reevalúa todas las alertas abiertas.
    Las que ya no cumplen la condición se cierran automáticamente.
    """
    try:
        resultado = reevaluar_alertas_activas(usuario=request.usuario)
        return JsonResponse({
            'mensaje': f"Reevaluación completada: {resultado['evaluadas']} evaluadas, "
                       f"{resultado['cerradas_automaticamente']} cerradas automáticamente.",
            **resultado
        })
    except Exception:
        logger.exception("Error al reevaluar las alertas activas")
        return JsonResponse({'error': 'Error al reevaluar las alertas.'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@requiere_rol(['ADMINISTRADOR'])
def migrar_riesgo_periodos(request):
    """
    POST /api/alertas/migrar-riesgo-periodos/
    Ejecuta la migración de datos de RiesgoEstudiante → RiesgoEstudiantePeriodo.
    Útil para entornos donde ya había datos antes de la nueva tabla.
    Solo accesible por ADMINISTRADOR.
    """
    try:
        solo_vacios = request.GET.get('solo_vacios', 'true').lower() != 'false'

        reglas = list(Regla.objects.filter(activo=True).exclude(tipo__in=TIPOS_FUERA_DEL_MOTOR_GENERAL).order_by('-prioridad'))
        if not reglas:
            return JsonResponse({'error': 'No hay reglas activas configuradas.'}, status=400)

        from academico.models import Periodo as _Periodo

        estudiantes_qs = Estudiante.objects.all()
        if solo_vacios:
            con_periodo = RiesgoEstudiantePeriodo.objects.values_list(
                'estudiante_id', flat=True
            ).distinct()
            estudiantes_qs = estudiantes_qs.exclude(codigo__in=con_periodo)

        total = estudiantes_qs.count()
        procesados = 0
        periodos_creados = 0
        errores_lista = []

        for estudiante in estudiantes_qs:
            try:
                tiene_notas = Nota.objects.filter(estudiante=estudiante).exists()
                if tiene_notas:
                    antes = RiesgoEstudiantePeriodo.objects.filter(
                        estudiante=estudiante
                    ).count()
                    calcular_y_guardar_riesgo_por_periodos(estudiante, reglas=reglas)
                    despues = RiesgoEstudiantePeriodo.objects.filter(
                        estudiante=estudiante
                    ).count()
                    periodos_creados += (despues - antes)
                else:
                    try:
                        snapshot = RiesgoEstudiante.objects.get(estudiante=estudiante)
                        periodo_reciente = _Periodo.objects.order_by(
                            '-anio', '-semestre'
                        ).first()
                        if periodo_reciente:
                            _, created = RiesgoEstudiantePeriodo.objects.update_or_create(
                                estudiante=estudiante,
                                periodo=periodo_reciente,
                                defaults={
                                    'nivel_riesgo': snapshot.nivel_riesgo,
                                    'reglas_aplicadas': snapshot.reglas_aplicadas,
                                }
                            )
                            if created:
                                periodos_creados += 1
                    except RiesgoEstudiante.DoesNotExist:
                        pass
                procesados += 1
            except Exception as e:
                errores_lista.append({'codigo': estudiante.codigo, 'error': str(e)})

        registrar_auditoria(
            request.usuario,
            'MIGRAR_RIESGO_PERIODOS',
            f"Migración de riesgo por periodos: {procesados}/{total} procesados, "
            f"{periodos_creados} registros creados."
        )

        return JsonResponse({
            'mensaje': f'Migración completada: {procesados}/{total} estudiantes procesados, '
                       f'{periodos_creados} registros de periodo creados.',
            'total': total,
            'procesados': procesados,
            'periodos_creados': periodos_creados,
            'errores': errores_lista[:20],  # máximo 20 errores en la respuesta
        })
    except Exception:
        logger.exception("Error al migrar el riesgo por periodos")
        return JsonResponse({'error': 'Error al migrar el riesgo por periodos.'}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@requiere_rol(['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR', 'DIRECTOR'])
def listar_alertas(request):
    """
    GET /api/alertas/
    Fix 3.1: soporta búsqueda por nombre del estudiante (param: search).
    Fix 3.2: ordena por nivel de riesgo descendente (high > medium > low).
    """
    usuario = request.usuario
    estado = request.GET.get('estado', 'activa')
    tipo_regla = request.GET.get('tipo_regla')
    search = request.GET.get('search', '').strip()  # 3.1
    
    qs = Alerta.objects.select_related('estudiante', 'regla').order_by('-fecha_generacion')
    total_qs = Alerta.objects.all()
    
    if usuario.rol == 'DOCENTE':
        try:
            docente = usuario.docente
            ids_cursos = Curso.objects.filter(docente=docente).values_list('id', flat=True)
            estudiantes_ids = Nota.objects.filter(curso__in=ids_cursos).values_list('estudiante_id', flat=True).distinct()
            qs = qs.filter(estudiante_id__in=estudiantes_ids)
            total_qs = total_qs.filter(estudiante_id__in=estudiantes_ids)
        except Exception:
            qs = qs.none()
            total_qs = total_qs.none()
            
    if estado:
        mapping = {
            'activa': ['activa', 'active'],
            'en_seguimiento': ['en_seguimiento'],
            'atendida': ['atendida'],
            'cerrada': ['cerrada', 'closed'],
        }
        target_states = mapping.get(estado.lower(), [estado])
        qs = qs.filter(estado__in=target_states)
        
    if tipo_regla and tipo_regla != 'all':
        qs = qs.filter(regla__tipo=tipo_regla)

    # Fix 3.1: filtrar por nombre del estudiante
    if search:
        qs = qs.filter(estudiante__nombre__icontains=search)
        
    conteos = {
        'activa': total_qs.filter(estado__in=['activa', 'active']).count(),
        'en_seguimiento': total_qs.filter(estado='en_seguimiento').count(),
        'atendida': total_qs.filter(estado='atendida').count(),
        'cerrada': total_qs.filter(estado__in=['cerrada', 'closed']).count(),
    }

    # Cargar el nivel de riesgo actual de cada estudiante en una sola query
    # para ordenar las alertas por riesgo del estudiante (high > medium > low > unknown)
    estudiante_ids = qs.values_list('estudiante_id', flat=True).distinct()
    riesgo_map = {
        r.estudiante_id: r.nivel_riesgo
        for r in RiesgoEstudiante.objects.filter(estudiante_id__in=estudiante_ids)
    }

    ORDEN_RIESGO_EST = {'high': 0, 'medium': 1, 'low': 2, 'unknown': 3}
    ORDEN_NIVEL_REGLA = {'high': 0, 'medium': 1, 'low': 2}

    data = []
    for a in qs:
        nivel_est = riesgo_map.get(a.estudiante_id, 'unknown')
        data.append({
            'id': a.id,
            'studentName': a.estudiante.nombre,
            'studentCode': a.estudiante.codigo,
            'riskLevel': a.regla.nivel,
            'studentRiskLevel': nivel_est,
            'alertType': a.regla.nombre,
            'generatedDate': a.fecha_generacion.strftime('%Y-%m-%d'),
            'status': a.estado,
            'tipo_regla': a.regla.tipo,
            'valor_causa': float(a.valor_causa) if a.valor_causa else None,
            'metadata': a.metadata,
            '_ord_est': ORDEN_RIESGO_EST.get(nivel_est, 3),
            '_ord_regla': ORDEN_NIVEL_REGLA.get(a.regla.nivel, 3),
        })

    # Ordenar: primero por riesgo del estudiante, luego por nivel de la alerta, luego fecha más reciente
    data.sort(key=lambda x: (x['_ord_est'], x['_ord_regla'], x['generatedDate']))
    for item in data:
        del item['_ord_est']
        del item['_ord_regla']
        
    return JsonResponse({
        'alertas': data,
        'conteos': conteos
    }, safe=False)

@csrf_exempt
@require_http_methods(["POST"])
@requiere_rol(['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR', 'DIRECTOR'])
def cerrar_alerta(request, alerta_id):
    """
    POST /api/alertas/<id>/cerrar/
    Cierra una alerta directamente.
    """
    alerta = get_object_or_404(Alerta, id=alerta_id)
    if not puede_acceder_alerta(request.usuario, alerta):
        return denegar_acceso_alerta()
    alerta.estado = 'cerrada'
    alerta.save()
    
    # Registrar auditoría de cierre de alerta
    registrar_auditoria(
        request.usuario,
        'CERRAR_ALERTA',
        f"Alerta ID {alerta.id} de tipo '{alerta.regla.nombre}' para estudiante {alerta.estudiante.codigo} fue cerrada."
    )
    
    return JsonResponse({'mensaje': 'Alerta cerrada correctamente'})


@csrf_exempt
@require_http_methods(["POST"])
@requiere_rol(['ADMINISTRADOR', 'DIRECTOR'])
def evaluar_cortes(request):
    """
    POST /api/alertas/corte/evaluar/
    Dispara manualmente la evaluación de alertas por corte para el periodo actual.
    """
    from alertas.tareas import ejecutar_en_segundo_plano
    from alertas.alertas_corte import evaluar_cortes_periodo_actual

    ejecutar_en_segundo_plano(evaluar_cortes_periodo_actual, request.usuario)
    registrar_auditoria(
        request.usuario,
        'GENERAR_ALERTAS',
        "Evaluación manual de alertas por corte disparada para el periodo actual."
    )
    return JsonResponse({
        'mensaje': 'Evaluación de alertas por corte iniciada. Los resultados estarán disponibles en breve.'
    })

