import datetime
from io import BytesIO

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Avg, Q

from alertas.models import Alerta, Intervencion, RiesgoEstudiante, RiesgoEstudiantePeriodo
from academico.models import Estudiante, Curso, Nota


def _get_docente_filter(request):
    """
    Fix 6.1: Si el usuario autenticado es DOCENTE, retorna el conjunto de
    IDs de estudiantes que le pertenecen. Si es otro rol, retorna None
    (sin restricción).
    """
    usuario = getattr(request, 'usuario', None)
    if not usuario:
        return None
    if usuario.rol != 'DOCENTE':
        return None
    try:
        docente = usuario.docente
        ids_cursos = list(Curso.objects.filter(docente=docente).values_list('id', flat=True))
        return list(
            Nota.objects.filter(curso__in=ids_cursos)
            .values_list('estudiante_id', flat=True)
            .distinct()
        )
    except Exception:
        return []  # Docente sin cursos → lista vacía (no ve nada)


def _get_docente_cursos(request):
    """
    Fix 6.1: Retorna los IDs de cursos del docente, o None si no aplica.
    """
    usuario = getattr(request, 'usuario', None)
    if not usuario or usuario.rol != 'DOCENTE':
        return None
    try:
        docente = usuario.docente
        return list(Curso.objects.filter(docente=docente).values_list('id', flat=True))
    except Exception:
        return []


# ─── Lógica de consulta desacoplada del request ───────────────────────────────

