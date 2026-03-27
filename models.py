# C:\Users\Juan Avedano\Desktop\Facultad\Proyecto\models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import Table, Column, Integer, ForeignKey 
from sqlalchemy.sql import func
from datetime import datetime
import base64

db = SQLAlchemy()

# Definición de la tabla de asociación
# Esta tabla conectará usuarios con servicios que han contratado
user_services_association = db.Table(
    'user_services_association', # Nombre de la tabla de asociación en la DB
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('service_id', db.Integer, db.ForeignKey('service.id'), primary_key=True),
)

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    totp_secret= db.Column(db.String(32),nullable = True)
    mfa_enable=db.Column(db.Boolean, default=False)
    complaints = db.relationship('Complaint', backref='complainant', lazy=True, cascade="all, delete-orphan")

    # Relación muchos-a-muchos con Service a través de la tabla de asociación
    # backref='users_who_contracted' permite acceder a los usuarios desde un servicio
    # lazy='dynamic' es útil para consultas encadenadas (ej. user.services.filter_by(...))
    technical_visits = db.relationship('TechnicalVisit', backref='user', lazy=True, cascade="all, delete-orphan")
    notifications = db.relationship('Notification', backref='user', lazy=True, order_by='Notification.timestamp.desc()', cascade= "all, delete-orphan")
    services_contracted = db.relationship(
        'Service',
        secondary=user_services_association,
        backref=db.backref('users_who_contracted', lazy='dynamic'),
        lazy='dynamic', cascade="all, delete"
    )
    peticiones = db.relationship(
        'Peticion', 
        backref='user', 
        lazy=True, 
        cascade="all, delete-orphan" 
    )
    invoices = db.relationship(
        'Invoice',
        backref='user',
        lazy=True,
        cascade="all, delete-orphan"
    )
    def set_password(self, password):
        """Hashea y establece la nueva contraseña del usuario."""
        from app import bcrypt 
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Verifica una contraseña plana contra el hash almacenado."""
        from app import bcrypt
        return bcrypt.check_password_hash(self.password, password)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}', 'Admin: {self.is_admin}')"

class Service(db.Model):
    __tablename__ = 'service'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(50), nullable=False, default='General')
    complaints = db.relationship('Complaint', backref='service_offered', lazy=True)
    # La 'backref' en User ya crea la relación inversa
    technical_visits = db.relationship('TechnicalVisit', backref='service', lazy=True, cascade="all, delete-orphan")
    wifi_config = db.relationship(
        'ConfiguracionWiFi', 
        backref='service', 
        uselist=False, # Es una relación 1:1 (un servicio tiene una sola config WiFi)
        # VITAL: Si el Servicio se va, elimina la configuración WiFi.
        cascade="all, delete-orphan" 
    )

    def __repr__(self):
        return f"Service('{self.name}', '{self.type}', '{self.price}')"

class Complaint(db.Model):
    __tablename__ = 'complaint'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Pendiente')
    date_created = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    def __repr__(self):
        return f"Complaint('{self.subject}', '{self.status}')"
    
class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    billing_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='Pendiente')
    external_reference = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f'<Invoice {self.id} - Amount: {self.amount}>'
    
    
    
class Technician(db.Model):
    """Modelo para representar a los técnicos de la empresa."""
    __tablename__ = 'technician'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    specialty = db.Column(db.String(100), nullable=True)
    current_lat = db.Column(db.Float, nullable=True) # Latitud para mapa en tiempo real
    current_lon = db.Column(db.Float, nullable=True) # Longitud para mapa en tiempo real
    
    # Relación uno-a-muchos con TechnicalVisit
    technical_visits = db.relationship('TechnicalVisit', backref='technician', lazy=True)

    def __repr__(self):
        return f"Technician('{self.name}', '{self.specialty}')"

class TechnicalVisit(db.Model):
    """Modelo para agendar y gestionar las visitas técnicas."""
    __tablename__ = 'technical_visit'
    id = db.Column(db.Integer, primary_key=True)
    reason = db.Column(db.Text, nullable=False)
    scheduled_datetime = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Agendada') # Ej: Agendada, En Camino, Completada, Cancelada
    
    # Foreign Keys para las relaciones
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    technician_id = db.Column(db.Integer, db.ForeignKey('technician.id'), nullable=True) # Puede ser nulo si aún no se asignó
    def __repr__(self):
        return f"TechnicalVisit(ID: {self.id}, Status: '{self.status}', Date: {self.scheduled_datetime})"

class Notification(db.Model):
    """Modelo para registrar notificaciones para los usuarios."""
    __tablename__ = 'notification'
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    link = db.Column(db.String(255), nullable=True) # URL opcional para redirigir al usuario
    
    # Foreign Key para la relación
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f"Notification(User: {self.user_id}, Message: '{self.message[:20]}...')"
    
    
    
 # --- Nuevos modelos para el Sprint 7 ---

class ConfiguracionWiFi(db.Model):
    """
    Almacena los parámetros de configuración de red (WiFi)
    asociados a un servicio de Internet Fijo específico.
    """
    __tablename__ = 'configuracion_wifi'
    id = db.Column(db.Integer, primary_key=True)
    
    # FK: Aseguramos que la configuración esté ligada a un Servicio, y cada servicio tenga solo una configuración WiFi.
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), unique=True, nullable=False) 
    
    # Datos modificables por el cliente
    ssid_2g = db.Column(db.String(64), nullable=False)
    clave_2g = db.Column(db.String(128), nullable=False) # Se almacenará cifrada o con hashing si es necesario
    ssid_5g = db.Column(db.String(64))
    clave_5g = db.Column(db.String(128))

    # Datos técnicos de sólo lectura para el cliente
    encriptacion = db.Column(db.String(20), default='WPA2')
    nro_serie_equipo = db.Column(db.String(50)) 
    

    def __repr__(self):
        return f"ConfiguracionWiFi(Service ID: {self.service_id}, SSID: {self.ssid_2g})"


class Peticion(db.Model):
    """
    Registra las solicitudes del cliente al administrador (ej. agregar packs de TV).
    """
    __tablename__ = 'peticion'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    tipo_peticion = db.Column(db.String(50), nullable=False) # Ej: 'TV', 'Internet'
    detalle_plan = db.Column(db.String(255), nullable=False) # Ej: 'Agregar Pack Fútbol'
    
    estado = db.Column(db.String(20), default='Pendiente') # Posibles: 'Pendiente', 'Aplicado', 'Rechazado', 'Eliminada'
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_gestion = db.Column(db.DateTime)
    
    # Relaciones
    
    
    def __repr__(self):
        return f"Peticion(User: {self.user_id}, Detalle: '{self.detalle_plan}', Estado: {self.estado})"


class CalificacionServicio(db.Model):
    """
    Almacena el feedback del cliente sobre la visita técnica.
    """
    __tablename__ = 'calificacion_servicio'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # FK a la visita técnica. Una visita solo debe tener una calificación.
    technical_visit_id = db.Column(db.Integer, db.ForeignKey('technical_visit.id'), unique=True, nullable=False) 
    
    puntuacion = db.Column(db.Integer, nullable=False) # 0 a 10
    satisfaccion_valida = db.Column(db.Boolean, default=True) # Validación de si se resolvió el problema.
    comentarios = db.Column(db.Text)
    
    fecha_calificacion = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación inversa a la Visita Técnica
    technical_visit = db.relationship('TechnicalVisit', backref=db.backref('calificacion', uselist=False, cascade="all, delete-orphan"))
    
    def __repr__(self):
        return f"Calificacion(Visita ID: {self.technical_visit_id}, Puntuacion: {self.puntuacion})"   