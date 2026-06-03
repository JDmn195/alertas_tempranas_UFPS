import json
import logging
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Q, Count, Avg
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404

from academico.models import Estudiante, Nota, Curso, Periodo
from alertas.models import Regla, Alerta, RiesgoEstudiante, RiesgoEstudiantePeriodo
from academico.views.student_views import calcular_nivel_riesgo
from alertas.services import NotificationService

from usuarios.decorators import requiere_rol
from usuarios.utils import registrar_auditoria

logger = logging.getLogger(__name__)


def _calcular_nivel_para_periodo(estudiante, periodo, reglas, semestre_en_periodo=None):
    """
    Calcula el nivel de riesgo de un estudiante usando solo las notas
    del periodo indicado como referencia para REPROBACION y ATRASO.
    Para PROMEDIO usa el PPA acumulado hasta ese periodo.

    semestre_en_periodo: semestre que cursaba el estudiante en ese periodo
    (posición ordinal desde su primer periodo con notas). Si no se pasa,
    se usa estudiante.semestre (snapshot actual).
    """
    from django.db.models import Avg as _Avg
    from academico.models import Materia as _Materia
    from academico.models import EquivalenciaMateria as _Equiv

    # Semestre de referencia para el cálculo de atraso
    semestre_ref = semestre_en_periodo if semestre_en_periodo is not None else estudiante.semestre

    # PPA acumulado hasta este periodo (inclusive)
    notas_hasta = Nota.objects.filter(
        estudiante=estudiante,
        periodo__anio__lte=periodo.anio
    ).exclude(
        periodo__anio=periodo.anio,
        periodo__semestre__gt=periodo.semestre
    ).exclude(definitiva__isnull=True)

    ppa_row = notas_hasta.aggregate(ppa=_Avg('definitiva'))
    ppa = float(ppa_row['ppa']) if ppa_row['ppa'] else None

    # Reprobadas acumuladas hasta este periodo
    reprobadas = notas_hasta.filter(definitiva__lt=3.0).count()

    # Materias aprobadas directamente
    aprobadas_materia_ids = set(
        notas_hasta.filter(definitiva__gte=3.0)
        .values_list('curso__materia_id', flat=True)
    )
    # Materias del pensum satisfechas por equivalencia:
    # si el estudiante aprobó una materia_equivalente, la materia_pensum se cuenta como aprobada
    equiv_satisfechas = _Equiv.objects.filter(
        materia_equivalente_id__in=aprobadas_materia_ids
    ).values_list('materia_pensum_id', flat=True)
    aprobadas_ids = aprobadas_materia_ids | set(equiv_satisfechas)

    # Atraso: materias obligatorias de semestres anteriores al semestre_ref sin aprobar
    atraso = _Materia.objects.filter(
        semestre__lt=semestre_ref
    ).exclude(codigo__in=aprobadas_ids).exclude(tipo__icontains='electiva').count()

    orden_niveles = {'high': 3, 'medium': 2, 'low': 1}
    nivel_actual = 'low'
    valor_max_nivel = 0
    reglas_aplicadas = []

    for regla in reglas:
        if ppa is None and regla.tipo == 'PROMEDIO':
            continue
        val = ppa if regla.tipo == 'PROMEDIO' else (reprobadas if regla.tipo == 'REPROBACION' else atraso)
        try:
            aplica = (
                (regla.operador == '<'  and val < float(regla.valor_umbral)) or
                (regla.operador == '>'  and val > float(regla.valor_umbral)) or
                (regla.operador == '<=' and val <= float(regla.valor_umbral)) or
                (regla.operador == '>=' and val >= float(regla.valor_umbral)) or
                (regla.operador == '==' and val == float(regla.valor_umbral))
            )
        except Exception:
            continue
        if aplica:
            if orden_niveles.get(regla.nivel, 0) > valor_max_nivel:
                nivel_actual = regla.nivel
                valor_max_nivel = orden_niveles[regla.nivel]
            reglas_aplicadas.append({'id': regla.id, 'nombre': regla.nombre, 'nivel': regla.nivel, 'valor': val})

    return nivel_actual, reglas_aplicadas, ppa


