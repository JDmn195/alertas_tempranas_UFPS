from django.urls import path
from .views import login_view, solicitar_recuperacion, cambiar_contrasena, sesion_actual
from .views import listar_usuarios, crear_usuario, actualizar_usuario, desactivar_usuario, listar_auditoria
from .views import cuenta_estudiante

urlpatterns = [
    path('login/', login_view, name='login'),
    path('recuperar-password/', solicitar_recuperacion, name='solicitar_recuperacion'),
    path('cambiar-password/', cambiar_contrasena, name='cambiar_contrasena'),
    path('me/', sesion_actual, name='sesion_actual'),
    # CRUD de Usuarios
    path('', listar_usuarios, name='listar_usuarios'),
    path('crear/', crear_usuario, name='crear_usuario'),
    path('<int:usuario_id>/actualizar/', actualizar_usuario, name='actualizar_usuario'),
    path('<int:usuario_id>/desactivar/', desactivar_usuario, name='desactivar_usuario'),
    # Cuentas de estudiantes para el portal (HU-37)
    path('estudiantes/<str:codigo>/cuenta/', cuenta_estudiante, name='cuenta_estudiante'),
    # Auditoría
    path('auditoria/', listar_auditoria, name='listar_auditoria'),
]
