"""
HU-40: Intervenciones (acompañamiento) de las alertas del estudiante en el portal.

Serializador propio del portal con lista blanca de campos: la respuesta se arma
solo con lo visible para el estudiante (tipo, fecha, estado, resultado, nombre del
responsable y la alerta a la que corresponde), así que un campo nuevo en el modelo
no aparece por sí solo. Nunca se exponen las observaciones, el campo `evidencia`,
las anotaciones, los archivos de evidencia ni datos del responsable distintos a su
nombre (correo, rol, identificador).
"""
from .alertas import origen

TIPOS_TEXTO = {'TUTORIA': 'Tutoría', 'CITACION': 'Citación', 'REMISION': 'Remisión'}

# Estado del portal → valor de Intervencion.concluida
ESTADOS = {'en_curso': False, 'concluida': True}
ESTADOS_TEXTO = {'en_curso': 'En curso', 'concluida': 'Concluida'}


def _responsable(intervencion):
    # Intervencion.usuario es obligatorio, pero si faltara la respuesta no falla
    # (RelatedObjectDoesNotExist es un AttributeError)
    usuario = getattr(intervencion, 'usuario', None)
    return usuario.nombre if usuario is not None else None


def resumen_alerta(alerta):
    meta = alerta.metadata or {}
    por_curso = origen(alerta.regla) != 'general'
    return {
        'id': alerta.id,
        'tipo': alerta.regla.nombre,
        'materia': meta.get('materia_nombre') if por_curso else None,
        'periodo': meta.get('periodo') if por_curso else None,
    }


def serializar_intervencion(intervencion):
    estado = 'concluida' if intervencion.concluida else 'en_curso'
    return {
        'id': intervencion.id,
        'tipo': intervencion.tipo,
        'tipo_texto': TIPOS_TEXTO.get(intervencion.tipo, intervencion.tipo),
        'fecha': intervencion.fecha.isoformat() if intervencion.fecha else None,
        'estado': estado,
        'estado_texto': ESTADOS_TEXTO[estado],
        'resultado': intervencion.resultado or None,
        'responsable': _responsable(intervencion),
        'alerta': resumen_alerta(intervencion.alerta),
    }
