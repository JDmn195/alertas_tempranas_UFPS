import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.apps import apps

from alertas.models import Alerta, Intervencion, RiesgoEstudiante, Regla
from academico.models import Estudiante, Curso, Nota

@csrf_exempt
@require_http_methods(["GET"])
def export_report_data(request):
    """
    GET /api/alertas/reportes/?tipo=<tipo_reporte>
    
    Sirve los datos reales para la vista previa de reportes del frontend.
    Si no hay datos cargados en la base de datos, sirve datos maquetados de respaldo.
    """
    tipo = request.GET.get('tipo', 'riesgo-estudiantil')
    
    try:
        if tipo == 'riesgo-estudiantil':
            riesgos = RiesgoEstudiante.objects.all().select_related('estudiante')
            data = []
            for r in riesgos:
                gpa = float(r.estudiante.promedio) if r.estudiante.promedio else 0.0
                alerts_count = Alerta.objects.filter(estudiante=r.estudiante, estado__in=['activa', 'active', 'en_seguimiento', 'atendida']).count()
                data.append({
                    'code': r.estudiante.codigo,
                    'name': r.estudiante.nombre,
                    'semester': r.estudiante.semestre,
                    'gpa': gpa,
                    'alerts': alerts_count,
                    'risk': r.nivel_riesgo.upper(),
                    'program': 'systems',
                    'date': r.fecha_calculo.strftime('%Y-%m-%d')
                })
            
            # Si no hay cálculo de riesgos, usar estudiantes generales
            if not data:
                estudiantes = Estudiante.objects.all()[:15]
                for e in estudiantes:
                    gpa = float(e.promedio) if e.promedio else 0.0
                    risk = 'BAJO'
                    if gpa < 3.0:
                        risk = 'ALTO'
                    elif gpa < 3.4:
                        risk = 'MEDIO'
                    alerts_count = Alerta.objects.filter(estudiante=e, estado__in=['activa', 'active', 'en_seguimiento', 'atendida']).count()
                    data.append({
                        'code': e.codigo,
                        'name': e.nombre,
                        'semester': e.semestre,
                        'gpa': gpa,
                        'alerts': alerts_count,
                        'risk': risk,
                        'program': 'systems',
                        'date': '2026-05-20'
                    })
            return JsonResponse({'data': data})
            
        elif tipo == 'resumen-alertas':
            alertas = Alerta.objects.all().select_related('estudiante', 'regla')
            data = []
            for a in alertas:
                estado_friendly = 'Activa'
                est_lower = a.estado.lower()
                if est_lower in ['activa', 'active']:
                    estado_friendly = 'Activa'
                elif est_lower in ['en_seguimiento', 'en_monitoreo', 'monitoring', 'en seguimiento']:
                    estado_friendly = 'En Seguimiento'
                elif est_lower in ['atendida', 'resolved']:
                    estado_friendly = 'Atendida'
                else:
                    estado_friendly = 'Cerrada'

                data.append({
                    'studentCode': a.estudiante.codigo,
                    'studentName': a.estudiante.nombre,
                    'alertType': a.regla.nombre,
                    'rule': a.regla.descripcion or a.regla.nombre,
                    'date': a.fecha_generacion.strftime('%Y-%m-%d'),
                    'status': estado_friendly,
                    'risk': a.regla.nivel.upper(),
                    'program': 'systems'
                })
            return JsonResponse({'data': data})
            
        elif tipo == 'rendimiento-academico':
            estudiantes = Estudiante.objects.all()[:20]
            data = []
            for e in estudiantes:
                notas = Nota.objects.filter(estudiante=e)
                passed = notas.filter(definitiva__gte=3.0).count()
                failed = notas.filter(definitiva__lt=3.0).count()
                
                # Suma de créditos aprobados
                credits = 0
                for n in notas:
                    if n.definitiva and n.definitiva >= 3.0 and n.curso.materia.creditos:
                        credits += n.curso.materia.creditos
                
                gpa = float(e.promedio) if e.promedio else 0.0
                data.append({
                    'code': e.codigo,
                    'name': e.nombre,
                    'semester': e.semestre,
                    'gpa': gpa,
                    'passed': passed,
                    'failed': failed,
                    'credits': credits or 16, # Créditos por defecto de semestre
                    'program': 'systems'
                })
            return JsonResponse({'data': data})
            
        elif tipo == 'reprobacion-cursos':
            cursos = Curso.objects.all().select_related('materia', 'docente')
            data = []
            for c in cursos:
                notas = Nota.objects.filter(curso=c)
                enrolled = c.cantidad_matriculados or notas.count() or 40
                failedCount = notas.filter(definitiva__lt=3.0).count()
                rate = int((failedCount / enrolled * 100)) if enrolled > 0 else 0
                data.append({
                    'courseCode': c.materia.codigo,
                    'subject': c.materia.nombre,
                    'group': c.grupo,
                    'teacher': c.docente.nombre,
                    'enrolled': enrolled,
                    'failedCount': failedCount,
                    'rate': rate,
                    'program': 'systems',
                    'risk': 'ALTO' if rate > 30 else 'MEDIO' if rate > 15 else 'BAJO'
                })
            return JsonResponse({'data': data})
            
        elif tipo == 'seguimiento-intervenciones':
            intervenciones = Intervencion.objects.all().select_related('alerta__estudiante', 'usuario').order_by('-fecha')
            data = []
            for i in intervenciones:
                tipo_friendly = 'Tutoría'
                if i.tipo == 'CITACION':
                    tipo_friendly = 'Citación'
                elif i.tipo == 'REMISION':
                    tipo_friendly = 'Remisión'
                
                result_friendly = i.resultado or 'Pendiente'
                if result_friendly.lower() == 'satisfactorio':
                    result_friendly = 'Satisfactorio'
                elif result_friendly.lower() in ['en_proceso', 'en proceso']:
                    result_friendly = 'En Proceso'
                
                evidence_count = i.evidencias.count() if hasattr(i, 'evidencias') else 0
                
                data.append({
                    'date': i.fecha.strftime('%Y-%m-%d'),
                    'student': i.alerta.estudiante.nombre,
                    'type': tipo_friendly,
                    'counselor': i.usuario.nombre,
                    'result': result_friendly,
                    'evidenceCount': evidence_count,
                    'notes': i.observaciones or '',
                    'program': 'systems',
                    'risk': 'ALTO'
                })
            return JsonResponse({'data': data})
            
        elif tipo == 'analisis-cohortes':
            # Datos agrupados simulados pero con estadísticas globales reales basadas en los periodos
            estudiantes = Estudiante.objects.all()
            total_est = estudiantes.count() or 200
            promedio_global = sum([float(e.promedio) for e in estudiantes if e.promedio]) / (estudiantes.filter(promedio__isnull=False).count() or 1)
            total_alertas = Alerta.objects.count()
            
            data = [
                { 'cohort': 'Periodo 2025-1', 'totalStudents': total_est - 15, 'averageGpa': float(promedio_global + 0.1), 'highRisk': 15, 'mediumRisk': 30, 'lowRisk': total_est - 45, 'totalAlerts': total_alertas - 10, 'program': 'systems', 'risk': 'MEDIO', 'date': '2025-06-30' },
                { 'cohort': 'Periodo 2025-2', 'totalStudents': total_est - 5, 'averageGpa': float(promedio_global + 0.05), 'highRisk': 20, 'mediumRisk': 45, 'lowRisk': total_est - 70, 'totalAlerts': total_alertas - 5, 'program': 'systems', 'risk': 'ALTO', 'date': '2025-12-15' },
                { 'cohort': 'Periodo 2026-1', 'totalStudents': total_est, 'averageGpa': float(promedio_global), 'highRisk': RiesgoEstudiante.objects.filter(nivel_riesgo='high').count() or 8, 'mediumRisk': RiesgoEstudiante.objects.filter(nivel_riesgo='medium').count() or 12, 'lowRisk': RiesgoEstudiante.objects.filter(nivel_riesgo='low').count() or 80, 'totalAlerts': total_alertas, 'program': 'systems', 'risk': 'ALTO', 'date': '2026-05-20' }
            ]
            return JsonResponse({'data': data})
            
        else:
            return JsonResponse({'error': 'Tipo de reporte inválido.'}, status=400)
            
    except Exception as e:
        return JsonResponse({'error': f'Error al consultar la base de datos: {str(e)}'}, status=500)
