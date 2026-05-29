"""
Tests unitarios para los helpers de import_views.py

Cubren las funciones:
  - _normalizar_codigo_docente
  - _validar_tamano_archivo
  - _validar_request_archivo
  - _leer_dataframe
  - _validar_columnas

No requieren base de datos (no heredan de TestCase con DB).
Se ejecutan con:
    python manage.py test academico.tests_import_helpers
"""

import io
import json
import pandas as pd
from unittest.mock import MagicMock, patch
from django.test import TestCase, RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile

from academico.views.import_views import (
    _normalizar_codigo_docente,
    _validar_tamano_archivo,
    _validar_request_archivo,
    _leer_dataframe,
    _validar_columnas,
    MAX_IMPORT_FILE_SIZE,
    _MAX_MB,
)


# ==============================================================================
# _normalizar_codigo_docente
# ==============================================================================

class NormalizarCodigoDocenteTests(TestCase):
    """Casos para la normalización de códigos de docente a 5 dígitos."""

    def test_entero_corto_rellena_ceros(self):
        self.assertEqual(_normalizar_codigo_docente(1713), "01713")

    def test_float_con_decimal_cero(self):
        """1713.0 debe tratarse igual que 1713."""
        self.assertEqual(_normalizar_codigo_docente(1713.0), "01713")

    def test_string_con_decimal_cero(self):
        self.assertEqual(_normalizar_codigo_docente("1713.0"), "01713")

    def test_string_ya_con_ceros(self):
        self.assertEqual(_normalizar_codigo_docente("01714"), "01714")

    def test_string_sin_ceros(self):
        self.assertEqual(_normalizar_codigo_docente("1715"), "01715")

    def test_cinco_digitos_exactos(self):
        self.assertEqual(_normalizar_codigo_docente("12345"), "12345")

    def test_codigo_con_comilla_inicial(self):
        """Algunos Excel exportan códigos con comilla inicial: '01713"""
        self.assertEqual(_normalizar_codigo_docente("'01713"), "01713")

    def test_nan_float_devuelve_none(self):
        import math
        self.assertIsNone(_normalizar_codigo_docente(float('nan')))

    def test_string_nan_devuelve_none(self):
        self.assertIsNone(_normalizar_codigo_docente("nan"))

    def test_string_vacio_devuelve_none(self):
        self.assertIsNone(_normalizar_codigo_docente(""))

    def test_string_solo_espacios_devuelve_none(self):
        self.assertIsNone(_normalizar_codigo_docente("   "))

    def test_none_devuelve_none(self):
        # pd.isna(None) es True
        self.assertIsNone(_normalizar_codigo_docente(None))

    def test_decimal_no_cero_se_preserva(self):
        """1713.5 no tiene decimal irrelevante, debe convertirse igual."""
        # int(float("1713.5")) = 1713 → "01713"
        self.assertEqual(_normalizar_codigo_docente("1713.5"), "01713")

    def test_codigo_largo_no_rellena(self):
        """Códigos de 6+ dígitos no deben truncarse."""
        self.assertEqual(_normalizar_codigo_docente(123456), "123456")


# ==============================================================================
# _validar_tamano_archivo
# ==============================================================================

def _make_fake_file(name, size_bytes):
    """Crea un mock de archivo con .name y .size."""
    f = MagicMock()
    f.name = name
    f.size = size_bytes
    return f


class ValidarTamanoArchivoTests(TestCase):
    """Casos para la validación de tamaño de archivos."""

    def test_archivo_dentro_del_limite_devuelve_none(self):
        archivo = _make_fake_file("datos.xlsx", 1 * 1024 * 1024)  # 1 MB
        self.assertIsNone(_validar_tamano_archivo(archivo))

    def test_archivo_exactamente_en_el_limite_devuelve_none(self):
        archivo = _make_fake_file("datos.xlsx", MAX_IMPORT_FILE_SIZE)
        self.assertIsNone(_validar_tamano_archivo(archivo))

    def test_archivo_un_byte_sobre_el_limite_devuelve_error(self):
        archivo = _make_fake_file("datos.xlsx", MAX_IMPORT_FILE_SIZE + 1)
        response = _validar_tamano_archivo(archivo)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 413)

    def test_respuesta_413_contiene_nombre_archivo(self):
        archivo = _make_fake_file("enorme.xlsx", MAX_IMPORT_FILE_SIZE + 1)
        response = _validar_tamano_archivo(archivo)
        body = json.loads(response.content)
        self.assertIn("enorme.xlsx", body["error"])

    def test_respuesta_413_menciona_limite_en_mb(self):
        archivo = _make_fake_file("enorme.xlsx", MAX_IMPORT_FILE_SIZE + 1)
        response = _validar_tamano_archivo(archivo)
        body = json.loads(response.content)
        self.assertIn(str(_MAX_MB), body["error"])

    def test_archivo_vacio_devuelve_none(self):
        """Un archivo de 0 bytes es válido en tamaño (la validación de contenido es otra)."""
        archivo = _make_fake_file("vacio.xlsx", 0)
        self.assertIsNone(_validar_tamano_archivo(archivo))


