from django.urls import path
from .views import (
    importar_estudiantes_dirplan,
    importar_historial_academico,
    importar_oferta_academica,
    importar_estadisticas_carga,
    importar_docentes,
)

urlpatterns = [
    # Rutas para las Historias de Usuario de Importación
    path('import/students/',  importar_estudiantes_dirplan,   name='import-students-dirplan'),
    path('import/history/',   importar_historial_academico,  name='import-history-individual'),
    path('import/offering/',  importar_oferta_academica,     name='import-academic-offering'),
    path('import/stats/',     importar_estadisticas_carga,   name='import-load-stats'),
    path('import/teachers/',  importar_docentes,             name='import-teachers'),
]
