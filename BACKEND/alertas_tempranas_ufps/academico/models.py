from django.db import models

class Periodo(models.Model):
    anio = models.IntegerField()
    semestre = models.SmallIntegerField()

    class Meta:
        db_table = 'periodo'
        unique_together = ('anio', 'semestre')
        verbose_name = 'Periodo'
        verbose_name_plural = 'Periodos'

    def __str__(self):
        return f"{self.anio}-{self.semestre}"


class Materia(models.Model):
    codigo = models.CharField(max_length=20, primary_key=True)
    nombre = models.CharField(max_length=150)
    creditos = models.SmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = 'materia'
        verbose_name = 'Materia'
        verbose_name_plural = 'Materias'

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Docente(models.Model):
    codigo = models.CharField(max_length=20, primary_key=True)
    nombre = models.CharField(max_length=150)
    tipo_vinculacion = models.CharField(max_length=50)
    departamento = models.CharField(max_length=100, null=True, blank=True)
    correo_personal = models.CharField(max_length=150, null=True, blank=True)
    correo_institucional = models.CharField(max_length=150, null=True, blank=True)
    celular = models.CharField(max_length=20, null=True, blank=True)
    usuario = models.OneToOneField('usuarios.Usuario', on_delete=models.PROTECT, related_name='docente')


    class Meta:
        db_table = 'docente'
        verbose_name = 'Docente'
        verbose_name_plural = 'Docentes'

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Curso(models.Model):
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, db_column='codigo_materia', related_name='cursos')
    grupo = models.CharField(max_length=2)
    docente = models.ForeignKey(Docente, on_delete=models.PROTECT, db_column='codigo_docente')
    horario = models.CharField(max_length=200, null=True, blank=True)
    cantidad_matriculados = models.IntegerField(default=0)

    class Meta:
        db_table = 'curso'
        unique_together = ('materia', 'grupo')
        verbose_name = 'Curso'
        verbose_name_plural = 'Cursos'

    def __str__(self):
        return f"{self.materia.codigo} - {self.grupo}"


class Estudiante(models.Model):
    codigo = models.CharField(max_length=20, primary_key=True)
    nombre = models.CharField(max_length=150)
    tipo_documento = models.CharField(max_length=30)
    numero_documento = models.CharField(max_length=30, unique=True)
    semestre = models.SmallIntegerField()
    pensum = models.CharField(max_length=20, null=True, blank=True)
    ingreso = models.DateField(null=True, blank=True)
    promedio = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    estado_matricula = models.CharField(max_length=30)
    celular = models.CharField(max_length=20, null=True, blank=True)
    email_personal = models.CharField(max_length=150, null=True, blank=True)
    email_institucional = models.CharField(max_length=150, null=True, blank=True)
    colegio_egresado = models.CharField(max_length=200, null=True, blank=True)
    municipio_nacimiento = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = 'estudiante'
        verbose_name = 'Estudiante'
        verbose_name_plural = 'Estudiantes'

    def __str__(self):
        return self.codigo


class Nota(models.Model):
    periodo = models.ForeignKey(Periodo, on_delete=models.PROTECT)
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, db_column='codigo_estudiante')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    definitiva = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = 'nota'
        verbose_name = 'Nota'
        verbose_name_plural = 'Notas'

    def __str__(self):
        return f"{self.estudiante.codigo} | {self.curso} | {self.definitiva}"


class BitacoraImportacion(models.Model):
    usuario = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL, null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    archivo_nombre = models.CharField(max_length=255)
    tipo = models.CharField(max_length=50)
    total_procesados = models.IntegerField(default=0)
    total_errores = models.IntegerField(default=0)
    detalles_errores = models.JSONField(default=list, blank=True)
    exitoso = models.BooleanField(default=False)

    class Meta:
        db_table = 'bitacora_importacion'
        verbose_name = 'Bitácora de Importación'
        verbose_name_plural = 'Bitácoras de Importación'

    def __str__(self):
        return f"{self.tipo} - {self.fecha} - {self.archivo_nombre}"
