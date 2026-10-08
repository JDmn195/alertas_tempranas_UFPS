from django.http import JsonResponse
from django.views.decorators.http import require_GET

from academico.models import Estudiante, Nota, Periodo
from academico.services.notas_corte import alertas_corte_abiertas, desglose_cortes, estado_nota
from academico.views.inasistencia_views import ROLES_CONSULTA, _parsear_periodo
from academico.views.student_views import _acceso_denegado_docente
from usuarios.decorators import requiere_rol


@require_GET
@requiere_rol(ROLES_CONSULTA)
def notas_corte_estudiante(request, codigo):
    """
    HU-31: GET /api/academico/students/<codigo>/notas-corte/?periodo=AAAA-S&materia=<codigo>

    Notas del estudiante desglosadas por corte 1, 2 y 3 y examen final en cada materia
    del periodo, con la nota necesaria en el examen y las alertas por corte abiertas (HU-32).
    Sin periodo usa el más reciente en que el estudiante tiene notas.
    """
    try:
        estudiante = Estudiante.objects.get(codigo=codigo)
    except Estudiante.DoesNotExist:
        return JsonResponse({'error': f'Estudiante con código {codigo} no encontrado'}, status=404)

    denegado = _acceso_denegado_docente(request, estudiante)
    if denegado:
        return denegado

    periodos_disponibles = list(
        Periodo.objects.filter(nota__estudiante=estudiante)
        .distinct()
        .order_by('-anio', '-semestre')
    )
    if request.GET.get('periodo'):
        periodo, error = _parsear_periodo(request.GET['periodo'])
        if error:
            return error
    else:
        periodo = periodos_disponibles[0] if periodos_disponibles else None

    respuesta = {
        'codigo':               estudiante.codigo,
        'nombre':               estudiante.nombre,
        'periodo':              str(periodo) if periodo else None,
        'periodos_disponibles': [str(p) for p in periodos_disponibles],
        'materias':             [],
    }
    if not periodo:
        return JsonResponse(respuesta)

    notas = (
        Nota.objects.filter(estudiante=estudiante, periodo=periodo)
        .select_related('periodo', 'curso__materia')
        .order_by('curso__materia__nombre')
    )
    if request.GET.get('materia'):
        notas = notas.filter(curso__materia__codigo=request.GET['materia'])

    alertas_por_curso = alertas_corte_abiertas(estudiante)
    respuesta['materias'] = [
        {
            'curso_id':   n.curso_id,
            'codigo':     n.curso.materia.codigo,
            'materia':    n.curso.materia.nombre,
            'grupo':      n.curso.grupo,
            'definitiva': float(n.definitiva) if n.definitiva is not None else None,
            'estado':     estado_nota(n),
            **desglose_cortes(n, alertas_por_curso),
        }
        for n in notas
    ]
    return JsonResponse(respuesta)
