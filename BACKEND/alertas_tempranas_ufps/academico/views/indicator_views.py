from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count, Avg, Subquery, OuterRef

from academico.models import Curso, Nota, Periodo, Estudiante
from alertas.models import RiesgoEstudiante, RiesgoEstudiantePeriodo, Alerta, Regla
from usuarios.models import Usuario

# Umbral para marcar un curso como crítico (configurable aquí)
UMBRAL_CRITICO = 30.0       # tasa de reprobación >= 30% → CRÍTICO
UMBRAL_OBSERVACION = 15.0   # tasa de reprobación >= 15% → EN OBSERVACIÓN
UMBRAL_ZONA_RIESGO_MIN = 2.5
UMBRAL_ZONA_RIESGO_MAX = 2.9


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_periodo(anio, semestre):
    """Busca un Periodo por año y semestre. Retorna None si no existe."""
    try:
        return Periodo.objects.get(anio=int(anio), semestre=int(semestre))
    except (Periodo.DoesNotExist, ValueError, TypeError):
        return None


def _get_periodo_anterior(anio, semestre):
    """
    Calcula el periodo inmediatamente anterior.
    Semestre 1 → anterior es semestre 2 del año pasado.
    Semestre 2 → anterior es semestre 1 del mismo año.
    """
    anio, semestre = int(anio), int(semestre)
    if semestre == 1:
        return _get_periodo(anio - 1, 2)
    else:
        return _get_periodo(anio, 1)


def _calcular_indicadores_curso_global(curso):
    """
    Calcula indicadores de un curso usando TODAS las notas disponibles,
    sin filtrar por periodo. Útil cuando no se especifica periodo o
    cuando el periodo solicitado no existe en la BD.
    """
    notas = Nota.objects.filter(curso=curso)
    matriculados = notas.count()

    if matriculados == 0:
        return {
            'matriculados':          0,
            'reprobados':            0,
            'tasa_reprobacion':      0.0,
            'promedio_curso':        None,
            'zona_riesgo':           0,
            'no_presentados':        0,
            'tasa_no_presentados':   0.0,
            'tendencia_puntos':      None,
            'tendencia_descripcion': 'Sin notas registradas',
            'estado':                'SIN DATOS',
            'es_critico':            False,
        }

    notas_con_nota = notas.exclude(definitiva__isnull=True)
    reprobados     = notas_con_nota.filter(definitiva__lt=3.0).count()
    no_presentados = notas.filter(definitiva__isnull=True).count()
    zona_riesgo    = notas_con_nota.filter(
                        definitiva__gte=UMBRAL_ZONA_RIESGO_MIN,
                        definitiva__lte=UMBRAL_ZONA_RIESGO_MAX
                    ).count()

    total_con_nota = notas_con_nota.count()
    suma_notas = sum(float(n.definitiva) for n in notas_con_nota if n.definitiva is not None)
    promedio_curso = round(suma_notas / total_con_nota, 2) if total_con_nota > 0 else None

    tasa_reprobacion    = round((reprobados / matriculados) * 100, 2)
    tasa_no_presentados = round((no_presentados / matriculados) * 100, 2)

    if tasa_reprobacion >= UMBRAL_CRITICO:
        estado = 'CRÍTICO'
    elif tasa_reprobacion >= UMBRAL_OBSERVACION:
        estado = 'EN OBSERVACIÓN'
    else:
        estado = 'ESTABLE'

    return {
        'matriculados':          matriculados,
        'reprobados':            reprobados,
        'tasa_reprobacion':      tasa_reprobacion,
        'promedio_curso':        promedio_curso,
        'zona_riesgo':           zona_riesgo,
        'no_presentados':        no_presentados,
        'tasa_no_presentados':   tasa_no_presentados,
        'tendencia_puntos':      None,
        'tendencia_descripcion': 'Acumulado de todos los periodos',
        'estado':                estado,
        'es_critico':            estado == 'CRÍTICO',
    }


# ─── Vista principal ──────────────────────────────────────────────────────────

