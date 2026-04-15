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


import pandas as pd
import os

from django.conf import settings

from academico.models import Curso, Docente

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


@csrf_exempt
def importar_estadisticas_carga(request):

    if request.method == 'POST' and request.FILES.get('file'):

        excel_file = request.FILES['file']

        try:

            # Leer Excel en memoria
            df = pd.read_excel(excel_file)

            # Limpiar nombres columnas
            df.columns = df.columns.str.strip()

            creados = 0
            actualizados = 0
            docentes_creados = 0

            for index, row in df.iterrows():

                codigo = row.get("Materia")
                nombre = row.get("Nombre")
                horario = row.get("Horario")
                matriculados = row.get("# Matriculados")
                codigo_docente = row.get("Código Docente")
                nombre_docente = row.get("Nombre Docente")

                # Ignorar filas vacías
                if pd.isna(codigo):
                    continue

                codigo = str(codigo).strip()

                # ─────────────────────────────
                # CREAR O BUSCAR DOCENTE
                # ─────────────────────────────

                docente_obj = None

                if not pd.isna(codigo_docente):

                    docente_codigo = str(
                        codigo_docente
                    ).strip()

                    docente_nombre = (
                        str(nombre_docente).strip()
                        if not pd.isna(nombre_docente)
                        else "SIN NOMBRE"
                    )

                    docente_obj, docente_created = (
                        Docente.objects.get_or_create(

                            codigo=docente_codigo,

                            defaults={

                                "nombre": docente_nombre,

                                "tipo_vinculacion":
                                    "DOCENTE CATEDRA"

                            }
                        )
                    )

                    if docente_created:
                        docentes_creados += 1

                # ─────────────────────────────
                # CREAR O ACTUALIZAR CURSO
                # ─────────────────────────────

                curso_obj, created = (
                    Curso.objects.update_or_create(

                        codigo=codigo,

                        defaults={

                            "nombre":
                                str(nombre).strip()
                                if not pd.isna(nombre)
                                else "SIN NOMBRE",

                            "horario":
                                str(horario).strip()
                                if not pd.isna(horario)
                                else None,

                            "num_matriculados":
                                int(matriculados)
                                if not pd.isna(matriculados)
                                else 0,

                            "docente":
                                docente_obj

                        }
                    )
                )

                if created:
                    creados += 1
                else:
                    actualizados += 1

            return JsonResponse({

                "message":
                    "HU-04 procesada correctamente",

                "cursos_creados":
                    creados,

                "cursos_actualizados":
                    actualizados,

                "docentes_creados":
                    docentes_creados

            })

        except Exception as e:

            import traceback

            print("ERROR IMPORTACIÓN:")
            traceback.print_exc()

            return JsonResponse({

                "error": str(e)

    }, status=500)

    return JsonResponse({

        "error": "No se envió archivo"

    }, status=400)

