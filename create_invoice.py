import sys
import os
from datetime import datetime

# --- CONFIGURACIÓN CRÍTICA ---
# Agrega el directorio padre al path para poder importar 'app' y 'models'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Si tu app no está en el directorio padre, ajusta el path.

try:
    from app import create_app, db
    from models import User, Invoice, Service
except ImportError as e:
    print(f"Error de Importación: Asegúrate de que los archivos 'app.py' y 'models.py' existan y las clases User/Invoice/Service estén definidas. {e}")
    sys.exit(14)

# 🎯 1. ID DEL USUARIO DE PRUEBA: CÁMBIALO AL ID DEL USUARIO CON EL QUE ESTÁS LOGUEADO 🎯
USER_ID_DE_PRUEBA = 14

def calculate_total_service_cost(user):
    """Calcula la suma de los precios de todos los servicios contratados."""
    # Usamos la relación directa services_contracted
    if user.services_contracted:
        # Aquí se asume que cada objeto Service tiene un atributo 'price'
        return sum(service.price for service in user.services_contracted)
    return 0.00

def create_pending_invoice():
    # 0. Inicializa la aplicación y el contexto
    app = create_app() # Si usas factory pattern
    # Si no usas factory pattern, simplemente usa: app = app_instance
    
    with app.app_context():
        user = User.query.get(USER_ID_DE_PRUEBA)

        if not user:
            print(f"Error: Usuario con ID {USER_ID_DE_PRUEBA} no encontrado en la base de datos.")
            return

        monto_calculado = calculate_total_service_cost(user)
        
        if monto_calculado <= 0:
            print(f"Advertencia: El usuario ID {user.id} no tiene servicios activos. Monto $0.00. No se creará la factura.")
            return

        try:
            # 3. Elimina cualquier factura PENDIENTE anterior para limpieza
            Invoice.query.filter_by(user_id=user.id, status='PENDIENTE').delete()
            
            # 4. Crea la nueva factura
            new_invoice = Invoice(
                amount=monto_calculado,
                billing_date=datetime.now(), 
                user_id=user.id,
                status='PENDIENTE' # Estado CRÍTICO
            )

            # 5. Agrega y Confirma
            db.session.add(new_invoice)
            db.session.commit()
            
            print("-------------------------------------------------------")
            print(f"✅ ÉXITO: Factura PENDIENTE creada.")
            print(f"Usuario ID: {user.id}")
            print(f"Monto: ${monto_calculado:.2f}")
            print("-------------------------------------------------------")

        except Exception as e:
            db.session.rollback()
            print(f"ERROR al intentar guardar en la BD: {e}")

if __name__ == '__main__':
    create_pending_invoice()