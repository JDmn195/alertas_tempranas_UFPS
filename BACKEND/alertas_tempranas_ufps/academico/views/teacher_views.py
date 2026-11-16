from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.db.models import Count, Avg, Q

from academico.models import Curso, Nota, Periodo, Estudiante, Materia
from alertas.models import alertas_abiertas, Alerta, RiesgoEstudiante, RiesgoEstudiantePeriodo
from alertas.riesgo_actual import ultimo_riesgo_por_estudiante
from usuarios.decorators import requiere_rol
from academico.asistencia import (
    calcular_inasistencia_curso, calcular_inasistencia_cursos, cerca_umbral, numero_o_none,
    obtener_umbral_general, obtener_umbral_inasistencia, obtener_umbrales_inasistencia, supera_umbral,
)
from academico.services.asistencia import periodo_actual


def _inasistencia_sobre_umbral(inasistencia_curso, umbral, origen):
    """HU-35: conteo de estudiantes sobre el umbral del curso; null si no hay umbral."""
    if umbral is None:
        sobre_umbral = cerca = None
    else:
        sobre_umbral = sum(
            1 for datos in inasistencia_curso.values() if supera_umbral(datos['porcentaje'], umbral)
        )
        cerca = sum(1 for datos in inasistencia_curso.values() if cerca_umbral(datos['porcentaje'], umbral))
    return {
        'inasistencia_sobre_umbral':  sobre_umbral,
        'inasistencia_cerca_umbral':  cerca,
        'umbral_inasistencia':        numero_o_none(umbral),
        'origen_umbral_inasistencia': origen,
    }


