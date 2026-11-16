"""
SDAT-303: caché breve del listado de alertas (GET /api/alertas/).

El listado completo pesa varios MB (miles de alertas) y la pantalla de gestión lo pide en cada
visita y cada "Actualizar" desde varios usuarios a la vez. Se guarda la respuesta ya serializada
en memoria del proceso, por alcance de consulta, durante pocos segundos.

No usa el caché de Django: en producción es DatabaseCache y guardar varios MB por consulta
en la base sería peor que recalcular. Se invalida al guardar o borrar una alerta o un riesgo
(señales) y, para escrituras masivas que no las disparan (bulk_create, update), vence solo.
"""
import threading
import time

SEGUNDOS_VIGENCIA = 10
MAX_ENTRADAS = 64
MAX_BYTES = 64 * 1024 * 1024  # tope de memoria del proceso para todas las entradas

_candado = threading.Lock()
_entradas = {}  # clave -> (vence, cuerpo)


def obtener(clave):
    with _candado:
        entrada = _entradas.get(clave)
        if entrada and entrada[0] > time.monotonic():
            return entrada[1]
        _entradas.pop(clave, None)
    return None


def guardar(clave, cuerpo):
    with _candado:
        ahora = time.monotonic()
        for k in [k for k, (vence, _) in _entradas.items() if vence <= ahora]:
            del _entradas[k]
        while _entradas and (len(_entradas) >= MAX_ENTRADAS or
                             sum(len(c) for _, c in _entradas.values()) + len(cuerpo) > MAX_BYTES):
            _entradas.pop(next(iter(_entradas)))
        _entradas[clave] = (ahora + SEGUNDOS_VIGENCIA, cuerpo)


def invalidar(*_args, **_kwargs):
    with _candado:
        _entradas.clear()
