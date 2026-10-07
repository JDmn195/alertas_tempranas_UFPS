"""
academico/services/asistencia.py

HU-33: Helpers reutilizables para el registro de asistencia.
Usados tanto en attendance_views.py (registro manual) como en import_views.py (importación).
"""
import unicodedata

from academico.models import Periodo, Nota


ESTADOS_ASISTENCIA = ('ASISTIO', 'FALTA', 'FALTA_JUSTIFICADA')

_ABREVIATURAS = {
    'A':  'ASISTIO',
    'F':  'FALTA',
    'FJ': 'FALTA_JUSTIFICADA',
}


def periodo_actual():
    """
    Devuelve el Periodo más reciente registrado (por año y semestre) o None.
    La asistencia se toma siempre sobre la matrícula de este periodo.
    """
    return Periodo.objects.order_by('-anio', '-semestre').first()


def normalizar_estado(valor):
    """
    Normaliza un valor de estado de asistencia:
      - Elimina espacios, convierte a mayúsculas y quita tildes.
      - Acepta abreviaturas: A → ASISTIO, F → FALTA, FJ → FALTA_JUSTIFICADA.
      - Acepta nombres canónicos directamente.
      - Devuelve el valor canónico o None si el valor no es reconocido.
    """
    if not valor or not isinstance(valor, str):
        return None

    nfd = unicodedata.normalize('NFD', valor)
    limpio = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn').strip().upper()

    if limpio in _ABREVIATURAS:
        return _ABREVIATURAS[limpio]
    if limpio in ESTADOS_ASISTENCIA:
        return limpio
    return None


def estudiantes_del_curso(curso, periodo) -> set:
    """
    Retorna el conjunto de códigos de estudiantes matriculados en un curso en un periodo:
    los que tienen una Nota con ese (estudiante, curso, periodo), aunque sus notas sean null.
    """
    return set(
        Nota.objects.filter(curso=curso, periodo=periodo)
        .values_list('estudiante_id', flat=True)
    )


def puede_gestionar_curso(usuario, curso) -> bool:
    """ADMINISTRADOR gestiona cualquier curso; DOCENTE solo los que tiene asignados."""
    if usuario.rol == 'ADMINISTRADOR':
        return True
    return usuario.rol == 'DOCENTE' and curso.docente.usuario_id == usuario.id
