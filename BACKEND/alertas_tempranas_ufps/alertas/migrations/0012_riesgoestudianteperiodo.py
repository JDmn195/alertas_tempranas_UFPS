from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academico', '0004_materia_tipo'),
        ('alertas', '0011_intervencion_concluida'),
    ]

    operations = [
        migrations.CreateModel(
            name='RiesgoEstudiantePeriodo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nivel_riesgo', models.CharField(
                    choices=[('high', 'Alto'), ('medium', 'Medio'), ('low', 'Bajo'), ('unknown', 'Sin Dato')],
                    default='unknown', max_length=20
                )),
                ('fecha_calculo', models.DateTimeField(auto_now=True)),
                ('reglas_aplicadas', models.JSONField(default=list)),
                ('estudiante', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='riesgos_por_periodo',
                    to='academico.estudiante',
                )),
                ('periodo', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='riesgos_estudiantes',
                    to='academico.periodo',
                )),
            ],
            options={
                'verbose_name': 'Riesgo Estudiante por Periodo',
                'verbose_name_plural': 'Riesgos Estudiantes por Periodo',
                'db_table': 'riesgo_estudiante_periodo',
                'ordering': ['periodo__anio', 'periodo__semestre'],
            },
        ),
        migrations.AddConstraint(
            model_name='riesgoestudianteperiodo',
            constraint=models.UniqueConstraint(
                fields=['estudiante', 'periodo'],
                name='unique_riesgo_estudiante_periodo',
            ),
        ),
    ]
