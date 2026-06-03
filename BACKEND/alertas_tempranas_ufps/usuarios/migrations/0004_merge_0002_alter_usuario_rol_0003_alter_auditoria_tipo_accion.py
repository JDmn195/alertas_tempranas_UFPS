# Generated manually to resolve migration conflict between
# 0002_alter_usuario_rol and 0003_alter_auditoria_tipo_accion

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0002_alter_usuario_rol'),
        ('usuarios', '0003_alter_auditoria_tipo_accion'),
    ]

    operations = [
    ]
