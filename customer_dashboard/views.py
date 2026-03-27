from flask import Blueprint, render_template, flash, redirect, session, url_for, request, Response, send_file,jsonify, abort,current_app
from flask_wtf.csrf import validate_csrf
from flask_login import login_required, current_user

from sqlalchemy.exc import IntegrityError

from sqlalchemy import extract,desc, func
from datetime import datetime, timedelta
from datetime import timedelta 
from models import db, User, Service, Invoice , ConfiguracionWiFi, Peticion, CalificacionServicio, TechnicalVisit
from forms import ContractServiceForm, ModifyServiceForm, ChangePasswordForm, ModificarWiFiForm, PeticionPlanForm, CalificacionServicioForm

import pyotp
import qrcode
import json
import base64
from fpdf import FPDF 
from utils import create_notification
import os
import io
from io import BytesIO

customer_dashboard_bp = Blueprint('customer_dashboard', __name__, template_folder='../templates/customer_dashboard')

# --- RUTA PRINCIPAL DEL PANEL ---
@customer_dashboard_bp.route('/')
@customer_dashboard_bp.route('/index')
@login_required
def index():
    
    


    
    
    # 2. DATOS DE SERVICIOS (USO EN RESUMEN RÁPIDO Y GRÁFICO DE BARRAS)
    user_services = current_user.services_contracted.all()
    total_saldo = sum(service.price for service in user_services)
    servicios_activos_count = len(user_services)
    
    # 3. DATOS DE FACTURACIÓN (USO EN GRÁFICO DE PAGOS)
    # 4. DATOS DE TABLA (Ultimas facturas, etc.)
    ultimas_facturas = Invoice.query.filter_by(user_id=current_user.id).order_by(desc(Invoice.billing_date)).limit(5).all()
    all_services = Service.query.all()
    contracted_service_ids = {service.id for service in user_services}
    
    return render_template(
        'dashboard_index.html', 
        active_tab='dashboard',
        user_services=user_services,
        total_saldo=total_saldo,
        servicios_activos_count=servicios_activos_count,
        all_services=all_services,
        contracted_service_ids=contracted_service_ids,
        ultimas_facturas = ultimas_facturas
        
    )

def get_user_monthly_total(user):
    """Calcula el monto total de los servicios contratados por el usuario."""
    
    # Ejemplo de lógica:
    total_amount = sum(service.price for service in user.services_contracted.all())
    return total_amount


def create_initial_invoice(user):
    """
    Crea una nueva fila en la tabla Invoice con estado 'PENDIENTE'.
    Retorna la nueva factura o None si falla.
    """
    try:
        # 1. Verificar si ya existe una factura pendiente (para evitar duplicados)
        existing_pending_invoice = Invoice.query.filter(
            Invoice.user_id == user.id,
            Invoice.status == 'PENDIENTE'
        ).first()

        if existing_pending_invoice:
            print(f"DEBUG: Ya existe factura pendiente para user {user.id}")
            return existing_pending_invoice
            
        # 2. Calcular el monto total
        amount = get_user_monthly_total(user)
        
        if amount <= 0:
            print(f"ADVERTENCIA: Monto de servicio cero para user {user.id}. No se crea factura.")
            return None # No crea factura si no hay costo

        # 3. Crear el nuevo objeto Invoice
        new_invoice = Invoice(
            amount=amount,
            billing_date=datetime.now(),
            user_id=user.id,
            status='PENDIENTE',
            external_reference=None
        )
        
        db.session.add(new_invoice)
        db.session.commit()
        
        print(f"INFO: Factura PENDIENTE creada exitosamente para user {user.id}")
        return new_invoice

    except Exception as e:
        # 🚨 Si algo falla (ej. error de columna o db no disponible), se hace ROLLBACK
        db.session.rollback()
        print(f"*** ERROR GRAVE AL CREAR FACTURA PARA USER {user.id}: {e} ***")
        # Podemos incluso levantar la excepción para verla en el servidor log
        # raise 
        return None




