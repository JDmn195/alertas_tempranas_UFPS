from django.apps import AppConfig


class AlertasConfig(AppConfig):
    name = 'alertas'

    def ready(self):
        from alertas import signals  # noqa: F401  (HU-30: cancelación de recordatorios)
