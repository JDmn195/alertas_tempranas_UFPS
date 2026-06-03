import json
import threading
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from ..models import Regla
from django.db.models import ProtectedError
from usuarios.models import Usuario
from usuarios.decorators import requiere_rol
from usuarios.utils import registrar_auditoria


def _recalcular_en_background(usuario, regla_id=None):
    """
    Lanza reprocesar_alertas_completas en un hilo separado para no bloquear la respuesta.
    Fix 3.3: si se pasa regla_id, solo reprocesa alertas de esa regla.
    """
    from alertas.views.alert_generation_views import reprocesar_alertas_completas
    from alertas.models import Regla as _Regla
    try:
        regla_obj = None
        if regla_id:
            try:
                regla_obj = _Regla.objects.get(pk=regla_id)
            except _Regla.DoesNotExist:
                pass
        reprocesar_alertas_completas(usuario=usuario, regla_especifica=regla_obj)
    except Exception:
        pass  # Errores en background no deben afectar la respuesta al usuario


@csrf_exempt
@require_http_methods(["GET", "POST"])
@requiere_rol(['ADMINISTRADOR', 'DIRECTOR', 'BIENESTAR'])
def listar_crear_reglas(request):
    """
    GET: Lista todas las reglas.
    POST: Crea una nueva regla y recalcula el riesgo de todos los estudiantes.
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

            # Recalcular riesgo en background — Fix 3.3: solo para esta regla
            threading.Thread(
                target=_recalcular_en_background,
                args=(request.usuario, regla.id),
                daemon=True
            ).start()

            return JsonResponse({
                'id': regla.id,
                'mensaje': 'Regla creada exitosamente. El riesgo de los estudiantes se está recalculando.'
            }, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
@requiere_rol(['ADMINISTRADOR', 'DIRECTOR', 'BIENESTAR'])
def detalle_regla(request, pk):
    """
    GET: Obtiene detalle de una regla.
    PUT: Actualiza/activa/desactiva una regla y recalcula el riesgo de todos los estudiantes.
    DELETE: Elimina una regla (solo si no tiene alertas asociadas).
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

            estado_anterior = regla.activo
            regla.nombre = body.get('nombre', regla.nombre)
            regla.tipo = body.get('tipo', regla.tipo)
            regla.valor_umbral = body.get('valor_umbral', regla.valor_umbral)
            regla.operador = body.get('operador', regla.operador)
            regla.nivel = body.get('nivel', regla.nivel)
            regla.activo = body.get('activo', regla.activo)
            regla.descripcion = body.get('descripcion', regla.descripcion)
            regla.save()

            if estado_anterior is True and regla.activo is False:
                accion = 'DESACTIVAR_REGLA'
                msg_audit = f"Regla '{regla.nombre}' desactivada."
                msg_resp  = 'Regla desactivada exitosamente. El riesgo de los estudiantes se está recalculando.'
            elif estado_anterior is False and regla.activo is True:
                accion = 'ACTIVAR_REGLA'
                msg_audit = f"Regla '{regla.nombre}' activada."
                msg_resp  = 'Regla activada exitosamente. El riesgo de los estudiantes se está recalculando.'
            else:
                accion = 'MODIFICAR_REGLA'
                msg_audit = f"Regla '{regla.nombre}' modificada."
                msg_resp  = 'Regla actualizada exitosamente. El riesgo de los estudiantes se está recalculando.'

            registrar_auditoria(request.usuario, accion, msg_audit)

            # Recalcular riesgo en background — Fix 3.3: solo para esta regla
            threading.Thread(
                target=_recalcular_en_background,
                args=(request.usuario, regla.id),
                daemon=True
            ).start()

            return JsonResponse({'mensaje': msg_resp})
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
