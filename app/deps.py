"""
Dependency injection module for FastAPI
"""
from typing import Generator, Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
import logging

from app.database import SessionLocal
from app.models import User, Role
from app.config import settings

logger = logging.getLogger(__name__)

# Security scheme for bearer tokens
security = HTTPBearer(auto_error=False)

def get_db() -> Generator:
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Dependency to get current authenticated user from JWT token
    
    Supports:
    1. Bearer token in Authorization header
    2. Token in cookies
    3. API key in headers
    """
    # Try to get token from Authorization header
    token = None
    if credentials:
        token = credentials.credentials
    
    # Try to get token from cookies
    if not token:
        token = request.cookies.get("access_token")
    
    # Try to get API key from headers
    if not token:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # For API key, we'll look for a user with matching API key
            user = db.query(User).filter(User.api_key == api_key).first()
            if user and user.is_active:
                return user
    
    if not token:
        return None
    
    # Decode JWT token
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        return None
    
    # Get user from database
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        return None
    
    return user

async def get_current_active_user(
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    """Dependency to get current active user, raises 401 if not authenticated"""
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
    """Dependency to get optional user (doesn't raise error if not authenticated)"""
    return current_user

def check_role(required_roles: list[str]):
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

async def get_department_manager(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Dependency to check if user is manager of specific department"""
    from app.models import Department
    
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    # Check if current user is the manager or has higher privileges
    if (current_user.id != department.manager_id and 
        current_user.role not in [Role.ADMIN, Role.HR, Role.DIRECTOR]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this department"
        )
    
    return current_user

async def get_user_from_path(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Dependency to get user from path parameter with permission check"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check permissions
    if current_user.id != user_id:
        # Admins and HR can access any user
        if current_user.role in [Role.ADMIN, Role.HR, Role.DIRECTOR]:
            return user
        
        # Managers can only access users in their department
        if current_user.role == Role.MANAGER:
            if user.department_id != current_user.department_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Can only access users in your department"
                )
            return user
        
        # Regular employees can only access themselves
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only access your own profile"
        )
    
    return user

async def get_department_from_path(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Dependency to get department from path with permission check"""
    from app.models import Department
    
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    # Check permissions
    if current_user.role in [Role.ADMIN, Role.HR, Role.DIRECTOR]:
        return department
    
    if current_user.role == Role.MANAGER:
        if current_user.department_id != department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only access your own department"
            )
    
    if current_user.role == Role.EMPLOYEE:
        if current_user.department_id != department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only access your own department"
            )
    
    return department

async def get_skill_from_path(
    skill_id: int,
    db: Session = Depends(get_db)
):
    """Dependency to get skill from path"""
    from app.models import Skill
    
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found"
        )
    
    return skill

