"""
Portal de autoconsulta del estudiante (EP-09, HU-37 a HU-42).

Todos los endpoints del portal exigen el rol ESTUDIANTE y obtienen al estudiante
con obtener_estudiante_autenticado: el código sale del token, nunca de la URL ni
de los parámetros. Las respuestas no incluyen observaciones, anotaciones,
evidencias, datos del personal ni campos de auditoría.
"""
import logging
import re

from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from academico.models import Materia, Nota
from academico.services.historial_promedios import serie_promedios_por_periodo, tendencia_promedio
from alertas.evaluacion import NOTA_APROBATORIA, calcular_indicadores, calcular_ppa
from alertas.models import Alerta, Regla, RiesgoEstudiante
from usuarios.decorators import obtener_estudiante_autenticado, requiere_rol
from usuarios.utils import registrar_auditoria

from .alertas import ESTADOS, serializar_alerta

logger = logging.getLogger(__name__)

NIVELES_TEXTO = {'high': 'Alto', 'medium': 'Medio', 'low': 'Bajo'}
TENDENCIA_TEXTO = {'up': 'sube', 'down': 'baja', 'stable': 'estable'}


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


@require_GET
@requiere_rol(['ESTUDIANTE'])
def evolucion_propia(request):
    """
    GET /api/portal/evolucion/  (HU-38)
    Evolución del promedio por periodo del estudiante autenticado (PPS y PPA), con
    la misma serie que la ficha académica. Solo entran los periodos con notas
    definitivas: un periodo con todas sus materias en curso aún no tiene promedio.
    """
    estudiante, error = obtener_estudiante_autenticado(request)
    if error:
        return error

    try:
        serie = [
            {campo: p[campo] for campo in ('periodo', 'pps', 'ppa', 'creditos_cursados', 'creditos_aprobados')}
            for p in serie_promedios_por_periodo(estudiante)
            if p['pps'] is not None
        ]
        respuesta = {
            'serie': serie,
            'promedio_actual': serie[-1]['ppa'] if serie else None,
            'variacion': None,
            'tendencia': None,
            'historia_suficiente': len(serie) >= 2,
            'mensaje': None,
        }

        if not serie:
            respuesta['mensaje'] = (
                'Aún no tienes periodos con notas definitivas. Tu evolución aparecerá '
                'cuando termines tu primer semestre.'
            )
        elif len(serie) == 1:
            respuesta['mensaje'] = (
                'Tienes un solo periodo con notas definitivas. La tendencia aparecerá '
                'cuando tengas más semestres registrados.'
            )
        else:
            tendencia = tendencia_promedio(serie[-1]['ppa'], serie[-2]['ppa'])
            respuesta['variacion'] = {'valor': tendencia['valor'], 'porcentaje': tendencia['porcentaje']}
            respuesta['tendencia'] = TENDENCIA_TEXTO[tendencia['direccion']]
        return JsonResponse(respuesta)
    except Exception:
        logger.exception("Error al consultar la evolución del estudiante %s", estudiante.codigo)
        return JsonResponse({'error': 'No fue posible consultar tu evolución académica.'}, status=500)


PATRON_PERIODO = re.compile(r'^\d{4}-[12]$')
TIPOS_REGLA = {tipo for tipo, _ in Regla.TIPO_CHOICES}


def _filtros_alertas(params):
    """Valida los filtros del listado. Retorna (filtros, errores)."""
    filtros, errores = {}, {}
    estado = (params.get('estado') or '').strip().lower()
    periodo = (params.get('periodo') or '').strip()
    tipo = (params.get('tipo') or '').strip().upper()

    if estado:
        if estado in ESTADOS:
            filtros['estado'] = estado
        else:
            errores['estado'] = f"Estado no válido. Use uno de: {', '.join(ESTADOS)}."
    if periodo:
        if PATRON_PERIODO.match(periodo):
            filtros['periodo'] = periodo
        else:
            errores['periodo'] = 'Periodo no válido. Use el formato AAAA-S (por ejemplo, 2026-1).'
    if tipo:
        if tipo in TIPOS_REGLA:
            filtros['tipo'] = tipo
        else:
            errores['tipo'] = f"Tipo no válido. Use uno de: {', '.join(sorted(TIPOS_REGLA))}."
    return filtros, errores


