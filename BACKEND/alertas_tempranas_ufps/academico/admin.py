from django.contrib import admin
from .models import Materia, Curso, Estudiante, Nota, Periodo, Docente, EquivalenciaMateria


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
