"""
Authentication and authorization utilities
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import logging

from app.config import settings
from app.database import get_db
from app.models import User, Role
from app.schemas import TokenData

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 password bearer for token authentication
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False
)

# ========== Password Utilities ==========

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)

def validate_password_strength(password: str) -> Dict[str, Any]:
    """Validate password strength"""
    errors = []
    
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        errors.append(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters")
    
    if len(password) > settings.PASSWORD_MAX_LENGTH:
        errors.append(f"Password must be at most {settings.PASSWORD_MAX_LENGTH} characters")
    
    # Check for at least one digit
    if not any(char.isdigit() for char in password):
        errors.append("Password must contain at least one digit")
    
    # Check for at least one uppercase letter
    if not any(char.isupper() for char in password):
        errors.append("Password must contain at least one uppercase letter")
    
    # Check for at least one lowercase letter
    if not any(char.islower() for char in password):
        errors.append("Password must contain at least one lowercase letter")
    
    # Check for at least one special character
    special_characters = "!@#$%^&*()-_=+[]{}|;:,.<>?/~`"
    if not any(char in special_characters for char in password):
        errors.append("Password must contain at least one special character")
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "score": max(0, 5 - len(errors))  # Simple score out of 5
    }

# ========== JWT Token Utilities ==========

def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt

def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt

def decode_token(token: str) -> Dict[str, Any]:
    """Decode JWT token"""
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def verify_token(token: str) -> bool:
    """Verify if token is valid (not expired)"""
    try:
        decode_token(token)
        return True
    except HTTPException:
        return False

def get_token_expiration(token: str) -> Optional[datetime]:
    """Get token expiration datetime"""
    try:
        payload = decode_token(token)
        exp = payload.get("exp")
        if exp:
            return datetime.fromtimestamp(exp)
    except Exception:
        pass
    return None

# ========== Authentication ==========

def authenticate_user(db: Session, login: str, password: str) -> Optional[User]:
    """Authenticate user by login/email and password"""
    # Try to find user by login or email
    user = db.query(User).filter(
        (User.login == login) | (User.email == login)
    ).first()
    
    if not user:
        return None
    
    if not verify_password(password, user.password_hash):
        return None
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is deactivated"
        )
    
    return user

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current authenticated user from token"""
    if token is None:
        return None
    
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if user_id is None:
            return None
        
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
    except JWTError:
        return None
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        return None
    
    return user

