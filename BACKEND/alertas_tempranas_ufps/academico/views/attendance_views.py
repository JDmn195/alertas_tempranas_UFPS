from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
import json
from datetime import date, datetime

from academico.models import Curso, Asistencia, Estudiante
from usuarios.decorators import requiere_rol
from usuarios.utils import registrar_auditoria
from academico.services.asistencia import (
    periodo_actual, normalizar_estado, estudiantes_del_curso, puede_gestionar_curso,
)

MAX_OBSERVACION = Asistencia._meta.get_field('observacion').max_length


def _evaluar_inasistencia_en_segundo_plano(curso, periodo, usuario):
    from alertas.alertas_inasistencia import evaluar_inasistencia_curso
    from alertas.tareas import ejecutar_en_segundo_plano

    ejecutar_en_segundo_plano(evaluar_inasistencia_curso, curso, periodo, usuario)


def _parsear_fecha(fecha_str):
    """Devuelve (fecha, None) o (None, JsonResponse) si la fecha falta, es inválida o es futura."""
    if not fecha_str:
        return None, JsonResponse({'status': 'error', 'mensaje': 'Debe proveer una fecha.'}, status=400)
    try:
        fecha_clase = datetime.strptime(str(fecha_str), '%Y-%m-%d').date()
    except ValueError:
        return None, JsonResponse({'status': 'error', 'mensaje': 'Formato de fecha inválido. Use AAAA-MM-DD.'}, status=400)
    if fecha_clase > date.today():
        return None, JsonResponse({'status': 'error', 'mensaje': 'No se puede registrar asistencia en una fecha futura.'}, status=400)
    return fecha_clase, None


@csrf_exempt
@requiere_rol(['DOCENTE', 'ADMINISTRADOR'])
def asistencia_curso(request, curso_id):
    """
    HU-33: /api/academico/cursos/<curso_id>/asistencia/

    GET ?fecha=AAAA-MM-DD: estudiantes matriculados en el periodo más reciente con su
    estado en esa fecha, y las fechas ya registradas del curso en ese periodo.
    POST {"fecha", "registros": [{"codigo_estudiante", "estado", "observacion"}]}:
    crea o actualiza los registros de esa fecha. Con un solo error no se guarda nada.
    """
    if request.method not in ('GET', 'POST'):
        return JsonResponse({'status': 'error', 'mensaje': 'Método no permitido.'}, status=405)

    usuario = request.usuario
    try:
        curso = Curso.objects.select_related('materia', 'docente').get(id=curso_id)
    except Curso.DoesNotExist:
        return JsonResponse({'error': 'El curso no existe.'}, status=404)

    if not puede_gestionar_curso(usuario, curso):
        registrar_auditoria(usuario, 'ACCESO_DENEGADO', f"Intento de registrar asistencia en el curso {curso_id}, no asignado al docente.")
        return JsonResponse({'error': 'Prohibido. El curso no está asignado a usted.'}, status=403)

    periodo = periodo_actual()
    if not periodo:
        return JsonResponse({'status': 'error', 'mensaje': 'No hay un periodo académico registrado.'}, status=400)

    if request.method == 'GET':
        return _consultar_asistencia(request, curso, periodo)
    return _registrar_asistencia(request, curso, periodo)


def _consultar_asistencia(request, curso, periodo):
    fecha_clase, error = _parsear_fecha(request.GET.get('fecha') or date.today().isoformat())
    if error:
        return error

    matriculados = estudiantes_del_curso(curso, periodo)
    estudiantes = Estudiante.objects.filter(codigo__in=matriculados).order_by('nombre')
    registros = {
        a.estudiante_id: a
        for a in Asistencia.objects.filter(curso=curso, fecha_clase=fecha_clase)
    }
    fechas_registradas = (
        Asistencia.objects.filter(curso=curso, periodo=periodo)
        .values_list('fecha_clase', flat=True)
        .distinct()
        .order_by('-fecha_clase')
    )

    return JsonResponse({
        'curso': {
            'id': curso.id,
            'materia': curso.materia.nombre,
            'codigo': curso.materia.codigo,
            'grupo': curso.grupo,
        },
        'periodo': str(periodo),
        'fecha': fecha_clase.isoformat(),
        'ya_registrada': bool(registros),
        'fechas_registradas': [f.isoformat() for f in fechas_registradas],
        'estudiantes': [
            {
                'codigo': est.codigo,
                'nombre': est.nombre,
                'estado': registros[est.codigo].estado if est.codigo in registros else None,
                'observacion': registros[est.codigo].observacion if est.codigo in registros else None,
            }
            for est in estudiantes
        ],
    })


