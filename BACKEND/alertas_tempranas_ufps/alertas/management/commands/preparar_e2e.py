"""
Deja la base de las pruebas e2e (Playwright) en un estado conocido.

Solo corre con E2E=True, que usa su propia base SQLite (db_e2e.sqlite3) y no carga
el .env: nunca toca la base real. Borra el archivo, aplica las migraciones (que
crean las reglas CORTE e INASISTENCIA) y carga el escenario fijo que usan las
pruebas de FRONTEND/e2e.

    E2E=True DEBUG=True python manage.py preparar_e2e
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from ._entorno_pruebas import crear_usuario as usuario, recrear_base


class Command(BaseCommand):
    help = 'Recrea la base de las pruebas e2e y carga el escenario fijo (solo con E2E=True).'

    def handle(self, *args, **options):
        recrear_base()
        self._cargar_escenario()
        self.stdout.write(self.style.SUCCESS('Base e2e lista.'))

    def _cargar_escenario(self):
        from academico.models import Curso, Docente, Estudiante, Materia, Nota, Periodo
        from alertas.alertas_corte import evaluar_cortes_estudiante
        from alertas.evaluacion import actualizar_promedio
        from alertas.models import Regla
        from alertas.views.alert_generation_views import (
            calcular_y_guardar_riesgo_por_periodos, reprocesar_alertas_completas,
        )
        usuario('Admin E2E', 'admin@ufps.edu.co', 'ADMINISTRADOR')
        usuario('Directora E2E', 'director@ufps.edu.co', 'DIRECTOR')
        usuario('Bienestar E2E', 'bienestar@ufps.edu.co', 'BIENESTAR')
        usuario_docente = usuario('Docente Curso', 'docente@ufps.edu.co', 'DOCENTE')
        usuario_otro = usuario('Otro Docente', 'otro@ufps.edu.co', 'DOCENTE')

        docente = Docente.objects.create(
            codigo='D001', nombre='Docente Curso', tipo_vinculacion='Planta', usuario=usuario_docente,
        )
        Docente.objects.create(codigo='D002', nombre='Otro Docente', tipo_vinculacion='Planta', usuario=usuario_otro)

        calculo = Materia.objects.create(codigo='1150101', nombre='Cálculo I', creditos=3, semestre=1)
        fisica = Materia.objects.create(codigo='1150102', nombre='Física I', creditos=3, semestre=1)
        curso_calculo = Curso.objects.create(materia=calculo, grupo='A', docente=docente)
        curso_fisica = Curso.objects.create(materia=fisica, grupo='A', docente=docente)

        anterior = Periodo.objects.create(anio=2025, semestre=2)
        actual = Periodo.objects.create(anio=2026, semestre=1)

        def estudiante(codigo, nombre, documento):
            return Estudiante.objects.create(
                codigo=codigo, nombre=nombre, tipo_documento='CC', numero_documento=documento,
                semestre=2, estado_matricula='ACTIVO', email_institucional=f'{codigo}@ufps.edu.co',
            )

        # En riesgo: Física I perdida (PPA 2.0) y cortes bajos en Cálculo I → alertas PROMEDIO y CORTE
        ana = estudiante('1152001', 'Ana Pérez', '100200300')
        # Sin notas: lo usa la prueba de importación de historial desde la pantalla
        estudiante('1152002', 'Bruno Gómez', '100200301')
        # Buen rendimiento y matriculada en Cálculo I del periodo actual: pruebas de asistencia
        carla = estudiante('1152003', 'Carla Ruiz', '100200302')

        Regla.objects.create(
            nombre='Promedio Crítico', tipo='PROMEDIO', operador='<', valor_umbral=Decimal('2.5'),
            nivel='high', prioridad=30,
        )

        Nota.objects.create(estudiante=ana, curso=curso_fisica, periodo=anterior, definitiva=Decimal('2.0'))
        Nota.objects.create(
            estudiante=ana, curso=curso_calculo, periodo=actual,
            corte1=Decimal('1.5'), corte2=Decimal('2.0'), corte3=Decimal('2.5'),
        )
        Nota.objects.create(estudiante=carla, curso=curso_fisica, periodo=anterior, definitiva=Decimal('4.2'))
        Nota.objects.create(
            estudiante=carla, curso=curso_calculo, periodo=actual,
            corte1=Decimal('4.0'), corte2=Decimal('4.5'),
        )

        # Mismo procesamiento que hace la importación de historial
        for est in (ana, carla):
            actualizar_promedio(est)
            calcular_y_guardar_riesgo_por_periodos(est)
            reprocesar_alertas_completas(Estudiante.objects.filter(codigo=est.codigo), usuario=None)
            evaluar_cortes_estudiante(est, usuario=None)
