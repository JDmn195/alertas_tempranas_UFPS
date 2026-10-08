from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone

class Usuario(models.Model):
    ROL_CHOICES = [
        ('DOCENTE', 'Docente'),
        ('DIRECTOR', 'Director'),
        ('BIENESTAR', 'Bienestar'),
        ('ADMINISTRADOR', 'Administrador'),
    ]

    nombre = models.CharField(max_length=150)
    correo = models.EmailField(max_length=150, unique=True)
    # Hash de la contraseña (formato de django.contrib.auth.hashers), nunca texto plano
    contrasena = models.CharField(max_length=255)
    rol = models.CharField(max_length=150, default='DOCENTE')
    activo = models.BooleanField(default=True)
    # True cuando la contraseña es temporal (asignada por un admin) y debe cambiarse al entrar
    debe_cambiar_contrasena = models.BooleanField(default=False)
    # Momento del último cambio de contraseña: los JWT emitidos antes dejan de valer
    contrasena_cambiada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'usuario'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f"{self.nombre} ({self.rol})"

    def set_password(self, raw_password):
        self.contrasena = make_password(raw_password)

    def cambiar_contrasena(self, raw_password):
        """Cambio definitivo hecho por el usuario: cierra las sesiones abiertas con la anterior."""
        self.set_password(raw_password)
        self.debe_cambiar_contrasena = False
        self.contrasena_cambiada_en = timezone.now()
        self.save(update_fields=['contrasena', 'debe_cambiar_contrasena', 'contrasena_cambiada_en'])

    def set_unusable_password(self):
        """El usuario solo podrá entrar tras definir su contraseña con el enlace de recuperación."""
        self.contrasena = make_password(None)

    def check_password(self, raw_password):
        def actualizar_hash(raw):
            # Re-hashea si cambió el algoritmo o las iteraciones por defecto
            self.set_password(raw)
            self.save(update_fields=['contrasena'])
        return check_password(raw_password, self.contrasena, actualizar_hash)

class Auditoria(models.Model):
    TIPO_ACCION_CHOICES = [
        ('CREAR_USUARIO', 'Crear Usuario'),
        ('EDITAR_ROL', 'Editar Rol de Usuario'),
        ('DESACTIVAR_USUARIO', 'Desactivar Usuario'),
        ('IMPORTACION', 'Importación de Datos'),
        ('CREAR_REGLA', 'Crear Regla'),
        ('MODIFICAR_REGLA', 'Modificar Regla'),
        ('ACTIVAR_REGLA', 'Activar Regla'),
        ('DESACTIVAR_REGLA', 'Desactivar Regla'),
        ('CERRAR_ALERTA', 'Cerrar Alerta'),
        ('REGISTRAR_INTERVENCION', 'Registrar Intervención'),
        ('CONCLUIR_INTERVENCION', 'Concluir Intervención'),
        ('GENERAR_ALERTAS', 'Generar Alertas'),
        ('LOGIN', 'Inicio de Sesión'),
        ('ACCESO_DENEGADO', 'Acceso Denegado (403)'),
        ('REGISTRO_ASISTENCIA', 'Registro de Asistencia'),  # HU-33
        ('ENVIO_RECORDATORIOS', 'Envío de Recordatorios'),  # HU-30
        ('CONFIGURAR_RECORDATORIOS', 'Configurar Recordatorios'),  # HU-30
        ('REEVALUAR_ALERTAS', 'Reevaluar Alertas'),
        ('RECALCULAR_RIESGO', 'Recalcular Riesgo de Estudiante'),
        ('REEVALUACION_RIESGO', 'Re-evaluación Periódica del Riesgo'),  # HU-29
        ('MIGRAR_RIESGO_PERIODOS', 'Migrar Riesgo por Periodos'),
        ('MODIFICAR_UMBRAL_INASISTENCIA', 'Modificar Umbral de Inasistencia'),  # HU-35
    ]

    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    tipo_accion = models.CharField(max_length=50, choices=TIPO_ACCION_CHOICES)
    detalle = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'auditoria'
        verbose_name = 'Auditoría'
        verbose_name_plural = 'Registros de Auditoría'
        ordering = ['-fecha_hora']

    def __str__(self):
        usuario_nombre = self.usuario.nombre if self.usuario else 'Sistema'
        return f"{self.fecha_hora} - {usuario_nombre} - {self.get_tipo_accion_display()}"
