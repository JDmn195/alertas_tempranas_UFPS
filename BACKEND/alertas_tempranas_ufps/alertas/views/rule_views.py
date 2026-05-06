import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from ..models import Regla
from usuarios.models import Usuario

@csrf_exempt
@require_http_methods(["GET", "POST"])
def listar_crear_reglas(request):
    """
    GET: Lista todas las reglas.
    POST: Crea una nueva regla (Solo DIRECTOR o BIENESTAR).
    """
    if request.method == "GET":
        reglas = Regla.objects.all().order_by('-activo', 'tipo')
        data = [{
            'id': r.id,
            'nombre': r.nombre,
            'tipo': r.tipo,
            'tipo_display': r.get_tipo_display(),
            'valor_umbral': float(r.valor_umbral),
            'operador': r.operador,
            'nivel': r.nivel,
            'activo': r.activo,
            'descripcion': r.descripcion
        } for r in reglas]
        return JsonResponse(data, safe=False)

    elif request.method == "POST":
        try:
            body = json.loads(request.body)
            # Validación básica de permisos (en un entorno real usaríamos decoradores de permisos)
            usuario_id = body.get('usuario_id')
            if not usuario_id:
                return JsonResponse({'error': 'usuario_id es requerido'}, status=400)
            
            usuario = get_object_or_404(Usuario, id=usuario_id)
            if usuario.rol not in [ 'BIENESTAR', 'ADMINISTRADOR']:
                return JsonResponse({'error': 'No tiene permisos para crear reglas'}, status=403)

            regla = Regla.objects.create(
                nombre=body.get('nombre'),
                tipo=body.get('tipo', 'PROMEDIO'),
                valor_umbral=body.get('valor_umbral', 0.0),
                operador=body.get('operador', '<'),
                nivel=body.get('nivel', 'medium'),
                activo=body.get('activo', True),
                descripcion=body.get('descripcion', '')
            )
            return JsonResponse({'id': regla.id, 'mensaje': 'Regla creada exitosamente'}, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

from django.db.models import ProtectedError

@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def detalle_regla(request, pk):
    """
    GET: Obtiene detalle de una regla.
    PUT: Actualiza una regla.
    DELETE: Elimina una regla.
    """
    regla = get_object_or_404(Regla, pk=pk)

    if request.method == "GET":
        return JsonResponse({
            'id': regla.id,
            'nombre': regla.nombre,
            'tipo': regla.tipo,
            'valor_umbral': float(regla.valor_umbral),
            'operador': regla.operador,
            'nivel': regla.nivel,
            'activo': regla.activo,
            'descripcion': regla.descripcion
        })

    elif request.method == "PUT":
        try:
            body = json.loads(request.body)
            usuario_id = body.get('usuario_id')
            usuario = get_object_or_404(Usuario, id=usuario_id)
            if usuario.rol not in ['BIENESTAR', 'ADMINISTRADOR']:
                return JsonResponse({'error': 'No tiene permisos para modificar reglas'}, status=403)

            regla.nombre = body.get('nombre', regla.nombre)
            regla.tipo = body.get('tipo', regla.tipo)
            regla.valor_umbral = body.get('valor_umbral', regla.valor_umbral)
            regla.operador = body.get('operador', regla.operador)
            regla.nivel = body.get('nivel', regla.nivel)
            regla.activo = body.get('activo', regla.activo)
            regla.descripcion = body.get('descripcion', regla.descripcion)
            regla.save()
            return JsonResponse({'mensaje': 'Regla actualizada exitosamente'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    elif request.method == "DELETE":
        try:
            regla.delete()
            return JsonResponse({'mensaje': 'Regla eliminada exitosamente'})
        except ProtectedError:
            return JsonResponse({
                'error': 'protected_error',
                'detalle': 'No se puede eliminar la regla porque tiene alertas asociadas.'
            }, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
