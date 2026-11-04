"""
HU-39: Alertas del estudiante en el portal.

Serializador propio del portal (no se reutiliza el de las vistas del personal):
expone solo lo que el estudiante necesita para entender la alerta, sin
observaciones, intervenciones, evidencias, datos del personal, auditoría ni
identificadores internos (regla, curso). La explicación se arma con la metadata
que guarda cada origen: alertas.evaluacion (reglas generales), alertas_corte e
alertas_inasistencia.
"""
from alertas.models import ESTADOS_ALERTA_CERRADA

NIVELES_TEXTO = {'high': 'Alta', 'medium': 'Media', 'low': 'Baja'}

# Estado del portal → estados guardados (algunas vías antiguas usan los nombres en inglés)
ESTADOS = {
    'activa': ('activa', 'active'),
    'en_seguimiento': ('en_seguimiento',),
    'atendida': ('atendida',),
    'cerrada': ESTADOS_ALERTA_CERRADA,
}
ESTADOS_TEXTO = {
    'activa': 'Activa',
    'en_seguimiento': 'En seguimiento',
    'atendida': 'Atendida',
    'cerrada': 'Cerrada',
}

OPERADORES_TEXTO = {
    '<': 'menor que', '<=': 'menor o igual a', '>': 'mayor que', '>=': 'mayor o igual a', '==': 'igual a',
}

NOTA_MAXIMA = 5.0


def estado_portal(estado):
    """Estado normalizado ('activa', 'en_seguimiento', 'atendida', 'cerrada') o el original si es otro."""
    for clave, guardados in ESTADOS.items():
        if estado in guardados:
            return clave
    return estado


def origen(regla):
    return {'CORTE': 'corte', 'INASISTENCIA': 'inasistencia'}.get(regla.tipo, 'general')


def _numero(valor):
    try:
        return float(valor) if valor is not None else None
    except (TypeError, ValueError):
        return None


def _fmt(valor, decimales=1):
    numero = _numero(valor)
    return f"{numero:.{decimales}f}" if numero is not None else 'sin dato'


def _curso_texto(meta):
    materia = meta.get('materia_nombre') or meta.get('materia_codigo') or 'la materia'
    grupo = f", grupo {meta['grupo']}" if meta.get('grupo') else ''
    periodo = f", periodo {meta['periodo']}" if meta.get('periodo') else ''
    return f"{materia}{grupo}{periodo}"


def _datos_curso(meta):
    datos = [{'etiqueta': 'Materia', 'valor': meta.get('materia_nombre') or meta.get('materia_codigo') or '—'}]
    if meta.get('grupo'):
        datos.append({'etiqueta': 'Grupo', 'valor': meta['grupo']})
    if meta.get('periodo'):
        datos.append({'etiqueta': 'Periodo', 'valor': meta['periodo']})
    return datos


# ---------------------------------------------------------------------------
# Reglas generales (PROMEDIO, REPROBACION, ATRASO)
# ---------------------------------------------------------------------------

def _explicacion_general(alerta, meta):
    regla = alerta.regla
    umbral = _numero(regla.valor_umbral)
    condicion = OPERADORES_TEXTO.get(regla.operador, regla.operador)
    valores = {'valor': None, 'umbral': umbral, 'operador': regla.operador}

    if regla.tipo == 'PROMEDIO':
        valor = _numero(meta.get('promedio', alerta.valor_causa))
        valores['valor'] = valor
        mensaje = (
            f"Tu promedio ponderado acumulado (PPA) es {_fmt(valor, 2)}. Esta alerta se registra cuando "
            f"el promedio es {condicion} {_fmt(umbral, 2)}."
        )
        recomendacion = (
            'Mejorar tus notas en las materias que cursas este semestre es la forma más directa de '
            'subir tu promedio acumulado. Puedes apoyarte en las tutorías y en tus docentes.'
        )
        datos = [
            {'etiqueta': 'Tu promedio acumulado', 'valor': _fmt(valor, 2)},
            {'etiqueta': 'Valor de referencia', 'valor': f"{condicion} {_fmt(umbral, 2)}"},
        ]

    elif regla.tipo == 'REPROBACION':
        materias = list(meta.get('materias') or [])
        valor = _numero(alerta.valor_causa)
        if valor is None:
            valor = float(len(materias))
        valores.update(valor=valor, materias=materias)
        cantidad = int(valor)
        mensaje = (
            f"Tienes {cantidad} {'materia reprobada' if cantidad == 1 else 'materias reprobadas'} que aún "
            f"no has aprobado. Esta alerta se registra cuando el número de materias reprobadas es "
            f"{condicion} {_fmt(umbral, 0)}."
        )
        recomendacion = (
            'Planear cuándo volver a cursar estas materias te ayuda a no acumular pendientes. '
            'Tu director de programa puede orientarte en la matrícula.'
        )
        datos = [
            {'etiqueta': 'Materias reprobadas pendientes', 'valor': str(cantidad)},
            {'etiqueta': 'Valor de referencia', 'valor': f"{condicion} {_fmt(umbral, 0)}"},
        ]
        if materias:
            datos.append({'etiqueta': 'Materias', 'valor': ', '.join(materias)})

    elif regla.tipo == 'ATRASO':
        materias = list(meta.get('materias_atrasadas') or [])
        valor = _numero(meta.get('total_atrasadas', alerta.valor_causa))
        semestre = meta.get('semestre_actual')
        valores.update(valor=valor, materias=materias, semestre=semestre)
        cantidad = int(valor or 0)
        inicio = f"Según tu semestre actual ({semestre}), tienes" if semestre else 'Tienes'
        mensaje = (
            f"{inicio} {cantidad} {'materia de línea' if cantidad == 1 else 'materias de línea'} "
            f"de semestres anteriores sin aprobar. Esta alerta se registra cuando son {condicion} "
            f"{_fmt(umbral, 0)}."
        )
        recomendacion = (
            'Priorizar estas materias en tus próximas matrículas te ayuda a avanzar en el plan de '
            'estudios. Consulta con tu director de programa el orden más conveniente.'
        )
        datos = [
            {'etiqueta': 'Materias de línea atrasadas', 'valor': str(cantidad)},
            {'etiqueta': 'Valor de referencia', 'valor': f"{condicion} {_fmt(umbral, 0)}"},
        ]
        if semestre:
            datos.insert(0, {'etiqueta': 'Semestre actual', 'valor': str(semestre)})
        if materias:
            datos.append({'etiqueta': 'Materias', 'valor': ', '.join(materias)})

    else:
        valor = _numero(alerta.valor_causa)
        valores['valor'] = valor
        mensaje = f"Esta alerta se registró por la regla «{regla.nombre}»."
        recomendacion = 'Si tienes dudas sobre esta alerta, comunícate con tu director de programa.'
        datos = []

    return mensaje, recomendacion, datos, valores


