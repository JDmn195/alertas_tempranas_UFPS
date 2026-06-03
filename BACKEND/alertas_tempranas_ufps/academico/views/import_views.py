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
from academico.models import Curso, Docente, Estudiante, Nota, Periodo, Materia, BitacoraImportacion, EquivalenciaMateria
from usuarios.models import Usuario
from usuarios.decorators import requiere_rol
from usuarios.utils import registrar_auditoria

# ==============================================================================
# VISTAS PARA LA IMPORTACIÓN DE DATOS ACADÉMICOS
# ==============================================================================

def _registrar_bitacora(request, archivo_nombre, tipo, total_procesados, errores, exitoso):
    # Leer usuario del JWT (inyectado por el decorador) o del POST body como fallback
    usuario = getattr(request, 'usuario', None)
    if not usuario:
        usuario_id = request.POST.get('usuario_id')
        if usuario_id:
            try:
                usuario = Usuario.objects.get(id=usuario_id)
            except Usuario.DoesNotExist:
                pass

    num_errores = len(errores) if isinstance(errores, list) else 0
    # Fix 1.1: total_procesados debe ser 0 cuando la importación falla completamente
    # (evita que "exitosos = total_procesados - errores" dé negativo en el frontend)
    procesados_real = total_procesados if exitoso else max(0, total_procesados)

    BitacoraImportacion.objects.create(
        usuario=usuario,
        archivo_nombre=archivo_nombre,
        tipo=tipo,
        total_procesados=procesados_real,
        total_errores=num_errores,
        detalles_errores=errores if isinstance(errores, list) else [],
        exitoso=exitoso
    )

