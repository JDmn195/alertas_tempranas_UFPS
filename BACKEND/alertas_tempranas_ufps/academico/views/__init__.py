from .import_views import (
    importar_estudiantes_dirplan,
    importar_historial_academico,
    importar_oferta_academica,
    importar_docentes,
)
from .student_views import listar_estudiantes, obtener_detalle_estudiante, obtener_indicadores_estudiante, obtener_historial_academico, obtener_intervenciones_estudiante
from .indicator_views import listar_indicadores_cursos, detalle_curso  # HU-11
from .teacher_views import teacher_dashboard, teacher_course_students  # Panel del Docente
