"""
Portal de autoconsulta del estudiante (EP-09, HU-37 a HU-42).

Todos los endpoints del portal exigen el rol ESTUDIANTE y obtienen al estudiante
con obtener_estudiante_autenticado: el código sale del token, nunca de la URL ni
de los parámetros. Las respuestas no incluyen observaciones, anotaciones,
evidencias, datos del personal ni campos de auditoría.
"""
import logging

from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from academico.models import Materia, Nota
from alertas.evaluacion import NOTA_APROBATORIA, calcular_indicadores, calcular_ppa
from alertas.models import Regla, RiesgoEstudiante
from usuarios.decorators import obtener_estudiante_autenticado, requiere_rol

logger = logging.getLogger(__name__)

NIVELES_TEXTO = {'high': 'Alto', 'medium': 'Medio', 'low': 'Bajo'}


def _ultimo_riesgo(estudiante):
    """
    Riesgo del periodo más reciente con su fecha de cálculo, con el mismo criterio
    que la ficha del estudiante: RiesgoEstudiantePeriodo y, si no hay, el snapshot.
    """
    por_periodo = (
        estudiante.riesgos_por_periodo
        .select_related('periodo')
        .order_by('-periodo__anio', '-periodo__semestre')
        .first()
    )
    if por_periodo is not None:
        return por_periodo, f"{por_periodo.periodo.anio}-{por_periodo.periodo.semestre}"
    return RiesgoEstudiante.objects.filter(estudiante=estudiante).first(), None


def _causas(reglas_aplicadas):
    """
    Causas del nivel de riesgo a partir de las reglas aplicadas que guardó
    alertas.evaluacion al calcularlo (así coinciden con el nivel y la fecha
    mostrados). El umbral y el operador salen de la regla.
    """
    reglas = Regla.objects.in_bulk([r.get('id') for r in reglas_aplicadas if r.get('id')])
    causas = []
    for aplicada in reglas_aplicadas:
        regla = reglas.get(aplicada.get('id'))
        tipo = aplicada.get('tipo') or (regla.tipo if regla else None)
        causa = {
            'regla': aplicada.get('nombre') or (regla.nombre if regla else ''),
            'tipo': tipo,
            'nivel': aplicada.get('nivel'),
            'valor': aplicada.get('valor'),
            'operador': regla.operador if regla else None,
            'umbral': float(regla.valor_umbral) if regla else None,
        }
        if tipo == 'INASISTENCIA':
            # El umbral puede ser propio de cada curso: se informa el de cada materia
            cursos = aplicada.get('cursos') or []
            nombres = dict(
                Materia.objects.filter(codigo__in=[c.get('materia_codigo') for c in cursos])
                .values_list('codigo', 'nombre')
            )
            causa['materias'] = [
                {
                    'materia': nombres.get(c.get('materia_codigo'), c.get('materia_codigo')),
                    'porcentaje': c.get('porcentaje'),
                    'umbral': c.get('umbral'),
                }
                for c in cursos
            ]
            mayor = max(cursos, key=lambda c: c.get('porcentaje') or 0, default=None)
            if mayor is not None:
                causa['umbral'] = mayor.get('umbral')
        causas.append(causa)
    return causas


def _indicadores(estudiante):
    """PPS del último periodo con notas definitivas, PPA, materias reprobadas y créditos aprobados."""
    notas = Nota.objects.filter(estudiante=estudiante)
    indicadores = calcular_indicadores(estudiante)

    ultima = (
        notas.filter(definitiva__isnull=False)
        .select_related('periodo')
        .order_by('-periodo__anio', '-periodo__semestre')
        .first()
    )
    pps, periodo_pps = None, None
    if ultima is not None:
        pps = calcular_ppa(notas.filter(periodo=ultima.periodo))
        periodo_pps = f"{ultima.periodo.anio}-{ultima.periodo.semestre}"

    # Cada materia aprobada cuenta una vez, aunque tenga varias notas aprobatorias
    creditos = Materia.objects.filter(
        codigo__in=notas.filter(definitiva__gte=NOTA_APROBATORIA).values('curso__materia_id')
    ).aggregate(total=Sum('creditos'))['total'] or 0

    return {
        'pps': float(pps) if pps is not None else None,
        'periodo_pps': periodo_pps,
        'ppa': indicadores['ppa'],
        'materias_reprobadas': indicadores['reprobadas'],
        'lista_materias_reprobadas': indicadores['materias_reprobadas'],
        'creditos_aprobados': creditos,
    }


@require_GET
@requiere_rol(['ESTUDIANTE'])
def riesgo_propio(request):
    """
    GET /api/portal/riesgo/  (HU-37)
    Nivel de riesgo actual del estudiante autenticado, sus causas e indicadores básicos.
    """
    estudiante, error = obtener_estudiante_autenticado(request)
    if error:
        return error

    try:
        riesgo, periodo = _ultimo_riesgo(estudiante)
        respuesta = {
            'estudiante': {
                'codigo': estudiante.codigo,
                'nombre': estudiante.nombre,
                'semestre': estudiante.semestre,
            },
            'riesgo': {
                'nivel': None,
                'nivel_texto': None,
                'periodo': periodo,
                'fecha_calculo': None,
                'mensaje': None,
            },
            'causas': [],
            'indicadores': _indicadores(estudiante),
        }

        if riesgo is None or riesgo.nivel_riesgo not in NIVELES_TEXTO:
            respuesta['riesgo']['mensaje'] = (
                'Aún no tenemos un cálculo de tu nivel de riesgo académico. '
                'Aparecerá aquí cuando se procesen tus notas.'
            )
            return JsonResponse(respuesta)

        respuesta['riesgo'].update({
            'nivel': riesgo.nivel_riesgo,
            'nivel_texto': NIVELES_TEXTO[riesgo.nivel_riesgo],
            'fecha_calculo': riesgo.fecha_calculo.isoformat(),
        })
        respuesta['causas'] = _causas(riesgo.reglas_aplicadas or [])
        return JsonResponse(respuesta)
    except Exception:
        logger.exception("Error al consultar el riesgo propio del estudiante %s", estudiante.codigo)
        return JsonResponse({'error': 'No fue posible consultar tu nivel de riesgo.'}, status=500)