def _registrar_asistencia(request, curso, periodo):
    usuario = request.usuario
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'status': 'error', 'mensaje': 'Cuerpo JSON inválido.'}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({'status': 'error', 'mensaje': 'Cuerpo JSON inválido.'}, status=400)

    fecha_clase, error = _parsear_fecha(data.get('fecha'))
    if error:
        return error

    registros = data.get('registros')
    if not registros or not isinstance(registros, list):
        return JsonResponse({'status': 'error', 'mensaje': 'Debe proveer una lista de registros.'}, status=400)

    matriculados = estudiantes_del_curso(curso, periodo)
    errores = []
    asistencias = []
    procesados = set()

    for reg in registros:
        if not isinstance(reg, dict):
            errores.append({'codigo_estudiante': None, 'campo': 'registro', 'mensaje': 'Registro inválido.'})
            continue

        codigo = str(reg.get('codigo_estudiante') or '').strip()
        estado_raw = reg.get('estado')
        observacion = reg.get('observacion')

        def _error(campo, mensaje):
            errores.append({'codigo_estudiante': codigo or None, 'campo': campo, 'mensaje': mensaje})

        if not codigo:
            _error('codigo_estudiante', 'Código de estudiante faltante.')
            continue
        if codigo in procesados:
            _error('codigo_estudiante', 'El estudiante está repetido en la petición.')
            continue
        procesados.add(codigo)

        if codigo not in matriculados:
            _error('codigo_estudiante', f'El estudiante no está matriculado en el curso en {periodo}.')
            continue

        estado = normalizar_estado(estado_raw)
        if not estado:
            _error('estado', f"Estado inválido: '{estado_raw}'. Use ASISTIO, FALTA o FALTA_JUSTIFICADA.")
            continue

        if observacion is not None and not isinstance(observacion, str):
            _error('observacion', 'La observación debe ser texto.')
            continue
        observacion = (observacion or '').strip() or None
        if observacion and len(observacion) > MAX_OBSERVACION:
            _error('observacion', f'La observación supera {MAX_OBSERVACION} caracteres.')
            continue

        asistencias.append(Asistencia(
            estudiante_id=codigo,
            curso=curso,
            periodo=periodo,
            fecha_clase=fecha_clase,
            estado=estado,
            observacion=observacion,
            registrado_por=usuario,
        ))

    if errores:
        return JsonResponse({'status': 'error', 'mensaje': 'Errores de validación. No se guardó ningún registro.', 'errores': errores}, status=400)

    with transaction.atomic():
        existentes = set(
            Asistencia.objects.filter(curso=curso, fecha_clase=fecha_clase)
            .values_list('estudiante_id', flat=True)
        )
        actualizados = sum(1 for a in asistencias if a.estudiante_id in existentes)
        creados = len(asistencias) - actualizados

        Asistencia.objects.bulk_create(
            asistencias,
            batch_size=500,
            update_conflicts=True,
            unique_fields=['estudiante', 'curso', 'fecha_clase'],
            update_fields=['estado', 'observacion', 'periodo', 'registrado_por', 'fecha_registro'],
        )
        registrar_auditoria(
            usuario,
            'REGISTRO_ASISTENCIA',
            f'Asistencia de {curso.materia.codigo}{curso.grupo} ({curso.materia.nombre}) del {fecha_clase.isoformat()}: '
            f'{creados} creados, {actualizados} actualizados.'
        )
        # HU-36: alertas por inasistencia del curso, en segundo plano tras confirmar
        transaction.on_commit(lambda: _evaluar_inasistencia_en_segundo_plano(curso, periodo, usuario))

    return JsonResponse({
        'status': 'success',
        'mensaje': 'Asistencia registrada correctamente.',
        'fecha': fecha_clase.isoformat(),
        'creados': creados,
        'actualizados': actualizados,
    })
