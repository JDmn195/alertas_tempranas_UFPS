import json
import jwt
from datetime import datetime, timedelta, timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core import signing
from django.core.mail import send_mail
from django.conf import settings
from django.apps import apps
from django.views.decorators.http import require_http_methods
from .models import Usuario
from .decorators import requiere_rol
from .utils import registrar_auditoria

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

        try:
            usuario = Usuario.objects.get(correo=correo, contrasena=contrasena)
            
            if not usuario.activo:
                return JsonResponse({'error': 'La cuenta está desactivada.'}, status=403)

            # Lógica de cambio obligatorio (primer login)
            cambio_obligatorio = False
            try:
                Docente = apps.get_model('academico', 'Docente')
                docente = Docente.objects.get(usuario=usuario)
                if contrasena == docente.codigo:
                    cambio_obligatorio = True
            except (Docente.DoesNotExist, LookupError):
                pass

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
                'cambio_obligatorio': cambio_obligatorio,
                'mensaje': 'Inicio de sesión exitoso.'
            }, status=200)

        except Usuario.DoesNotExist:
            return JsonResponse({'error': 'Credenciales incorrectas.'}, status=401)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error inesperado: {str(e)}'}, status=500)

@csrf_exempt
def solicitar_recuperacion(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido.'}, status=405)
    
    try:
        data = json.loads(request.body)
        correo = data.get('email')
        
        try:
            usuario = Usuario.objects.get(correo=correo)
            
            signer = signing.TimestampSigner()
            token = signer.sign(signing.dumps({'user_id': usuario.id}))
            
            link = f"{settings.FRONTEND_URL}/reset-password/{token}"
            
            asunto = 'Recuperación de contraseña - SAT UFPS'
            mensaje = f'Hola {usuario.nombre},\n\nHaz clic en el siguiente enlace para restablecer tu contraseña:\n\n{link}\n\nEste enlace es válido por 1 hora.'
            
            send_mail(asunto, mensaje, settings.DEFAULT_FROM_EMAIL, [correo])
            
            return JsonResponse({'mensaje': 'Correo de recuperación enviado.'}, status=200)
            
        except Usuario.DoesNotExist:
            return JsonResponse({'mensaje': 'Si el correo existe, se enviarán instrucciones.'}, status=200)
            
    except Exception as e:
        return JsonResponse({'error': f'Error al procesar la solicitud: {str(e)}'}, status=500)

@csrf_exempt
def cambiar_contrasena(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido.'}, status=405)
    
    try:
        data = json.loads(request.body)
        token = data.get('token')
        nueva_contrasena = data.get('password')
        user_id = data.get('user_id')

        if token:
            try:
                signer = signing.TimestampSigner()
                original_data = signer.unsign(token, max_age=3600)
                payload = signing.loads(original_data)
                usuario = Usuario.objects.get(id=payload['user_id'])
            except signing.SignatureExpired:
                return JsonResponse({'error': 'El enlace ha expirado.'}, status=400)
            except (signing.BadSignature, Exception):
                return JsonResponse({'error': 'Enlace de recuperación inválido.'}, status=400)
        elif user_id:
            try:
                usuario = Usuario.objects.get(id=user_id)
            except Usuario.DoesNotExist:
                return JsonResponse({'error': 'Usuario no encontrado.'}, status=404)
        else:
            return JsonResponse({'error': 'Información insuficiente para cambiar contraseña.'}, status=400)

        usuario.contrasena = nueva_contrasena
        usuario.save()
        
        return JsonResponse({'mensaje': 'Contraseña actualizada correctamente.'}, status=200)
            
    except Exception as e:
        return JsonResponse({'error': f'Error al actualizar contraseña: {str(e)}'}, status=500)



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
            
        # Contraseña por defecto igual al correo
        nuevo_usuario = Usuario.objects.create(
            nombre=nombre,
            correo=correo,
            rol=rol,
            contrasena=correo,
            activo=True
        )
        
        registrar_auditoria(request.usuario, 'CREAR_USUARIO', f"Creado usuario {correo} con rol {rol}")
        return JsonResponse({'mensaje': 'Usuario creado exitosamente', 'id': nuevo_usuario.id}, status=201)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

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
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

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
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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
