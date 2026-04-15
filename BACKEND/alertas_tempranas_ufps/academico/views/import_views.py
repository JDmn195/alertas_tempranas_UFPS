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

from academico.models import Estudiante, Curso, Docente

@csrf_exempt
def importar_estudiantes_dirplan(request):
    """
    HU-01: IMPORTAR REPORTE GENERAL DE ESTUDIANTES DESDE DIRPLAN
    
    Objetivo: Consolidar la información básica de los estudiantes en el sistema.
    """
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        try:
            # Leer archivo según extensión
            if file.name.endswith('.xlsx'):
                df = pd.read_excel(file)
            elif file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                return JsonResponse({"error": "Formato no soportado. Use .xlsx o .csv"}, status=400)

            # Normalizar nombres de columnas a minúsculas y sin espacios
            df.columns = df.columns.str.strip().str.lower()
            
            # Mapa de posibles nombres de columnas
            col_map = {
                'codigo': ['codigo', 'código', 'cod', 'id'],
                'nombre': ['nombre', 'nombre completo', 'estudiante', 'nombre_estudiante'],
                'anio_ingreso': ['año ingreso', 'anio ingreso', 'año_ingreso', 'anio'],
                'semestre_ingreso': ['semestre ingreso', 'sem_ingreso', 'semestre_ingreso'],
                'promedio': ['promedio', 'promedio acumulado', 'promedio_acumulado', 'prom'],
                'semestre_actual': ['semestre actual', 'semestre matriculado', 'semestre_actual', 'semestre']
            }

            def find_col(possible_names):
                for name in possible_names:
                    if name in df.columns:
                        return name
                return None

            c_codigo = find_col(col_map['codigo'])
            c_nombre = find_col(col_map['nombre'])
            c_anio = find_col(col_map['anio_ingreso'])
            c_sem_ing = find_col(col_map['semestre_ingreso'])
            c_prom = find_col(col_map['promedio'])
            c_sem_act = find_col(col_map['semestre_actual'])

            if not c_codigo:
                return JsonResponse({"error": "No se encontró la columna de Código en el archivo"}, status=400)

            creados = 0
            actualizados = 0

            for _, row in df.iterrows():
                codigo_val = str(row[c_codigo]).strip()
                if not codigo_val or pd.isna(codigo_val) or codigo_val.lower() == 'nan':
                    continue

                defaults = {}
                if c_nombre: defaults['nombre'] = str(row[c_nombre]).strip()
                if c_anio: defaults['anio_ingreso'] = int(row[c_anio]) if not pd.isna(row[c_anio]) else None
                if c_sem_ing: defaults['semestre_ingreso'] = int(row[c_sem_ing]) if not pd.isna(row[c_sem_ing]) else None
                if c_prom: defaults['promedio_acumulado'] = float(row[c_prom]) if not pd.isna(row[c_prom]) else None
                if c_sem_act: defaults['semestre_actual'] = int(row[c_sem_act]) if not pd.isna(row[c_sem_act]) else None

                _, created = Estudiante.objects.update_or_create(
                    codigo=codigo_val,
                    defaults=defaults
                )
                if created:
                    creados += 1
                else:
                    actualizados += 1

            return JsonResponse({
                "status": "success",
                "message": "Importación finalizada",
                "detalles": {
                    "creados": creados,
                    "actualizados": actualizados,
                    "total_procesados": creados + actualizados
                }
            })
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse({"status": "error", "message": "Método no permitido o archivo faltante"}, status=400)


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