@csrf_exempt
@require_GET
@requiere_rol(['DOCENTE'])
def teacher_dashboard(request):
    """
    GET /api/academico/teacher/dashboard/

    Fix 6.2: Reemplaza N+1 queries por aggregations SQL.
    Fix 6.3: Incluye total_alertas_activas en la respuesta.
    Fix 6.4: Añade indicadores enriquecidos.
    """
    usuario = request.usuario

    try:
        docente = usuario.docente
    except Exception:
        return JsonResponse({'error': 'El usuario no tiene perfil de docente.'}, status=404)

    # ── Cursos del docente ────────────────────────────────────────────────────
    cursos_qs = Curso.objects.filter(docente=docente).select_related('materia')
    ids_cursos = list(cursos_qs.values_list('id', flat=True))

    # ── IDs únicos de todos los estudiantes de este docente (histórico) ───────
    # SDAT-303: subconsulta en vez de pasar miles de códigos como literales en cada consulta
    estudiantes_docente = Nota.objects.filter(curso__in=ids_cursos).values('estudiante_id')
    todos_estudiantes_ids = list(estudiantes_docente.distinct().values_list('estudiante_id', flat=True))

    # SDAT-334: matrícula, reprobación y promedio del panel son del periodo más reciente,
    # no la suma de todos los periodos históricos.
    periodo_vigente = periodo_actual()
    notas_vigentes = Nota.objects.filter(curso__in=ids_cursos)
    if periodo_vigente:
        notas_vigentes = notas_vigentes.filter(periodo=periodo_vigente)

    # ── Fix 6.2: Stats por curso en UNA sola query SQL ────────────────────────
    stats_curso = (
        notas_vigentes
        .values('curso_id')
        .annotate(
            total_notas=Count('id'),
            reprobados=Count('id', filter=Q(definitiva__lt=3.0, definitiva__isnull=False)),
            promedio_curso=Avg('definitiva'),
        )
    )
    stats_map = {row['curso_id']: row for row in stats_curso}

    # ── En riesgo por curso: una query ────────────────────────────────────────
    # Obtener el RiesgoEstudiantePeriodo más reciente por estudiante
    from django.db.models import Subquery, OuterRef
    # SDAT-303: un solo recorrido del último riesgo (antes eran 4 subconsultas correlacionadas)
    riesgo_ultimo = ultimo_riesgo_por_estudiante(estudiantes_docente)
    en_riesgo_ids = {est for est, nivel in riesgo_ultimo.items() if nivel in ('high', 'medium')}
    # SDAT-303: estudiantes del periodo vigente por curso en una consulta (antes una por curso)
    estudiantes_por_curso = {}
    for curso_id, est_id in notas_vigentes.values_list('curso_id', 'estudiante_id'):
        estudiantes_por_curso.setdefault(curso_id, set()).add(est_id)

    # ── HU-34: inasistencia del periodo más reciente, una consulta para todos los cursos ──
    periodo_asistencia = periodo_actual()
    inasistencia_cursos = (
        calcular_inasistencia_cursos(ids_cursos, periodo_asistencia) if periodo_asistencia else {}
    )
    # HU-35: umbral efectivo de cada curso (propio o general)
    umbrales = obtener_umbrales_inasistencia(cursos_qs)

    # ── Construir lista de cursos ─────────────────────────────────────────────
    cursos_data = []
    for curso in cursos_qs:
        s = stats_map.get(curso.id)
        if s:
            matriculados = s['total_notas']
            reprobados = s['reprobados']
            tasa = round(reprobados / matriculados * 100, 1) if matriculados > 0 else 0.0
            estado = 'CRÍTICO' if tasa >= 30 else 'EN OBSERVACIÓN' if tasa >= 15 else 'ESTABLE'
            promedio_c = round(float(s['promedio_curso']), 2) if s['promedio_curso'] else None
            # Estudiantes de este curso que están en riesgo
            en_riesgo = len(estudiantes_por_curso.get(curso.id, set()) & en_riesgo_ids)
        else:
            matriculados = 0
            reprobados = 0
            tasa = 0.0
            estado = 'SIN DATOS'
            promedio_c = None
            en_riesgo = 0

        cursos_data.append({
            'curso_id':     curso.id,
            'materia':      curso.materia.nombre,
            'codigo':       curso.materia.codigo,
            'grupo':        curso.grupo,
            'matriculados': matriculados,
            'reprobados':   reprobados,
            'tasa_reprobacion': tasa,
            'promedio_curso': promedio_c,
            'en_riesgo':    en_riesgo,
            'estado':       estado,
            **_inasistencia_sobre_umbral(inasistencia_cursos.get(curso.id, {}), *umbrales[curso.id]),
        })

    total_en_riesgo = len(
        set(todos_estudiantes_ids) & en_riesgo_ids
    )

    # ── Fix 6.3: Total alertas activas de los estudiantes del docente ─────────

    # ── Fix 6.4: Indicadores adicionales ─────────────────────────────────────

    # 1. Promedio general de todos sus estudiantes
    # SDAT-303: promedio, total y aprobadas en una sola agregación (antes 3 consultas)
    prom_result = (
        Nota.objects
        .filter(curso__in=ids_cursos)
        .exclude(definitiva__isnull=True)
        .aggregate(
            ppa=Avg('definitiva'),
            total=Count('id'),
            aprobadas=Count('id', filter=Q(definitiva__gte=3.0)),
        )
    )
    promedio_general = round(float(prom_result['ppa']), 2) if prom_result['ppa'] else None

    # 2. Total estudiantes únicos
    total_estudiantes = len(todos_estudiantes_ids)

    # 3. Tasa global de aprobación
    total_notas = prom_result['total']
    aprobadas = prom_result['aprobadas']
    tasa_aprobacion = round(aprobadas / total_notas * 100, 1) if total_notas > 0 else 0.0

    # 4. Top 3 materias más reprobadas del docente
    top_reprobadas = (
        Nota.objects
        .filter(curso__in=ids_cursos, definitiva__lt=3.0)
        .values('curso__materia__nombre')
        .annotate(veces=Count('id'))
        .order_by('-veces')[:3]
    )
    materias_criticas = [
        {'materia': r['curso__materia__nombre'], 'reprobaciones': r['veces']}
        for r in top_reprobadas
    ]

    # 5. Distribución por nivel de riesgo de sus estudiantes
    dist_riesgo = {'high': 0, 'medium': 0, 'low': 0, 'unknown': 0}
    for nivel in riesgo_ultimo.values():
        dist_riesgo[nivel] = dist_riesgo.get(nivel, 0) + 1

    # 6. Cursos con estado CRÍTICO o EN OBSERVACIÓN
    cursos_criticos = sum(1 for c in cursos_data if c['estado'] in ['CRÍTICO', 'EN OBSERVACIÓN'])

    # ── Estudiantes en riesgo (para el modal) — paginado ─────────────────────
    try:
        page      = max(1, int(request.GET.get('page', 1)))
        page_size = min(50, max(1, int(request.GET.get('page_size', 10))))
    except ValueError:
        page, page_size = 1, 10

    # Orden previo: nivel descendente (como '-nivel_riesgo'); desempate por código
    en_riesgo_ordenado = sorted(
        (item for item in riesgo_ultimo.items() if item[1] in ('high', 'medium')),
        key=lambda item: (item[1], item[0]), reverse=True,
    )

    from django.core.paginator import Paginator
    paginator = Paginator(en_riesgo_ordenado, page_size)
    page_obj = paginator.get_page(page)
    estudiantes_pagina = {
        e.codigo: e for e in Estudiante.objects.filter(codigo__in=[est for est, _ in page_obj.object_list])
    }
    # SDAT-303: curso de cada estudiante de la página en una consulta (antes una por estudiante)
    nota_por_estudiante = {}
    for nota in (
        Nota.objects.filter(estudiante_id__in=estudiantes_pagina, curso__in=ids_cursos)
        .select_related('curso__materia').order_by('-id')
    ):
        nota_por_estudiante.setdefault(nota.estudiante_id, nota)

    # Alertas por estudiante en una sola query
    alertas_por_est = dict(
        alertas_abiertas(Alerta.objects.filter(estudiante__in=estudiantes_docente))
        .values('estudiante_id')
        .annotate(total=Count('id'))
        .values_list('estudiante_id', 'total')
    )
    total_alertas_activas = sum(alertas_por_est.values())

    estudiantes_data = []
    for est_codigo, nivel_riesgo in page_obj.object_list:
        est = estudiantes_pagina[est_codigo]
        # Curso del docente donde aparece este estudiante
        nota_rel = nota_por_estudiante.get(est_codigo)
        estudiantes_data.append({
            'codigo':          est.codigo,
            'nombre':          est.nombre,
            'curso':           nota_rel.curso.materia.nombre if nota_rel else '—',
            'nivel_riesgo':    nivel_riesgo,
            'alertas_activas': alertas_por_est.get(est.codigo, 0),
        })

    return JsonResponse({
        'nombre_docente':          usuario.nombre,
        'cursos':                  cursos_data,
        'estudiantes_en_riesgo':   estudiantes_data,
        'total_en_riesgo':         total_en_riesgo,
        'total_alertas_activas':   total_alertas_activas,   # 6.3
        'total_estudiantes':       total_estudiantes,        # 6.4
        'promedio_general':        promedio_general,         # 6.4
        'tasa_aprobacion':         tasa_aprobacion,          # 6.4
        'materias_criticas':       materias_criticas,        # 6.4
        'distribucion_riesgo':     dist_riesgo,              # 6.4
        'cursos_criticos':         cursos_criticos,          # 6.4
        'umbral_inasistencia':     numero_o_none(obtener_umbral_general()),  # HU-35: umbral general
        'page':                    page,
        'pages':                   paginator.num_pages,
        'page_size':               page_size,
    })


