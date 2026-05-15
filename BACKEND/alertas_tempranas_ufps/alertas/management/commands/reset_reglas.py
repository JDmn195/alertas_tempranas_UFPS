from django.core.management.base import BaseCommand
from alertas.models import Regla, Alerta
from django.db import transaction

class Command(BaseCommand):
    help = 'Borra todas las alertas y reglas, y crea 9 reglas coherentes base.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Iniciando reset de reglas y alertas...'))
        
        with transaction.atomic():
            # 1. Borrar alertas (esto borra en cascada intervenciones, evidencias, anotaciones)
            num_alertas, _ = Alerta.objects.all().delete()
            self.stdout.write(f'Se eliminaron {num_alertas} alertas.')

            # 2. Borrar reglas
            num_reglas, _ = Regla.objects.all().delete()
            self.stdout.write(f'Se eliminaron {num_reglas} reglas.')

            # 3. Crear reglas coherentes
            reglas_base = [
                # PROMEDIO
                {'nombre': 'Promedio Crítico', 'tipo': 'PROMEDIO', 'operador': '<', 'valor_umbral': 2.5, 'nivel': 'high', 'prioridad': 30},
                {'nombre': 'Promedio Bajo', 'tipo': 'PROMEDIO', 'operador': '<', 'valor_umbral': 3.0, 'nivel': 'medium', 'prioridad': 20},
                {'nombre': 'Promedio En Riesgo', 'tipo': 'PROMEDIO', 'operador': '<', 'valor_umbral': 3.5, 'nivel': 'low', 'prioridad': 10},
                
                # REPROBACION
                {'nombre': 'Múltiples Reprobadas Crítico', 'tipo': 'REPROBACION', 'operador': '>=', 'valor_umbral': 4, 'nivel': 'high', 'prioridad': 30},
                {'nombre': 'Reprobadas Moderado', 'tipo': 'REPROBACION', 'operador': '>=', 'valor_umbral': 2, 'nivel': 'medium', 'prioridad': 20},
                {'nombre': 'Una Reprobada', 'tipo': 'REPROBACION', 'operador': '>=', 'valor_umbral': 1, 'nivel': 'low', 'prioridad': 10},
                
                # ATRASO
                {'nombre': 'Atraso Severo', 'tipo': 'ATRASO', 'operador': '>=', 'valor_umbral': 3, 'nivel': 'high', 'prioridad': 30},
                {'nombre': 'Atraso Moderado', 'tipo': 'ATRASO', 'operador': '>=', 'valor_umbral': 2, 'nivel': 'medium', 'prioridad': 20},
                {'nombre': 'Atraso Leve', 'tipo': 'ATRASO', 'operador': '>=', 'valor_umbral': 1, 'nivel': 'low', 'prioridad': 10},
            ]

            for r in reglas_base:
                Regla.objects.create(**r)
            
            self.stdout.write(self.style.SUCCESS('Se crearon 9 reglas coherentes exitosamente.'))