@customer_dashboard_bp.route('/invoice/download')
@login_required
def download_invoice():
  
    user_obj = None
    user_services = []

    if current_app.config.get('SIMULATION_MODE', False):
    
        user_services_data = [
            {'name': 'Internet Fibra Óptica 300Mbps', 'description': 'Alta velocidad simulada', 'price': 35000.00},
            {'name': 'TV Cable Premium', 'description': 'Full HD simulada', 'price': 25000.00},
        ]
        class MockService: # Objeto simple para simular un servicio
            def __init__(self, name, description, price):
                self.name = name
                self.description = description
                self.price = price
        user_services = [MockService(**s) for s in user_services_data]

        user_mock_attrs = { # Atributos simulados para el usuario
            'username': current_user.username if hasattr(current_user, 'username') else 'ClienteDemo',
            'email': current_user.email if hasattr(current_user, 'email') else 'cliente.demo@example.com',
            'id': current_user.id if hasattr(current_user, 'id') else 101
        }
        user_obj = type('User', (object,), user_mock_attrs)() # Crea un objeto usuario simulado
        # --- FIN DATOS DE SIMULACIÓN ---
    else: # Modo NO simulación (base de database real)
        if not hasattr(current_user, 'services_contracted'):
            flash('Error: No se pueden obtener los servicios del usuario.', 'danger')
            return redirect(url_for('customer_dashboard.index'))

        user_services = current_user.services_contracted.all()
        user_obj = current_user # El usuario logueado

    if not user_services and not current_app.config.get('SIMULATION_MODE', False):
        flash('No tienes servicios contratados actualmente para generar una factura.', 'warning')
        return redirect(url_for('customer_dashboard.index'))

    # --- Cálculos y detalles de la factura ---
    total_amount = sum(service.price for service in user_services)
    invoice_details = {
        'number': f"INV-{datetime.now().strftime('%Y%m%d')}-{user_obj.id}",
        'date': datetime.now().strftime('%Y-%m-%d'),
        'due_date': (datetime.now() + timedelta(days=15)).strftime('%Y-%m-%d') # Ejemplo
    }
    company_details = { 
        'name': 'Customer Portal Telecom S.A.',
        'address_line1': 'Av. Siempreviva 742',
        'address_line2': 'Springfield, CP 12345, País',
        'phone': '+00 123 456 7890',
        'email': 'facturacion@tuportal.com',
        'cuit': 'CUIT: 30-12345678-9' # Ejemplo de CUIT
    }
    # --- FIN Cálculos y detalles ---

    # ==============================================
    # === INICIO DE GENERACIÓN DE PDF CON FPDF2 ===
    pdf = FPDF(orientation='P', unit='mm', format='A4') # P: Portrait, mm: milímetros, A4
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15) # Margen inferior para evitar cortes

    # --- Márgenes Generales ---
    page_width = pdf.w - 20 # Ancho de página menos márgenes (10mm de cada lado)
    pdf.set_left_margin(10)
    pdf.set_right_margin(10)
    pdf.set_top_margin(10)

    # --- Sección 1: Logo y Título "FACTURA" ---
    logo_filename = 'custom.png' 
   
    logo_path_local = os.path.join(current_app.root_path, 'static', 'imgs', logo_filename)

    if os.path.exists(logo_path_local):
        pdf.image(logo_path_local, x=10, y=12, w=45) 

    pdf.set_font('Arial', 'B', 24) # Fuente para el título "FACTURA"
    pdf.set_xy(page_width - 70, 15) # Posiciona el título a la derecha
    pdf.cell(70, 10, 'FACTURA', 0, 1, 'R')

    pdf.set_font('Arial', '', 9) # Fuente más pequeña para los detalles de la factura
    pdf.set_xy(page_width - 70, pdf.get_y())
    pdf.cell(70, 5, f"Nro: {invoice_details['number']}", 0, 1, 'R')
    pdf.set_xy(page_width - 70, pdf.get_y())
    pdf.cell(70, 5, f"Emisión: {invoice_details['date']}", 0, 1, 'R')
    pdf.set_xy(page_width - 70, pdf.get_y())
    pdf.cell(70, 5, f"Vencimiento: {invoice_details['due_date']}", 0, 1, 'R')

    pdf.ln(15) # Espacio después del encabezado

    # --- Sección 2: Datos de la Empresa y Cliente ---
    current_y_info = pdf.get_y()
    col_width_info = page_width / 2 - 5 # Ancho para cada columna de info (Empresa/Cliente)

    # Datos Empresa (Izquierda)
    pdf.set_font('Arial', 'B', 10)
    pdf.multi_cell(col_width_info, 5, company_details['name'], 0, 'L')
    pdf.set_font('Arial', '', 9)
    pdf.set_x(10) # Vuelve al margen izquierdo
    pdf.multi_cell(col_width_info, 5, f"{company_details['address_line1']}\n{company_details['address_line2']}", 0, 'L')
    pdf.set_x(10)
    pdf.multi_cell(col_width_info, 5, f"Tel: {company_details['phone']}", 0, 'L')
    if company_details.get('email'):
        pdf.set_x(10)
        pdf.multi_cell(col_width_info, 5, f"Email: {company_details['email']}", 0, 'L')
    if company_details.get('cuit'):
        pdf.set_x(10)
        pdf.multi_cell(col_width_info, 5, company_details['cuit'], 0, 'L')

    # Datos Cliente (Derecha)
    pdf.set_y(current_y_info) # Vuelve a la Y inicial de esta sección
    pdf.set_x(10 + col_width_info + 10) # Posiciona a la derecha (10 de margen izq + ancho col + 10 de espaciado)
    pdf.set_font('Arial', 'B', 10)
    pdf.multi_cell(col_width_info, 5, "Facturado a:", 0, 'L')
    pdf.set_x(10 + col_width_info + 10)
    pdf.set_font('Arial', '', 9)
    pdf.multi_cell(col_width_info, 5, user_obj.username, 0, 'L')
    pdf.set_x(10 + col_width_info + 10)
    pdf.multi_cell(col_width_info, 5, user_obj.email, 0, 'L')

    pdf.ln(10) # Espacio después de la info

    # --- Sección 3: Tabla de Servicios ---
    pdf.set_font('Arial', 'B', 10)
    pdf.set_fill_color(220, 220, 220) # Gris claro para encabezado de tabla
    line_height_table = 7

    # Encabezados de la tabla
    pdf.cell(page_width * 0.7, line_height_table, 'Descripción del Servicio', 1, 0, 'C', True) # 70% del ancho
    pdf.cell(page_width * 0.3, line_height_table, 'Precio', 1, 1, 'C', True) # 30% del ancho, con salto de línea

    pdf.set_font('Arial', '', 9)
    pdf.set_fill_color(255, 255, 255) # Blanco para las celdas de datos
    if user_services:
        for service in user_services:
            # Guardar Y actual antes de multi_cell para la descripción
            y_before_desc = pdf.get_y()
            pdf.multi_cell(page_width * 0.7, line_height_table, f"{service.name}\n{service.description}", 1, 'L', True)
            y_after_desc = pdf.get_y()
            height_of_desc_cell = y_after_desc - y_before_desc

            # Celda de precio (debe tener la misma altura que la celda de descripción)
            # Volver a la posición X inicial de la columna de precio
            pdf.set_xy(10 + (page_width * 0.7), y_before_desc)
            pdf.cell(page_width * 0.3, height_of_desc_cell, f"${service.price:,.2f}", 1, 1, 'R', True)
    else:
        pdf.cell(page_width, line_height_table, 'No hay servicios contratados.', 1, 1, 'C', True)

    pdf.ln(1) # Pequeño espacio antes del total

    # --- Sección 4: Total ---
    pdf.set_font('Arial', 'B', 11)
    total_label_width = page_width * 0.7 # Ancho para la etiqueta "TOTAL"
    total_value_width = page_width * 0.3 # Ancho para el valor del total

    pdf.set_x(10 + total_label_width) # Alinear a la derecha
    pdf.cell(total_value_width, 8, f"TOTAL: ${total_amount:,.2f}", 1, 1, 'R')

    pdf.ln(10) # Espacio

    # --- Sección 5: Pie de página simple ---
    pdf.set_font('Arial', 'I', 8) # Fuente itálica y pequeña
    pdf.cell(0, 10, 'Gracias por utilizar nuestros servicios.', 0, 1, 'C')
    # ============================================
    # === FIN DE GENERACIÓN DE PDF CON FPDF2 ===
    # ============================================

    # --- LÓGICA DE ENVÍO CORREGIDA Y FINAL ---
    # 1. Crear un buffer de bytes en memoria
    pdf_buffer = BytesIO(pdf.output())

    # 2. Mover el "cursor" al inicio del buffer
    pdf_buffer.seek(0)

    # 3. Enviar el archivo usando send_file
    download_filename = f"factura_{user_obj.username}_{invoice_details['date']}.pdf" 

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=download_filename,
        mimetype='application/pdf'
    )


