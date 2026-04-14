from django.db import models


class Usuario(models.Model):
    ROL_CHOICES = [
        ('ESTUDIANTE',    'Estudiante'),
        ('DOCENTE',       'Docente'),
        ('ADMINISTRADOR', 'Administrador'),
    ]

    nombre     = models.CharField(max_length=100)
    correo     = models.EmailField(max_length=150, unique=True)
    contrasena = models.CharField(max_length=255)          # almacenar hash, nunca texto plano
    rol        = models.CharField(max_length=30, choices=ROL_CHOICES)
    activo     = models.BooleanField(default=True)

    class Meta:
        db_table         = 'usuario'
        verbose_name     = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f"{self.correo} ({self.rol})"


class Administrador(models.Model):
    usuario      = models.OneToOneField(Usuario, on_delete=models.CASCADE,
                                        related_name='administrador')
    nivel_acceso = models.CharField(max_length=50, default='TOTAL')

    class Meta:
        db_table         = 'administrador'
        verbose_name     = 'Administrador'
        verbose_name_plural = 'Administradores'

    def __str__(self):
        return f"Admin: {self.usuario.correo}"
