from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
import json
from datetime import datetime

from academico.models import Curso, Asistencia
from usuarios.decorators import requiere_rol
from usuarios.utils import registrar_auditoria
from academico.services.asistencia import periodo_desde_fecha, normalizar_estado, estudiantes_del_curso

@csrf_exempt
@requiere_rol(['DOCENTE'])
def asistencia_docente(request, curso_id):
    usuario = request.usuario
    try:
        docente = usuario.docente
    except Exception:
        return JsonResponse({'error': 'El usuario no tiene perfil de docente.'}, status=404)

    try:
        curso = Curso.objects.get(id=curso_id, docente=docente)
    except Curso.DoesNotExist:
        return JsonResponse({'error': 'El curso no existe o no está asignado a usted.'}, status=404)

    if request.method == 'GET':
        fecha_str = request.GET.get('fecha')
        if not fecha_str:
            return JsonResponse({'status': 'error', 'mensaje': 'Debe proveer una fecha.'}, status=400)
        
        try:
            fecha_clase = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'status': 'error', 'mensaje': 'Formato de fecha inválido. Use YYYY-MM-DD.'}, status=400)
            
        if fecha_clase > datetime.now().date():
            return JsonResponse({'status': 'error', 'mensaje': 'No se pueden registrar asistencias para fechas futuras.'}, status=400)

        periodo = periodo_desde_fecha(fecha_clase)
        if not periodo:
            return JsonResponse({'status': 'error', 'mensaje': 'No existe un periodo académico configurado para esta fecha.'}, status=400)

        estudiantes_ids = estudiantes_del_curso(curso, periodo)
        
        from academico.models import Estudiante
        estudiantes = Estudiante.objects.filter(codigo__in=estudiantes_ids).order_by('nombre')
        
        asistencias = Asistencia.objects.filter(curso=curso, fecha_clase=fecha_clase)
        asistencias_map = {a.estudiante_id: a.estado for a in asistencias}
        
        estudiantes_data = []
        for est in estudiantes:
            estudiantes_data.append({
                'codigo': est.codigo,
                'nombre': est.nombre,
                'estado': asistencias_map.get(est.codigo, None)
            })
            
        return JsonResponse({
            'curso': {
                'id': curso.id,
                'materia': curso.materia.nombre,
                'codigo': curso.materia.codigo,
                'grupo': curso.grupo
            },
            'fecha': fecha_str,
            'periodo': {
                'anio': periodo.anio,
                'semestre': periodo.semestre
            },
            'ya_registrada': len(asistencias) > 0,
            'estudiantes': estudiantes_data
        })

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            fecha_str = data.get('fecha')
            registros = data.get('registros', [])
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'mensaje': 'Cuerpo JSON inválido.'}, status=400)

        if not fecha_str:
            return JsonResponse({'status': 'error', 'mensaje': 'Debe proveer una fecha.'}, status=400)

        try:
            fecha_clase = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'status': 'error', 'mensaje': 'Formato de fecha inválido. Use YYYY-MM-DD.'}, status=400)
            
        if fecha_clase > datetime.now().date():
            return JsonResponse({'status': 'error', 'mensaje': 'No se pueden registrar asistencias para fechas futuras.'}, status=400)

        periodo = periodo_desde_fecha(fecha_clase)
        if not periodo:
            return JsonResponse({'status': 'error', 'mensaje': 'No existe un periodo académico configurado para esta fecha.'}, status=400)

        if not registros or not isinstance(registros, list):
            return JsonResponse({'status': 'error', 'mensaje': 'Debe proveer una lista de registros.'}, status=400)

        estudiantes_validos = estudiantes_del_curso(curso, periodo)
        
        errores = []
        asistencias_objs = []
        codigos_procesados = set()

        for idx, reg in enumerate(registros):
            codigo = reg.get('codigo')
            estado_raw = reg.get('estado')
            
            if not codigo:
                errores.append(f'Registro {idx}: Código de estudiante faltante.')
                continue
                
            if codigo in codigos_procesados:
                errores.append(f'Registro {idx}: Código {codigo} duplicado en la petición.')
                continue
            
            if codigo not in estudiantes_validos:
                errores.append(f'Registro {idx}: Estudiante {codigo} no pertenece al curso en este periodo.')
                continue
                
            estado_norm = normalizar_estado(estado_raw)
            if not estado_norm:
                errores.append(f'Registro {idx}: Estado {estado_raw} inválido para {codigo}.')
                continue
                
            codigos_procesados.add(codigo)
            asistencias_objs.append(
                Asistencia(
                    estudiante_id=codigo,
                    curso=curso,
                    periodo=periodo,
                    fecha_clase=fecha_clase,
                    estado=estado_norm,
                    registrado_por=usuario
                )
            )

        if errores:
            return JsonResponse({'status': 'error', 'mensaje': 'Errores de validación', 'errores': errores}, status=400)

        if asistencias_objs:
            with transaction.atomic():
                Asistencia.objects.bulk_create(
                    asistencias_objs,
                    batch_size=500,
                    update_conflicts=True,
                    unique_fields=['estudiante_id', 'curso_id', 'fecha_clase'],
                    update_fields=['estado', 'periodo', 'registrado_por']
                )
                registrar_auditoria(
                    usuario,
                    'REGISTRO_ASISTENCIA',
                    f'Registro de asistencia para curso {curso.materia.nombre} grupo {curso.grupo} en {fecha_str}. Registros: {len(asistencias_objs)}'
                )

        return JsonResponse({'status': 'success', 'mensaje': 'Asistencia registrada correctamente.', 'registrados': len(asistencias_objs)})

    return JsonResponse({'status': 'error', 'mensaje': 'Método no permitido.'}, status=405)
