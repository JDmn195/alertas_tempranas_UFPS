from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import localtime
from academico.models import BitacoraImportacion

@csrf_exempt
def listar_bitacoras(request):
    """
    Retorna la lista de todas las importaciones ordenadas de la más reciente a la más antigua.
    No incluye el detalle completo de errores por rendimiento.
    """
    if request.method == 'GET':
        bitacoras = BitacoraImportacion.objects.select_related('usuario').order_by('-fecha')
        data = []
        for b in bitacoras:
            data.append({
                "id": b.id,
                "fecha": localtime(b.fecha).strftime("%Y-%m-%d %H:%M:%S"),
                "archivo_nombre": b.archivo_nombre,
                "tipo": b.tipo,
                "total_procesados": b.total_procesados,
                "total_errores": b.total_errores,
                "exitoso": b.exitoso,
                "usuario": b.usuario.nombre if b.usuario else "Desconocido"
            })
        return JsonResponse({"status": "success", "data": data}, safe=False)
    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
def detalle_bitacora(request, id):
    """
    Retorna el detalle completo de una importación específica por ID,
    incluyendo los detalles de los errores (JSONField).
    """
    if request.method == 'GET':
        try:
            b = BitacoraImportacion.objects.select_related('usuario').get(id=id)
            data = {
                "id": b.id,
                "fecha": localtime(b.fecha).strftime("%Y-%m-%d %H:%M:%S"),
                "archivo_nombre": b.archivo_nombre,
                "tipo": b.tipo,
                "total_procesados": b.total_procesados,
                "total_errores": b.total_errores,
                "detalles_errores": b.detalles_errores,
                "exitoso": b.exitoso,
                "usuario": b.usuario.nombre if b.usuario else "Desconocido"
            }
            return JsonResponse({"status": "success", "data": data})
        except BitacoraImportacion.DoesNotExist:
            return JsonResponse({"error": "Bitácora no encontrada"}, status=404)
    return JsonResponse({"error": "Método no permitido"}, status=405)
