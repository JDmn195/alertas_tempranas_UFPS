"""
HU-36: Alertas por inasistencia.

Genera una alerta cuando el porcentaje de inasistencia de un estudiante en un curso
supera el umbral del curso (o el general de la regla INASISTENCIA activa), solo en el
periodo más reciente. Mismo ciclo de vida que las alertas por corte (alertas_corte.py):
una alerta abierta por estudiante + regla + curso + periodo, actualización mientras siga
aplicando y cierre automático cuando baja del umbral.

La inasistencia también es un factor del nivel de riesgo por periodo (factor_inasistencia).
"""
import logging

from django.db import transaction

from academico.asistencia import (
    calcular_inasistencia, calcular_inasistencia_curso, calcular_inasistencia_cursos,
    calcular_inasistencia_por_curso, numero_o_none, obtener_umbral_inasistencia,
    obtener_umbrales_inasistencia, umbral_efectivo,
)
from academico.models import Asistencia, Curso, Estudiante, Periodo
from academico.services.asistencia import periodo_actual
from alertas.alertas_corte import ESTADOS_CERRADOS, _cumple_operador
from alertas.models import Alerta, Regla
from alertas.services import NotificationService
from usuarios.utils import registrar_auditoria

logger = logging.getLogger(__name__)

MOTIVO_CIERRE = 'Inasistencia por debajo del umbral'


def obtener_regla_inasistencia():
    """Regla INASISTENCIA activa (la misma que da el umbral general) o None."""
    return Regla.objects.filter(tipo='INASISTENCIA', activo=True).order_by('id').first()


def _min_clases(regla):
    valor = (regla.parametros or {}).get('min_clases')
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else 0


def supera_umbral_regla(regla, resultado, umbral):
    """
    True/False si el porcentaje cumple el operador de la regla frente al umbral.
    None si no se evalúa: sin umbral, sin clases o con menos clases que min_clases.
    """
    if umbral is None or resultado['porcentaje'] is None:
        return None
    if resultado['total_clases'] < _min_clases(regla):
        return None
    return _cumple_operador(resultado['porcentaje'], regla.operador, umbral)


def _texto_periodo(periodo):
    return f"{periodo.anio}-{periodo.semestre}"


def _es_periodo_reciente(periodo):
    reciente = periodo_actual()
    return reciente is not None and periodo is not None and getattr(periodo, 'pk', periodo) == reciente.pk


def _metadata(curso, periodo_str, resultado, umbral, origen):
    return {
        'curso_id': curso.pk,
        'materia_codigo': curso.materia.codigo,
        'materia_nombre': curso.materia.nombre,
        'grupo': curso.grupo,
        'periodo': periodo_str,
        'porcentaje': numero_o_none(resultado['porcentaje']),
        'umbral': numero_o_none(umbral),
        'origen_umbral': origen,
        'total_clases': resultado['total_clases'],
        'faltas': resultado['faltas'],
        'faltas_justificadas': resultado['faltas_justificadas'],
    }


def _notificar_al_confirmar(alerta_id):
    def _enviar():
        try:
            alerta = Alerta.objects.select_related('estudiante', 'regla').get(id=alerta_id)
            NotificationService.notificar_alerta(alerta)
        except Exception as e:
            logger.error("Error al notificar alerta por inasistencia %s: %s", alerta_id, e, exc_info=True)

    transaction.on_commit(_enviar)


def _recalcular_riesgo(estudiante):
    from alertas.views.alert_generation_views import calcular_y_guardar_riesgo_por_periodos

    if not isinstance(estudiante, Estudiante):
        estudiante = Estudiante.objects.get(pk=estudiante)
    calcular_y_guardar_riesgo_por_periodos(estudiante)


