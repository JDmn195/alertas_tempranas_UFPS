"""
Comando: poblar_riesgo_periodos
================================
Migra los datos históricos de RiesgoEstudiante → RiesgoEstudiantePeriodo.

Situación que resuelve:
  - Se creó el modelo RiesgoEstudiantePeriodo para registrar el nivel de riesgo
    por periodo académico, pero ya existían registros en RiesgoEstudiante (snapshot
    global sin periodo).
  - Esta tabla nueva estaba vacía, haciendo que la ficha del estudiante, la gráfica
    de evolución de riesgo y el panel del director mostraran datos incorrectos.

Estrategia:
  1. Para cada estudiante que tiene notas registradas, calcula el nivel de riesgo
     acumulado hasta cada periodo (usando la lógica real de reglas activas).
  2. Crea o actualiza un RiesgoEstudiantePeriodo por cada periodo con notas.
  3. También actualiza el snapshot RiesgoEstudiante con el nivel del último periodo.
  4. Si un estudiante tiene RiesgoEstudiante pero NO tiene notas, conserva el
     snapshot existente y lo "replica" como un registro de periodo usando la fecha
     del snapshot como referencia (si hay algún periodo disponible).

Uso:
    python manage.py poblar_riesgo_periodos
    python manage.py poblar_riesgo_periodos --solo-vacios     # Solo estudiantes sin registros en la tabla nueva
    python manage.py poblar_riesgo_periodos --batch-size 100  # Lotes de 100 estudiantes
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from academico.models import Estudiante, Nota, Periodo
from alertas.models import Regla, RiesgoEstudiante, RiesgoEstudiantePeriodo


class Command(BaseCommand):
    help = (
        'Puebla RiesgoEstudiantePeriodo a partir de notas históricas. '
        'Soluciona el estado vacío de la tabla cuando ya existían datos en RiesgoEstudiante.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--solo-vacios',
            action='store_true',
            default=False,
            help='Solo procesa estudiantes que no tienen ningún registro en RiesgoEstudiantePeriodo.',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Número de estudiantes a procesar por lote (default: 50).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Simula el proceso sin escribir en la BD.',
        )

    def handle(self, *args, **options):
        solo_vacios = options['solo_vacios']
        batch_size  = options['batch_size']
        dry_run     = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('MODO SIMULACIÓN — no se escribirá nada en la BD.'))

        # ── 1. Cargar reglas activas una sola vez ─────────────────────────────
        reglas = list(Regla.objects.filter(activo=True).order_by('-prioridad'))
        if not reglas:
            self.stdout.write(self.style.ERROR(
                'No hay reglas activas. Ejecuta "python manage.py reset_reglas" primero.'
            ))
            return

        self.stdout.write(f'Reglas activas cargadas: {len(reglas)}')

        # ── 2. Seleccionar estudiantes a procesar ─────────────────────────────
        estudiantes_qs = Estudiante.objects.all().order_by('codigo')

        if solo_vacios:
            # Solo los que no tienen ningún RiesgoEstudiantePeriodo
            con_periodo = RiesgoEstudiantePeriodo.objects.values_list(
                'estudiante_id', flat=True
            ).distinct()
            estudiantes_qs = estudiantes_qs.exclude(codigo__in=con_periodo)
            self.stdout.write(
                f'Modo --solo-vacios: procesando solo estudiantes sin registros de periodo.'
            )

        total = estudiantes_qs.count()
        self.stdout.write(f'Estudiantes a procesar: {total}')

        if total == 0:
            self.stdout.write(self.style.SUCCESS('Nada que hacer. Todos los estudiantes ya tienen registros de periodo.'))
            return

        # ── 3. Importar la función de cálculo ─────────────────────────────────
        from alertas.views.alert_generation_views import calcular_y_guardar_riesgo_por_periodos

        # ── 4. Procesar en lotes ──────────────────────────────────────────────
        procesados   = 0
        con_notas    = 0
        sin_notas    = 0
        periodos_creados = 0
        errores      = 0

        codigos = list(estudiantes_qs.values_list('codigo', flat=True))

        for i in range(0, len(codigos), batch_size):
            lote = codigos[i:i + batch_size]
            self.stdout.write(
                f'  Procesando lote {i // batch_size + 1} '
                f'({i + 1}–{min(i + batch_size, total)} de {total})...'
            )

            for codigo in lote:
                try:
                    estudiante = Estudiante.objects.get(codigo=codigo)
                    tiene_notas = Nota.objects.filter(estudiante=estudiante).exists()

                    if tiene_notas:
                        # Caso principal: calcular riesgo por cada periodo con notas
                        periodos_estudiante = (
                            Periodo.objects
                            .filter(nota__estudiante=estudiante)
                            .distinct()
                            .count()
                        )

                        if not dry_run:
                            with transaction.atomic():
                                calcular_y_guardar_riesgo_por_periodos(estudiante, reglas=reglas)

                        periodos_creados += periodos_estudiante
                        con_notas += 1
                    else:
                        # Sin notas: el estudiante tiene snapshot en RiesgoEstudiante
                        # pero no tiene notas para calcular periodos.
                        # Replicamos el snapshot al periodo más reciente disponible en la BD
                        # solo si hay algún periodo disponible.
                        try:
                            snapshot = RiesgoEstudiante.objects.get(estudiante=estudiante)
                            periodo_reciente = Periodo.objects.order_by('-anio', '-semestre').first()

                            if periodo_reciente and not dry_run:
                                with transaction.atomic():
                                    RiesgoEstudiantePeriodo.objects.update_or_create(
                                        estudiante=estudiante,
                                        periodo=periodo_reciente,
                                        defaults={
                                            'nivel_riesgo': snapshot.nivel_riesgo,
                                            'reglas_aplicadas': snapshot.reglas_aplicadas,
                                        }
                                    )
                                periodos_creados += 1
                        except RiesgoEstudiante.DoesNotExist:
                            pass  # Sin snapshot ni notas → nada que migrar

                        sin_notas += 1

                    procesados += 1

                except Exception as e:
                    errores += 1
                    self.stdout.write(
                        self.style.ERROR(f'    Error procesando {codigo}: {e}')
                    )

        # ── 5. Resumen ────────────────────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('═' * 55))
        self.stdout.write(self.style.SUCCESS('RESULTADO'))
        self.stdout.write(self.style.SUCCESS('═' * 55))
        self.stdout.write(f'  Estudiantes procesados:       {procesados}')
        self.stdout.write(f'  Con notas (calculado):        {con_notas}')
        self.stdout.write(f'  Sin notas (snapshot copiado): {sin_notas}')
        self.stdout.write(f'  Registros de periodo creados: {periodos_creados}')
        if errores:
            self.stdout.write(self.style.ERROR(f'  Errores:                      {errores}'))
        else:
            self.stdout.write(f'  Errores:                      0')

        if dry_run:
            self.stdout.write(self.style.WARNING('\nMODO SIMULACIÓN — ningún dato fue modificado.'))
        else:
            self.stdout.write(self.style.SUCCESS('\nMigración completada exitosamente.'))
            self.stdout.write(
                'Puedes verificar con: '
                'python manage.py shell -c '
                '"from alertas.models import RiesgoEstudiantePeriodo; '
                'print(RiesgoEstudiantePeriodo.objects.count())"'
            )
