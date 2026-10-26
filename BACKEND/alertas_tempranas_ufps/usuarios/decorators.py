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
        usuario = Usuario.objects.get(id=user_id, activo=True)
        # Un token emitido antes del último cambio de contraseña ya no es válido
        if usuario.contrasena_cambiada_en is not None:
            emitido = payload.get('iat')
            if not isinstance(emitido, (int, float)) or emitido < int(usuario.contrasena_cambiada_en.timestamp()):
                return None
        return usuario
    except jwt.ExpiredSignatureError:
        return None
    except (jwt.InvalidTokenError, Usuario.DoesNotExist):
        return None


def _detalle_acceso_denegado(request, usuario, kwargs):
    detalle = f"Intento de acceso denegado a la ruta {request.path} con rol {usuario.rol}"
    if usuario.rol != 'ESTUDIANTE':
        return detalle
    # HU-37: si un estudiante intenta consultar a otro, se deja su código en la auditoría
    codigo = kwargs.get('codigo') or request.GET.get('codigo') or request.GET.get('estudiante')
    propio = getattr(getattr(usuario, 'estudiante', None), 'codigo', None)
    if codigo and codigo != propio:
        detalle += f". Intentó consultar la información del estudiante {codigo}"
    return detalle


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
                registrar_auditoria(usuario, 'ACCESO_DENEGADO', _detalle_acceso_denegado(request, usuario, kwargs))
                return JsonResponse({'error': 'Prohibido. No tiene los permisos necesarios para realizar esta acción.'}, status=403)
                
            # Si pasa la validación, inyectamos el usuario en el request
            request.usuario = usuario
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def obtener_estudiante_autenticado(request):
    """
    HU-37: Estudiante asociado al usuario del token, para los endpoints del portal.

    Retorna (estudiante, None) o (None, respuesta de error). El código del estudiante
    sale siempre del token, nunca de la URL ni de los parámetros. Usar después de
    @requiere_rol(['ESTUDIANTE']): ese decorador ya rechaza y audita a los usuarios de
    otro rol, así que sus denegaciones nunca llegan aquí y no se registran dos veces.
    """
    usuario = getattr(request, 'usuario', None) or obtener_usuario_de_request(request)
    if not usuario:
        return None, JsonResponse({'error': 'No autorizado. Se requiere inicio de sesión.'}, status=401)

    if usuario.rol != 'ESTUDIANTE':
        registrar_auditoria(usuario, 'ACCESO_DENEGADO',
                            f"Intento de acceso denegado al portal ({request.path}) con rol {usuario.rol}")
        return None, JsonResponse({'error': 'Prohibido. Esta sección es solo para estudiantes.'}, status=403)

    estudiante = getattr(usuario, 'estudiante', None)  # RelatedObjectDoesNotExist es un AttributeError
    if estudiante is None:
        registrar_auditoria(usuario, 'ACCESO_DENEGADO',
                            f"Cuenta de estudiante {usuario.correo} sin estudiante asociado intentó acceder a {request.path}")
        return None, JsonResponse(
            {'error': 'Prohibido. Su cuenta no está asociada a ningún estudiante. Comuníquese con la universidad.'},
            status=403,
        )
    return estudiante, None
