from django.http import JsonResponse
from django.core.files.storage import FileSystemStorage
from django.views.decorators.csrf import csrf_exempt
# from rest_framework.decorators import api_view # Descomentar si usan REST Framework
# from rest_framework.response import Response

# ==============================================================================
# VISTAS PARA LA IMPORTACIÓN DE DATOS ACADÉMICOS
# Este archivo contiene la estructura base para las tareas de importación.
# Cada función debe ser desarrollada por el integrante asignado.
# ==============================================================================

def importar_estudiantes_dirplan(request):
    """
    HU-01: IMPORTAR REPORTE GENERAL DE ESTUDIANTES DESDE DIRPLAN
    
    Responsable: [Nombre del Integrante]
    Objetivo: Consolidar la información básica de los estudiantes en el sistema.
    
    Campos a importar:
    - Código del estudiante
    - Nombre completo
    - Año/Semestre de ingreso
    - Promedio acumulado
    - Semestre matriculado actualmente
    
    Modelo principal: Estudiante
    Formato sugerido: Excel (.xlsx) o CSV
    """
    # TODO: Implementar lógica de lectura de archivo
    # TODO: Validar datos y manejar duplicados (get_or_create)
    # TODO: Retornar resumen de la importación (ej. creados: 10, actualizados: 5)
    return JsonResponse({"status": "template", "message": "HU-01 pendiente de implementación"})


def importar_historial_academico(request):
    """
    HU-02: IMPORTAR REPORTES INDIVIDUALES DE CADA ESTUDIANTE
    
    Responsable: [Nombre del Integrante]
    Objetivo: Construir el historial académico detallado (materias y notas).
    
    Acciones requeridas:
    - Identificar al estudiante por su código.
    - Procesar el listado de materias aprobadas.
    - Registrar la nota y el periodo para cada materia.
    
    Modelos involucrados: Estudiante, Matricula, Curso, PeriodoAcademico.
    """
    # TODO: Implementar lógica de vinculación de notas con estudiantes existentes
    # TODO: Validar que el periodo académico exista o crearlo
    return JsonResponse({"status": "template", "message": "HU-02 pendiente de implementación"})


def importar_oferta_academica(request):
    """
    HU-03: IMPORTAR LISTADO GENERAL DE CURSOS Y DOCENTES
    
    Responsable: [Nombre del Integrante]
    Objetivo: Mantener la oferta académica y la asignación docente actualizada.
    
    Campos a importar:
    - Nombre del curso y código
    - Nombre del docente y código
    - Departamento adscrito
    
    Modelos involucrados: Curso, Docente, Departamento.
    """
    # TODO: Implementar creación/actualización de docentes
    # TODO: Vincular cursos con sus respectivos docentes
    return JsonResponse({"status": "template", "message": "HU-03 pendiente de implementación"})


def importar_estadisticas_carga(request):
    """
    HU-04: IMPORTAR REPORTES DE CANTIDAD DE ESTUDIANTES POR CURSO Y SEMESTRE
    
    Responsable: [Nombre del Integrante]
    Objetivo: Conocer la carga académica detallada de cada periodo.
    
    Información clave:
    - Número de estudiantes matriculados por curso.
    - Distribución por semestre.
    
    Modelos involucrados: Curso, Matricula (conteo).
    """
    # TODO: Implementar actualización masiva de 'num_matriculados' en el modelo Curso
    # TODO: Generar logs de discrepancias si el conteo no coincide con las matrículas registradas
    return JsonResponse({"status": "template", "message": "HU-04 pendiente de implementación"})
