"""
academico/asistencia.py

HU-34: Cálculo del porcentaje de inasistencia por estudiante, curso y periodo.

Porcentaje = faltas sin justificar / clases registradas x 100 (Decimal, 2 decimales).
Las faltas justificadas cuentan como clase registrada pero no como falta.
Sin clases registradas el porcentaje es None, no 0.

HU-35: el umbral es parametrizable. El general es el valor_umbral de la regla
INASISTENCIA activa y cada curso puede tener el suyo (Curso.umbral_inasistencia).

Criterio del Sprint 5: se advierte cuando el porcentaje se aproxima al umbral, es decir,
cuando alcanza PORCENTAJE_AVISO_PREVENTIVO % del umbral sin superarlo.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, F, Q

from academico.models import Asistencia, Nota
from alertas.models import Regla

ORIGEN_UMBRAL_CURSO = 'curso'
ORIGEN_UMBRAL_GENERAL = 'general'

# Porción del umbral desde la que se considera que el estudiante se aproxima a él
PORCENTAJE_AVISO_PREVENTIVO = Decimal('80')

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


def obtener_umbral_general():
    """valor_umbral de la regla INASISTENCIA activa, o None si no hay ninguna activa."""
    return (
        Regla.objects.filter(tipo='INASISTENCIA', activo=True)
        .order_by('id').values_list('valor_umbral', flat=True).first()
    )


def umbral_efectivo(umbral_curso, umbral_general):
    """(umbral, origen) a partir del umbral propio del curso y del general."""
    if umbral_curso is not None:
        return umbral_curso, ORIGEN_UMBRAL_CURSO
    if umbral_general is not None:
        return umbral_general, ORIGEN_UMBRAL_GENERAL
    return None, None


def obtener_umbral_inasistencia(curso):
    """
    Umbral de inasistencia que aplica al curso: (umbral, origen).
    origen es "curso" si el curso tiene umbral propio y "general" si se usa el de
    la regla INASISTENCIA activa. Sin ninguno de los dos devuelve (None, None).
    """
    if curso.umbral_inasistencia is not None:
        return umbral_efectivo(curso.umbral_inasistencia, None)
    return umbral_efectivo(None, obtener_umbral_general())


def obtener_umbrales_inasistencia(cursos):
    """
    Umbral de varios cursos (instancias de Curso) consultando la regla una sola vez:
    {curso_id: (umbral, origen)}.
    """
    general = obtener_umbral_general()
    return {curso.pk: umbral_efectivo(curso.umbral_inasistencia, general) for curso in cursos}


def supera_umbral(porcentaje, umbral):
    """True/False si el porcentaje supera el umbral; None si no hay umbral configurado."""
    if umbral is None:
        return None
    return porcentaje is not None and porcentaje > umbral


def umbral_aviso(umbral):
    """Porcentaje de inasistencia desde el que se advierte la aproximación al umbral."""
    if umbral is None:
        return None
    return (Decimal(str(umbral)) * PORCENTAJE_AVISO_PREVENTIVO / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def cerca_umbral(porcentaje, umbral):
    """
    True si el porcentaje alcanza el umbral de aviso sin superar el umbral; None sin umbral.
    Un 0 % nunca está cerca (umbral 0 haría avisar a todos).
    """
    if umbral is None:
        return None
    if porcentaje is None or porcentaje <= 0 or supera_umbral(porcentaje, umbral):
        return False
    return porcentaje >= umbral_aviso(umbral)


def numero_o_none(valor):
    return float(valor) if valor is not None else None


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