async def get_assessment_from_path(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Dependency to get assessment from path with permission check"""
    from app.models import SkillAssessment
    
    assessment = db.query(SkillAssessment).filter(SkillAssessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    # Check permissions
    if current_user.id != assessment.user_id:
        if current_user.role in [Role.ADMIN, Role.HR, Role.DIRECTOR]:
            return assessment
        
        if current_user.role == Role.MANAGER:
            # Get user to check department
            from app.models import User
            user = db.query(User).filter(User.id == assessment.user_id).first()
            if user and user.department_id == current_user.department_id:
                return assessment
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this assessment"
        )
    
    return assessment

async def rate_limit(
    request: Request,
    redis_client = None,  # Would be injected in production
    limit: int = 100,
    window: int = 60  # seconds
):
    """
    Simple rate limiting dependency
    
    Note: In production, use Redis for distributed rate limiting
    """
    # For now, we'll implement a simple in-memory rate limiter
    # In production, replace with Redis-based solution
    
    client_ip = request.client.host
    path = request.url.path
    
    # Create rate limit key
    import time
    current_window = int(time.time() / window)
    key = f"rate_limit:{client_ip}:{path}:{current_window}"
    
    # In production, increment counter in Redis
    # For now, we'll just return (skip rate limiting in development)
    if settings.ENVIRONMENT == "production" and redis_client:
        current = redis_client.incr(key)
        if current == 1:
            redis_client.expire(key, window)
        
        if current > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {window} seconds."
            )
    
    return True

async def validate_json_payload(
    request: Request,
    max_size: int = 1024 * 1024  # 1MB
):
    """Dependency to validate JSON payload size"""
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Payload too large. Maximum size is {max_size / 1024 / 1024}MB"
        )
    
    return True

async def get_pagination_params(
    page: int = 1,
    per_page: int = 20,
    max_per_page: int = 100
) -> Dict[str, int]:
    """Dependency to get pagination parameters"""
    page = max(1, page)
    per_page = min(max(1, per_page), max_per_page)
    
    return {
        "page": page,
        "per_page": per_page,
        "skip": (page - 1) * per_page
    }

async def get_sorting_params(
    sort_by: Optional[str] = None,
    sort_order: str = "asc"  # asc or desc
) -> Dict[str, Any]:
    """Dependency to get sorting parameters"""
    if sort_order not in ["asc", "desc"]:
        sort_order = "asc"
    
    return {
        "sort_by": sort_by,
        "sort_order": sort_order
    }

async def get_filter_params(
    request: Request,
    allowed_filters: Optional[list] = None
) -> Dict[str, Any]:
    """Dependency to extract filter parameters from query string"""
    query_params = dict(request.query_params)
    
    # Remove pagination and sorting params
    query_params.pop("page", None)
    query_params.pop("per_page", None)
    query_params.pop("sort_by", None)
    query_params.pop("sort_order", None)
    
    # Apply allowed filters if specified
    if allowed_filters:
        query_params = {k: v for k, v in query_params.items() if k in allowed_filters}
    
    return query_params

async def get_current_user_preferences(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Dependency to get current user preferences"""
    from app.models import UserPreference
    
    preferences = db.query(UserPreference).filter(
        UserPreference.user_id == current_user.id
    ).all()
    
    # Convert to dictionary
    prefs_dict = {p.key: p.value for p in preferences}
    
    # Set defaults if not present
    defaults = {
        "theme": "light",
        "notifications": "true",
        "language": "ru",
        "timezone": "Europe/Moscow"
    }
    
    for key, value in defaults.items():
        if key not in prefs_dict:
            prefs_dict[key] = value
    
    return prefs_dict

async def validate_csrf_token(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """CSRF protection dependency for state-changing operations"""
    if request.method in ["GET", "HEAD", "OPTIONS"]:
        return True
    
    # Skip CSRF for API endpoints with proper auth
    if request.url.path.startswith("/api/"):
        return True
    
    # For authenticated web requests, check CSRF token
    if current_user:
        csrf_token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
        cookie_token = request.cookies.get("csrf_token")
        
        if not csrf_token or csrf_token != cookie_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid CSRF token"
            )
    
    return True

async def get_request_id(request: Request) -> str:
    """Get or generate request ID for logging"""
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        import uuid
        request_id = str(uuid.uuid4())
    
    return request_id

async def audit_log(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """Dependency for audit logging"""
    from app.models import AuditLog
    
    # Create audit log entry for non-GET requests
    if request.method not in ["GET", "HEAD", "OPTIONS"]:
        audit_entry = AuditLog(
            user_id=current_user.id if current_user else None,
            action=request.method,
            endpoint=request.url.path,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            request_body=None  # In production, sanitize and store relevant parts
        )
        
        db.add(audit_entry)
        db.commit()
    
    yield
    
    # Post-request processing could go here

async def cache_control(
    request: Request,
    max_age: int = 60  # seconds
):
    """Dependency to add cache control headers"""
    from fastapi.responses import Response
    
    # Skip cache for non-GET requests
    if request.method != "GET":
        return
    
    # Add cache control headers
    response = Response()
    response.headers["Cache-Control"] = f"public, max-age={max_age}"
    
    return response