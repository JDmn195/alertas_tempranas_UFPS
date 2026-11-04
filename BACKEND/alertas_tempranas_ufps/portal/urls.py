from django.urls import path

from .views import alertas_propias, detalle_alerta_propia, evolucion_propia, riesgo_propio

# Portal del estudiante (EP-09). Ninguna ruta recibe el código del estudiante:
# sale siempre del token.
urlpatterns = [
    path('riesgo/', riesgo_propio, name='portal-riesgo'),  # HU-37
    path('evolucion/', evolucion_propia, name='portal-evolucion'),  # HU-38
    path('alertas/', alertas_propias, name='portal-alertas'),  # HU-39
    path('alertas/<int:alerta_id>/', detalle_alerta_propia, name='portal-alerta-detalle'),  # HU-39
]
