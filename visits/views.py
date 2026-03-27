# visits/views.py

from flask import Blueprint, render_template, flash, redirect, url_for, request, json,jsonify
from flask_login import login_required, current_user
from models import db, TechnicalVisit, Service, Technician, Notification, CalificacionServicio
from forms import ScheduleVisitForm, ModifyVisitForm, CalificacionServicioForm
from datetime import datetime
from utils import create_notification

visits_bp = Blueprint('visits', __name__, template_folder='../templates/visits')

@visits_bp.route('/')
@login_required
def list_visits():
    user_visits = TechnicalVisit.query.filter_by(user_id=current_user.id).order_by(TechnicalVisit.scheduled_datetime.desc()).all()
    return render_template('list_visits.html', 
                           visits=user_visits, 
                           active_tab='visits')

@visits_bp.route('/schedule', methods=['GET', 'POST'])
@login_required
def schedule_visit():
    form = ScheduleVisitForm()
    form.service.choices = [(s.id, s.name) for s in current_user.services_contracted.all()]

    if form.validate_on_submit():
        try:
            schedule_date = datetime.strptime(form.scheduled_datetime.data, '%Y-%m-%d %H:%M')
            
            new_visit = TechnicalVisit(
                reason=form.reason.data,
                scheduled_datetime=schedule_date,
                status='Agendada',
                user_id=current_user.id,
                service_id=form.service.data
            )
            
            # 1. Añadimos la nueva visita a la sesión
            db.session.add(new_visit)
            
            # 2. GUARDAMOS los cambios en la base de datos. ¡Este es el paso clave!
            db.session.commit()
            
            # 3. AHORA que la visita está guardada, podemos acceder a .service sin problemas
            create_notification(
                current_user, 
                f"Tu visita para el servicio '{new_visit.service.name}' ha sido agendada.",
                link=url_for('visits.list_visits')
            )

            # Volvemos a hacer commit para guardar la notificación que se creó
            db.session.commit()
            
            flash('Tu visita técnica ha sido agendada con éxito.', 'success')
            return redirect(url_for('visits.list_visits'))
            
        except ValueError:
            flash('El formato de fecha y hora es incorrecto. Por favor, usa AAAA-MM-DD HH:MM.', 'danger')
            db.session.rollback() # Revertimos los cambios si hubo un error

    return render_template('schedule_visits.html', 
                           form=form,
                           active_tab='visits')





# --- ¡NUEVA RUTA PARA QUE EL USUARIO COMPLETE LA VISITA! ---
@visits_bp.route('/<int:visit_id>/complete', methods=['POST'])
@login_required
def complete_visit(visit_id):
    """
    Permite a un usuario marcar una de sus visitas como 'Completada' 
    y lo redirige inmediatamente al formulario de calificación (flujo obligatorio).
    """
    visit_to_complete = TechnicalVisit.query.filter_by(id=visit_id, user_id=current_user.id).first_or_404()

    # (El código de validación se mantiene)
    if visit_to_complete.status not in ['Asignada', 'En Camino']:
        flash('Solo puedes marcar como completada una visita que está en curso.', 'warning')
        return redirect(url_for('visits.list_visits'))

    # Cambiar estado
    visit_to_complete.status = 'Completada'
    
    # NOTA: La notificación se realiza DENTRO del try/except para asegurar el commit
    
    try:
        # Hacemos el commit del cambio de estado primero
        db.session.commit()
        
        # Luego creamos la notificación (el commit de la notificación se maneja internamente en utils.py)
        create_notification(
            current_user,
            f"La visita para '{visit_to_complete.service.name}' ha sido marcada como completada. ¡Califica el servicio!",
            # El enlace de la notificación debe ser la URL del formulario
            link=url_for('customer_dashboard.calificar_visita', visit_id=visit_id)
        )
        
        # Mensaje flash para la página de calificación
        flash('¡Servicio completado! Por favor, califique la atención recibida.', 'warning') 
        
        # 🎯 REDIRECCIÓN FORZADA AL FORMULARIO DE CALIFICACIÓN
        return redirect(url_for("customer_dashboard.calificar_visita", visit_id=visit_id))
        
    except Exception as e:
        db.session.rollback()
        # Es posible que el error esté en create_notification si el servicio o su nombre es nulo.
        flash(f'Error al completar la visita y generar notificación: {e}', 'danger')
        return redirect(url_for('visits.list_visits'))

