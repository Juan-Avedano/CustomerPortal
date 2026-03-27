# C:\Users\Juan Avedano\Desktop\Facultad\Proyecto\forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectMultipleField, HiddenField,SelectField, TextAreaField # <-- Asegúrate de que SelectField y TextAreaField estén aquí
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, NumberRange
from wtforms.widgets import ListWidget, CheckboxInput

class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('Contraseña Actual', validators=[DataRequired()])
    new_password = PasswordField('Nueva Contraseña', validators=[DataRequired(), Length(min=6, max=60)])
    confirm_new_password = PasswordField('Confirmar Nueva Contraseña', 
                                         validators=[DataRequired(), EqualTo('new_password', message='Las contraseñas no coinciden.')])
    submit = SubmitField('Cambiar Contraseña')
    
class LoginForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    remember_me = BooleanField('Recordarme')
    submit = SubmitField('Entrar')

class RegistrationForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email(message='El formato del correo electrónico no es válido. Debe ser: usuario@ejemplo.com')])
    password = PasswordField('Contraseña', validators=[DataRequired(),Length(min=6, max=20)])
    confirm_password = PasswordField('Confirmar Contraseña', validators=[DataRequired(), Length(min=6, max=20), EqualTo('password', message='Las contraseñas no coinciden.')])
    submit = SubmitField('Registrarse')

