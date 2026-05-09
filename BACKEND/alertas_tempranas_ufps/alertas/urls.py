from django.urls import path
from .views import rule_views
from .views.intervencion_views import registrar_intervencion, listar_intervenciones

urlpatterns = [
    path('reglas/', rule_views.listar_crear_reglas, name='listar_crear_reglas'),
    path('reglas/<int:pk>/', rule_views.detalle_regla, name='detalle_regla'),
    path('<int:alerta_id>/intervenciones/', listar_intervenciones,  name='listar-intervenciones'),
    path('<int:alerta_id>/intervenciones/registrar/', registrar_intervencion, name='registrar-intervencion'),
]
