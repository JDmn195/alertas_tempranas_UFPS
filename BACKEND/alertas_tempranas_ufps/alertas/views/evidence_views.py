import os
import uuid
import logging
from urllib.parse import urlparse

import httpx
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from alertas.models import Intervencion, Evidencia
from alertas.permisos import denegar_acceso_alerta, puede_acceder_alerta
from usuarios.decorators import requiere_rol

logger = logging.getLogger(__name__)

BUCKET = os.environ.get("SUPABASE_BUCKET_NAME", "evidencias")

# Formatos permitidos (los mismos que acepta el formulario: imágenes y PDF)
EXTENSIONES_PERMITIDAS = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp'}
MAX_EVIDENCIA_MB = int(os.environ.get("MAX_EVIDENCIA_MB", 10))

# Valores de ejemplo de .env.example: si siguen así, la conexión falla con
# "[Errno -2] Name or service not known" porque ese host no existe (INC-03).
_VALORES_DE_EJEMPLO = ('tu-proyecto', 'tu-service-role-key')

MSG_SIN_CONFIGURACION = (
    'El almacenamiento de evidencias no está configurado. El administrador debe definir '
    'SUPABASE_URL y SUPABASE_KEY con los datos reales del proyecto de Supabase.'
)
MSG_SIN_CONEXION = (
    'No se pudo conectar con el servicio de almacenamiento de evidencias. '
    'Inténtelo más tarde; si persiste, el administrador debe revisar SUPABASE_URL '
    '(python manage.py verificar_almacenamiento).'
)

# Cliente lazy: se inicializa la primera vez que se necesita
_supabase_client = None


def configuracion_supabase():
    """
    Retorna (url, key, problema). `problema` describe por qué la configuración no
    sirve (falta, es el valor de ejemplo o la URL no es válida), o None si está bien.
    """
    url = (os.environ.get("SUPABASE_URL") or '').strip()
    key = (os.environ.get("SUPABASE_KEY") or '').strip()
    if not url or not key:
        return url, key, 'SUPABASE_URL o SUPABASE_KEY no están definidas.'
    if any(v in url or v in key for v in _VALORES_DE_EJEMPLO):
        return url, key, 'SUPABASE_URL o SUPABASE_KEY tienen todavía el valor de ejemplo de .env.example.'
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname:
        return url, key, f"SUPABASE_URL no es una URL https válida: '{url}'."
    return url, key, None


def get_supabase():
    """Devuelve el cliente Supabase, inicializándolo si es necesario.
    Reintenta siempre que no haya un cliente válido."""
    global _supabase_client

    from supabase import create_client

    if _supabase_client is not None:
        return _supabase_client

    url, key, problema = configuracion_supabase()
    if problema:
        logger.error("Almacenamiento de evidencias mal configurado: %s", problema)
        return None

    try:
        _supabase_client = create_client(url, key)
        return _supabase_client
    except Exception as e:
        logger.error("Error al inicializar cliente Supabase: %s", e, exc_info=True)
        _supabase_client = None  # Permitir reintento en la próxima petición
        return None


@csrf_exempt
@require_http_methods(["POST"])
@requiere_rol(['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR', 'DIRECTOR'])
def upload_evidence(request, intervencion_id):
    """
    POST /api/alertas/intervenciones/<id>/evidencias/upload/
    Recibe un archivo vía form-data (key: 'file')
    """
    try:
        intervencion = Intervencion.objects.select_related('alerta').get(id=intervencion_id)
    except Intervencion.DoesNotExist:
        return JsonResponse({'error': 'Intervención no encontrada'}, status=404)
    if not puede_acceder_alerta(request.usuario, intervencion.alerta):
        return denegar_acceso_alerta()

    file_obj = request.FILES.get('file')
    if not file_obj:
        return JsonResponse({'error': 'No se proporcionó ningún archivo'}, status=400)

    ext = os.path.splitext(file_obj.name)[1].lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        return JsonResponse({
            'error': f"Formato no permitido ('{ext or 'sin extensión'}'). "
                     f"Se aceptan: {', '.join(sorted(EXTENSIONES_PERMITIDAS))}."
        }, status=400)
    if file_obj.size > MAX_EVIDENCIA_MB * 1024 * 1024:
        return JsonResponse({'error': f'El archivo supera el tamaño máximo de {MAX_EVIDENCIA_MB} MB.'}, status=413)

    supabase = get_supabase()
    if not supabase:
        return JsonResponse({'error': MSG_SIN_CONFIGURACION}, status=503)

    try:
        # 1. Nombre único, en una carpeta por intervención
        filepath = f"intervencion_{intervencion_id}/{uuid.uuid4()}{ext}"

        # 2. Subir a Supabase Storage
        supabase.storage.from_(BUCKET).upload(
            path=filepath,
            file=file_obj.read(),
            file_options={"content-type": file_obj.content_type}
        )

        # 3. URL pública (el bucket debe ser público o tener política de lectura).
        # En versiones recientes de supabase-py es una cadena.
        public_url = supabase.storage.from_(BUCKET).get_public_url(filepath)

        # 4. Guardar registro en la base de datos local
        evidencia = Evidencia.objects.create(
            intervencion=intervencion,
            archivo_url=public_url,
            nombre_archivo=file_obj.name,
            tipo_archivo=file_obj.content_type
        )

        return JsonResponse({
            'mensaje': 'Evidencia subida correctamente',
            'evidencia': {
                'id': evidencia.id,
                'url': evidencia.archivo_url,
                'nombre': evidencia.nombre_archivo,
                'tipo': evidencia.tipo_archivo,
                'fecha': evidencia.fecha_subida.strftime('%Y-%m-%d %H:%M')
            }
        }, status=201)

    except (httpx.TransportError, OSError) as e:
        # DNS, red o TLS: es un problema de configuración/infraestructura, no del archivo
        logger.error("Sin conexión con Supabase (%s) al subir evidencia para intervención %s: %s",
                     urlparse(os.environ.get("SUPABASE_URL", "")).hostname, intervencion_id, e, exc_info=True)
        return JsonResponse({'error': MSG_SIN_CONEXION}, status=503)
    except Exception as e:
        logger.error("Error inesperado al subir evidencia para intervención %s: %s",
                     intervencion_id, e, exc_info=True)
        return JsonResponse({'error': 'Error en el proceso de subida del archivo.'}, status=500)