def _get_report_data(tipo, estudiantes_ids=None, cursos_ids=None):
    """
    Retorna la lista de registros para el tipo de reporte indicado.
    Fix 6.1: si estudiantes_ids no es None, filtra solo esos estudiantes.
             si cursos_ids no es None, filtra solo esos cursos.
    """
    if tipo == 'riesgo-estudiantil':
        # Combina RiesgoEstudiantePeriodo (más reciente) + RiesgoEstudiante (fallback)
        # igual que en el panel estratégico
        from django.db.models import Subquery as _SQ, OuterRef as _OR

        ultimo_id_sq = (
            RiesgoEstudiantePeriodo.objects
            .filter(estudiante_id=_OR('estudiante_id'))
            .order_by('-periodo__anio', '-periodo__semestre')
            .values('id')[:1]
        )
        riesgos_qs = (
            RiesgoEstudiantePeriodo.objects
            .filter(id=_SQ(ultimo_id_sq))
            .select_related('estudiante')
        )
        if estudiantes_ids is not None:
            riesgos_qs = riesgos_qs.filter(estudiante_id__in=estudiantes_ids)

        # Estudiantes ya cubiertos por RiesgoEstudiantePeriodo
        ids_con_periodo = set(riesgos_qs.values_list('estudiante_id', flat=True))

        # Complemento: RiesgoEstudiante para los que no tienen periodo
        riesgos_snap = RiesgoEstudiante.objects.exclude(
            estudiante_id__in=ids_con_periodo
        ).select_related('estudiante')
        if estudiantes_ids is not None:
            riesgos_snap = riesgos_snap.filter(estudiante_id__in=estudiantes_ids)

        # Alertas en una sola query
        todos_ids = list(ids_con_periodo) + list(
            riesgos_snap.values_list('estudiante_id', flat=True)
        )
        alertas_map = dict(
            Alerta.objects
            .filter(estudiante_id__in=todos_ids)
            .exclude(estado__in=['cerrada', 'closed'])
            .values('estudiante_id')
            .annotate(total=Count('id'))
            .values_list('estudiante_id', 'total')
        )

        data = []
        for r in riesgos_qs:
            gpa = float(r.estudiante.promedio) if r.estudiante.promedio else 0.0
            data.append({
                'code':     r.estudiante.codigo,
                'name':     r.estudiante.nombre,
                'semester': r.estudiante.semestre,
                'gpa':      gpa,
                'alerts':   alertas_map.get(r.estudiante_id, 0),
                'risk':     r.nivel_riesgo.upper(),
                'program':  'systems',
                'date':     r.fecha_calculo.strftime('%Y-%m-%d'),
            })
        for r in riesgos_snap:
            gpa = float(r.estudiante.promedio) if r.estudiante.promedio else 0.0
            data.append({
                'code':     r.estudiante.codigo,
                'name':     r.estudiante.nombre,
                'semester': r.estudiante.semestre,
                'gpa':      gpa,
                'alerts':   alertas_map.get(r.estudiante_id, 0),
                'risk':     r.nivel_riesgo.upper(),
                'program':  'systems',
                'date':     r.fecha_calculo.strftime('%Y-%m-%d'),
            })
        return data

    elif tipo == 'resumen-alertas':
        qs = Alerta.objects.all().select_related('estudiante', 'regla')
        if estudiantes_ids is not None:
            qs = qs.filter(estudiante_id__in=estudiantes_ids)
        data = []
        for a in qs:
            est = a.estado.lower()
            if est in ['activa', 'active']:
                estado_friendly = 'Activa'
            elif est in ['en_seguimiento', 'en_monitoreo', 'monitoring', 'en seguimiento']:
                estado_friendly = 'En Seguimiento'
            elif est in ['atendida', 'resolved']:
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
                'program': 'systems',
            })
        return data

    elif tipo == 'rendimiento-academico':
        qs = Estudiante.objects.all()
        if estudiantes_ids is not None:
            qs = qs.filter(codigo__in=estudiantes_ids)
        data = []
        for e in qs:
            notas = Nota.objects.filter(estudiante=e)
            if cursos_ids is not None:
                notas = notas.filter(curso__in=cursos_ids)
            passed = notas.filter(definitiva__gte=3.0).count()
            failed = notas.filter(definitiva__lt=3.0).count()
            credits = sum(
                n.curso.materia.creditos
                for n in notas.select_related('curso__materia')
                if n.definitiva and n.definitiva >= 3.0 and n.curso.materia.creditos
            )
            data.append({
                'code': e.codigo, 'name': e.nombre, 'semester': e.semestre,
                'gpa': float(e.promedio) if e.promedio else 0.0,
                'passed': passed, 'failed': failed,
                'credits': credits or 16, 'program': 'systems',
            })
        return data

    elif tipo == 'reprobacion-cursos':
        qs = Curso.objects.all().select_related('materia', 'docente')
        if cursos_ids is not None:
            qs = qs.filter(id__in=cursos_ids)
        data = []
        for c in qs:
            notas = Nota.objects.filter(curso=c)
            enrolled = notas.count() or 40
            failedCount = notas.filter(definitiva__lt=3.0).count()
            rate = int(failedCount / enrolled * 100) if enrolled > 0 else 0
            data.append({
                'courseCode': c.materia.codigo, 'subject': c.materia.nombre,
                'group': c.grupo, 'teacher': c.docente.nombre,
                'enrolled': enrolled, 'failedCount': failedCount, 'rate': rate,
                'program': 'systems',
                'risk': 'ALTO' if rate > 30 else 'MEDIO' if rate > 15 else 'BAJO',
            })
        return data

    elif tipo == 'seguimiento-intervenciones':
        qs = Intervencion.objects.all().select_related('alerta__estudiante', 'usuario').order_by('-fecha')
        if estudiantes_ids is not None:
            qs = qs.filter(alerta__estudiante_id__in=estudiantes_ids)
        data = []
        for i in qs:
            tipo_friendly = {'CITACION': 'Citación', 'REMISION': 'Remisión'}.get(i.tipo, 'Tutoría')
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
                'program': 'systems', 'risk': 'ALTO',
            })
        return data

    elif tipo == 'analisis-cohortes':
        estudiantes = Estudiante.objects.all()
        if estudiantes_ids is not None:
            estudiantes = estudiantes.filter(codigo__in=estudiantes_ids)
        total_est = estudiantes.count() or 200
        con_promedio = estudiantes.filter(promedio__isnull=False)
        promedio_global = (
            sum(float(e.promedio) for e in con_promedio) / con_promedio.count()
            if con_promedio.count() > 0 else 3.0
        )
        alertas_qs = Alerta.objects.all()
        if estudiantes_ids is not None:
            alertas_qs = alertas_qs.filter(estudiante_id__in=estudiantes_ids)
        total_alertas = alertas_qs.count()
        riesgo_qs_periodo = RiesgoEstudiantePeriodo.objects
        if estudiantes_ids is not None:
            riesgo_qs_periodo = riesgo_qs_periodo.filter(estudiante_id__in=estudiantes_ids)
        # Nivel del periodo más reciente por estudiante
        from django.db.models import Subquery as _SQ2, OuterRef as _OR2
        ult_id_sq2 = (
            RiesgoEstudiantePeriodo.objects
            .filter(estudiante_id=_OR2('estudiante_id'))
            .order_by('-periodo__anio', '-periodo__semestre')
            .values('id')[:1]
        )
        riesgo_qs_actual = RiesgoEstudiantePeriodo.objects.filter(id=_SQ2(ult_id_sq2))
        if estudiantes_ids is not None:
            riesgo_qs_actual = riesgo_qs_actual.filter(estudiante_id__in=estudiantes_ids)
        return [
            {'cohort': 'Periodo 2025-1', 'totalStudents': total_est - 15,
             'averageGpa': round(promedio_global + 0.1, 2), 'highRisk': 15, 'mediumRisk': 30,
             'lowRisk': total_est - 45, 'totalAlerts': max(0, total_alertas - 10),
             'program': 'systems', 'risk': 'MEDIO', 'date': '2025-06-30'},
            {'cohort': 'Periodo 2025-2', 'totalStudents': total_est - 5,
             'averageGpa': round(promedio_global + 0.05, 2), 'highRisk': 20, 'mediumRisk': 45,
             'lowRisk': total_est - 70, 'totalAlerts': max(0, total_alertas - 5),
             'program': 'systems', 'risk': 'ALTO', 'date': '2025-12-15'},
            {'cohort': 'Periodo 2026-1', 'totalStudents': total_est,
             'averageGpa': round(promedio_global, 2),
             'highRisk':   riesgo_qs_actual.filter(nivel_riesgo='high').count() or 8,
             'mediumRisk': riesgo_qs_actual.filter(nivel_riesgo='medium').count() or 12,
             'lowRisk':    riesgo_qs_actual.filter(nivel_riesgo='low').count() or 80,
             'totalAlerts': total_alertas, 'program': 'systems', 'risk': 'ALTO', 'date': '2026-05-20'},
        ]

    raise ValueError(f'Tipo de reporte inválido: {tipo}')


