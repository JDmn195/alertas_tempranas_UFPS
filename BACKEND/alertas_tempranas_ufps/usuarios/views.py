import json
import logging
import secrets
import jwt
from datetime import datetime, timedelta, timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.http import require_http_methods
from .models import Usuario
from .decorators import obtener_usuario_de_request, requiere_rol
from .utils import registrar_auditoria

logger = logging.getLogger(__name__)

SALT_CAMBIO_CONTRASENA = 'usuarios.cambiar-contrasena'
VIGENCIA_TOKEN_CAMBIO = 3600  # segundos


def _huella_contrasena(usuario):
    """Cambia en cuanto cambia la contraseña, así un enlace ya usado deja de servir."""
    return salted_hmac('usuarios.huella-contrasena', usuario.contrasena).hexdigest()[:16]


def _generar_token_cambio(usuario):
    return signing.dumps(
        {'user_id': usuario.id, 'huella': _huella_contrasena(usuario)},
        salt=SALT_CAMBIO_CONTRASENA,
    )


@csrf_exempt
def login_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido. Se espera POST.'}, status=405)

    try:
        data = json.loads(request.body)
        correo = data.get('email')
        contrasena = data.get('password')

        if not correo or not contrasena:
            return JsonResponse({'error': 'Faltan credenciales.'}, status=400)

        usuario = Usuario.objects.filter(correo=correo).first()
        if usuario is None:
            # Hashear igual para no revelar por el tiempo de respuesta si el correo existe
            Usuario().set_password(contrasena)
            return JsonResponse({'error': 'Credenciales incorrectas.'}, status=401)
        if not usuario.check_password(contrasena):
            return JsonResponse({'error': 'Credenciales incorrectas.'}, status=401)

        if not usuario.activo:
            return JsonResponse({'error': 'La cuenta está desactivada.'}, status=403)

        # Contraseña temporal: no se entrega sesión, solo un token para cambiarla
        if usuario.debe_cambiar_contrasena:
            return JsonResponse({
                'cambio_obligatorio': True,
                'token_cambio': _generar_token_cambio(usuario),
            }, status=200)

        # Lógica de JWT
        payload = {
            'user_id': usuario.id,
            'exp': datetime.now(timezone.utc) + timedelta(days=1),
            'iat': datetime.now(timezone.utc)
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

        registrar_auditoria(usuario, 'LOGIN', f"Usuario {usuario.correo} inició sesión exitosamente.")

        # Respuesta exitosa con datos del usuario
        return JsonResponse({
            'token': token,
            'id': usuario.id,
            'nombre': usuario.nombre,
            'correo': usuario.correo,
            'rol': usuario.rol,
            'cambio_obligatorio': False,
            'mensaje': 'Inicio de sesión exitoso.'
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido.'}, status=400)
    except Exception:
        logger.exception("Error inesperado en el inicio de sesión")
        return JsonResponse({'error': 'Error inesperado al iniciar sesión.'}, status=500)

@csrf_exempt
def solicitar_recuperacion(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido.'}, status=405)

    try:
        data = json.loads(request.body)
        correo = data.get('email')

        usuario = Usuario.objects.filter(correo=correo, activo=True).first() if correo else None
        if usuario:
            link = f"{settings.FRONTEND_URL}/reset-password/{_generar_token_cambio(usuario)}"

            asunto = 'Recuperación de contraseña - SAT UFPS'
            mensaje = f'Hola {usuario.nombre},\n\nHaz clic en el siguiente enlace para restablecer tu contraseña:\n\n{link}\n\nEste enlace es válido por 1 hora y solo puede usarse una vez.'

            send_mail(asunto, mensaje, settings.DEFAULT_FROM_EMAIL, [usuario.correo])

        # Misma respuesta exista o no el correo, para no revelar qué cuentas existen
        return JsonResponse({'mensaje': 'Si el correo existe, se enviarán instrucciones.'}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido.'}, status=400)
    except Exception:
        logger.exception("Error al procesar la solicitud de recuperación")
        return JsonResponse({'error': 'Error al procesar la solicitud.'}, status=500)

@csrf_exempt
def cambiar_contrasena(request):
    """
    POST {token, password}. El token sale del enlace de recuperación o del login
    con contraseña temporal; vale 1 hora y deja de servir en cuanto se cambia la contraseña.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido.'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido.'}, status=400)

    token = data.get('token')
    nueva_contrasena = data.get('password')
    if not token or not nueva_contrasena:
        return JsonResponse({'error': 'Información insuficiente para cambiar contraseña.'}, status=400)

    try:
        payload = signing.loads(token, salt=SALT_CAMBIO_CONTRASENA, max_age=VIGENCIA_TOKEN_CAMBIO)
        usuario = Usuario.objects.get(id=payload['user_id'], activo=True)
    except signing.SignatureExpired:
        return JsonResponse({'error': 'El enlace ha expirado.'}, status=400)
    except (signing.BadSignature, Usuario.DoesNotExist, KeyError, TypeError):
        return JsonResponse({'error': 'Enlace de recuperación inválido.'}, status=400)

    if not constant_time_compare(payload.get('huella', ''), _huella_contrasena(usuario)):
        return JsonResponse({'error': 'Este enlace ya fue utilizado.'}, status=400)

    try:
        validate_password(nueva_contrasena, user=usuario)
    except ValidationError as e:
        return JsonResponse({'error': ' '.join(e.messages)}, status=400)

    usuario.set_password(nueva_contrasena)
    usuario.debe_cambiar_contrasena = False
    usuario.save(update_fields=['contrasena', 'debe_cambiar_contrasena'])

    return JsonResponse({'mensaje': 'Contraseña actualizada correctamente.'}, status=200)



@require_http_methods(["GET"])
def sesion_actual(request):
    """
    GET /api/usuarios/me/
    Datos del usuario según el JWT. El frontend toma el rol de aquí y no de
    localStorage, que el usuario puede modificar.
    """
    u = obtener_usuario_de_request(request)
    if not u:
        return JsonResponse({'error': 'No autorizado. Se requiere inicio de sesión.'}, status=401)
    return JsonResponse({'id': u.id, 'nombre': u.nombre, 'correo': u.correo, 'rol': u.rol})


# --- CRUD de Usuarios (HU-26) ---

@csrf_exempt
@require_http_methods(["GET"])
@requiere_rol(['ADMINISTRADOR'])
def listar_usuarios(request):
    usuarios = Usuario.objects.all().order_by('nombre')
    data = [{
        'id': u.id,
        'nombre': u.nombre,
        'correo': u.correo,
        'rol': u.rol,
        'activo': u.activo
    } for u in usuarios]
    return JsonResponse({'usuarios': data}, status=200)

@csrf_exempt
@require_http_methods(["POST"])
@requiere_rol(['ADMINISTRADOR'])
def crear_usuario(request):
    try:
        data = json.loads(request.body)
        nombre = data.get('nombre')
        correo = data.get('correo')
        rol = data.get('rol')
        
        if not all([nombre, correo, rol]):
            return JsonResponse({'error': 'Faltan campos obligatorios'}, status=400)
            
        if Usuario.objects.filter(correo=correo).exists():
            return JsonResponse({'error': 'El correo electrónico ya está registrado.'}, status=400)
            
        # Contraseña temporal aleatoria: se muestra una sola vez al admin y
        # se obliga a cambiarla en el primer inicio de sesión
        contrasena_temporal = secrets.token_urlsafe(9)
        nuevo_usuario = Usuario(
            nombre=nombre,
            correo=correo,
            rol=rol,
            activo=True,
            debe_cambiar_contrasena=True,
        )
        nuevo_usuario.set_password(contrasena_temporal)
        nuevo_usuario.save()

        registrar_auditoria(request.usuario, 'CREAR_USUARIO', f"Creado usuario {correo} con rol {rol}")
        return JsonResponse({
            'mensaje': 'Usuario creado exitosamente',
            'id': nuevo_usuario.id,
            'contrasena_temporal': contrasena_temporal,
        }, status=201)
        
    except Exception:
        logger.exception("Error al crear usuario")
        return JsonResponse({'error': 'Error al crear el usuario.'}, status=500)

@csrf_exempt
@require_http_methods(["PUT", "PATCH"])
@requiere_rol(['ADMINISTRADOR'])
def actualizar_usuario(request, usuario_id):
    try:
        usuario_target = Usuario.objects.get(id=usuario_id)
        data = json.loads(request.body)
        
        old_rol = usuario_target.rol
        if 'nombre' in data: usuario_target.nombre = data['nombre']
        if 'rol' in data: usuario_target.rol = data['rol']
        
        usuario_target.save()
        
        if old_rol != usuario_target.rol:
            registrar_auditoria(request.usuario, 'EDITAR_ROL', f"Rol de {usuario_target.correo} cambiado de {old_rol} a {usuario_target.rol}")
            
        return JsonResponse({'mensaje': 'Usuario actualizado correctamente'})
    except Usuario.DoesNotExist:
        return JsonResponse({'error': 'Usuario no encontrado'}, status=404)
    except Exception:
        logger.exception("Error al actualizar el usuario %s", usuario_id)
        return JsonResponse({'error': 'Error al actualizar el usuario.'}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@requiere_rol(['ADMINISTRADOR'])
def desactivar_usuario(request, usuario_id):
    try:
        usuario_target = Usuario.objects.get(id=usuario_id)
        
        if usuario_target.id == request.usuario.id:
            return JsonResponse({'error': 'No puedes desactivarte a ti mismo.'}, status=400)
            
        # HU-26: Solo se desactivan
        usuario_target.activo = not usuario_target.activo
        accion = "activado" if usuario_target.activo else "desactivado"
        usuario_target.save()
        
        registrar_auditoria(request.usuario, 'DESACTIVAR_USUARIO', f"Usuario {usuario_target.correo} {accion}")
        
        return JsonResponse({'mensaje': f'Usuario {accion} correctamente', 'activo': usuario_target.activo})
    except Usuario.DoesNotExist:
        return JsonResponse({'error': 'Usuario no encontrado'}, status=404)
    except Exception:
        logger.exception("Error al activar/desactivar el usuario %s", usuario_id)
        return JsonResponse({'error': 'Error al cambiar el estado del usuario.'}, status=500)


# --- Auditoría (HU-28) ---

@csrf_exempt
@require_http_methods(["GET"])
@requiere_rol(['ADMINISTRADOR'])
def listar_auditoria(request):
    from .models import Auditoria
    
    tipo_accion = request.GET.get('tipo_accion')
    usuario_id = request.GET.get('usuario_id')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    
    qs = Auditoria.objects.select_related('usuario').all()
    
    if tipo_accion:
        qs = qs.filter(tipo_accion=tipo_accion)
    if usuario_id:
        qs = qs.filter(usuario_id=usuario_id)
    if fecha_inicio:
        qs = qs.filter(fecha_hora__gte=fecha_inicio)
    if fecha_fin:
        qs = qs.filter(fecha_hora__lte=fecha_fin)
        
    data = []
    for a in qs:
        data.append({
            'id': a.id,
            'usuario_nombre': a.usuario.nombre if a.usuario else 'Sistema',
            'usuario_correo': a.usuario.correo if a.usuario else '',
            'fecha_hora': a.fecha_hora.isoformat(),
            'tipo_accion': a.tipo_accion,
            'tipo_accion_display': a.get_tipo_accion_display(),
            'detalle': a.detalle
        })
        
    return JsonResponse({'registros': data}, status=200)
