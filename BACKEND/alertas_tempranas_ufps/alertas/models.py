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

    TIPO_CHOICES = [
        ('ALERTA', 'Alerta generada'),
        ('RECORDATORIO', 'Recordatorio de seguimiento'),  # HU-30
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
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='ALERTA')
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


class ConfiguracionRecordatorio(models.Model):
    """
    HU-30: Parámetros de los recordatorios de casos sin seguimiento.
    Es una configuración única (fila con pk=1); usar ConfiguracionRecordatorio.obtener().
    Los valores iniciales salen de settings (variables de entorno RECORDATORIOS_*).
    """
    activo = models.BooleanField(default=True)
    # Días sin intervenciones desde que se generó la alerta
    dias_inactividad_alerta = models.PositiveIntegerField(default=7)
    # Días sin actividad (registro, anotación o evidencia) en una intervención no concluida
    dias_inactividad_intervencion = models.PositiveIntegerField(default=15)
    # Si el caso sigue sin seguimiento, cada cuántos días se vuelve a recordar
    dias_entre_recordatorios = models.PositiveIntegerField(default=7)
    # Intentos de envío por recordatorio (1 = sin reintentos)
    max_intentos = models.PositiveSmallIntegerField(default=3)
    # Roles que reciben todos los recordatorios (coordinación)
    roles_destinatarios = models.JSONField(default=list, blank=True)
    # En intervenciones, notificar también al usuario que la registró
    notificar_responsable = models.BooleanField(default=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL, null=True, blank=True)
    # Bloqueo entre procesos: inicio de la ejecución en curso (None = libre)
    ejecutando_desde = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'configuracion_recordatorio'
        verbose_name = 'Configuración de Recordatorios'
        verbose_name_plural = 'Configuración de Recordatorios'

    def __str__(self):
        return (f"Recordatorios: alertas {self.dias_inactividad_alerta} días, "
                f"intervenciones {self.dias_inactividad_intervencion} días")

    @classmethod
    def obtener(cls):
        from django.conf import settings
        config, _ = cls.objects.get_or_create(pk=1, defaults={
            'dias_inactividad_alerta': settings.RECORDATORIOS_DIAS_INACTIVIDAD_ALERTA,
            'dias_inactividad_intervencion': settings.RECORDATORIOS_DIAS_INACTIVIDAD_INTERVENCION,
            'dias_entre_recordatorios': settings.RECORDATORIOS_DIAS_ENTRE_RECORDATORIOS,
            'max_intentos': settings.RECORDATORIOS_MAX_INTENTOS,
            'roles_destinatarios': list(settings.RECORDATORIOS_ROLES_DESTINATARIOS),
        })
        return config


class Recordatorio(models.Model):
    """
    HU-30: Recordatorio enviado a un usuario por un caso (alerta o intervención)
    sin seguimiento. Guarda el estado por canal y cada intento de envío.
    """
    TIPO_CASO_CHOICES = [
        ('ALERTA', 'Alerta sin intervenciones'),
        ('INTERVENCION', 'Intervención sin seguimiento'),
    ]

    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente / en reintento'),
        ('ENVIADO', 'Enviado'),
        ('PARCIAL', 'Enviado parcialmente'),
        ('FALLIDO', 'Fallido'),
        ('CANCELADO', 'Cancelado'),
    ]

    tipo_caso = models.CharField(max_length=20, choices=TIPO_CASO_CHOICES)
    alerta = models.ForeignKey(Alerta, on_delete=models.CASCADE, related_name='recordatorios')
    intervencion = models.ForeignKey(
        Intervencion, on_delete=models.CASCADE, null=True, blank=True, related_name='recordatorios'
    )
    destinatario = models.ForeignKey('usuarios.Usuario', on_delete=models.CASCADE, related_name='recordatorios')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')

    # Momento de la última actividad del caso cuando se detectó; si cambia, hubo seguimiento
    ultima_actividad = models.DateTimeField()
    dias_inactivo = models.PositiveIntegerField(default=0)

    # Estado por canal: {"EMAIL": "exitoso" | "fallido" | "pendiente", "INTERNA": ...}
    canales = models.JSONField(default=dict, blank=True)
    intentos = models.PositiveSmallIntegerField(default=0)
    max_intentos = models.PositiveSmallIntegerField(default=3)
    historial_intentos = models.JSONField(default=list, blank=True)
    ultimo_error = models.TextField(null=True, blank=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_ultimo_intento = models.DateTimeField(null=True, blank=True)
    fecha_envio = models.DateTimeField(null=True, blank=True)
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)
    motivo_cancelacion = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'recordatorio'
        verbose_name = 'Recordatorio'
        verbose_name_plural = 'Recordatorios'
        ordering = ['-fecha_creacion']
        indexes = [models.Index(fields=['estado'])]

    def __str__(self):
        return f"Recordatorio {self.tipo_caso} alerta {self.alerta_id} a {self.destinatario_id} - {self.estado}"
