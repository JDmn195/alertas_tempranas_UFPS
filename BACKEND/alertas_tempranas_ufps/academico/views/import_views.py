from django.http import JsonResponse
from django.core.files.storage import FileSystemStorage
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction, reset_queries
import pandas as pd
import os
import re
import unicodedata
from datetime import date
from django.conf import settings
from academico.models import Curso, Docente, Estudiante, Nota, Periodo, Materia
from usuarios.models import Usuario

# ==============================================================================
# VISTAS PARA LA IMPORTACIÓN DE DATOS ACADÉMICOS
# ==============================================================================

@csrf_exempt
def importar_estudiantes_dirplan(request):
    """
    HU-01: IMPORTAR REPORTE GENERAL DE ESTUDIANTES DESDE DIRPLAN
    
    Objetivo: Consolidar la información básica de los estudiantes en el sistema.
    Adaptado al nuevo esquema de base de datos (PRIMARY KEY codigo, Sin Usuario).
    """
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        try:
            # Leer archivo según extensión
            if file.name.endswith('.xlsx'):
                df = pd.read_excel(file)
            elif file.name.endswith('.csv'):
                try:
                    first_line = file.readline().decode('utf-8')
                    file.seek(0)
                    sep = ';' if ';' in first_line else ','
                    df = pd.read_csv(file, sep=sep)
                except:
                    file.seek(0)
                    df = pd.read_csv(file)
            else:
                return JsonResponse({"error": "Formato no soportado. Use .xlsx o .csv"}, status=400)

            # Normalizar nombres de columnas: minúsculas, sin espacios y SIN TILDES
            def normalize_str(s):
                if not isinstance(s, str): return s
                s = s.strip().lower()
                s = ''.join(c for c in unicodedata.normalize('NFD', s)
                           if unicodedata.category(c) != 'Mn')
                return s

            df.columns = [normalize_str(col) for col in df.columns]
            
            # Mapa de posibles nombres de columnas
            col_map = {
                'codigo': ['codigo', 'id', 'cod', 'codigo alumno'],
                'nombre': ['nombre', 'nombre completo', 'estudiante', 'nombre alumno'],
                'tipo_doc': ['tipo doc', 'tipo documento', 'tipo_doc'],
                'documento': ['documento', 'cedula', 'identificacion', 'documento_identidad', 'numero_documento'],
                'ingreso': ['ingreso', 'año ingreso', 'anio ingreso', 'periodo ingreso'],
                'promedio': ['promedio', 'promedio acumulado', 'promedio_acumulado', 'prom'],
                'semestre': ['semestre', 'semestre actual', 'semestre matriculado'],
                'pensum': ['pensum', 'pensum_estudiante'],
                'estado_matricula': ['estado matricula', 'estado', 'estado_matricula'],
                'celular': ['celular', 'telefono', 'teléfono', 'cel'],
                'email_personal': ['email', 'correo', 'e-mail', 'email personal'],
                'email_institucional': ['email institucional', 'correo institucional', 'email_institucional'],
                'colegio': ['colegio egresado', 'colegio', 'institucion_procedencia'],
                'municipio': ['municipio nacimiento', 'municipio', 'lugar_nacimiento']
            }

            def find_col(possible_names):
                for name in possible_names:
                    norm_name = normalize_str(name)
                    if norm_name in df.columns:
                        return norm_name
                return None

            c_codigo = find_col(col_map['codigo'])
            c_nombre = find_col(col_map['nombre'])
            c_tipo_doc = find_col(col_map['tipo_doc'])
            c_doc = find_col(col_map['documento'])
            c_ingreso = find_col(col_map['ingreso'])
            c_prom = find_col(col_map['promedio'])
            c_sem = find_col(col_map['semestre'])
            c_pensum = find_col(col_map['pensum'])
            c_estado_mat = find_col(col_map['estado_matricula'])
            c_cel = find_col(col_map['celular'])
            c_email_p = find_col(col_map['email_personal'])
            c_email_i = find_col(col_map['email_institucional'])
            c_colegio = find_col(col_map['colegio'])
            c_municipio = find_col(col_map['municipio'])

            if not c_codigo or not c_nombre:
                detected_cols = list(df.columns)
                return JsonResponse({
                    "status": "error",
                    "error": f"Columnas requeridas 'Codigo' y 'Nombre' no encontradas. Detectadas: {', '.join(detected_cols)}"
                }, status=400)

            def safe_int(val):
                if pd.isna(val): return None
                try:
                    s = str(val).strip()
                    if not s: return None
                    if '-' in s: s = s.split('-')[0]
                    return int(float(s))
                except:
                    return None

            creados = 0
            actualizados = 0
            omitidos = 0

            with transaction.atomic():
                for i, row in df.iterrows():
                    if i % 100 == 0: reset_queries()

                    codigo_val = str(row[c_codigo]).strip()
                    if not codigo_val or pd.isna(codigo_val) or codigo_val.lower() == 'nan':
                        omitidos += 1
                        continue

                    defaults = {}
                    if c_nombre: defaults['nombre'] = str(row[c_nombre]).strip()
                    if c_tipo_doc: defaults['tipo_documento'] = str(row[c_tipo_doc]).strip()
                    if c_doc: defaults['numero_documento'] = str(row[c_doc]).strip()
                    if c_pensum: defaults['pensum'] = str(row[c_pensum]).strip()
                    if c_estado_mat: defaults['estado_matricula'] = str(row[c_estado_mat]).strip()
                    if c_cel: defaults['celular'] = str(row[c_cel]).strip()
                    if c_email_p: defaults['email_personal'] = str(row[c_email_p]).strip()
                    if c_email_i: defaults['email_institucional'] = str(row[c_email_i]).strip()
                    if c_colegio: defaults['colegio_egresado'] = str(row[c_colegio]).strip()
                    if c_municipio: defaults['municipio_nacimiento'] = str(row[c_municipio]).strip()
                    if c_sem: defaults['semestre'] = safe_int(row[c_sem]) or 1

                    # Lógica de Promedio (DecimalField)
                    if c_prom:
                        try:
                            val_prom = str(row[c_prom]).replace(',', '.')
                            defaults['promedio'] = float(val_prom) if not pd.isna(row[c_prom]) else None
                        except:
                            defaults['promedio'] = None

                    # Lógica de Ingreso (DateField)
                    if c_ingreso:
                        ingreso_val = str(row[c_ingreso]).strip()
                        if '-' in ingreso_val:
                            try:
                                partes = ingreso_val.split('-')
                                anio = safe_int(partes[0])
                                sem = safe_int(partes[1])
                                if anio and sem:
                                    mes = 2 if sem == 1 else 8
                                    defaults['ingreso'] = date(anio, mes, 1)
                            except: pass

                    try:
                        _, created = Estudiante.objects.update_or_create(
                            codigo=codigo_val,
                            defaults=defaults
                        )
                        if created: creados += 1
                        else: actualizados += 1
                    except Exception as row_error:
                        print(f"Error en fila {i} (Código {codigo_val}): {str(row_error)}")

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


