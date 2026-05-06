from django.urls import path
from .views import rule_views

urlpatterns = [
    path('reglas/', rule_views.listar_crear_reglas, name='listar_crear_reglas'),
    path('reglas/<int:pk>/', rule_views.detalle_regla, name='detalle_regla'),
]
