"""
academico/asistencia.py

HU-34: Cálculo del porcentaje de inasistencia por estudiante, curso y periodo.

Porcentaje = faltas sin justificar / clases registradas x 100 (Decimal, 2 decimales).
Las faltas justificadas cuentan como clase registrada pero no como falta.
Sin clases registradas el porcentaje es None, no 0.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, F, Q

from academico.models import Asistencia, Nota


# Temporal: la HU-35 la reemplaza por el umbral parametrizado.
UMBRAL_INASISTENCIA_POR_DEFECTO = 20

_ESTADOS = {
    'asistencias':         'ASISTIO',
    'faltas':              'FALTA',
    'faltas_justificadas': 'FALTA_JUSTIFICADA',
}
_AGREGADOS = {
    'total_clases': Count('id'),
    **{clave: Count('id', filter=Q(estado=estado)) for clave, estado in _ESTADOS.items()},
}


def calcular_porcentaje(faltas, total_clases):
    """Porcentaje de inasistencia redondeado a 2 decimales, o None sin clases registradas."""
    if not total_clases:
        return None
    return (Decimal(faltas) * 100 / Decimal(total_clases)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def supera_umbral(porcentaje, umbral=UMBRAL_INASISTENCIA_POR_DEFECTO):
    return porcentaje is not None and porcentaje > umbral


def _resultado(fila=None):
    fila = fila or {}
    total = fila.get('total_clases', 0)
    faltas = fila.get('faltas', 0)
    return {
        'total_clases':        total,
        'asistencias':         fila.get('asistencias', 0),
        'faltas':              faltas,
        'faltas_justificadas': fila.get('faltas_justificadas', 0),
        'porcentaje':          calcular_porcentaje(faltas, total),
    }


def calcular_inasistencia(estudiante, curso, periodo):
    """Totales y porcentaje de inasistencia de un estudiante en un curso y periodo."""
    fila = Asistencia.objects.filter(
        estudiante=estudiante, curso=curso, periodo=periodo,
    ).aggregate(**_AGREGADOS)
    return _resultado(fila)


def calcular_inasistencia_por_curso(estudiante, periodo, cursos):
    """Inasistencia de un estudiante en varios cursos de un periodo: {curso_id: resultado}."""
    filas = (
        Asistencia.objects.filter(estudiante=estudiante, periodo=periodo, curso__in=cursos)
        .values('curso_id')
        .annotate(**_AGREGADOS)
    )
    por_curso = {fila['curso_id']: fila for fila in filas}
    return {curso_id: _resultado(por_curso.get(curso_id)) for curso_id in cursos}


def calcular_inasistencia_cursos(cursos, periodo):
    """
    Inasistencia de todos los matriculados (Nota en curso y periodo) de varios cursos,
    en una sola consulta agregada sin importar cuántos cursos o estudiantes haya.
    Devuelve {curso_id: {codigo_estudiante: resultado}}; los matriculados sin
    registros aparecen con total_clases 0 y porcentaje None.
    """
    # Nota -> Estudiante -> Asistencia, contando solo los registros del mismo curso y periodo
    mismo_curso = Q(
        estudiante__asistencias__curso_id=F('curso_id'),
        estudiante__asistencias__periodo_id=F('periodo_id'),
    )
    agregados = {
        'total_clases': Count('estudiante__asistencias', filter=mismo_curso),
    }
    for clave, estado in _ESTADOS.items():
        agregados[clave] = Count(
            'estudiante__asistencias',
            filter=mismo_curso & Q(estudiante__asistencias__estado=estado),
        )

    filas = (
        Nota.objects.filter(curso__in=cursos, periodo=periodo)
        .values('curso_id', 'estudiante_id')
        .annotate(**agregados)
    )
    resultado = {}
    for fila in filas:
        resultado.setdefault(fila['curso_id'], {})[fila['estudiante_id']] = _resultado(fila)
    return resultado


def calcular_inasistencia_curso(curso, periodo):
    """Inasistencia de cada matriculado del curso: {codigo_estudiante: resultado}."""
    curso_id = getattr(curso, 'pk', curso)
    return calcular_inasistencia_cursos([curso_id], periodo).get(curso_id, {})
