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
from usuarios.models import Usuario

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
                # Intentar detectar el separador (común en Excel de regiones hispanas)
                try:
                    # Leer solo la primera línea para detectar el separador
                    first_line = file.readline().decode('utf-8')
                    file.seek(0) # Volver al inicio
                    sep = ';' if ';' in first_line else ','
                    df = pd.read_csv(file, sep=sep)
                except:
                    file.seek(0)
                    df = pd.read_csv(file)
            else:
                return JsonResponse({"error": "Formato no soportado. Use .xlsx o .csv"}, status=400)

            import unicodedata

            # Normalizar nombres de columnas: minúsculas, sin espacios y SIN TILDES
            def normalize_str(s):
                if not isinstance(s, str): return s
                s = s.strip().lower()
                # Eliminar tildes
                s = ''.join(c for c in unicodedata.normalize('NFD', s)
                           if unicodedata.category(c) != 'Mn')
                return s

            df.columns = [normalize_str(col) for col in df.columns]
            
            # Mapa de posibles nombres de columnas (Sinónimos - ya normalizados sin tildes)
            col_map = {
                'codigo': ['codigo', 'id', 'cod', 'codigo alumno'],
                'nombre': ['nombre', 'nombre completo', 'estudiante', 'nombre alumno'],
                'tipo_doc': ['tipo doc', 'tipo documento', 'tipo_doc'],
                'documento': ['documento', 'cedula', 'identificacion', 'documento_identidad'],
                'anio_ingreso': ['ingreso', 'año ingreso', 'anio ingreso', 'periodo ingreso'],
                'promedio': ['promedio', 'promedio acumulado', 'promedio_acumulado', 'prom'],
                'semestre_actual': ['semestre', 'semestre actual', 'semestre matriculado'],
                'pensum': ['pensum', 'pensum_estudiante'],
                'estado_matricula': ['estado matricula', 'estado', 'estado_matricula'],
                'celular': ['celular', 'telefono', 'teléfono', 'cel'],
                'email': ['email', 'correo', 'e-mail'],
                'email_institucional': ['email institucional', 'correo institucional', 'email_institucional'],
                'colegio': ['colegio egresado', 'colegio', 'institucion_procedencia'],
                'municipio': ['municipio nacimiento', 'municipio', 'lugar_nacimiento']
            }

            def find_col(possible_names):
                for name in possible_names:
                    # Normalizar también los nombres buscados por si acaso
                    norm_name = normalize_str(name)
                    if norm_name in df.columns:
                        return norm_name
                return None

            c_codigo = find_col(col_map['codigo'])
            c_nombre = find_col(col_map['nombre'])
            c_tipo_doc = find_col(col_map['tipo_doc'])
            c_doc = find_col(col_map['documento'])
            c_ingreso = find_col(col_map['anio_ingreso'])
            c_prom = find_col(col_map['promedio'])
            c_sem_act = find_col(col_map['semestre_actual'])
            c_pensum = find_col(col_map['pensum'])
            c_estado_mat = find_col(col_map['estado_matricula'])
            c_cel = find_col(col_map['celular'])
            c_email = find_col(col_map['email'])
            c_email_inst = find_col(col_map['email_institucional'])
            c_colegio = find_col(col_map['colegio'])
            c_municipio = find_col(col_map['municipio'])

            print(f"COLUMNAS DETECTADAS: codigo={c_codigo}, nombre={c_nombre}")

            # VALIDACIÓN: Si no tiene las dos columnas base, el archivo es incorrecto
            if not c_codigo or not c_nombre:
                detected_cols = list(df.columns)
                print(f"ERROR: Archivo inválido. Columnas detectadas: {detected_cols}")
                return JsonResponse({
                    "status": "error",
                    "error": f"El archivo no parece ser un reporte de DIRPLAN válido. Debe contener al menos las columnas 'Codigo' y 'Nombre Alumno'. Detectamos estas columnas: {', '.join(detected_cols)}"
                }, status=400)

            def safe_int(val):
                if pd.isna(val): return None
                try:
                    # Eliminar cualquier cosa que no sea número
                    s = str(val).strip()
                    if not s: return None
                    # Si tiene un guion (como 2024-1), solo tomar la primera parte si se espera un solo entero
                    if '-' in s: s = s.split('-')[0]
                    return int(float(s))
                except:
                    return None

            creados = 0
            actualizados = 0
            omitidos = 0

            print(f"PROCESANDO {len(df)} FILAS...")

            for i, row in df.iterrows():
                codigo_val = str(row[c_codigo]).strip()
                if not codigo_val or pd.isna(codigo_val) or codigo_val.lower() == 'nan':
                    omitidos += 1
                    continue

                defaults = {}
                nombre_val = str(row[c_nombre]).strip() if c_nombre else "SIN NOMBRE"
                if c_nombre: defaults['nombre'] = nombre_val
                if c_tipo_doc: defaults['tipo_documento'] = str(row[c_tipo_doc]).strip()
                if c_doc: defaults['documento'] = str(row[c_doc]).strip()
                if c_pensum: defaults['pensum'] = safe_int(row[c_pensum])
                if c_estado_mat: defaults['estado_matricula'] = str(row[c_estado_mat]).strip()
                if c_cel: defaults['celular'] = str(row[c_cel]).strip()
                
                email_inst = str(row[c_email_inst]).strip() if c_email_inst and not pd.isna(row[c_email_inst]) else None
                email_pers = str(row[c_email]).strip() if c_email and not pd.isna(row[c_email]) else None
                
                if c_email: defaults['email'] = email_pers
                if c_email_inst: defaults['email_institucional'] = email_inst
                if c_colegio: defaults['colegio_egresado'] = str(row[c_colegio]).strip()
                if c_municipio: defaults['municipio_nacimiento'] = str(row[c_municipio]).strip()
                
                # ─────────────────────────────────────────────────────────────
                # GESTIÓN DE USUARIO (Crear cuenta automáticamente)
                # ─────────────────────────────────────────────────────────────
                correo_u = email_inst or email_pers or f"{codigo_val}@ufps.edu.co"
                usuario_obj, _ = Usuario.objects.get_or_create(
                    correo=correo_u,
                    defaults={
                        'nombre': nombre_val,
                        'rol': 'ESTUDIANTE',
                        'contrasena': codigo_val, # Password por defecto es su código
                        'activo': True
                    }
                )
                defaults['usuario'] = usuario_obj
                # ─────────────────────────────────────────────────────────────

                try:
                    if c_prom: defaults['promedio_acumulado'] = float(row[c_prom]) if not pd.isna(row[c_prom]) else None
                except: pass
                
                if c_sem_act: defaults['semestre_actual'] = safe_int(row[c_sem_act])

                # Lógica especial para 'Ingreso' (ej: 2026-1)
                if c_ingreso:
                    ingreso_val = str(row[c_ingreso]).strip()
                    if '-' in ingreso_val:
                        try:
                            partes = ingreso_val.split('-')
                            defaults['anio_ingreso'] = safe_int(partes[0])
                            defaults['semestre_ingreso'] = safe_int(partes[1])
                        except:
                            pass
                    else:
                        defaults['anio_ingreso'] = safe_int(ingreso_val)

                try:
                    _, created = Estudiante.objects.update_or_create(
                        codigo=codigo_val,
                        defaults=defaults
                    )
                    if created:
                        creados += 1
                    else:
                        actualizados += 1
                except Exception as row_error:
                    print(f"Error en fila {i} (Código {codigo_val}): {str(row_error)}")

            print(f"FIN IMPORTACIÓN: Creados={creados}, Actualizados={actualizados}, Omitidos={omitidos}")

            return JsonResponse({
                "status": "success",
                "message": "Importación finalizada correctamente",
                "detalles": {
                    "creados": creados,
                    "actualizados": actualizados,
                    "omitidos": omitidos,
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

