"""
academico/services/notas_corte.py

HU-31: desglose de las notas por corte (corte 1, 2 y 3 y examen final) de cada materia,
con las alertas tempranas por corte (HU-32) abiertas sobre esa materia y periodo.
Lo usan el historial académico y la consulta de notas por corte.
"""
from collections import defaultdict

from academico.constants import NOTA_APROBATORIA

ESTADO_EN_CURSO = 'En curso'


def _numero(valor):
    return float(valor) if valor is not None else None


def estado_nota(nota):
    """'Aprobado' / 'Reprobado' según la definitiva; 'En curso' si aún no hay definitiva."""
    if nota.definitiva is None:
        return ESTADO_EN_CURSO
    return 'Aprobado' if nota.definitiva >= NOTA_APROBATORIA else 'Reprobado'


def alertas_corte_abiertas(estudiante):
    """
    Alertas CORTE abiertas del estudiante agrupadas por (curso_id, 'AAAA-S').
    Una sola consulta para todo el historial.
    """
    from alertas.alertas_corte import ESTADOS_CERRADOS
    from alertas.models import Alerta

    agrupadas = defaultdict(list)
    alertas = (
        Alerta.objects
        .filter(estudiante=estudiante, regla__tipo='CORTE')
        .exclude(estado__in=ESTADOS_CERRADOS)
        .select_related('regla')
        .order_by('fecha_generacion')
    )
    for a in alertas:
        meta = a.metadata or {}
        agrupadas[(meta.get('curso_id'), meta.get('periodo'))].append({
            'id': a.id,
            'clave': meta.get('clave'),
            'regla': a.regla.nombre,
            'nivel': a.regla.nivel,
            'corte': meta.get('corte'),
            'valor_causa': _numero(a.valor_causa),
            'nota_necesaria': meta.get('nota_necesaria'),
            'estado': a.estado,
        })
    return agrupadas


def desglose_cortes(nota, alertas_por_curso):
    """Cortes, examen, nota necesaria en el examen y alertas por corte de una nota."""
    from alertas.alertas_corte import calcular_nota_necesaria

    cortes_completos = None not in (nota.corte1, nota.corte2, nota.corte3)
    nota_necesaria = None
    if cortes_completos and nota.examen_final is None:
        nota_necesaria = _numero(calcular_nota_necesaria(nota.corte1, nota.corte2, nota.corte3))

    periodo_str = f"{nota.periodo.anio}-{nota.periodo.semestre}"
    return {
        'corte1': _numero(nota.corte1),
        'corte2': _numero(nota.corte2),
        'corte3': _numero(nota.corte3),
        'examen_final': _numero(nota.examen_final),
        'nota_necesaria_examen': nota_necesaria,
        'alertas_corte': alertas_por_curso.get((nota.curso_id, periodo_str), []),
    }
