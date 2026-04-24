from django.urls import path
from .views import (
    importar_estudiantes_dirplan,
    importar_historial_academico,
    importar_oferta_academica,
    importar_docentes,
    listar_estudiantes,
    obtener_detalle_estudiante,
)

urlpatterns = [
    # Lista de estudiantes con filtros
    path('students/',         listar_estudiantes,             name='list-students'),
    # Detalle de estudiante
    path('students/<str:codigo>/', obtener_detalle_estudiante,     name='detail-student'),
    # Rutas para las Historias de Usuario de Importación
    path('import/students/',  importar_estudiantes_dirplan,   name='import-students-dirplan'),
    path('import/history/',   importar_historial_academico,  name='import-history-individual'),
    path('import/offering/',  importar_oferta_academica,     name='import-academic-offering'),
    path('import/teachers/',  importar_docentes,             name='import-teachers'),
]