@csrf_exempt
@requiere_rol(['ADMINISTRADOR'])
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
                'promedio': ['promedio', 'promedio acumulado', 'promedio_accumulado', 'prom'],
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
                err_msg = f"Columnas requeridas 'Codigo' y 'Nombre' no encontradas. Detectadas: {', '.join(detected_cols)}"
                _registrar_bitacora(request, file.name, 'ESTUDIANTES', 0, [{"mensaje": err_msg}], False)
                return JsonResponse({
                    "status": "error",
                    "error": err_msg
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

                    # Fix 1.4: Para los estudiantes que tienen notas registradas,
                    # recalcular el promedio a partir de sus notas reales.
                    # Los que no tienen notas conservan el promedio del archivo.
                    from django.db.models import Avg as _Avg
                    from django.db.models import OuterRef, Subquery
                    codigos_importados = [est.codigo for est in estudiantes_objs]
                    # Obtener promedios calculados desde notas para los estudiantes importados
                    notas_con_prom = (
                        Nota.objects
                        .filter(estudiante_id__in=codigos_importados)
                        .exclude(definitiva__isnull=True)
                        .values('estudiante_id')
                        .annotate(ppa=_Avg('definitiva'))
                    )
                    for row in notas_con_prom:
                        Estudiante.objects.filter(codigo=row['estudiante_id']).update(
                            promedio=round(row['ppa'], 2)
                        )

            # AUTOMATIZACIÓN: Generar alertas para los estudiantes procesados
            # Fix 1.2: se ejecuta en background para no demorar la respuesta HTTP
            try:
                from alertas.views.alert_generation_views import reprocesar_alertas_completas
                import threading
                codigos_importados = [est.codigo for est in estudiantes_objs]
                def _generar_alertas_bg():
                    try:
                        qs = Estudiante.objects.filter(codigo__in=codigos_importados)
                        reprocesar_alertas_completas(qs, usuario=None)
                    except Exception as bg_err:
                        print(f"[BG] Error en generación automática de alertas: {bg_err}")
                threading.Thread(target=_generar_alertas_bg, daemon=True).start()
            except Exception as ae:
                print(f"Error en generación automática de alertas: {ae}")

            _registrar_bitacora(request, file.name, 'ESTUDIANTES', processed_count, [], True)
            registrar_auditoria(
                request.usuario,
                'IMPORTACION',
                f"Importación de ESTUDIANTES exitosa: {processed_count} registros procesados desde '{file.name}'."
            )

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
            if 'file' in locals() and hasattr(file, 'name'):
                _registrar_bitacora(request, file.name, 'ESTUDIANTES', 0, [{"mensaje": str(e)}], False)
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse({"status": "error", "message": "Método no permitido o archivo faltante"}, status=400)


@csrf_exempt
@requiere_rol(['ADMINISTRADOR'])
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
            err_msg = f"Faltan columnas requeridas: {', '.join(columnas_faltantes)}"
            _registrar_bitacora(request, nombre_archivo, 'HISTORIAL', 0, [{"mensaje": err_msg}], False)
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

            # Si el periodo no existe, se crea automáticamente
            periodo_obj, _ = Periodo.objects.get_or_create(anio=anio, semestre=semestre)

            # --- Validar Curso ---
            codigo_materia = str(row.get('Codigo Materia', '')).strip()
            if pd.isna(row.get('Codigo Materia')) or codigo_materia == '':
                errores.append({"fila": fila_num, "campo": "Codigo Materia", "mensaje": "Código vacío."})
                continue

            # Materia Base es el código limpio sin grupo (puede venir como número en Excel)
            materia_base_raw = row.get('Materia Base', '')
            if not pd.isna(materia_base_raw) and str(materia_base_raw).strip():
                # Limpiar: quitar decimales si pandas lo leyó como float (ej: 1155101.0 → "1155101")
                try:
                    base_materia = str(int(float(str(materia_base_raw).strip())))
                except (ValueError, TypeError):
                    base_materia = str(materia_base_raw).strip()
            else:
                # Fallback: extraer parte numérica de Codigo Materia
                match_codigo = re.match(r'^(\d+)(.*)$', codigo_materia)
                base_materia = match_codigo.group(1) if match_codigo else codigo_materia

            # Extraer grupo desde Codigo Materia eliminando el prefijo numérico base
            # Ej: "1155101A" con base "1155101" → grupo "A"
            grupo_str = ''
            if codigo_materia.startswith(base_materia):
                grupo_str = codigo_materia[len(base_materia):].strip('- ').upper()
            else:
                # Fallback regex si el codigo no empieza exactamente con base
                match_codigo = re.match(r'^(\d+)(.*)$', codigo_materia)
                if match_codigo:
                    grupo_str = match_codigo.group(2).strip('- ').upper()

            curso_obj = None
            if grupo_str:
                curso_obj = Curso.objects.filter(materia__codigo=base_materia, grupo=grupo_str).first()
            if not curso_obj:
                curso_obj = Curso.objects.filter(materia__codigo=base_materia).first()
            
            if not curso_obj:
                # Si el curso no existe, se crea automáticamente a partir de la materia.
                # Antes de crear una materia nueva, verificar si existe una del pensum
                # con el mismo nombre normalizado → registrar equivalencia automática.
                nombre_materia = str(row.get('Nombre Materia', '')).strip()
                creditos_raw = row.get('Creditos')
                try:
                    creditos_val = int(float(creditos_raw)) if not pd.isna(creditos_raw) else None
                except:
                    creditos_val = None

                def _normalizar(s):
                    """Normaliza un nombre: minúsculas, sin tildes, sin espacios extra."""
                    s = s.strip().lower()
                    s = ''.join(
                        c for c in unicodedata.normalize('NFD', s)
                        if unicodedata.category(c) != 'Mn'
                    )
                    return ' '.join(s.split())

                nombre_norm = _normalizar(nombre_materia)

                # Buscar materia del pensum (con semestre asignado) con mismo nombre normalizado
                materia_pensum_equiv = None
                for m in Materia.objects.filter(semestre__isnull=False):
                    if _normalizar(m.nombre) == nombre_norm and m.codigo != base_materia:
                        materia_pensum_equiv = m
                        break

                # Obtener o crear la materia con el código del historial
                materia_obj, creada = Materia.objects.get_or_create(
                    codigo=base_materia,
                    defaults={
                        "nombre": nombre_materia,
                        "creditos": creditos_val,
                        "tipo": "linea"
                    }
                )

                # Si encontramos una materia del pensum equivalente, registrar la relación
                if materia_pensum_equiv:
                    EquivalenciaMateria.objects.get_or_create(
                        materia_pensum=materia_pensum_equiv,
                        materia_equivalente=materia_obj
                    )

                # Obtener o crear docente por defecto para satisfacer el FK obligatorio
                default_user, _ = Usuario.objects.get_or_create(
                    correo='docente.defecto@ufps.edu.co',
                    defaults={
                        'nombre': 'Docente por Asignar',
                        'rol': 'DOCENTE',
                        'contrasena': '00000',
                        'activo': True
                    }
                )
                default_docente, _ = Docente.objects.get_or_create(
                    codigo='00000',
                    defaults={
                        'nombre': 'Docente por Asignar',
                        'tipo_vinculacion': 'DOCENTE CATEDRA',
                        'usuario': default_user
                    }
                )

                # Crear el curso con grupo por defecto 'A' si no viene especificado
                grupo_para_crear = grupo_str if grupo_str else 'A'
                curso_obj = Curso.objects.create(
                    materia=materia_obj,
                    grupo=grupo_para_crear,
                    docente=default_docente,
                    horario='POR DEFINIR',
                    cantidad_matriculados=0
                )

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
            _registrar_bitacora(request, nombre_archivo, 'HISTORIAL', 0, errores, False)
            return JsonResponse({
                "status": "error", "mensaje": "Errores encontrados en el archivo.",
                "errores": errores
            }, status=400)

        creados = 0
        with transaction.atomic():
            # Bulk upsert de notas — una sola query en lugar de N update_or_create
            nota_objs = [
                Nota(
                    estudiante=fila["estudiante"],
                    curso=fila["curso"],
                    periodo=fila["periodo"],
                    definitiva=fila["definitiva"],
                )
                for fila in filas_validas
            ]
            Nota.objects.bulk_create(
                nota_objs,
                batch_size=500,
                update_conflicts=True,
                unique_fields=['estudiante_id', 'curso_id', 'periodo_id'],
                update_fields=['definitiva'],
            )
            creados = len(nota_objs)

            # Fix 1.4: actualizar promedio del estudiante desde sus notas reales
            from django.db.models import Avg as _Avg
            ppa_result = Nota.objects.filter(
                estudiante=estudiante
            ).exclude(definitiva__isnull=True).aggregate(ppa=_Avg('definitiva'))
            if ppa_result['ppa'] is not None:
                Estudiante.objects.filter(codigo=estudiante.codigo).update(
                    promedio=round(ppa_result['ppa'], 2)
                )
                estudiante.refresh_from_db()

        _registrar_bitacora(request, nombre_archivo, 'HISTORIAL', creados, [], True)
        registrar_auditoria(
            request.usuario,
            'IMPORTACION',
            f"Importación de HISTORIAL exitosa: {creados} notas registradas desde '{nombre_archivo}'."
        )

        # Recalcular riesgo por periodo tras importar historial
        # Fix 1.2: se ejecuta en background para no demorar la respuesta HTTP
        try:
            from alertas.views.alert_generation_views import calcular_y_guardar_riesgo_por_periodos, reprocesar_alertas_completas
            import threading
            _codigo = codigo_estudiante
            _est = estudiante
            def _recalcular_bg():
                try:
                    calcular_y_guardar_riesgo_por_periodos(_est)
                    reprocesar_alertas_completas(
                        Estudiante.objects.filter(codigo=_codigo), usuario=None
                    )
                except Exception as bg_err:
                    print(f"[BG] Error en recálculo automático de riesgo/alertas: {bg_err}")
            threading.Thread(target=_recalcular_bg, daemon=True).start()
        except Exception as ae:
            print(f"Error en recálculo automático de riesgo/alertas: {ae}")

        return JsonResponse({"status": "success", "creados": creados})
    except Exception as e:
        traceback.print_exc()
        if 'nombre_archivo' in locals():
            _registrar_bitacora(request, nombre_archivo, 'HISTORIAL', 0, [{"mensaje": str(e)}], False)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
@requiere_rol(['ADMINISTRADOR'])
def importar_oferta_academica(request):   
    # 1. VALIDAR MÉTODO
    if request.method != 'POST':
        return JsonResponse(
            {"error": "Método no permitido. Use POST."},
            status=405
        )

    archivo = request.FILES.get('file')

    if not archivo:
        return JsonResponse(
            {"error": "No se envió ningún archivo."},
            status=400
        )

    # VALIDAR EXTENSIÓN
    nombre_archivo = archivo.name
    extension = os.path.splitext(nombre_archivo)[1].lower()

    if extension not in ['.xlsx', '.xls', '.csv']:
        return JsonResponse(
            {"error": f"Formato no soportado: {extension}"},
            status=400
        )

    # 2. LEER ARCHIVO
    try:
        if extension == '.csv':
            df = pd.read_csv(
                archivo,
                dtype={
                    'Materia': str,
                    'Código Docente': str
                }
            )
        else:
            df = pd.read_excel(
                archivo,
                dtype={
                    'Materia': str,
                    'Código Docente': str
                }
            )

    except Exception as e:
        return JsonResponse(
            {"error": f"Error leyendo archivo: {str(e)}"},
            status=400
        )

    # LIMPIAR COLUMNAS
    df.columns = df.columns.str.strip()

    columnas_requeridas = [
        'Materia',
        'Nombre',
        'Código Docente',
        'Nombre Docente',
        'Horario',
        '# Matriculados'
    ]

    faltantes = [
        c for c in columnas_requeridas
        if c not in df.columns
    ]

    if faltantes:
        err_msg = f"Faltan columnas requeridas: {', '.join(faltantes)}"
        _registrar_bitacora(request, nombre_archivo, 'OFERTA', 0, [{"mensaje": err_msg}], False)
        return JsonResponse({
            "status": "error",
            "mensaje": "El archivo no tiene el formato de Oferta Académica esperado.",
            "error": "Faltan columnas requeridas.",
            "columnas_faltantes": faltantes,
            "columnas_encontradas": list(df.columns)
        }, status=400)

    # ELIMINAR FILAS VACÍAS
    df = df.dropna(subset=['Materia'])

    errores = []
    registros_validos = []

    # 3. VALIDAR FILAS
    for index, row in df.iterrows():

        fila_num = index + 2

        codigo_materia_grupo = str(row['Materia']).strip()

        # Separar base y grupo (ej: 1150114A)
        # Identificamos la parte numérica inicial como 'base' y el resto como 'grupo'
        match = re.match(r'^(\d+)(.*)$', codigo_materia_grupo)

        if not match:
            errores.append({
                "fila": fila_num,
                "campo": "Materia",
                "valor": codigo_materia_grupo,
                "mensaje": "Formato inválido."
            })
            continue

        base_materia = match.group(1)
        grupo = match.group(2)

        if grupo == '':
            errores.append({
                "fila": fila_num,
                "campo": "Grupo",
                "valor": codigo_materia_grupo,
                "mensaje": "No se encontró grupo."
            })
            continue

        nombre_materia = str(row['Nombre']).strip()

        codigo_docente = str(row['Código Docente']).strip()
        # Asegurar que el código tenga 5 dígitos (rellenar con ceros a la izquierda)
        if codigo_docente and codigo_docente.lower() != 'nan':
            if '.' in codigo_docente:
                parts = codigo_docente.split('.')
                if parts[1] == '0' or parts[1] == '00' or all(ch == '0' for ch in parts[1]):
                    codigo_docente = parts[0]
            try:
                codigo_docente = str(int(float(codigo_docente))).zfill(5)
            except:
                codigo_docente = codigo_docente.zfill(5)
        
        if not codigo_docente or codigo_docente.lower() == 'nan':
            continue

        nombre_docente = str(
            row['Nombre Docente']
        ).strip()

        horario = str(row['Horario']).strip()

        matriculados_raw = row['# Matriculados']

        try:
            matriculados = int(matriculados_raw)
        except:
            matriculados = 0

        # VALIDAR DOCENTE
        try:
            docente_obj = Docente.objects.get(
                codigo=codigo_docente
            )

        except Docente.DoesNotExist:
            errores.append({
                "fila": fila_num,
                "campo": "Código Docente",
                "valor": codigo_docente,
                "mensaje": "El docente no existe."
            })
            continue

        registros_validos.append({
            "base": base_materia,
            "grupo": grupo,
            "nombre": nombre_materia,
            "docente": docente_obj,
            "horario": horario,
            "matriculados": matriculados
        })

    # CANCELAR SI HAY ERRORES
    if errores:
        _registrar_bitacora(request, nombre_archivo, 'OFERTA', len(registros_validos), errores, False)
        return JsonResponse({
            "status": "error",
            "mensaje": "Se encontraron errores.",
            "total_errores": len(errores),
            "errores": errores
        }, status=400)

    # 4. GUARDAR
    try:

        materias_creadas = 0
        materias_actualizadas = 0
        cursos_creados = 0
        cursos_actualizados = 0

        with transaction.atomic():

            for fila in registros_validos:

                # CREAR / ACTUALIZAR MATERIA
                materia_obj, creada = Materia.objects.update_or_create(
                    codigo=fila["base"],
                    defaults={
                        "nombre": fila["nombre"]
                    }
                )

                if creada:
                    materias_creadas += 1
                else:
                    materias_actualizadas += 1

                # CREAR / ACTUALIZAR CURSO
                curso_obj, created = Curso.objects.update_or_create(
                    materia=materia_obj,
                    grupo=fila["grupo"],
                    defaults={
                        "docente": fila["docente"],
                        "horario": fila["horario"],
                        "cantidad_matriculados":
                            fila["matriculados"]
                    }
                )

                if created:
                    cursos_creados += 1
                else:
                    cursos_actualizados += 1

        _registrar_bitacora(request, nombre_archivo, 'OFERTA', len(registros_validos), [], True)
        registrar_auditoria(
            request.usuario,
            'IMPORTACION',
            f"Importación de OFERTA ACADÉMICA exitosa: {len(registros_validos)} registros desde '{nombre_archivo}'."
        )
        return JsonResponse({

            "status": "success",
            "mensaje": "Relación de materias/oferta académica procesada correctamente.",

            "materias_creadas": materias_creadas,
            "materias_actualizadas": materias_actualizadas,
            "cursos_creados": cursos_creados,
            "cursos_actualizados": cursos_actualizados,
            "total_procesado": len(registros_validos)

        })

    except Exception as e:

        traceback.print_exc()

        if 'nombre_archivo' in locals():
            _registrar_bitacora(request, nombre_archivo, 'OFERTA', 0, [{"mensaje": str(e)}], False)
        return JsonResponse({
            "status": "error",
            "mensaje": str(e)
        }, status=500)


@csrf_exempt
@requiere_rol(['ADMINISTRADOR'])
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
    # 2. LEER ARCHIVO Y VALIDAR FORMATO
    # ────────────────────────────────────────────
    try:
        df = pd.read_excel(archivo)
        df.columns = df.columns.str.strip()
    except Exception as e:
        _registrar_bitacora(request, archivo.name, 'DOCENTES', 0, [{"mensaje": f"Error al leer el archivo: {str(e)}"}], False)
        return JsonResponse(
            {"error": f"Error al leer el archivo: {str(e)}"},
            status=400
        )

    # 1. Detectar columnas dinámicamente para tolerar caracteres especiales
    col_codigo      = next((c for c in df.columns if 'Docente' in c and ('digo' in c or 'igo' in c)), None)
    col_nombre      = next((c for c in df.columns if 'Nombre' in c and 'Docente' in c), None)
    col_vinculacion = next((c for c in df.columns if 'Vinculaci' in c), None)
    col_depto       = next((c for c in df.columns if 'Departamento' in c), None)
    col_correo_p    = next((c for c in df.columns if 'Personal' in c), None)
    col_correo_i    = next((c for c in df.columns if 'Institucional' in c), None)
    col_celular     = next((c for c in df.columns if 'Celular' in c), None)

    # 2. VALIDACIÓN DE FIRMA (Evitar confusión con Cursos o Historial)
    # Si tiene la columna 'Materia', probablemente es un archivo de Cursos u Oferta Académica
    es_otro_archivo = any(c for c in df.columns if 'Materia' in c or 'Horario' in c)

    if es_otro_archivo:
        err_msg = "El archivo parece ser un reporte de Cursos u Oferta Académica."
        _registrar_bitacora(request, archivo.name, 'DOCENTES', 0, [{"mensaje": err_msg}], False)
        return JsonResponse({
            "status": "error",
            "mensaje": err_msg,
            "error": "Se detectó la columna 'Materia' o 'Horario', las cuales no pertenecen al formato de Docentes."
        }, status=400)

    # 3. VERIFICAR COLUMNAS MÍNIMAS
    if not col_codigo or not col_nombre:
        err_msg = "No se encontraron las columnas de Código o Nombre del docente."
        _registrar_bitacora(request, archivo.name, 'DOCENTES', 0, [{"mensaje": err_msg}], False)
        return JsonResponse({
            "status": "error",
            "mensaje": err_msg,
            "encontradas": list(df.columns)
        }, status=400)

    # ─────────────────────────────────────────────
    # 3. PROCESAR CADA FILA
    # ─────────────────────────────────────────────
    creados          = 0
    actualizados     = 0
    usuarios_creados = 0
    errores          = []

    with transaction.atomic():
        for index, row in df.iterrows():
            fila_num = index + 2

            # Limpiar memoria de queries cada 50 filas
            if index % 50 == 0:
                reset_queries()

            # ── Leer y limpiar código ──────────────────────────────────
            codigo_raw = row.get(col_codigo)
            if pd.isna(codigo_raw) or str(codigo_raw).strip() == '':
                continue
            
            codigo = str(codigo_raw).strip().lstrip("'")
            # Asegurar que el código tenga 5 dígitos (rellenar con ceros a la izquierda)
            if codigo and codigo.lower() != 'nan':
                if '.' in codigo:
                    parts = codigo.split('.')
                    if parts[1] == '0' or parts[1] == '00' or all(ch == '0' for ch in parts[1]):
                        codigo = parts[0]
                try:
                    codigo = str(int(float(codigo))).zfill(5)
                except:
                    codigo = codigo.zfill(5)
            
            if not codigo or codigo.lower() == 'nan':
                continue

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
                # ── 1. Crear o buscar Usuario ──────────────────────
                correo_usuario = correo_institucional or correo_personal or f"{codigo}@ufps.edu.co"

                usuario_obj, usuario_creado = Usuario.objects.get_or_create(
                    correo=correo_usuario,
                    defaults={
                        "nombre":     nombre,
                        "rol":        "DOCENTE",
                        "contrasena": codigo,
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

    # ─────────────────────────────────────────────
    # 4. RETORNAR RESUMEN
    # ─────────────────────────────────────────────
    _registrar_bitacora(request, archivo.name, 'DOCENTES', creados + actualizados, errores, not errores)
    if not errores:
        registrar_auditoria(
            request.usuario,
            'IMPORTACION',
            f"Importación de DOCENTES exitosa: {creados} creados, {actualizados} actualizados desde '{archivo.name}'."
        )
    return JsonResponse({
        "status":                "success" if not errores else "parcial",
        "mensaje":               "Importación de docentes completada.",
        "usuarios_creados":      usuarios_creados,
        "docentes_creados":      creados,
        "docentes_actualizados": actualizados,
        "errores":               errores,
    })