def calcular_y_guardar_riesgo_por_periodos(estudiante, reglas=None):
    """
    Para un estudiante, calcula y persiste RiesgoEstudiantePeriodo
    para cada periodo en el que tiene notas registradas.
    También actualiza RiesgoEstudiante (snapshot actual = último periodo).

    Si el estudiante no tiene notas pero sí tiene promedio registrado,
    se evalúa el riesgo directamente con las reglas de PROMEDIO para
    evitar que quede en 'unknown' al ser importado sin historial.

    Retorna el nivel del periodo más reciente (o calculado desde promedio).
    """
    if reglas is None:
        reglas = list(Regla.objects.filter(activo=True).order_by('-prioridad'))

    # Periodos en los que el estudiante tiene notas, ordenados cronológicamente
    periodos = (
        Periodo.objects
        .filter(nota__estudiante=estudiante)
        .distinct()
        .order_by('anio', 'semestre')
    )

    nivel_actual = 'unknown'
    reglas_actuales = []

    for idx, periodo in enumerate(periodos):
        # Semestre que cursaba el estudiante en este periodo:
        # el primer periodo con notas = semestre 1, el siguiente = 2, etc.
        semestre_en_periodo = idx + 1
        nivel, reglas_ap, _ = _calcular_nivel_para_periodo(
            estudiante, periodo, reglas, semestre_en_periodo=semestre_en_periodo
        )
        RiesgoEstudiantePeriodo.objects.update_or_create(
            estudiante=estudiante,
            periodo=periodo,
            defaults={'nivel_riesgo': nivel, 'reglas_aplicadas': reglas_ap}
        )
        nivel_actual = nivel
        reglas_actuales = reglas_ap

    # Si no hay notas pero el estudiante tiene promedio, evaluar solo reglas de PROMEDIO.
    # No evaluar REPROBACION ni ATRASO: sin notas registradas esos valores serían
    # espurios (0 reprobadas, pero N materias "no aprobadas" inflarían el atraso).
    if nivel_actual == 'unknown' and estudiante.promedio is not None:
        orden_niveles = {'high': 3, 'medium': 2, 'low': 1}
        nivel_prom = 'low'
        valor_max_prom = 0
        reglas_prom_aplicadas = []
        for regla in reglas:
            if regla.tipo != 'PROMEDIO':
                continue
            try:
                val = float(estudiante.promedio)
                umbral = float(regla.valor_umbral)
                aplica = (
                    (regla.operador == '<'  and val < umbral) or
                    (regla.operador == '>'  and val > umbral) or
                    (regla.operador == '<=' and val <= umbral) or
                    (regla.operador == '>=' and val >= umbral) or
                    (regla.operador == '==' and val == umbral)
                )
            except Exception:
                continue
            if aplica and orden_niveles.get(regla.nivel, 0) > valor_max_prom:
                nivel_prom = regla.nivel
                valor_max_prom = orden_niveles[regla.nivel]
                reglas_prom_aplicadas.append({
                    'id': regla.id, 'nombre': regla.nombre,
                    'nivel': regla.nivel, 'valor': float(estudiante.promedio)
                })
        # Solo asignar nivel distinto de 'unknown' si alguna regla aplicó;
        # si el promedio es bueno y no dispara ninguna regla, queda en 'low'
        # (hay suficientes datos para decir que no está en riesgo).
        nivel_actual = nivel_prom
        reglas_actuales = reglas_prom_aplicadas

    # Snapshot actual
    RiesgoEstudiante.objects.update_or_create(
        estudiante=estudiante,
        defaults={'nivel_riesgo': nivel_actual, 'reglas_aplicadas': reglas_actuales}
    )
    return nivel_actual


def _evaluar_regla_para_estudiante(est, r):
    """
    Evalúa si una regla aplica al estudiante dado su estado académico actual.
    Retorna (aplica: bool, val: float, metadata: dict).
    Respeta equivalencias de materias para el cálculo de ATRASO.
    """
    from academico.models import Materia, EquivalenciaMateria
    aplica = False
    val = 0
    metadata_regla = {}

    if r.tipo == 'PROMEDIO':
        val = float(est.promedio) if est.promedio else 0
        metadata_regla = {'promedio': val}
    elif r.tipo == 'REPROBACION':
        reprobadas_qs = Nota.objects.filter(
            estudiante=est, definitiva__lt=3.0
        ).select_related('curso__materia')
        val = reprobadas_qs.count()
        metadata_regla = {'materias': [n.curso.materia.nombre for n in reprobadas_qs]}
    elif r.tipo == 'ATRASO':
        if Nota.objects.filter(estudiante=est).exists():
            # Materias aprobadas directamente
            aprobadas_materia_ids = set(
                Nota.objects.filter(estudiante=est, definitiva__gte=3.0)
                .values_list('curso__materia_id', flat=True)
            )
            # Materias del pensum satisfechas por equivalencia
            equiv_satisfechas = EquivalenciaMateria.objects.filter(
                materia_equivalente_id__in=aprobadas_materia_ids
            ).values_list('materia_pensum_id', flat=True)
            aprobadas_ids = aprobadas_materia_ids | set(equiv_satisfechas)

            atrasadas_qs = Materia.objects.filter(
                semestre__lt=est.semestre
            ).exclude(codigo__in=aprobadas_ids).exclude(tipo__icontains='electiva')
            val = atrasadas_qs.count()
            metadata_regla = {
                'semestre_actual': est.semestre,
                'materias_atrasadas': [m.nombre for m in atrasadas_qs],
                'total_atrasadas': val
            }

    try:
        if r.operador == '<':  aplica = val < float(r.valor_umbral)
        elif r.operador == '>':  aplica = val > float(r.valor_umbral)
        elif r.operador == '<=': aplica = val <= float(r.valor_umbral)
        elif r.operador == '>=': aplica = val >= float(r.valor_umbral)
        elif r.operador == '==': aplica = val == float(r.valor_umbral)
    except Exception:
        pass

    return aplica, val, metadata_regla


