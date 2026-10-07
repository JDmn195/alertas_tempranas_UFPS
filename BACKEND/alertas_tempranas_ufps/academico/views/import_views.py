from django.http import JsonResponse
from django.contrib.auth.hashers import make_password
from django.core.files.storage import FileSystemStorage
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction, reset_queries
import pandas as pd
import os
import re
import unicodedata
import traceback
import logging
from datetime import date, datetime
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from academico.models import Curso, Docente, Estudiante, Nota, Periodo, Materia, BitacoraImportacion, EquivalenciaMateria, Asistencia
from usuarios.models import Usuario
from usuarios.decorators import requiere_rol
from usuarios.utils import registrar_auditoria
from academico.services.asistencia import normalizar_estado, estudiantes_del_curso, puede_gestionar_curso

logger = logging.getLogger(__name__)

from academico.constants import NOTA_APROBATORIA, PESO_CORTES, PESO_EXAMEN, DECIMALES_REDONDEO, CANTIDAD_CORTES

def calcular_definitiva(c1, c2, c3, examen):
    cortes = (Decimal(str(c1)) + Decimal(str(c2)) + Decimal(str(c3))) / CANTIDAD_CORTES
    nota = (cortes * PESO_CORTES) + (Decimal(str(examen)) * PESO_EXAMEN)
    return float(nota.quantize(DECIMALES_REDONDEO, rounding=ROUND_HALF_UP))

# Tamaño máximo permitido para archivos de importación (configurable en settings).
# Por defecto: 10 MB. Ajustar en settings.py con MAX_IMPORT_FILE_SIZE_MB.
_MAX_MB = getattr(settings, 'MAX_IMPORT_FILE_SIZE_MB', 10)
MAX_IMPORT_FILE_SIZE = _MAX_MB * 1024 * 1024  # bytes

# Porcentaje máximo de registros inválidos antes de cancelar una importación (INC-01)
MAX_PORCENTAJE_INVALIDOS = getattr(settings, 'IMPORT_MAX_PORCENTAJE_INVALIDOS', 10)


def _validar_tamano_archivo(archivo):
    """
    Devuelve un JsonResponse de error (status 413) si el archivo supera
    MAX_IMPORT_FILE_SIZE, o None si el tamaño es aceptable.
    """
    if archivo.size > MAX_IMPORT_FILE_SIZE:
        mb_recibido = archivo.size / (1024 * 1024)
        logger.warning(
            "Archivo rechazado por tamaño: '%s' (%.2f MB, límite %d MB)",
            archivo.name, mb_recibido, _MAX_MB
        )
        return JsonResponse(
            {
                "status": "error",
                "error": (
                    f"El archivo '{archivo.name}' supera el tamaño máximo permitido "
                    f"({_MAX_MB} MB). Tamaño recibido: {mb_recibido:.2f} MB."
                ),
            },
            status=413,
        )
    return None


def _validar_request_archivo(request, extensiones_permitidas=None):
    """
    Valida método POST, presencia del archivo, tamaño y extensión.
    Devuelve (archivo, None) si todo es correcto, o (None, JsonResponse) con el error.
    """
    if request.method != 'POST':
        return None, JsonResponse({"error": "Método no permitido. Use POST."}, status=405)

    archivo = request.FILES.get('file')
    if not archivo:
        return None, JsonResponse({"error": "No se envió ningún archivo."}, status=400)

    error_tamano = _validar_tamano_archivo(archivo)
    if error_tamano:
        return None, error_tamano

    if extensiones_permitidas:
        extension = os.path.splitext(archivo.name)[1].lower()
        if extension not in extensiones_permitidas:
            ext_str = ', '.join(extensiones_permitidas)
            return None, JsonResponse(
                {"error": f"Formato no soportado: '{extension}'. Se aceptan {ext_str}"},
                status=400,
            )

    return archivo, None


def _leer_dataframe(archivo, dtype=None):
    """
    Lee un archivo Excel o CSV en un DataFrame, limpia los nombres de columnas
    y devuelve (df, None) o (None, JsonResponse) si la lectura falla.
    """
    extension = os.path.splitext(archivo.name)[1].lower()
    try:
        if extension == '.csv':
            df = pd.read_csv(archivo, dtype=dtype or {})
        else:
            df = pd.read_excel(archivo, dtype=dtype or {})
        df.columns = df.columns.str.strip()
        return df, None
    except Exception as e:
        logger.warning("Error leyendo archivo '%s': %s", archivo.name, e, exc_info=True)
        return None, JsonResponse({"error": "Error leyendo archivo: verifica que sea un Excel o CSV válido y no esté dañado."}, status=400)


def _validar_columnas(df, columnas_requeridas, nombre_archivo, tipo_bitacora, request, nombre_formato):
    """
    Comprueba que df contenga todas las columnas requeridas.
    Devuelve None si está bien, o un JsonResponse de error (400) si faltan columnas.
    Registra la bitácora automáticamente en caso de error.
    """
    faltantes = [c for c in columnas_requeridas if c not in df.columns]
    if faltantes:
        err_msg = f"Faltan columnas requeridas: {', '.join(faltantes)}"
        _registrar_bitacora(request, nombre_archivo, tipo_bitacora, 0, [{"mensaje": err_msg}], False)
        return JsonResponse({
            "status": "error",
            "mensaje": f"El archivo no tiene el formato de {nombre_formato} esperado.",
            "error": "Faltan columnas requeridas.",
            "columnas_faltantes": faltantes,
            "columnas_encontradas": list(df.columns),
        }, status=400)
    return None


def _normalizar_codigo_docente(codigo_raw):
    """
    Limpia y normaliza un código de docente a 5 dígitos con ceros a la izquierda.
    Devuelve None si el valor es vacío o inválido.
    """
    if pd.isna(codigo_raw):
        return None
    codigo = str(codigo_raw).strip().lstrip("'")
    if not codigo or codigo.lower() == 'nan':
        return None
    # Eliminar parte decimal irrelevante (ej: "1234.0" → "1234")
    if '.' in codigo:
        parts = codigo.split('.')
        if all(ch == '0' for ch in parts[1]):
            codigo = parts[0]
    try:
        codigo = str(int(float(codigo))).zfill(5)
    except (ValueError, TypeError):
        codigo = codigo.zfill(5)
    return codigo if codigo.lower() != 'nan' else None

# ==============================================================================
# VISTAS PARA LA IMPORTACIÓN DE DATOS ACADÉMICOS
# ==============================================================================
#
# NOTA DE SEGURIDAD — @csrf_exempt
# ─────────────────────────────────
# Todas las vistas de este módulo usan @csrf_exempt porque esta API es
# stateless: la autenticación se realiza exclusivamente mediante JWT en el
# header "Authorization: Bearer <token>", no mediante cookies de sesión.
#
# La protección CSRF de Django está diseñada para ataques que explotan
# cookies de sesión. Un atacante que intente un CSRF desde otro origen
# no puede leer ni inyectar el header Authorization, por lo que el riesgo
# que CSRF mitiga no existe en este contexto.
#
# La autenticación y autorización real la provee el decorador @requiere_rol,
# que valida y decodifica el JWT en cada petición.
# ==============================================================================

