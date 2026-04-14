from django.db import models


# ─────────────────────────────────────────────
# REGLA DE ALERTA
# ─────────────────────────────────────────────
class ReglaAlerta(models.Model):
    NIVEL_CHOICES = [
        (1, 'Bajo'),
        (2, 'Medio'),
        (3, 'Alto'),
    ]

    nombre    = models.CharField(max_length=100)
    nivel     = models.IntegerField(choices=NIVEL_CHOICES)
    condicion = models.CharField(max_length=200)
    umbral    = models.FloatField()
    activo    = models.BooleanField(default=True)

    class Meta:
        db_table         = 'reglaalerta'
        verbose_name     = 'Regla de Alerta'
        verbose_name_plural = 'Reglas de Alerta'

    def __str__(self):
        return self.nombre


# ─────────────────────────────────────────────
# ALERTA
# ─────────────────────────────────────────────
class Alerta(models.Model):
    ESTADO_CHOICES = [
        ('PENDIENTE',  'Pendiente'),
        ('EN_PROCESO', 'En Proceso'),
        ('RESUELTA',   'Resuelta'),
        ('DESCARTADA', 'Descartada'),
    ]

    estudiante       = models.ForeignKey('academico.Estudiante', on_delete=models.CASCADE,
                                         related_name='alertas')
    regla            = models.ForeignKey(ReglaAlerta, on_delete=models.PROTECT)
    tipo             = models.CharField(max_length=50)
    valor            = models.CharField(max_length=20, null=True, blank=True)
    fecha_generacion = models.DateField(auto_now_add=True)
    estado           = models.CharField(max_length=20, choices=ESTADO_CHOICES,
                                        default='PENDIENTE')

    class Meta:
        db_table         = 'alerta'
        verbose_name     = 'Alerta'
        verbose_name_plural = 'Alertas'

    def __str__(self):
        return f"[{self.tipo}] {self.estudiante} — {self.estado}"


# ─────────────────────────────────────────────
# INTERVENCIÓN
# ─────────────────────────────────────────────
class Intervencion(models.Model):
    alerta       = models.ForeignKey(Alerta, on_delete=models.CASCADE,
                                     related_name='intervenciones')
    usuario      = models.ForeignKey('usuarios.Usuario', on_delete=models.PROTECT)
    fecha        = models.DateField(auto_now_add=True)
    tipo         = models.CharField(max_length=80,  null=True, blank=True)
    observaciones = models.TextField(null=True, blank=True)
    evidencia    = models.TextField(null=True, blank=True)
    resultado    = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        db_table         = 'intervencion'
        verbose_name     = 'Intervención'
        verbose_name_plural = 'Intervenciones'

    def __str__(self):
        return f"Intervención #{self.id} → Alerta #{self.alerta_id}"


# ─────────────────────────────────────────────
# NOTIFICACIÓN
# ─────────────────────────────────────────────
class Notificacion(models.Model):
    CANAL_CHOICES = [
        ('EMAIL',    'Email'),
        ('SMS',      'SMS'),
        ('SISTEMA',  'Sistema'),
        ('WHATSAPP', 'WhatsApp'),
    ]

    alerta      = models.ForeignKey(Alerta, on_delete=models.CASCADE,
                                    related_name='notificaciones')
    usuario     = models.ForeignKey('usuarios.Usuario', on_delete=models.PROTECT)
    canal       = models.CharField(max_length=30, choices=CANAL_CHOICES)
    fecha_envio = models.DateTimeField(auto_now_add=True)
    resultado   = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table         = 'notificacion'
        verbose_name     = 'Notificación'
        verbose_name_plural = 'Notificaciones'

    def __str__(self):
        return f"{self.canal} → {self.usuario} ({self.fecha_envio:%Y-%m-%d})"


# ─────────────────────────────────────────────
# BITÁCORA DE IMPORTACIÓN
# ─────────────────────────────────────────────
class BitacoraImportacion(models.Model):
    usuario         = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL,
                                        null=True, blank=True)
    fecha           = models.DateTimeField(auto_now_add=True)
    tipo_reporte    = models.CharField(max_length=60)
    total_registros = models.IntegerField(default=0)
    errores         = models.IntegerField(default=0)
    exitoso         = models.BooleanField(default=True)

    class Meta:
        db_table         = 'bitacoraimportacion'
        verbose_name     = 'Bitácora de Importación'
        verbose_name_plural = 'Bitácoras de Importación'

    def __str__(self):
        return f"{self.tipo_reporte} — {self.fecha:%Y-%m-%d %H:%M}"
