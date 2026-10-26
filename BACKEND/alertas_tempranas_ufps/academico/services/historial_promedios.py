"""
Serie histórica de promedios por periodo (PPS y PPA) de un estudiante.

La usan la ficha académica del personal (/students/<codigo>/indicators/) y el
portal del estudiante (/api/portal/evolucion/, HU-38), para que ambos muestren
los mismos valores.
"""
from academico.constants import NOTA_APROBATORIA
from academico.models import Nota


def serie_promedios_por_periodo(estudiante):
    """
    Un elemento por periodo con notas, del más antiguo al más reciente:

    - periodo: 'AAAA-S'
    - pps: promedio ponderado por créditos del periodo, solo con notas definitivas
      (las materias en curso no cuentan). None si no hay créditos con definitiva.
    - ppa: promedio ponderado acumulado hasta ese periodo (None si aún no hay créditos).
    - creditos_cursados: créditos de las materias con definitiva en el periodo.
    - creditos_aprobados: créditos de las materias aprobadas en el periodo.
    - materias_en_curso: materias del periodo aún sin definitiva.
    """
    notas = Nota.objects.filter(estudiante=estudiante).select_related(
        'periodo', 'curso__materia'
    ).order_by('periodo__anio', 'periodo__semestre')

    # Agrupar por periodo preservando el orden cronológico
    periodos = {}
    for n in notas:
        periodos.setdefault(f"{n.periodo.anio}-{n.periodo.semestre}", []).append(n)

    serie = []
    puntos_acumulados = 0
    creditos_acumulados = 0

    for periodo, notas_periodo in periodos.items():
        puntos_semestre = 0
        creditos_semestre = 0
        creditos_aprobados = 0
        en_curso = 0

        for n in notas_periodo:
            if n.definitiva is None:
                en_curso += 1  # sin nota definitiva no cuenta para el promedio (igual que el PPA guardado)
                continue
            creditos = n.curso.materia.creditos or 0
            puntos_semestre += float(n.definitiva) * creditos
            creditos_semestre += creditos
            if n.definitiva >= NOTA_APROBATORIA:
                creditos_aprobados += creditos

        puntos_acumulados += puntos_semestre
        creditos_acumulados += creditos_semestre

        serie.append({
            'periodo': periodo,
            'pps': round(puntos_semestre / creditos_semestre, 2) if creditos_semestre > 0 else None,
            'ppa': round(puntos_acumulados / creditos_acumulados, 2) if creditos_acumulados > 0 else None,
            'creditos_cursados': creditos_semestre,
            'creditos_aprobados': creditos_aprobados,
            'materias_en_curso': en_curso,
        })

    return serie


def tendencia_promedio(actual, anterior):
    """
    Variación del promedio actual respecto al anterior.
    direccion: 'up' / 'down' / 'stable' (cambios de hasta 0.01 se consideran estables).
    """
    tendencia = {'valor': 0, 'porcentaje': 0, 'direccion': 'stable'}
    if anterior is None or actual is None or anterior <= 0:
        return tendencia

    diff = actual - anterior
    tendencia['valor'] = round(diff, 2)
    tendencia['porcentaje'] = round(abs(diff / anterior * 100), 1)
    if diff > 0.01:
        tendencia['direccion'] = 'up'
    elif diff < -0.01:
        tendencia['direccion'] = 'down'
    return tendencia
