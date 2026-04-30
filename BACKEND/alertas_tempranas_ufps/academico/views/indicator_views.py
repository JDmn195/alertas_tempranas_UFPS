from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt

from academico.models import Curso, Nota, Periodo
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


def _calcular_indicadores_curso(curso, periodo, periodo_anterior=None):
    """
    Calcula todos los indicadores de un curso en un periodo dado.

    Indicadores calculados:
    - matriculados        : estudiantes con nota registrada en el periodo
    - reprobados          : definitiva < 3.0 (y no es null)
    - tasa_reprobacion    : (reprobados / matriculados) × 100
    - promedio_curso      : promedio ponderado de definitivas del grupo
    - zona_riesgo         : estudiantes con 2.5 <= definitiva <= 2.9
    - no_presentados      : estudiantes con definitiva = null
    - tasa_no_presentados : (no_presentados / matriculados) × 100
    - tendencia_puntos    : diferencia de tasa_reprobacion vs periodo anterior
    - tendencia_descripcion
    - estado              : CRÍTICO / EN OBSERVACIÓN / ESTABLE
    - es_critico          : bool
    """
    notas = Nota.objects.filter(curso=curso, periodo=periodo)
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
            'tendencia_descripcion': 'Sin datos para este periodo',
            'estado':                'SIN DATOS',
            'es_critico':            False,
        }

    # Notas con definitiva registrada (no null)
    notas_con_nota = notas.exclude(definitiva__isnull=True)

    reprobados      = notas_con_nota.filter(definitiva__lt=3.0).count()
    no_presentados  = notas.filter(definitiva__isnull=True).count()
    zona_riesgo     = notas_con_nota.filter(
                        definitiva__gte=UMBRAL_ZONA_RIESGO_MIN,
                        definitiva__lte=UMBRAL_ZONA_RIESGO_MAX
                    ).count()

    # Promedio del curso (solo sobre quienes tienen nota)
    suma_notas = sum(
        float(n.definitiva)
        for n in notas_con_nota
        if n.definitiva is not None
    )
    total_con_nota = notas_con_nota.count()
    promedio_curso = round(suma_notas / total_con_nota, 2) if total_con_nota > 0 else None

    tasa_reprobacion    = round((reprobados / matriculados) * 100, 2)
    tasa_no_presentados = round((no_presentados / matriculados) * 100, 2)

    # ── Tendencia vs periodo anterior ────────────────────────────────────────
    tendencia_puntos      = None
    tendencia_descripcion = 'Sin datos anteriores para calcular tendencia'

    if periodo_anterior:
        notas_ant = Nota.objects.filter(curso=curso, periodo=periodo_anterior)
        matriculados_ant = notas_ant.count()
        if matriculados_ant > 0:
            reprobados_ant  = notas_ant.exclude(definitiva__isnull=True).filter(definitiva__lt=3.0).count()
            tasa_ant        = round((reprobados_ant / matriculados_ant) * 100, 2)
            tendencia_puntos = round(tasa_reprobacion - tasa_ant, 2)
            signo = '+' if tendencia_puntos > 0 else ''
            tendencia_descripcion = (
                f'{signo}{tendencia_puntos}% respecto al periodo anterior '
                f'({periodo_anterior.anio}-{periodo_anterior.semestre})'
            )

    # ── Estado del curso ─────────────────────────────────────────────────────
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
        'tendencia_puntos':      tendencia_puntos,
        'tendencia_descripcion': tendencia_descripcion,
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
        page_size = min(100, max(1, int(request.GET.get('page_size', 15))))
    except ValueError:
        page, page_size = 1, 15

    # ── Validar usuario ───────────────────────────────────────────────────────
    try:
        usuario = Usuario.objects.get(id=int(usuario_id))
    except (Usuario.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'error': 'usuario_id inválido o no encontrado'}, status=400)

    # ── Obtener periodos ──────────────────────────────────────────────────────
    periodo = _get_periodo(periodo_anio, periodo_semestre)
    if not periodo:
        return JsonResponse({
            'total': 0, 'page': 1, 'page_size': page_size,
            'pages': 1, 'results': [],
            'advertencia': f'No existe el periodo {periodo_anio}-{periodo_semestre}'
        })

    periodo_anterior = _get_periodo_anterior(periodo_anio, periodo_semestre)

    # ── Filtro por rol ────────────────────────────────────────────────────────
    if usuario.rol == 'DOCENTE':
        try:
            docente = usuario.docente  # reverso del OneToOneField
            cursos = Curso.objects.filter(docente=docente).select_related('materia', 'docente')
        except Exception:
            cursos = Curso.objects.none()
    else:
        # DIRECTOR y BIENESTAR ven todos
        cursos = Curso.objects.all().select_related('materia', 'docente')

    # ── Búsqueda por materia ──────────────────────────────────────────────────
    if search:
        cursos = cursos.filter(materia__nombre__icontains=search) | \
                cursos.filter(materia__codigo__icontains=search)

    # ── Construir resultados ──────────────────────────────────────────────────
    results = []
    for curso in cursos:
        indicadores = _calcular_indicadores_curso(curso, periodo, periodo_anterior)

        # Filtro por estado
        if estado_filter and indicadores['estado'] != estado_filter:
            continue

        results.append({
            'curso_id':              curso.id,
            'codigo_materia':        curso.materia.codigo,
            'materia':               curso.materia.nombre,
            'grupo':                 curso.grupo,
            'docente':               curso.docente.nombre if curso.docente else 'Sin asignar',
            # Indicadores
            'matriculados':          indicadores['matriculados'],
            'reprobados':            indicadores['reprobados'],
            'tasa_reprobacion':      indicadores['tasa_reprobacion'],
            'promedio_curso':        indicadores['promedio_curso'],
            'zona_riesgo':           indicadores['zona_riesgo'],
            'no_presentados':        indicadores['no_presentados'],
            'tasa_no_presentados':   indicadores['tasa_no_presentados'],
            'tendencia_puntos':      indicadores['tendencia_puntos'],
            'tendencia_descripcion': indicadores['tendencia_descripcion'],
            'estado':                indicadores['estado'],
            'es_critico':            indicadores['es_critico'],
        })

    # ── Paginación ────────────────────────────────────────────────────────────
    total        = len(results)
    start        = (page - 1) * page_size
    page_results = results[start: start + page_size]

    return JsonResponse({
        'total':     total,
        'page':      page,
        'page_size': page_size,
        'pages':     max(1, -(-total // page_size)),
        'results':   page_results,
    })
