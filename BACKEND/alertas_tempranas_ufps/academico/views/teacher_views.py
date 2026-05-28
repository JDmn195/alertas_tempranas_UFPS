from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.core.paginator import Paginator

from academico.models import Curso, Nota, Periodo, Estudiante
from alertas.models import Alerta, RiesgoEstudiante
from usuarios.decorators import requiere_rol


@csrf_exempt
@require_GET
@requiere_rol(['DOCENTE'])
def teacher_dashboard(request):
    """
    GET /api/academico/teacher/dashboard/

    Devuelve datos personalizados del panel del docente autenticado.
    El nombre del docente se extrae del JWT via request.usuario (inyectado por @requiere_rol).

    Query params:
        page          – página de estudiantes en riesgo (default: 1)
        page_size     – ítems por página (default: 10, max: 50)
        periodo_anio  – año del periodo (default: 2025)
        periodo_semestre – semestre 1 o 2 (default: 1)

    Respuesta:
        nombre_docente  – nombre del docente desde JWT
        cursos          – lista de cursos del docente con indicadores básicos
        estudiantes_en_riesgo – paginado: estudiantes en riesgo de sus cursos
        total_en_riesgo – conteo total sin paginación
        page / pages / page_size
    """
    usuario = request.usuario  # inyectado por @requiere_rol desde JWT

    # ── Parámetros ────────────────────────────────────────────────────────────
    try:
        page      = max(1, int(request.GET.get('page', 1)))
        page_size = min(50, max(1, int(request.GET.get('page_size', 10))))
    except ValueError:
        page, page_size = 1, 10

    periodo_anio     = request.GET.get('periodo_anio', '2025').strip()
    periodo_semestre = request.GET.get('periodo_semestre', '1').strip()

    # ── Obtener docente desde el usuario JWT ──────────────────────────────────
    try:
        docente = usuario.docente  # OneToOne reverse
    except Exception:
        return JsonResponse({'error': 'El usuario no tiene perfil de docente.'}, status=404)

    # ── Cursos del docente ────────────────────────────────────────────────────
    cursos_qs = Curso.objects.filter(docente=docente).select_related('materia')

    # ── Periodo actual ────────────────────────────────────────────────────────
    try:
        periodo = Periodo.objects.get(anio=int(periodo_anio), semestre=int(periodo_semestre))
    except (Periodo.DoesNotExist, ValueError):
        periodo = None

    # ── Construir lista de cursos con indicadores básicos ─────────────────────
    cursos_data = []
    for curso in cursos_qs:
        matriculados = 0
        en_riesgo    = 0
        estado       = 'SIN DATOS'

        if periodo:
            notas = Nota.objects.filter(curso=curso, periodo=periodo)
            matriculados = notas.count()
            notas_con_nota = notas.exclude(definitiva__isnull=True)
            reprobados = notas_con_nota.filter(definitiva__lt=3.0).count()
            if matriculados > 0:
                tasa = round((reprobados / matriculados) * 100, 1)
                if tasa >= 30:
                    estado = 'CRÍTICO'
                elif tasa >= 15:
                    estado = 'EN OBSERVACIÓN'
                else:
                    estado = 'ESTABLE'

            # Estudiantes de este curso con riesgo alto o medio
            estudiantes_ids = notas.values_list('estudiante_id', flat=True)
            en_riesgo = RiesgoEstudiante.objects.filter(
                estudiante__in=estudiantes_ids,
                nivel_riesgo__in=['high', 'medium']
            ).count()

        cursos_data.append({
            'curso_id':     curso.id,
            'materia':      curso.materia.nombre,
            'codigo':       curso.materia.codigo,
            'grupo':        curso.grupo,
            'matriculados': matriculados,
            'en_riesgo':    en_riesgo,
            'estado':       estado,
        })

    # ── Estudiantes en riesgo de los cursos del docente ───────────────────────
    # Obtener IDs de todos los estudiantes con notas en los cursos del docente
    ids_cursos = [c.id for c in cursos_qs]

    if periodo:
        estudiantes_ids_riesgo = Nota.objects.filter(
            curso__in=ids_cursos, periodo=periodo
        ).values_list('estudiante_id', flat=True).distinct()
    else:
        estudiantes_ids_riesgo = Nota.objects.filter(
            curso__in=ids_cursos
        ).values_list('estudiante_id', flat=True).distinct()

    # Filtrar solo los que tienen riesgo medio o alto
    riesgos_qs = RiesgoEstudiante.objects.filter(
        estudiante__in=estudiantes_ids_riesgo,
        nivel_riesgo__in=['high', 'medium']
    ).select_related('estudiante')

    total_en_riesgo = riesgos_qs.count()

    # ── Paginación de estudiantes en riesgo ───────────────────────────────────
    paginator = Paginator(list(riesgos_qs), page_size)
    page_obj  = paginator.get_page(page)

    estudiantes_data = []
    for riesgo in page_obj.object_list:
        est = riesgo.estudiante
        # Número de alertas activas del estudiante
        alertas_count = Alerta.objects.filter(estudiante=est, estado='activa').count()
        # Último curso del docente donde aparece este estudiante
        ultima_nota = Nota.objects.filter(
            estudiante=est, curso__in=ids_cursos
        ).select_related('curso__materia').order_by('-id').first()
        nombre_curso = ultima_nota.curso.materia.nombre if ultima_nota else '—'

        estudiantes_data.append({
            'codigo':        est.codigo,
            'nombre':        est.nombre,
            'curso':         nombre_curso,
            'nivel_riesgo':  riesgo.nivel_riesgo,
            'alertas_activas': alertas_count,
        })

    return JsonResponse({
        'nombre_docente':       usuario.nombre,
        'cursos':               cursos_data,
        'estudiantes_en_riesgo': estudiantes_data,
        'total_en_riesgo':      total_en_riesgo,
        'page':                 page,
        'pages':                paginator.num_pages,
        'page_size':            page_size,
    })


