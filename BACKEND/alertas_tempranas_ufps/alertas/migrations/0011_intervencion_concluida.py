# Generated manually - Add concluida field to Intervencion

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('alertas', '0010_notificacionhistorial_notificacioninterna'),
    ]

    operations = [
        migrations.AddField(
            model_name='intervencion',
            name='concluida',
            field=models.BooleanField(default=False),
        ),
    ]
