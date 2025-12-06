from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, 
    create_refresh_token, 
    jwt_required, 
    get_jwt_identity,
    get_jwt
)
from ..models import db, User, AuditLog
from ..schemas import LoginSchema, UserCreateSchema
from app.schemas import LoginSchema, UserCreateSchema
from ..utils.auth_utils import hash_password, verify_password
from ..services.user_service import UserService
from ..utils.validation import validate_input

auth_bp = Blueprint('auth', __name__)
user_service = UserService()

login_schema = LoginSchema()
user_create_schema = UserCreateSchema()


@auth_bp.route('/login', methods=['POST'])
def login():
    """Аутентификация пользователя"""
    try:
        # Валидация входных данных
        data = request.get_json()
        errors = login_schema.validate(data)
        if errors:
            return jsonify({'error': 'Validation error', 'details': errors}), 400
        
        # Поиск пользователя
        username = data.get('username')
        password = data.get('password')
        
        user = user_service.get_user_by_username(username)
        if not user or not verify_password(password, user.password_hash):
            return jsonify({'error': 'Invalid username or password'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account is disabled'}), 403
        
        # Обновление времени последнего входа
        user_service.update_last_login(user.id)
        
        # Создание JWT токенов
        access_token = create_access_token(identity=user)
        refresh_token = create_refresh_token(identity=user)
        
        # Логирование входа
        audit_log = AuditLog(
            user_id=user.id,
            action='user_login',
            entity_type='user',
            entity_id=user.id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Login failed', 'message': str(e)}), 500


@auth_bp.route('/register', methods=['POST'])
@jwt_required()
def register():
    """Регистрация нового пользователя (только для администраторов)"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Only administrators can register new users'}), 403
        
        # Валидация данных
        data = request.get_json()
        errors = user_create_schema.validate(data)
        if errors:
            return jsonify({'error': 'Validation error', 'details': errors}), 400
        
        # Проверка уникальности username и email
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 409
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already exists'}), 409
        
        # Создание пользователя
        user = user_service.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            patronymic=data.get('patronymic'),
            position=data.get('position'),
            role=data.get('role', 'employee'),
            department_id=data.get('department_id'),
            manager_id=data.get('manager_id'),
            phone=data.get('phone')
        )
        
        # Логирование создания
        audit_log = AuditLog(
            user_id=current_user_id,
            action='user_created',
            entity_type='user',
            entity_id=user.id,
            new_values={'username': user.username, 'email': user.email, 'role': user.role},
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'message': 'User created successfully',
            'user': user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Registration failed', 'message': str(e)}), 500


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Обновление access токена"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or not user.is_active:
            return jsonify({'error': 'User not found or inactive'}), 404
        
        access_token = create_access_token(identity=user)
        
        return jsonify({
            'access_token': access_token
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Token refresh failed', 'message': str(e)}), 500


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Выход из системы"""
    try:
        # В реальном приложении здесь может быть добавление токена в blacklist
        return jsonify({'message': 'Successfully logged out'}), 200
        
    except Exception as e:
        return jsonify({'error': 'Logout failed', 'message': str(e)}), 500


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Получение информации о текущем пользователе"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'user': user.to_dict(include_ratings=True)
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get user info', 'message': str(e)}), 500


@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Изменение пароля"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not current_password or not new_password or not confirm_password:
            return jsonify({'error': 'All password fields are required'}), 400
        
        if new_password != confirm_password:
            return jsonify({'error': 'New passwords do not match'}), 400
        
        if len(new_password) < 6:
            return jsonify({'error': 'New password must be at least 6 characters'}), 400
        
        user = User.query.get(current_user_id)
        if not verify_password(current_password, user.password_hash):
            return jsonify({'error': 'Current password is incorrect'}), 400
        
        # Обновление пароля
        user.password_hash = hash_password(new_password)
        db.session.commit()
        
        # Логирование изменения пароля
        audit_log = AuditLog(
            user_id=current_user_id,
            action='password_changed',
            entity_type='user',
            entity_id=user.id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({'message': 'Password changed successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to change password', 'message': str(e)}), 500


@auth_bp.route('/check-username/<username>', methods=['GET'])
def check_username(username):
    """Проверка доступности username"""
    try:
        user = User.query.filter_by(username=username).first()
        available = user is None
        
        return jsonify({
            'username': username,
            'available': available
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Check failed', 'message': str(e)}), 500


@auth_bp.route('/check-email/<email>', methods=['GET'])
def check_email(email):
    """Проверка доступности email"""
    try:
        user = User.query.filter_by(email=email).first()
        available = user is None
        
        return jsonify({
            'email': email,
            'available': available
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Check failed', 'message': str(e)}), 500
