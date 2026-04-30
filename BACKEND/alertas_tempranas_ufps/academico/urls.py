from django.urls import path
from .views import (
    importar_estudiantes_dirplan,
    importar_historial_academico,
    importar_oferta_academica,
    importar_docentes,
    listar_estudiantes,
    obtener_detalle_estudiante,
    obtener_indicadores_estudiante,
    obtener_historial_academico,
    listar_indicadores_cursos,
)
from .views.bitacora_views import listar_bitacoras, detalle_bitacora

urlpatterns = [
    path('students/',                           listar_estudiantes,             name='list-students'),
    path('students/<str:codigo>/',              obtener_detalle_estudiante,     name='detail-student'),
    path('students/<str:codigo>/indicators/',   obtener_indicadores_estudiante, name='student-indicators'),
    path('students/<str:codigo>/history/',      obtener_historial_academico,    name='student-history'),
    path('import/students/',                    importar_estudiantes_dirplan,   name='import-students-dirplan'),
    path('import/history/',                     importar_historial_academico,   name='import-history-individual'),
    path('import/offering/',                    importar_oferta_academica,      name='import-academic-offering'),
    path('import/teachers/',                    importar_docentes,              name='import-teachers'),
    path('courses/indicators/',                 listar_indicadores_cursos,      name='course-indicators'),
    path('bitacora/',                           listar_bitacoras,               name='list-bitacoras'),
    path('bitacora/<int:id>/',                  detalle_bitacora,               name='detail-bitacora'),
]
