from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from .config import config

# Инициализация расширений
db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
bcrypt = Bcrypt()
jwt = JWTManager()
mail = Mail()

def create_app(config_name='default'):
    """Фабрика приложения"""
    app = Flask(__name__)
    
    # Загрузка конфигурации
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    # Инициализация расширений
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
    bcrypt.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)
    
    # Регистрация обработчиков ошибок
    register_error_handlers(app)
    
    # Регистрация маршрутов
    register_blueprints(app)
    
    # Регистрация контекста команд
    register_commands(app)
    
    # Создание таблиц при первом запуске
    with app.app_context():
        db.create_all()
    
    return app


def register_error_handlers(app):
    """Регистрация обработчиков ошибок"""
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Not Found',
            'message': 'The requested resource was not found'
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500
    
    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Authentication is required'
        }), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            'error': 'Forbidden',
            'message': 'You do not have permission to access this resource'
        }), 403


def register_blueprints(app):
    """Регистрация blueprint'ов"""
    from .routes.auth_routes import auth_bp
    from .routes.employee_routes import employee_bp
    from .routes.manager_routes import manager_bp
    from .routes.admin_routes import admin_bp
    from .routes.skill_routes import skill_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(employee_bp, url_prefix='/api/employee')
    app.register_blueprint(manager_bp, url_prefix='/api/manager')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(skill_bp, url_prefix='/api/skills')


def register_commands(app):
    """Регистрация CLI команд"""
    from .utils.seed import seed_command
    
    @app.cli.command('seed')
    def seed():
        """Заполнение базы данных тестовыми данными"""
        seed_command(app)
    
    @app.cli.command('create-admin')
    def create_admin():
        """Создание администратора"""
        from .services.user_service import create_admin_user
        create_admin_user()


@jwt.user_identity_loader
def user_identity_lookup(user):
    """Возвращает идентификатор пользователя для JWT"""
    return user.id


@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    """Загружает пользователя по JWT токену"""
    from .models import User
    identity = jwt_data["sub"]
    return User.query.get(identity)


@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_data):
    """Обработчик истекшего токена"""
    return jsonify({
        'error': 'Token expired',
        'message': 'The authentication token has expired'
    }), 401


@jwt.invalid_token_loader
def invalid_token_callback(error):
    """Обработчик невалидного токена"""
    return jsonify({
        'error': 'Invalid token',
        'message': 'The authentication token is invalid'
    }), 401


@jwt.unauthorized_loader
def missing_token_callback(error):
    """Обработчик отсутствия токена"""
    return jsonify({
        'error': 'Authorization required',
        'message': 'Request does not contain an access token'
    }), 401