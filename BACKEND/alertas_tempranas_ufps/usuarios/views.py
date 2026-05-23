import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core import signing
from django.core.mail import send_mail
from django.conf import settings
from django.apps import apps
from .models import Usuario

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

        # Búsqueda simple (sin encriptar como pidió el usuario)
        try:
            usuario = Usuario.objects.get(correo=correo, contrasena=contrasena)
            
            if not usuario.activo:
                return JsonResponse({'error': 'La cuenta está desactivada.'}, status=403)

            # Lógica de cambio obligatorio (primer login)
            # Verifica si el correo existe en Docentes y si la contraseña es igual al código
            cambio_obligatorio = False
            try:
                Docente = apps.get_model('academico', 'Docente')
                # Buscamos el docente asociado a este usuario
                docente = Docente.objects.get(usuario=usuario)
                if contrasena == docente.codigo:
                    cambio_obligatorio = True
            except (Docente.DoesNotExist, LookupError):
                # Si no es docente o no existe el modelo, no aplica cambio obligatorio por esta lógica
                pass

            # Respuesta exitosa con datos del usuario
            return JsonResponse({
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
            
            # Generar token firmado con marca de tiempo
            signer = signing.TimestampSigner()
            token = signer.sign(signing.dumps({'user_id': usuario.id}))
            
            link = f"{settings.FRONTEND_URL}/reset-password/{token}"
            
            asunto = 'Recuperación de contraseña - SAT UFPS'
            mensaje = f'Hola {usuario.nombre},\n\nHaz clic en el siguiente enlace para restablecer tu contraseña:\n\n{link}\n\nEste enlace es válido por 1 hora.'
            
            send_mail(asunto, mensaje, settings.DEFAULT_FROM_EMAIL, [correo])
            
            return JsonResponse({'mensaje': 'Correo de recuperación enviado.'}, status=200)
            
        except Usuario.DoesNotExist:
            # Por seguridad no revelamos si el correo existe o no
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
        user_id = data.get('user_id') # Para el caso de cambio obligatorio directo

        if token:
            # Flujo de recuperación por correo
            try:
                signer = signing.TimestampSigner()
                # Expira en 3600 segundos (1 hora)
                original_data = signer.unsign(token, max_age=3600)
                payload = signing.loads(original_data)
                usuario = Usuario.objects.get(id=payload['user_id'])
            except signing.SignatureExpired:
                return JsonResponse({'error': 'El enlace ha expirado.'}, status=400)
            except (signing.BadSignature, Exception):
                return JsonResponse({'error': 'Enlace de recuperación inválido.'}, status=400)
        elif user_id:
            # Flujo de cambio obligatorio tras login
            try:
                usuario = Usuario.objects.get(id=user_id)
            except Usuario.DoesNotExist:
                return JsonResponse({'error': 'Usuario no encontrado.'}, status=404)
        else:
            return JsonResponse({'error': 'Información insuficiente para cambiar contraseña.'}, status=400)

        # Actualizar contraseña
        usuario.contrasena = nueva_contrasena
        usuario.save()
        
        return JsonResponse({'mensaje': 'Contraseña actualizada correctamente.'}, status=200)
            
    except Exception as e:
        return JsonResponse({'error': f'Error al actualizar contraseña: {str(e)}'}, status=500)


@csrf_exempt
def listar_usuarios(request):
    if request.method == 'GET':
        usuarios = Usuario.objects.all().order_by('nombre')
        results = []
        for u in usuarios:
            roles = u.rol.split(',') if u.rol else []
            results.append({
                'id': u.id,
                'nombre': u.nombre,
                'correo': u.correo,
                'roles': roles,
                'activo': u.activo,
            })
        return JsonResponse({'usuarios': results}, status=200)
        
    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Body JSON inválido.'}, status=400)
        
        nombre = body.get('nombre', '').strip()
        correo = body.get('correo', '').strip()
        contrasena = body.get('contrasena', '').strip()
        roles = body.get('roles', [])

        if not nombre or not correo or not contrasena:
            return JsonResponse({'error': 'Nombre, correo y contraseña son obligatorios.'}, status=400)

        if not isinstance(roles, list):
            return JsonResponse({'error': 'El campo roles debe ser una lista.'}, status=400)
        
        roles = [r.strip().upper() for r in roles if r.strip()]
        if len(roles) == 0:
            return JsonResponse({'error': 'Debe asignar al menos un rol.'}, status=400)

        roles_validos = ['DOCENTE', 'DIRECTOR', 'BIENESTAR', 'ADMINISTRADOR']
        for r in roles:
            if r not in roles_validos:
                return JsonResponse({'error': f'Rol inválido: {r}'}, status=400)

        if Usuario.objects.filter(correo=correo).exists():
            return JsonResponse({'error': 'El correo electrónico ya está registrado.'}, status=400)

        try:
            usuario = Usuario.objects.create(
                nombre=nombre,
                correo=correo,
                contrasena=contrasena,
                rol=','.join(roles),
                activo=True
            )
        except Exception as e:
            return JsonResponse({'error': f'Error al crear el usuario: {str(e)}'}, status=500)

        return JsonResponse({
            'mensaje': 'Usuario creado correctamente.',
            'usuario': {
                'id': usuario.id,
                'nombre': usuario.nombre,
                'correo': usuario.correo,
                'roles': usuario.rol.split(','),
                'activo': usuario.activo,
            }
        }, status=201)
        
    else:
        return JsonResponse({'error': 'Método no permitido. Se espera GET o POST.'}, status=405)


@csrf_exempt
def gestionar_usuario(request, usuario_id):
    if request.method not in ['PUT', 'POST']:
        return JsonResponse({'error': 'Método no permitido. Se espera PUT o POST.'}, status=405)

    try:
        usuario = Usuario.objects.get(id=usuario_id)
    except Usuario.DoesNotExist:
        return JsonResponse({'error': 'Usuario no encontrado.'}, status=404)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Body JSON inválido.'}, status=400)

    nombre = body.get('nombre')
    correo = body.get('correo')
    activo = body.get('activo')
    roles = body.get('roles')

    if nombre is not None:
        usuario.nombre = nombre
    if correo is not None:
        usuario.correo = correo
    if activo is not None:
        usuario.activo = bool(activo)

    if roles is not None:
        if not isinstance(roles, list):
            return JsonResponse({'error': 'El campo roles debe ser una lista.'}, status=400)
        
        roles = [r.strip().upper() for r in roles if r.strip()]
        # Validar que tenga al menos un rol (Escenario 3)
        if len(roles) == 0:
            return JsonResponse({'error': 'Debe asignar al menos un rol.'}, status=400)

        roles_validos = ['DOCENTE', 'DIRECTOR', 'BIENESTAR', 'ADMINISTRADOR']
        for r in roles:
            if r not in roles_validos:
                return JsonResponse({'error': f'Rol inválido: {r}'}, status=400)

        usuario.rol = ','.join(roles)

    try:
        usuario.save()
    except Exception as e:
        return JsonResponse({'error': f'Error al guardar el usuario: {str(e)}'}, status=500)

    return JsonResponse({
        'mensaje': 'Usuario actualizado correctamente.',
        'usuario': {
            'id': usuario.id,
            'nombre': usuario.nombre,
            'correo': usuario.correo,
            'roles': usuario.rol.split(','),
            'activo': usuario.activo,
        }
    }, status=200)