async def get_current_active_user(
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    """Get current active user, raise 401 if not authenticated"""
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user

async def get_optional_user(
    current_user: Optional[User] = Depends(get_current_user)
) -> Optional[User]:
    """Get optional user (doesn't raise error if not authenticated)"""
    return current_user

# ========== Authorization ==========

def check_role(required_roles: list[Role]):
    """Factory function to create role-based dependency"""
    async def role_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker

# Role-specific dependencies
get_admin_user = check_role([Role.ADMIN, Role.HR, Role.DIRECTOR])
get_manager_user = check_role([Role.MANAGER, Role.ADMIN, Role.HR, Role.DIRECTOR])
get_hr_user = check_role([Role.HR, Role.ADMIN, Role.DIRECTOR])
get_director_user = check_role([Role.DIRECTOR])

def check_permission(user: User, resource: Any, action: str) -> bool:
    """Check if user has permission for specific resource and action"""
    # This is a simplified permission check
    # In production, you might want to implement a more sophisticated RBAC system
    
    # Admin, HR, and Director have full access
    if user.role in [Role.ADMIN, Role.HR, Role.DIRECTOR]:
        return True
    
    # Managers can only manage their own department
    if user.role == Role.MANAGER:
        if hasattr(resource, 'department_id'):
            return resource.department_id == user.department_id
        elif hasattr(resource, 'user'):
            return resource.user.department_id == user.department_id
    
    # Employees can only access their own resources
    if user.role == Role.EMPLOYEE:
        if hasattr(resource, 'user_id'):
            return resource.user_id == user.id
        elif hasattr(resource, 'id'):
            return resource.id == user.id
    
    return False

def require_permission(resource_getter):
    """Decorator factory for permission checking"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract resource and current user
            # This is a simplified implementation
            # In practice, you'd need to adapt based on your endpoint structure
            pass
        return wrapper
    return decorator

# ========== Session Management ==========

def update_user_last_login(db: Session, user: User) -> None:
    """Update user's last login timestamp"""
    user.last_login = datetime.utcnow()
    db.commit()

def invalidate_user_sessions(db: Session, user: User) -> None:
    """Invalidate all user sessions (clear refresh token)"""
    user.refresh_token = None
    user.refresh_token_expiry = None
    db.commit()

def generate_api_key(user: User) -> str:
    """Generate API key for user"""
    import secrets
    api_key = secrets.token_urlsafe(32)
    return api_key

def validate_api_key(db: Session, api_key: str) -> Optional[User]:
    """Validate API key and return user"""
    user = db.query(User).filter(
        User.api_key == api_key,
        User.is_active == True,
        (User.api_key_expiry.is_(None) | (User.api_key_expiry > datetime.utcnow()))
    ).first()
    
    return user

# ========== Password Reset ==========

def create_password_reset_token(user: User) -> str:
    """Create password reset token"""
    import secrets
    reset_token = secrets.token_urlsafe(32)
    return reset_token

def verify_password_reset_token(db: Session, token: str) -> Optional[User]:
    """Verify password reset token and return user"""
    user = db.query(User).filter(
        User.reset_token == token,
        User.reset_token_expiry > datetime.utcnow()
    ).first()
    
    return user

def expire_password_reset_token(db: Session, user: User) -> None:
    """Expire password reset token"""
    user.reset_token = None
    user.reset_token_expiry = None
    db.commit()

# ========== Audit Logging ==========

def log_auth_activity(
    db: Session,
    user: Optional[User],
    action: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    success: bool = True,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """Log authentication activity"""
    from app.models import AuditLog
    
    audit_log = AuditLog(
        user_id=user.id if user else None,
        action=action,
        entity_type="Authentication",
        endpoint="/auth/login",
        ip_address=ip_address,
        user_agent=user_agent,
        request_body=str(details) if details else None,
        response_status=200 if success else 401
    )
    
    db.add(audit_log)
    db.commit()

# ========== Security Headers ==========

def add_security_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Add security headers to response"""
    security_headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }
    
    headers.update(security_headers)
    return headers

# ========== Rate Limiting ==========

class RateLimiter:
    """Simple rate limiter (in-memory, for production use Redis)"""
    
    def __init__(self, requests: int = 100, window: int = 60):
        self.requests = requests
        self.window = window  # seconds
        self.attempts = {}
    
    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed"""
        import time
        
        current_time = time.time()
        window_start = current_time - self.window
        
        # Clean old attempts
        self.attempts[key] = [
            attempt for attempt in self.attempts.get(key, [])
            if attempt > window_start
        ]
        
        if len(self.attempts[key]) >= self.requests:
            return False
        
        self.attempts[key].append(current_time)
        return True

# Create rate limiter instances
login_rate_limiter = RateLimiter(requests=5, window=300)  # 5 attempts per 5 minutes
api_rate_limiter = RateLimiter(requests=100, window=60)   # 100 requests per minute

# ========== Export ==========

__all__ = [
    # Password utilities
    "verify_password",
    "get_password_hash",
    "validate_password_strength",
    
    # JWT utilities
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "verify_token",
    "get_token_expiration",
    
    # Authentication
    "authenticate_user",
    "get_current_user",
    "get_current_active_user",
    "get_optional_user",
    
    # Authorization
    "check_role",
    "get_admin_user",
    "get_manager_user",
    "get_hr_user",
    "get_director_user",
    "check_permission",
    "require_permission",
    
    # Session management
    "update_user_last_login",
    "invalidate_user_sessions",
    "generate_api_key",
    "validate_api_key",
    
    # Password reset
    "create_password_reset_token",
    "verify_password_reset_token",
    "expire_password_reset_token",
    
    # Audit logging
    "log_auth_activity",
    
    # Security headers
    "add_security_headers",
    
    # Rate limiting
    "RateLimiter",
    "login_rate_limiter",
    "api_rate_limiter",
    
    # OAuth2 scheme
    "oauth2_scheme",
]