# ==============================================================================
# _validar_request_archivo
# ==============================================================================

class ValidarRequestArchivoTests(TestCase):
    """Casos para la validación completa de request + archivo."""

    def setUp(self):
        self.factory = RequestFactory()

    def _make_request(self, method='POST', file_name='datos.xlsx',
                      file_size=1024, file_content=b'x'):
        """Crea un request con un archivo adjunto."""
        uploaded = SimpleUploadedFile(file_name, file_content * file_size)
        if method == 'POST':
            request = self.factory.post('/', {'file': uploaded})
        else:
            request = self.factory.get('/')
        return request

    def test_get_devuelve_405(self):
        request = self.factory.get('/')
        archivo, error = _validar_request_archivo(request)
        self.assertIsNone(archivo)
        self.assertEqual(error.status_code, 405)

    def test_post_sin_archivo_devuelve_400(self):
        request = self.factory.post('/', {})
        archivo, error = _validar_request_archivo(request)
        self.assertIsNone(archivo)
        self.assertEqual(error.status_code, 400)

    def test_post_con_archivo_valido_devuelve_archivo(self):
        request = self._make_request()
        archivo, error = _validar_request_archivo(request)
        self.assertIsNotNone(archivo)
        self.assertIsNone(error)

    def test_extension_no_permitida_devuelve_400(self):
        request = self._make_request(file_name='datos.txt')
        archivo, error = _validar_request_archivo(
            request, extensiones_permitidas=['.xlsx', '.csv']
        )
        self.assertIsNone(archivo)
        self.assertEqual(error.status_code, 400)
        body = json.loads(error.content)
        self.assertIn(".txt", body["error"])

    def test_extension_permitida_pasa(self):
        request = self._make_request(file_name='datos.csv')
        archivo, error = _validar_request_archivo(
            request, extensiones_permitidas=['.xlsx', '.csv']
        )
        self.assertIsNotNone(archivo)
        self.assertIsNone(error)

    def test_sin_restriccion_de_extension_cualquier_archivo_pasa(self):
        request = self._make_request(file_name='datos.txt')
        archivo, error = _validar_request_archivo(request)
        self.assertIsNotNone(archivo)
        self.assertIsNone(error)

    def test_archivo_demasiado_grande_devuelve_413(self):
        # Crear un archivo que supere el límite
        big_content = b'x' * (MAX_IMPORT_FILE_SIZE + 1)
        uploaded = SimpleUploadedFile('grande.xlsx', big_content)
        request = self.factory.post('/', {'file': uploaded})
        archivo, error = _validar_request_archivo(request)
        self.assertIsNone(archivo)
        self.assertEqual(error.status_code, 413)


# ==============================================================================
# _leer_dataframe
# ==============================================================================

def _make_excel_bytes(data: dict) -> bytes:
    """Genera bytes de un Excel a partir de un dict."""
    output = io.BytesIO()
    pd.DataFrame(data).to_excel(output, index=False)
    output.seek(0)
    return output.read()


def _make_csv_bytes(data: dict) -> bytes:
    output = io.BytesIO()
    pd.DataFrame(data).to_csv(output, index=False)
    output.seek(0)
    return output.read()