@visits_bp.route('/<int:visit_id>/modify', methods=['GET', 'POST'])
@login_required
def modify_visit(visit_id):
    # 1. Buscamos la visita y nos aseguramos de que sea del usuario y esté 'Agendada'
    visit = TechnicalVisit.query.filter_by(id=visit_id, user_id=current_user.id).first_or_404()
    if visit.status != 'Agendada':
        flash('Solo se pueden modificar las visitas que están agendadas.', 'warning')
        return redirect(url_for('visits.list_visits'))

    form = ModifyVisitForm()
    form.service.choices = [(s.id, s.name) for s in current_user.services_contracted.all()]

    # 2. Si el formulario se envía, actualizamos los datos
    if form.validate_on_submit():
        try:
            visit.service_id = form.service.data
            visit.reason = form.reason.data
            visit.scheduled_datetime = datetime.strptime(form.scheduled_datetime.data, '%Y-%m-%d %H:%M')
            
            create_notification(
                current_user,
                f"Tu visita para '{visit.service.name}' ha sido modificada.",
                link=url_for('visits.list_visits')
            )
            
            db.session.commit()
            flash('La visita ha sido actualizada correctamente.', 'success')
            return redirect(url_for('visits.list_visits'))
        except ValueError:
            flash('El formato de fecha y hora es incorrecto.', 'danger')
    
    # 3. Si es la primera vez que se carga la página, llenamos el formulario con los datos existentes
    elif request.method == 'GET':
        form.service.data = visit.service_id
        form.reason.data = visit.reason
        form.scheduled_datetime.data = visit.scheduled_datetime.strftime('%Y-%m-%d %H:%M')

    return render_template('modify_visit.html', form=form, visit=visit, active_tab='visits')







@visits_bp.route('/<int:visit_id>/cancel', methods=['POST'])
@login_required
def cancel_visit(visit_id):
    visit_to_cancel = TechnicalVisit.query.filter_by(id=visit_id, user_id=current_user.id).first_or_404()
    if visit_to_cancel.status != 'Agendada':
        flash('No se puede cancelar una visita que ya está en camino o completada.', 'warning')
        return redirect(url_for('visits.list_visits'))
    visit_to_cancel.status = 'Cancelada'
    create_notification(
        current_user,
        f"La visita para '{visit_to_cancel.service.name}' ha sido cancelada.",
        link=url_for('visits.list_visits')
    )
    db.session.commit()
    flash('La visita ha sido cancelada correctamente.', 'success')
    return redirect(url_for('visits.list_visits'))

@visits_bp.route('/track/<int:visit_id>')
@login_required
def track_visit(visit_id):
    visit = TechnicalVisit.query.filter_by(id=visit_id, user_id=current_user.id).first_or_404()
    
    # --- Lógica de Calificación (Sprint 7) ---
    form_calificacion = None
    
    # 1. Chequea si la visita está COMPLETED y aún NO tiene calificación (backref)
    if visit.status == 'Completada' and not visit.calificacion:
        # Inicializa el formulario para la plantilla, pasando el ID de la visita al campo oculto
        from forms import CalificacionServicioForm # Mueve esta importación aquí si no está al principio
        form_calificacion = CalificacionServicioForm(visita_id=visit_id)
    # --- Fin Lógica de Calificación ---
    
    # Si la visita no tiene técnico asignado y no está completada, no se puede trackear
    if not visit.technician and visit.status != 'Completada':
        flash('Aún no se ha asignado un técnico a esta visita.', 'warning')
        return redirect(url_for('visits.list_visits'))
    
    # Si está completada y ya calificada, no hay problema, se muestra el estado final.

    return render_template('track_technician.html', 
                            visit=visit, 
                            technician_id=visit.technician.id if visit.technician else None,
                            form_calificacion=form_calificacion, # Nuevo: Pasamos el formulario
                            active_tab='visits')
    
@visits_bp.route('/api/technician/<int:technician_id>/location')
@login_required
def get_technician_location(technician_id):
    # Verificamos que el técnico existe
    Technician.query.get_or_404(technician_id) 
    
    # Coordenadas exactas del centro de Córdoba (Plaza San Martín)
    base_lat = -31.4167  
    base_lon = -64.1833
    
    # Simulación basada en segundos para que el punto "vibre" o se mueva
    # Dividimos por 15000 para que el movimiento sea dentro de unas pocas cuadras
    offset = (datetime.now().second / 15000.0) 
    
    return jsonify({
        'lat': base_lat + offset, 
        'lon': base_lon + offset
    })

@visits_bp.route('/notifications')
@login_required
def notifications():
    user_notifications = current_user.notifications
    for notif in user_notifications:
        notif.is_read = True
    db.session.commit()
    return render_template('notifications.html', 
                           notifications=user_notifications,
                           active_tab='notifications')



@visits_bp.route('/api/unread_notifications_count')
@login_required
def unread_notifications_api():
    """
    API que devuelve el número de notificaciones no leídas para el usuario actual.
    """
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})


# --- ¡NUEVA RUTA PARA ELIMINAR NOTIFICACIONES! ---
@visits_bp.route('/notifications/<int:notif_id>/delete', methods=['POST'])
@login_required
def delete_notification(notif_id):
    """
    Permite a un usuario eliminar una de sus propias notificaciones.
    """
    # Se busca la notificación asegurando que pertenezca al usuario logueado
    notif_to_delete = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first_or_404()
    
    db.session.delete(notif_to_delete)
    db.session.commit()
    
    return redirect(url_for('visits.notifications'))
