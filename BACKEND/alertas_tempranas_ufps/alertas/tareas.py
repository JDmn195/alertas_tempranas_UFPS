"""
Ejecución de tareas en segundo plano (recálculo de riesgo/alertas tras
importaciones, cambios de reglas y re-evaluación).

En producción cada tarea corre en un hilo para no demorar la respuesta HTTP
y cierra su conexión a la BD al terminar. En los tests
(TAREAS_EN_SEGUNDO_PLANO=False) corre de forma síncrona: un hilo que sigue
vivo después del test choca con SQLite ("database table is locked").
"""
import logging
import threading

from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)


def _ejecutar(func, args, kwargs):
    try:
        func(*args, **kwargs)
    except Exception as e:
        logger.error("Error en tarea en segundo plano %s: %s", func.__name__, e, exc_info=True)


def _ejecutar_en_hilo(func, args, kwargs):
    try:
        _ejecutar(func, args, kwargs)
    finally:
        connection.close()


def ejecutar_en_segundo_plano(func, *args, **kwargs):
    if not getattr(settings, 'TAREAS_EN_SEGUNDO_PLANO', True):
        _ejecutar(func, args, kwargs)
        return
    threading.Thread(target=_ejecutar_en_hilo, args=(func, args, kwargs), daemon=True).start()
