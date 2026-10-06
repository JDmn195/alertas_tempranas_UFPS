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
    prioridad = models.IntegerField(default=0)
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
    valor_causa = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    metadata = models.JSONField(default=dict, null=True, blank=True)

    class Meta:
        db_table = 'alerta'
        verbose_name = 'Alerta'
        verbose_name_plural = 'Alertas'

    def __str__(self):
        return f"{self.estudiante.codigo} - {self.estado}"


class RiesgoEstudiante(models.Model):
    NIVEL_CHOICES = [
        ('high', 'Alto'),
        ('medium', 'Medio'),
        ('low', 'Bajo'),
        ('unknown', 'Sin Dato'),
    ]

    estudiante = models.OneToOneField('academico.Estudiante', on_delete=models.CASCADE, related_name='riesgo')
    nivel_riesgo = models.CharField(max_length=20, choices=NIVEL_CHOICES, default='unknown')
    fecha_calculo = models.DateTimeField(auto_now=True)
    reglas_aplicadas = models.JSONField(default=list)

    class Meta:
        db_table = 'riesgo_estudiante'
        verbose_name = 'Riesgo Estudiante'
        verbose_name_plural = 'Riesgos Estudiantes'

    def __str__(self):
        return f"{self.estudiante.codigo} - {self.nivel_riesgo}"


class RiesgoEstudiantePeriodo(models.Model):
    """
    Historial del nivel de riesgo de un estudiante por periodo académico.
    Permite ver la evolución del riesgo a lo largo del tiempo.
    """
    NIVEL_CHOICES = [
        ('high', 'Alto'),
        ('medium', 'Medio'),
        ('low', 'Bajo'),
        ('unknown', 'Sin Dato'),
    ]

    estudiante = models.ForeignKey(
        'academico.Estudiante',
        on_delete=models.CASCADE,
        related_name='riesgos_por_periodo'
    )
    periodo = models.ForeignKey(
        'academico.Periodo',
        on_delete=models.PROTECT,
        related_name='riesgos_estudiantes'
    )
    nivel_riesgo = models.CharField(max_length=20, choices=NIVEL_CHOICES, default='unknown')
    fecha_calculo = models.DateTimeField(auto_now=True)
    reglas_aplicadas = models.JSONField(default=list)

    class Meta:
        db_table = 'riesgo_estudiante_periodo'
        unique_together = ('estudiante', 'periodo')
        verbose_name = 'Riesgo Estudiante por Periodo'
        verbose_name_plural = 'Riesgos Estudiantes por Periodo'
        ordering = ['periodo__anio', 'periodo__semestre']

    def __str__(self):
        return f"{self.estudiante.codigo} - {self.periodo} - {self.nivel_riesgo}"


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
    concluida = models.BooleanField(default=False)

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


class NotificacionHistorial(models.Model):
    CANAL_CHOICES = [
        ('EMAIL', 'Correo Electrónico'),
        ('INTERNA', 'Notificación Interna'),
    ]

    ESTADO_CHOICES = [
        ('exitoso', 'Exitoso'),
        ('fallido', 'Fallido'),
        ('reintento', 'Pendiente de Reintento'),
    ]

    alerta = models.ForeignKey(Alerta, on_delete=models.CASCADE, related_name='historial_notificaciones')
    destinatario = models.CharField(max_length=255)  # Email o ID de usuario
    rol_destinatario = models.CharField(max_length=50)
    canal = models.CharField(max_length=20, choices=CANAL_CHOICES)
    fecha_envio = models.DateTimeField(auto_now_add=True)
    resultado = models.CharField(max_length=20, choices=ESTADO_CHOICES)
    detalle_error = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'notificacion_historial'
        verbose_name = 'Historial de Notificación'
        verbose_name_plural = 'Historial de Notificaciones'
        ordering = ['-fecha_envio']

    def __str__(self):
        return f"{self.canal} a {self.destinatario} - {self.resultado}"


class NotificacionInterna(models.Model):
    usuario = models.ForeignKey('usuarios.Usuario', on_delete=models.CASCADE, related_name='notificaciones_internas')
    alerta = models.ForeignKey(Alerta, on_delete=models.CASCADE)
    mensaje = models.TextField()
    leida = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notificacion_interna'
        verbose_name = 'Notificación Interna'
        verbose_name_plural = 'Notificaciones Internas'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Notificación para {self.usuario.nombre} - {self.leida}"


class EjecucionReevaluacion(models.Model):
    """
    HU-29: Registro de cada ejecución de la re-evaluación periódica del riesgo.
    Cada intento (incluidos los reintentos) queda como una fila independiente,
    enlazada al intento anterior mediante `reintento_de`.
    """
    ORIGEN_CHOICES = [
        ('PROGRAMADA', 'Programada'),
        ('MANUAL', 'Manual'),
    ]

    ESTADO_CHOICES = [
        ('EN_CURSO', 'En curso'),
        ('EXITOSA', 'Exitosa'),
        ('PARCIAL', 'Parcial (con errores)'),
        ('FALLIDA', 'Fallida'),
    ]

    origen = models.CharField(max_length=20, choices=ORIGEN_CHOICES, default='PROGRAMADA')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='EN_CURSO')
    usuario = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL, null=True, blank=True)
    intento = models.PositiveSmallIntegerField(default=1)
    reintento_de = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='reintentos'
    )
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)

    # Alcance: estudiantes y reglas considerados en la ejecución
    alcance = models.JSONField(default=dict, blank=True)

    # Totales
    total_estudiantes = models.IntegerField(default=0)
    procesados = models.IntegerField(default=0)
    total_errores = models.IntegerField(default=0)
    cambios_riesgo = models.IntegerField(default=0)
    alertas_generadas = models.IntegerField(default=0)
    alertas_actualizadas = models.IntegerField(default=0)
    alertas_cerradas = models.IntegerField(default=0)
    estudiantes_por_nivel = models.JSONField(default=dict, blank=True)

    # Detalle (listas acotadas para no crecer sin límite)
    detalle_cambios = models.JSONField(default=list, blank=True)
    errores = models.JSONField(default=list, blank=True)
    mensaje_error = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'ejecucion_reevaluacion'
        verbose_name = 'Ejecución de Re-evaluación'
        verbose_name_plural = 'Ejecuciones de Re-evaluación'
        ordering = ['-fecha_inicio']

    def __str__(self):
        return f"Re-evaluación {self.id} ({self.origen}) intento {self.intento} - {self.estado}"