@csrf_exempt
@require_GET
@requiere_rol(['DOCENTE'])
def teacher_course_students(request, curso_id):
    """
    GET /api/academico/teacher/course/<int:curso_id>/students/
    Retorna la lista de estudiantes del curso con su nivel de riesgo.
    Incluye todos los estudiantes (no solo los de riesgo medio/alto).
    """
    usuario = request.usuario
    try:
        docente = usuario.docente
    except Exception:
        return JsonResponse({'error': 'El usuario no tiene perfil de docente.'}, status=404)

    try:
        curso = Curso.objects.get(id=curso_id, docente=docente)
    except Curso.DoesNotExist:
        return JsonResponse({'error': 'El curso no existe o no está asignado a usted.'}, status=404)

    try:
        page      = max(1, int(request.GET.get('page', 1)))
        page_size = min(50, max(1, int(request.GET.get('page_size', 5))))
    except ValueError:
        page, page_size = 1, 5

    # Obtener todos los estudiantes del curso con sus notas
    # SDAT-303: solo las columnas necesarias, sin instanciar modelos
    notas = (
        Nota.objects
        .filter(curso=curso)
        .order_by('-periodo__anio', '-periodo__semestre')
        .values_list('estudiante_id', 'estudiante__nombre', 'definitiva')
    )

    # Agrupar: un registro por estudiante (la nota más reciente)
    visto = set()
    estudiantes_notas = []
    for codigo_est, nombre_est, definitiva in notas:
        if codigo_est not in visto:
            visto.add(codigo_est)
            estudiantes_notas.append((codigo_est, nombre_est, definitiva))

    estudiantes_ids = [n[0] for n in estudiantes_notas]

    # Nivel de riesgo: preferir RiesgoEstudiantePeriodo, fallback a RiesgoEstudiante
    # Cargar ambos en una sola query cada uno
    riesgo_periodo_map = {}
    for est_id, nivel_rep in (
        RiesgoEstudiantePeriodo.objects
        .filter(estudiante_id__in=estudiantes_ids)
        .order_by('estudiante_id', '-periodo__anio', '-periodo__semestre')
        .values_list('estudiante_id', 'nivel_riesgo')
    ):
        riesgo_periodo_map.setdefault(est_id, nivel_rep)

    riesgo_snapshot_map = dict(
        RiesgoEstudiante.objects.filter(estudiante_id__in=estudiantes_ids)
        .values_list('estudiante_id', 'nivel_riesgo')
    )

    # Alertas no cerradas por estudiante
    alertas_map = dict(
        alertas_abiertas(Alerta.objects.filter(estudiante_id__in=estudiantes_ids))
        .values('estudiante_id')
        .annotate(total=Count('id'))
        .values_list('estudiante_id', 'total')
    )

    # HU-34: porcentaje de inasistencia en el periodo más reciente, una sola consulta
    periodo_asistencia = periodo_actual()
    inasistencia = calcular_inasistencia_curso(curso, periodo_asistencia) if periodo_asistencia else {}
    umbral, origen_umbral = obtener_umbral_inasistencia(curso)

    # Construir lista completa ordenada por riesgo (high > medium > low > unknown)
    ORDEN_RIESGO = {'high': 0, 'medium': 1, 'low': 2, 'unknown': 3}
    resultado = []
    for est_codigo, est_nombre, definitiva in estudiantes_notas:
        nivel = riesgo_periodo_map.get(est_codigo) or riesgo_snapshot_map.get(est_codigo, 'unknown')
        porcentaje = inasistencia.get(est_codigo, {}).get('porcentaje')
        resultado.append({
            'codigo':          est_codigo,
            'nombre':          est_nombre,
            'nivel_riesgo':    nivel,
            'alertas_activas': alertas_map.get(est_codigo, 0),
            'ultima_nota':     float(definitiva) if definitiva is not None else None,
            'porcentaje_inasistencia': float(porcentaje) if porcentaje is not None else None,
            'supera_umbral_inasistencia': supera_umbral(porcentaje, umbral),
            'cerca_umbral_inasistencia':  cerca_umbral(porcentaje, umbral),
            '_ord':            ORDEN_RIESGO.get(nivel, 3),
        })

    resultado.sort(key=lambda x: (x['_ord'], x['nombre']))
    for item in resultado:
        del item['_ord']

    # Paginación manual
    total = len(resultado)
    start = (page - 1) * page_size
    page_results = resultado[start:start + page_size]

    return JsonResponse({
        'curso': {
            'id':      curso.id,
            'materia': curso.materia.nombre,
            'codigo':  curso.materia.codigo,
            'grupo':   curso.grupo,
        },
        'estudiantes': page_results,
        'total':       total,
        'page':        page,
        'pages':       max(1, -(-total // page_size)),
        'page_size':   page_size,
        'periodo_asistencia':  str(periodo_asistencia) if periodo_asistencia else None,
        'umbral_inasistencia': numero_o_none(umbral),
        'origen_umbral_inasistencia': origen_umbral,
    })