def _procesar(regla, estudiante, curso, periodo_str, resultado, umbral, origen, abierta, usuario):
    """
    Crea, actualiza o cierra la alerta de un estudiante en un curso. Se llama dentro
    de la transacción del estudiante. Retorna la alerta afectada o None.
    """
    supera = supera_umbral_regla(regla, resultado, umbral)
    if supera is None:
        return None  # sin umbral o con menos clases que min_clases: no se crea ni se cierra nada

    codigo = getattr(estudiante, 'pk', estudiante)
    curso_txt = f"{curso.materia.codigo}-{curso.grupo}"

    if supera:
        metadata = _metadata(curso, periodo_str, resultado, umbral, origen)
        if abierta:
            if abierta.valor_causa != resultado['porcentaje'] or abierta.metadata != metadata:
                abierta.valor_causa = resultado['porcentaje']
                abierta.metadata = metadata
                abierta.save(update_fields=['valor_causa', 'metadata'])
            return abierta

        nueva = Alerta.objects.create(
            estudiante_id=codigo,
            regla=regla,
            estado='activa',
            valor_causa=resultado['porcentaje'],
            metadata=metadata,
        )
        registrar_auditoria(
            usuario,
            'GENERAR_ALERTAS',
            f"Alerta generada por regla '{regla.nombre}' para estudiante {codigo} en curso {curso_txt}: "
            f"{resultado['porcentaje']}% de inasistencia (umbral {umbral}%, {origen})."
        )
        _recalcular_riesgo(estudiante)
        _notificar_al_confirmar(nueva.id)
        return nueva

    if abierta:
        abierta.estado = 'cerrada'
        meta = abierta.metadata or {}
        meta.update(_metadata(curso, periodo_str, resultado, umbral, origen))
        meta['cierre_automatico'] = True
        meta['motivo_cierre'] = MOTIVO_CIERRE
        abierta.metadata = meta
        abierta.valor_causa = resultado['porcentaje']
        abierta.save()  # Dispara post_save (cancelación de recordatorios)
        registrar_auditoria(
            usuario,
            'CERRAR_ALERTA',
            f"Alerta ID {abierta.id} de regla '{regla.nombre}' cerrada automáticamente. Motivo: {MOTIVO_CIERRE}."
        )
        _recalcular_riesgo(estudiante)
        return abierta
    return None


def _alertas_abiertas(regla, periodo_str, curso_ids):
    """Alertas abiertas de la regla en el periodo: {(estudiante_id, curso_id): alerta}."""
    qs = (
        Alerta.objects.filter(regla=regla, metadata__periodo=periodo_str)
        .exclude(estado__in=ESTADOS_CERRADOS)
    )
    if len(curso_ids) == 1:
        qs = qs.filter(metadata__curso_id=next(iter(curso_ids)))
    abiertas = {}
    for alerta in qs:
        curso_id = (alerta.metadata or {}).get('curso_id')
        if curso_id in curso_ids:
            abiertas.setdefault((alerta.estudiante_id, curso_id), alerta)
    return abiertas


def _evaluar_cursos(regla, periodo, cursos, resultados, umbrales, usuario):
    """
    cursos: instancias de Curso (con materia); resultados: {curso_id: {codigo: resultado}};
    umbrales: {curso_id: (umbral, origen)}. Cada estudiante va en su propia transacción.
    """
    periodo_str = _texto_periodo(periodo)
    abiertas = _alertas_abiertas(regla, periodo_str, {c.pk for c in cursos})
    afectadas = []
    for curso in cursos:
        umbral, origen = umbrales[curso.pk]
        for codigo, resultado in resultados.get(curso.pk, {}).items():
            try:
                with transaction.atomic():
                    alerta = _procesar(regla, codigo, curso, periodo_str, resultado, umbral, origen,
                                       abiertas.get((codigo, curso.pk)), usuario)
            except Exception as e:
                # Un estudiante con datos problemáticos no detiene a los demás
                logger.error("Error al evaluar inasistencia de %s en el curso %s: %s",
                             codigo, curso.pk, e, exc_info=True)
                continue
            if alerta:
                afectadas.append(alerta)
    return afectadas


