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

from academico.models import Curso, Docente, Estudiante, Nota, Periodo

@csrf_exempt
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


@csrf_exempt
def importar_historial_academico(request):
    """
    HU-02: IMPORTAR REPORTES INDIVIDUALES DE CADA ESTUDIANTE

    Objetivo: Construir el historial académico detallado (materias y notas).

    Flujo:
    1. Recibe un archivo Excel/CSV con columnas:
    (Periodo, Materia Base, Codigo Materia, Nombre Materia, Tipo Nota, Definitiva, Creditos)
    2. Extrae el código del estudiante del nombre del archivo (ej: "Relacion de Notas 1152430").
    3. Valida que el estudiante, cada curso y cada periodo existan en la BD.
    4. Si todo es válido, crea los registros de Matrícula de forma atómica.
    5. Si algo falla, no guarda nada y retorna el detalle de errores.

    Modelos involucrados: Estudiante, Nota, Curso, Periodo.
    """
    import re
    import traceback
    from django.db import transaction

    # ─────────────────────────────────────────────
    # 1. VALIDAR MÉTODO Y PRESENCIA DE ARCHIVO
    # ─────────────────────────────────────────────
    if request.method != 'POST':
        return JsonResponse(
            {"error": "Método no permitido. Se espera POST."},
            status=405
        )

    archivo = request.FILES.get('file')
    if not archivo:
        return JsonResponse(
            {"error": "No se envió ningún archivo."},
            status=400
        )

    # Validar extensión del archivo
    nombre_archivo = archivo.name
    extension = os.path.splitext(nombre_archivo)[1].lower()
    if extension not in ['.xlsx', '.xls', '.csv']:
        return JsonResponse(
            {"error": f"Formato de archivo no soportado: '{extension}'. "
                    f"Se aceptan: .xlsx, .xls, .csv"},
            status=400
        )

    # ─────────────────────────────────────────────
    # 2. EXTRAER CÓDIGO DEL ESTUDIANTE DEL NOMBRE
    # ─────────────────────────────────────────────
    match = re.search(r'(\d{5,10})', nombre_archivo)
    if not match:
        return JsonResponse(
            {"error": f"No se pudo extraer el código del estudiante del nombre "
                    f"del archivo: '{nombre_archivo}'. "
                    f"El nombre debe contener el código numérico "
                    f"(ej: 'Relacion de Notas 1152430.xlsx')."},
            status=400
        )

    codigo_estudiante = match.group(1)

    # ─────────────────────────────────────────────
    # 3. VALIDAR QUE EL ESTUDIANTE EXISTA
    # ─────────────────────────────────────────────
    try:
        estudiante = Estudiante.objects.get(codigo=codigo_estudiante)
    except Estudiante.DoesNotExist:
        return JsonResponse(
            {"error": f"El estudiante con código '{codigo_estudiante}' no existe "
                    f"en el sistema. Debe ser creado antes de importar su "
                    f"historial académico.",
            "codigo_estudiante": codigo_estudiante,
            "tipo_error": "ESTUDIANTE_NO_ENCONTRADO"},
            status=404
        )

    # ─────────────────────────────────────────────
    # 4. LEER EL ARCHIVO CON PANDAS
    # ─────────────────────────────────────────────
    try:
        if extension == '.csv':
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo)
    except Exception as e:
        return JsonResponse(
            {"error": f"Error al leer el archivo: {str(e)}"},
            status=400
        )

    # Limpiar nombres de columnas
    df.columns = df.columns.str.strip()

    # Validar que el archivo tenga las columnas esperadas
    columnas_requeridas = [
        'Periodo', 'Materia Base', 'Codigo Materia',
        'Nombre Materia', 'Tipo Nota', 'Definitiva', 'Creditos'
    ]
    columnas_faltantes = [
        col for col in columnas_requeridas if col not in df.columns
    ]
    if columnas_faltantes:
        return JsonResponse(
            {"error": f"El archivo no contiene las columnas requeridas. "
                    f"Faltan: {', '.join(columnas_faltantes)}",
            "columnas_encontradas": list(df.columns),
            "columnas_requeridas": columnas_requeridas},
            status=400
        )

    # ─────────────────────────────────────────────
    # 5. VALIDACIÓN ESTRICTA DE EXISTENCIA
    #    (Periodos y Cursos deben existir previamente)
    # ─────────────────────────────────────────────
    errores = []
    filas_validas = []

    for index, row in df.iterrows():
        fila_num = index + 2  # +2 porque fila 1 es el encabezado

        # --- Parsear Periodo (ej: "2024-1" -> anio=2024, semestre=1) ---
        periodo_raw = str(row.get('Periodo', '')).strip()
        periodo_match = re.match(r'^(\d{4})\s*[-/]\s*([12])$', periodo_raw)

        if not periodo_match:
            errores.append({
                "fila": fila_num,
                "campo": "Periodo",
                "valor": periodo_raw,
                "mensaje": f"Formato de periodo inválido: '{periodo_raw}'. "
                        f"Se espera formato 'AAAA-S' (ej: 2024-1)."
            })
            continue

        anio = int(periodo_match.group(1))
        semestre = int(periodo_match.group(2))

        try:
            periodo_obj = Periodo.objects.get(
                anio=anio, semestre=semestre
            )
        except Periodo.DoesNotExist:
            errores.append({
                "fila": fila_num,
                "campo": "Periodo",
                "valor": periodo_raw,
                "mensaje": f"El periodo académico '{periodo_raw}' no existe "
                        f"en el sistema. Debe ser creado manualmente."
            })
            continue

        # --- Validar Curso ---
        codigo_materia = str(row.get('Codigo Materia', '')).strip()
        if pd.isna(row.get('Codigo Materia')) or codigo_materia == '':
            errores.append({
                "fila": fila_num,
                "campo": "Codigo Materia",
                "valor": "",
                "mensaje": "El código de materia está vacío."
            })
            continue

        try:
            curso_obj = Curso.objects.get(codigo=codigo_materia)
        except Curso.DoesNotExist:
            nombre_materia = str(row.get('Nombre Materia', '')).strip()
            errores.append({
                "fila": fila_num,
                "campo": "Codigo Materia",
                "valor": codigo_materia,
                "mensaje": f"El curso '{codigo_materia} - {nombre_materia}' "
                        f"no existe en el sistema. Debe ser creado "
                        f"manualmente."
            })
            continue

        # --- Validar Nota ---
        nota_raw = row.get('Definitiva')
        if pd.isna(nota_raw):
            errores.append({
                "fila": fila_num,
                "campo": "Definitiva",
                "valor": str(nota_raw),
                "mensaje": "La nota definitiva está vacía."
            })
            continue

        try:
            nota = float(nota_raw)
        except (ValueError, TypeError):
            errores.append({
                "fila": fila_num,
                "campo": "Definitiva",
                "valor": str(nota_raw),
                "mensaje": f"La nota '{nota_raw}' no es un número válido."
            })
            continue

        if nota < 0.0 or nota > 5.0:
            errores.append({
                "fila": fila_num,
                "campo": "Definitiva",
                "valor": str(nota),
                "mensaje": f"La nota {nota} está fuera del rango "
                        f"permitido (0.0 - 5.0)."
            })
            continue

        # --- Determinar estado según la nota ---
        estado = 'APROBADO' if nota >= 3.0 else 'REPROBADO'

        # Fila válida: guardar para inserción posterior
        filas_validas.append({
            "estudiante": estudiante,
            "curso": curso_obj,
            "periodo": periodo_obj,
            "nota": nota,
            "estado": estado,
        })

    # ─────────────────────────────────────────────
    # 6. SI HAY ERRORES, ABORTAR SIN GUARDAR NADA
    # ─────────────────────────────────────────────
    if errores:
        return JsonResponse({
            "status": "error",
            "mensaje": f"Se encontraron {len(errores)} error(es) en el archivo. "
                    f"No se guardó ningún registro. Corrija los problemas "
                    f"e intente de nuevo.",
            "codigo_estudiante": codigo_estudiante,
            "total_filas": len(df),
            "filas_con_error": len(errores),
            "errores": errores
        }, status=400)

    # ─────────────────────────────────────────────
    # 7. GUARDAR DE FORMA ATÓMICA
    # ─────────────────────────────────────────────
    try:
        creados = 0
        actualizados = 0

        with transaction.atomic():
            for fila in filas_validas:
                _obj, created = Nota.objects.update_or_create(
                    estudiante=fila["estudiante"],
                    curso=fila["curso"],
                    periodo=fila["periodo"],
                    defaults={
                        "definitiva": fila["nota"],
                    }
                )
                if created:
                    creados += 1
                else:
                    actualizados += 1

        return JsonResponse({
            "status": "success",
            "mensaje": f"Historial académico del estudiante "
                    f"'{codigo_estudiante}' importado correctamente.",
            "codigo_estudiante": codigo_estudiante,
            "total_filas_procesadas": len(filas_validas),
            "matriculas_creadas": creados,
            "matriculas_actualizadas": actualizados,
        })

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({
            "status": "error",
            "mensaje": f"Error inesperado al guardar los datos: {str(e)}",
            "codigo_estudiante": codigo_estudiante,
        }, status=500)


