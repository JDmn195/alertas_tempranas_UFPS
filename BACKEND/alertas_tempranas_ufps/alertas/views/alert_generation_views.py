import json
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Q, Count
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404

from academico.models import Estudiante, Nota
from alertas.models import Regla, Alerta, RiesgoEstudiante
from academico.views.student_views import calcular_nivel_riesgo
from alertas.services import NotificationService

def reprocesar_alertas_completas(estudiantes_qs=None):
    """
    Función de servicio para (re)generar alertas y riesgos.
    Se puede llamar desde vistas de importación o manualmente.
    """
    reglas = Regla.objects.filter(activo=True).order_by('-prioridad')
    if estudiantes_qs is None:
        # Evaluar a todos los estudiantes que no estén retirados o graduados
        estudiantes_qs = Estudiante.objects.exclude(
            Q(estado_matricula__icontains='retirado') | 
            Q(estado_matricula__icontains='graduado') |
            Q(estado_matricula__icontains='cancelado')
        )
    
    nuevas_alertas = 0
    actualizados = 0
    por_nivel = {'high': 0, 'medium': 0, 'low': 0, 'unknown': 0}

    with transaction.atomic():
        for est in estudiantes_qs:
            # 0. Limpieza de alertas activas sin intervenciones para evitar duplicidad
            Alerta.objects.filter(
                estudiante=est, 
                estado__in=['activa', 'active']
            ).annotate(n_int=Count('intervencion')).filter(n_int=0).delete()

            nivel = calcular_nivel_riesgo(est, est.promedio, reglas)
            por_nivel[nivel] = por_nivel.get(nivel, 0) + 1
            
            # 1. Evaluar reglas
            reglas_por_tipo = {}
            for r in reglas:
                aplica = False
                val = 0
                metadata_regla = {}

                if r.tipo == 'PROMEDIO': 
                    val = float(est.promedio) if est.promedio else 0
                    metadata_regla = {'promedio': val}
                elif r.tipo == 'REPROBACION': 
                    reprobadas_qs = Nota.objects.filter(estudiante=est, definitiva__lt=3.0).select_related('curso__materia')
                    val = reprobadas_qs.count()
                    metadata_regla = {'materias': [n.curso.materia.nombre for n in reprobadas_qs]}
                elif r.tipo == 'ATRASO':
                    from academico.models import Materia
                    tiene_notas = Nota.objects.filter(estudiante=est).exists()
                    
                    if tiene_notas:
                        aprobadas_ids = Nota.objects.filter(estudiante=est, definitiva__gte=3.0).values_list('curso__materia_id', flat=True)
                        atrasadas_qs = Materia.objects.filter(semestre__lt=est.semestre).exclude(codigo__in=aprobadas_ids)
                        
                        val = atrasadas_qs.count()
                        metadata_regla = {
                            'semestre_actual': est.semestre, 
                            'materias_atrasadas': [m.nombre for m in atrasadas_qs],
                            'total_atrasadas': val
                        }
                    else:
                        val = 0
                        metadata_regla = {}
                
                try:
                    if r.operador == '<': aplica = val < float(r.valor_umbral)
                    elif r.operador == '>': aplica = val > float(r.valor_umbral)
                    elif r.operador == '<=': aplica = val <= float(r.valor_umbral)
                    elif r.operador == '>=': aplica = val >= float(r.valor_umbral)
                    elif r.operador == '==': aplica = val == float(r.valor_umbral)
                except: continue
                
                if aplica:
                    # Guardamos solo la más prioritaria por tipo (PROMEDIO, REPROBACION, ATRASO)
                    if r.tipo not in reglas_por_tipo:
                        reglas_por_tipo[r.tipo] = {
                            'id': r.id, 
                            'nombre': r.nombre, 
                            'nivel': r.nivel,
                            'valor': val,
                            'metadata': metadata_regla
                        }
            
            reglas_que_aplican = list(reglas_por_tipo.values())
            
            # 2. Persistir RiesgoEstudiante
            RiesgoEstudiante.objects.update_or_create(
                estudiante=est,
                defaults={
                    'nivel_riesgo': nivel,
                    'reglas_aplicadas': reglas_que_aplican
                }
            )
            actualizados += 1

            # 3. Generar Alertas
            for r_app in reglas_que_aplican:
                nueva_alerta = Alerta.objects.create(
                    estudiante=est,
                    regla_id=r_app['id'],
                    estado='activa',
                    valor_causa=r_app['valor'],
                    metadata=r_app['metadata']
                )
                NotificationService.notificar_alerta(nueva_alerta)
                nuevas_alertas += 1

    return {
        'total_evaluados': estudiantes_qs.count(),
        'actualizados': actualizados,
        'nuevas_alertas': nuevas_alertas,
        'estudiantes_por_nivel': por_nivel
    }

@csrf_exempt
@require_http_methods(["POST"])
def generar_alertas(request):
    """
    POST /api/alertas/generar/
    """
    try:
        resultado = reprocesar_alertas_completas()
        return JsonResponse({
            'mensaje': 'Proceso de generación completado',
            **resultado
        })
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(["GET"])
def listar_alertas(request):
    """
    GET /api/alertas/
    """
    estado = request.GET.get('estado', 'activa')
    tipo_regla = request.GET.get('tipo_regla')
    
    qs = Alerta.objects.select_related('estudiante', 'regla').order_by('-fecha_generacion')
    
    if estado:
        mapping = {'activa': ['activa', 'active'], 'en_monitoreo': ['en_monitoreo', 'monitoring'], 'atendida': ['atendida', 'atended'], 'cerrada': ['cerrada', 'closed']}
        target_states = mapping.get(estado.lower(), [estado])
        qs = qs.filter(estado__in=target_states)
        
    if tipo_regla and tipo_regla != 'all':
        qs = qs.filter(regla__tipo=tipo_regla)
        
    total_qs = Alerta.objects.all()
    conteos = {
        'activa': total_qs.filter(estado__in=['activa', 'active']).count(),
        'en_monitoreo': total_qs.filter(estado__in=['en_monitoreo', 'monitoring']).count(),
        'atendida': total_qs.filter(estado__in=['atendida', 'atended']).count(),
        'cerrada': total_qs.filter(estado__in=['cerrada', 'closed']).count(),
    }

    data = []
    for a in qs:
        data.append({
            'id': a.id,
            'studentName': a.estudiante.nombre,
            'studentCode': a.estudiante.codigo,
            'riskLevel': a.regla.nivel,
            'alertType': a.regla.nombre,
            'generatedDate': a.fecha_generacion.strftime('%Y-%m-%d'),
            'status': a.estado,
            'tipo_regla': a.regla.tipo,
            'valor_causa': float(a.valor_causa) if a.valor_causa else None,
            'metadata': a.metadata
        })
        
    return JsonResponse({
        'alertas': data,
        'conteos': conteos
    }, safe=False)

@csrf_exempt
@require_http_methods(["POST"])
def cerrar_alerta(request, alerta_id):
    """
    POST /api/alertas/<id>/cerrar/
    Cierra una alerta directamente.
    """
    alerta = get_object_or_404(Alerta, id=alerta_id)
    alerta.estado = 'cerrada'
    alerta.save()
    return JsonResponse({'mensaje': 'Alerta cerrada correctamente'})
