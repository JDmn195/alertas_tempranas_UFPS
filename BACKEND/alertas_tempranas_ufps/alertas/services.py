import requests
import json
import os
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import escape
from .models import Alerta, NotificacionHistorial, NotificacionInterna
from academico.models import Estudiante, Docente, Nota, Periodo
from usuarios.models import Usuario

class NotificationService:
    @staticmethod
    def get_brevo_config():
        return {
            'api_key': os.getenv('BREVO_API_KEY'),
            'sender_email': os.getenv('BREVO_SENDER_EMAIL', 'alertas@ufps.edu.co'),
            'sender_name': 'Sistema de Alertas Tempranas UFPS'
        }

    @staticmethod
    def registrar_historial(alerta, destinatario, rol_destinatario, canal, resultado, detalle_error=None, tipo='ALERTA'):
        return NotificacionHistorial.objects.create(
            alerta=alerta,
            destinatario=destinatario,
            rol_destinatario=rol_destinatario,
            canal=canal,
            tipo=tipo,
            resultado=resultado,
            detalle_error=detalle_error,
        )

    @classmethod
    def enviar_brevo(cls, to_email, subject, html_content):
        """Envía el correo por Brevo sin registrar historial. Retorna (resultado, detalle_error)."""
        config = cls.get_brevo_config()
        if not config['api_key']:
            return 'fallido', 'BREVO_API_KEY no configurada'

        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": config['api_key']
        }
        payload = {
            "sender": {"name": config['sender_name'], "email": config['sender_email']},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_content
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code in [201, 202]:
                return 'exitoso', None
            return 'fallido', f"Error API Brevo: {response.status_code} - {response.text}"
        except Exception as e:
            return 'reintento', str(e)

    @classmethod
    def enviar_correo(cls, to_email, subject, html_content, alerta, rol_destinatario, tipo='ALERTA'):
        """Envía el correo por Brevo y retorna el NotificacionHistorial registrado."""
        resultado, detalle_error = cls.enviar_brevo(to_email, subject, html_content)
        return cls.registrar_historial(alerta, to_email, rol_destinatario, 'EMAIL', resultado, detalle_error, tipo)

    @classmethod
    def enviar_correo_brevo(cls, to_email, subject, html_content, alerta, rol_destinatario, tipo='ALERTA'):
        return cls.enviar_correo(to_email, subject, html_content, alerta, rol_destinatario, tipo).resultado == 'exitoso'

    @classmethod
    def enviar_interna(cls, usuario, alerta, mensaje, tipo='ALERTA'):
        """Crea la notificación interna y retorna el NotificacionHistorial registrado."""
        try:
            NotificacionInterna.objects.create(
                usuario=usuario,
                alerta=alerta,
                mensaje=mensaje
            )
            return cls.registrar_historial(alerta, usuario.correo, usuario.rol, 'INTERNA', 'exitoso', tipo=tipo)
        except Exception as e:
            return cls.registrar_historial(alerta, usuario.correo, usuario.rol, 'INTERNA', 'fallido', str(e), tipo)

    @classmethod
    def crear_notificacion_interna(cls, usuario, alerta, mensaje, tipo='ALERTA'):
        return cls.enviar_interna(usuario, alerta, mensaje, tipo).resultado == 'exitoso'

    @staticmethod
    def generar_html_basico(alerta, destinatario_nombre):
        """Genera un HTML estético para el correo. Los datos importados se escapan."""
        estudiante = alerta.estudiante
        regla = alerta.regla
        destinatario_nombre = escape(destinatario_nombre)
        
        # Estilos embebidos para compatibilidad con clientes de correo
        html = f"""
        <html>
        <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-top: 5px solid #aa1916;">
                <div style="padding: 20px; text-align: center; background-color: #f8f9fa;">
                    <h2 style="color: #aa1916; margin: 0;">Alerta Académica Generada</h2>
                </div>
                <div style="padding: 30px;">
                    <p>Hola, <strong>{destinatario_nombre}</strong>.</p>
                    <p>Se ha detectado una nueva alerta en el sistema para el estudiante:</p>
                    
                    <div style="background-color: #fff8f8; padding: 15px; border-left: 4px solid #aa1916; margin: 20px 0;">
                        <p style="margin: 5px 0;"><strong>Estudiante:</strong> {escape(estudiante.nombre)} ({escape(estudiante.codigo)})</p>
                        <p style="margin: 5px 0;"><strong>Tipo de Alerta:</strong> {escape(regla.nombre)}</p>
                        <p style="margin: 5px 0;"><strong>Severidad:</strong> {escape(regla.get_nivel_display())}</p>
                        <p style="margin: 5px 0;"><strong>Causa:</strong> {escape(alerta.valor_causa)}</p>
                    </div>

                    <p>Por favor, revisa el sistema para realizar el seguimiento correspondiente.</p>
                </div>
                <div style="padding: 20px; text-align: center; font-size: 12px; color: #6c757d; background-color: #f8f9fa;">
                    &copy; 2026 Universidad Francisco de Paula Santander - Alertas Tempranas
                </div>
            </div>
        </body>
        </html>
        """
        return html

    @classmethod
    def notificar_alerta(cls, alerta):
        """Lógica principal de enrutamiento de notificaciones"""
        estudiante = alerta.estudiante
        regla = alerta.regla
        
        destinatarios = []
        
        # 1. SIEMPRE al estudiante (Email)
        if estudiante.email_institucional:
            destinatarios.append({
                'nombre': estudiante.nombre,
                'email': estudiante.email_institucional,
                'rol': 'ESTUDIANTE',
                'usuario_obj': None # El estudiante no tiene objeto Usuario necesariamente
            })
        elif estudiante.email_personal:
             destinatarios.append({
                'nombre': estudiante.nombre,
                'email': estudiante.email_personal,
                'rol': 'ESTUDIANTE',
                'usuario_obj': None
            })

        # 2. DOCENTES (si están involucrados)
        docentes_involucrados = set()
        if regla.tipo == 'REPROBACION':
            # Buscar docentes de materias reprobadas
            periodo_reciente = Periodo.objects.order_by('-anio', '-semestre').first()
            notas_reprobadas = Nota.objects.filter(
                estudiante=estudiante, 
                definitiva__lt=3.0,
                periodo=periodo_reciente
            ).select_related('curso__docente__usuario')
            
            for nota in notas_reprobadas:
                docentes_involucrados.add(nota.curso.docente.usuario)
        
        for u_docente in docentes_involucrados:
            destinatarios.append({
                'nombre': u_docente.nombre,
                'email': u_docente.correo,
                'rol': 'DOCENTE',
                'usuario_obj': u_docente
            })

        # 3. DIRECTOR (si es severidad Alta)
        if regla.nivel == 'high':
            directores = Usuario.objects.filter(rol__contains='DIRECTOR', activo=True)
            for director in directores:
                destinatarios.append({
                    'nombre': director.nombre,
                    'email': director.correo,
                    'rol': 'DIRECTOR',
                    'usuario_obj': director
                })

        # 4. ADMINISTRADORES (Siempre reciben copia)
        administradores = Usuario.objects.filter(rol__contains='ADMINISTRADOR', activo=True)
        for admin in administradores:
            destinatarios.append({
                'nombre': admin.nombre,
                'email': admin.correo,
                'rol': 'ADMINISTRADOR',
                'usuario_obj': admin
            })

        # Ejecutar envíos
        for dest in destinatarios:
            html = cls.generar_html_basico(alerta, dest['nombre'])
            subject = f"Alerta {regla.get_nivel_display()} - {estudiante.nombre}"
            
            # Enviar Email
            cls.enviar_correo_brevo(dest['email'], subject, html, alerta, dest['rol'])
            
            # Notificación Interna (si tiene usuario)
            if dest['usuario_obj']:
                mensaje = f"Se ha generado una alerta de nivel {regla.get_nivel_display()} para el estudiante {estudiante.nombre} por la regla: {regla.nombre} (Valor: {alerta.valor_causa})."
                cls.crear_notificacion_interna(dest['usuario_obj'], alerta, mensaje)

        return True