# ---------------------------------------------------------------------------
# Alertas por corte (HU-32)
# ---------------------------------------------------------------------------

def _explicacion_corte(alerta, meta):
    regla = alerta.regla
    params = regla.parametros or {}
    clave = meta.get('clave') or params.get('clave')
    notas = meta.get('notas') or {}
    numero_corte = meta.get('corte') or params.get('corte')
    nota_necesaria = _numero(meta.get('nota_necesaria'))
    umbral = _numero(regla.valor_umbral)
    curso = _curso_texto(meta)

    nota = _numero(notas.get(f'corte{numero_corte}')) if numero_corte else None
    if nota is None and params.get('evalua') == 'CORTE':
        nota = _numero(alerta.valor_causa)

    valores = {
        'clave': clave,
        'materia': meta.get('materia_nombre'),
        'grupo': meta.get('grupo'),
        'periodo': meta.get('periodo'),
        'corte': numero_corte,
        'nota': nota,
        'nota_necesaria': None,
        'notas': {k: _numero(notas.get(k)) for k in ('corte1', 'corte2', 'corte3')},
    }
    datos = _datos_curso(meta)
    cortes = valores['notas']

    if clave in ('C3', 'C4'):
        valores['nota_necesaria'] = nota_necesaria
        registrados = ', '.join(_fmt(cortes[k]) for k in ('corte1', 'corte2', 'corte3'))
        datos += [
            {'etiqueta': 'Notas de los cortes', 'valor': registrados},
            {'etiqueta': 'Nota necesaria en el examen final', 'valor': _fmt(nota_necesaria, 2)},
        ]
        if clave == 'C4':
            mensaje = (
                f"En {curso} tus tres cortes son {registrados}. Para aprobar con 3.0 necesitarías "
                f"{_fmt(nota_necesaria, 2)} en el examen final, más que la nota máxima ({_fmt(NOTA_MAXIMA)})."
            )
            recomendacion = (
                'Habla con tu docente o con tu director de programa para conocer tus opciones con esta '
                'materia y planear cómo cursarla de nuevo.'
            )
        else:
            mensaje = (
                f"En {curso} tus tres cortes son {registrados}. Para aprobar con 3.0 necesitas "
                f"{_fmt(nota_necesaria, 2)} en el examen final."
            )
            recomendacion = (
                'Aún puedes aprobar. Prepara el examen final con tiempo y apóyate en tu docente o en las '
                'tutorías para repasar los temas con más dificultad.'
            )
    else:
        datos.append({'etiqueta': f"Nota del corte {numero_corte}" if numero_corte else 'Nota', 'valor': _fmt(nota)})
        previo = _numero(cortes.get('corte1')) if numero_corte == 2 else None
        if previo is not None:
            datos.append({'etiqueta': 'Nota del corte 1', 'valor': _fmt(previo)})

        if clave == 'C2A':
            mensaje = (
                f"En {curso} obtuviste {_fmt(nota)} en el corte 2 y {_fmt(previo)} en el corte 1; ambas "
                f"notas están por debajo de 3.0, así que aún no tienes asegurado aprobar la materia."
            )
            recomendacion = (
                'Todavía quedan el corte 3 y el examen final. Revisa con tu docente qué temas reforzar y '
                'aprovecha las tutorías.'
            )
        elif clave == 'C2B':
            mensaje = (
                f"En {curso} obtuviste {_fmt(nota)} en el corte 2, por debajo de 3.0, después de "
                f"{_fmt(previo)} en el corte 1. Es una caída respecto al corte anterior."
            )
            recomendacion = (
                'Identificar qué cambió en este corte (temas, tiempo de estudio, carga académica) te '
                'ayuda a recuperar el ritmo que tenías.'
            )
        else:
            referencia = f", por debajo de {_fmt(umbral)}" if umbral is not None else ''
            corte_txt = f"el corte {numero_corte}" if numero_corte else 'el corte'
            mensaje = f"En {curso} obtuviste {_fmt(nota)} en {corte_txt}{referencia}."
            recomendacion = (
                'Aún quedan cortes por evaluar. Conversa con tu docente sobre los temas con más dificultad '
                'y, si lo necesitas, sobre las opciones que tienes con la materia.'
            )

    return mensaje, recomendacion, datos, valores