def reprocesar_alertas_completas(estudiantes_qs=None, usuario=None, regla_especifica=None):
    """
    (Re)genera alertas y riesgos para los estudiantes indicados.

    Fix 3.3: si se pasa regla_especifica (Regla), solo genera/reevalúa alertas
    de esa regla, sin tocar las demás.

    Fix 3.4: no crea una alerta si ya existe una de la misma regla para el
    estudiante en cualquier estado (activa, en_seguimiento, atendida, cerrada).
    Así se evitan duplicados en generación manual.
    """
    reglas = list(Regla.objects.filter(activo=True).order_by('-prioridad'))
    if estudiantes_qs is None:
        estudiantes_qs = Estudiante.objects.exclude(
            Q(estado_matricula__icontains='retirado') |
            Q(estado_matricula__icontains='graduado') |
            Q(estado_matricula__icontains='cancelado')
        )

    # Si solo aplica a una regla específica, restringir la lista
    reglas_a_evaluar = [regla_especifica] if regla_especifica else reglas

    nuevas_alertas = 0
    actualizados = 0
    por_nivel = {'high': 0, 'medium': 0, 'low': 0, 'unknown': 0}

    with transaction.atomic():
        for est in estudiantes_qs:
            # 0. Limpieza solo aplica en modo completo (no por regla específica)
            if not regla_especifica:
                Alerta.objects.filter(
                    estudiante=est,
                    estado__in=['activa', 'active']
                ).annotate(n_int=Count('intervencion')).filter(n_int=0).delete()

            # 1. Calcular y persistir riesgo por periodo + snapshot actual
            nivel = calcular_y_guardar_riesgo_por_periodos(est, reglas)
            por_nivel[nivel] = por_nivel.get(nivel, 0) + 1
            actualizados += 1

            # 2. Evaluar reglas para generar alertas
            reglas_por_tipo = {}
            for r in reglas_a_evaluar:
                aplica, val, metadata_regla = _evaluar_regla_para_estudiante(est, r)
                if aplica and r.tipo not in reglas_por_tipo:
                    reglas_por_tipo[r.tipo] = {
                        'id': r.id, 'nombre': r.nombre, 'nivel': r.nivel,
                        'valor': val, 'metadata': metadata_regla
                    }

            # 3. Generar alertas — Fix 3.4: omitir si ya existe alerta de esa regla
            for r_app in list(reglas_por_tipo.values()):
                ya_existe = Alerta.objects.filter(
                    estudiante=est,
                    regla_id=r_app['id']
                ).exists()
                if ya_existe:
                    continue  # No duplicar sin importar el estado

                nueva_alerta = Alerta.objects.create(
                    estudiante=est,
                    regla_id=r_app['id'],
                    estado='activa',
                    valor_causa=r_app['valor'],
                    metadata=r_app['metadata']
                )
                NotificationService.notificar_alerta(nueva_alerta)
                nuevas_alertas += 1

    resultado = {
        'total_evaluados': estudiantes_qs.count(),
        'actualizados': actualizados,
        'nuevas_alertas': nuevas_alertas,
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
        f"nuevas alertas: {resultado['nuevas_alertas']}."
    )

    return resultado


def reevaluar_alertas_activas(usuario=None):
    """
    Fix 3.5/3.7: Recorre todas las alertas activas/en_seguimiento/atendidas y
    verifica si el estudiante sigue cumpliendo la regla.
    Si ya no la cumple → cierra la alerta automáticamente.
    Retorna un resumen del proceso.
    """
    estados_abiertos = ['activa', 'active', 'en_seguimiento', 'atendida']
    alertas = (
        Alerta.objects
        .filter(estado__in=estados_abiertos)
        .select_related('estudiante', 'regla', 'estudiante__riesgo')
    )

    cerradas = 0
    evaluadas = 0

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

            aplica, val, metadata_regla = _evaluar_regla_para_estudiante(est, r)
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
        from django.db.models import Avg as _Avg

        # 1. Recalcular promedio desde notas reales si tiene notas
        notas_qs = Nota.objects.filter(estudiante=estudiante).exclude(definitiva__isnull=True)
        if notas_qs.exists():
            ppa = notas_qs.aggregate(ppa=_Avg('definitiva'))['ppa']
            if ppa is not None:
                Estudiante.objects.filter(codigo=codigo).update(promedio=round(ppa, 2))
                estudiante.refresh_from_db()

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
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


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
        return JsonResponse({'error': str(e)}, status=500)


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
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


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

        reglas = list(Regla.objects.filter(activo=True).order_by('-prioridad'))
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
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)

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
    alerta.estado = 'cerrada'
    alerta.save()
    
    # Registrar auditoría de cierre de alerta
    registrar_auditoria(
        request.usuario,
        'CERRAR_ALERTA',
        f"Alerta ID {alerta.id} de tipo '{alerta.regla.nombre}' para estudiante {alerta.estudiante.codigo} fue cerrada."
    )
    
    return JsonResponse({'mensaje': 'Alerta cerrada correctamente'})

