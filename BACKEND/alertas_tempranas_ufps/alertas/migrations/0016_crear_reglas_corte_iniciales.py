from django.db import migrations

def crear_reglas_corte(apps, schema_editor):
    Regla = apps.get_model('alertas', 'Regla')
    if Regla.objects.filter(tipo='CORTE').exists():
        return

    reglas_corte = [
        {
            'nombre': 'Posible pérdida de la materia: evaluar cancelación',
            'tipo': 'CORTE',
            'valor_umbral': 2.0,
            'operador': '<',
            'nivel': 'medium',
            'prioridad': 10,
            'activo': True,
            'descripcion': 'Se dispara si el estudiante obtiene una nota inferior a 2.0 en el primer corte.',
            'parametros': {
                'clave': 'C1',
                'evalua': 'CORTE',
                'corte': 1,
            }
        },
        {
            'nombre': 'Dos cortes perdidos: no tiene asegurado aprobar',
            'tipo': 'CORTE',
            'valor_umbral': 3.0,
            'operador': '<',
            'nivel': 'high',
            'prioridad': 20,
            'activo': True,
            'descripcion': 'Se dispara si el estudiante pierde el corte 2 (< 3.0) habiendo perdido también el corte 1 (< 3.0).',
            'parametros': {
                'clave': 'C2A',
                'evalua': 'CORTE',
                'corte': 2,
                'corte_previo': 1,
                'operador_previo': '<',
                'umbral_previo': 3.0,
            }
        },
        {
            'nombre': 'Caída de rendimiento en el segundo corte',
            'tipo': 'CORTE',
            'valor_umbral': 3.0,
            'operador': '<',
            'nivel': 'low',
            'prioridad': 10,
            'activo': True,
            'descripcion': 'Se dispara si el estudiante pierde el corte 2 (< 3.0) pero aprobó el corte 1 (>= 3.0).',
            'parametros': {
                'clave': 'C2B',
                'evalua': 'CORTE',
                'corte': 2,
                'corte_previo': 1,
                'operador_previo': '>=',
                'umbral_previo': 3.0,
            }
        },
        {
            'nombre': 'Necesita X en el examen final para aprobar',
            'tipo': 'CORTE',
            'valor_umbral': 4.0,
            'operador': '>',
            'nivel': 'high',
            'prioridad': 30,
            'activo': True,
            'descripcion': 'Con los tres cortes registrados, la nota requerida en el examen final para aprobar supera 4.0.',
            'parametros': {
                'clave': 'C3',
                'evalua': 'NOTA_NECESARIA',
            }
        },
        {
            'nombre': 'Materia perdida: aunque saque 5.0 en el examen no alcanza',
            'tipo': 'CORTE',
            'valor_umbral': 5.0,
            'operador': '>',
            'nivel': 'high',
            'prioridad': 40,
            'activo': True,
            'descripcion': 'Con los tres cortes registrados, la nota requerida en el examen supera 5.0, por lo que matemáticamente no es posible aprobar.',
            'parametros': {
                'clave': 'C4',
                'evalua': 'NOTA_NECESARIA',
            }
        },
    ]

    for data in reglas_corte:
        Regla.objects.create(**data)

def revertir_reglas_corte(apps, schema_editor):
    Regla = apps.get_model('alertas', 'Regla')
    Regla.objects.filter(tipo='CORTE').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('alertas', '0015_regla_tipo_corte_y_parametros'),
    ]

    operations = [
        migrations.RunPython(crear_reglas_corte, revertir_reglas_corte),
    ]
