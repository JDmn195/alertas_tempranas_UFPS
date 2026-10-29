from django.urls import path

from .views import (
    alertas_propias, asistencia_propia, cancelar_solicitud_propia, detalle_alerta_propia, detalle_intervencion_propia,
    evolucion_propia, intervenciones_propias, riesgo_propio, solicitudes_propias,
)

# Portal del estudiante (EP-09). Ninguna ruta recibe el código del estudiante:
# sale siempre del token.
urlpatterns = [
    path('riesgo/', riesgo_propio, name='portal-riesgo'),  # HU-37
    path('evolucion/', evolucion_propia, name='portal-evolucion'),  # HU-38
    path('alertas/', alertas_propias, name='portal-alertas'),  # HU-39
    path('alertas/<int:alerta_id>/', detalle_alerta_propia, name='portal-alerta-detalle'),  # HU-39
    path('intervenciones/', intervenciones_propias, name='portal-intervenciones'),  # HU-40
    path('intervenciones/<int:intervencion_id>/', detalle_intervencion_propia,
         name='portal-intervencion-detalle'),  # HU-40
    path('solicitudes/', solicitudes_propias, name='portal-solicitudes'),  # HU-41
    path('solicitudes/<int:solicitud_id>/cancelar/', cancelar_solicitud_propia,
         name='portal-solicitud-cancelar'),  # HU-41
    path('asistencia/', asistencia_propia, name='portal-asistencia'),  # HU-42
]
