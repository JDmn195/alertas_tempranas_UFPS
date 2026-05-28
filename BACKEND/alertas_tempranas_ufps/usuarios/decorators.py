import jwt
from django.conf import settings
from functools import wraps
from django.http import JsonResponse
from .models import Usuario
from .utils import registrar_auditoria

def obtener_usuario_de_request(request):
    """
    Intenta obtener el usuario validando el token JWT en el header Authorization.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
        
    token = auth_header.split(' ')[1]
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
        if not user_id:
            return None
        return Usuario.objects.get(id=user_id, activo=True)
    except jwt.ExpiredSignatureError:
        return None
    except (jwt.InvalidTokenError, Usuario.DoesNotExist):
        return None
def requiere_rol(roles_permitidos):
    """
    Decorador para validar que el usuario que hace la petición tenga el rol adecuado.
    También valida que el usuario esté activo.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            usuario = obtener_usuario_de_request(request)
            
            if not usuario:
                return JsonResponse({'error': 'No autorizado. Se requiere inicio de sesión.'}, status=401)
                
            if usuario.rol not in roles_permitidos:
                # Registrar el intento fallido
                detalle = f"Intento de acceso denegado a la ruta {request.path} con rol {usuario.rol}"
                registrar_auditoria(usuario, 'ACCESO_DENEGADO', detalle)
                return JsonResponse({'error': 'Prohibido. No tiene los permisos necesarios para realizar esta acción.'}, status=403)
                
            # Si pasa la validación, inyectamos el usuario en el request
            request.usuario = usuario
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
