from django.db import models


# ─────────────────────────────────────────────
# DEPARTAMENTO
# ─────────────────────────────────────────────
class Departamento(models.Model):
    nombre = models.CharField(max_length=120, unique=True)

    class Meta:
        db_table         = 'departamento'
        verbose_name     = 'Departamento'
        verbose_name_plural = 'Departamentos'

    def __str__(self):
        return self.nombre


# ─────────────────────────────────────────────
# PERÍODO ACADÉMICO
# ─────────────────────────────────────────────
class PeriodoAcademico(models.Model):
    SEMESTRE_CHOICES = [(1, 'Primero'), (2, 'Segundo')]

    anio         = models.IntegerField()
    semestre     = models.IntegerField(choices=SEMESTRE_CHOICES)
    fecha_inicio = models.DateField()
    fecha_fin    = models.DateField()

    class Meta:
        db_table         = 'periodoacademico'
        unique_together  = ('anio', 'semestre')
        verbose_name     = 'Período Académico'
        verbose_name_plural = 'Períodos Académicos'

    def __str__(self):
        return f"{self.anio}-{self.semestre}"


# ─────────────────────────────────────────────
# DOCENTE
# ─────────────────────────────────────────────
class Docente(models.Model):
    VINCULACION_CHOICES = [
        ('DOCENTE PLANTA',   'Docente Planta'),
        ('DOCENTE CATEDRA',  'Docente Cátedra'),
    ]

    usuario              = models.OneToOneField(
                               'usuarios.Usuario',
                               on_delete=models.CASCADE,
                               null=True, blank=True,
                               related_name='docente')
    codigo               = models.CharField(max_length=10, unique=True)
    nombre               = models.CharField(max_length=120)
    tipo_vinculacion     = models.CharField(max_length=30, choices=VINCULACION_CHOICES)
    departamento         = models.ForeignKey(Departamento, on_delete=models.SET_NULL,
                                             null=True, blank=True)
    correo_personal      = models.EmailField(max_length=150, null=True, blank=True)
    correo_institucional = models.EmailField(max_length=150, null=True, blank=True)
    celular              = models.CharField(max_length=20,  null=True, blank=True)

    class Meta:
        db_table         = 'docente'
        verbose_name     = 'Docente'
        verbose_name_plural = 'Docentes'

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


# ─────────────────────────────────────────────
# ESTUDIANTE
# ─────────────────────────────────────────────
class Estudiante(models.Model):
    TIPO_DOC_CHOICES = [
        ('TI',  'Tarjeta de Identidad'),
        ('CC',  'Cédula de Ciudadanía'),
        ('CE',  'Cédula de Extranjería'),
        ('PAS', 'Pasaporte'),
    ]
    ESTADO_MATRICULA_CHOICES = [
        ('MATRICULADO',              'Matriculado'),
        ('LIQUIDADO',                'Liquidado'),
        ('ACTIVADO PARA LIQUIDACION','Activado para Liquidación'),
        ('CURSO DE VACACIONES',      'Curso de Vacaciones'),
        ('EXCLUIDO O INACTIVO',      'Excluido o Inactivo'),
        ('PENDIENTE POR PROCESAR',   'Pendiente por Procesar'),
    ]

    usuario              = models.OneToOneField(
                               'usuarios.Usuario',
                               on_delete=models.CASCADE,
                               null=True, blank=True,
                               related_name='estudiante')
    codigo               = models.CharField(max_length=20, unique=True)
    tipo_documento       = models.CharField(max_length=5,  choices=TIPO_DOC_CHOICES,
                                            null=True, blank=True)
    documento            = models.CharField(max_length=20,  null=True, blank=True)
    anio_ingreso         = models.IntegerField(null=True, blank=True)
    semestre_ingreso     = models.IntegerField(null=True, blank=True)
    promedio_acumulado   = models.FloatField(null=True, blank=True)
    semestre_actual      = models.IntegerField(null=True, blank=True)
    pensum               = models.IntegerField(null=True, blank=True)
    estado_matricula     = models.CharField(max_length=40, choices=ESTADO_MATRICULA_CHOICES,
                                            null=True, blank=True)
    celular              = models.CharField(max_length=20,  null=True, blank=True)
    email                = models.EmailField(max_length=150, null=True, blank=True)
    email_institucional  = models.EmailField(max_length=150, null=True, blank=True)
    colegio_egresado     = models.CharField(max_length=120,  null=True, blank=True)
    municipio_nacimiento = models.CharField(max_length=80,   null=True, blank=True)

    class Meta:
        db_table         = 'estudiante'
        verbose_name     = 'Estudiante'
        verbose_name_plural = 'Estudiantes'

    def __str__(self):
        return f"{self.codigo}"


# ─────────────────────────────────────────────
# CURSO
# ─────────────────────────────────────────────
class Curso(models.Model):
    docente          = models.ForeignKey(Docente, on_delete=models.SET_NULL,
                                         null=True, blank=True)
    codigo           = models.CharField(max_length=20, unique=True)
    nombre           = models.CharField(max_length=120)
    horario          = models.CharField(max_length=200, null=True, blank=True)
    num_matriculados = models.IntegerField(default=0)
    creditos         = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table     = 'curso'
        verbose_name = 'Curso'
        verbose_name_plural = 'Cursos'

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


# ─────────────────────────────────────────────
# MATRÍCULA
# ─────────────────────────────────────────────
class Matricula(models.Model):
    ESTADO_CHOICES = [
        ('ACTIVO',    'Activo'),
        ('RETIRADO',  'Retirado'),
        ('CANCELADO', 'Cancelado'),
        ('APROBADO',  'Aprobado'),
        ('REPROBADO', 'Reprobado'),
    ]

    estudiante = models.ForeignKey(Estudiante,      on_delete=models.CASCADE)
    curso      = models.ForeignKey(Curso,            on_delete=models.PROTECT)
    periodo    = models.ForeignKey(PeriodoAcademico, on_delete=models.PROTECT)
    nota       = models.FloatField(null=True, blank=True)
    estado     = models.CharField(max_length=30, choices=ESTADO_CHOICES, default='ACTIVO')

    class Meta:
        db_table        = 'matricula'
        unique_together = ('estudiante', 'curso', 'periodo')
        verbose_name    = 'Matrícula'
        verbose_name_plural = 'Matrículas'

    def __str__(self):
        return f"{self.estudiante} | {self.curso} | {self.periodo}"
