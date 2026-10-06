"""
Comando: enviar_recordatorios  (HU-30)
=====================================
Detecta alertas e intervenciones sin seguimiento según los parámetros de
ConfiguracionRecordatorio, envía los recordatorios (correo + notificación
interna), reintenta los pendientes y cancela los que ya tienen seguimiento.

Pensado para ejecutarse de forma programada (Render Cron Job, cron del SO, etc.).

Uso:
    python manage.py enviar_recordatorios
"""
from django.core.management.base import BaseCommand

from alertas.recordatorios import RecordatoriosEnCurso, procesar_recordatorios


class Command(BaseCommand):
    help = 'Envía recordatorios de alertas e intervenciones sin seguimiento (HU-30).'

    def add_arguments(self, parser):
        parser.add_argument('--origen', choices=['PROGRAMADA', 'MANUAL'], default='PROGRAMADA')

    def handle(self, *args, **options):
        try:
            resumen = procesar_recordatorios(origen=options['origen'])
        except RecordatoriosEnCurso as e:
            self.stdout.write(self.style.WARNING(str(e)))
            return

        if not resumen['activo']:
            self.stdout.write(self.style.WARNING('Los recordatorios están desactivados en la configuración.'))
            return

        estilo = self.style.SUCCESS if not (resumen['fallido'] or resumen['errores']) else self.style.WARNING
        self.stdout.write(estilo(
            f"{resumen['casos_detectados']} casos sin seguimiento — "
            f"{resumen['creados']} recordatorios nuevos, {resumen['reintentados']} reintentos, "
            f"{resumen['omitidos']} omitidos (ya recordados), {resumen['cancelados']} cancelados, "
            f"{resumen['correos_enviados']} correos de resumen. "
            f"Enviados: {resumen['enviado']}, pendientes: {resumen['pendiente']}, "
            f"parciales: {resumen['parcial']}, fallidos: {resumen['fallido']}, errores: {resumen['errores']}."
        ))
