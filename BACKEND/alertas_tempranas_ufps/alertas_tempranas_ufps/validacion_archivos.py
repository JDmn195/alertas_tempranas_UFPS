"""Comprueba el contenido de los archivos recibidos antes de procesarlos."""

import zipfile


FIRMAS = {
    '.pdf': lambda b: b.startswith(b'%PDF-'),
    '.png': lambda b: b.startswith(b'\x89PNG\r\n\x1a\n'),
    '.jpg': lambda b: b.startswith(b'\xff\xd8\xff'),
    '.jpeg': lambda b: b.startswith(b'\xff\xd8\xff'),
    '.gif': lambda b: b.startswith((b'GIF87a', b'GIF89a')),
    '.webp': lambda b: b.startswith(b'RIFF') and b[8:12] == b'WEBP',
    '.xls': lambda b: b.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'),
}


def firma_valida(archivo, extension):
    """Valida la firma sin cambiar la posición de lectura del archivo."""
    posicion = archivo.tell()
    try:
        archivo.seek(0)
        cabecera = archivo.read(4096)
        if extension == '.csv':
            return bool(cabecera) and b'\x00' not in cabecera
        if extension == '.xlsx':
            if not cabecera.startswith(b'PK\x03\x04'):
                return False
            archivo.seek(0)
            with zipfile.ZipFile(archivo) as libro:
                entradas = libro.infolist()
                nombres = {entrada.filename for entrada in entradas}
                return (
                    len(entradas) <= 2000
                    and sum(entrada.file_size for entrada in entradas) <= 100 * 1024 * 1024
                    and {'[Content_Types].xml', 'xl/workbook.xml'} <= nombres
                )
        comprobador = FIRMAS.get(extension)
        return comprobador(cabecera) if comprobador else False
    except (OSError, ValueError, zipfile.BadZipFile):
        return False
    finally:
        archivo.seek(posicion)
