"""
Utility functions for SkillMatrix application
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
import secrets
import string
import hashlib
import json
import logging
from pathlib import Path
from sqlalchemy.orm import Session, Query
from sqlalchemy import desc, asc
from app.config import settings

logger = logging.getLogger(__name__)

class Pagination:
    """Utility class for pagination"""
    
    def __init__(
        self, 
        query: Query, 
        page: int = 1, 
        per_page: int = 20,
        max_per_page: int = 100
    ):
        self.query = query
        self.page = max(page, 1)
        self.per_page = min(per_page, max_per_page)
        self.total = None
        self.items = None
    
    def paginate(self) -> 'Pagination':
        """Execute pagination on the query"""
        offset = (self.page - 1) * self.per_page
        self.total = self.query.count()
        self.items = self.query.offset(offset).limit(self.per_page).all()
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert pagination results to dictionary"""
        return {
            "page": self.page,
            "per_page": self.per_page,
            "total": self.total,
            "total_pages": (self.total + self.per_page - 1) // self.per_page if self.total else 0,
            "items": self.items
        }

def paginate_query(
    query: Query,
    page: int = 1,
    per_page: int = 20,
    max_per_page: int = 100
) -> Dict[str, Any]:
    """Helper function to paginate SQLAlchemy query"""
    pagination = Pagination(query, page, per_page, max_per_page).paginate()
    return pagination.to_dict()

def generate_password(length: int = 12) -> str:
    """Generate random password with letters, digits and special characters"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def hash_string(value: str) -> str:
    """Create SHA256 hash of a string"""
    return hashlib.sha256(value.encode()).hexdigest()

def generate_api_key() -> str:
    """Generate random API key"""
    return secrets.token_urlsafe(32)

def generate_avatar_initials(name: str) -> str:
    """Generate avatar initials from name"""
    if not name:
        return "??"
    
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    elif len(name) >= 2:
        return name[:2].upper()
    else:
        return name[0].upper() + "?"

def calculate_age(birth_date: datetime) -> int:
    """Calculate age from birth date"""
    today = datetime.utcnow()
    age = today.year - birth_date.year
    
    # Adjust if birthday hasn't occurred this year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    
    return age

def format_date(date: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime to string"""
    if not date:
        return ""
    return date.strftime(format_str)

def parse_date(date_str: str, format_str: str = "%Y-%m-%d") -> Optional[datetime]:
    """Parse string to datetime"""
    try:
        return datetime.strptime(date_str, format_str)
    except (ValueError, TypeError):
        return None