class LeerDataframeTests(TestCase):
    """Casos para la lectura de archivos Excel y CSV."""

    def test_lee_excel_correctamente(self):
        content = _make_excel_bytes({"Nombre": ["Ana"], "Codigo": ["001"]})
        archivo = SimpleUploadedFile("datos.xlsx", content)
        df, error = _leer_dataframe(archivo)
        self.assertIsNone(error)
        self.assertIn("Nombre", df.columns)
        self.assertEqual(df.iloc[0]["Nombre"], "Ana")

    def test_lee_csv_correctamente(self):
        content = _make_csv_bytes({"Nombre": ["Luis"], "Codigo": ["002"]})
        archivo = SimpleUploadedFile("datos.csv", content)
        df, error = _leer_dataframe(archivo)
        self.assertIsNone(error)
        self.assertIn("Nombre", df.columns)

    def test_columnas_se_limpian_de_espacios(self):
        """Columnas con espacios al inicio/fin deben normalizarse."""
        content = _make_excel_bytes({"  Nombre  ": ["Ana"], " Codigo ": ["001"]})
        archivo = SimpleUploadedFile("datos.xlsx", content)
        df, error = _leer_dataframe(archivo)
        self.assertIsNone(error)
        self.assertIn("Nombre", df.columns)
        self.assertIn("Codigo", df.columns)

    def test_archivo_corrupto_devuelve_error_400(self):
        archivo = SimpleUploadedFile("corrupto.xlsx", b"esto no es un excel")
        df, error = _leer_dataframe(archivo)
        self.assertIsNone(df)
        self.assertEqual(error.status_code, 400)
        body = json.loads(error.content)
        self.assertIn("Error leyendo archivo", body["error"])

    def test_dtype_se_aplica_en_csv(self):
        """El parámetro dtype debe pasarse al lector."""
        content = _make_csv_bytes({"Codigo": [1713, 1714]})
        archivo = SimpleUploadedFile("datos.csv", content)
        df, error = _leer_dataframe(archivo, dtype={"Codigo": str})
        self.assertIsNone(error)
        # Con dtype=str el valor debe ser string, no int
        self.assertIsInstance(df.iloc[0]["Codigo"], str)


# ==============================================================================
# _validar_columnas
# ==============================================================================

class ValidarColumnasTests(TestCase):
    """Casos para la validación de columnas requeridas en un DataFrame."""

    def _make_request(self):
        factory = RequestFactory()
        request = factory.post('/')
        # _validar_columnas llama a _registrar_bitacora internamente;
        # lo mockeamos para aislar la lógica de validación de la BD.
        request.usuario = None
        request.POST = {}
        return request

    @patch('academico.views.import_views._registrar_bitacora')
    def test_todas_las_columnas_presentes_devuelve_none(self, mock_bitacora):
        df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
        result = _validar_columnas(df, ["A", "B"], "archivo.xlsx", "TEST", self._make_request(), "Formato X")
        self.assertIsNone(result)
        mock_bitacora.assert_not_called()

    @patch('academico.views.import_views._registrar_bitacora')
    def test_columna_faltante_devuelve_400(self, mock_bitacora):
        df = pd.DataFrame({"A": [1]})
        result = _validar_columnas(df, ["A", "B"], "archivo.xlsx", "TEST", self._make_request(), "Formato X")
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 400)
        mock_bitacora.assert_called_once()

    @patch('academico.views.import_views._registrar_bitacora')
    def test_respuesta_incluye_columnas_faltantes(self, mock_bitacora):
        df = pd.DataFrame({"A": [1]})
        result = _validar_columnas(df, ["A", "B", "C"], "archivo.xlsx", "TEST", self._make_request(), "Formato X")
        body = json.loads(result.content)
        self.assertIn("B", body["columnas_faltantes"])
        self.assertIn("C", body["columnas_faltantes"])

    @patch('academico.views.import_views._registrar_bitacora')
    def test_respuesta_incluye_columnas_encontradas(self, mock_bitacora):
        df = pd.DataFrame({"A": [1], "Z": [9]})
        result = _validar_columnas(df, ["A", "B"], "archivo.xlsx", "TEST", self._make_request(), "Formato X")
        body = json.loads(result.content)
        self.assertIn("A", body["columnas_encontradas"])
        self.assertIn("Z", body["columnas_encontradas"])

    @patch('academico.views.import_views._registrar_bitacora')
    def test_mensaje_incluye_nombre_formato(self, mock_bitacora):
        df = pd.DataFrame({"X": [1]})
        result = _validar_columnas(df, ["A"], "archivo.xlsx", "TEST", self._make_request(), "Oferta Académica")
        body = json.loads(result.content)
        self.assertIn("Oferta Académica", body["mensaje"])

    @patch('academico.views.import_views._registrar_bitacora')
    def test_dataframe_vacio_con_columnas_correctas_devuelve_none(self, mock_bitacora):
        """Un DataFrame sin filas pero con las columnas correctas es válido."""
        df = pd.DataFrame(columns=["A", "B"])
        result = _validar_columnas(df, ["A", "B"], "archivo.xlsx", "TEST", self._make_request(), "Formato X")
        self.assertIsNone(result)
        mock_bitacora.assert_not_called()
