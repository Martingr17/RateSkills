"""
Модуль для аутентификации и авторизации
"""

from functools import wraps
from flask import request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    verify_jwt_in_request,
    get_jwt
)
from datetime import datetime, timedelta
import jwt as pyjwt

from .models import User, db, AuditLog
from .utils.auth_utils import verify_password, hash_password
from .utils.validation import validate_email_address, validate_password


class AuthError(Exception):
    """Исключение для ошибок аутентификации"""
    def __init__(self, message, status_code=401):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


def authenticate_user(username, password):
    """
    Аутентификация пользователя

    Args:
        username (str): Имя пользователя
        password (str): Пароль

    Returns:
        tuple: (user, error_message)
    """
    if not username or not password:
        return None, "Имя пользователя и пароль обязательны"

    # Ищем пользователя по username или email
    user = User.query.filter(
        (User.username == username) | (User.email == username)
    ).first()

    if not user:
        return None, "Неверное имя пользователя или пароль"

    if not user.is_active:
        return None, "Учетная запись отключена"

    if not verify_password(password, user.password_hash):
        return None, "Неверное имя пользователя или пароль"

    # Обновляем время последнего входа
    user.last_login = datetime.utcnow()
    db.session.commit()

    return user, None


def generate_tokens(user):
    """
    Генерация JWT токенов для пользователя

    Args:
        user (User): Объект пользователя

    Returns:
        dict: Токены доступа
    """
    # Дополнительные claims для токена
    additional_claims = {
        'role': user.role,
        'username': user.username,
        'email': user.email
    }

    # Создаем access токен
    access_token = create_access_token(
        identity=user,
        additional_claims=additional_claims,
        expires_delta=timedelta(hours=24)
    )

    # Создаем refresh токен
    refresh_token = create_refresh_token(
        identity=user,
        additional_claims=additional_claims
    )

    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'bearer',
        'expires_in': 24 * 60 * 60  # 24 часа в секундах
    }