@csrf_exempt
@require_GET
@requiere_rol(['DOCENTE'])
def teacher_course_students(request, curso_id):
    """
    GET /api/academico/teacher/course/<int:curso_id>/students/
    Retorna la lista de estudiantes en riesgo de un curso del docente.
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
        page_size = min(50, max(1, int(request.GET.get('page_size', 10))))
    except ValueError:
        page, page_size = 1, 10

    periodo_anio     = request.GET.get('periodo_anio', '2025').strip()
    periodo_semestre = request.GET.get('periodo_semestre', '1').strip()

    try:
        periodo = Periodo.objects.get(anio=int(periodo_anio), semestre=int(periodo_semestre))
    except (Periodo.DoesNotExist, ValueError):
        periodo = None

    if periodo:
        notas = Nota.objects.filter(curso=curso, periodo=periodo)
    else:
        notas = Nota.objects.filter(curso=curso)

    estudiantes_ids = notas.values_list('estudiante_id', flat=True).distinct()

    # Filtrar solo los que tienen riesgo medio o alto
    riesgos_qs = RiesgoEstudiante.objects.filter(
        estudiante__in=estudiantes_ids,
        nivel_riesgo__in=['high', 'medium']
    ).select_related('estudiante')

    total_en_riesgo = riesgos_qs.count()

    paginator = Paginator(list(riesgos_qs), page_size)
    page_obj  = paginator.get_page(page)

    estudiantes_data = []
    for riesgo in page_obj.object_list:
        est = riesgo.estudiante
        alertas_count = Alerta.objects.filter(estudiante=est, estado='activa').count()
        estudiantes_data.append({
            'codigo':        est.codigo,
            'nombre':        est.nombre,
            'nivel_riesgo':  riesgo.nivel_riesgo,
            'alertas_activas': alertas_count,
        })

    return JsonResponse({
        'curso': {
            'id': curso.id,
            'materia': curso.materia.nombre,
            'codigo': curso.materia.codigo,
            'grupo': curso.grupo,
        },
        'estudiantes': estudiantes_data,
        'total': total_en_riesgo,
        'page': page,
        'pages': paginator.num_pages,
        'page_size': page_size,
    })

