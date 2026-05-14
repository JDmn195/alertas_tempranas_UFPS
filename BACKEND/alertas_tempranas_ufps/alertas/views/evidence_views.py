import os
import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from supabase import create_client, Client
from alertas.models import Intervencion, Evidencia

# Configuración Supabase desde variables de entorno
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
BUCKET = os.environ.get("SUPABASE_BUCKET_NAME", "evidencias")

# Inicializar cliente si las variables existen
supabase: Client = None
if URL and KEY:
    try:
        supabase = create_client(URL, KEY)
    except Exception as e:
        print(f"Error al inicializar cliente Supabase: {e}")

@csrf_exempt
@require_http_methods(["POST"])
def upload_evidence(request, intervencion_id):
    """
    POST /api/alertas/intervenciones/<id>/evidencias/upload/
    Recibe un archivo vía form-data (key: 'file')
    """
    if not supabase:
        return JsonResponse({'error': 'Configuración de Supabase no encontrada'}, status=500)

    try:
        intervencion = Intervencion.objects.get(id=intervencion_id)
    except Intervencion.DoesNotExist:
        return JsonResponse({'error': 'Intervención no encontrada'}, status=404)

    file_obj = request.FILES.get('file')
    if not file_obj:
        return JsonResponse({'error': 'No se proporcionó ningún archivo'}, status=400)

    try:
        # 1. Preparar metadatos y nombre único
        ext = os.path.splitext(file_obj.name)[1]
        unique_name = f"{uuid.uuid4()}{ext}"
        # Estructura de carpetas por intervención para orden
        filepath = f"intervencion_{intervencion_id}/{unique_name}"

        # 2. Subir a Supabase Storage
        # Leemos el contenido del archivo
        file_content = file_obj.read()
        
        supabase.storage.from_(BUCKET).upload(
            path=filepath,
            file=file_content,
            file_options={"content-type": file_obj.content_type}
        )

        # 3. Obtener URL pública (asumiendo que el bucket es público o tiene política de lectura)
        res_url = supabase.storage.from_(BUCKET).get_public_url(filepath)
        # get_public_url puede devolver la URL directamente dependiendo de la versión del SDK
        # En versiones recientes de supabase-py es una cadena
        public_url = res_url

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

    except Exception as e:
        return JsonResponse({'error': f'Error en el proceso de subida: {str(e)}'}, status=500)


@require_http_methods(["GET"])
def list_evidence(request, intervencion_id):
    """
    GET /api/alertas/intervenciones/<id>/evidencias/
    Lista todas las evidencias de una intervención y devuelve detalles del estado.
    """
    try:
        intervencion = Intervencion.objects.select_related('alerta__estudiante').get(id=intervencion_id)
    except Intervencion.DoesNotExist:
        return JsonResponse({'error': 'Intervención no encontrada'}, status=404)

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
        'total': len(data),
        'evidencias': data
    })


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_evidence(request, evidencia_id):
    """
    DELETE /api/alertas/evidencias/<id>/
    Elimina el registro de la BD y del Storage.
    """
    if not supabase:
        return JsonResponse({'error': 'Configuración de Supabase no encontrada'}, status=500)

    try:
        evidencia = Evidencia.objects.get(id=evidencia_id)
        
        # Eliminar del Storage físicamente
        try:
            # La URL es como: https://.../storage/v1/object/public/evidencias/intervencion_1/uuid.ext
            # Necesitamos extraer: intervencion_1/uuid.ext
            if f"/{BUCKET}/" in evidencia.archivo_url:
                file_path = evidencia.archivo_url.split(f"/{BUCKET}/")[-1]
                supabase.storage.from_(BUCKET).remove([file_path])
        except Exception as e:
            print(f"Error al eliminar de Supabase: {e}")
            # Continuamos para al menos borrar de la BD si Supabase falla (o el archivo ya no existe)

        evidencia.delete()
        return JsonResponse({'mensaje': 'Evidencia eliminada correctamente'})
    except Evidencia.DoesNotExist:
        return JsonResponse({'error': 'Evidencia no encontrada'}, status=404)
