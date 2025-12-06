"""
Blueprint для маршрутов
"""

from .auth_routes import auth_bp
from .employee_routes import employee_bp
from .manager_routes import manager_bp
from .admin_routes import admin_bp
from .skill_routes import skill_bp

__all__ = ['auth_bp', 'employee_bp', 'manager_bp', 'admin_bp', 'skill_bp']
