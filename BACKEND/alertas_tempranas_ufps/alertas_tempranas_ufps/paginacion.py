"""SDAT-302: paginación optativa compatible con los consumidores existentes."""
from django.core.paginator import Paginator


def paginar_si_se_pide(request, datos):
    if 'page' not in request.GET and 'page_size' not in request.GET:
        return None
    try:
        numero = max(1, int(request.GET.get('page', 1)))
        tamano = min(100, max(1, int(request.GET.get('page_size', 20))))
    except (ValueError, TypeError):
        numero, tamano = 1, 20
    return Paginator(datos, tamano).get_page(numero)


def metadatos_pagina(pagina):
    if pagina is None:
        return {}
    return {
        'page': pagina.number,
        'page_size': pagina.paginator.per_page,
        'pages': pagina.paginator.num_pages,
        'total': pagina.paginator.count,
    }
