"""
Alcance de cada rol sobre las alertas y su seguimiento.

DIRECTOR, BIENESTAR y ADMINISTRADOR ven todas las alertas. Un DOCENTE solo las
de estudiantes con notas en los cursos que dicta (el mismo criterio del listado
de alertas y de los reportes).
"""
from django.http import JsonResponse

from academico.models import Curso, Nota
from usuarios.utils import registrar_auditoria


def estudiantes_del_docente(usuario):
    """Códigos de los estudiantes del docente, o None si el rol no tiene restricción."""
    if usuario.rol != 'DOCENTE':
        return None
    docente = getattr(usuario, 'docente', None)  # RelatedObjectDoesNotExist es un AttributeError
    if docente is None:
        return set()
    cursos = Curso.objects.filter(docente=docente).values_list('id', flat=True)
    return set(
        Nota.objects.filter(curso__in=cursos).values_list('estudiante_id', flat=True).distinct()
    )


def puede_acceder_alerta(usuario, alerta):
    estudiantes = estudiantes_del_docente(usuario)
    return estudiantes is None or alerta.estudiante_id in estudiantes


def denegar_acceso_alerta():
    return JsonResponse(
        {'error': 'No tiene acceso a esta alerta: el estudiante no pertenece a sus cursos.'},
        status=403,
    )


def filtrar_intervenciones_visibles(usuario, queryset):
    """Un DOCENTE solo ve las intervenciones que él registró (no las de Bienestar ni de otros docentes)."""
    return queryset.filter(usuario=usuario) if usuario.rol == 'DOCENTE' else queryset


def puede_ver_intervencion(usuario, intervencion):
    return usuario.rol != 'DOCENTE' or intervencion.usuario_id == usuario.id


def denegar_acceso_intervencion(usuario, intervencion):
    registrar_auditoria(
        usuario, 'ACCESO_DENEGADO',
        f"Docente intentó ver la intervención {intervencion.id} registrada por otro usuario",
    )
    return JsonResponse({'error': 'No tiene acceso a esta intervención.'}, status=403)