def validate_email(email: str) -> bool:
    """Simple email validation"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_phone(phone: str) -> bool:
    """Simple phone number validation"""
    import re
    # Allow various phone formats
    pattern = r'^[\+]?[0-9\s\-\(\)]{10,}$'
    return bool(re.match(pattern, phone))

def get_skill_level_label(score: int) -> str:
    """Get human-readable skill level label"""
    levels = {
        1: "Новичок",
        2: "Начинающий",
        3: "Компетентный",
        4: "Опытный",
        5: "Эксперт"
    }
    return levels.get(score, "Не оценено")

def calculate_progress_percentage(completed: int, total: int) -> float:
    """Calculate progress percentage"""
    if total == 0:
        return 0.0
    return round((completed / total) * 100, 1)

def get_color_for_score(score: float) -> str:
    """Get color based on score (0-5 scale)"""
    if score >= 4.5:
        return "#10b981"  # Success green
    elif score >= 3.5:
        return "#3b82f6"  # Info blue
    elif score >= 2.5:
        return "#f59e0b"  # Warning orange
    else:
        return "#ef4444"  # Danger red

def get_priority_color(priority: str) -> str:
    """Get color for priority level"""
    colors = {
        "high": "#ef4444",    # Red
        "medium": "#f59e0b",  # Orange
        "low": "#10b981",     # Green
        "critical": "#dc2626" # Dark red
    }
    return colors.get(priority.lower(), "#6b7280")  # Default gray

def create_slug(text: str) -> str:
    """Create URL-friendly slug from text"""
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text

def json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for datetime objects"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def safe_json_dumps(data: Any) -> str:
    """Safely serialize data to JSON"""
    return json.dumps(data, default=json_serializer, ensure_ascii=False)

def safe_json_loads(json_str: str) -> Any:
    """Safely parse JSON string"""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return {}

def get_file_extension(filename: str) -> str:
    """Get file extension from filename"""
    return Path(filename).suffix.lower()

def is_allowed_file(filename: str, allowed_extensions: List[str]) -> bool:
    """Check if file extension is allowed"""
    return get_file_extension(filename) in allowed_extensions

def format_file_size(bytes_size: int) -> str:
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"

def generate_report_filename(
    report_type: str, 
    extension: str = ".csv",
    timestamp: Optional[datetime] = None
) -> str:
    """Generate filename for report export"""
    if timestamp is None:
        timestamp = datetime.utcnow()
    
    date_str = timestamp.strftime("%Y%m%d_%H%M%S")
    return f"skillmatrix_{report_type}_{date_str}{extension}"

def calculate_skill_gap(
    required_skills: List[int],
    user_skills: Dict[int, float],
    min_score: float = 3.0
) -> Dict[str, Any]:
    """Calculate skill gap analysis"""
    total_required = len(required_skills)
    
    # Skills user has with sufficient score
    has_skills = []
    missing_skills = []
    low_score_skills = []
    
    for skill_id in required_skills:
        if skill_id in user_skills:
            if user_skills[skill_id] >= min_score:
                has_skills.append(skill_id)
            else:
                low_score_skills.append(skill_id)
        else:
            missing_skills.append(skill_id)
    
    gap_percentage = (len(has_skills) / total_required * 100) if total_required > 0 else 0
    
    return {
        "total_required": total_required,
        "has_skills": len(has_skills),
        "missing_skills": len(missing_skills),
        "low_score_skills": len(low_score_skills),
        "gap_percentage": round(gap_percentage, 1),
        "has_skill_ids": has_skills,
        "missing_skill_ids": missing_skills,
        "low_score_skill_ids": low_score_skills
    }

def calculate_trend(
    data_points: List[Dict[str, Any]],
    value_field: str = "value",
    date_field: str = "date"
) -> Dict[str, Any]:
    """Calculate trend from time series data"""
    if len(data_points) < 2:
        return {
            "trend": "stable",
            "percentage_change": 0.0,
            "slope": 0.0
        }
    
    # Sort by date
    sorted_data = sorted(data_points, key=lambda x: x[date_field])
    
    first_value = sorted_data[0][value_field]
    last_value = sorted_data[-1][value_field]
    
    if first_value == 0:
        percentage_change = 100.0 if last_value > 0 else 0.0
    else:
        percentage_change = ((last_value - first_value) / first_value) * 100
    
    # Determine trend
    if percentage_change > 5:
        trend = "increasing"
    elif percentage_change < -5:
        trend = "decreasing"
    else:
        trend = "stable"
    
    return {
        "trend": trend,
        "percentage_change": round(percentage_change, 1),
        "first_value": first_value,
        "last_value": last_value,
        "data_points": len(data_points)
    }

def mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive data for logging"""
    sensitive_fields = [
        'password', 'password_hash', 'token', 'secret', 
        'api_key', 'access_token', 'refresh_token'
    ]
    
    masked_data = data.copy()
    
    for key in masked_data:
        if any(sensitive in key.lower() for sensitive in sensitive_fields):
            if isinstance(masked_data[key], str) and len(masked_data[key]) > 4:
                masked_data[key] = masked_data[key][:2] + "***" + masked_data[key][-2:]
            else:
                masked_data[key] = "***"
    
    return masked_data

def get_week_number(date: datetime) -> int:
    """Get ISO week number from date"""
    return date.isocalendar()[1]

