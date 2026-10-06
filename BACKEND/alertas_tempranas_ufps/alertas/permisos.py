"""
Alcance de cada rol sobre las alertas y su seguimiento.

DIRECTOR, BIENESTAR y ADMINISTRADOR ven todas las alertas. Un DOCENTE solo las
de estudiantes con notas en los cursos que dicta (el mismo criterio del listado
de alertas y de los reportes).
"""
from django.http import JsonResponse

from academico.models import Curso, Nota


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
