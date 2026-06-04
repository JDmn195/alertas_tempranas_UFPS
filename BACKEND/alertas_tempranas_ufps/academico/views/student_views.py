from django.http import JsonResponse
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt

from academico.models import Estudiante, Nota, Materia
from alertas.models import Alerta, Regla
from usuarios.decorators import requiere_rol



def calcular_nivel_riesgo(estudiante, promedio=None, reglas=None):
    """
    Calcula el nivel de riesgo de un estudiante basado en las reglas activas.
    Si no se pasan reglas, se consultan las activas de la BD.

    Retorna 'unknown' solo si el estudiante no tiene promedio ni notas
    registradas (no hay datos suficientes para evaluar ninguna regla).

    Si el estudiante no tiene notas, solo se evalúan reglas de PROMEDIO
    para evitar que el atraso calculado sobre materias sin historial
    dispare un nivel de riesgo incorrecto.
    """
    if promedio is None and hasattr(estudiante, 'promedio'):
        promedio = estudiante.promedio

    if reglas is None:
        reglas = list(Regla.objects.filter(activo=True))

    tiene_notas = Nota.objects.filter(estudiante=estudiante).exists()

    # Sin promedio y sin notas: no hay datos suficientes para evaluar
    if promedio is None and not tiene_notas:
        return 'unknown'

    # Ordenamos por nivel de severidad para retornar el más alto que aplique
    # high > medium > low
    orden_niveles = {'high': 3, 'medium': 2, 'low': 1}
    nivel_actual = 'low'
    valor_max_nivel = 0

    for regla in reglas:
        aplica = False
        valor_comparar = 0

        if regla.tipo == 'PROMEDIO':
            if promedio is None:
                continue  # No evaluar reglas de promedio si no hay promedio
            valor_comparar = float(promedio)
        elif regla.tipo == 'REPROBACION':
            if not tiene_notas:
                continue  # Sin notas, REPROBACION = 0 pero no es dato real
            valor_comparar = Nota.objects.filter(estudiante=estudiante, definitiva__lt=3.0).count()
        elif regla.tipo == 'ATRASO':
            if not tiene_notas:
                continue  # Sin notas, el atraso calculado sería espurio
            aprobadas_materia_ids = set(
                Nota.objects.filter(
                    estudiante=estudiante, definitiva__gte=3.0
                ).values_list('curso__materia_id', flat=True)
            )
            from academico.models import EquivalenciaMateria
            equiv_satisfechas = EquivalenciaMateria.objects.filter(
                materia_equivalente_id__in=aprobadas_materia_ids
            ).values_list('materia_pensum_id', flat=True)
            aprobadas_ids = aprobadas_materia_ids | set(equiv_satisfechas)
            valor_comparar = Materia.objects.filter(
                semestre__lt=estudiante.semestre
            ).exclude(codigo__in=aprobadas_ids).exclude(tipo__icontains='electiva').count()

        # Evaluación de la condición
        try:
            if regla.operador == '<': aplica = valor_comparar < float(regla.valor_umbral)
            elif regla.operador == '>': aplica = valor_comparar > float(regla.valor_umbral)
            elif regla.operador == '<=': aplica = valor_comparar <= float(regla.valor_umbral)
            elif regla.operador == '>=': aplica = valor_comparar >= float(regla.valor_umbral)
            elif regla.operador == '==': aplica = valor_comparar == float(regla.valor_umbral)
        except:
            continue

        if aplica:
            if orden_niveles.get(regla.nivel, 0) > valor_max_nivel:
                nivel_actual = regla.nivel
                valor_max_nivel = orden_niveles[regla.nivel]

    return nivel_actual


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
@requiere_rol(['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR', 'DIRECTOR'])
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

    # Filtro RBAC según rol del usuario (HU-27)
    if request.usuario.rol == 'DOCENTE':
        # Docente solo ve estudiantes que estén en sus cursos
        estudiantes_ids = Nota.objects.filter(curso__docente__usuario=request.usuario).values_list('estudiante_id', flat=True).distinct()
        qs = qs.filter(codigo__in=estudiantes_ids)

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
            filter=~Q(alerta__estado__in=['cerrada', 'closed']),
        )
    )

    # Obtener todos para poder filtrar por nivel de riesgo calculado
    # Optimizado: calcula nivel_riesgo solo con el promedio (sin queries extra por estudiante)
    # Las reglas de REPROBACION/ATRASO requieren queries individuales — se omiten aquí
    # para mantener O(1) queries totales. El perfil individual sí las calcula.
    reglas_promedio = [r for r in Regla.objects.filter(activo=True, tipo='PROMEDIO')]

    estudiantes_raw = qs.values(
        'codigo', 'nombre', 'semestre', 'promedio',
        'estado_matricula', 'total_alertas',
    )

    # ── Construcción de resultados con nivel de riesgo ────────────────────────
    orden_niveles = {'high': 3, 'medium': 2, 'low': 1}

    # Cargar el nivel de riesgo más reciente desde RiesgoEstudiantePeriodo para
    # todos los estudiantes en una sola query, con fallback a RiesgoEstudiante.
    from alertas.models import RiesgoEstudiantePeriodo as _REP, RiesgoEstudiante as _RE
    from django.db.models import Subquery as _SQ, OuterRef as _OR

    _ultimo_id_sq = (
        _REP.objects
        .filter(estudiante_id=_OR('estudiante_id'))
        .order_by('-periodo__anio', '-periodo__semestre')
        .values('id')[:1]
    )
    # Mapa codigo_estudiante → nivel_riesgo desde el periodo más reciente
    nivel_periodo_map = dict(
        _REP.objects
        .filter(id=_SQ(_ultimo_id_sq))
        .values_list('estudiante_id', 'nivel_riesgo')
    )
    # Mapa codigo_estudiante → nivel_riesgo desde snapshot (fallback)
    nivel_snap_map = dict(
        _RE.objects.values_list('estudiante_id', 'nivel_riesgo')
    )

    # Calcular PPA real desde notas para todos los estudiantes de la página
    # (solo promedio ponderado por créditos; sin N+1: una sola query agregada)
    from django.db.models import Sum as _Sum, Avg as _Avg, F as _F
    from decimal import Decimal

    def _ppa_desde_notas(codigos):
        """Devuelve dict codigo → ppa calculado desde notas."""
        from academico.models import Nota as _Nota
        rows = (
            _Nota.objects
            .filter(estudiante_id__in=codigos, definitiva__isnull=False)
            .values('estudiante_id')
            .annotate(
                puntos=_Sum(_F('definitiva') * _F('curso__materia__creditos')),
                creditos=_Sum('curso__materia__creditos'),
            )
        )
        result = {}
        for r in rows:
            if r['creditos']:
                result[r['estudiante_id']] = round(float(r['puntos']) / float(r['creditos']), 2)
        return result

    codigos_pagina = [e['codigo'] for e in estudiantes_raw]
    ppa_map = _ppa_desde_notas(codigos_pagina)

    def _nivel_por_promedio(promedio_val):
        if promedio_val is None:
            return 'unknown'
        nivel_actual = 'low'
        valor_max = 0
        for regla in reglas_promedio:
            try:
                v = float(promedio_val)
                u = float(regla.valor_umbral)
                aplica = (
                    (regla.operador == '<'  and v < u) or
                    (regla.operador == '>'  and v > u) or
                    (regla.operador == '<=' and v <= u) or
                    (regla.operador == '>=' and v >= u) or
                    (regla.operador == '==' and v == u)
                )
            except Exception:
                continue
            if aplica and orden_niveles.get(regla.nivel, 0) > valor_max:
                nivel_actual = regla.nivel
                valor_max = orden_niveles[regla.nivel]
        return nivel_actual

    results = []
    for e in estudiantes_raw:
        codigo = e['codigo']

        # Nivel de riesgo: usar el más reciente de RiesgoEstudiantePeriodo,
        # con fallback a RiesgoEstudiante snapshot, y como último recurso
        # calcular desde el PPA real.
        ppa_real = ppa_map.get(codigo)
        nivel = (
            nivel_periodo_map.get(codigo)
            or nivel_snap_map.get(codigo)
            or _nivel_por_promedio(ppa_real if ppa_real is not None else e['promedio'])
        )

        if risk and risk != nivel:
            continue

        results.append({
            'codigo':           codigo,
            'nombre':           e['nombre'],
            'semestre':         e['semestre'],
            'promedio':         ppa_real if ppa_real is not None else (float(e['promedio']) if e['promedio'] is not None else None),
            'nivel_riesgo':     nivel,
            'alertas_activas':  e['total_alertas'],
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
@requiere_rol(['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR', 'DIRECTOR'])
def obtener_detalle_estudiante(request, codigo):
    """
    GET /api/academico/students/<codigo>/
    Devuelve la información completa de un estudiante específico.
    """
    try:
        e = Estudiante.objects.get(codigo=codigo)
        
        # Filtro RBAC según rol del usuario (HU-27)
        if request.usuario.rol == 'DOCENTE':
            # Verificar si el docente tiene acceso a este estudiante
            tiene_acceso = Nota.objects.filter(estudiante=e, curso__docente__usuario=request.usuario).exists()
            if not tiene_acceso:
                from usuarios.utils import registrar_auditoria
                registrar_auditoria(request.usuario, 'ACCESO_DENEGADO', f"Docente intentó acceder al detalle del estudiante {codigo} sin tenerlo en sus cursos")
                return JsonResponse({'error': 'Prohibido. No tiene acceso a los datos de este estudiante.'}, status=403)

        # Anotar conteo de alertas activas
        total_alertas = Alerta.objects.filter(
            estudiante=e
        ).exclude(estado__in=['cerrada', 'closed']).count()
        # Fix 2.1/2.6: usar el nivel de riesgo del periodo más reciente calculado (RiesgoEstudiantePeriodo)
        # Si no hay registro por periodo, caer al snapshot RiesgoEstudiante
        nivel = 'unknown'
        try:
            ultimo_riesgo_periodo = (
                e.riesgos_por_periodo
                .select_related('periodo')
                .order_by('-periodo__anio', '-periodo__semestre')
                .first()
            )
            if ultimo_riesgo_periodo:
                nivel = ultimo_riesgo_periodo.nivel_riesgo
            else:
                nivel = e.riesgo.nivel_riesgo
        except Exception:
            nivel = calcular_nivel_riesgo(e)

        # Calcular PPA real desde notas (promedio ponderado por créditos)
        from django.db.models import Sum as _DSum, F as _DF
        _row = Nota.objects.filter(
            estudiante=e, definitiva__isnull=False
        ).aggregate(
            puntos=_DSum(_DF('definitiva') * _DF('curso__materia__creditos')),
            creditos=_DSum('curso__materia__creditos'),
        )
        if _row['creditos']:
            ppa_calculado = round(float(_row['puntos']) / float(_row['creditos']), 2)
        else:
            ppa_calculado = float(e.promedio) if e.promedio is not None else None

        return JsonResponse({
            'codigo':              e.codigo,
            'nombre':              e.nombre,
            'tipo_documento':      e.tipo_documento,
            'numero_documento':    e.numero_documento,
            'semestre':            e.semestre,
            'pensum':              e.pensum,
            'ingreso':             e.ingreso.isoformat() if e.ingreso else None,
            'promedio':            ppa_calculado,
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
    
    # 1. Total de créditos del programa (Valor fijo: 165)
    TOTAL_CREDITOS_SISTEMA = 165
    
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
    if TOTAL_CREDITOS_SISTEMA > 0:
        porcentaje = round((creditos_aprobados / TOTAL_CREDITOS_SISTEMA) * 100, 1)

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

    # 8. Alertas Activas (todo excepto cerradas)
    alertas_activas = Alerta.objects.filter(
        estudiante=estudiante
    ).exclude(estado__in=['cerrada', 'closed']).count()

    # 9. Evolución del riesgo por periodo (2.5)
    from alertas.models import RiesgoEstudiantePeriodo
    riesgo_evolucion = [
        {
            'periodo': f"{r.periodo.anio}-{r.periodo.semestre}",
            'nivel_riesgo': r.nivel_riesgo,
        }
        for r in RiesgoEstudiantePeriodo.objects.filter(
            estudiante=estudiante
        ).select_related('periodo').order_by('periodo__anio', 'periodo__semestre')
    ]

    return JsonResponse({
        'codigo': codigo,
        'indicadores': {
            'aprobadas': aprobadas_count,
            'reprobadas': reprobadas_count,
            'creditos_cursados': creditos_aprobados,
            'porcentaje_progreso': porcentaje,
            'total_sistema': TOTAL_CREDITOS_SISTEMA,
            'materias_repetidas': materias_repetidas,
            'promedio_acumulado': datos_promedio['promedio_acumulado'],
            'tendencia': datos_promedio['tendencia'],
            'evolucion': datos_promedio['evolucion'],
            'alertas_activas': alertas_activas,
            'riesgo_evolucion': riesgo_evolucion,
        }
    })


@require_GET
def obtener_historial_academico(request, codigo):
    """
    GET /api/academico/students/<codigo>/history/
    Devuelve el historial académico agrupado por periodos.
    """
    estudiante = get_object_or_404(Estudiante, codigo=codigo)
    notas = Nota.objects.filter(estudiante=estudiante).select_related(
        'periodo', 'curso__materia', 'curso__docente'
    ).order_by('periodo__anio', 'periodo__semestre')

    historial = {}

    for n in notas:
        periodo_str = f"{n.periodo.anio}-{n.periodo.semestre}"
        
        if periodo_str not in historial:
            historial[periodo_str] = {
                'periodo': periodo_str,
                'materias': [],
                'promedio_semestre': 0,
                'creditos_cursados': 0
            }

        creditos = n.curso.materia.creditos or 0
        definitiva = float(n.definitiva or 0)
        estado = 'Aprobado' if n.definitiva and n.definitiva >= 3.0 else 'Reprobado'
        
        materia_data = {
            'codigo': n.curso.materia.codigo,
            'materia': n.curso.materia.nombre,
            'creditos': creditos,
            'grupo': n.curso.grupo,
            'docente': n.curso.docente.nombre if n.curso.docente else 'Desconocido',
            'nota_final': definitiva,
            'estado': estado
        }
        
        historial[periodo_str]['materias'].append(materia_data)

    # Calcular los totales (promedio ponderado y créditos por semestre)
    resultados = []
    for p_str, datos in historial.items():
        total_puntos = 0
        total_creditos = 0
        
        for m in datos['materias']:
            total_puntos += m['nota_final'] * m['creditos']
            if m['estado'] == 'Aprobado':
                total_creditos += m['creditos']
                
        # Para el promedio se toman en cuenta los créditos de todas las materias cursadas
        creditos_cursados_semestre = sum(m['creditos'] for m in datos['materias'])
        promedio = round(total_puntos / creditos_cursados_semestre, 2) if creditos_cursados_semestre > 0 else 0
        
        datos['promedio_semestre'] = promedio
        datos['creditos_cursados'] = total_creditos # Solo aprobados según suelen calcular el progreso de pensum, o total?
        # Normalmente los créditos cursados incluye todos, y los aprobados son los ganados.
        datos['creditos_aprobados'] = total_creditos
        datos['creditos_intentados'] = creditos_cursados_semestre
        
        resultados.append(datos)

    return JsonResponse({
        'codigo': codigo,
        'historial': resultados
    })


@require_GET
def obtener_intervenciones_estudiante(request, codigo):
    """
    GET /api/academico/students/<codigo>/intervenciones/
    Devuelve el historial de intervenciones de un estudiante,
    ordenadas de forma descendente por fecha.
    """
    estudiante = get_object_or_404(Estudiante, codigo=codigo)
    
    from alertas.models import Intervencion
    intervenciones = Intervencion.objects.filter(alerta__estudiante=estudiante).select_related(
        'usuario', 'alerta__regla'
    ).order_by('-fecha')
    
    results = []
    for i in intervenciones:
        results.append({
            'id':            i.id,
            'tipo':          i.get_tipo_display(),
            'tipo_raw':      i.tipo,
            'observaciones': i.observaciones,
            'evidencia':     i.evidencia,
            'resultado':     i.resultado,
            'fecha':         i.fecha.strftime('%Y-%m-%d %H:%M'),
            'usuario':       i.usuario.nombre,
            'usuario_rol':   i.usuario.rol,
            'alerta_id':     i.alerta.id,
            'alerta_causa':  i.alerta.regla.nombre if i.alerta.regla else 'Alerta manual',
            'alerta_estado': i.alerta.estado,
        })
        
    return JsonResponse({
        'codigo': codigo,
        'intervenciones': results
    })