@csrf_exempt
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


@csrf_exempt
def importar_docentes(request):
    """
    
    """
    from django.db import transaction
    from usuarios.models import Usuario

    # ─────────────────────────────────────────────
    # 1. VALIDAR MÉTODO Y ARCHIVO
    # ─────────────────────────────────────────────
    if request.method != 'POST':
        return JsonResponse(
            {"error": "Método no permitido. Se espera POST."},
            status=405
        )

    archivo = request.FILES.get('file')
    if not archivo:
        return JsonResponse(
            {"error": "No se envió ningún archivo."},
            status=400
        )

    extension = os.path.splitext(archivo.name)[1].lower()
    if extension not in ['.xlsx', '.xls']:
        return JsonResponse(
            {"error": f"Formato no soportado: '{extension}'. Se aceptan .xlsx, .xls"},
            status=400
        )

    # ─────────────────────────────────────────────
    # 2. LEER ARCHIVO Y DETECTAR COLUMNAS
    # ─────────────────────────────────────────────
    try:
        df = pd.read_excel(archivo)
        df.columns = df.columns.str.strip()
    except Exception as e:
        return JsonResponse(
            {"error": f"Error al leer el archivo: {str(e)}"},
            status=400
        )

    # Detectar columnas dinámicamente para tolerar caracteres especiales
    col_codigo      = next((c for c in df.columns if 'Codigo' in c and 'Docente' in c), None)
    col_nombre      = next((c for c in df.columns if 'Nombre' in c and 'Docente' in c), None)
    col_vinculacion = next((c for c in df.columns if 'Vinculaci' in c), None)
    col_depto       = next((c for c in df.columns if 'Departamento' in c), None)
    col_correo_p    = next((c for c in df.columns if 'Personal' in c), None)
    col_correo_i    = next((c for c in df.columns if 'Institucional' in c), None)
    col_celular     = next((c for c in df.columns if 'Celular' in c), None)

    if not col_codigo or not col_nombre:
        return JsonResponse(
            {"error": "No se encontraron las columnas requeridas en el archivo.",
            "columnas_encontradas": list(df.columns)},
            status=400
        )

    # ─────────────────────────────────────────────
    # 3. PROCESAR CADA FILA
    # ─────────────────────────────────────────────
    creados          = 0
    actualizados     = 0
    usuarios_creados = 0
    errores          = []

    for index, row in df.iterrows():
        fila_num = index + 2

        # ── Leer y limpiar código ──────────────────────────────────
        codigo_raw = row.get(col_codigo)
        if pd.isna(codigo_raw):
            continue
        codigo = str(codigo_raw).strip().lstrip("'")

        # ── Leer demás campos ──────────────────────────────────────
        nombre               = str(row.get(col_nombre, '')).strip()
        tipo_vinculacion     = str(row.get(col_vinculacion, 'DOCENTE CATEDRA')).strip() if col_vinculacion else 'DOCENTE CATEDRA'
        departamento_nombre  = str(row.get(col_depto, '')).strip() if col_depto else ''
        correo_personal      = row.get(col_correo_p)  if col_correo_p  else None
        correo_institucional = row.get(col_correo_i)  if col_correo_i  else None
        celular              = row.get(col_celular)   if col_celular   else None 
        # Normalizar tipo de vinculación
        if tipo_vinculacion not in ['DOCENTE PLANTA', 'DOCENTE CATEDRA']:
            tipo_vinculacion = 'DOCENTE CATEDRA'

        # Limpiar valores nulos
        correo_personal      = str(correo_personal).strip()      if correo_personal      is not None and not pd.isna(correo_personal)      else None
        correo_institucional = str(correo_institucional).strip() if correo_institucional is not None and not pd.isna(correo_institucional) else None
        celular              = str(celular).strip()              if celular              is not None and not pd.isna(celular)              else None
        departamento_nombre  = departamento_nombre if departamento_nombre and departamento_nombre != 'nan' else None

        try:
            with transaction.atomic():

                # ── 1. Crear o buscar Usuario ──────────────────────
                # El correo institucional es el identificador principal.
                # Si no existe, se usa el personal o se genera uno por defecto.
                correo_usuario = correo_institucional or correo_personal or f"{codigo}@ufps.edu.co"

                usuario_obj, usuario_creado = Usuario.objects.get_or_create(
                    correo=correo_usuario,
                    defaults={
                        "nombre":     nombre,
                        "rol":        "DOCENTE",
                        "contrasena": codigo,   # contraseña inicial = código del docente
                        "activo":     True,
                    }
                )
                if usuario_creado:
                    usuarios_creados += 1

                # ── 2. Crear o actualizar Docente ──────────────────
                _obj, creado = Docente.objects.update_or_create(
                    codigo=codigo,
                    defaults={
                        "nombre":               nombre,
                        "tipo_vinculacion":     tipo_vinculacion,
                        "departamento":         departamento_nombre,
                        "correo_personal":      correo_personal,
                        "correo_institucional": correo_institucional,
                        "celular":              celular,
                        "usuario":              usuario_obj,
                    }
                )
                if creado:
                    creados += 1
                else:
                    actualizados += 1

        except Exception as e:
            errores.append({"fila": fila_num, "codigo": codigo, "error": str(e)})

    # agrega aquí ↓
    print("CREADOS:", creados)
    print("ACTUALIZADOS:", actualizados)
    print("USUARIOS CREADOS:", usuarios_creados)
    print("ERRORES:", errores)
    # ─────────────────────────────────────────────
    # 4. RETORNAR RESUMEN
    # ─────────────────────────────────────────────
    return JsonResponse({
        "status":                "success" if not errores else "parcial",
        "mensaje":               "Importación de docentes completada.",
        "usuarios_creados":      usuarios_creados,
        "docentes_creados":      creados,
        "docentes_actualizados": actualizados,
        "errores":               errores,
    })