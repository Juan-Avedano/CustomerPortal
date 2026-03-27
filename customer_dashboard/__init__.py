# C:\Users\Juan Avedano\Desktop\Facultad\Proyecto\customer_dashboard\__init__.py

from flask import Blueprint

# Definición del Blueprint 
customer_dashboard_bp = Blueprint('customer_dashboard', __name__,
                                  template_folder='templates',
                                  static_folder='static',
                                  static_url_path='/customer_dashboard/static') 


from . import views