# ¡NUEVO FORMULARIO PARA EDICIÓN DE USUARIOS!
class UserEditForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email(message='El formato del correo electrónico no es válido. Debe ser: usuario@ejemplo.com')])
    # La contraseña y confirmar contraseña son OPCIONALES para la edición
    password = PasswordField('Nueva Contraseña (dejar vacío para no cambiar)', validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField('Confirmar Nueva Contraseña', validators=[EqualTo('password', message='Las contraseñas deben coincidir.')])
    submit = SubmitField('Actualizar Usuario')

# ¡NUEVO FORMULARIO: Contratar Servicio!
class ContractServiceForm(FlaskForm):
    # Este campo contendrá los IDs de los servicios que el usuario seleccione
    services = SelectMultipleField(
        'Servicios Disponibles',
        coerce=int, # Asegura que los valores sean enteros (IDs de servicio)
        # widget=CheckboxSelectMultiple(), # <--- ¡CAMBIO AQUÍ TAMBIÉN!
        widget=ListWidget(prefix_label=False), # <-- Utiliza ListWidget
        option_widget=CheckboxInput(),     # <-- Y CheckboxInput para cada opción
    )
    submit = SubmitField('Contratar Servicios Seleccionados')
    # Si quisieras editar si el usuario es admin, también lo añadirías aquí:
    # is_admin = BooleanField('Es Administrador')

class ModifyServiceForm(FlaskForm):
    # Este campo 'plan' permitirá al usuario seleccionar otro "plan" para su servicio.
    # Las opciones se llenarán dinámicamente desde la base de datos en la vista de Flask.
    # 'coerce=int' es crucial para que WTForms maneje los IDs como enteros.
    plan = SelectField('Seleccionar Nuevo Plan', validators=[DataRequired()], coerce=int)
        
    # Puedes añadir más campos aquí si quieres que el usuario modifique otras cosas.
    # Por ejemplo, si un servicio tuviera una descripción editable:
    # description = TextAreaField('Descripción del Servicio', validators=[Optional(), Length(max=500)])

    submit = SubmitField('Guardar Cambios del Servicio')

class ToggleUserStatusForm(FlaskForm):
    pass 



# --- ¡NUEVO FORMULARIO PARA AGENDAR VISITAS TÉCNICAS! ---

class ScheduleVisitForm(FlaskForm):
    """
    Formulario para que un cliente pueda solicitar una nueva visita técnica.
    """
    # Campo para seleccionar el servicio afectado. Las opciones se llenarán dinámicamente.
    service = SelectField('¿Para qué servicio necesitas asistencia?', 
                          validators=[DataRequired(message="Debes seleccionar un servicio.")], 
                          coerce=int)

    # Campo de texto largo para que el usuario describa el problema.
    reason = TextAreaField('Describe el motivo de tu solicitud', 
                           validators=[DataRequired(message="Por favor, describe el motivo."), Length(min=10, max=500)],
                           render_kw={'placeholder': 'Ej: No tengo conexión a internet, la señal del cable se ve mal...'})

    # Campo de fecha y hora. Por ahora es un campo de texto, luego lo integraremos con un calendario.
    scheduled_datetime = StringField('Fecha y Hora Propuesta', 
                                     validators=[DataRequired(message="Debes proponer una fecha y hora.")],
                                     render_kw={'placeholder': 'YYYY-MM-DD HH:MM'})

    submit = SubmitField('Agendar Visita')
    
    
    
class AssignTechnicianForm(FlaskForm):
    """
    Formulario para que un administrador asigne un técnico a una visita.
    """
    # Menú desplegable que llenaremos con los técnicos disponibles
    technician = SelectField('Seleccionar Técnico', 
                             validators=[DataRequired(message="Debes seleccionar un técnico.")], 
                             coerce=int)
    
    submit = SubmitField('Asignar Técnico')
    
#------------------------------ sprint 7
    
class ModifyVisitForm(FlaskForm):
    """
    Formulario para que un cliente pueda editar una visita técnica agendada.
    """
    # Los campos son idénticos a los de 'ScheduleVisitForm'
    service = SelectField('Servicio para la asistencia', 
                          validators=[DataRequired(message="Debes seleccionar un servicio.")], 
                          coerce=int)

    reason = TextAreaField('Motivo de la solicitud', 
                           validators=[DataRequired(message="Por favor, describe el motivo."), Length(min=10, max=500)])

    scheduled_datetime = StringField('Nueva Fecha y Hora', 
                                     validators=[DataRequired(message="Debes proponer una fecha y hora.")])

    submit = SubmitField('Guardar Cambios')


# --- 1. Formulario para Modificación de WiFi (RD: Modificar SSID y Clave) ---

class ModificarWiFiForm(FlaskForm):
    # Campos para la banda 2.4 GHz
    ssid_2g = StringField('Nombre de Red (SSID 2.4Ghz)', validators=[DataRequired(), Length(min=1, max=64)])
    clave_2g = PasswordField('Contraseña 2.4Ghz', validators=[DataRequired(), Length(min=8, max=64)])
    
    # Campos para la banda 5 GHz (opcional)
    ssid_5g = StringField('Nombre de Red (SSID 5Ghz)', validators=[Length(max=64)])
    clave_5g = PasswordField('Contraseña 5Ghz', validators=[Length(min=8, max=64)])
    
    # Nota: Aquí se podría añadir una validación para asegurar que clave_5g se ingrese si ssid_5g se modifica.
    
    submit = SubmitField('Modificar Configuración')

# --- 2. Formulario para Solicitud de Planes (RD: Registrar una solicitud) ---

class MFAChallengeForm(FlaskForm):
    token = StringField('Código de 6 dígitos', validators=[DataRequired(message="El código debe tener 6 dígitos.")], render_kw={'placeholder': 'Ej:123456'})
    submit = SubmitField('Verificar y Acceder')
    



class PeticionPlanForm(FlaskForm):
    # Campo 1: Tipo general de petición (Se mantiene, aunque es menos relevante ahora)
    tipo_peticion = SelectField('Tipo de Solicitud', choices=[
        ('TV', 'Servicios de TV y Streaming'),
        ('Internet', 'Aumento de Velocidad/Modificación de Internet'),
        ('Otro', 'Otro Servicio/Consulta')
    ], validators=[DataRequired()])
    
    # Campo 2: SELECCIÓN MÚLTIPLE (Convertido a SelectMultipleField)
    # coerce=str asegura que los valores se manejen como strings, incluso si son IDs.
    pack_solicitado = SelectMultipleField('Packs Específicos / Servicios a Agregar', choices=[
        ('Pack Futbol', 'Pack Fútbol'),
        ('HBO Max', 'HBO Max'),
        ('Netflix Estándar', 'Netflix Estándar'),
        ('Disney+ / Star+', 'Disney+ / Star+'),
        ('Aumento 500Mbps', 'Aumento de Velocidad (500Mbps)'),
        ('Aumento 1Gbps', 'Aumento de Velocidad (1Gbps)'),
        ('Otros', 'Otros (Detallar en el campo inferior)')
    ], validators=[DataRequired()], coerce=str)
    
    # Campo 3: Campo de Texto Libre para detalles/servicios no listados
    detalle_adicional = TextAreaField('Detalle Adicional o Comentarios', 
                                    validators=[Length(max=255)], 
                                    render_kw={"rows": 3, "placeholder": "Ej: Quiero el plan más alto de Netflix, o especificar fecha de activación."})
    
    submit = SubmitField('Enviar Solicitud al Administrador')

# --- 3. Formulario para Calificación de Servicio (RD: Emitir mini-formulario) ---

class CalificacionServicioForm(FlaskForm):

    puntuacion = SelectField('Puntuación de la Atención (0-10)', 
                            choices=[(i, str(i)) for i in range(11)], 
                            coerce=int,
                            validators=[DataRequired(), NumberRange(min=0, max=10)])
    
    satisfaccion_valida = SelectField('¿El servicio satisfizo su necesidad?', 
                                    choices=[
                                        ('True', 'Sí, el problema fue resuelto'), 
                                        ('False', 'No, el problema persiste')
                                    ], 
                                    # Esta función de coerción convierte el string 'True' o 'False' al valor booleano Python
                                    coerce=lambda x: x == 'True', 
                                    validators=[])
    
    comentarios = TextAreaField('Comentarios adicionales (opcional)', validators=[Length(max=500)])
    
    # Campo oculto para llevar el ID de la visita (HiddenField, asumimos que está importado)
    visita_id = HiddenField(validators=[DataRequired()]) 
    
    submit = SubmitField('Enviar Calificación')