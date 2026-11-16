"""
SDAT-303: nivel de riesgo del periodo más reciente de cada estudiante.

Antes cada vista repetía una subconsulta correlacionada por fila de RiesgoEstudiantePeriodo
(~150 ms con 16 000 filas y hasta 4 veces por petición). Ahora se lee una vez, sin join ni orden
en la base (los periodos son pocos y se ordenan en memoria), y se conserva la fila más reciente
de cada estudiante. El resultado es el mismo.
"""
from academico.models import Periodo
from alertas.models import RiesgoEstudiantePeriodo


def ultimo_riesgo_por_estudiante(estudiantes=None):
    """Devuelve {codigo_estudiante: nivel_riesgo} del periodo más reciente de cada estudiante.

    `estudiantes` (opcional, lista o consulta de códigos) limita la lectura a esos estudiantes.
    """
    orden_periodo = {pid: (anio, semestre) for pid, anio, semestre in Periodo.objects.values_list('id', 'anio', 'semestre')}
    filas = RiesgoEstudiantePeriodo.objects.all()
    if estudiantes is not None:
        filas = filas.filter(estudiante_id__in=estudiantes)
    mejor = {}  # estudiante -> (clave de orden, nivel)
    for fila_id, estudiante_id, periodo_id, nivel in filas.values_list('id', 'estudiante_id', 'periodo_id', 'nivel_riesgo'):
        clave = (*orden_periodo.get(periodo_id, (0, 0)), fila_id)
        actual = mejor.get(estudiante_id)
        if actual is None or clave > actual[0]:
            mejor[estudiante_id] = (clave, nivel)
    return {estudiante_id: nivel for estudiante_id, (_, nivel) in mejor.items()}
