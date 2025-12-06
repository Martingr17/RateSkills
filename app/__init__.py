"""
Skill Matrix Application Package
"""

import os
import sys
from flask import Flask, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask import render_template

# Добавляем текущую директорию в Python path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Инициализация расширений
db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
bcrypt = Bcrypt()
jwt = JWTManager()
mail = Mail()

def create_app(config_name='default'):
    """Фабрика приложения Flask"""

    # Импортируем здесь, чтобы избежать циклических импортов
    from .config import config

    app = Flask(__name__, template_folder='templates')

    # Загрузка конфигурации
    app.config.from_object(config[config_name])

    # Инициализация расширений с приложением
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
    bcrypt.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)
    @app.route('/')
    def home():
        return render_template('index.html')

    @app.route('/api/test')
    def test():
        return {'status': 'ok', 'message': 'API работает'}
    # Регистрация обработчиков ошибок
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not Found', 'message': 'Resource not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal Server Error', 'message': 'Something went wrong'}), 500

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({'error': 'Unauthorized', 'message': 'Authentication required'}), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({'error': 'Forbidden', 'message': 'Insufficient permissions'}), 403

    # Регистрация blueprint'ов (импортируем здесь, чтобы избежать циклических импортов)
    try:
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

    except ImportError as e:
        print(f"⚠️  Warning: Could not import some blueprints: {e}")
        print("Some routes may not be available")

    # Настройка JWT callbacks
    @jwt.user_identity_loader
    def user_identity_lookup(user):
        return user.id

    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        from .models import User
        identity = jwt_data["sub"]
        return User.query.get(identity)

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_data):
        return jsonify({'error': 'Token expired', 'message': 'The token has expired'}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({'error': 'Invalid token', 'message': 'The token is invalid'}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({'error': 'Authorization required', 'message': 'Request does not contain a token'}), 401

    # Регистрация CLI команд
    register_commands(app)

    # Создание таблиц при первом запуске
    with app.app_context():
        db.create_all()

    return app


def register_commands(app):
    """Регистрация CLI команд"""

    @app.cli.command('seed')
    def seed():
        """Заполнение базы данных тестовыми данными"""
        import sys
        import os

        # Добавляем корневую директорию в путь Python
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, current_dir)

        try:
            from seed_data import create_test_data
            create_test_data()
            print("✅ Тестовые данные успешно созданы!")
        except ImportError as e:
            print(f"❌ Ошибка импорта: {e}")
            print("Создайте файл seed_data.py в корне проекта")
            print("Или запустите: python seed_data.py")

    @app.cli.command('create-admin')
    def create_admin():
        """Создание администратора"""
        from .models import User, db
        from .utils.auth_utils import hash_password

        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
            if admin:
                print("⚠️  Администратор уже существует")
                return

            admin = User(
                username='admin',
                email='admin@company.com',
                password_hash=hash_password('admin123'),
                first_name='Admin',
                last_name='System',
                role='admin',
                is_active=True,
                is_verified=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Администратор создан")
            print("Логин: admin")
            print("Пароль: admin123")

    @app.cli.command('init-db')
    def init_db():
        """Инициализация базы данных"""
        from .models import db

        with app.app_context():
            db.create_all()
            print("✅ База данных инициализирована")

            # Проверяем созданные таблицы
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"Создано таблиц: {len(tables)}")
            for table in tables:
                print(f"  - {table}")

    @app.cli.command('drop-db')
    def drop_db():
        """Удаление всех таблиц базы данных"""
        from .models import db

        with app.app_context():
            db.drop_all()
            print("🗑️  Все таблицы базы данных удалены")
