from django.db import models

class Usuario(models.Model):
    ROL_CHOICES = [
        ('DOCENTE', 'Docente'),
        ('DIRECTOR', 'Director'),
        ('BIENESTAR', 'Bienestar'),
        ('ADMINISTRADOR', 'Administrador'),
    ]

    nombre = models.CharField(max_length=150)
    correo = models.EmailField(max_length=150, unique=True)
    contrasena = models.CharField(max_length=255)
    rol = models.CharField(max_length=20, choices=ROL_CHOICES)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'usuario'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f"{self.nombre} ({self.rol})"

class Auditoria(models.Model):
    TIPO_ACCION_CHOICES = [
        ('CREAR_USUARIO', 'Crear Usuario'),
        ('EDITAR_ROL', 'Editar Rol de Usuario'),
        ('DESACTIVAR_USUARIO', 'Desactivar Usuario'),
        ('IMPORTACION', 'Importación de Datos'),
        ('CREAR_REGLA', 'Crear Regla'),
        ('MODIFICAR_REGLA', 'Modificar Regla'),
        ('DESACTIVAR_REGLA', 'Desactivar Regla'),
        ('CERRAR_ALERTA', 'Cerrar Alerta'),
        ('REGISTRAR_INTERVENCION', 'Registrar Intervención'),
        ('CONCLUIR_INTERVENCION', 'Concluir Intervención'),
        ('GENERAR_ALERTAS', 'Generar Alertas'),
        ('LOGIN', 'Inicio de Sesión'),
        ('ACCESO_DENEGADO', 'Acceso Denegado (403)'),
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
