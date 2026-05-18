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
