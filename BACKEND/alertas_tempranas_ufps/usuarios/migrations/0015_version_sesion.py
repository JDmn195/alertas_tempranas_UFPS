"""SDAT-323: versionado de sesiones sin modificar los datos de usuarios existentes."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0014_solicitud_acompanamiento')]

    operations = [
        migrations.AddField(
            model_name='usuario', name='version_sesion',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='auditoria', name='tipo_accion',
            field=models.CharField(max_length=50, choices=[('CREAR_USUARIO', 'Crear Usuario'), ('EDITAR_ROL', 'Editar Rol de Usuario'), ('DESACTIVAR_USUARIO', 'Desactivar Usuario'), ('IMPORTACION', 'Importación de Datos'), ('CREAR_REGLA', 'Crear Regla'), ('MODIFICAR_REGLA', 'Modificar Regla'), ('ACTIVAR_REGLA', 'Activar Regla'), ('DESACTIVAR_REGLA', 'Desactivar Regla'), ('CERRAR_ALERTA', 'Cerrar Alerta'), ('REGISTRAR_INTERVENCION', 'Registrar Intervención'), ('CONCLUIR_INTERVENCION', 'Concluir Intervención'), ('GENERAR_ALERTAS', 'Generar Alertas'), ('LOGIN', 'Inicio de Sesión'), ('LOGOUT', 'Cierre de Sesión'), ('ACCESO_DENEGADO', 'Acceso Denegado (403)'), ('REGISTRO_ASISTENCIA', 'Registro de Asistencia'), ('ENVIO_RECORDATORIOS', 'Envío de Recordatorios'), ('CONFIGURAR_RECORDATORIOS', 'Configurar Recordatorios'), ('REEVALUAR_ALERTAS', 'Reevaluar Alertas'), ('RECALCULAR_RIESGO', 'Recalcular Riesgo de Estudiante'), ('REEVALUACION_RIESGO', 'Re-evaluación Periódica del Riesgo'), ('MIGRAR_RIESGO_PERIODOS', 'Migrar Riesgo por Periodos'), ('MODIFICAR_UMBRAL_INASISTENCIA', 'Modificar Umbral de Inasistencia'), ('CREAR_CUENTA_ESTUDIANTE', 'Crear Cuenta de Estudiante'), ('ASOCIAR_CUENTA_ESTUDIANTE', 'Asociar Cuenta de Estudiante'), ('SOLICITAR_ACOMPANAMIENTO', 'Solicitar Acompañamiento'), ('CANCELAR_SOLICITUD', 'Cancelar Solicitud de Acompañamiento'), ('GESTIONAR_SOLICITUD', 'Gestionar Solicitud de Acompañamiento')]),
        ),
    ]
