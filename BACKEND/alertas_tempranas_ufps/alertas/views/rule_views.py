import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from ..models import Regla
from django.db.models import ProtectedError
from usuarios.models import Usuario
from usuarios.decorators import requiere_rol
from usuarios.utils import registrar_auditoria

@csrf_exempt
@require_http_methods(["GET", "POST"])
@requiere_rol(['ADMINISTRADOR', 'DIRECTOR', 'BIENESTAR'])
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

            regla = Regla.objects.create(
                nombre=body.get('nombre'),
                tipo=body.get('tipo', 'PROMEDIO'),
                valor_umbral=body.get('valor_umbral', 0.0),
                operador=body.get('operador', '<'),
                nivel=body.get('nivel', 'medium'),
                activo=body.get('activo', True),
                descripcion=body.get('descripcion', '')
            )
            registrar_auditoria(request.usuario, 'CREAR_REGLA', f"Regla '{regla.nombre}' creada.")
            return JsonResponse({'id': regla.id, 'mensaje': 'Regla creada exitosamente'}, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
@requiere_rol(['ADMINISTRADOR', 'DIRECTOR', 'BIENESTAR'])
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

            regla.nombre = body.get('nombre', regla.nombre)
            regla.tipo = body.get('tipo', regla.tipo)
            regla.valor_umbral = body.get('valor_umbral', regla.valor_umbral)
            regla.operador = body.get('operador', regla.operador)
            regla.nivel = body.get('nivel', regla.nivel)
            regla.activo = body.get('activo', regla.activo)
            regla.descripcion = body.get('descripcion', regla.descripcion)
            regla.save()
            registrar_auditoria(request.usuario, 'MODIFICAR_REGLA', f"Regla '{regla.nombre}' modificada.")
            return JsonResponse({'mensaje': 'Regla actualizada exitosamente'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    elif request.method == "DELETE":
        try:
            nombre_regla = regla.nombre
            regla.delete()
            registrar_auditoria(request.usuario, 'DESACTIVAR_REGLA', f"Regla '{nombre_regla}' eliminada.")
            return JsonResponse({'mensaje': 'Regla eliminada exitosamente'})
        except ProtectedError:
            return JsonResponse({
                'error': 'protected_error',
                'detalle': 'No se puede eliminar la regla porque tiene alertas asociadas.'
            }, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