# --- RUTAS DE GESTIÓN DE USUARIO ---
@customer_dashboard_bp.route('/profile')
@login_required
def view_profile():
    user_services = current_user.services_contracted.all()
    return render_template('profile.html', user=current_user, user_services=user_services, active_tab='profile')

@customer_dashboard_bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.old_password.data):
            flash('La contraseña actual es incorrecta.', 'danger')
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Tu contraseña ha sido actualizada exitosamente.', 'success')
            return redirect(url_for('customer_dashboard.view_profile'))
            
    return render_template('change_password.html', form=form, active_tab='change_password')

# --- RUTAS DE GESTIÓN DE SERVICIOS ---
@customer_dashboard_bp.route('/contract_service')
@login_required
def customer_contract_service():
    all_services = Service.query.all()
    contracted_service_ids = {service.id for service in current_user.services_contracted.all()}
    return render_template(
        'contract_service.html', 
        active_tab='contract_service',
        all_services=all_services,
        contracted_service_ids=contracted_service_ids
    )

@customer_dashboard_bp.route('/add_service/<int:service_id>', methods=['POST'])
@login_required
def add_service(service_id):
    service_to_add = Service.query.get_or_404(service_id)
    if service_to_add not in current_user.services_contracted.all():
        current_user.services_contracted.append(service_to_add)
        
        db.session.commit()
        
        factura_creada = create_initial_invoice(current_user)
        base_message = f'El servicio "{service_to_add.name}" ha sido contratado.'
        if factura_creada:
            # Éxito total: Contratación y Factura generada
            flash('✅ Se ha generado su factura pendiente de pago.', 'success')
        else:
            # Advertencia: Contratación OK, pero la factura falló o ya existía.
            flash(f'⚠️ {base_message} Pero la factura no se pudo generar (Revise el log).', 'warning')
    else:
        flash('Ya tienes este servicio contratado.', 'info')
    return redirect(url_for('customer_dashboard.customer_contract_service'))

