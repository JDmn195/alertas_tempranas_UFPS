import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alertas_tempranas_ufps.settings')
django.setup()

from alertas.models import Regla

rules = [
    {
        'nombre': 'Bajo Promedio - Crítico',
        'tipo': 'PROMEDIO',
        'valor_umbral': 3.0,
        'operador': '<',
        'nivel': 'high',
        'descripcion': 'Estudiantes con promedio por debajo del mínimo de permanencia (UFPS Art. PCE).'
    },
    {
        'nombre': 'Prueba Académica / Advertencia',
        'tipo': 'PROMEDIO',
        'valor_umbral': 3.3,
        'operador': '<',
        'nivel': 'medium',
        'descripcion': 'Estudiantes con promedio en zona de riesgo de prueba académica.'
    },
    {
        'nombre': 'Múltiples Cursos Reprobados',
        'tipo': 'REPROBACION',
        'valor_umbral': 2,
        'operador': '>',
        'nivel': 'high',
        'descripcion': 'Estudiantes que han reprobado más de 2 materias en su historial.'
    },
    {
        'nombre': 'Atraso Curricular Crítico',
        'tipo': 'ATRASO',
        'valor_umbral': 2,
        'operador': '>',
        'nivel': 'high',
        'descripcion': 'Estudiantes con un atraso de más de 2 semestres respecto a su avance teórico.'
    }
]

for rule_data in rules:
    Regla.objects.get_or_create(
        nombre=rule_data['nombre'],
        defaults=rule_data
    )

print("Reglas tradicionales UFPS cargadas exitosamente.")
