# C:\Users\Juan Avedano\Desktop\Facultad\Proyecto\app.py
from flask import send_file
from flask import Flask, render_template, redirect, url_for, flash, request, Blueprint, current_app
from flask_login import LoginManager, login_user, current_user, logout_user, login_required, UserMixin
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from flask import jsonify 
from forms import LoginForm, RegistrationForm, UserEditForm, ContractServiceForm, ToggleUserStatusForm
from config import Config # <-- Mantenla comentada si no tienes un config.py con tu URL de DB
from functools import wraps
from datetime import datetime
from sqlalchemy import func 
from utils import create_notification, generate_whatsapp_link
import pyotp
import os

# === IMPORTAR la instancia 'db' declarada en models.py ===
from models import db, User, Service, Complaint, user_services_association 

print("=== DEBUG: app.py ha sido recargado y ejecutado ===") # Este print se ejecuta cuando el módulo es cargado
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
bcrypt = Bcrypt()
# Definición de la función create_app
def create_app():
    # === INSTANCIA DE LA APP Y CONFIGURACIÓN ===
    app = Flask(__name__)

    csrf = CSRFProtect(app)
    app.config.from_object(Config)
    # --- Configuración de la base de datos MySQL (comentadas, asumo que usas Config.py) ---
    #app.config["SECRET_KEY"] = "PirataCordobesInstaMegaNashey2025"
    #app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:juancho16@localhost:3306/customer_portal'
    #app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    #app.config['SIMULATION_MODE'] = False 

    # === INSTANCIAS DE EXTENSIÓN INICIALIZADAS CON LA APP YA CONFIGURADA ===
    db.init_app(app) 
    
    # Bcrypt inicializado aquí, dentro de create_app
    # Para acceder a él fuera de create_app, usaremos current_app.extensions['flask-bcrypt']
    bcrypt.init_app(app)

 
    login_manager.init_app(app)
    
    migrate = Migrate(app, db)

    # Define un User mock para el modo simulación si no hay DB real
    class MockUser(UserMixin):
        def __init__(self, id, username, email, is_admin=False):
            self.id = id
            self.username = username
            self.email = email
            self.is_admin = is_admin

        def get_id(self):
            return str(self.id)

        @property
        def is_active(self):
            return True
        @property
        def is_authenticated(self):
            return True
        @property
        def is_anonymous(self):
            return False

        def check_password(self, password):
            mock_passwords = {
                'admin': 'admin123',
                'cliente': 'cliente123',
                'test': 'test123'
            }
            return mock_passwords.get(self.username) == password


    @app.context_processor
    def inject_now():
        return {'now': datetime.now()}


    @app.context_processor
    def inject_utilities():
        return { 'generate_whatsapp_link': generate_whatsapp_link}
    
    @app.context_processor
    def inject_now():
        return{'now': datetime.now()}

    @login_manager.user_loader
    def load_user(user_id):

        if app.config.get('SIMULATION_MODE', False): 
            mock_users_data = {
                1: {'username': 'admin', 'email': 'admin@example.com', 'is_admin': True},
                2: {'username': 'cliente', 'email': 'cliente@example.com', 'is_admin': False},
                3: {'username': 'test', 'email': 'test@example.com', 'is_admin': False},
            }
            user_data = mock_users_data.get(int(user_id))
            if user_data:
                return MockUser(int(user_id), user_data['username'], user_data['email'], user_data['is_admin'])
            return None
        else:
            user = User.query.get(int(user_id))
            if user and user.is_active: 
                return user
            return None 

    # --- Rutas de Autenticación y Registro (DENTRO de create_app) ---
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            # Lógica original para usuarios ya autenticados
            if current_user.is_admin:
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('customer_dashboard.index'))

        form = LoginForm()
        if form.validate_on_submit():
            
            username_to_check = form.username.data
            user = User.query.filter_by(username=username_to_check).first()
            
            if user:
                # 1. VERIFICACIÓN DE CONTRASEÑA
                if bcrypt.check_password_hash(user.password, form.password.data):
                    
                    # 2. VERIFICACIÓN DE CUENTA ACTIVA (Lógica existente de soporte)
                    if user.is_active:
                        
                        # 🎯 NUEVA LÓGICA: VERIFICACIÓN MFA (Solo si está activo)
                        if user.mfa_enable:
                            # Si el usuario tiene MFA activado, redirigimos al desafío (Etapa 2).
                            from flask import session
                            session['temp_user_id'] = user.id # Guardamos el ID en sesión temporal
                            
                            flash('Contraseña correcta. Por favor, ingrese su código de verificación (2FA).', 'info')
                            return redirect(url_for('mfa_challenge'))
                        
                        # 🎯 SI NO HAY MFA REQUERIDO, PROCEDEMOS CON EL LOGIN NORMAL:
                        
                        # Ejecuta el login de la sesión
                        login_user(user, remember=form.remember_me.data)
                        
                        # Lógica de notificación existente
                        create_notification(user, "Has iniciado sesión correctamente.")
                        db.session.commit()
                        
                        flash('Inicio de sesión exitoso!', 'success')
                        
                        # Redirección por rol (Lógica existente)
                        if user.is_admin:
                            return redirect(url_for('admin.dashboard'))
                        else:
                            return redirect(url_for('customer_dashboard.index'))
                            
                    else:
                        # Mensaje de cuenta desactivada (Lógica existente)
                        flash('Tu cuenta ha sido desactivada.', 'danger')
                else:
                    # Contraseña incorrecta (Lógica existente)
                    flash('Nombre de usuario o contraseña incorrectos.', 'danger')
            else:
                # Usuario no encontrado (Lógica existente)
                flash('Nombre de usuario o contraseña incorrectos.', 'danger')
            
        return render_template('auth.html', title='Iniciar Sesión', form=form, form_register=RegistrationForm())
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        form_register = RegistrationForm()
        if form_register.validate_on_submit():
            existing_user = User.query.filter_by(username=form_register.username.data).first()
            existing_email = User.query.filter_by(email=form_register.email.data).first()

            if existing_user:
                flash('Ese nombre de usuario ya está en uso. Por favor, elige otro.', 'danger')
                return render_template('auth.html', title='Registrarse', form=LoginForm(), form_register=form_register, show_register=True)
            if existing_email:
                flash('Ese correo electrónico ya está registrado. Por favor, usa otro.', 'danger')
                return render_template('auth.html', title='Registrarse', form=LoginForm(), form_register=form_register, show_register=True)

            # Usa la instancia de bcrypt de create_app
        
            hashed_password = bcrypt.generate_password_hash(form_register.password.data).decode('utf-8')
            user = User(username=form_register.username.data, email=form_register.email.data, password=hashed_password, is_active=True, mfa_enable= False, totp_secret=None)
            db.session.add(user)
            db.session.commit()
            
            flash('¡Tu cuenta ha sido creada con éxito! Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
        
        return render_template('auth.html', title='Registrarse', form=LoginForm(), form_register=form_register, show_register=True)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Has cerrado sesión.', 'info')
        return redirect(url_for('login'))





    @app.route('/mfa_challenge', methods=['GET', 'POST'])
    def mfa_challenge():
        from flask import session
        from forms import MFAChallengeForm 
        
        user_id = session.get('temp_user_id')
        if not user_id:
            # No pasó la etapa 1 (contraseña), o la sesión expiró.
            flash('Acceso denegado. Por favor, ingrese sus credenciales nuevamente.', 'danger')
            return redirect(url_for('login')) 
        
        user = User.query.get(user_id)
        
        # Debe tener MFA activo para estar aquí
        if not user or not user.mfa_enable:
            session.pop('temp_user_id', None)
            return redirect(url_for('login')) 

        form = MFAChallengeForm()
        if form.validate_on_submit():
            token = form.token.data
            
            # 🎯 VERIFICACIÓN TOTP
            totp = pyotp.TOTP(user.totp_secret)
            
            if totp.verify(token):
                # 🟢 VERIFICACIÓN EXITOSA: Autenticación completa
                login_user(user)
                session.pop('temp_user_id', None) # Limpiar la sesión temporal
                flash('Verificación de dos factores exitosa. Acceso concedido.', 'success')
                
                # Redirección final por rol
                return redirect(url_for('admin.dashboard') if user.is_admin else url_for('customer_dashboard.index'))
            else:
                flash('Código de verificación incorrecto. Intente de nuevo.', 'danger')

        return render_template('mfa_challenge.html', title='Verificación de Dos Factores', form=form)

    # --- Rutas de la Raíz (DENTRO de create_app) ---
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            if current_user.is_admin:
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('customer_dashboard.index'))
        return redirect(url_for('login'))

    from customer_dashboard.views import customer_dashboard_bp
    from admin.views import admin_bp 
    from visits.views import visits_bp  # Ajusta la ruta si es necesario

    # --- Registro de Blueprints (DENTRO de create_app, y ANTES del return app) ---

    app.register_blueprint(admin_bp)
    app.register_blueprint(customer_dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(visits_bp, url_prefix='/dashboard/visits')
    

    
    
    

    return app 

# --- La instancia de la aplicación que Gunicorn y Flask CLI usarán ---
app = create_app()

# --- Comando CLI para seeding (AFUERA de create_app, usando la 'app' global) ---
@app.cli.command("seed-data")
def seed_data_command():
    """Crea el usuario admin y servicios de ejemplo si no existen."""
    with app.app_context():
        try:
            print("Verificando y creando usuario admin y servicios de ejemplo...")
            # Accede a bcrypt a través de current_app.extensions si se inicializó dentro de create_app
            # Flask-Bcrypt guarda su instancia bajo la clave 'flask-bcrypt' en app.extensions
            

            if not User.query.filter_by(username='admin').first():
                # Usa la instancia de bcrypt obtenida del contexto
                hashed_password = bcrypt.generate_password_hash('admin123').decode('utf-8')
                admin_user = User(username='admin', email='admin@example.com', password=hashed_password, is_admin=True, is_active=True)
                db.session.add(admin_user)
                db.session.commit()
                print("Usuario admin creado automáticamente.")
            else:
                print("El usuario admin ya existe, no se creó.")

            if not Service.query.first():
                service1 = Service(name="Internet Fibra Óptica 300Mbps", description="Conexión de alta velocidad para hogar y teletrabajo.", price=35000.00, type="Internet")
                service2 = Service(name="Telefonía Fija Ilimitada", description="Llamadas ilimitadas a números fijos nacionales.", price=15000.00, type="Telefonía")
                service3 = Service(name="TV Cable Premium", description="Paquete con más de 100 canales HD, incluye deportes y películas.", price=50000.00, type="TV")
                service4 = Service(name="Internet Fibra Óptica 1Gbps", description="Conexión ultra rápida para gaming y streaming 4K.", price=25000.00, type="Internet")
                service5 = Service(name="TV Cable Básico", description="Paquete con 50 canales esenciales.", price=18000.00, type="TV")

                db.session.add_all([service1, service2, service3, service4, service5])
                db.session.commit()
                print("Servicios de ejemplo creados automáticamente.")
            else:
                print("Los servicios ya existen, no se crearon nuevos.")
            print("Proceso de seeding completado.")

        except Exception as e:
            print(f"Error durante el seeding de datos: {e}")
            import traceback
            traceback.print_exc()

# Bloque de ejecución principal para desarrollo local
if __name__ == '__main__': 

    app.run(debug=True)