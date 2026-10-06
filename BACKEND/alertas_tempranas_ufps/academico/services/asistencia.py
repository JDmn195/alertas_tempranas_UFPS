"""
academico/services/asistencia.py

HU-33: Helpers reutilizables para el registro de asistencia.
Usados tanto en attendance_views.py (docente) como en import_views.py (admin).
"""
import unicodedata
from datetime import date

from academico.models import Periodo, Nota


# ── SDAT-201 / SDAT-204 ───────────────────────────────────────────────────────

def periodo_desde_fecha(fecha: date):
    """
    Deriva el Periodo correspondiente a una fecha usando la regla:
      - meses 1-6  → semestre 1
      - meses 7-12 → semestre 2

    Busca el Periodo en BD. Devuelve None si no existe;
    NUNCA lo crea (decisión HU-33).
    """
    semestre = 1 if fecha.month <= 6 else 2
    try:
        return Periodo.objects.get(anio=fecha.year, semestre=semestre)
    except Periodo.DoesNotExist:
        return None


def normalizar_estado(valor: str):
    """
    Normaliza un valor de estado de asistencia:
      - Elimina espacios, convierte a mayúsculas y quita tildes.
      - Acepta abreviaturas: A → ASISTIO, F → FALTA, FJ → FALTA_JUSTIFICADA.
      - Acepta nombres canónicos directamente.
      - Devuelve el valor canónico ('ASISTIO', 'FALTA', 'FALTA_JUSTIFICADA')
        o None si el valor no es reconocido.

    SDAT-204: controlar estados de asistió, falta y falta justificada.
    """
    if not valor or not isinstance(valor, str):
        return None

    # Quitar tildes, strip, mayúsculas
    nfd = unicodedata.normalize('NFD', valor)
    limpio = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    limpio = limpio.strip().upper()

    # Abreviaturas
    ABREVIATURAS = {
        'A':  'ASISTIO',
        'F':  'FALTA',
        'FJ': 'FALTA_JUSTIFICADA',
    }
    if limpio in ABREVIATURAS:
        return ABREVIATURAS[limpio]

    # Nombres canónicos (sin tilde ya)
    CANONICOS = {'ASISTIO', 'FALTA', 'FALTA_JUSTIFICADA'}
    if limpio in CANONICOS:
        return limpio

    return None


# ── SDAT-201 / SDAT-205 ───────────────────────────────────────────────────────

def estudiantes_del_curso(curso, periodo) -> set:
    """
    Retorna el conjunto de códigos de estudiantes que pertenecen a un curso
    en un periodo, determinado por la existencia de una Nota con ese
    (estudiante, curso, periodo). Decisión HU-33.

    SDAT-205: la pertenencia al curso es la fuente de verdad para validar
    si se puede registrar asistencia de un estudiante.
    """
    return set(
        Nota.objects.filter(curso=curso, periodo=periodo)
        .values_list('estudiante_id', flat=True)
    )
