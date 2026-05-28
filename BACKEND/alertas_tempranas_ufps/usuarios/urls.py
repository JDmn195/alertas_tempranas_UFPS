from django.urls import path
from .views import login_view, solicitar_recuperacion, cambiar_contrasena
from .views import listar_usuarios, crear_usuario, actualizar_usuario, desactivar_usuario, listar_auditoria

urlpatterns = [
    path('login/', login_view, name='login'),
    path('recuperar-password/', solicitar_recuperacion, name='solicitar_recuperacion'),
    path('cambiar-password/', cambiar_contrasena, name='cambiar_contrasena'),
    # CRUD de Usuarios
    path('', listar_usuarios, name='listar_usuarios'),
    path('crear/', crear_usuario, name='crear_usuario'),
    path('<int:usuario_id>/actualizar/', actualizar_usuario, name='actualizar_usuario'),
    path('<int:usuario_id>/desactivar/', desactivar_usuario, name='desactivar_usuario'),
    # Auditoría
    path('auditoria/', listar_auditoria, name='listar_auditoria'),
]
