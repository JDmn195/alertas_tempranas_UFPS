"""
HU-30: Cancela los recordatorios pendientes cuando se registra seguimiento.

Se usan señales para cubrir cualquier vía de registro (API, admin, comandos).
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from alertas.models import Alerta, AnotacionIntervencion, Evidencia, Intervencion
from alertas.recordatorios import ESTADOS_ALERTA_CERRADOS, cancelar_recordatorios


@receiver(post_save, sender=Intervencion)
def intervencion_guardada(sender, instance, created, **kwargs):
    if created:
        cancelar_recordatorios('Se registró una intervención en la alerta.',
                               alerta=instance.alerta, tipo_caso='ALERTA')
    elif instance.concluida:
        cancelar_recordatorios('La intervención fue concluida.', intervencion=instance)


@receiver(post_save, sender=AnotacionIntervencion)
def anotacion_guardada(sender, instance, created, **kwargs):
    if created:
        cancelar_recordatorios('Se registró una anotación en la intervención.',
                               intervencion=instance.intervencion)


@receiver(post_save, sender=Evidencia)
def evidencia_guardada(sender, instance, created, **kwargs):
    if created:
        cancelar_recordatorios('Se subió una evidencia a la intervención.',
                               intervencion=instance.intervencion)


@receiver(post_save, sender=Alerta)
def alerta_guardada(sender, instance, created, update_fields=None, **kwargs):
    if update_fields is not None and 'estado' not in update_fields:
        return
    if instance.estado in ESTADOS_ALERTA_CERRADOS:
        cancelar_recordatorios('La alerta fue cerrada.', alerta=instance)
