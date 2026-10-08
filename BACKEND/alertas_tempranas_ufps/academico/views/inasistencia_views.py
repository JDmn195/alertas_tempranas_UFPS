from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from academico.asistencia import (
    calcular_inasistencia_curso, calcular_inasistencia_por_curso, cerca_umbral, numero_o_none, umbral_aviso,
    obtener_umbral_general, obtener_umbral_inasistencia, obtener_umbrales_inasistencia, supera_umbral,
)
from academico.models import Asistencia, Curso, Estudiante, Nota, Periodo
from academico.services.asistencia import normalizar_estado, periodo_actual
from academico.views.student_views import _acceso_denegado_docente
from usuarios.decorators import requiere_rol
from usuarios.utils import registrar_auditoria

ROLES_CONSULTA = ['ADMINISTRADOR', 'DIRECTOR', 'BIENESTAR', 'DOCENTE']


def _porcentaje_json(porcentaje):
    return float(porcentaje) if porcentaje is not None else None


def _parsear_periodo(valor):
    """'2026-2' -> (Periodo, None); (None, JsonResponse 400) si no existe o está mal formado."""
    try:
        anio, semestre = (int(p) for p in str(valor).split('-'))
        return Periodo.objects.get(anio=anio, semestre=semestre), None
    except (ValueError, Periodo.DoesNotExist):
        return None, JsonResponse({'error': f'Periodo inválido o inexistente: {valor}. Use AAAA-S.'}, status=400)


def _parsear_entero(valor, campo):
    try:
        return int(valor), None
    except (TypeError, ValueError):
        return None, JsonResponse({'error': f'El parámetro {campo} debe ser un número.'}, status=400)


@csrf_exempt
@require_GET
@requiere_rol(ROLES_CONSULTA)
def inasistencia_estudiante(request, codigo):
    """
    HU-34: GET /api/academico/students/<codigo>/asistencia/?curso=&periodo=

    Porcentaje de inasistencia del estudiante por curso en un periodo, con el detalle por fecha.
    Sin periodo usa el más reciente en que el estudiante está matriculado.
    Un docente solo ve los cursos que dicta.
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
        'umbral':               numero_o_none(obtener_umbral_general()),  # HU-35: general
        'cursos':               [],
    }
    if not periodo:
        return JsonResponse(respuesta)

    notas = (
        Nota.objects.filter(estudiante=estudiante, periodo=periodo)
        .select_related('curso__materia')
        .order_by('curso__materia__nombre', 'curso__grupo')
    )
    if request.usuario.rol == 'DOCENTE':
        notas = notas.filter(curso__docente__usuario=request.usuario)
    if request.GET.get('curso'):
        curso_id, error = _parsear_entero(request.GET['curso'], 'curso')
        if error:
            return error
        notas = notas.filter(curso_id=curso_id)
    notas = list(notas)
    ids_cursos = [n.curso_id for n in notas]

    totales = calcular_inasistencia_por_curso(estudiante, periodo, ids_cursos)
    umbrales = obtener_umbrales_inasistencia([n.curso for n in notas])
    detalle = {}
    registros = Asistencia.objects.filter(estudiante=estudiante, periodo=periodo, curso__in=ids_cursos)
    for a in registros.order_by('fecha_clase'):
        detalle.setdefault(a.curso_id, []).append({
            'fecha':       a.fecha_clase.isoformat(),
            'estado':      a.estado,
            'observacion': a.observacion,
        })

    for nota in notas:
        curso = nota.curso
        datos = totales[curso.id]
        umbral, origen_umbral = umbrales[curso.id]
        respuesta['cursos'].append({
            'curso_id':     curso.id,
            'materia':      curso.materia.nombre,
            'codigo':       curso.materia.codigo,
            'grupo':        curso.grupo,
            **datos,
            'porcentaje':   _porcentaje_json(datos['porcentaje']),
            'umbral':        numero_o_none(umbral),
            'origen_umbral': origen_umbral,
            'supera_umbral': supera_umbral(datos['porcentaje'], umbral),
            'cerca_umbral':  cerca_umbral(datos['porcentaje'], umbral),
            'umbral_aviso':  numero_o_none(umbral_aviso(umbral)),
            'detalle':      detalle.get(curso.id, []),
        })
    return JsonResponse(respuesta)


@csrf_exempt
@require_GET
@requiere_rol(ROLES_CONSULTA)
def inasistencia_curso(request, curso_id):
    """
    HU-34: GET /api/academico/cursos/<curso_id>/inasistencia/?periodo=&estado=

    Porcentaje de inasistencia de cada matriculado del curso. Sin periodo usa el más
    reciente. Con estado, solo los estudiantes con al menos un registro en ese estado.
    Un docente solo puede consultar los cursos que dicta.
    """
    try:
        curso = Curso.objects.select_related('materia', 'docente').get(id=curso_id)
    except Curso.DoesNotExist:
        return JsonResponse({'error': 'El curso no existe.'}, status=404)

    usuario = request.usuario
    if usuario.rol == 'DOCENTE' and curso.docente.usuario_id != usuario.id:
        registrar_auditoria(usuario, 'ACCESO_DENEGADO', f"Intento de consultar la inasistencia del curso {curso_id}, no asignado al docente.")
        return JsonResponse({'error': 'Prohibido. El curso no está asignado a usted.'}, status=403)

    if request.GET.get('periodo'):
        periodo, error = _parsear_periodo(request.GET['periodo'])
        if error:
            return error
    else:
        periodo = periodo_actual()
        if not periodo:
            return JsonResponse({'error': 'No hay un periodo académico registrado.'}, status=400)

    inasistencia = calcular_inasistencia_curso(curso, periodo)

    estado = None
    if request.GET.get('estado'):
        estado = normalizar_estado(request.GET['estado'])
        if not estado:
            return JsonResponse({'error': 'Estado inválido. Use ASISTIO, FALTA o FALTA_JUSTIFICADA.'}, status=400)
        con_estado = set(
            Asistencia.objects.filter(curso=curso, periodo=periodo, estado=estado)
            .values_list('estudiante_id', flat=True)
        )
        inasistencia = {c: d for c, d in inasistencia.items() if c in con_estado}

    umbral, origen_umbral = obtener_umbral_inasistencia(curso)
    nombres = dict(Estudiante.objects.filter(codigo__in=inasistencia).values_list('codigo', 'nombre'))
    estudiantes = []
    for codigo, datos in inasistencia.items():
        estudiantes.append({
            'codigo':        codigo,
            'nombre':        nombres.get(codigo, ''),
            **datos,
            'porcentaje':    _porcentaje_json(datos['porcentaje']),
            'supera_umbral': supera_umbral(datos['porcentaje'], umbral),
            'cerca_umbral':  cerca_umbral(datos['porcentaje'], umbral),
        })
    estudiantes.sort(key=lambda e: e['nombre'])

    return JsonResponse({
        'curso': {
            'id':      curso.id,
            'materia': curso.materia.nombre,
            'codigo':  curso.materia.codigo,
            'grupo':   curso.grupo,
        },
        'periodo':     str(periodo),
        'estado':      estado,
        'umbral':        numero_o_none(umbral),
        'origen_umbral': origen_umbral,
        # HU-35: null cuando no hay umbral configurado
        'total_sobre_umbral': (
            None if umbral is None else sum(1 for e in estudiantes if e['supera_umbral'])
        ),
        'umbral_aviso':       numero_o_none(umbral_aviso(umbral)),
        'total_cerca_umbral': (
            None if umbral is None else sum(1 for e in estudiantes if e['cerca_umbral'])
        ),
        'estudiantes': estudiantes,
    })
