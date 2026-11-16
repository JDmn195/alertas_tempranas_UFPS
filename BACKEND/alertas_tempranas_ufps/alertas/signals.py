"""
HU-30: Cancela los recordatorios pendientes cuando se registra seguimiento.

Se usan señales para cubrir cualquier vía de registro (API, admin, comandos).
"""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from alertas import cache_listado
from alertas.models import Alerta, AnotacionIntervencion, Evidencia, Intervencion, RiesgoEstudiante
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


# SDAT-303: cualquier cambio de una alerta o del riesgo de un estudiante invalida el listado en caché
for _modelo in (Alerta, RiesgoEstudiante):
    post_save.connect(cache_listado.invalidar, sender=_modelo, dispatch_uid=f'listado_alertas_save_{_modelo.__name__}')
    post_delete.connect(cache_listado.invalidar, sender=_modelo, dispatch_uid=f'listado_alertas_del_{_modelo.__name__}')
