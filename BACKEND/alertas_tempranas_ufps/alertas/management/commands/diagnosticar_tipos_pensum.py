"""SDAT-343: diagnóstico de solo lectura de los tipos de materia frente al atraso curricular.

El atraso (alertas/evaluacion.py) cuenta solo materias tipo='linea'. Si la base tiene tipos fuera de
Materia.TIPO_CHOICES (p. ej. OBLIGATORIA o ELECTIVA, que el importador del pensum rechaza), esas
materias no cuentan y la regla puede no dispararse nunca.

Este comando NO modifica datos. Con --respaldo guarda un JSON {codigo: tipo} que sirve para revertir.

Normalización propuesta (fuera de este comando, con aprobación del responsable):
  1. Ejecutar este diagnóstico y el respaldo (--respaldo).
  2. Obtener el pensum oficial con la columna Tipo (linea | profesional | sociohumanistica).
  3. Reimportarlo por la importación de pensum (atómica, upsert por código, no borra materias).
     OBLIGATORIA no se convierte automáticamente en linea: el tipo lo decide el pensum oficial.
  4. Volver a ejecutar este diagnóstico y reevaluar_riesgo.
  Reversión: reponer los tipos desde el JSON de respaldo.
"""
import json
from collections import Counter

from django.core.management.base import BaseCommand

from academico.models import Materia


class Command(BaseCommand):
    help = 'Diagnostica (solo lectura) los tipos de materia incompatibles con el atraso curricular.'

    def add_arguments(self, parser):
        parser.add_argument('--respaldo', help='Ruta de un JSON donde guardar {codigo: tipo} antes de normalizar.')

    def handle(self, *args, **opciones):
        validos = {clave for clave, _ in Materia.TIPO_CHOICES}
        materias = list(Materia.objects.values('codigo', 'nombre', 'tipo', 'semestre'))
        por_tipo = Counter(m['tipo'] for m in materias)

        self.stdout.write(f'Materias: {len(materias)}')
        for tipo, total in sorted(por_tipo.items()):
            marca = '' if tipo in validos else '  <-- NO válido (no cuenta para ATRASO)'
            self.stdout.write(f'  {tipo!r}: {total}{marca}')

        invalidas = [m for m in materias if m['tipo'] not in validos]
        lineas = [m for m in materias if m['tipo'] == 'linea' and m['semestre'] is not None]
        self.stdout.write(f'Materias con tipo no válido: {len(invalidas)}')
        self.stdout.write(f"Materias 'linea' con semestre (base del atraso): {len(lineas)}")
        for m in invalidas[:20]:
            self.stdout.write(f"  {m['codigo']} | {m['nombre']} | tipo={m['tipo']!r} | semestre={m['semestre']}")
        if len(invalidas) > 20:
            self.stdout.write(f'  ... y {len(invalidas) - 20} más')

        if not lineas:
            self.stdout.write(self.style.WARNING(
                'Sin materias linea con semestre: el atraso curricular nunca se dispara.'))
        elif invalidas:
            self.stdout.write(self.style.WARNING(
                'Hay tipos no válidos: corregir con el pensum oficial (ver docstring del comando).'))
        else:
            self.stdout.write(self.style.SUCCESS('Tipos compatibles con el atraso curricular.'))

        if opciones['respaldo']:
            with open(opciones['respaldo'], 'w', encoding='utf-8') as f:
                json.dump({m['codigo']: m['tipo'] for m in materias}, f, ensure_ascii=False, indent=1)
            self.stdout.write(f"Respaldo escrito en {opciones['respaldo']} ({len(materias)} materias).")
