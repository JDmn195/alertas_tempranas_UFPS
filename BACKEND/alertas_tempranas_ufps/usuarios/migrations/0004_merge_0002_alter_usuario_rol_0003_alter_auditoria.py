from django.db import migrations


class Migration(migrations.Migration):
    """
    Merge migration: resuelve el conflicto entre las dos ramas de 0002.
    - 0002_alter_usuario_rol (rama A): solo cambia el campo rol
    - 0003_alter_auditoria_tipo_accion (rama B): depende de 0002_alter_usuario_rol_auditoria
    """

    dependencies = [
        ('usuarios', '0002_alter_usuario_rol'),
        ('usuarios', '0003_alter_auditoria_tipo_accion'),
    ]

    operations = [
    ]