@customer_dashboard_bp.route('/service_management')
@login_required
def service_management():
    user_services = current_user.services_contracted.all()
    return render_template('service_management.html', user_services=user_services, active_tab='service_management')

@customer_dashboard_bp.route('/services/modify/<int:service_id>', methods=['GET', 'POST'])
@login_required
def modify_service(service_id):
    service_to_modify = Service.query.get_or_404(service_id)
    if service_to_modify not in current_user.services_contracted.all():
        flash('No tienes permiso para modificar este servicio.', 'danger')
        return redirect(url_for('customer_dashboard.service_management'))

    form = ModifyServiceForm()
    available_plans = Service.query.filter_by(type=service_to_modify.type).all()
    form.plan.choices = [(s.id, f"{s.name} (${s.price:,.2f})") for s in available_plans]

    if form.validate_on_submit():
        new_plan_service_id = form.plan.data
        new_plan_service = Service.query.get(new_plan_service_id)

        
        # Verificamos si el nuevo plan ya está contratado por el usuario
        if new_plan_service in current_user.services_contracted.all() and new_plan_service.id != service_to_modify.id:
            flash(f'No se puede cambiar al plan "{new_plan_service.name}" porque ya lo tienes contratado.', 'warning')
            return redirect(url_for('customer_dashboard.service_management'))


        if new_plan_service and new_plan_service.id != service_to_modify.id:
            current_user.services_contracted.remove(service_to_modify)
            current_user.services_contracted.append(new_plan_service)
            create_notification(
                current_user,
                f"Has modificado tu plan a'{new_plan_service.name}'.",
                link=url_for('customer_dashboard.service_management')
            )
            db.session.commit()
            flash(f'Tu servicio ha sido actualizado a "{new_plan_service.name}"!', 'success')
        else:
            flash('No se realizaron cambios porque seleccionaste el mismo plan.', 'info')
        
        return redirect(url_for('customer_dashboard.service_management'))

    elif request.method == 'GET':
        form.plan.data = service_to_modify.id

    return render_template('modify_service.html', 
                           form=form, 
                           service=service_to_modify, 
                           active_tab='service_management')
    
    
    
@customer_dashboard_bp.route('/services/unsubscribe/<int:service_id>', methods=['POST'])
@login_required
def unsubscribe_service(service_id):
    service_to_unsubscribe = Service.query.get_or_404(service_id)
    if service_to_unsubscribe not in current_user.services_contracted.all():
        flash('No puedes dar de baja este servicio.', 'danger')
    else:
        current_user.services_contracted.remove(service_to_unsubscribe)
        create_notification(
            current_user,
            f"Has dado de baja el servicio'{service_to_unsubscribe.name}'."
        )
        db.session.commit()
        flash(f'El servicio "{service_to_unsubscribe.name}" ha sido dado de baja.', 'success')
    return redirect(url_for('customer_dashboard.service_management'))

# --- RUTAS DE API PARA GRÁFICOS ---
@customer_dashboard_bp.route('/api/billing_history')
@login_required
def billing_history_api():
    # ... (lógica del historial de facturación) ...
    return jsonify({'labels': [], 'data': []}) # Ejemplo