# Periodo 'AAAA-S' (historial y asistencia) y materia + grupo como en la oferta ('1155501A')
_RE_PERIODO = re.compile(r'^(\d{4})\s*[-/]\s*([12])$')
_RE_MATERIA_GRUPO = re.compile(r'^(\d+)(.*)$')


def _periodo_mas_reciente(periodos_archivo=()):
    """
    Devuelve (anio, semestre) del periodo más reciente entre los registrados en la BD
    y los valores válidos de periodos_archivo, o None si no hay ninguno.
    """
    candidatos = list(Periodo.objects.values_list('anio', 'semestre'))
    for valor in periodos_archivo:
        match = _RE_PERIODO.match(str(valor).strip())
        if match:
            candidatos.append((int(match.group(1)), int(match.group(2))))
    return max(candidatos) if candidatos else None


def _registrar_bitacora(request, archivo_nombre, tipo, total_procesados, errores, exitoso, advertencias=None):
    # Usuario del JWT (inyectado por @requiere_rol); nunca de datos del cliente
    usuario = getattr(request, 'usuario', None)

    # total_procesados = registros realmente guardados: 0 si la importación se canceló
    num_errores = len(errores) if isinstance(errores, list) else 0

    detalles = errores if isinstance(errores, list) else []
    if advertencias and isinstance(advertencias, list):
        detalles = detalles + advertencias

    BitacoraImportacion.objects.create(
        usuario=usuario,
        archivo_nombre=archivo_nombre,
        tipo=tipo,
        total_procesados=total_procesados,
        total_errores=num_errores,
        detalles_errores=detalles,
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
        error_tamano = _validar_tamano_archivo(file)
        if error_tamano:
            return error_tamano
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
                except (UnicodeDecodeError, ValueError):
                    # Fallback: intentar con encoding latin-1 o separador por defecto
                    file.seek(0)
                    df = pd.read_csv(file, encoding='latin-1')
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

            if not c_codigo or not c_nombre or not c_doc:
                detected_cols = list(df.columns)
                err_msg = f"Columnas requeridas 'Codigo', 'Nombre' y 'Documento' no encontradas. Detectadas: {', '.join(detected_cols)}"
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
                except (ValueError, TypeError):
                    return None

            estudiantes_objs = []
            errores = []        # registros rechazados por formato o campos en blanco
            duplicados = []     # códigos o documentos repetidos en el archivo (se conserva la primera fila)
            codigos_vistos = {}
            documentos_vistos = {}
            omitidos = 0        # filas completamente vacías (no cuentan como registros)

            # Los campos que se actualizarán si ya existe el registro
            update_fields = [
                'nombre', 'tipo_documento', 'numero_documento', 'pensum',
                'estado_matricula', 'celular', 'email_personal', 'email_institucional',
                'colegio_egresado', 'municipio_nacimiento', 'semestre', 'promedio', 'ingreso'
            ]

            def texto(row, col):
                if not col or pd.isna(row[col]):
                    return ''
                return str(row[col]).strip()

            def error(fila, campo, valor, mensaje):
                return {"fila": fila, "campo": campo, "valor": valor, "mensaje": mensaje}

            for i, row in df.iterrows():
                fila = i + 2  # +1 por el encabezado, +1 porque Excel numera desde 1
                if row.isna().all():
                    omitidos += 1
                    continue

                errores_fila = []

                codigo_val = texto(row, c_codigo)
                if codigo_val.endswith('.0'):
                    codigo_val = codigo_val[:-2]
                if not codigo_val:
                    errores_fila.append(error(fila, 'Código', '', 'El código del estudiante está en blanco.'))
                elif not codigo_val.isdigit():
                    errores_fila.append(error(fila, 'Código', codigo_val, 'El código debe contener solo números.'))

                nombre_val = texto(row, c_nombre)
                if not nombre_val:
                    errores_fila.append(error(fila, 'Nombre', '', 'El nombre del estudiante está en blanco.'))

                documento_val = texto(row, c_doc)
                if documento_val.endswith('.0'):
                    documento_val = documento_val[:-2]
                if not documento_val:
                    errores_fila.append(error(fila, 'Documento', '', 'El número de documento está en blanco.'))

                semestre_val = 1
                if c_sem and texto(row, c_sem):
                    semestre_val = safe_int(row[c_sem])
                    if semestre_val is None or not 1 <= semestre_val <= 12:
                        errores_fila.append(error(fila, 'Semestre', texto(row, c_sem),
                                                  'El semestre debe ser un número entre 1 y 12.'))

                promedio_val = None
                if c_prom and texto(row, c_prom):
                    try:
                        promedio_val = float(texto(row, c_prom).replace(',', '.'))
                        if not 0 <= promedio_val <= 5:
                            raise ValueError
                    except ValueError:
                        errores_fila.append(error(fila, 'Promedio', texto(row, c_prom),
                                                  'El promedio debe ser un número entre 0 y 5.'))

                for col, campo in ((c_email_p, 'Email personal'), (c_email_i, 'Email institucional')):
                    correo = texto(row, col)
                    if correo:
                        try:
                            validate_email(correo)
                        except DjangoValidationError:
                            errores_fila.append(error(fila, campo, correo, 'El correo no tiene un formato válido.'))

                if errores_fila:
                    errores.extend(errores_fila)
                    continue

                if codigo_val in codigos_vistos:
                    duplicados.append(error(
                        fila, 'Código', codigo_val,
                        f'Código duplicado en el archivo (ya aparece en la fila {codigos_vistos[codigo_val]}); '
                        f'se rechazó este registro.'
                    ))
                    continue
                if documento_val in documentos_vistos:
                    duplicados.append(error(
                        fila, 'Documento', documento_val,
                        f'Documento duplicado en el archivo (ya aparece en la fila {documentos_vistos[documento_val]}); '
                        f'se rechazó este registro.'
                    ))
                    continue
                codigos_vistos[codigo_val] = fila
                documentos_vistos[documento_val] = fila

                est_data = {
                    'codigo': codigo_val,
                    'nombre': nombre_val,
                    'tipo_documento': texto(row, c_tipo_doc),
                    'numero_documento': documento_val,
                    'pensum': texto(row, c_pensum),
                    'estado_matricula': texto(row, c_estado_mat),
                    'celular': texto(row, c_cel),
                    'email_personal': texto(row, c_email_p),
                    'email_institucional': texto(row, c_email_i),
                    'colegio_egresado': texto(row, c_colegio),
                    'municipio_nacimiento': texto(row, c_municipio),
                    'semestre': semestre_val,
                    'promedio': promedio_val,
                }

                # Lógica de Ingreso
                est_data['ingreso'] = None
                if c_ingreso:
                    ingreso_val = texto(row, c_ingreso)
                    if '-' in ingreso_val:
                        try:
                            partes = ingreso_val.split('-')
                            anio = safe_int(partes[0])
                            sem = safe_int(partes[1])
                            if anio and sem:
                                mes = 2 if sem == 1 else 8
                                est_data['ingreso'] = date(anio, mes, 1)
                        except (ValueError, IndexError):
                            pass  # Formato de ingreso no reconocido, se deja como None

                estudiantes_objs.append(Estudiante(**est_data))

            # El documento es único: rechazar los que ya pertenecen a otro estudiante registrado
            if estudiantes_objs:
                dueno_documento = dict(
                    Estudiante.objects
                    .filter(numero_documento__in=[e.numero_documento for e in estudiantes_objs])
                    .values_list('numero_documento', 'codigo')
                )
                validos = []
                for est, fila in ((e, codigos_vistos[e.codigo]) for e in estudiantes_objs):
                    dueno = dueno_documento.get(est.numero_documento)
                    if dueno and dueno != est.codigo:
                        errores.append(error(
                            fila, 'Documento', est.numero_documento,
                            f'El documento ya está registrado para el estudiante {dueno}.'
                        ))
                    else:
                        validos.append(est)
                estudiantes_objs = validos

            # INC-01: si los registros rechazados superan el umbral, se cancela todo
            # (no se guarda nada) para no dejar estudiantes con datos inconsistentes.
            rechazados = errores + duplicados
            total_registros = len(estudiantes_objs) + len(rechazados)
            if total_registros == 0:
                msg = "El archivo no contiene registros de estudiantes."
                _registrar_bitacora(request, file.name, 'ESTUDIANTES', 0, [{"mensaje": msg}], False)
                return JsonResponse({"status": "error", "mensaje": msg}, status=400)

            porcentaje_invalidos = len(rechazados) * 100 / total_registros
            if porcentaje_invalidos > MAX_PORCENTAJE_INVALIDOS:
                msg = (f"Error: más del {MAX_PORCENTAJE_INVALIDOS:g} % de registros inválidos, importación cancelada "
                       f"({len(rechazados)} de {total_registros}, {porcentaje_invalidos:.1f} %).")
                _registrar_bitacora(request, file.name, 'ESTUDIANTES', 0, rechazados, False)
                registrar_auditoria(
                    request.usuario, 'IMPORTACION',
                    f"Importación de ESTUDIANTES cancelada desde '{file.name}': {len(rechazados)} de "
                    f"{total_registros} registros inválidos ({porcentaje_invalidos:.1f} %)"
                    + (f", de ellos {len(duplicados)} con código duplicado." if duplicados else ".")
                )
                return JsonResponse({
                    "status": "error",
                    "mensaje": msg,
                    "total_registros": total_registros,
                    "total_errores": len(rechazados),
                    "porcentaje_invalidos": round(porcentaje_invalidos, 1),
                    "errores": rechazados,
                }, status=400)

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
                    # recalcular el promedio (PPA ponderado por créditos) a partir
                    # de sus notas reales. Los que no tienen notas conservan el
                    # promedio del archivo.
                    from alertas.evaluacion import actualizar_promedio
                    codigos_importados = [est.codigo for est in estudiantes_objs]
                    codigos_con_notas = (
                        Nota.objects
                        .filter(estudiante_id__in=codigos_importados, definitiva__isnull=False)
                        .values_list('estudiante_id', flat=True)
                        .distinct()
                    )
                    for est in Estudiante.objects.filter(codigo__in=codigos_con_notas):
                        actualizar_promedio(est)

            # AUTOMATIZACIÓN: Generar alertas para los estudiantes procesados
            # Fix 1.2: se ejecuta en background para no demorar la respuesta HTTP
            try:
                from alertas.views.alert_generation_views import reprocesar_alertas_completas
                from alertas.tareas import ejecutar_en_segundo_plano
                codigos_importados = [est.codigo for est in estudiantes_objs]
                def _generar_alertas_bg():
                    qs = Estudiante.objects.filter(codigo__in=codigos_importados)
                    reprocesar_alertas_completas(qs, usuario=None)
                ejecutar_en_segundo_plano(_generar_alertas_bg)
            except Exception as ae:
                logger.warning("Error en generación automática de alertas tras importar estudiantes: %s", ae, exc_info=True)

            # Los rechazados (por debajo del umbral) quedan como errores en la bitácora.
            # total_procesados = registros leídos, así "exitosos = procesados - errores" en el frontend.
            _registrar_bitacora(request, file.name, 'ESTUDIANTES', total_registros, rechazados, True)
            detalle = f"Importación de ESTUDIANTES exitosa: {processed_count} registros procesados desde '{file.name}'."
            if errores:
                detalle += f" {len(errores)} registros rechazados por errores de formato o campos en blanco."
            if duplicados:
                codigos_dup = ', '.join(sorted({d['valor'] for d in duplicados}))
                detalle += (f" {len(duplicados)} registros rechazados por código duplicado en el archivo "
                            f"(códigos: {codigos_dup}).")
            registrar_auditoria(request.usuario, 'IMPORTACION', detalle)

            mensaje = f"Importación finalizada: {processed_count} estudiantes guardados."
            if rechazados:
                mensaje += f" {len(rechazados)} registros rechazados (ver advertencias)."
            return JsonResponse({
                "status": "success",
                "mensaje": mensaje,
                "message": "Importación masiva finalizada correctamente",
                "advertencias": rechazados,
                "detalles": {
                    "total_procesados": processed_count,
                    "rechazados": len(errores),
                    "duplicados": len(duplicados),
                    "omitidos": omitidos
                }
            })

        except Exception as e:
            logger.error("Error inesperado al importar estudiantes desde '%s': %s", 
                         file.name if 'file' in locals() and hasattr(file, 'name') else 'archivo desconocido',
                         e, exc_info=True)
            if 'file' in locals() and hasattr(file, 'name'):
                _registrar_bitacora(request, file.name, 'ESTUDIANTES', 0, [{"mensaje": str(e)}], False)
            return JsonResponse({"status": "error", "mensaje": "Error inesperado al procesar la importación. Revisa la bitácora o contacta al administrador."}, status=500)

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

    error_tamano = _validar_tamano_archivo(archivo)
    if error_tamano:
        return error_tamano

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

        # Validar que el archivo tenga las columnas esperadas.
        # Tipo Nota y Creditos se ignoran si vienen; no son requeridas.
        columnas_requeridas = [
            'Periodo', 'Materia Base', 'Codigo Materia',
            'Nombre Materia', 'Corte 1', 'Corte 2', 'Corte 3',
            'Examen Final', 'Definitiva'
        ]
        error = _validar_columnas(df, columnas_requeridas, nombre_archivo, 'HISTORIAL', request, 'Historial Académico')
        if error:
            return error

        errores = []
        advertencias = []
        filas_validas = []

        # HU-33: el periodo más reciente (de la BD o del archivo) admite filas sin notas,
        # que representan la matrícula del estudiante en el curso.
        periodo_reciente = _periodo_mas_reciente(df['Periodo'])

        for index, row in df.iterrows():
            fila_num = index + 2

            if index % 50 == 0:
                reset_queries()

            # --- Parsear Periodo ---
            periodo_raw = str(row.get('Periodo', '')).strip()
            periodo_match = _RE_PERIODO.match(periodo_raw)

            if not periodo_match:
                errores.append({
                    "fila": fila_num, "campo": "Periodo", "valor": periodo_raw,
                    "mensaje": f"Formato de periodo inválido: '{periodo_raw}'. Se espera 'AAAA-S'."
                })
                continue

            anio = int(periodo_match.group(1))
            semestre_num = int(periodo_match.group(2))
            periodo_obj, _ = Periodo.objects.get_or_create(anio=anio, semestre=semestre_num)

            # --- Materia Base y grupo ---
            codigo_materia = str(row.get('Codigo Materia', '')).strip()
            if pd.isna(row.get('Codigo Materia')) or codigo_materia == '':
                errores.append({"fila": fila_num, "campo": "Codigo Materia", "mensaje": "Código vacío."})
                continue

            materia_base_raw = row.get('Materia Base', '')
            if not pd.isna(materia_base_raw) and str(materia_base_raw).strip():
                try:
                    base_materia = str(int(float(str(materia_base_raw).strip())))
                except (ValueError, TypeError):
                    base_materia = str(materia_base_raw).strip()
            else:
                match_codigo = re.match(r'^(\d+)(.*)$', codigo_materia)
                base_materia = match_codigo.group(1) if match_codigo else codigo_materia

            grupo_str = ''
            if codigo_materia.startswith(base_materia):
                grupo_str = codigo_materia[len(base_materia):].strip('- ').upper()
            else:
                match_codigo = re.match(r'^(\d+)(.*)$', codigo_materia)
                if match_codigo:
                    grupo_str = match_codigo.group(2).strip('- ').upper()

            # --- Materia debe existir en el pensum ---
            try:
                materia_obj = Materia.objects.get(codigo=base_materia)
            except Materia.DoesNotExist:
                errores.append({
                    "fila": fila_num, "campo": "Codigo Materia", "valor": base_materia,
                    "mensaje": f"Materia {base_materia} no registrada en el pensum."
                })
                continue

            # --- Curso: buscar por materia y grupo; crear si no existe ---
            curso_obj = None
            if grupo_str:
                curso_obj = Curso.objects.filter(materia=materia_obj, grupo=grupo_str).first()
            if not curso_obj:
                # Crear docente por defecto
                default_user, _ = Usuario.objects.get_or_create(
                    correo='docente.defecto@ufps.edu.co',
                    defaults={
                        'nombre': 'Docente por Asignar',
                        'rol': 'DOCENTE',
                        'contrasena': make_password(None),  # cuenta de relleno, sin acceso
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
                grupo_para_crear = grupo_str if grupo_str else 'A'
                curso_obj = Curso.objects.create(
                    materia=materia_obj,
                    grupo=grupo_para_crear,
                    docente=default_docente,
                    horario='POR DEFINIR',
                    cantidad_matriculados=0
                )

            # --- Validar notas por corte y examen ---
            def _leer_nota_columna(col_name):
                """Retorna (valor_float_o_None, error_str_o_None)."""
                raw = row.get(col_name)
                if raw is None or (isinstance(raw, float) and pd.isna(raw)) or str(raw).strip() == '':
                    return None, None
                try:
                    val = float(raw)
                    if not (0.0 <= val <= 5.0):
                        return None, f"Nota '{raw}' fuera de rango (0.0 – 5.0)."
                    return val, None
                except (ValueError, TypeError):
                    return None, f"Nota '{raw}' no es un número válido."

            fila_con_error = False
            corte1, err = _leer_nota_columna('Corte 1')
            if err:
                errores.append({"fila": fila_num, "campo": "Corte 1", "valor": row.get('Corte 1'), "mensaje": err})
                fila_con_error = True
            corte2, err = _leer_nota_columna('Corte 2')
            if err:
                errores.append({"fila": fila_num, "campo": "Corte 2", "valor": row.get('Corte 2'), "mensaje": err})
                fila_con_error = True
            corte3, err = _leer_nota_columna('Corte 3')
            if err:
                errores.append({"fila": fila_num, "campo": "Corte 3", "valor": row.get('Corte 3'), "mensaje": err})
                fila_con_error = True
            examen, err = _leer_nota_columna('Examen Final')
            if err:
                errores.append({"fila": fila_num, "campo": "Examen Final", "valor": row.get('Examen Final'), "mensaje": err})
                fila_con_error = True
            definitiva_archivo, err = _leer_nota_columna('Definitiva')
            if err:
                errores.append({"fila": fila_num, "campo": "Definitiva", "valor": row.get('Definitiva'), "mensaje": err})
                fila_con_error = True

            if fila_con_error:
                continue

            tiene_cortes = corte1 is not None and corte2 is not None and corte3 is not None
            tiene_examen = examen is not None
            todas_notas = tiene_cortes and tiene_examen
            ninguna_nota = (corte1 is None and corte2 is None and corte3 is None and examen is None)

            # --- Calcular definitiva según reglas ---
            definitiva_final = None

            if todas_notas:
                definitiva_calc = calcular_definitiva(corte1, corte2, corte3, examen)
                if definitiva_archivo is not None and abs(definitiva_archivo - definitiva_calc) > 0.05:
                    advertencias.append({
                        "fila": fila_num, "campo": "Definitiva", "nivel": "advertencia",
                        "mensaje": f"Definitiva del archivo ({definitiva_archivo}) difiere de la calculada ({definitiva_calc}). Se guardó la calculada."
                    })
                definitiva_final = definitiva_calc

            elif ninguna_nota and definitiva_archivo is not None:
                # Periodo antiguo: solo viene definitiva
                definitiva_final = definitiva_archivo

            elif ninguna_nota and definitiva_archivo is None:
                # HU-33: en el periodo más reciente es la matrícula (Nota con todas las notas en null)
                if (anio, semestre_num) != periodo_reciente:
                    errores.append({
                        "fila": fila_num, "campo": "Notas", "mensaje": "Fila sin notas."
                    })
                    continue
                definitiva_final = None

            elif not todas_notas and definitiva_archivo is None:
                # Semestre en curso: cortes parciales, definitiva vacía → aceptar con null
                definitiva_final = None

            else:
                # Cortes parciales pero sí hay definitiva en el archivo
                definitiva_final = definitiva_archivo
                advertencias.append({
                    "fila": fila_num, "campo": "Definitiva", "nivel": "advertencia",
                    "mensaje": "Notas parciales con definitiva en el archivo; se usó la del archivo."
                })

            filas_validas.append({
                "estudiante": estudiante, "curso": curso_obj, "periodo": periodo_obj,
                "definitiva": definitiva_final,
                "corte1": corte1, "corte2": corte2, "corte3": corte3, "examen_final": examen,
            })

        if errores:
            _registrar_bitacora(request, nombre_archivo, 'HISTORIAL', 0, errores, False)
            return JsonResponse({
                "status": "error", "mensaje": "Errores encontrados en el archivo.",
                "errores": errores
            }, status=400)

        creados = 0
        with transaction.atomic():
            nota_objs = [
                Nota(
                    estudiante=fila["estudiante"],
                    curso=fila["curso"],
                    periodo=fila["periodo"],
                    definitiva=fila["definitiva"],
                    corte1=fila["corte1"],
                    corte2=fila["corte2"],
                    corte3=fila["corte3"],
                    examen_final=fila["examen_final"],
                )
                for fila in filas_validas
            ]
            Nota.objects.bulk_create(
                nota_objs,
                batch_size=500,
                update_conflicts=True,
                unique_fields=['estudiante_id', 'curso_id', 'periodo_id'],
                update_fields=['definitiva', 'corte1', 'corte2', 'corte3', 'examen_final'],
            )
            creados = len(nota_objs)

            # Actualizar promedio del estudiante (PPA ponderado, solo notas con definitiva)
            from alertas.evaluacion import actualizar_promedio
            actualizar_promedio(estudiante)

        _registrar_bitacora(request, nombre_archivo, 'HISTORIAL', creados, [], True, advertencias=advertencias)
        registrar_auditoria(
            request.usuario,
            'IMPORTACION',
            f"Importación de HISTORIAL exitosa: {creados} notas registradas desde '{nombre_archivo}'."
        )

        # Recalcular riesgo en segundo plano
        try:
            from alertas.views.alert_generation_views import calcular_y_guardar_riesgo_por_periodos, reprocesar_alertas_completas
            from alertas.alertas_corte import evaluar_cortes_estudiante
            from alertas.tareas import ejecutar_en_segundo_plano
            _codigo = codigo_estudiante
            _est = estudiante
            def _recalcular_bg():
                calcular_y_guardar_riesgo_por_periodos(_est)
                reprocesar_alertas_completas(
                    Estudiante.objects.filter(codigo=_codigo), usuario=None
                )
                evaluar_cortes_estudiante(_est, usuario=None)
            ejecutar_en_segundo_plano(_recalcular_bg)
        except Exception as ae:
            logger.warning("Error en generación automática de alertas tras importar historial de '%s': %s",
                           codigo_estudiante, ae, exc_info=True)

        resp = {"status": "success", "creados": creados}
        if advertencias:
            resp["advertencias"] = advertencias
        return JsonResponse(resp)
    except Exception as e:
        logger.error("Error inesperado al importar historial académico desde '%s': %s",
                     nombre_archivo if 'nombre_archivo' in locals() else 'archivo desconocido',
                     e, exc_info=True)
        if 'nombre_archivo' in locals():
            _registrar_bitacora(request, nombre_archivo, 'HISTORIAL', 0, [{"mensaje": str(e)}], False)
        return JsonResponse({"status": "error", "mensaje": "Error inesperado al procesar la importación. Revisa la bitácora o contacta al administrador."}, status=500)


@csrf_exempt
@requiere_rol(['ADMINISTRADOR'])
def importar_oferta_academica(request):
    # 1. VALIDAR MÉTODO, ARCHIVO Y EXTENSIÓN
    archivo, error = _validar_request_archivo(request, extensiones_permitidas=['.xlsx', '.xls', '.csv'])
    if error:
        return error

    nombre_archivo = archivo.name

    # 2. LEER ARCHIVO
    df, error = _leer_dataframe(archivo, dtype={'Materia': str, 'Código Docente': str})
    if error:
        return error

    # 3. VALIDAR COLUMNAS
    columnas_requeridas = ['Materia', 'Nombre', 'Código Docente', 'Nombre Docente', 'Horario', '# Matriculados']
    error = _validar_columnas(df, columnas_requeridas, nombre_archivo, 'OFERTA', request, 'Oferta Académica')
    if error:
        return error

    # ELIMINAR FILAS VACÍAS
    df = df.dropna(subset=['Materia'])

    errores = []
    registros_validos = []

    # 4. VALIDAR FILAS
    for index, row in df.iterrows():
        fila_num = index + 2
        codigo_materia_grupo = str(row['Materia']).strip()

        match = _RE_MATERIA_GRUPO.match(codigo_materia_grupo)
        if not match:
            errores.append({"fila": fila_num, "campo": "Materia", "valor": codigo_materia_grupo, "mensaje": "Formato inválido."})
            continue

        base_materia = match.group(1)
        grupo = match.group(2)

        if grupo == '':
            errores.append({"fila": fila_num, "campo": "Grupo", "valor": codigo_materia_grupo, "mensaje": "No se encontró grupo."})
            continue

        nombre_materia = str(row['Nombre']).strip()

        codigo_docente = _normalizar_codigo_docente(row['Código Docente'])
        if not codigo_docente:
            continue

        horario = str(row['Horario']).strip()

        try:
            matriculados = int(row['# Matriculados'])
        except (ValueError, TypeError):
            matriculados = 0

        try:
            docente_obj = Docente.objects.get(codigo=codigo_docente)
        except Docente.DoesNotExist:
            errores.append({"fila": fila_num, "campo": "Código Docente", "valor": codigo_docente, "mensaje": "El docente no existe."})
            continue

        registros_validos.append({
            "base": base_materia, "grupo": grupo, "nombre": nombre_materia,
            "docente": docente_obj, "horario": horario, "matriculados": matriculados,
        })

    # CANCELAR SI HAY ERRORES (no se guarda nada)
    if errores:
        _registrar_bitacora(request, nombre_archivo, 'OFERTA', 0, errores, False)
        return JsonResponse({"status": "error", "mensaje": "Se encontraron errores.", "total_errores": len(errores), "errores": errores}, status=400)

    # 5. GUARDAR
    try:
        materias_creadas = materias_actualizadas = cursos_creados = cursos_actualizados = 0

        with transaction.atomic():
            for fila in registros_validos:
                materia_obj, creada = Materia.objects.update_or_create(
                    codigo=fila["base"], defaults={"nombre": fila["nombre"]}
                )
                if creada:
                    materias_creadas += 1
                else:
                    materias_actualizadas += 1

                curso_obj, created = Curso.objects.update_or_create(
                    materia=materia_obj, grupo=fila["grupo"],
                    defaults={"docente": fila["docente"], "horario": fila["horario"], "cantidad_matriculados": fila["matriculados"]},
                )
                if created:
                    cursos_creados += 1
                else:
                    cursos_actualizados += 1

        _registrar_bitacora(request, nombre_archivo, 'OFERTA', len(registros_validos), [], True)
        registrar_auditoria(
            request.usuario, 'IMPORTACION',
            f"Importación de OFERTA ACADÉMICA exitosa: {len(registros_validos)} registros desde '{nombre_archivo}'."
        )
        return JsonResponse({
            "status": "success",
            "mensaje": "Relación de materias/oferta académica procesada correctamente.",
            "materias_creadas": materias_creadas,
            "materias_actualizadas": materias_actualizadas,
            "cursos_creados": cursos_creados,
            "cursos_actualizados": cursos_actualizados,
            "total_procesado": len(registros_validos),
        })

    except Exception as e:
        logger.error("Error inesperado al importar oferta académica desde '%s': %s", nombre_archivo, e, exc_info=True)
        _registrar_bitacora(request, nombre_archivo, 'OFERTA', 0, [{"mensaje": str(e)}], False)
        return JsonResponse({"status": "error", "mensaje": "Error inesperado al procesar la importación. Revisa la bitácora o contacta al administrador."}, status=500)


@csrf_exempt
@requiere_rol(['ADMINISTRADOR'])
def importar_docentes(request):
    from django.db import transaction
    from usuarios.models import Usuario

    # 1. VALIDAR MÉTODO, ARCHIVO Y EXTENSIÓN
    archivo, error = _validar_request_archivo(request, extensiones_permitidas=['.xlsx', '.xls'])
    if error:
        return error

    # 2. LEER ARCHIVO
    df, error = _leer_dataframe(archivo)
    if error:
        _registrar_bitacora(request, archivo.name, 'DOCENTES', 0, [{"mensaje": str(error.content)}], False)
        return error

    # 3. DETECTAR COLUMNAS DINÁMICAMENTE (tolera caracteres especiales)
    col_codigo      = next((c for c in df.columns if 'Docente' in c and ('digo' in c or 'igo' in c)), None)
    col_nombre      = next((c for c in df.columns if 'Nombre' in c and 'Docente' in c), None)
    col_vinculacion = next((c for c in df.columns if 'Vinculaci' in c), None)
    col_depto       = next((c for c in df.columns if 'Departamento' in c), None)
    col_correo_p    = next((c for c in df.columns if 'Personal' in c), None)
    col_correo_i    = next((c for c in df.columns if 'Institucional' in c), None)
    col_celular     = next((c for c in df.columns if 'Celular' in c), None)

    # Validación de firma: evitar confusión con archivos de Cursos u Oferta Académica
    if any(c for c in df.columns if 'Materia' in c or 'Horario' in c):
        err_msg = "El archivo parece ser un reporte de Cursos u Oferta Académica."
        _registrar_bitacora(request, archivo.name, 'DOCENTES', 0, [{"mensaje": err_msg}], False)
        return JsonResponse({
            "status": "error",
            "mensaje": err_msg,
            "error": "Se detectó la columna 'Materia' o 'Horario', las cuales no pertenecen al formato de Docentes.",
        }, status=400)

    if not col_codigo or not col_nombre:
        err_msg = "No se encontraron las columnas de Código o Nombre del docente."
        _registrar_bitacora(request, archivo.name, 'DOCENTES', 0, [{"mensaje": err_msg}], False)
        return JsonResponse({"status": "error", "mensaje": err_msg, "encontradas": list(df.columns)}, status=400)

    # 4. PROCESAR CADA FILA
    creados = actualizados = usuarios_creados = 0
    errores = []

    with transaction.atomic():
        for index, row in df.iterrows():
            fila_num = index + 2

            if index % 50 == 0:
                reset_queries()

            codigo = _normalizar_codigo_docente(row.get(col_codigo))
            if not codigo:
                continue

            nombre               = str(row.get(col_nombre, '')).strip()
            tipo_vinculacion     = str(row.get(col_vinculacion, 'DOCENTE CATEDRA')).strip() if col_vinculacion else 'DOCENTE CATEDRA'
            departamento_nombre  = str(row.get(col_depto, '')).strip() if col_depto else ''
            correo_personal      = row.get(col_correo_p) if col_correo_p else None
            correo_institucional = row.get(col_correo_i) if col_correo_i else None
            celular              = row.get(col_celular)  if col_celular  else None

            if tipo_vinculacion not in ['DOCENTE PLANTA', 'DOCENTE CATEDRA']:
                tipo_vinculacion = 'DOCENTE CATEDRA'

            correo_personal      = str(correo_personal).strip()      if correo_personal      is not None and not pd.isna(correo_personal)      else None
            correo_institucional = str(correo_institucional).strip() if correo_institucional is not None and not pd.isna(correo_institucional) else None
            celular              = str(celular).strip()              if celular              is not None and not pd.isna(celular)              else None
            departamento_nombre  = departamento_nombre if departamento_nombre and departamento_nombre != 'nan' else None

            try:
                correo_usuario = correo_institucional or correo_personal or f"{codigo}@ufps.edu.co"
                usuario_obj, usuario_creado = Usuario.objects.get_or_create(
                    correo=correo_usuario,
                    # Sin contraseña utilizable: el docente define la suya con el enlace de recuperación
                    defaults={"nombre": nombre, "rol": "DOCENTE", "contrasena": make_password(None), "activo": True},
                )
                if usuario_creado:
                    usuarios_creados += 1

                _obj, creado = Docente.objects.update_or_create(
                    codigo=codigo,
                    defaults={
                        "nombre": nombre, "tipo_vinculacion": tipo_vinculacion,
                        "departamento": departamento_nombre, "correo_personal": correo_personal,
                        "correo_institucional": correo_institucional, "celular": celular,
                        "usuario": usuario_obj,
                    },
                )
                if creado:
                    creados += 1
                else:
                    actualizados += 1

            except Exception as e:
                errores.append({"fila": fila_num, "codigo": codigo, "error": str(e)})

    # 5. RETORNAR RESUMEN
    _registrar_bitacora(request, archivo.name, 'DOCENTES', creados + actualizados, errores, not errores)
    if not errores:
        registrar_auditoria(
            request.usuario, 'IMPORTACION',
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


def _leer_fecha_clase(valor):
    """
    Convierte la celda Fecha (fecha de Excel o texto AAAA-MM-DD) a date.
    Devuelve None si el valor está vacío o no tiene un formato válido.
    """
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return None
    if isinstance(valor, datetime):  # incluye pd.Timestamp
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()
    # Excel puede guardar la fecha como número de serie
    if re.fullmatch(r'\d+(\.0+)?', texto):
        try:
            return (pd.Timestamp('1899-12-30') + pd.Timedelta(days=int(float(texto)))).date()
        except (ValueError, OverflowError):
            return None
    # Texto AAAA-MM-DD; se ignora una hora en cero si Excel la agregó
    texto = re.sub(r'[ T]00:00(:00)?$', '', texto)
    try:
        return datetime.strptime(texto, '%Y-%m-%d').date()
    except ValueError:
        return None


def _evaluar_inasistencia_cursos(cursos_afectados, usuario):
    """HU-36: evalúa en segundo plano la inasistencia de los (curso_id, periodo_id) importados."""
    from alertas.alertas_inasistencia import evaluar_inasistencia_curso
    from alertas.tareas import ejecutar_en_segundo_plano

    def _evaluar():
        for curso_id, periodo_id in cursos_afectados:
            try:
                evaluar_inasistencia_curso(curso_id, periodo_id, usuario)
            except Exception as e:
                logger.error("Error al evaluar inasistencia del curso %s: %s", curso_id, e, exc_info=True)

    ejecutar_en_segundo_plano(_evaluar)


@csrf_exempt
@requiere_rol(['ADMINISTRADOR', 'DOCENTE'])
def importar_asistencia(request):
    """
    HU-33: IMPORTAR ASISTENCIA DESDE ARCHIVO

    Columnas: Periodo | Codigo Estudiante | Materia | Fecha | Estado.
    El DOCENTE solo puede importar asistencia de sus cursos. Con cualquier error
    no se guarda nada; sin errores se crean o actualizan los registros.
    """
    archivo, error = _validar_request_archivo(request, extensiones_permitidas=['.csv', '.xlsx', '.xls'])
    if error:
        return error

    nombre_archivo = archivo.name

    df, error = _leer_dataframe(archivo, dtype={'Periodo': str, 'Codigo Estudiante': str, 'Materia': str, 'Estado': str})
    if error:
        return error

    columnas_requeridas = ['Periodo', 'Codigo Estudiante', 'Materia', 'Fecha', 'Estado']
    error = _validar_columnas(df, columnas_requeridas, nombre_archivo, 'ASISTENCIA', request, 'Asistencia')
    if error:
        return error

    df = df.dropna(how='all')
    usuario = request.usuario
    hoy = date.today()

    periodos = {(p.anio, p.semestre): p for p in Periodo.objects.all()}
    cursos = {
        (c.materia_id, c.grupo): c
        for c in Curso.objects.select_related('docente')
    }
    cache_matricula = {}

    errores = []
    filas_validas = []
    vistas = {}

    for index, row in df.iterrows():
        fila_num = index + 2
        fila_con_error = False

        def _error(campo, valor, mensaje):
            errores.append({"fila": fila_num, "campo": campo, "valor": valor, "mensaje": mensaje})

        # --- Periodo ---
        periodo_raw = '' if pd.isna(row['Periodo']) else str(row['Periodo']).strip()
        periodo_match = _RE_PERIODO.match(periodo_raw)
        periodo = periodos.get((int(periodo_match.group(1)), int(periodo_match.group(2)))) if periodo_match else None
        if not periodo:
            _error("Periodo", periodo_raw, "Periodo inválido o no registrado. Se espera 'AAAA-S'.")
            fila_con_error = True

        # --- Estudiante ---
        codigo = '' if pd.isna(row['Codigo Estudiante']) else str(row['Codigo Estudiante']).strip()
        if codigo.endswith('.0'):
            codigo = codigo[:-2]
        if not codigo:
            _error("Codigo Estudiante", codigo, "Código de estudiante vacío.")
            fila_con_error = True

        # --- Curso (código + grupo, como en la oferta) ---
        materia_raw = '' if pd.isna(row['Materia']) else str(row['Materia']).strip()
        match = _RE_MATERIA_GRUPO.match(materia_raw)
        curso = cursos.get((match.group(1), match.group(2))) if match and match.group(2) else None
        if not curso:
            _error("Materia", materia_raw, "El curso no existe.")
            fila_con_error = True
        elif not puede_gestionar_curso(usuario, curso):
            _error("Materia", materia_raw, "El curso no está asignado a usted.")
            fila_con_error = True

        # --- Fecha ---
        fecha_clase = _leer_fecha_clase(row['Fecha'])
        if not fecha_clase:
            _error("Fecha", str(row['Fecha']), "Fecha inválida. Use AAAA-MM-DD.")
            fila_con_error = True
        elif fecha_clase > hoy:
            _error("Fecha", str(fecha_clase), "No se puede registrar asistencia en una fecha futura.")
            fila_con_error = True

        # --- Estado ---
        estado_raw = '' if pd.isna(row['Estado']) else str(row['Estado'])
        estado = normalizar_estado(estado_raw)
        if not estado:
            _error("Estado", estado_raw, "Estado inválido. Use A, F, FJ o ASISTIO, FALTA, FALTA_JUSTIFICADA.")
            fila_con_error = True

        if fila_con_error:
            continue

        # --- Matrícula del estudiante en el curso y periodo ---
        clave_matricula = (curso.id, periodo.id)
        if clave_matricula not in cache_matricula:
            cache_matricula[clave_matricula] = estudiantes_del_curso(curso, periodo)
        if codigo not in cache_matricula[clave_matricula]:
            _error("Codigo Estudiante", codigo, f"El estudiante no está matriculado en {materia_raw} en {periodo}.")
            continue

        # --- Filas repetidas en el archivo ---
        clave = (codigo, curso.id, fecha_clase)
        if clave in vistas:
            _error("Fila", None, f"Fila repetida: mismo estudiante, curso y fecha que la fila {vistas[clave]}.")
            continue
        vistas[clave] = fila_num

        filas_validas.append(Asistencia(
            estudiante_id=codigo,
            curso=curso,
            periodo=periodo,
            fecha_clase=fecha_clase,
            estado=estado,
            registrado_por=usuario,
        ))

    if errores:
        _registrar_bitacora(request, nombre_archivo, 'ASISTENCIA', 0, errores, False)
        return JsonResponse({
            "status": "error",
            "mensaje": "Errores encontrados en el archivo. No se guardó ningún registro.",
            "creados": 0,
            "actualizados": 0,
            "errores": errores,
        }, status=400)

    try:
        with transaction.atomic():
            existentes = set(
                Asistencia.objects.filter(
                    curso_id__in={a.curso_id for a in filas_validas},
                    fecha_clase__in={a.fecha_clase for a in filas_validas},
                ).values_list('estudiante_id', 'curso_id', 'fecha_clase')
            )
            actualizados = sum(
                1 for a in filas_validas if (a.estudiante_id, a.curso_id, a.fecha_clase) in existentes
            )
            creados = len(filas_validas) - actualizados

            Asistencia.objects.bulk_create(
                filas_validas,
                batch_size=500,
                update_conflicts=True,
                unique_fields=['estudiante', 'curso', 'fecha_clase'],
                update_fields=['estado', 'periodo', 'registrado_por', 'fecha_registro'],
            )
            # HU-36: alertas por inasistencia de cada curso afectado, en segundo plano tras confirmar
            cursos_afectados = sorted({(a.curso_id, a.periodo_id) for a in filas_validas})
            transaction.on_commit(lambda: _evaluar_inasistencia_cursos(cursos_afectados, usuario))

        _registrar_bitacora(request, nombre_archivo, 'ASISTENCIA', len(filas_validas), [], True)
        registrar_auditoria(
            usuario, 'IMPORTACION',
            f"Importación de ASISTENCIA exitosa desde '{nombre_archivo}': {creados} creados, {actualizados} actualizados."
        )
        return JsonResponse({
            "status": "success",
            "mensaje": f"Asistencia importada correctamente: {creados} creados, {actualizados} actualizados.",
            "creados": creados,
            "actualizados": actualizados,
            "errores": [],
        })
    except Exception as e:
        logger.error("Error inesperado al guardar asistencia desde '%s': %s", nombre_archivo, e, exc_info=True)
        _registrar_bitacora(request, nombre_archivo, 'ASISTENCIA', 0, [{"mensaje": str(e)}], False)
        return JsonResponse({"status": "error", "mensaje": "Error inesperado al procesar la importación. Revisa la bitácora o contacta al administrador."}, status=500)


@csrf_exempt
@requiere_rol(['ADMINISTRADOR'])
def importar_pensum(request):
    archivo, error = _validar_request_archivo(request, extensiones_permitidas=['.xlsx', '.xls', '.csv'])
    if error:
        return error

    nombre_archivo = archivo.name
    df, error = _leer_dataframe(archivo, dtype={'Codigo': str, 'Equivale A': str})
    if error:
        return error

    # Validar columnas (las requeridas estrictamente)
    columnas_requeridas = ['Codigo', 'Nombre', 'Creditos', 'Tipo']
    error = _validar_columnas(df, columnas_requeridas, nombre_archivo, 'PENSUM', request, 'Pensum')
    if error:
        return error

    # Asegurar columnas opcionales
    if 'Semestre' not in df.columns:
        df['Semestre'] = pd.NA
    if 'Equivale A' not in df.columns:
        df['Equivale A'] = pd.NA

    errores = []
    registros_validos = []
    codigos_en_archivo = set()

    for index, row in df.iterrows():
        fila_num = index + 2
        codigo_raw = str(row.get('Codigo', '')).strip()
        
        if not codigo_raw or codigo_raw.lower() == 'nan':
            errores.append({"fila": fila_num, "campo": "Codigo", "valor": codigo_raw, "mensaje": "Código vacío."})
            continue
            
        try:
            codigo = str(int(float(codigo_raw)))
        except (ValueError, TypeError):
            codigo = codigo_raw

        if codigo in codigos_en_archivo:
            errores.append({"fila": fila_num, "campo": "Codigo", "valor": codigo, "mensaje": "Código repetido en el archivo."})
            continue
        codigos_en_archivo.add(codigo)

        nombre = str(row.get('Nombre', '')).strip()
        if not nombre or nombre.lower() == 'nan':
            errores.append({"fila": fila_num, "campo": "Nombre", "valor": nombre, "mensaje": "Nombre vacío."})
            continue

        creditos_raw = row.get('Creditos')
        try:
            creditos = int(float(creditos_raw))
            if creditos <= 0:
                raise ValueError
        except (ValueError, TypeError):
            errores.append({"fila": fila_num, "campo": "Creditos", "valor": str(creditos_raw), "mensaje": "Debe ser un entero mayor que 0."})
            continue

        semestre_raw = row.get('Semestre')
        semestre = None
        if pd.notna(semestre_raw) and str(semestre_raw).strip() != '' and str(semestre_raw).strip().lower() != 'nan':
            try:
                semestre = int(float(semestre_raw))
                if not (1 <= semestre <= 10):
                    raise ValueError
            except (ValueError, TypeError):
                errores.append({"fila": fila_num, "campo": "Semestre", "valor": str(semestre_raw), "mensaje": "Debe ser un entero entre 1 y 10."})
                continue

        tipo_raw = str(row.get('Tipo', '')).strip().lower()
        tipo_choices_keys = [choice[0] for choice in Materia.TIPO_CHOICES]
        if tipo_raw not in tipo_choices_keys:
            errores.append({"fila": fila_num, "campo": "Tipo", "valor": tipo_raw, "mensaje": f"Tipo no válido. Debe ser uno de: {', '.join(tipo_choices_keys)}."})
            continue

        equivale_raw = str(row.get('Equivale A', '')).strip()
        equivale_a = None
        if equivale_raw and equivale_raw.lower() != 'nan':
            try:
                equivale_a = str(int(float(equivale_raw)))
            except (ValueError, TypeError):
                equivale_a = equivale_raw
            
            if equivale_a == codigo:
                errores.append({"fila": fila_num, "campo": "Equivale A", "valor": equivale_a, "mensaje": "Equivale A igual al propio Código."})
                continue

        registros_validos.append({
            "fila": fila_num,
            "codigo": codigo,
            "nombre": nombre,
            "creditos": creditos,
            "semestre": semestre,
            "tipo": tipo_raw,
            "equivale_a": equivale_a
        })

    # Segunda pasada de validación: comprobar Equivale A existe
    for reg in registros_validos:
        if reg['equivale_a']:
            equiv = reg['equivale_a']
            if equiv not in codigos_en_archivo:
                if not Materia.objects.filter(codigo=equiv).exists():
                    errores.append({"fila": reg['fila'], "campo": "Equivale A", "valor": equiv, "mensaje": "Materia equivalente no existe en archivo ni BD."})

    if errores:
        _registrar_bitacora(request, nombre_archivo, 'PENSUM', 0, errores, False)
        return JsonResponse({"status": "error", "mensaje": "Se encontraron errores.", "total_errores": len(errores), "errores": errores}, status=400)

    try:
        materias_creadas = 0
        materias_actualizadas = 0
        equivalencias_creadas = 0
        
        with transaction.atomic():
            # Primera pasada: crear/actualizar materias
            for reg in registros_validos:
                _, created = Materia.objects.update_or_create(
                    codigo=reg['codigo'],
                    defaults={
                        'nombre': reg['nombre'],
                        'creditos': reg['creditos'],
                        'semestre': reg['semestre'],
                        'tipo': reg['tipo']
                    }
                )
                if created:
                    materias_creadas += 1
                else:
                    materias_actualizadas += 1

            # Segunda pasada: crear equivalencias
            for reg in registros_validos:
                if reg['equivale_a']:
                    materia_pensum = Materia.objects.get(codigo=reg['equivale_a'])
                    materia_equivalente = Materia.objects.get(codigo=reg['codigo'])
                    _, created = EquivalenciaMateria.objects.get_or_create(
                        materia_pensum=materia_pensum,
                        materia_equivalente=materia_equivalente
                    )
                    if created:
                        equivalencias_creadas += 1

        _registrar_bitacora(request, nombre_archivo, 'PENSUM', len(registros_validos), [], True)
        registrar_auditoria(
            request.usuario, 'IMPORTACION',
            f"Importación de PENSUM exitosa: {len(registros_validos)} registros desde '{nombre_archivo}'."
        )
        return JsonResponse({
            "status": "success",
            "mensaje": "Pensum importado correctamente.",
            "materias_creadas": materias_creadas,
            "materias_actualizadas": materias_actualizadas,
            "equivalencias_creadas": equivalencias_creadas,
            "total_procesados": len(registros_validos)
        })

    except Exception as e:
        logger.error("Error inesperado al importar pensum desde '%s': %s", nombre_archivo, e, exc_info=True)
        _registrar_bitacora(request, nombre_archivo, 'PENSUM', 0, [{"mensaje": str(e)}], False)
        return JsonResponse({"status": "error", "mensaje": "Error inesperado al procesar la importación. Revisa la bitácora o contacta al administrador."}, status=500)
