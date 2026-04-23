from django.http import JsonResponse
from django.db.models import Count, Q
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt

from academico.models import Estudiante
from alertas.models import Alerta


def calcular_nivel_riesgo(promedio):
    """
    Calcula el nivel de riesgo de un estudiante basado en su promedio acumulado.
    - Alto  : promedio < 3.0
    - Medio : 3.0 <= promedio < 3.5
    - Bajo  : promedio >= 3.5
    Si no hay promedio registrado se clasifica como desconocido.
    """
    if promedio is None:
        return 'unknown'
    p = float(promedio)
    if p < 3.0:
        return 'high'
    elif p < 3.5:
        return 'medium'
    return 'low'


@csrf_exempt
@require_GET
def listar_estudiantes(request):
    """
    GET /api/academico/students/

    Query params opcionales:
        search   – filtra por nombre o código (icontains)
        semester – filtra por semestre exacto (número)
        risk     – filtra por nivel de riesgo: high | medium | low
        page     – número de página (default 1)
        page_size – tamaño de página (default 20, max 100)
    """

    # ── Parámetros de entrada ────────────────────────────────────────────────
    search    = request.GET.get('search', '').strip()
    semester  = request.GET.get('semester', '').strip()
    risk      = request.GET.get('risk', '').strip().lower()
    try:
        page      = max(1, int(request.GET.get('page', 1)))
        page_size = min(100, max(1, int(request.GET.get('page_size', 20))))
    except ValueError:
        page, page_size = 1, 20

    # ── Consulta base ────────────────────────────────────────────────────────
    qs = Estudiante.objects.all()

    # Búsqueda por nombre o código
    if search:
        qs = qs.filter(
            Q(nombre__icontains=search) | Q(codigo__icontains=search)
        )

    # Filtro por semestre
    if semester.isdigit():
        qs = qs.filter(semestre=int(semester))

    # Anotar conteo de alertas activas
    qs = qs.annotate(
        total_alertas=Count(
            'alerta',
            filter=Q(alerta__estado='activa'),
        )
    )

    # Obtener todos para poder filtrar por nivel de riesgo calculado
    # (el nivel se calcula sobre el campo promedio, no con una expresión DB)
    estudiantes_raw = qs.values(
        'codigo', 'nombre', 'semestre', 'promedio',
        'estado_matricula', 'total_alertas',
    )

    # ── Construcción de resultados con nivel de riesgo ────────────────────────
    results = []
    for e in estudiantes_raw:
        nivel = calcular_nivel_riesgo(e['promedio'])

        # Aplicar filtro de riesgo en Python (evita expr complejas en SQL)
        if risk and risk != nivel:
            continue

        results.append({
            'codigo':          e['codigo'],
            'nombre':          e['nombre'],
            'semestre':        e['semestre'],
            'promedio':        float(e['promedio']) if e['promedio'] is not None else None,
            'nivel_riesgo':    nivel,
            'alertas_activas': e['total_alertas'],
            'estado_matricula': e['estado_matricula'],
        })

    # ── Paginación ────────────────────────────────────────────────────────────
    total = len(results)
    start = (page - 1) * page_size
    end   = start + page_size
    page_results = results[start:end]

    return JsonResponse({
        'total':     total,
        'page':      page,
        'page_size': page_size,
        'pages':     max(1, -(-total // page_size)),  # ceil division
        'results':   page_results,
    })