@customer_dashboard_bp.route('/api/user_peticiones_summary')
@login_required
def user_peticiones_summary_api():
    """Devuelve el conteo de peticiones (pedidos de packs) del usuario actual agrupadas por estado."""
    
    peticion_stats = db.session.query(
        Peticion.estado, 
        func.count(Peticion.id).label('count')
    ).filter(Peticion.user_id == current_user.id).group_by(Peticion.estado).all()
    
    # 🎯 DEFINICIÓN DE COLORES EN MAYÚSCULAS 🎯
    color_map = {
        'APLICADO': 'rgba(40, 167, 69, 0.9)',   # Verde (Aplicado/Aceptado)
        'PENDIENTE': 'rgba(255, 193, 7, 0.9)',  # Amarillo (Pendiente)
        'RECHAZADO': 'rgba(220, 53, 69, 0.9)',  # Rojo (Rechazado)
        'ELIMINADA': 'rgba(108, 117, 125, 0.6)' # Gris (Eliminada/Otros)
    }
    
    border_map = {
        'APLICADO': 'rgba(40, 167, 69, 1)',   
        'PENDIENTE': 'rgba(255, 193, 7, 1)',  
        'RECHAZADO': 'rgba(220, 53, 69, 1)',  
        'ELIMINADA': 'rgba(108, 117, 125, 1)'
    }

    labels = []
    data = []
    background_colors = []
    border_colors = []

    for stat in peticion_stats:
        # 🎯 NORMALIZACIÓN CRÍTICA: Convierte el estado de la BD a MAYÚSCULAS 🎯
        estado_normalizado = stat.estado.upper()
        
        labels.append(stat.estado) # Mantenemos el label original para la leyenda
        data.append(stat.count)
        
        # Obtenemos los colores usando la clave normalizada
        background_colors.append(color_map.get(estado_normalizado, 'rgba(108, 117, 125, 0.6)'))
        border_colors.append(border_map.get(estado_normalizado, 'rgba(108, 117, 125, 1)'))
        
    return jsonify({
        'labels': labels,
        'data': data,
        'background_colors': background_colors,
        'border_colors': border_colors
    })


@customer_dashboard_bp.route('/api/user_visits_summary')
@login_required
def user_visits_summary_api():
    """Devuelve el conteo de visitas del usuario actual agrupadas por estado."""
    
    # Consulta: Filtrar por el usuario actual, agrupar por estado y contar
    visit_stats = db.session.query(
        TechnicalVisit.status, 
        func.count(TechnicalVisit.id).label('count')
    ).filter(TechnicalVisit.user_id == current_user.id).group_by(TechnicalVisit.status).all()
    
    # Formatear la data
    labels = [stat.status for stat in visit_stats]
    data = [stat.count for stat in visit_stats]
    
    # Definir colores para cada estado (para mejor visualización)
    color_map = {
        'Completada': '#198754',    # Verde (Éxito)
        'Agendada': '#ffc107',      # Amarillo (Pendiente)
        'En Camino': '#0d6efd',     # Azul (En progreso)
        'Cancelada': '#dc3545',     # Rojo (Fallo)
    }

    return jsonify({
        'labels': labels,
        'data': data,
        'background_colors': [color_map.get(label, '#6c757d') for label in labels]
    })


@customer_dashboard_bp.route('/api/user_rating_history')
@login_required
def user_rating_history_api():
    """Devuelve el historial de calificaciones del servicio del usuario actual."""
    
    try:
        # Consulta: Obtener las últimas 5 calificaciones del usuario, ordenadas por fecha descendente
        ratings = CalificacionServicio.query.filter_by(user_id=current_user.id).order_by(
            desc(CalificacionServicio.fecha_calificacion)
        ).limit(5).all()
        
        # Invertir el orden para que la tendencia vaya de izquierda (viejo) a derecha (nuevo)
        ratings.reverse()
        
        labels = []
        values = []
        
        for r in ratings:
            # Columna 'fecha_calificacion' de la BD
            fecha_str = r.fecha_calificacion.strftime('%d/%b')
            labels.append(fecha_str) 
            
            # Columna 'puntuacion' de la BD
            values.append(r.puntuacion)

        # Devolver JSON con las claves 'labels' y 'values' que espera el JS
        return jsonify({
            'labels': labels,
            'values': values 
        })
        
    except Exception as e:
        # Esto atrapará errores de importación o de consulta SQL
        print(f"ERROR EN API user_rating_history_api: {e}")
        # Devuelve un JSON vacío para que el frontend no falle
        return jsonify({'labels': [], 'values': []}), 500

@customer_dashboard_bp.route('/api/service_status_chart')
@login_required
def service_status_chart_api():
    all_services = Service.query.order_by(Service.price.desc()).all()
    contracted_services = current_user.services_contracted.all()
    contracted_service_ids = {service.id for service in contracted_services}
    labels = [service.name for service in all_services]
    prices = [service.price for service in all_services]
    is_contracted_list = [1 if service.id in contracted_service_ids else 0 for service in all_services]
    return jsonify({'labels': labels, 'prices': prices, 'is_contracted': is_contracted_list})