@require_GET
@requiere_rol(['ESTUDIANTE'])
def alertas_propias(request):
    """
    GET /api/portal/alertas/?estado=&periodo=&tipo=  (HU-39)
    Alertas del estudiante autenticado, de la más reciente a la más antigua. Los
    filtros son opcionales y acumulables. El periodo es el de las alertas por curso
    (corte e inasistencia): las de reglas generales no pertenecen a un periodo.
    """
    estudiante, error = obtener_estudiante_autenticado(request)
    if error:
        return error

    filtros, errores = _filtros_alertas(request.GET)
    if errores:
        return JsonResponse({'error': 'Filtros no válidos.', 'detalle': errores}, status=400)

    try:
        propias = Alerta.objects.filter(estudiante=estudiante).select_related('regla')
        qs = propias
        if 'estado' in filtros:
            qs = qs.filter(estado__in=ESTADOS[filtros['estado']])
        if 'periodo' in filtros:
            qs = qs.filter(metadata__periodo=filtros['periodo']).filter(regla__tipo__in=('CORTE', 'INASISTENCIA'))
        if 'tipo' in filtros:
            qs = qs.filter(regla__tipo=filtros['tipo'])

        conteos = {
            clave: propias.filter(estado__in=guardados).count()
            for clave, guardados in ESTADOS.items()
        }
        conteos['total'] = propias.count()

        periodos = sorted(
            {
                p for p in propias.filter(regla__tipo__in=('CORTE', 'INASISTENCIA'))
                .values_list('metadata__periodo', flat=True) if p
            },
            reverse=True,
        )

        alertas = [serializar_alerta(a) for a in qs.order_by('-fecha_generacion', '-id')]
        mensaje = None
        if not conteos['total']:
            mensaje = 'No tienes alertas registradas. ¡Sigue así!'
        elif not alertas:
            mensaje = 'Ninguna alerta coincide con los filtros seleccionados.'

        return JsonResponse({
            'alertas': alertas,
            'conteos': conteos,
            'periodos': periodos,
            'filtros': filtros,
            'mensaje': mensaje,
        })
    except Exception:
        logger.exception("Error al consultar las alertas del estudiante %s", estudiante.codigo)
        return JsonResponse({'error': 'No fue posible consultar tus alertas.'}, status=500)


@require_GET
@requiere_rol(['ESTUDIANTE'])
def detalle_alerta_propia(request, alerta_id):
    """
    GET /api/portal/alertas/<id>/  (HU-39)
    Detalle de una alerta del estudiante autenticado con su explicación. Si la
    alerta no existe o es de otro estudiante responde 404 (no 403, para no revelar
    que existe) y el intento queda en la auditoría.
    """
    estudiante, error = obtener_estudiante_autenticado(request)
    if error:
        return error

    alerta = Alerta.objects.select_related('regla').filter(id=alerta_id).first()
    if alerta is None or alerta.estudiante_id != estudiante.codigo:
        situacion = 'que no existe' if alerta is None else f'del estudiante {alerta.estudiante_id}'
        registrar_auditoria(
            request.usuario, 'ACCESO_DENEGADO',
            f"El estudiante {estudiante.codigo} intentó consultar en el portal la alerta ID {alerta_id}, {situacion}",
        )
        return JsonResponse({'error': 'Alerta no encontrada.'}, status=404)

    try:
        return JsonResponse(serializar_alerta(alerta, detalle=True))
    except Exception:
        logger.exception("Error al consultar la alerta %s del estudiante %s", alerta_id, estudiante.codigo)
        return JsonResponse({'error': 'No fue posible consultar la alerta.'}, status=500)
