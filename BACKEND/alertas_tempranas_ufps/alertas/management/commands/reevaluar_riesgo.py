"""
Comando: reevaluar_riesgo  (HU-29)
==================================
Re-evalúa el riesgo académico de los estudiantes con las reglas vigentes,
sin necesidad de una nueva importación. Genera, actualiza y cierra alertas y
registra cada ejecución (con sus reintentos) en EjecucionReevaluacion.

Pensado para ejecutarse de forma programada (Render Cron Job, cron del SO, etc.).

Uso:
    python manage.py reevaluar_riesgo
    python manage.py reevaluar_riesgo --max-intentos 3 --espera 60
    python manage.py reevaluar_riesgo --codigos 1151234 1155678
"""
from django.core.management.base import BaseCommand, CommandError

from alertas.reevaluacion import ReevaluacionEnCurso, ejecutar_reevaluacion


class Command(BaseCommand):
    help = 'Re-evalúa periódicamente el riesgo académico y actualiza las alertas (HU-29).'

    def add_arguments(self, parser):
        parser.add_argument('--max-intentos', type=int, default=None,
                            help='Intentos máximos (default: REEVALUACION_MAX_INTENTOS).')
        parser.add_argument('--espera', type=int, default=None,
                            help='Segundos base entre reintentos (default: REEVALUACION_ESPERA_SEGUNDOS).')
        parser.add_argument('--codigos', nargs='+', default=None,
                            help='Limita la re-evaluación a estos códigos de estudiante.')
        parser.add_argument('--origen', choices=['PROGRAMADA', 'MANUAL'], default='PROGRAMADA')

    def handle(self, *args, **options):
        try:
            ejecuciones = ejecutar_reevaluacion(
                origen=options['origen'],
                codigos=options['codigos'],
                max_intentos=options['max_intentos'],
                espera_segundos=options['espera'],
            )
        except ReevaluacionEnCurso as e:
            self.stdout.write(self.style.WARNING(str(e)))
            return

        for ej in ejecuciones:
            estilo = self.style.SUCCESS if ej.estado == 'EXITOSA' else self.style.WARNING
            self.stdout.write(estilo(
                f'Intento {ej.intento} (#{ej.id}): {ej.estado} — '
                f'{ej.procesados}/{ej.total_estudiantes} evaluados, '
                f'{ej.cambios_riesgo} cambios de riesgo, '
                f'{ej.alertas_generadas} alertas nuevas, {ej.alertas_actualizadas} actualizadas, '
                f'{ej.alertas_cerradas} cerradas, {ej.total_errores} errores.'
            ))
            if ej.mensaje_error:
                self.stdout.write(self.style.ERROR(f'  {ej.mensaje_error}'))

        # HU-32: Evaluar alertas por corte para el periodo actual
        try:
            from alertas.alertas_corte import evaluar_cortes_periodo_actual
            alertas_corte = evaluar_cortes_periodo_actual()
            self.stdout.write(self.style.SUCCESS(
                f'Alertas por corte procesadas en periodo actual: {len(alertas_corte)}'
            ))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Error al evaluar alertas por corte: {e}'))

        # HU-36: Evaluar alertas por inasistencia para el periodo actual
        try:
            from alertas.alertas_inasistencia import evaluar_inasistencia_periodo_actual
            alertas_inasistencia = evaluar_inasistencia_periodo_actual()
            self.stdout.write(self.style.SUCCESS(
                f'Alertas por inasistencia procesadas en periodo actual: {len(alertas_inasistencia)}'
            ))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Error al evaluar alertas por inasistencia: {e}'))

        if not ejecuciones or ejecuciones[-1].estado == 'FALLIDA':
            # Código de salida != 0 para que el programador marque la ejecución como fallida
            raise CommandError('La re-evaluación terminó en estado FALLIDA.')