@customer_dashboard_bp.route('/modificar-wifi/<int:service_id>', methods=['GET', 'POST'])
@login_required
def modificar_wifi(service_id):
    # 1. Verificar que el servicio existe y pertenece al usuario actual
    servicio = Service.query.get_or_404(service_id)
    if servicio not in current_user.services_contracted.all():
        flash('Acceso denegado. El servicio no le pertenece.', 'danger')
        return redirect(url_for('customer_dashboard.index')) # Redirige a la página principal del dashboard

    # 2. Obtener la configuración WiFi
    config = ConfiguracionWiFi.query.filter_by(service_id=service_id).first()
    
    if not config:
        # Esto no debería pasar en un sistema real, pero es una buena práctica:
        flash('Configuración de WiFi no encontrada para este servicio.', 'danger')
        return redirect(url_for('customer_dashboard.index'))

    form = ModificarWiFiForm()

    if form.validate_on_submit():
        # Lógica de Modificación (RD: Modificar SSID y Clave)
        
        # 3. Simulación de la comunicación con el equipo
        # En una implementación real, aquí iría la API call o script
        # para enviar los nuevos valores al router/ONT.
        
        # 4. Actualizar la base de datos
        config.ssid_2g = form.ssid_2g.data
        config.clave_2g = form.clave_2g.data
        config.ssid_5g = form.ssid_5g.data
        config.clave_5g = form.clave_5g.data
        
        try:
            db.session.commit()
            flash('Configuración WiFi actualizada con éxito. Los cambios se aplicarán en breve.', 'success')
            # Redirige de vuelta con los nuevos datos
            return redirect(url_for('customer_dashboard.modificar_wifi', service_id=service_id))
        except Exception as e:
            db.session.rollback()
            flash('Ocurrió un error al guardar la configuración.', 'danger')

    elif request.method == 'GET':
        # Lógica de Consulta (RD: Consultar datos técnicos)
        # 5. Rellenar el formulario con los datos actuales
        form.ssid_2g.data = config.ssid_2g
        # No rellenamos la clave por seguridad, aunque Flask-WTF lo puede hacer con PasswordField
        form.ssid_5g.data = config.ssid_5g
        
    # Aquí se puede también obtener los datos del plan de TV si el servicio es de TV, 
    # pero para simplicidad, esta ruta solo maneja la configuración WiFi.
    
    return render_template('customer_dashboard/modify_wifi.html', 
                           title=f'Configuración WiFi - {servicio.name}', 
                           form=form,
                           servicio=servicio,
                           config=config) # Pasamos la configuración para mostrar los datos técnicos

@customer_dashboard_bp.route('/solicitar-plan', methods=['GET', 'POST'])
@login_required
def solicitar_plan():
    form = PeticionPlanForm()
    
    if form.validate_on_submit():
        
        # 1. Procesar las múltiples selecciones del SelectMultipleField
        # La data viene como una lista de strings (ej: ['Pack Futbol', 'Netflix Estándar'])
        packs_seleccionados = form.pack_solicitado.data
        
        # 2. Convertir la lista a una cadena para guardar en la BD (Peticion.detalle_plan)
        # Usamos una coma para separar los elementos seleccionados
        lista_packs_str = ", ".join(packs_seleccionados)
        
        # 3. Combinar las selecciones con los detalles adicionales del cliente
        detalle_adicional_str = form.detalle_adicional.data or "Ninguno"
        
        detalle_plan_final = f"Packs Solicitados: {lista_packs_str} | Comentarios: {detalle_adicional_str}"
        
        # 4. Crear nueva petición con la cadena final
        peticion = Peticion(
            user_id=current_user.id,
            tipo_peticion=form.tipo_peticion.data,
            detalle_plan=detalle_plan_final, # <-- Cadena con múltiples servicios
            estado='Pendiente'
        )
        
        try:
            db.session.add(peticion)
            db.session.commit()
            flash('Su solicitud ha sido enviada al administrador con éxito.', 'success')
            
            
            return redirect(url_for('customer_dashboard.ver_peticiones'))
        except Exception as e:
            db.session.rollback()
            flash('Ocurrió un error al registrar su solicitud.', 'danger')
            
    # 2. (RD: Consultar estado actualizado de sus peticiones enviadas)
    # Mostraremos el historial de peticiones en una ruta separada o en esta misma. 
    # Usaremos una ruta separada para limpiar la lógica.
    
    return render_template('customer_dashboard/request_plan.html', title='Solicitar Nuevo Plan', form=form)

@customer_dashboard_bp.route('/peticiones-enviadas')
@login_required
def ver_peticiones():
    # Obtiene todas las peticiones del usuario, incluyendo eliminadas o rechazadas si el modelo lo permite
    peticiones = Peticion.query.filter_by(user_id=current_user.id).order_by(Peticion.fecha_creacion.desc()).all()
    
    return render_template('customer_dashboard/peticiones_enviadas.html', title='Mis Solicitudes de Planes', peticiones=peticiones)


