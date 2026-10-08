import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from academico.asistencia import numero_o_none, obtener_umbral_inasistencia
from academico.models import Curso
from usuarios.decorators import requiere_rol
from usuarios.utils import registrar_auditoria


def _parsear_umbral(valor):
    """Devuelve (umbral, None) con un Decimal entre 0 y 100 o None, o (None, mensaje de error)."""
    if valor is None:
        return None, None
    if isinstance(valor, bool) or not isinstance(valor, (int, float, str)):
        return None, "El umbral debe ser un número entre 0 y 100, o null para usar el umbral general."
    try:
        umbral = Decimal(str(valor).strip())
    except InvalidOperation:
        return None, "El umbral debe ser un número entre 0 y 100, o null para usar el umbral general."
    if not umbral.is_finite() or umbral < 0 or umbral > 100:
        return None, "El umbral debe estar entre 0 y 100."
    return umbral.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), None


def _texto_umbral(umbral):
    return f"{umbral}%" if umbral is not None else "general"


@csrf_exempt
@require_http_methods(["PATCH"])
@requiere_rol(['ADMINISTRADOR'])
def umbral_inasistencia_curso(request, curso_id):
    """
    HU-35: PATCH /api/academico/cursos/<curso_id>/umbral-inasistencia/

    Body: {"umbral": número entre 0 y 100, o null para volver al umbral general}.
    El umbral del curso reemplaza al general (regla INASISTENCIA activa) para ese curso.
    """
    try:
        curso = Curso.objects.select_related('materia').get(id=curso_id)
    except Curso.DoesNotExist:
        return JsonResponse({'error': 'El curso no existe.'}, status=404)

    try:
        body = json.loads(request.body or b'{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'El cuerpo de la petición debe ser JSON.'}, status=400)
    if not isinstance(body, dict) or 'umbral' not in body:
        return JsonResponse({'error': "Debe enviar el campo 'umbral' (número entre 0 y 100, o null)."}, status=400)

    nuevo, error = _parsear_umbral(body['umbral'])
    if error:
        return JsonResponse({'error': error}, status=400)

    anterior = curso.umbral_inasistencia
    curso.umbral_inasistencia = nuevo
    curso.save(update_fields=['umbral_inasistencia'])

    registrar_auditoria(
        request.usuario, 'MODIFICAR_UMBRAL_INASISTENCIA',
        f"Umbral de inasistencia del curso {curso.materia.codigo}-{curso.grupo} ({curso.materia.nombre}, id {curso.id}): "
        f"anterior {_texto_umbral(anterior)}, nuevo {_texto_umbral(nuevo)}.",
    )

    # HU-36: el cambio de umbral puede generar o cerrar alertas del curso
    from academico.services.asistencia import periodo_actual
    from alertas.alertas_inasistencia import evaluar_inasistencia_curso
    from alertas.tareas import ejecutar_en_segundo_plano
    ejecutar_en_segundo_plano(evaluar_inasistencia_curso, curso, periodo_actual(), request.usuario)

    umbral, origen = obtener_umbral_inasistencia(curso)
    return JsonResponse({
        'curso_id':        curso.id,
        'umbral_curso':    numero_o_none(curso.umbral_inasistencia),
        'umbral_efectivo': numero_o_none(umbral),
        'origen':          origen,
        'mensaje': (
            'Umbral de inasistencia del curso actualizado.' if nuevo is not None
            else 'El curso vuelve a usar el umbral general de inasistencia.'
        ),
    })
