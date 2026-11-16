"""SDAT-343: el diagnóstico de tipos de materia no modifica datos y detecta tipos incompatibles."""
import json
import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from academico.models import Materia


def _diagnosticar(**opciones):
    salida = StringIO()
    call_command('diagnosticar_tipos_pensum', stdout=salida, **opciones)
    return salida.getvalue()


class DiagnosticoTiposPensumTests(TestCase):
    def test_detecta_tipos_no_validos_y_no_modifica_datos(self):
        Materia.objects.create(codigo='A1', nombre='Cálculo', semestre=1, tipo='OBLIGATORIA')
        Materia.objects.create(codigo='A2', nombre='Física', semestre=2, tipo='ELECTIVA')
        texto = _diagnosticar()
        self.assertIn('Materias con tipo no válido: 2', texto)
        self.assertIn('el atraso curricular nunca se dispara', texto)
        self.assertEqual(set(Materia.objects.values_list('tipo', flat=True)), {'OBLIGATORIA', 'ELECTIVA'})

    def test_tipos_compatibles(self):
        Materia.objects.create(codigo='A1', nombre='Cálculo', semestre=1, tipo='linea')
        Materia.objects.create(codigo='A2', nombre='Ética', semestre=2, tipo='sociohumanistica')
        self.assertIn('Tipos compatibles', _diagnosticar())

    def test_respaldo_guarda_codigo_y_tipo(self):
        Materia.objects.create(codigo='A1', nombre='Cálculo', semestre=1, tipo='OBLIGATORIA')
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, 'respaldo.json')
            _diagnosticar(respaldo=ruta)
            with open(ruta, encoding='utf-8') as f:
                self.assertEqual(json.load(f), {'A1': 'OBLIGATORIA'})
