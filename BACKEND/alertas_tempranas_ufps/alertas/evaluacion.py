"""
Cálculo único de los indicadores académicos (PPA, materias reprobadas, atraso)
y de la evaluación de reglas de riesgo.

Lo usan el nivel de riesgo, la generación/re-evaluación de alertas y las
importaciones, para que todos lleguen al mismo resultado con los mismos datos.
"""
from decimal import Decimal

from django.db.models import Avg, F, Q, Sum

from academico.models import EquivalenciaMateria, Materia, Nota

ORDEN_NIVELES = {'high': 3, 'medium': 2, 'low': 1}
NOTA_APROBATORIA = 3.0


def calcular_ppa(notas_qs):
    """
    Promedio ponderado acumulado (PPA): suma(definitiva × créditos) / suma(créditos),
    solo con notas que tienen definitiva. Si ninguna materia tiene créditos
    registrados se usa el promedio simple. None si no hay notas.
    """
    agg = notas_qs.filter(definitiva__isnull=False).aggregate(
        puntos=Sum(F('definitiva') * F('curso__materia__creditos')),
        creditos=Sum('curso__materia__creditos'),
        simple=Avg('definitiva'),
    )
    if agg['creditos']:
        return round(Decimal(str(agg['puntos'])) / Decimal(agg['creditos']), 2)
    if agg['simple'] is not None:
        return round(Decimal(str(agg['simple'])), 2)
    return None


def actualizar_promedio(estudiante):
    """
    Recalcula el PPA desde las notas y lo guarda si cambió.
    Sin notas se conserva el promedio importado del archivo.
    """
    ppa = calcular_ppa(Nota.objects.filter(estudiante=estudiante))
    if ppa is not None and estudiante.promedio != ppa:
        type(estudiante).objects.filter(pk=estudiante.pk).update(promedio=ppa)
        estudiante.promedio = ppa
    return estudiante.promedio


def _notas_hasta(estudiante, periodo):
    qs = Nota.objects.filter(estudiante=estudiante)
    if periodo is not None:
        qs = qs.filter(
            Q(periodo__anio__lt=periodo.anio) |
            Q(periodo__anio=periodo.anio, periodo__semestre__lte=periodo.semestre)
        )
    return qs


def calcular_indicadores(estudiante, periodo=None, semestre_ref=None):
    """
    Indicadores del estudiante con sus notas hasta `periodo` (inclusive; todas si es None).

    - ppa: PPA de esas notas. Sin notas, el promedio importado (puede ser None).
    - reprobadas: materias perdidas que aún no ha aprobado, ni directamente ni por
      equivalencia. Cada materia cuenta una vez aunque la haya perdido varias veces.
    - atraso: materias de línea de semestres anteriores a `semestre_ref`
      (por defecto el semestre actual) que no ha aprobado.

    Sin notas, reprobadas y atraso son None: no hay datos para evaluarlos.
    """
    notas = _notas_hasta(estudiante, periodo)
    semestre = semestre_ref if semestre_ref is not None else estudiante.semestre

    if not notas.exists():
        return {
            'tiene_notas': False,
            'ppa': float(estudiante.promedio) if estudiante.promedio is not None else None,
            'reprobadas': None, 'materias_reprobadas': [],
            'atraso': None, 'materias_atrasadas': [],
            'semestre_ref': semestre,
        }

    ppa = calcular_ppa(notas)

    aprobadas = set(
        notas.filter(definitiva__gte=NOTA_APROBATORIA).values_list('curso__materia_id', flat=True)
    )
    # Equivalencias en ambos sentidos: aprobar una cubre a la otra
    for pensum_id, equivalente_id in EquivalenciaMateria.objects.filter(
        Q(materia_equivalente_id__in=aprobadas) | Q(materia_pensum_id__in=aprobadas)
    ).values_list('materia_pensum_id', 'materia_equivalente_id'):
        aprobadas.update((pensum_id, equivalente_id))

    perdidas = dict(
        notas.filter(definitiva__lt=NOTA_APROBATORIA)
        .values_list('curso__materia_id', 'curso__materia__nombre')
    )
    pendientes = sorted(nombre for materia_id, nombre in perdidas.items() if materia_id not in aprobadas)

    if semestre is not None:
        atrasadas = list(
            Materia.objects.filter(semestre__lt=semestre, tipo='linea')
            .exclude(codigo__in=aprobadas)
            .order_by('semestre', 'nombre')
            .values_list('nombre', flat=True)
        )
    else:
        atrasadas = []

    return {
        'tiene_notas': True,
        'ppa': float(ppa) if ppa is not None else None,
        'reprobadas': len(pendientes), 'materias_reprobadas': pendientes,
        'atraso': len(atrasadas) if semestre is not None else None, 'materias_atrasadas': atrasadas,
        'semestre_ref': semestre,
    }


def _valor(regla, indicadores):
    return {
        'PROMEDIO': indicadores['ppa'],
        'REPROBACION': indicadores['reprobadas'],
        'ATRASO': indicadores['atraso'],
    }.get(regla.tipo)


def _cumple(regla, valor):
    if valor is None:
        return False  # sin datos la regla no aplica
    try:
        v, umbral = float(valor), float(regla.valor_umbral)
    except (TypeError, ValueError):
        return False
    return {
        '<': v < umbral, '>': v > umbral, '<=': v <= umbral, '>=': v >= umbral, '==': v == umbral,
    }.get(regla.operador, False)


def _metadata(regla, valor, indicadores):
    if regla.tipo == 'PROMEDIO':
        return {'promedio': valor}
    if regla.tipo == 'REPROBACION':
        return {'materias': indicadores['materias_reprobadas']}
    if regla.tipo == 'ATRASO':
        return {
            'semestre_actual': indicadores['semestre_ref'],
            'materias_atrasadas': indicadores['materias_atrasadas'],
            'total_atrasadas': valor,
        }
    return {}


def evaluar_regla(regla, indicadores):
    """Retorna (aplica, valor, metadata) de la regla con los indicadores dados."""
    valor = _valor(regla, indicadores)
    if not _cumple(regla, valor):
        return False, valor, {}
    return True, valor, _metadata(regla, valor, indicadores)


def nivel_de_riesgo(reglas, indicadores):
    """
    Nivel más alto entre las reglas que aplican y la lista de reglas aplicadas.
    'unknown' si no hay notas ni promedio (no hay datos para evaluar).
    """
    if not indicadores['tiene_notas'] and indicadores['ppa'] is None:
        return 'unknown', []

    nivel, peso = 'low', 0
    aplicadas = []
    for regla in reglas:
        aplica, valor, _ = evaluar_regla(regla, indicadores)
        if not aplica:
            continue
        aplicadas.append({'id': regla.id, 'nombre': regla.nombre, 'nivel': regla.nivel, 'valor': valor})
        if ORDEN_NIVELES.get(regla.nivel, 0) > peso:
            nivel, peso = regla.nivel, ORDEN_NIVELES[regla.nivel]
    return nivel, aplicadas