@csrf_exempt
@require_GET
def listar_indicadores_cursos(request):
    """
    GET /api/academico/courses/indicators/

    Query params:
        usuario_id       – id del usuario logueado (requerido)
        periodo_anio     – año del periodo (default: 2025)
        periodo_semestre – semestre 1 o 2   (default: 1)
        search           – buscar por nombre o código de materia
        estado           – filtrar por estado: CRÍTICO | EN OBSERVACIÓN | ESTABLE
        page             – número de página (default: 1)
        page_size        – registros por página (default: 15, max: 100)

    Roles:
        DIRECTOR  → ve todos los cursos
        BIENESTAR → ve todos los cursos
        DOCENTE   → solo ve los cursos que dicta
    """

    # ── Leer parámetros ───────────────────────────────────────────────────────
    usuario_id       = request.GET.get('usuario_id', '').strip()
    periodo_anio     = request.GET.get('periodo_anio', '2025').strip()
    periodo_semestre = request.GET.get('periodo_semestre', '1').strip()
    search           = request.GET.get('search', '').strip()
    estado_filter    = request.GET.get('estado', '').strip().upper()

    try:
        page      = max(1, int(request.GET.get('page', 1)))
        page_size = min(500, max(1, int(request.GET.get('page_size', 15))))
    except ValueError:
        page, page_size = 1, 15

    # ── Validar usuario ───────────────────────────────────────────────────────
    try:
        usuario = Usuario.objects.get(id=int(usuario_id))
    except (Usuario.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'error': 'usuario_id inválido o no encontrado'}, status=400)

    # ── Obtener periodos ──────────────────────────────────────────────────────
    usar_global = (periodo_anio.lower() == 'todos')
    periodo = None
    periodo_anterior = None
    advertencia = None

    if not usar_global:
        periodo = _get_periodo(periodo_anio, periodo_semestre)
        if not periodo:
            # El periodo no existe: mostrar todos los cursos con indicadores globales
            usar_global = True
            advertencia = (
                f'El periodo {periodo_anio}-{periodo_semestre} no existe en la base de datos. '
                f'Mostrando indicadores acumulados de todos los periodos.'
            )
        else:
            periodo_anterior = _get_periodo_anterior(periodo_anio, periodo_semestre)

    # ── Filtro por rol ────────────────────────────────────────────────────────
    if usuario.rol == 'DOCENTE':
        try:
            docente = usuario.docente
            curso_ids_base = list(
                Curso.objects.filter(docente=docente).values_list('id', flat=True)
            )
        except Exception:
            curso_ids_base = []
    else:
        curso_ids_base = None  # None = todos

    # ── Búsqueda por materia ──────────────────────────────────────────────────
    cursos_qs = Curso.objects.select_related('materia', 'docente')
    if curso_ids_base is not None:
        cursos_qs = cursos_qs.filter(id__in=curso_ids_base)
    if search:
        cursos_qs = cursos_qs.filter(
            Q(materia__nombre__icontains=search) | Q(materia__codigo__icontains=search)
        )

    curso_ids = list(cursos_qs.values_list('id', flat=True))

    # ── Aggregations SQL: una sola query para todos los indicadores ───────────
    from django.db.models import Count, Avg, Q as DQ

    if usar_global:
        notas_filter = Q(curso_id__in=curso_ids)
    else:
        notas_filter = Q(curso_id__in=curso_ids, periodo=periodo)

    stats = (
        Nota.objects
        .filter(notas_filter)
        .values('curso_id')
        .annotate(
            total_notas=Count('id'),
            reprobados=Count('id', filter=Q(definitiva__lt=3.0, definitiva__isnull=False)),
            no_presentados=Count('id', filter=Q(definitiva__isnull=True)),
            zona_riesgo=Count('id', filter=Q(
                definitiva__gte=UMBRAL_ZONA_RIESGO_MIN,
                definitiva__lte=UMBRAL_ZONA_RIESGO_MAX,
            )),
            promedio=Avg('definitiva'),
        )
    )
    stats_map = {row['curso_id']: row for row in stats}

    # Para tendencia (solo modo periodo): una query del periodo anterior
    stats_ant_map = {}
    if not usar_global and periodo_anterior:
        stats_ant = (
            Nota.objects
            .filter(curso_id__in=curso_ids, periodo=periodo_anterior)
            .values('curso_id')
            .annotate(
                total_notas=Count('id'),
                reprobados=Count('id', filter=Q(definitiva__lt=3.0, definitiva__isnull=False)),
            )
        )
        stats_ant_map = {row['curso_id']: row for row in stats_ant}

    # ── Construir resultados ──────────────────────────────────────────────────
    results = []
    for curso in cursos_qs:
        s = stats_map.get(curso.id)

        if s is None:
            # Sin notas para este curso/periodo
            matriculados = curso.cantidad_matriculados or 0
            indicadores = {
                'matriculados':          matriculados,
                'reprobados':            0,
                'tasa_reprobacion':      0.0,
                'promedio_curso':        None,
                'zona_riesgo':           0,
                'no_presentados':        0,
                'tasa_no_presentados':   0.0,
                'tendencia_puntos':      None,
                'tendencia_descripcion': 'Sin notas registradas' if usar_global else 'Sin datos para este periodo',
                'estado':                'SIN DATOS',
                'es_critico':            False,
            }
        else:
            # Usar siempre el conteo real de notas como denominador.
            # cantidad_matriculados puede estar desactualizado o ser mayor
            # que las notas reales, lo que bajaría artificialmente la tasa.
            matriculados = s['total_notas']
            reprobados   = s['reprobados']
            tasa = round(reprobados / matriculados * 100, 2) if matriculados > 0 else 0.0
            tasa_np = round(s['no_presentados'] / matriculados * 100, 2) if matriculados > 0 else 0.0

            if tasa >= UMBRAL_CRITICO:
                estado = 'CRÍTICO'
            elif tasa >= UMBRAL_OBSERVACION:
                estado = 'EN OBSERVACIÓN'
            else:
                estado = 'ESTABLE'

            # Tendencia
            tendencia_puntos = None
            tendencia_desc   = 'Acumulado de todos los periodos' if usar_global else 'Sin datos anteriores para calcular tendencia'
            if not usar_global and periodo_anterior:
                sa = stats_ant_map.get(curso.id)
                if sa and sa['total_notas'] > 0:
                    tasa_ant = round(sa['reprobados'] / sa['total_notas'] * 100, 2)
                    tendencia_puntos = round(tasa - tasa_ant, 2)
                    signo = '+' if tendencia_puntos > 0 else ''
                    tendencia_desc = (
                        f'{signo}{tendencia_puntos}% respecto al periodo anterior '
                        f'({periodo_anterior.anio}-{periodo_anterior.semestre})'
                    )

            indicadores = {
                'matriculados':          matriculados,
                'reprobados':            reprobados,
                'tasa_reprobacion':      tasa,
                'promedio_curso':        round(float(s['promedio']), 2) if s['promedio'] else None,
                'zona_riesgo':           s['zona_riesgo'],
                'no_presentados':        s['no_presentados'],
                'tasa_no_presentados':   tasa_np,
                'tendencia_puntos':      tendencia_puntos,
                'tendencia_descripcion': tendencia_desc,
                'estado':                estado,
                'es_critico':            estado == 'CRÍTICO',
            }

        # Filtro por estado
        if estado_filter and indicadores['estado'] != estado_filter:
            continue

        results.append({
            'curso_id':              curso.id,
            'codigo_materia':        curso.materia.codigo,
            'materia':               curso.materia.nombre,
            'grupo':                 curso.grupo,
            'docente':               curso.docente.nombre if curso.docente else 'Sin asignar',
            **indicadores,
        })

    # ── Paginación ────────────────────────────────────────────────────────────
    # Ordenar por tasa de reprobación descendente para que los críticos
    # siempre aparezcan primero (importante para la gráfica del frontend)
    results.sort(key=lambda x: x['tasa_reprobacion'], reverse=True)

    total        = len(results)
    start        = (page - 1) * page_size
    page_results = results[start: start + page_size]

    response_data = {
        'total':     total,
        'page':      page,
        'page_size': page_size,
        'pages':     max(1, -(-total // page_size)),
        'results':   page_results,
    }
    if advertencia:
        response_data['advertencia'] = advertencia

    return JsonResponse(response_data)


from usuarios.decorators import requiere_rol

@csrf_exempt
@require_GET
@requiere_rol(['ADMINISTRADOR', 'DOCENTE', 'DIRECTOR', 'BIENESTAR'])
def detalle_curso(request, curso_id):
    """
    GET /api/academico/courses/<int:curso_id>/detail/
    Retorna el detalle de un curso: materia, docente y lista de estudiantes matriculados ordenados por periodo más reciente.
    """
    try:
        curso = Curso.objects.select_related('materia', 'docente').get(id=curso_id)
    except Curso.DoesNotExist:
        return JsonResponse({'error': 'Curso no encontrado'}, status=404)

    usuario = request.usuario
    if usuario.rol == 'DOCENTE':
        try:
            docente = usuario.docente
            if curso.docente != docente:
                return JsonResponse({'error': 'Acceso denegado: este curso no le pertenece.'}, status=403)
        except Exception:
            return JsonResponse({'error': 'El usuario no tiene perfil de docente.'}, status=404)

    # Estudiantes matriculados a través de Notas, ordenados por periodo más reciente
    notas = Nota.objects.filter(curso=curso).select_related('estudiante', 'periodo').order_by(
        '-periodo__anio', '-periodo__semestre', 'estudiante__nombre'
    )

    estudiantes_data = []
    for n in notas:
        est = n.estudiante
        periodo_str = f"{n.periodo.anio}-{n.periodo.semestre}" if n.periodo else "—"
        estudiantes_data.append({
            'codigo': est.codigo,
            'nombre': est.nombre,
            'periodo': periodo_str,
            'definitiva': float(n.definitiva) if n.definitiva is not None else None,
        })

    return JsonResponse({
        'curso_id': curso.id,
        'codigo_materia': curso.materia.codigo,
        'materia': curso.materia.nombre,
        'grupo': curso.grupo,
        'docente': curso.docente.nombre if curso.docente else 'Sin asignar',
        'estudiantes': estudiantes_data,
    })



# ─── Vista KPIs globales para el Director ─────────────────────────────────────

@csrf_exempt
@require_GET
def director_indicadores(request):
    """
    GET /api/academico/indicadores/

    Retorna los KPIs globales del panel estratégico del director.
    Optimizado: usa aggregations SQL en lugar de loops Python (N+1 → O(1) queries).
    """
    from collections import defaultdict

    try:
        # ── KPI 1: Total estudiantes activos ─────────────────────────────────
        total_activos = Estudiante.objects.exclude(
            Q(estado_matricula__icontains='retirado') |
            Q(estado_matricula__icontains='graduado') |
            Q(estado_matricula__icontains='cancelado')
        ).count()

        # ── KPI 2: Porcentaje en riesgo ───────────────────────────────────────
        # Combina ambas fuentes igual que la distribución por semestre.
        _periodo_max_id_sq = (
            RiesgoEstudiantePeriodo.objects
            .filter(estudiante_id=OuterRef('estudiante_id'))
            .order_by('-periodo__anio', '-periodo__semestre')
            .values('id')[:1]
        )
        # Estudiantes con RiesgoEstudiantePeriodo en riesgo
        ids_en_riesgo_con_periodo = set(
            RiesgoEstudiantePeriodo.objects
            .filter(id=Subquery(_periodo_max_id_sq))
            .filter(nivel_riesgo__in=['high', 'medium'])
            .values_list('estudiante_id', flat=True)
        )
        # Estudiantes sin RiesgoEstudiantePeriodo pero con snapshot en riesgo
        ids_en_riesgo_sin_periodo = set(
            RiesgoEstudiante.objects
            .exclude(estudiante_id__in=ids_en_riesgo_con_periodo)
            .filter(nivel_riesgo__in=['high', 'medium'])
            .values_list('estudiante_id', flat=True)
        )
        en_riesgo = len(ids_en_riesgo_con_periodo) + len(ids_en_riesgo_sin_periodo)
        porcentaje_riesgo = round((en_riesgo / total_activos * 100), 2) if total_activos > 0 else 0.0

        # ── KPI 3: Total alertas activas ─────────────────────────────────────
        alertas_activas = Alerta.objects.filter(
            estado__in=['activa', 'active']
        ).count()

        # ── KPIs 4 + tabla cursos críticos: una sola query agregada ──────────
        # Agrupa todas las notas por curso y calcula reprobados/matriculados en SQL
        stats_por_curso = (
            Nota.objects
            .values('curso_id', 'curso__materia__nombre', 'curso__cantidad_matriculados')
            .annotate(
                total_notas=Count('id'),
                reprobados=Count('id', filter=Q(definitiva__lt=3.0, definitiva__isnull=False)),
                promedio=Avg('definitiva'),
            )
        )

        cursos_alta_reprobacion = 0
        cursos_criticos_list = []

        for row in stats_por_curso:
            matriculados = row['total_notas']
            if matriculados <= 0:
                continue
            reprobados = row['reprobados']
            tasa = round(reprobados / matriculados * 100, 2)
            if tasa >= UMBRAL_CRITICO:
                cursos_alta_reprobacion += 1
                cursos_criticos_list.append({
                    'course': row['curso__materia__nombre'],
                    'failureRate': tasa,
                    'enrolled': matriculados,
                    'failed': reprobados,
                })

        cursos_criticos_list.sort(key=lambda x: x['failureRate'], reverse=True)

        # ── Distribución de riesgo por semestre ──────────────────────────────
        # Fuente 1: estudiantes CON historial de notas → usar el nivel del
        # RiesgoEstudiantePeriodo más reciente (más preciso).
        # Fuente 2: estudiantes SIN notas → usar RiesgoEstudiante (snapshot).
        # Combinamos ambas para no dejar fuera a los estudiantes recién importados.

        periodo_max_id_sq = (
            RiesgoEstudiantePeriodo.objects
            .filter(estudiante_id=OuterRef('estudiante_id'))
            .order_by('-periodo__anio', '-periodo__semestre')
            .values('id')[:1]
        )

        # Estudiantes con RiesgoEstudiantePeriodo
        estudiantes_con_periodo = set(
            RiesgoEstudiantePeriodo.objects
            .filter(id=Subquery(periodo_max_id_sq))
            .values_list('estudiante_id', flat=True)
        )

        dist_map = defaultdict(lambda: {'low': 0, 'medium': 0, 'high': 0})

        # Fuente 1: nivel del periodo más reciente
        dist_raw = (
            RiesgoEstudiantePeriodo.objects
            .filter(id=Subquery(periodo_max_id_sq))
            .filter(nivel_riesgo__in=['low', 'medium', 'high'])
            .values('nivel_riesgo', 'estudiante__semestre')
            .annotate(total=Count('id'))
        )
        for row in dist_raw:
            sem = row['estudiante__semestre']
            dist_map[sem][row['nivel_riesgo']] += row['total']

        # Fuente 2: snapshot de estudiantes sin RiesgoEstudiantePeriodo
        dist_snapshot = (
            RiesgoEstudiante.objects
            .exclude(estudiante_id__in=estudiantes_con_periodo)
            .filter(nivel_riesgo__in=['low', 'medium', 'high'])
            .values('nivel_riesgo', 'estudiante__semestre')
            .annotate(total=Count('id'))
        )
        for row in dist_snapshot:
            sem = row['estudiante__semestre']
            dist_map[sem][row['nivel_riesgo']] += row['total']

        distribucion_riesgo = [
            {
                'semester': f'Sem {sem}',
                'low': counts['low'],
                'medium': counts['medium'],
                'high': counts['high'],
            }
            for sem, counts in sorted(dist_map.items())
        ]

        # ── Tendencia GPA por periodo: una query agregada ─────────────────────
        tendencia_raw = (
            Nota.objects
            .exclude(definitiva__isnull=True)
            .values('periodo__anio', 'periodo__semestre')
            .annotate(gpa=Avg('definitiva'))
            .order_by('periodo__anio', 'periodo__semestre')
        )
        tendencia_gpa = [
            {
                'cohort': f"{row['periodo__anio']}-{row['periodo__semestre']}",
                'gpa': round(float(row['gpa']), 2),
            }
            for row in tendencia_raw
            if row['periodo__anio'] is not None
        ]

        return JsonResponse({
            'total_estudiantes_activos': total_activos,
            'porcentaje_riesgo': porcentaje_riesgo,
            'alertas_activas': alertas_activas,
            'cursos_alta_reprobacion': cursos_alta_reprobacion,
            'distribucion_riesgo': distribucion_riesgo,
            'tendencia_gpa': tendencia_gpa,
            'cursos_criticos': cursos_criticos_list,
        })

    except Exception as e:
        return JsonResponse({'error': f'Error al calcular indicadores: {str(e)}'}, status=500)
