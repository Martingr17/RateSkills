from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, create_refresh_token
import secrets
import string

bcrypt = Bcrypt()

def hash_password(password):
    """Хеширование пароля"""
    return bcrypt.generate_password_hash(password).decode('utf-8')

def verify_password(password, password_hash):
    """Проверка пароля"""
    return bcrypt.check_password_hash(password_hash, password)

def generate_token(user_id, additional_claims=None):
    """Генерация JWT токена"""
    claims = {'user_id': user_id}
    if additional_claims:
        claims.update(additional_claims)
    
    access_token = create_access_token(identity=user_id, additional_claims=claims)
    refresh_token = create_refresh_token(identity=user_id)
    
    return {
        'access_token': access_token,
        'refresh_token': refresh_token
    }

def generate_password(length=12):
    """Генерация случайного пароля"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for i in range(length))

def validate_token(token):
    """Валидация JWT токена"""
    try:
        from flask_jwt_extended import decode_token
        decoded = decode_token(token)
        return decoded
    except Exception:
        return None

def get_user_from_token(token):
    """Получение пользователя из JWT токена"""
    decoded = validate_token(token)
    if not decoded:
        return None
    
    from ..models import User
    user_id = decoded.get('sub')
    return User.query.get(user_id)

def requires_roles(*roles):
    """Декоратор для проверки ролей"""
    def wrapper(f):
        from functools import wraps
        from flask_jwt_extended import get_jwt_identity
        from flask import jsonify
        
        @wraps(f)
        def decorated_function(*args, **kwargs):
            current_user_id = get_jwt_identity()
            from ..models import User
            user = User.query.get(current_user_id)
            
            if not user or user.role not in roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return wrapper