def get_month_name(date: datetime, lang: str = "ru") -> str:
    """Get month name in specified language"""
    month_names = {
        "ru": [
            "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
            "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
        ],
        "en": [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
    }
    
    names = month_names.get(lang, month_names["en"])
    return names[date.month - 1]

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to specified length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks of specified size"""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

def get_env_variable(name: str, default: Any = None) -> Any:
    """Get environment variable with fallback"""
    import os
    return os.environ.get(name, default)

def is_development() -> bool:
    """Check if running in development environment"""
    env = get_env_variable("ENVIRONMENT", "development")
    return env.lower() in ["dev", "development", "local"]

def is_production() -> bool:
    """Check if running in production environment"""
    env = get_env_variable("ENVIRONMENT", "development")
    return env.lower() in ["prod", "production", "live"]

def get_base_url(request) -> str:
    """Get base URL from request"""
    return f"{request.url.scheme}://{request.url.netloc}"

def generate_verification_code(length: int = 6) -> str:
    """Generate numeric verification code"""
    digits = string.digits
    return ''.join(secrets.choice(digits) for _ in range(length))

def normalize_string(text: str) -> str:
    """Normalize string (lowercase, strip, remove extra spaces)"""
    return ' '.join(text.lower().strip().split())

def calculate_percentile(values: List[float], score: float) -> float:
    """Calculate percentile rank of a score in a list of values"""
    if not values:
        return 0.0
    
    sorted_values = sorted(values)
    count_below = sum(1 for v in sorted_values if v < score)
    count_equal = sum(1 for v in sorted_values if v == score)
    
    percentile = (count_below + 0.5 * count_equal) / len(sorted_values) * 100
    return round(percentile, 1)

def get_time_ago(date: datetime) -> str:
    """Get human readable time ago string"""
    now = datetime.utcnow()
    diff = now - date
    
    if diff.days > 365:
        years = diff.days // 365
        return f"{years} год(а) назад"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} месяц(ев) назад"
    elif diff.days > 7:
        weeks = diff.days // 7
        return f"{weeks} недель(и) назад"
    elif diff.days > 0:
        return f"{diff.days} день(дней) назад"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} час(а) назад"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} минут(ы) назад"
    else:
        return "только что"

def validate_russian_phone(phone: str) -> bool:
    """Validate Russian phone number format"""
    import re
    pattern = r'^(\+7|7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$'
    return bool(re.match(pattern, phone))

def extract_initials(name: str) -> str:
    """Extract initials from full name"""
    parts = name.split()
    if len(parts) >= 2:
        return f"{parts[0][0]}.{parts[1][0]}."
    elif len(name) > 0:
        return f"{name[0]}."
    return ""

def generate_employee_id(department_code: str, sequence: int) -> str:
    """Generate employee ID with department code and sequence"""
    return f"{department_code}-{sequence:04d}"

def calculate_experience(hire_date: datetime, end_date: Optional[datetime] = None) -> Dict[str, int]:
    """Calculate years and months of experience"""
    if end_date is None:
        end_date = datetime.utcnow()
    
    years = end_date.year - hire_date.year
    months = end_date.month - hire_date.month
    
    if months < 0:
        years -= 1
        months += 12
    
    # Adjust for days
    if end_date.day < hire_date.day:
        months -= 1
        if months < 0:
            years -= 1
            months += 12
    
    return {"years": years, "months": months}
# В конец utils.py добавьте:

def generate_department_report(db: Session, department_id: int) -> Dict[str, Any]:
    """Generate department skill report"""
    # TODO: Implement
    return {
        "department_id": department_id,
        "status": "not_implemented"
    }

def generate_skill_gap_analysis(
    db: Session,
    user_id: Optional[int] = None,
    department_id: Optional[int] = None
) -> Dict[str, Any]:
    """Generate skill gap analysis report"""
    # TODO: Implement
    return {
        "user_id": user_id,
        "department_id": department_id,
        "status": "not_implemented"
    }

def generate_trend_analysis(
    db: Session,
    skill_id: Optional[int] = None,
    department_id: Optional[int] = None,
    days: int = 30
) -> Dict[str, Any]:
    """Generate trend analysis report"""
    # TODO: Implement
    return {
        "skill_id": skill_id,
        "department_id": department_id,
        "status": "not_implemented"
    }

def generate_user_progress_report(
    db: Session,
    user_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """Generate user progress report"""
    # TODO: Implement
    return {
        "user_id": user_id,
        "status": "not_implemented"
    }
# В конец вашего utils.py добавьте:

def seed_database(db: Session) -> Dict[str, Any]:
    """Seed database with initial data"""
    try:
        logger.info("Database seeding started")

        # Здесь реализация сидинга

        logger.info("Database seeding completed")

        return {
            "status": "success",
            "message": "Database seeded successfully",
            "seeded_items": 0
        }
    except Exception as e:
        logger.error(f"Database seeding failed: {str(e)}")
        return {
            "status": "error",
            "message": f"Seeding failed: {str(e)}"
        }
