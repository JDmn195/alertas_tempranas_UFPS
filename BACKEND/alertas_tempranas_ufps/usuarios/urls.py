from django.urls import path
from .views import login_view, solicitar_recuperacion, cambiar_contrasena, listar_usuarios, gestionar_usuario

urlpatterns = [
    path('login/', login_view, name='login'),
    path('recuperar-password/', solicitar_recuperacion, name='solicitar_recuperacion'),
    path('cambiar-password/', cambiar_contrasena, name='cambiar_contrasena'),
    path('', listar_usuarios, name='listar_usuarios'),
    path('<int:usuario_id>/', gestionar_usuario, name='gestionar_usuario'),
]
