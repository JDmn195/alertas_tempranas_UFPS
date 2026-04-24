from django.http import JsonResponse
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt

from academico.models import Estudiante, Nota, Materia
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


def _calcular_historial_promedios(estudiante):
    """
    Calcula el PPS (Semestral) y PPA (Acumulado) periodo a periodo.
    """
    notas = Nota.objects.filter(estudiante=estudiante).select_related(
        'periodo', 'curso__materia'
    ).order_by('periodo__anio', 'periodo__semestre')
    
    # Agrupar por periodo preservando el orden cronológico
    periodos_dict = {}
    for n in notas:
        key = f"{n.periodo.anio}-{n.periodo.semestre}"
        if key not in periodos_dict:
            periodos_dict[key] = []
        periodos_dict[key].append(n)
        
    evolucion = []
    puntos_acumulados = 0
    creditos_acumulados = 0
    
    for periodo_key, notas_periodo in periodos_dict.items():
        puntos_semestre = 0
        creditos_semestre = 0
        
        for n in notas_periodo:
            creditos = n.curso.materia.creditos or 0
            definitiva = float(n.definitiva or 0)
            puntos_semestre += definitiva * creditos
            creditos_semestre += creditos
            
        pps = round(puntos_semestre / creditos_semestre, 2) if creditos_semestre > 0 else 0
        
        puntos_acumulados += puntos_semestre
        creditos_acumulados += creditos_semestre
        
        ppa = round(puntos_acumulados / creditos_acumulados, 2) if creditos_acumulados > 0 else 0
        
        evolucion.append({
            'periodo': periodo_key,
            'pps': pps,
            'ppa': ppa
        })
        
    # Tendencia: comparativa del último PPA contra el anterior
    promedio_actual = evolucion[-1]['ppa'] if evolucion else 0
    tendencia = { 'valor': 0, 'porcentaje': 0, 'direccion': 'stable' }
    
    if len(evolucion) >= 2:
        prev_ppa = evolucion[-2]['ppa']
        if prev_ppa > 0:
            diff = promedio_actual - prev_ppa
            porcentaje = (diff / prev_ppa) * 100
            
            tendencia['valor'] = round(diff, 2)
            tendencia['porcentaje'] = round(abs(porcentaje), 1)
            if diff > 0.01:
                tendencia['direccion'] = 'up'
            elif diff < -0.01:
                tendencia['direccion'] = 'down'
            else:
                tendencia['direccion'] = 'stable'
                
    return {
        'promedio_acumulado': promedio_actual,
        'tendencia': tendencia,
        'evolucion': evolucion
    }


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


@csrf_exempt
@require_GET
def obtener_detalle_estudiante(request, codigo):
    """
    GET /api/academico/students/<codigo>/
    Devuelve la información completa de un estudiante específico.
    """
    try:
        e = Estudiante.objects.get(codigo=codigo)
        
        # Anotar conteo de alertas activas
        total_alertas = Alerta.objects.filter(estudiante=e, estado='activa').count()
        nivel = calcular_nivel_riesgo(e.promedio)

        return JsonResponse({
            'codigo':              e.codigo,
            'nombre':              e.nombre,
            'tipo_documento':      e.tipo_documento,
            'numero_documento':    e.numero_documento,
            'semestre':            e.semestre,
            'pensum':              e.pensum,
            'ingreso':             e.ingreso.isoformat() if e.ingreso else None,
            'promedio':            float(e.promedio) if e.promedio is not None else None,
            'estado_matricula':    e.estado_matricula,
            'celular':             e.celular,
            'email_personal':      e.email_personal,
            'email_institucional': e.email_institucional,
            'colegio_egresado':    e.colegio_egresado,
            'municipio_nacimiento': e.municipio_nacimiento,
            'nivel_riesgo':        nivel,
            'alertas_activas':     total_alertas,
        })
    except Estudiante.DoesNotExist:
        return JsonResponse({'error': f'Estudiante con código {codigo} no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def obtener_indicadores_estudiante(request, codigo):
    """
    Calcula los indicadores académicos para un estudiante específico:
    - Materias aprobadas
    - Materias reprobadas
    - Créditos cursados (aprobados)
    - Porcentaje de progreso basado en el total de créditos del sistema
    """
    estudiante = get_object_or_404(Estudiante, codigo=codigo)
    
    # 1. Total de créditos disponibles en el sistema
    total_creditos_sistema = Materia.objects.aggregate(total=Sum('creditos'))['total'] or 0
    
    # 2. Obtener todas las notas del estudiante
    notas_qs = Nota.objects.filter(estudiante=estudiante)
    
    # 3. Conteo de materias (histórico)
    aprobadas_count = notas_qs.filter(definitiva__gte=3.0).count()
    reprobadas_count = notas_qs.filter(definitiva__lt=3.0).count()
    
    # 4. Créditos cursados (solo de materias aprobadas)
    creditos_aprobados = notas_qs.filter(definitiva__gte=3.0).aggregate(
        total=Sum('curso__materia__creditos')
    )['total'] or 0
    
    # 5. Calcular porcentaje
    porcentaje = 0
    if total_creditos_sistema > 0:
        porcentaje = round((creditos_aprobados / total_creditos_sistema) * 100, 1)

    # 6. Identificar materias repetidas
    materias_dict = {}
    for nota in notas_qs.select_related('curso__materia', 'periodo').order_by('periodo__anio', 'periodo__semestre'):
        nombre_mat = nota.curso.materia.nombre
        if nombre_mat not in materias_dict:
            materias_dict[nombre_mat] = []
        
        materias_dict[nombre_mat].append({
            'periodo': f"{nota.periodo.anio}-{nota.periodo.semestre}",
            'nota': float(nota.definitiva) if nota.definitiva else 0,
            'estado': 'Aprobado' if nota.definitiva >= 3.0 else 'Reprobado'
        })
    
    materias_repetidas = []
    for nombre, intentos in materias_dict.items():
        if len(intentos) > 1:
            materias_repetidas.append({
                'nombre': nombre,
                'veces': len(intentos),
                'intentos': intentos
            })
        
    # 7. Promedios y Evolución
    datos_promedio = _calcular_historial_promedios(estudiante)
    
    # 8. Alertas Activas
    alertas_activas = Alerta.objects.filter(estudiante=estudiante, estado='activa').count()
        
    return JsonResponse({
        'codigo': codigo,
        'indicadores': {
            'aprobadas': aprobadas_count,
            'reprobadas': reprobadas_count,
            'creditos_cursados': creditos_aprobados,
            'porcentaje_progreso': porcentaje,
            'total_sistema': total_creditos_sistema,
            'materias_repetidas': materias_repetidas,
            'promedio_acumulado': datos_promedio['promedio_acumulado'],
            'tendencia': datos_promedio['tendencia'],
            'evolucion': datos_promedio['evolucion'],
            'alertas_activas': alertas_activas
        }
    })
