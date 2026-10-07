import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from ..models import Regla
from ..tareas import ejecutar_en_segundo_plano
from django.db.models import ProtectedError
from usuarios.models import Usuario
from usuarios.decorators import requiere_rol
from usuarios.utils import registrar_auditoria


def _recalcular_en_background(usuario, regla_id=None):
    """
    Recalcula el riesgo tras crear/modificar una regla (se lanza en segundo plano).
    Fix 3.3: si se pasa regla_id, solo reprocesa alertas de esa regla.
    Para reglas de tipo CORTE, ejecuta evaluar_cortes_periodo_actual en segundo plano.
    """
    from alertas.views.alert_generation_views import reprocesar_alertas_completas
    from alertas.models import Regla as _Regla
    regla_obj = None
    if regla_id:
        try:
            regla_obj = _Regla.objects.get(pk=regla_id)
        except _Regla.DoesNotExist:
            pass

    if regla_obj and regla_obj.tipo == 'CORTE':
        from alertas.alertas_corte import evaluar_cortes_periodo_actual
        evaluar_cortes_periodo_actual(usuario=usuario)
        return

    reprocesar_alertas_completas(usuario=usuario, regla_especifica=regla_obj)


def _validar_regla_corte(tipo, valor_umbral, parametros, regla_id=None):
    if tipo != 'CORTE':
        return

    if not isinstance(parametros, dict):
        raise ValueError("Para reglas de tipo CORTE, 'parametros' debe ser un objeto JSON.")

    clave = parametros.get('clave')
    evalua = parametros.get('evalua')

    if not clave or not isinstance(clave, str) or not clave.strip():
        raise ValueError("El parámetro 'clave' es obligatorio para reglas CORTE.")
    clave = clave.strip()

    # Unicidad de clave entre reglas CORTE
    qs_clave = Regla.objects.filter(tipo='CORTE', parametros__clave=clave)
    if regla_id:
        qs_clave = qs_clave.exclude(pk=regla_id)
    if qs_clave.exists():
        raise ValueError(f"Ya existe una regla de corte con la clave '{clave}'.")

    if evalua not in ['CORTE', 'NOTA_NECESARIA']:
        raise ValueError("El parámetro 'evalua' debe ser 'CORTE' o 'NOTA_NECESARIA'.")

    # Validar valor_umbral principal entre 0.0 y 5.0
    try:
        vu = float(valor_umbral)
    except (TypeError, ValueError):
        raise ValueError("El valor del umbral debe ser numérico.")
    if vu < 0.0 or vu > 5.0:
        raise ValueError("El valor del umbral debe estar entre 0.0 y 5.0.")

    if evalua == 'CORTE':
        corte = parametros.get('corte')
        if corte not in [1, 2, 3]:
            raise ValueError("Para 'evalua': 'CORTE', 'corte' debe ser 1, 2 o 3.")

        corte_previo = parametros.get('corte_previo')
        operador_previo = parametros.get('operador_previo')
        umbral_previo = parametros.get('umbral_previo')

        tiene_previo = any(x is not None for x in [corte_previo, operador_previo, umbral_previo])
        if tiene_previo:
            if corte_previo is None or operador_previo is None or umbral_previo is None:
                raise ValueError("Para condición previa, 'corte_previo', 'operador_previo' y 'umbral_previo' deben proporcionarse juntos.")
            if corte_previo not in [1, 2]:
                raise ValueError("'corte_previo' debe ser 1 o 2.")
            if corte_previo >= corte:
                raise ValueError("'corte_previo' debe ser estrictamente menor que 'corte'.")
            if operador_previo not in ['<', '>', '<=', '>=', '==']:
                raise ValueError(f"Operador previo inválido: '{operador_previo}'.")
            try:
                up = float(umbral_previo)
            except (TypeError, ValueError):
                raise ValueError("'umbral_previo' debe ser numérico.")
            if up < 0.0 or up > 5.0:
                raise ValueError("'umbral_previo' debe estar entre 0.0 y 5.0.")


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
            'descripcion': r.descripcion,
            'parametros': r.parametros or {},
        } for r in reglas]
        return JsonResponse(data, safe=False)

    elif request.method == "POST":
        try:
            body = json.loads(request.body)
            tipo = body.get('tipo', 'PROMEDIO')
            valor_umbral = body.get('valor_umbral', 0.0)
            parametros = body.get('parametros', {})

            _validar_regla_corte(tipo, valor_umbral, parametros)

            regla = Regla.objects.create(
                nombre=body.get('nombre'),
                tipo=tipo,
                valor_umbral=valor_umbral,
                operador=body.get('operador', '<'),
                nivel=body.get('nivel', 'medium'),
                activo=body.get('activo', True),
                descripcion=body.get('descripcion', ''),
                parametros=parametros if tipo == 'CORTE' else {}
            )
            registrar_auditoria(request.usuario, 'CREAR_REGLA', f"Regla '{regla.nombre}' creada.")

            # Recalcular riesgo en background — Fix 3.3: solo para esta regla
            ejecutar_en_segundo_plano(_recalcular_en_background, request.usuario, regla.id)

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
            'descripcion': regla.descripcion,
            'parametros': regla.parametros or {},
        })

    elif request.method == "PUT":
        try:
            body = json.loads(request.body)

            nuevo_tipo = body.get('tipo', regla.tipo)
            nuevo_umbral = body.get('valor_umbral', regla.valor_umbral)
            nuevos_parametros = body.get('parametros', regla.parametros or {})

            _validar_regla_corte(nuevo_tipo, nuevo_umbral, nuevos_parametros, regla_id=regla.id)

            estado_anterior = regla.activo
            regla.nombre = body.get('nombre', regla.nombre)
            regla.tipo = nuevo_tipo
            regla.valor_umbral = nuevo_umbral
            regla.operador = body.get('operador', regla.operador)
            regla.nivel = body.get('nivel', regla.nivel)
            regla.activo = body.get('activo', regla.activo)
            regla.descripcion = body.get('descripcion', regla.descripcion)
            regla.parametros = nuevos_parametros if nuevo_tipo == 'CORTE' else {}
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
            ejecutar_en_segundo_plano(_recalcular_en_background, request.usuario, regla.id)

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
