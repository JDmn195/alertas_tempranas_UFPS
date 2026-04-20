import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
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

            # Respuesta exitosa con datos del usuario
            return JsonResponse({
                'id': usuario.id,
                'nombre': usuario.nombre,
                'correo': usuario.correo,
                'rol': usuario.rol,
                'mensaje': 'Inicio de sesión exitoso.'
            }, status=200)

        except Usuario.DoesNotExist:
            return JsonResponse({'error': 'Credenciales incorrectas.'}, status=401)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error inesperado: {str(e)}'}, status=500)
