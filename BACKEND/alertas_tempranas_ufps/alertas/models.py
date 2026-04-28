from django.db import models

class Regla(models.Model):
    nombre = models.CharField(max_length=150)
    nivel = models.CharField(max_length=30)
    condicion = models.TextField()

    class Meta:
        db_table = 'regla'
        verbose_name = 'Regla'
        verbose_name_plural = 'Reglas'

    def __str__(self):
        return self.nombre


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
    alerta = models.ForeignKey(Alerta, on_delete=models.CASCADE)
    usuario = models.ForeignKey('usuarios.Usuario', on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)
    observaciones = models.TextField(null=True, blank=True)
    evidencia = models.CharField(max_length=300, null=True, blank=True)
    resultado = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = 'intervencion'
        verbose_name = 'Intervención'
        verbose_name_plural = 'Intervenciones'

    def __str__(self):
        return f"Intervención a alerta {self.alerta_id}"