def refresh_access_token():
    """
    Обновление access токена с помощью refresh токена

    Returns:
        dict: Новый access токен
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user or not user.is_active:
        raise AuthError("Пользователь не найден или неактивен", 401)

    additional_claims = {
        'role': user.role,
        'username': user.username,
        'email': user.email
    }

    access_token = create_access_token(
        identity=user,
        additional_claims=additional_claims,
        expires_delta=timedelta(hours=24)
    )

    return {
        'access_token': access_token,
        'token_type': 'bearer',
        'expires_in': 24 * 60 * 60
    }


def get_current_user():
    """
    Получение текущего пользователя из JWT токена

    Returns:
        User: Объект текущего пользователя
    """
    try:
        user_id = get_jwt_identity()
        return User.query.get(user_id)
    except Exception:
        return None


def requires_roles(*roles):
    """
    Декоратор для проверки ролей пользователя

    Args:
        *roles: Роли, которым разрешен доступ

    Returns:
        function: Декорированная функция
    """
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            verify_jwt_in_request()

            current_user = get_current_user()
            if not current_user:
                return jsonify({'error': 'Пользователь не найден'}), 401

            if current_user.role not in roles:
                return jsonify({
                    'error': 'Доступ запрещен',
                    'message': f'Требуются роли: {", ".join(roles)}'
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return wrapper


def requires_self_or_roles(*roles):
    """
    Декоратор для проверки, что пользователь либо сам объект, либо имеет нужную роль

    Args:
        *roles: Роли, которым разрешен доступ

    Returns:
        function: Декорированная функция
    """
    def wrapper(f):
        @wraps(f)
        def decorated_function(user_id, *args, **kwargs):
            verify_jwt_in_request()

            current_user = get_current_user()
            if not current_user:
                return jsonify({'error': 'Пользователь не найден'}), 401

            # Проверяем, является ли пользователь самим собой
            is_self = current_user.id == user_id

            # Проверяем, есть ли у пользователя нужная роль
            has_role = current_user.role in roles

            if not (is_self or has_role):
                return jsonify({
                    'error': 'Доступ запрещен',
                    'message': 'Нет прав для доступа к этому ресурсу'
                }), 403

            return f(user_id, *args, **kwargs)
        return decorated_function
    return wrapper


def log_auth_action(user_id, action, ip_address=None, user_agent=None):
    """
    Логирование действий аутентификации

    Args:
        user_id (int): ID пользователя
        action (str): Действие (login, logout, register, etc.)
        ip_address (str): IP адрес
        user_agent (str): User-Agent заголовок
    """
    audit_log = AuditLog(
        user_id=user_id,
        action=f'auth_{action}',
        entity_type='user',
        entity_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.session.add(audit_log)
    db.session.commit()


def validate_registration_data(data):
    """
    Валидация данных регистрации

    Args:
        data (dict): Данные регистрации

    Returns:
        tuple: (is_valid, errors, validated_data)
    """
    errors = []
    validated_data = {}

    # Валидация email
    if 'email' not in data or not data['email']:
        errors.append({'field': 'email', 'error': 'Email обязателен'})
    else:
        is_valid, message = validate_email_address(data['email'])
        if not is_valid:
            errors.append({'field': 'email', 'error': message})
        else:
            validated_data['email'] = message  # normalized email

    # Валидация username
    if 'username' not in data or not data['username']:
        errors.append({'field': 'username', 'error': 'Имя пользователя обязательно'})
    else:
        username = data['username'].strip()
        if len(username) < 3:
            errors.append({'field': 'username', 'error': 'Имя пользователя должно содержать минимум 3 символа'})
        elif len(username) > 64:
            errors.append({'field': 'username', 'error': 'Имя пользователя не должно превышать 64 символа'})
        elif not username.isalnum() and '_' not in username and '-' not in username and '.' not in username:
            errors.append({'field': 'username', 'error': 'Имя пользователя может содержать только буквы, цифры, точку, подчеркивание и дефис'})
        else:
            validated_data['username'] = username

    # Валидация пароля
    if 'password' not in data or not data['password']:
        errors.append({'field': 'password', 'error': 'Пароль обязателен'})
    else:
        is_valid, message = validate_password(data['password'])
        if not is_valid:
            errors.append({'field': 'password', 'error': message})
        else:
            validated_data['password_hash'] = hash_password(data['password'])

    # Проверка подтверждения пароля
    if 'password' in data and 'confirm_password' in data:
        if data['password'] != data['confirm_password']:
            errors.append({'field': 'confirm_password', 'error': 'Пароли не совпадают'})

    # Валидация имени
    if 'first_name' not in data or not data['first_name']:
        errors.append({'field': 'first_name', 'error': 'Имя обязательно'})
    else:
        first_name = data['first_name'].strip()
        if len(first_name) < 2:
            errors.append({'field': 'first_name', 'error': 'Имя должно содержать минимум 2 символа'})
        elif len(first_name) > 64:
            errors.append({'field': 'first_name', 'error': 'Имя не должно превышать 64 символа'})
        else:
            validated_data['first_name'] = first_name

    # Валидация фамилии
    if 'last_name' not in data or not data['last_name']:
        errors.append({'field': 'last_name', 'error': 'Фамилия обязательна'})
    else:
        last_name = data['last_name'].strip()
        if len(last_name) < 2:
            errors.append({'field': 'last_name', 'error': 'Фамилия должна содержать минимум 2 символа'})
        elif len(last_name) > 64:
            errors.append({'field': 'last_name', 'error': 'Фамилия не должна превышать 64 символа'})
        else:
            validated_data['last_name'] = last_name

    # Валидация отчества (не обязательно)
    if 'patronymic' in data and data['patronymic']:
        patronymic = data['patronymic'].strip()
        if patronymic and len(patronymic) > 64:
            errors.append({'field': 'patronymic', 'error': 'Отчество не должно превышать 64 символа'})
        else:
            validated_data['patronymic'] = patronymic

    # Валидация роли (если указана)
    if 'role' in data and data['role']:
        role = data['role'].lower()
        if role not in ['employee', 'manager', 'admin']:
            errors.append({'field': 'role', 'error': 'Неверная роль пользователя'})
        else:
            validated_data['role'] = role

    # Валидация телефона (не обязательно)
    if 'phone' in data and data['phone']:
        phone = data['phone'].strip()
        if phone and len(phone) > 20:
            errors.append({'field': 'phone', 'error': 'Телефон не должен превышать 20 символов'})
        elif phone:
            # Простая проверка формата телефона
            if not phone.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '').isdigit():
                errors.append({'field': 'phone', 'error': 'Неверный формат телефона'})
            else:
                validated_data['phone'] = phone

    # Валидация должности (не обязательно)
    if 'position' in data and data['position']:
        position = data['position'].strip()
        if position and len(position) > 100:
            errors.append({'field': 'position', 'error': 'Должность не должна превышать 100 символов'})
        else:
            validated_data['position'] = position

    return len(errors) == 0, errors, validated_data


def check_username_availability(username):
    """
    Проверка доступности имени пользователя

    Args:
        username (str): Имя пользователя для проверки

    Returns:
        bool: True если доступно
    """
    user = User.query.filter_by(username=username).first()
    return user is None


def check_email_availability(email):
    """
    Проверка доступности email

    Args:
        email (str): Email для проверки

    Returns:
        bool: True если доступно
    """
    user = User.query.filter_by(email=email).first()
    return user is None


def create_user_from_registration(validated_data, created_by=None):
    """
    Создание пользователя из валидированных данных

    Args:
        validated_data (dict): Валидированные данные
        created_by (int): ID пользователя, который создает аккаунт

    Returns:
        User: Созданный пользователь
    """
    # Создаем пользователя
    user = User(
        username=validated_data['username'],
        email=validated_data['email'],
        password_hash=validated_data['password_hash'],
        first_name=validated_data['first_name'],
        last_name=validated_data['last_name'],
        role=validated_data.get('role', 'employee'),
        is_active=True,
        is_verified=False
    )

    # Опциональные поля
    if 'patronymic' in validated_data:
        user.patronymic = validated_data['patronymic']

    if 'phone' in validated_data:
        user.phone = validated_data['phone']

    if 'position' in validated_data:
        user.position = validated_data['position']

    if 'department_id' in validated_data:
        user.department_id = validated_data['department_id']

    if 'manager_id' in validated_data:
        user.manager_id = validated_data['manager_id']

    if created_by:
        user.created_by = created_by

    db.session.add(user)
    db.session.commit()

    # Логирование создания пользователя
    log_auth_action(
        user_id=user.id if created_by else user.id,
        action='registered' if not created_by else 'created_by_admin',
        ip_address=request.remote_addr if request else None,
        user_agent=request.user_agent.string if request else None
    )

    return user


def change_user_password(user_id, current_password, new_password, confirm_password):
    """
    Смена пароля пользователя

    Args:
        user_id (int): ID пользователя
        current_password (str): Текущий пароль
        new_password (str): Новый пароль
        confirm_password (str): Подтверждение нового пароля

    Returns:
        tuple: (success, message)
    """
    user = User.query.get(user_id)
    if not user:
        return False, "Пользователь не найден"

    # Проверяем текущий пароль
    if not verify_password(current_password, user.password_hash):
        return False, "Текущий пароль неверен"

    # Проверяем новый пароль
    is_valid, message = validate_password(new_password)
    if not is_valid:
        return False, message

    # Проверяем подтверждение пароля
    if new_password != confirm_password:
        return False, "Новые пароли не совпадают"

    # Хешируем и сохраняем новый пароль
    user.password_hash = hash_password(new_password)
    db.session.commit()

    # Логируем смену пароля
    log_auth_action(
        user_id=user_id,
        action='password_changed',
        ip_address=request.remote_addr if request else None,
        user_agent=request.user_agent.string if request else None
    )

    return True, "Пароль успешно изменен"


def reset_user_password(user_id, new_password=None, reset_by_admin=False):
    """
    Сброс пароля пользователя

    Args:
        user_id (int): ID пользователя
        new_password (str): Новый пароль (если None, генерируется автоматически)
        reset_by_admin (bool): Сброс администратором

    Returns:
        tuple: (success, message, new_password)
    """
    from .utils.auth_utils import generate_password

    user = User.query.get(user_id)
    if not user:
        return False, "Пользователь не найден", None

    # Генерируем новый пароль, если не указан
    if not new_password:
        new_password = generate_password()

    # Проверяем пароль
    is_valid, message = validate_password(new_password)
    if not is_valid:
        return False, message, None

    # Хешируем и сохраняем новый пароль
    user.password_hash = hash_password(new_password)
    db.session.commit()

    # Логируем сброс пароля
    action = 'password_reset_by_admin' if reset_by_admin else 'password_reset'
    log_auth_action(
        user_id=user_id,
        action=action,
        ip_address=request.remote_addr if request else None,
        user_agent=request.user_agent.string if request else None
    )

    return True, "Пароль успешно сброшен", new_password


def verify_jwt_token(token):
    """
    Верификация JWT токена

    Args:
        token (str): JWT токен

    Returns:
        tuple: (is_valid, payload_or_error)
    """
    try:
        # Убираем префикс "Bearer " если есть
        if token.startswith('Bearer '):
            token = token[7:]

        # Декодируем токен
        payload = pyjwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=['HS256']
        )

        # Проверяем, что пользователь существует и активен
        user_id = payload.get('sub')
        user = User.query.get(user_id)

        if not user or not user.is_active:
            return False, "Пользователь не найден или неактивен"

        return True, payload
    except pyjwt.ExpiredSignatureError:
        return False, "Токен истек"
    except pyjwt.InvalidTokenError as e:
        return False, f"Неверный токен: {str(e)}"


def get_user_permissions(user):
    """
    Получение прав пользователя

    Args:
        user (User): Объект пользователя

    Returns:
        dict: Права пользователя
    """
    permissions = {
        'can_view_own_profile': True,
        'can_edit_own_profile': True,
        'can_rate_skills': True,
        'can_view_own_ratings': True,
        'can_view_own_history': True,
        'can_view_notifications': True,
    }

    if user.role == 'manager':
        permissions.update({
            'can_view_department_employees': True,
            'can_manage_employee_ratings': True,
            'can_confirm_ratings': True,
            'can_compare_employees': True,
            'can_search_employees': True,
            'can_view_department_stats': True,
        })

    if user.role == 'admin':
        permissions.update({
            'can_manage_users': True,
            'can_manage_skills': True,
            'can_manage_categories': True,
            'can_manage_departments': True,
            'can_generate_reports': True,
            'can_export_data': True,
            'can_view_all_ratings': True,
            'can_view_audit_logs': True,
            'can_manage_system': True,
        })

    return permissions


def validate_token_expiration(token):
    """
    Проверка срока действия токена

    Args:
        token (str): JWT токен

    Returns:
        tuple: (is_valid, time_remaining_seconds)
    """
    try:
        if token.startswith('Bearer '):
            token = token[7:]

        payload = pyjwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=['HS256'],
            options={'verify_exp': False}  # Не проверяем срок, чтобы получить payload
        )

        # Получаем время истечения
        exp_timestamp = payload.get('exp')
        if not exp_timestamp:
            return False, 0

        exp_datetime = datetime.fromtimestamp(exp_timestamp)
        now = datetime.utcnow()

        if exp_datetime < now:
            return False, 0

        time_remaining = (exp_datetime - now).total_seconds()
        return True, time_remaining

    except Exception:
        return False, 0
