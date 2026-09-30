from django.contrib import admin
from .models import Materia, Curso, Estudiante, Nota, Periodo, Docente, EquivalenciaMateria, Asistencia



@admin.register(EquivalenciaMateria)
class EquivalenciaMateriaAdmin(admin.ModelAdmin):
    list_display = ('materia_pensum', 'materia_equivalente')
    search_fields = (
        'materia_pensum__codigo', 'materia_pensum__nombre',
        'materia_equivalente__codigo', 'materia_equivalente__nombre',
    )
    autocomplete_fields = ('materia_pensum', 'materia_equivalente')


@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'semestre', 'creditos', 'tipo')
    search_fields = ('codigo', 'nombre')
    list_filter = ('tipo', 'semestre')


# HU-33
@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display  = ('estudiante', 'curso', 'periodo', 'fecha_clase', 'estado', 'registrado_por', 'fecha_registro')
    list_filter   = ('estado', 'periodo', 'curso')
    search_fields = ('estudiante__codigo', 'estudiante__nombre', 'curso__materia__nombre')
    date_hierarchy = 'fecha_clase'
    raw_id_fields  = ('estudiante', 'curso', 'periodo', 'registrado_por')
