from django.db import models

class Regla(models.Model):
    TIPO_CHOICES = [
        ('PROMEDIO', 'Promedio Acumulado'),
        ('REPROBACION', 'Número de Materias Reprobadas'),
        ('ATRASO', 'Atraso Curricular'),
    ]

    NIVEL_CHOICES = [
        ('high', 'Alto'),
        ('medium', 'Medio'),
        ('low', 'Bajo'),
    ]

    OPERADOR_CHOICES = [
        ('<', 'Menor que'),
        ('>', 'Mayor que'),
        ('<=', 'Menor o igual que'),
        ('>=', 'Mayor o igual que'),
        ('==', 'Igual que'),
    ]

    nombre = models.CharField(max_length=150)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='PROMEDIO')
    valor_umbral = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    operador = models.CharField(max_length=5, choices=OPERADOR_CHOICES, default='<')
    nivel = models.CharField(max_length=20, choices=NIVEL_CHOICES, default='medium')
    activo = models.BooleanField(default=True)
    descripcion = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'regla'
        verbose_name = 'Regla'
        verbose_name_plural = 'Reglas'

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"


class Alerta(models.Model):
    estudiante = models.ForeignKey('academico.Estudiante', on_delete=models.CASCADE, db_column='codigo_estudiante')
    regla = models.ForeignKey(Regla, on_delete=models.PROTECT)
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=30)

    class Meta:
        db_table = 'alerta'
        verbose_name = 'Alerta'
        verbose_name_plural = 'Alertas'

    def __str__(self):
        return f"{self.estudiante.codigo} - {self.estado}"


class Intervencion(models.Model):
    TIPO_CHOICES = [
        ('TUTORIA', 'Tutoría'),
        ('CITACION', 'Citación'),
        ('REMISION', 'Remisión'),
    ]

    alerta = models.ForeignKey(Alerta, on_delete=models.CASCADE)
    usuario = models.ForeignKey('usuarios.Usuario', on_delete=models.PROTECT)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    fecha = models.DateTimeField(auto_now_add=True)
    observaciones = models.TextField(null=True, blank=True)
    evidencia = models.CharField(max_length=300, null=True, blank=True)
    resultado = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = 'intervencion'
        verbose_name = 'Intervención'
        verbose_name_plural = 'Intervenciones'

    def __str__(self):
        return f"Intervención {self.tipo} a alerta {self.alerta_id}"


class Evidencia(models.Model):
    intervencion = models.ForeignKey(Intervencion, on_delete=models.CASCADE, related_name='evidencias')
    archivo_url = models.URLField(max_length=500)
    nombre_archivo = models.CharField(max_length=255)
    tipo_archivo = models.CharField(max_length=100, null=True, blank=True)
    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'evidencia'
        verbose_name = 'Evidencia'
        verbose_name_plural = 'Evidencias'

    def __str__(self):
        return f"Evidencia: {self.nombre_archivo} de Intervención {self.intervencion_id}"


class AnotacionIntervencion(models.Model):
    intervencion = models.ForeignKey(Intervencion, on_delete=models.CASCADE, related_name='anotaciones')
    usuario = models.ForeignKey('usuarios.Usuario', on_delete=models.PROTECT)
    texto = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'anotacion_intervencion'
        verbose_name = 'Anotación'
        verbose_name_plural = 'Anotaciones'
        ordering = ['-fecha']

    def __str__(self):
        return f"Anotación de {self.usuario.nombre} en Intervención {self.intervencion_id}"
