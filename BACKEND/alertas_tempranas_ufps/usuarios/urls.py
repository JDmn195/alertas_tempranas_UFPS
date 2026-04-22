from django.urls import path
from .views import login_view, solicitar_recuperacion, cambiar_contrasena

urlpatterns = [
    path('login/', login_view, name='login'),
    path('recuperar-password/', solicitar_recuperacion, name='solicitar_recuperacion'),
    path('cambiar-password/', cambiar_contrasena, name='cambiar_contrasena'),
]