@customer_dashboard_bp.route('/calificar-visita/<int:visit_id>', methods=['GET', 'POST'])
@login_required
def calificar_visita(visit_id):
    # 1. Buscar la visita técnica
    visita = TechnicalVisit.query.get_or_404(visit_id)
    
    # 2. Criterio de Aceptación: La visita debe estar 'Completada' y pertenecer al usuario
    if visita.user_id != current_user.id or visita.status != 'Completada':
        flash('Esta visita no está lista para ser calificada o no le pertenece.', 'danger')
        return redirect(url_for('customer_dashboard.dashboard_index'))
    
    # 3. Prevenir doble calificación
    if visita.calificacion: # Usa el backref que definimos en models.py
        flash('Esta visita ya ha sido calificada.', 'info')
        return redirect(url_for('customer_dashboard.index'))
        
    form = CalificacionServicioForm(visita_id=visit_id) # Inicializa el campo oculto

    if form.validate_on_submit():
        # 4. Registrar la calificación (RD: Emitir mini-formulario y registrar)
        calificacion = CalificacionServicio(
            user_id=current_user.id,
            technical_visit_id=visita.id,
            puntuacion=form.puntuacion.data,
            satisfaccion_valida=form.satisfaccion_valida.data,
            comentarios=form.comentarios.data
        )
        
        try:
            db.session.add(calificacion)
            db.session.commit()
            flash('¡Gracias por su feedback! Su calificación ha sido registrada.', 'success')
            return redirect(url_for('customer_dashboard.index'))
        except IntegrityError:
            db.session.rollback()
            flash('Error: Esta visita ya fue calificada previamente.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash('Ocurrió un error al registrar su calificación.', 'danger')

    return render_template('customer_dashboard/calificar_visita.html', 
                           title='Calificar Servicio Técnico', 
                           form=form, 
                           visita=visita)
    
    
    
    
@customer_dashboard_bp.route('/mfa/setup', methods=['GET', 'POST'])
@login_required
def mfa_setup():
    # Evitar que el usuario configure MFA si ya está activo
    if current_user.mfa_enable:
        flash("La autenticación de dos factores ya está activa.", 'info')
        return redirect(url_for('customer_dashboard.view_profile')) # Redirige al perfil

    # Si no tiene clave secreta, la generamos
    if not current_user.totp_secret:
        # Generar una clave secreta Base32 aleatoria
        current_user.totp_secret = pyotp.random_base32()
        db.session.commit() # Guardar la clave secreta en la DB

    # Generar la URI de provisión (el contenido del QR)
    # Formato: otpauth://totp/App:User?secret=KEY&issuer=App
    uri = pyotp.totp.TOTP(current_user.totp_secret).provisioning_uri(
        name=current_user.email,
        issuer_name="CustomerPortalTelecom" # Nombre que aparecerá en Google Authenticator
    )

    # Generar el código QR como imagen en base64 para mostrarlo en HTML
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    # Usamos el formulario de desafío MFA para la confirmación
    from forms import MFAChallengeForm
    form = MFAChallengeForm()

    if form.validate_on_submit():
        token = form.token.data
        totp = pyotp.TOTP(current_user.totp_secret)
        
        if totp.verify(token):
            # Activación exitosa
            current_user.mfa_enable = True
            db.session.commit()
            flash("La autenticación de dos factores ha sido ACTIVADA exitosamente.", 'success')
            return redirect(url_for('customer_dashboard.view_profile'))
        else:
            flash("El código ingresado es incorrecto. Intente de nuevo.", 'danger')

    return render_template('customer_dashboard/mfa_setup.html', 
                           title='Activar Seguridad 2FA', 
                           qr_base64=qr_base64,
                           form=form)
    
    
    # Simulación de SDK de Mercado Pago (MP)
def generate_mp_checkout_url(invoice_id, amount):
    """
    Genera una URL EXTERNA de MP de prueba que contiene un enlace de retorno
    a nuestra ruta de conciliación (handle_mp_return).
    """
    
    # 1. Definir los parámetros de éxito que MP devolvería
    status_success = 'approved' 
    mp_trans_id = f"TRANS_{invoice_id}_{amount}" # ID de transacción único
    
    # 2. Construir la URL de RETORNO completa y absoluta
    return_url_success = url_for('customer_dashboard.handle_mp_return', 
                                 invoice_id=invoice_id, 
                                 status=status_success, 
                                 external_reference=mp_trans_id, 
                                 _external=True) # _external=True es CRÍTICO para URLs externas

    
    
    # Por ahora, simplemente devolveremos el link de retorno para la prueba de concepto
    # avanzada, simulando que el usuario acaba de pagar y es redirigido.
    return return_url_success # Simula la redirección de MP con el resultado exitoso

@customer_dashboard_bp.route('/pay/invoice/<int:invoice_id>')
@login_required
def initiate_payment(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    
    if invoice.user_id != current_user.id:
        abort(403) 
        
    # 1. 🎯 Cambiar el estado de la factura 🎯
    invoice.status = 'PAGADA' # O 'ACTIVA', según tu nomenclatura
    
    # 2. Guardar el cambio en la base de datos
    db.session.commit() 
    
    flash(f"¡Pago de ${invoice.amount:.2f} realizado con éxito!", 'success')
    return redirect(url_for('customer_dashboard.index'))


# ⚠️ C. Lógica de Conciliación (Webhook/Success Return)
@customer_dashboard_bp.route('/pay/conciliate/<int:invoice_id>')
@login_required
def handle_mp_return(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Asumimos que Mercado Pago devuelve un 'status' y una 'external_reference' (transaction_id)
    # Requerimiento: Conciliación y Registro

    payment_status = request.args.get('status') # Ej: 'approved', 'pending', 'rejected'
    mp_trans_id = request.args.get('external_reference') or 'TRANS_ID_FAKE'
    
    if invoice.status != 'PENDIENTE':
        session['payment_result'] = {'message': f"ℹ️ La factura N°{invoice.id} ya fue procesada.", 'category': 'info'}
        return redirect(url_for('customer_dashboard.index'))
    
    if payment_status == 'approved':
        invoice.status = 'Pagada'
        invoice.external_reference = mp_trans_id
        
        # Lógica de rehabilitación de servicio (si aplica)
        # service = Service.query.get(invoice.service_id)
        # service.is_suspended = False 
        db.session.commit()
        flash("¡Pago completado! Su factura ha sido marcada como PAGADA con éxito.", 'success')

    elif payment_status == 'rejected':
        # Requerimiento: Manejo de Fallas        
        flash("El pago falló. Verifique su tarjeta e intente de nuevo.", 'danger')
        
    else:
        session['payment_result'] = {
                    'message': "⚠️ El estado del pago es incierto. Verifique su estado.", 
                    'category': 'warning'}
    return redirect(url_for('customer_dashboard.index'))



@customer_dashboard_bp.route('/checkout/mp/<int:invoice_id>')
@login_required
def show_mp_simulation(invoice_id):
    """Renderiza la página de simulación de pago (mp_checkout_simulation.html)."""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Comprobar la propiedad y el estado
    if invoice.user_id != current_user.id or invoice.status != 'PENDIENTE':
        abort(403) 
        
    # Renderiza la plantilla que adjuntaste
    return render_template('customer_dashboard/mp_checkout_simulation.html', invoice=invoice)



@customer_dashboard_bp.route('/iniciar-pago-pendiente')
@login_required
def iniciar_pago_pendiente():
    from sqlalchemy import asc
    
    # 1. Obtener la factura pendiente
    factura_pendiente = Invoice.query.filter(
        Invoice.user_id == current_user.id,
        Invoice.status == 'PENDIENTE'
    ).order_by(Invoice.billing_date.asc()).first()
    
    if factura_pendiente:
        # 2. Calcular el monto basado en los servicios contratados
        # Llama a la función que ya tienes implementada en tu código de PDF:
        new_amount = get_user_monthly_total(current_user) 
        
        # 3. Actualizar la factura pendiente con el monto calculado y guardar
        if factura_pendiente.amount != new_amount:
            factura_pendiente.amount = new_amount
            db.session.commit()
        
        # 4. Redirige a la función de pago
        return redirect(url_for('customer_dashboard.show_mp_simulation', invoice_id=factura_pendiente.id))
    
    if not factura_pendiente:
        flash("¡Felicidades! No tienes facturas pendientes de pago.", 'success')
        return redirect(url_for('customer_dashboard.index'))
    
    
@customer_dashboard_bp.route('/facturacion/historial')
@login_required
def historial_facturacion():
    """
    Muestra el listado de todas las facturas del usuario, pagadas y pendientes.
    """
    # Consulta: Obtiene todas las facturas del usuario, ordenadas por fecha de emisión descendente
    facturas = Invoice.query.filter_by(user_id=current_user.id).order_by(desc(Invoice.billing_date)).all()
    
    return render_template('customer_dashboard/client_invoices.html', 
                           title='Historial de Facturación y Pagos',
                           facturas=facturas,
                           active_tab='facturacion')