def evaluar_inasistencia(estudiante, curso, periodo, usuario=None):
    """Evalúa la inasistencia de un estudiante en un curso. Retorna la lista de alertas afectadas."""
    regla = obtener_regla_inasistencia()
    if regla is None or not _es_periodo_reciente(periodo):
        return []

    periodo_str = _texto_periodo(periodo)
    resultado = calcular_inasistencia(estudiante, curso, periodo)
    umbral, origen = obtener_umbral_inasistencia(curso)
    abierta = _alertas_abiertas(regla, periodo_str, {curso.pk}).get((estudiante.pk, curso.pk))
    with transaction.atomic():
        alerta = _procesar(regla, estudiante, curso, periodo_str, resultado, umbral, origen, abierta, usuario)
    return [alerta] if alerta else []


def evaluar_inasistencia_curso(curso, periodo, usuario=None):
    """
    Evalúa a todos los matriculados del curso con una sola consulta de asistencia
    (calcular_inasistencia_curso). Acepta instancias o ids de curso y periodo.
    """
    regla = obtener_regla_inasistencia()
    if regla is None or not _es_periodo_reciente(periodo):
        return []

    if not isinstance(curso, Curso):
        curso = Curso.objects.select_related('materia').get(pk=curso)
    if not isinstance(periodo, Periodo):
        periodo = Periodo.objects.get(pk=periodo)

    resultados = {curso.pk: calcular_inasistencia_curso(curso, periodo)}
    umbrales = {curso.pk: obtener_umbral_inasistencia(curso)}
    return _evaluar_cursos(regla, periodo, [curso], resultados, umbrales, usuario)


def evaluar_inasistencia_periodo_actual(usuario=None):
    """Evalúa todos los cursos con asistencia registrada en el periodo más reciente."""
    regla = obtener_regla_inasistencia()
    periodo = periodo_actual()
    if regla is None or periodo is None:
        return []

    cursos = list(
        Curso.objects.filter(asistencias__periodo=periodo).distinct().select_related('materia')
    )
    if not cursos:
        return []
    resultados = calcular_inasistencia_cursos([c.pk for c in cursos], periodo)
    umbrales = obtener_umbrales_inasistencia(cursos)
    return _evaluar_cursos(regla, periodo, cursos, resultados, umbrales, usuario)


def periodos_con_asistencia(estudiante):
    return set(Asistencia.objects.filter(estudiante=estudiante).values_list('periodo_id', flat=True).distinct())


def factor_inasistencia(estudiante, periodo, regla):
    """
    Entrada para reglas_aplicadas si el estudiante supera el umbral en al menos un curso
    del periodo (respetando min_clases y el operador de la regla), o None.
    """
    cursos = list(
        Curso.objects.filter(asistencias__estudiante=estudiante, asistencias__periodo=periodo)
        .distinct().select_related('materia')
    )
    if not cursos:
        return None

    resultados = calcular_inasistencia_por_curso(estudiante, periodo, [c.pk for c in cursos])
    sobre_umbral = []
    for curso in cursos:
        umbral, _ = umbral_efectivo(curso.umbral_inasistencia, regla.valor_umbral)
        resultado = resultados[curso.pk]
        if supera_umbral_regla(regla, resultado, umbral):
            sobre_umbral.append({
                'curso_id': curso.pk,
                'materia_codigo': curso.materia.codigo,
                'grupo': curso.grupo,
                'porcentaje': numero_o_none(resultado['porcentaje']),
                'umbral': numero_o_none(umbral),
            })
    if not sobre_umbral:
        return None
    return {
        'id': regla.id,
        'nombre': regla.nombre,
        'nivel': regla.nivel,
        'valor': max(c['porcentaje'] for c in sobre_umbral),
        'tipo': 'INASISTENCIA',
        'cursos': sobre_umbral,
    }
