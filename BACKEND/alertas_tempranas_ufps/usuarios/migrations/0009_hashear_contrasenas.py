from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX, identify_hasher, make_password
from django.db import migrations, models


def hashear_contrasenas(apps, schema_editor):
    """
    Convierte las contraseñas guardadas en texto plano a hash.
    Las que coinciden con un valor por defecto predecible (correo, código del
    docente, '00000' o vacía) quedan inutilizables: el usuario deberá definir
    una nueva con el enlace de recuperación.
    """
    Usuario = apps.get_model('usuarios', 'Usuario')
    Docente = apps.get_model('academico', 'Docente')
    codigos = dict(Docente.objects.values_list('usuario_id', 'codigo'))

    for usuario in Usuario.objects.all().iterator():
        actual = usuario.contrasena or ''
        if actual.startswith(UNUSABLE_PASSWORD_PREFIX):
            continue
        try:
            identify_hasher(actual)
            continue  # ya está hasheada
        except ValueError:
            pass

        predecibles = {'', '00000', usuario.correo, codigos.get(usuario.id)}
        usuario.contrasena = make_password(None if actual in predecibles else actual)
        usuario.save(update_fields=['contrasena'])


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0008_alter_auditoria_tipo_accion'),
        ('academico', '0008_merge_asistencia_notas_cortes'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='debe_cambiar_contrasena',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(hashear_contrasenas, migrations.RunPython.noop),
    ]