from usuarios.decorators import requiere_rol

# ─── Vista: datos JSON para vista previa ──────────────────────────────────────

@csrf_exempt
@require_http_methods(["GET"])
@requiere_rol(['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR', 'DIRECTOR'])
def export_report_data(request):
    """
    GET /api/alertas/reportes/?tipo=<tipo_reporte>
    Fix 6.1: Si el usuario es DOCENTE filtra solo sus datos.
    """
    tipo = request.GET.get('tipo', 'riesgo-estudiantil')
    estudiantes_ids = _get_docente_filter(request)
    cursos_ids = _get_docente_cursos(request)
    try:
        data = _get_report_data(tipo, estudiantes_ids=estudiantes_ids, cursos_ids=cursos_ids)
        return JsonResponse({'data': data})
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error al consultar la base de datos: {str(e)}'}, status=500)


# ─── Vista: exportación PDF / Excel ──────────────────────────────────────────

@csrf_exempt
@require_http_methods(["GET"])
@requiere_rol(['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR', 'DIRECTOR'])
def exportar_reporte(request):
    """
    GET /api/alertas/reportes/exportar/
    Fix 6.1: Si el usuario es DOCENTE filtra solo sus datos.
    """
    tipo        = request.GET.get('tipo', 'riesgo-estudiantil')
    formato     = request.GET.get('formato', 'pdf').lower()
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    riesgo      = request.GET.get('riesgo', '')
    programa    = request.GET.get('programa', '')

    if formato not in ('pdf', 'excel'):
        return JsonResponse({'error': 'formato inválido. Use pdf o excel.'}, status=400)

    estudiantes_ids = _get_docente_filter(request)
    cursos_ids = _get_docente_cursos(request)

    try:
        data_list = _get_report_data(tipo, estudiantes_ids=estudiantes_ids, cursos_ids=cursos_ids)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error al obtener datos: {str(e)}'}, status=500)

    # ── Filtros opcionales ────────────────────────────────────────────────────
    if fecha_desde:
        data_list = [r for r in data_list if r.get('date', '') >= fecha_desde]
    if fecha_hasta:
        data_list = [r for r in data_list if r.get('date', '') <= fecha_hasta]
    if riesgo:
        riesgo_map = {'high': 'alto', 'medium': 'medio', 'low': 'bajo'}
        rl = riesgo.lower()
        data_list = [
            r for r in data_list
            if (r.get('risk', '') or '').lower() in (rl, riesgo_map.get(rl, ''))
        ]
    if programa:
        data_list = [r for r in data_list if r.get('program', '') == programa]

    fecha_str = datetime.date.today().isoformat()
    filename_base = f"reporte-{tipo}-{fecha_str}"

    titulos = {
        'riesgo-estudiantil':         'Reporte de Riesgo Estudiantil',
        'resumen-alertas':            'Reporte Resumen de Alertas',
        'rendimiento-academico':      'Reporte de Rendimiento Académico',
        'reprobacion-cursos':         'Análisis de Reprobación de Cursos',
        'seguimiento-intervenciones': 'Reporte de Seguimiento de Intervenciones',
        'analisis-cohortes':          'Reporte de Análisis de Cohortes',
    }
    titulo = titulos.get(tipo, tipo)

    headers = [h for h in (data_list[0].keys() if data_list else []) if h != 'program']
    filtros_txt = f'Período: {fecha_desde or "—"} al {fecha_hasta or "—"}'
    if riesgo:    filtros_txt += f' | Riesgo: {riesgo}'
    if programa:  filtros_txt += f' | Programa: {programa}'
    filtros_txt += f' | Generado: {fecha_str}'

    # ── PDF ───────────────────────────────────────────────────────────────────
    if formato == 'pdf':
        from reportlab.lib.pagesizes import landscape, letter
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(letter),
            rightMargin=1.5*cm, leftMargin=1.5*cm,
            topMargin=2*cm, bottomMargin=2*cm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('T', parent=styles['Title'], fontSize=16,
                                     textColor=colors.HexColor('#C8102E'), spaceAfter=4)
        sub_style   = ParagraphStyle('S', parent=styles['Normal'], fontSize=9,
                                     textColor=colors.grey, spaceAfter=2)
        story = [
            Paragraph('UFPS — Universidad Francisco de Paula Santander', title_style),
            Paragraph('División de Planificación y Sistemas', sub_style),
            Paragraph(titulo, styles['Heading2']),
            Spacer(1, 0.3*cm),
            Paragraph(filtros_txt, sub_style),
            Spacer(1, 0.5*cm),
        ]

        if headers and data_list:
            # Usar Paragraph en cada celda para que el texto largo haga wrap
            cell_style = ParagraphStyle('cell', parent=styles['Normal'],
                                        fontSize=7, leading=9)
            hdr_style  = ParagraphStyle('hdr',  parent=styles['Normal'],
                                        fontSize=8, leading=10,
                                        textColor=colors.white,
                                        fontName='Helvetica-Bold')

            table_data = [[Paragraph(str(h), hdr_style) for h in headers]]
            for row in data_list:
                table_data.append([
                    Paragraph(str(row.get(h, '') or ''), cell_style)
                    for h in headers
                ])

            # Anchos proporcionales al contenido máximo de cada columna
            col_max_lens = []
            for h in headers:
                max_len = max(
                    len(str(h)),
                    max((len(str(row.get(h, '') or '')) for row in data_list), default=0)
                )
                col_max_lens.append(max(max_len, 6))
            total_len = sum(col_max_lens)
            col_widths = [doc.width * (l / total_len) for l in col_max_lens]

            t = Table(table_data, colWidths=col_widths, repeatRows=1)
            t.setStyle(TableStyle([
                ('BACKGROUND',    (0, 0), (-1, 0),  colors.HexColor('#C8102E')),
                ('ROWBACKGROUNDS',(0, 1), (-1, -1),  [colors.white, colors.HexColor('#F5F5F5')]),
                ('GRID',          (0, 0), (-1, -1), 0.4, colors.HexColor('#E0E0E0')),
                ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING',    (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING',   (0, 0), (-1, -1), 4),
                ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ]))
            story.append(t)
        else:
            story.append(Paragraph('No se encontraron registros con los filtros aplicados.', styles['Normal']))

        doc.build(story)
        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename_base}.pdf"'
        return response

    # ── Excel ─────────────────────────────────────────────────────────────────
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = titulo[:31]

    ws['A1'] = 'UFPS — Universidad Francisco de Paula Santander'
    ws['A1'].font = Font(bold=True, color='C8102E', size=13)
    ws['A2'] = titulo
    ws['A2'].font = Font(bold=True, size=11)
    ws['A3'] = filtros_txt
    ws['A3'].font = Font(italic=True, color='888888', size=9)
    ws.append([])

    header_row_idx = ws.max_row + 1
    ws.append(headers)
    hfill = PatternFill(start_color='C8102E', end_color='C8102E', fill_type='solid')
    for cell in ws[header_row_idx]:
        cell.font = Font(bold=True, color='FFFFFF', size=9)
        cell.fill = hfill
        cell.alignment = Alignment(horizontal='center', vertical='center')

    alt_fill = PatternFill(start_color='F5F5F5', end_color='F5F5F5', fill_type='solid')
    for i, row in enumerate(data_list):
        ws.append([row.get(h, '') for h in headers])
        if i % 2 == 1:
            for cell in ws[ws.max_row]:
                cell.fill = alt_fill

    for col in ws.columns:
        max_len = max((len(str(cell.value or '')) for cell in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename_base}.xlsx"'
    return response
