from django.db import migrations

NOMBRE_REGLA = 'Inasistencia superior al umbral'


def crear_regla_inasistencia(apps, schema_editor):
    Regla = apps.get_model('alertas', 'Regla')
    if Regla.objects.filter(tipo='INASISTENCIA').exists():
        return

    Regla.objects.create(
        nombre=NOMBRE_REGLA,
        tipo='INASISTENCIA',
        valor_umbral=20,
        operador='>',
        nivel='high',
        activo=True,
        descripcion=(
            'Umbral general de inasistencia: se considera en riesgo al estudiante cuyo '
            'porcentaje de faltas sin justificar en un curso supera este valor, una vez '
            'registradas al menos min_clases clases. Cada curso puede tener su propio umbral.'
        ),
        parametros={'min_clases': 4},
    )


def eliminar_regla_inasistencia(apps, schema_editor):
    Regla = apps.get_model('alertas', 'Regla')
    Regla.objects.filter(tipo='INASISTENCIA', nombre=NOMBRE_REGLA).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('alertas', '0017_regla_tipo_inasistencia'),
    ]

    operations = [
        migrations.RunPython(crear_regla_inasistencia, eliminar_regla_inasistencia),
    ]
