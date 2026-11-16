"""Búsqueda de texto sin distinguir tildes ni mayúsculas (SDAT-340)."""
import unicodedata


def normalizar_texto(texto):
    """Minúsculas y sin tildes: 'Pérez' -> 'perez'."""
    descompuesto = unicodedata.normalize('NFKD', str(texto or ''))
    return ''.join(c for c in descompuesto if not unicodedata.combining(c)).casefold()


def filtrar_sin_tildes(queryset, termino, campos):
    """
    Filtra el queryset a las filas donde alguno de `campos` contiene `termino`,
    ignorando tildes y mayúsculas. Se compara en Python porque icontains distingue
    tildes en PostgreSQL y unaccent exige una extensión.
    """
    buscado = normalizar_texto(termino).strip()
    if not buscado:
        return queryset
    ids = [
        fila[0]
        for fila in queryset.values_list('pk', *campos)
        if any(buscado in normalizar_texto(valor) for valor in fila[1:])
    ]
    return queryset.filter(pk__in=ids)