@require_http_methods(["GET"])
@requiere_rol(['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR', 'DIRECTOR'])
def list_evidence(request, intervencion_id):
    """
    GET /api/alertas/intervenciones/<id>/evidencias/
    Lista todas las evidencias de una intervención y devuelve detalles del estado.
    """
    try:
        intervencion = Intervencion.objects.select_related('alerta__estudiante').get(id=intervencion_id)
    except Intervencion.DoesNotExist:
        return JsonResponse({'error': 'Intervención no encontrada'}, status=404)
    if not puede_acceder_alerta(request.usuario, intervencion.alerta):
        return denegar_acceso_alerta()

    evidencias = Evidencia.objects.filter(intervencion_id=intervencion_id).order_by('-fecha_subida')
    
    data = [{
        'id': e.id,
        'url': e.archivo_url,
        'nombre': e.nombre_archivo,
        'tipo': e.tipo_archivo,
        'fecha': e.fecha_subida.strftime('%Y-%m-%d %H:%M')
    } for e in evidencias]

    return JsonResponse({
        'intervencion_id': intervencion_id,
        'alerta_estado': intervencion.alerta.estado,
        'estudiante_nombre': intervencion.alerta.estudiante.nombre,
        'estudiante_codigo': intervencion.alerta.estudiante.codigo,
        'resultado': intervencion.resultado,
        'concluida': intervencion.concluida,
        'total': len(data),
        'evidencias': data
    })


@csrf_exempt
@require_http_methods(["DELETE"])
@requiere_rol(['ADMINISTRADOR', 'DOCENTE', 'BIENESTAR', 'DIRECTOR'])
def delete_evidence(request, evidencia_id):
    """
    DELETE /api/alertas/evidencias/<id>/
    Elimina el registro de la BD y del Storage.
    """
    try:
        evidencia = Evidencia.objects.select_related('intervencion__alerta').get(id=evidencia_id)
    except Evidencia.DoesNotExist:
        return JsonResponse({'error': 'Evidencia no encontrada'}, status=404)
    if not puede_acceder_alerta(request.usuario, evidencia.intervencion.alerta):
        return denegar_acceso_alerta()

    supabase = get_supabase()
    if not supabase:
        return JsonResponse({'error': MSG_SIN_CONFIGURACION}, status=503)

    # Eliminar del Storage físicamente
    try:
        # La URL es como: https://.../storage/v1/object/public/evidencias/intervencion_1/uuid.ext
        # Necesitamos extraer: intervencion_1/uuid.ext
        if f"/{BUCKET}/" in evidencia.archivo_url:
            file_path = evidencia.archivo_url.split(f"/{BUCKET}/")[-1]
            supabase.storage.from_(BUCKET).remove([file_path])
    except Exception as e:
        logger.warning("Error al eliminar archivo de Supabase (path derivado de '%s'): %s",
                       evidencia.archivo_url, e, exc_info=True)
        # Continuamos para al menos borrar de la BD si Supabase falla (o el archivo ya no existe)

    evidencia.delete()
    return JsonResponse({'mensaje': 'Evidencia eliminada correctamente'})
