from flask import url_for
from flask_login import current_user
import urllib.parse
from models import db, Notification
WHATSAPP_NUMBER="5493518553366"
def create_notification(user, message, link=None):
    """
    Crea y guarda una nueva notificación para un usuario específico.
    """
    if not user:
        return
        
    notification = Notification(
        user_id=user.id,
        message=message,
        link=link
    )
    db.session.add(notification)
    
    
def generate_whatsapp_link(motive="Consulta general del portal"):
    """
    Genera el URL de WhatsApp con el ID del cliente y el motivo precargados.
    
    HU: Generar un link de WhatsApp con datos precargados para la derivación a un agente.
    """
    if not current_user.is_authenticated:
        return "javascript:void(0);" # Enlace seguro si el usuario no está logueado
        
    user_id = current_user.id
    username = current_user.username
    
    # Contenido Precargado (Requerimiento)
    message_content = f"Hola, soy {username} (ID Cliente: {user_id}). Necesito soporte. Motivo: {motive}"
    
    # Codificar el mensaje (Requerimiento)
    encoded_message = urllib.parse.quote(message_content)
    
    # Generar el URL final
    whatsapp_url = f"https://wa.me/{WHATSAPP_NUMBER}?text={encoded_message}"
    
    return whatsapp_url