from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.db.models import Count, Avg, Q

from academico.models import Curso, Nota, Periodo, Estudiante, Materia
from alertas.models import Alerta, RiesgoEstudiante, RiesgoEstudiantePeriodo
from usuarios.decorators import requiere_rol


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
    todos_estudiantes_ids = list(
        Nota.objects.filter(curso__in=ids_cursos)
        .values_list('estudiante_id', flat=True)
        .distinct()
    )

    # ── Fix 6.2: Stats por curso en UNA sola query SQL ────────────────────────
    stats_curso = (
        Nota.objects
        .filter(curso__in=ids_cursos)
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
    ultimo_riesgo_id = (
        RiesgoEstudiantePeriodo.objects
        .filter(estudiante_id=OuterRef('estudiante_id'))
        .order_by('-periodo__anio', '-periodo__semestre')
        .values('id')[:1]
    )
    en_riesgo_ids = set(
        RiesgoEstudiantePeriodo.objects
        .filter(id=Subquery(ultimo_riesgo_id), nivel_riesgo__in=['high', 'medium'])
        .values_list('estudiante_id', flat=True)
    )

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
            est_ids_curso = set(
                Nota.objects.filter(curso=curso)
                .values_list('estudiante_id', flat=True)
            )
            en_riesgo = len(est_ids_curso & en_riesgo_ids)
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
        })

    total_en_riesgo = len(
        set(todos_estudiantes_ids) & en_riesgo_ids
    )

    # ── Fix 6.3: Total alertas activas de los estudiantes del docente ─────────
    total_alertas_activas = Alerta.objects.filter(
        estudiante__in=todos_estudiantes_ids,
        estado__in=['activa', 'active']
    ).count()

    # ── Fix 6.4: Indicadores adicionales ─────────────────────────────────────

    # 1. Promedio general de todos sus estudiantes
    prom_result = (
        Nota.objects
        .filter(curso__in=ids_cursos)
        .exclude(definitiva__isnull=True)
        .aggregate(ppa=Avg('definitiva'))
    )
    promedio_general = round(float(prom_result['ppa']), 2) if prom_result['ppa'] else None

    # 2. Total estudiantes únicos
    total_estudiantes = len(todos_estudiantes_ids)

    # 3. Tasa global de aprobación
    totales = Nota.objects.filter(curso__in=ids_cursos).exclude(definitiva__isnull=True)
    total_notas = totales.count()
    aprobadas = totales.filter(definitiva__gte=3.0).count()
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
    riesgos_rows = (
        RiesgoEstudiantePeriodo.objects
        .filter(id=Subquery(ultimo_riesgo_id), estudiante__in=todos_estudiantes_ids)
        .values('nivel_riesgo')
        .annotate(total=Count('id'))
    )
    for row in riesgos_rows:
        dist_riesgo[row['nivel_riesgo']] = row['total']

    # 6. Cursos con estado CRÍTICO o EN OBSERVACIÓN
    cursos_criticos = sum(1 for c in cursos_data if c['estado'] in ['CRÍTICO', 'EN OBSERVACIÓN'])

    # ── Estudiantes en riesgo (para el modal) — paginado ─────────────────────
    try:
        page      = max(1, int(request.GET.get('page', 1)))
        page_size = min(50, max(1, int(request.GET.get('page_size', 10))))
    except ValueError:
        page, page_size = 1, 10

    riesgo_estudiantes = (
        RiesgoEstudiantePeriodo.objects
        .filter(id=Subquery(ultimo_riesgo_id), estudiante__in=todos_estudiantes_ids,
                nivel_riesgo__in=['high', 'medium'])
        .select_related('estudiante')
        .order_by('-nivel_riesgo')
    )

    from django.core.paginator import Paginator
    paginator = Paginator(list(riesgo_estudiantes), page_size)
    page_obj = paginator.get_page(page)

    # Alertas por estudiante en una sola query
    alertas_por_est = dict(
        Alerta.objects
        .filter(estudiante__in=todos_estudiantes_ids, estado__in=['activa', 'active'])
        .values('estudiante_id')
        .annotate(total=Count('id'))
        .values_list('estudiante_id', 'total')
    )

    estudiantes_data = []
    for rep in page_obj.object_list:
        est = rep.estudiante
        # Curso del docente donde aparece este estudiante
        nota_rel = (
            Nota.objects
            .filter(estudiante=est, curso__in=ids_cursos)
            .select_related('curso__materia')
            .order_by('-id')
            .first()
        )
        estudiantes_data.append({
            'codigo':          est.codigo,
            'nombre':          est.nombre,
            'curso':           nota_rel.curso.materia.nombre if nota_rel else '—',
            'nivel_riesgo':    rep.nivel_riesgo,
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
    notas = (
        Nota.objects
        .filter(curso=curso)
        .select_related('estudiante', 'periodo')
        .order_by('-periodo__anio', '-periodo__semestre')
    )

    # Agrupar: un registro por estudiante (la nota más reciente)
    visto = set()
    estudiantes_notas = []
    for n in notas:
        if n.estudiante_id not in visto:
            visto.add(n.estudiante_id)
            estudiantes_notas.append(n)

    estudiantes_ids = [n.estudiante_id for n in estudiantes_notas]

    # Nivel de riesgo: preferir RiesgoEstudiantePeriodo, fallback a RiesgoEstudiante
    # Cargar ambos en una sola query cada uno
    riesgo_periodo_map = {}
    for rep in (
        RiesgoEstudiantePeriodo.objects
        .filter(estudiante_id__in=estudiantes_ids)
        .order_by('estudiante_id', '-periodo__anio', '-periodo__semestre')
        .select_related('periodo')
    ):
        if rep.estudiante_id not in riesgo_periodo_map:
            riesgo_periodo_map[rep.estudiante_id] = rep.nivel_riesgo

    riesgo_snapshot_map = {
        r.estudiante_id: r.nivel_riesgo
        for r in RiesgoEstudiante.objects.filter(estudiante_id__in=estudiantes_ids)
    }

    # Alertas no cerradas por estudiante
    alertas_map = dict(
        Alerta.objects
        .filter(estudiante_id__in=estudiantes_ids)
        .exclude(estado__in=['cerrada', 'closed'])
        .values('estudiante_id')
        .annotate(total=Count('id'))
        .values_list('estudiante_id', 'total')
    )

    # Construir lista completa ordenada por riesgo (high > medium > low > unknown)
    ORDEN_RIESGO = {'high': 0, 'medium': 1, 'low': 2, 'unknown': 3}
    resultado = []
    for n in estudiantes_notas:
        est = n.estudiante
        nivel = riesgo_periodo_map.get(est.codigo) or riesgo_snapshot_map.get(est.codigo, 'unknown')
        resultado.append({
            'codigo':          est.codigo,
            'nombre':          est.nombre,
            'nivel_riesgo':    nivel,
            'alertas_activas': alertas_map.get(est.codigo, 0),
            'ultima_nota':     float(n.definitiva) if n.definitiva is not None else None,
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
    })

