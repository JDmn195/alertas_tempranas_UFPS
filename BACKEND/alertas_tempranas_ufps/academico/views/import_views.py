from django.http import JsonResponse
from django.core.files.storage import FileSystemStorage
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction, reset_queries
import pandas as pd
import os
import re
import unicodedata
import traceback
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
    
    Optimizado: Utiliza bulk_create con update_conflicts para realizar 
    inserciones/actualizaciones masivas en una sola operación.
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

            # Normalizar nombres de columnas
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

            estudiantes_objs = []
            omitidos = 0

            # Los campos que se actualizarán si ya existe el registro
            update_fields = [
                'nombre', 'tipo_documento', 'numero_documento', 'pensum', 
                'estado_matricula', 'celular', 'email_personal', 'email_institucional',
                'colegio_egresado', 'municipio_nacimiento', 'semestre', 'promedio', 'ingreso'
            ]

            for i, row in df.iterrows():
                codigo_val = str(row[c_codigo]).strip()
                if not codigo_val or pd.isna(codigo_val) or codigo_val.lower() == 'nan':
                    omitidos += 1
                    continue

                est_data = {
                    'codigo': codigo_val,
                    'nombre': str(row[c_nombre]).strip() if c_nombre else '',
                    'tipo_documento': str(row[c_tipo_doc]).strip() if c_tipo_doc else '',
                    'numero_documento': str(row[c_doc]).strip() if c_doc else '',
                    'pensum': str(row[c_pensum]).strip() if c_pensum else '',
                    'estado_matricula': str(row[c_estado_mat]).strip() if c_estado_mat else '',
                    'celular': str(row[c_cel]).strip() if c_cel else '',
                    'email_personal': str(row[c_email_p]).strip() if c_email_p else '',
                    'email_institucional': str(row[c_email_i]).strip() if c_email_i else '',
                    'colegio_egresado': str(row[c_colegio]).strip() if c_colegio else '',
                    'municipio_nacimiento': str(row[c_municipio]).strip() if c_municipio else '',
                    'semestre': safe_int(row[c_sem]) or 1,
                }

                # Lógica de Promedio
                if c_prom:
                    try:
                        val_prom = str(row[c_prom]).replace(',', '.')
                        est_data['promedio'] = float(val_prom) if not pd.isna(row[c_prom]) else None
                    except:
                        est_data['promedio'] = None
                else:
                    est_data['promedio'] = None

                # Lógica de Ingreso
                est_data['ingreso'] = None
                if c_ingreso:
                    ingreso_val = str(row[c_ingreso]).strip()
                    if '-' in ingreso_val:
                        try:
                            partes = ingreso_val.split('-')
                            anio = safe_int(partes[0])
                            sem = safe_int(partes[1])
                            if anio and sem:
                                mes = 2 if sem == 1 else 8
                                est_data['ingreso'] = date(anio, mes, 1)
                        except: pass

                estudiantes_objs.append(Estudiante(**est_data))

            # Ejecutar bulk_create con lógica de actualización en conflictos (ON CONFLICT DO UPDATE)
            # Esto realiza una única consulta masiva a a base de datos.
            processed_count = 0
            if estudiantes_objs:
                with transaction.atomic():
                    # Dividimos en lotes de 500 para mayor seguridad con el driver
                    Estudiante.objects.bulk_create(
                        estudiantes_objs,
                        batch_size=500,
                        update_conflicts=True,
                        unique_fields=['codigo'],
                        update_fields=update_fields
                    )
                    processed_count = len(estudiantes_objs)

            return JsonResponse({
                "status": "success",
                "message": "Importación masiva finalizada correctamente",
                "detalles": {
                    "total_procesados": processed_count,
                    "omitidos": omitidos
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

        # Validar que el archivo tenga las columnas esperadas
        columnas_requeridas = [
            'Periodo', 'Materia Base', 'Codigo Materia',
            'Nombre Materia', 'Tipo Nota', 'Definitiva', 'Creditos'
        ]
        columnas_faltantes = [
            col for col in columnas_requeridas if col not in df.columns
        ]
        if columnas_faltantes:
            return JsonResponse({
                "status": "error",
                "mensaje": "El archivo no tiene el formato de Historial Académico esperado.",
                "error": "Faltan columnas requeridas.",
                "columnas_faltantes": columnas_faltantes,
                "columnas_encontradas": list(df.columns)
            }, status=400)

        errores = []
        filas_validas = []

        for index, row in df.iterrows():
            fila_num = index + 2
            
            if index % 50 == 0:
                reset_queries()

            # --- Parsear Periodo ---
            periodo_raw = str(row.get('Periodo', '')).strip()
            periodo_match = re.match(r'^(\d{4})\s*[-/]\s*([12])$', periodo_raw)

            if not periodo_match:
                errores.append({
                    "fila": fila_num, "campo": "Periodo", "valor": periodo_raw,
                    "mensaje": f"Formato de periodo inválido: '{periodo_raw}'. Se espera 'AAAA-S'."
                })
                continue

            anio = int(periodo_match.group(1))
            semestre = int(periodo_match.group(2))

            try:
                periodo_obj = Periodo.objects.get(anio=anio, semestre=semestre)
            except Periodo.DoesNotExist:
                errores.append({
                    "fila": fila_num, "campo": "Periodo", "valor": periodo_raw,
                    "mensaje": f"El periodo '{periodo_raw}' no existe en el sistema."
                })
                continue

            # --- Validar Curso ---
            codigo_materia = str(row.get('Codigo Materia', '')).strip()
            if pd.isna(row.get('Codigo Materia')) or codigo_materia == '':
                errores.append({"fila": fila_num, "campo": "Codigo Materia", "mensaje": "Código vacío."})
                continue

            match_codigo = re.match(r'^(\d+)(.*)$', codigo_materia)
            if match_codigo:
                base_materia = match_codigo.group(1)
                grupo_str = match_codigo.group(2).strip('- ').upper()
            else:
                base_materia = codigo_materia
                grupo_str = ''

            curso_obj = None
            if grupo_str:
                curso_obj = Curso.objects.filter(materia__codigo=base_materia, grupo=grupo_str).first()
            if not curso_obj:
                curso_obj = Curso.objects.filter(materia__codigo=base_materia).first()

            if not curso_obj:
                nombre_materia = str(row.get('Nombre Materia', '')).strip()
                errores.append({
                    "fila": fila_num, "campo": "Codigo Materia",
                    "mensaje": f"No existe curso con materia base '{base_materia} - {nombre_materia}'."
                })
                continue

            # --- Validar Nota ---
            nota_raw = row.get('Definitiva')
            try:
                nota = float(nota_raw)
                if not (0.0 <= nota <= 5.0): raise ValueError
            except:
                errores.append({"fila": fila_num, "campo": "Definitiva", "mensaje": f"Nota '{nota_raw}' inválida."})
                continue

            filas_validas.append({
                "estudiante": estudiante, "curso": curso_obj, "periodo": periodo_obj, "definitiva": nota,
            })

        if errores:
            return JsonResponse({
                "status": "error", "mensaje": "Errores encontrados en el archivo.",
                "errores": errores
            }, status=400)

        creados = 0
        with transaction.atomic():
            for fila in filas_validas:
                Nota.objects.update_or_create(
                    estudiante=fila["estudiante"],
                    curso=fila["curso"],
                    periodo=fila["periodo"],
                    defaults={"definitiva": fila["definitiva"]}
                )
                creados += 1

        return JsonResponse({"status": "success", "creados": creados})
    except Exception as e:
        traceback.print_exc()
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
                    
                    materia_obj, _ = Materia.objects.get_or_create(
                        codigo=cod_materia,
                        defaults={"nombre": str(row.get("Nombre", "SIN NOMBRE")).strip()}
                    )
                    
                    docente_obj = None
                    if not pd.isna(row.get("Código Docente")):
                        docente_obj, _ = Docente.objects.get_or_create(
                            codigo=str(row.get("Código Docente")).strip(),
                            defaults={"nombre": str(row.get("Nombre Docente", "SIN NOMBRE")).strip(), "usuario_id": 1} # Mock
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
        
        col_codigo = next((c for c in df.columns if 'Docente' in c and ('digo' in c or 'igo' in c)), None)
        col_nombre = next((c for c in df.columns if 'Nombre' in c and 'Docente' in c), None)
        col_vinculacion = next((c for c in df.columns if 'Vinculaci' in c), None)
        col_depto = next((c for c in df.columns if 'Departamento' in c), None)
        col_correo_p = next((c for c in df.columns if 'Personal' in c), None)
        col_correo_i = next((c for c in df.columns if 'Institucional' in c), None)
        col_celular = next((c for c in df.columns if 'Celular' in c), None)

        if not col_codigo or not col_nombre:
            return JsonResponse({"status": "error", "mensaje": "Columnas Código o Nombre no encontradas."}, status=400)

        creados = 0
        actualizados = 0
        usuarios_creados = 0
        errores = []

        with transaction.atomic():
            for index, row in df.iterrows():
                fila_num = index + 2
                if index % 50 == 0: reset_queries()
                
                codigo_raw = row.get(col_codigo)
                if pd.isna(codigo_raw): continue
                codigo = str(codigo_raw).strip().lstrip("'")

                nombre = str(row.get(col_nombre, '')).strip()
                tipo_vinculacion = str(row.get(col_vinculacion, 'DOCENTE CATEDRA')).strip() if col_vinculacion else 'DOCENTE CATEDRA'
                if tipo_vinculacion not in ['DOCENTE PLANTA', 'DOCENTE CATEDRA']: tipo_vinculacion = 'DOCENTE CATEDRA'
                
                depto = str(row.get(col_depto, '')).strip() if col_depto else ''
                correo_p = str(row.get(col_correo_p, '')).strip() if not pd.isna(row.get(col_correo_p)) else None
                correo_i = str(row.get(col_correo_i, '')).strip() if not pd.isna(row.get(col_correo_i)) else None
                celular = str(row.get(col_celular, '')).strip() if not pd.isna(row.get(col_celular)) else None

                try:
                    correo_u = correo_i or correo_p or f"{codigo}@ufps.edu.co"
                    usuario_obj, u_creado = Usuario.objects.get_or_create(
                        correo=correo_u,
                        defaults={"nombre": nombre, "rol": "DOCENTE", "contrasena": codigo, "activo": True}
                    )
                    if u_creado: usuarios_creados += 1

                    _, creado = Docente.objects.update_or_create(
                        codigo=codigo,
                        defaults={
                            "nombre": nombre, "tipo_vinculacion": tipo_vinculacion, "departamento": depto,
                            "correo_personal": correo_p, "correo_institucional": correo_i, "celular": celular,
                            "usuario": usuario_obj,
                        }
                    )
                    if creado: creados += 1
                    else: actualizados += 1
                except Exception as e:
                    errores.append({"fila": fila_num, "codigo": codigo, "error": str(e)})

        return JsonResponse({
            "status": "success" if not errores else "parcial",
            "mensaje": "Importación de docentes completada.",
            "usuarios_creados": usuarios_creados,
            "docentes_creados": creados,
            "docentes_actualizados": actualizados,
            "errores": errores,
        })
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
def importar_oferta_academica(request):
    if request.method != 'POST': return JsonResponse({"error": "Use POST"}, status=405)
    archivo = request.FILES.get('file')
    if not archivo: return JsonResponse({"error": "No file"}, status=400)
    
    try:
        extension = os.path.splitext(archivo.name)[1].lower()
        df = pd.read_csv(archivo, dtype={'Materia': str, 'Código Docente': str}) if extension == '.csv' else pd.read_excel(archivo, dtype={'Materia': str, 'Código Docente': str})
        df.columns = df.columns.str.strip()
        
        columnas_requeridas = ['Materia', 'Nombre', 'Código Docente', 'Nombre Docente', 'Horario', '# Matriculados']
        faltantes = [c for c in columnas_requeridas if c not in df.columns]
        if faltantes: return JsonResponse({"status": "error", "mensaje": "Faltan columnas.", "faltantes": faltantes}, status=400)

        df = df.dropna(subset=['Materia'])
        materias_creadas = 0
        cursos_creados = 0
        cursos_actualizados = 0

        with transaction.atomic():
            for index, row in df.iterrows():
                codigo_raw = str(row['Materia']).strip()
                match = re.match(r'^(\d+)([A-Z]?)$', codigo_raw)
                if not match: continue
                
                base = match.group(1)
                grupo = match.group(2)
                if not grupo: continue

                docente_cod = str(row['Código Docente']).strip()
                try:
                    docente_obj = Docente.objects.get(codigo=docente_cod)
                except Docente.DoesNotExist: continue

                materia_obj, creada = Materia.objects.get_or_create(codigo=base, defaults={"nombre": str(row['Nombre']).strip()})
                if creada: materias_creadas += 1

                curso_obj, created = Curso.objects.update_or_create(
                    materia=materia_obj, grupo=grupo,
                    defaults={
                        "docente": docente_obj, "horario": str(row['Horario']).strip(),
                        "cantidad_matriculados": int(row.get('# Matriculados', 0))
                    }
                )
                if created: cursos_creados += 1
                else: cursos_actualizados += 1

        return JsonResponse({
            "status": "success", "materias_creadas": materias_creadas,
            "cursos_creados": cursos_creados, "cursos_actualizados": cursos_actualizados
        })
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"status": "error", "mensaje": str(e)}, status=500)