@csrf_exempt
def importar_historial_academico(request):
    """
    HU-02: IMPORTAR REPORTES INDIVIDUALES DE CADA ESTUDIANTE
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Método no permitido"}, status=405)

    archivo = request.FILES.get('file')
    if not archivo:
        return JsonResponse({"error": "No se envió ningún archivo"}, status=400)

    nombre_archivo = archivo.name
    match = re.search(r'(\d{5,10})', nombre_archivo)
    if not match:
        return JsonResponse({"error": "Código de estudiante no encontrado en el nombre del archivo"}, status=400)

    codigo_estudiante = match.group(1)
    try:
        estudiante = Estudiante.objects.get(codigo=codigo_estudiante)
    except Estudiante.DoesNotExist:
        return JsonResponse({"error": f"Estudiante {codigo_estudiante} no existe"}, status=404)

    try:
        extension = os.path.splitext(nombre_archivo)[1].lower()
        df = pd.read_excel(archivo) if extension != '.csv' else pd.read_csv(archivo)
        df.columns = df.columns.str.strip()

        creados = 0
        with transaction.atomic():
            for index, row in df.iterrows():
                # Lógica simplificada para ejemplo
                periodo_raw = str(row.get('Periodo', '')).strip()
                match_p = re.match(r'^(\d{4})\s*[-/]\s*([12])$', periodo_raw)
                if match_p:
                    periodo_obj, _ = Periodo.objects.get_or_create(
                        anio=int(match_p.group(1)),
                        semestre=int(match_p.group(2))
                    )
                    base_materia = str(row.get('Codigo Materia', '')).strip()[:7]
                    curso = Curso.objects.filter(materia__codigo=base_materia).first()
                    if curso:
                        Nota.objects.update_or_create(
                            estudiante=estudiante,
                            curso=curso,
                            periodo=periodo_obj,
                            defaults={"definitiva": float(row.get('Definitiva', 0))}
                        )
                        creados += 1

        return JsonResponse({"status": "success", "creados": creados})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
def importar_estadisticas_carga(request):
    if request.method == 'POST' and request.FILES.get('file'):
        excel_file = request.FILES['file']
        try:
            df = pd.read_excel(excel_file)
            df.columns = df.columns.str.strip()
            creados = 0
            with transaction.atomic():
                for index, row in df.iterrows():
                    cod_materia = str(row.get("Materia")).strip()
                    if pd.isna(cod_materia): continue
                    
                    # Asegurar que la materia exista
                    materia_obj, _ = Materia.objects.get_or_create(
                        codigo=cod_materia,
                        defaults={"nombre": str(row.get("Nombre", "SIN NOMBRE")).strip()}
                    )
                    
                    docente_obj = None
                    if not pd.isna(row.get("Código Docente")):
                        docente_obj, _ = Docente.objects.get_or_create(
                            codigo=str(row.get("Código Docente")).strip(),
                            defaults={"nombre": str(row.get("Nombre Docente", "SIN NOMBRE")).strip(), "usuario_id": 1} # Mock usuario
                        )

                    Curso.objects.update_or_create(
                        materia=materia_obj,
                        grupo=str(row.get("Grupo", "A")).strip()[:2],
                        defaults={
                            "docente": docente_obj,
                            "horario": str(row.get("Horario")).strip(),
                            "cantidad_matriculados": int(row.get("# Matriculados", 0))
                        }
                    )
                    creados += 1
            return JsonResponse({"message": "OK", "creados": creados})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "No file"}, status=400)


@csrf_exempt
def importar_docentes(request):
    if request.method != 'POST' or not request.FILES.get('file'):
        return JsonResponse({"error": "Bad request"}, status=400)
    
    try:
        df = pd.read_excel(request.FILES['file'])
        df.columns = df.columns.str.strip()
        creados = 0
        with transaction.atomic():
            for index, row in df.iterrows():
                codigo = str(row.get('Código Docente', row.get('Docente', ''))).strip()
                if not codigo: continue
                
                # Gestión de Usuario corregida para Docente
                correo = row.get('Correo Institucional', f"{codigo}@ufps.edu.co")
                usuario, _ = Usuario.objects.get_or_create(
                    correo=correo,
                    defaults={"nombre": str(row.get('Nombre Docente', '')), "rol": "DOCENTE", "contrasena": codigo}
                )
                
                Docente.objects.update_or_create(
                    codigo=codigo,
                    defaults={
                        "nombre": str(row.get('Nombre Docente', '')),
                        "tipo_vinculacion": "DOCENTE CATEDRA",
                        "usuario": usuario
                    }
                )
                creados += 1
        return JsonResponse({"status": "success", "creados": creados})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