# ---------------------------------------------------------------------------
# Alertas por inasistencia (HU-36)
# ---------------------------------------------------------------------------

def _explicacion_inasistencia(alerta, meta):
    porcentaje = _numero(meta.get('porcentaje', alerta.valor_causa))
    umbral = _numero(meta.get('umbral'))
    faltas = meta.get('faltas')
    total = meta.get('total_clases')
    justificadas = meta.get('faltas_justificadas') or 0

    valores = {
        'materia': meta.get('materia_nombre'),
        'grupo': meta.get('grupo'),
        'periodo': meta.get('periodo'),
        'porcentaje': porcentaje,
        'umbral': umbral,
        'faltas': faltas,
        'total_clases': total,
        'faltas_justificadas': justificadas,
    }
    mensaje = (
        f"En {_curso_texto(meta)} tienes {faltas} faltas sin justificar de {total} clases registradas "
        f"({_fmt(porcentaje)} %). El límite de inasistencia del curso es {_fmt(umbral)} %."
    )
    if justificadas:
        mensaje += f" Tus {justificadas} faltas justificadas no se cuentan como faltas."
    recomendacion = (
        'Asistir a las próximas clases hace que tu porcentaje baje. Si tienes faltas con soporte, '
        'pide a tu docente que las registre como justificadas.'
    )
    datos = _datos_curso(meta) + [
        {'etiqueta': 'Faltas sin justificar', 'valor': f"{faltas} de {total} clases"},
        {'etiqueta': 'Porcentaje de inasistencia', 'valor': f"{_fmt(porcentaje)} %"},
        {'etiqueta': 'Límite del curso', 'valor': f"{_fmt(umbral)} %"},
    ]
    return mensaje, recomendacion, datos, valores


_EXPLICACIONES = {
    'general': _explicacion_general,
    'corte': _explicacion_corte,
    'inasistencia': _explicacion_inasistencia,
}


def _resumen(alerta, meta):
    """Una línea para el listado."""
    if origen(alerta.regla) == 'general':
        return 'Situación académica general'
    return _curso_texto(meta)


def _cierre(alerta, meta):
    if estado_portal(alerta.estado) != 'cerrada':
        return None
    automatico = bool(meta.get('cierre_automatico'))
    motivo = meta.get('motivo_cierre') if automatico else None
    if automatico and motivo:
        mensaje = f"Esta alerta se cerró automáticamente: {motivo}."
    elif automatico:
        mensaje = 'Esta alerta se cerró automáticamente porque la condición dejó de cumplirse.'
    else:
        mensaje = 'Esta alerta fue cerrada.'
    return {
        'automatico': automatico,
        'motivo': motivo,
        'fecha': alerta.fecha_cierre.isoformat() if alerta.fecha_cierre else None,
        'mensaje': mensaje,
    }


def serializar_alerta(alerta, detalle=False):
    """Alerta para el portal. Con detalle=True agrega la explicación completa."""
    meta = alerta.metadata or {}
    estado = estado_portal(alerta.estado)
    tipo_origen = origen(alerta.regla)
    cierre = _cierre(alerta, meta)
    data = {
        'id': alerta.id,
        'tipo': alerta.regla.nombre,
        'categoria': alerta.regla.tipo,
        'origen': tipo_origen,
        'severidad': alerta.regla.nivel,
        'severidad_texto': NIVELES_TEXTO.get(alerta.regla.nivel, alerta.regla.nivel),
        'estado': estado,
        'estado_texto': ESTADOS_TEXTO.get(estado, estado),
        'fecha_generacion': alerta.fecha_generacion.isoformat(),
        'fecha_cierre': cierre['fecha'] if cierre else None,
        'cierre_automatico': cierre['automatico'] if cierre else False,
        'periodo': meta.get('periodo') if tipo_origen != 'general' else None,
        'materia': meta.get('materia_nombre') if tipo_origen != 'general' else None,
        'resumen': _resumen(alerta, meta),
    }
    if detalle:
        mensaje, recomendacion, datos, valores = _EXPLICACIONES[tipo_origen](alerta, meta)
        data['explicacion'] = {
            'mensaje': mensaje,
            'recomendacion': recomendacion,
            'datos': datos,
            'valores': valores,
        }
        data['cierre'] = cierre
    return data
