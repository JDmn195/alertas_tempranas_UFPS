from django.urls import path
from .views import rule_views
from .views.intervencion_views import registrar_intervencion, listar_intervenciones, gestionar_anotaciones, eliminar_anotacion, concluir_intervencion
from .views.evidence_views import upload_evidence, list_evidence, delete_evidence

urlpatterns = [
    path('reglas/', rule_views.listar_crear_reglas, name='listar_crear_reglas'),
    path('reglas/<int:pk>/', rule_views.detalle_regla, name='detalle_regla'),
    path('<int:alerta_id>/intervenciones/', listar_intervenciones,  name='listar-intervenciones'),
    path('<int:alerta_id>/intervenciones/registrar/', registrar_intervencion, name='registrar-intervencion'),
    # Evidencias y Anotaciones
    path('intervenciones/<int:intervencion_id>/anotaciones/', gestionar_anotaciones, name='gestionar-anotaciones'),
    path('anotaciones/<int:anotacion_id>/', eliminar_anotacion, name='eliminar-anotacion'),
    path('intervenciones/<int:intervencion_id>/concluir/', concluir_intervencion, name='concluir-intervencion'),
    path('intervenciones/<int:intervencion_id>/evidencias/', list_evidence, name='listar-evidencias'),
    path('intervenciones/<int:intervencion_id>/evidencias/upload/', upload_evidence, name='subir-evidencia'),
    path('evidencias/<int:evidencia_id>/', delete_evidence, name='eliminar-evidencia'),
]
