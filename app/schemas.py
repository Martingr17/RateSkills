"""
Pydantic schemas for request/response validation
"""
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from pydantic import BaseModel, EmailStr, Field, validator, root_validator
from pydantic import model_validator
from typing import Generic, TypeVar
import re
from enum import Enum

from app.models import Role, AssessmentStatus, GoalStatus, GoalPriority, NotificationType, EventType

# ========== Base Schemas ==========

class BaseSchema(BaseModel):
    """Base schema with common fields"""
    class Config:
        from_attributes = True  # Allows ORM mode (formerly orm_mode)
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
        }

class TimestampMixin(BaseModel):
    """Mixin for timestamp fields"""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# ========== Authentication Schemas ==========

class UserLogin(BaseSchema):
    """Schema for user login"""
    login: str = Field(..., min_length=3, max_length=50, description="Username or email")
    password: str = Field(..., min_length=1, max_length=128, description="Password")

class UserCreate(BaseSchema):
    """Schema for user creation (admin/HR only)"""
    login: str = Field(..., min_length=3, max_length=50, description="Username")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password")
    full_name: str = Field(..., min_length=2, max_length=255, description="Full name")
    department_id: int = Field(..., description="Department ID")
    position: str = Field(..., min_length=2, max_length=100, description="Job position")
    role: Role = Field(default=Role.EMPLOYEE, description="User role")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    hire_date: Optional[date] = Field(None, description="Hire date")
    salary: Optional[float] = Field(None, ge=0, description="Salary")
    bio: Optional[str] = Field(None, description="Biography")
    
    @validator('phone')
    def validate_phone(cls, v):
        if v and not re.match(r'^[\+]?[0-9\s\-\(\)]{10,}$', v):
            raise ValueError('Invalid phone number format')
        return v

class UserUpdate(BaseSchema):
    """Schema for user updates"""
    login: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    department_id: Optional[int] = None
    position: Optional[str] = Field(None, min_length=2, max_length=100)
    role: Optional[Role] = None
    phone: Optional[str] = Field(None, max_length=20)
    hire_date: Optional[date] = None
    salary: Optional[float] = Field(None, ge=0)
    bio: Optional[str] = None
    is_active: Optional[bool] = None
    performance_score: Optional[float] = Field(None, ge=0, le=5)
    skills_required_rated: Optional[bool] = None
    
    @validator('phone')
    def validate_phone(cls, v):
        if v and not re.match(r'^[\+]?[0-9\s\-\(\)]{10,}$', v):
            raise ValueError('Invalid phone number format')
        return v

class UserResponse(BaseSchema, TimestampMixin):
    """Schema for user response (without sensitive data)"""
    id: int
    login: str
    email: EmailStr
    full_name: str
    avatar: str
    department_id: int
    position: str
    role: Role
    phone: Optional[str] = None
    hire_date: Optional[date] = None
    salary: Optional[float] = None
    bio: Optional[str] = None
    performance_score: Optional[float] = None
    skills_required_rated: bool
    is_active: bool
    is_verified: bool
    last_login: Optional[datetime] = None

class UserWithStats(UserResponse):
    """User response with statistics"""
    average_rating: Optional[float] = None
    pending_assessments: int = 0
    skill_score: Optional[float] = None  # For specific skill searches

class Token(BaseSchema):
    """Schema for authentication tokens"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: Optional[int] = None
    role: Optional[Role] = None

class TokenData(BaseSchema):
    """Schema for token payload data"""
    user_id: int
    role: Optional[Role] = None

class PasswordChange(BaseSchema):
    """Schema for password change"""
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

class PasswordResetRequest(BaseSchema):
    """Schema for password reset request"""
    email: EmailStr

class PasswordReset(BaseSchema):
    """Schema for password reset"""
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

# ========== Department Schemas ==========

class DepartmentCreate(BaseSchema):
    """Schema for department creation"""
    name: str = Field(..., min_length=2, max_length=100)
    code: str = Field(..., min_length=2, max_length=10, pattern=r'^[A-Z0-9_]+$')
    description: Optional[str] = None
    manager_id: Optional[int] = None
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')

class DepartmentUpdate(BaseSchema):
    """Schema for department updates"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    code: Optional[str] = Field(None, min_length=2, max_length=10, pattern=r'^[A-Z0-9_]+$')
    description: Optional[str] = None
    manager_id: Optional[int] = None
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')

class DepartmentResponse(BaseSchema, TimestampMixin):
    """Schema for department response"""
    id: int
    name: str
    code: str
    description: Optional[str] = None
    manager_id: Optional[int] = None
    color: str
    manager_name: Optional[str] = None

class DepartmentStats(BaseSchema):
    """Schema for department statistics"""
    department_id: int
    total_users: int
    total_assessments: int
    approved_assessments: int
    pending_assessments: int
    average_score: float
    required_skills: int
    covered_skills: int
    skill_coverage: float

# ========== Skill Category Schemas ==========

class SkillCategoryCreate(BaseSchema):
    """Schema for skill category creation"""
    name: str = Field(..., min_length=2, max_length=100)
    icon: str = Field(default="fa-question", max_length=50)
    color: str = Field(default="#6366f1", pattern=r'^#[0-9A-Fa-f]{6}$')
    description: Optional[str] = None
    order: Optional[int] = Field(0, ge=0)

class SkillCategoryUpdate(BaseSchema):
    """Schema for skill category updates"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    icon: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    description: Optional[str] = None
    order: Optional[int] = Field(None, ge=0)

class SkillCategoryResponse(BaseSchema, TimestampMixin):
    """Schema for skill category response"""
    id: int
    name: str
    icon: str
    color: str
    description: Optional[str] = None
    order: int

# ========== Skill Schemas ==========

class SkillCreate(BaseSchema):
    """Schema for skill creation"""
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    category_id: Optional[int] = None  # Can be null for uncategorized
    difficulty_level: int = Field(default=3, ge=1, le=5)
    required_for_departments: Optional[List[int]] = Field(default_factory=list)

class SkillUpdate(BaseSchema):
    """Schema for skill updates"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    category_id: Optional[int] = None
    difficulty_level: Optional[int] = Field(None, ge=1, le=5)
    required_for_departments: Optional[List[int]] = None
    is_active: Optional[bool] = None

class SkillResponse(BaseSchema, TimestampMixin):
    """Schema for skill response"""
    id: int
    name: str
    description: Optional[str] = None
    category_id: Optional[int] = None
    difficulty_level: int
    is_active: bool
    category_name: Optional[str] = None

class SkillWithStats(SkillResponse):
    """Skill response with statistics"""
    total_assessments: int
    approved_assessments: int
    pending_assessments: int
    average_score: float
    score_distribution: Dict[int, int]
    requiring_departments: List[str]

class CategoryWithSkills(SkillCategoryResponse):
    """Category with its skills"""
    skills: List[SkillResponse] = []

class SkillMatrix(BaseSchema):
    """Schema for skill matrix"""
    skills: List[SkillResponse]
    departments: List[DepartmentResponse]
    matrix: Dict[int, Dict[int, bool]]  # skill_id -> {dept_id -> is_required}

# ========== Skill Assessment Schemas ==========

class SkillAssessmentCreate(BaseSchema):
    """Schema for skill assessment creation (self-assessment)"""
    user_id: int = Field(..., description="User ID")
    skill_id: int = Field(..., description="Skill ID")
    self_score: int = Field(..., ge=1, le=5, description="Self-assessment score (1-5)")
    comment: Optional[str] = None

class SkillAssessmentUpdate(BaseSchema):
    """Schema for skill assessment updates"""
    self_score: Optional[int] = Field(None, ge=1, le=5)
    manager_score: Optional[int] = Field(None, ge=1, le=5)
    status: Optional[AssessmentStatus] = None
    comment: Optional[str] = None
    reject_reason: Optional[str] = None

class SkillAssessmentResponse(BaseSchema, TimestampMixin):
    """Schema for skill assessment response"""
    id: int
    user_id: int
    skill_id: int
    self_score: int
    manager_score: Optional[int] = None
    status: AssessmentStatus
    comment: Optional[str] = None
    reject_reason: Optional[str] = None
    assessed_at: datetime
    approved_by_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    
    # Related data
    user_name: Optional[str] = None
    skill_name: Optional[str] = None
    category_name: Optional[str] = None
    approved_by_name: Optional[str] = None

class AssessmentHistoryResponse(BaseSchema):
    """Schema for assessment history response"""
    id: int
    assessment_id: int
    old_score: Optional[int] = None
    new_score: Optional[int] = None
    changed_by_id: int
    change_type: str
    comment: Optional[str] = None
    changed_at: datetime
    changed_by_name: Optional[str] = None

class AssessmentWithHistory(SkillAssessmentResponse):
    """Assessment with its history"""
    history: List[AssessmentHistoryResponse] = []

class AssessmentStats(BaseSchema):
    """Schema for assessment statistics"""
    user_id: int
    total_assessments: int
    approved_assessments: int
    pending_assessments: int
    rejected_assessments: int
    average_score: float
    required_skills: int
    approved_required_skills: int
    completion_rate: float

# ========== Comparison Schemas ==========

class ComparisonRequest(BaseSchema):
    """Schema for comparison request"""
    user_ids: Optional[List[int]] = None
    department_ids: Optional[List[int]] = None
    skill_ids: Optional[List[int]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    @model_validator(mode='after')  # ✅ Новый синтаксис
    def validate_comparison(self) -> 'ComparisonRequest':
        # Теперь доступ через self
        if self.field1 and self.field2:
            # валидация
            pass
        return self

class ComparisonResult(BaseSchema):
    """Schema for comparison result"""
    entity_id: int
    entity_name: str
    entity_type: str  # "user" or "department"
    skill_scores: Dict[int, float]  # skill_id -> score
    average_score: float

class UserAssessment(BaseSchema):
    """Schema for user assessment data"""
    user_id: int
    user_name: str
    skill_id: int
    skill_name: str
    self_score: int
    manager_score: Optional[int] = None
    status: AssessmentStatus
    assessed_at: datetime

# ========== Goal Schemas ==========

class GoalCreate(BaseSchema):
    """Schema for goal creation"""
    user_id: int = Field(..., description="User ID")
    title: str = Field(..., min_length=1, max_length=255, description="Goal title")
    description: Optional[str] = None
    status: GoalStatus = Field(default=GoalStatus.NOT_STARTED)
    priority: GoalPriority = Field(default=GoalPriority.MEDIUM)
    progress_percentage: int = Field(default=0, ge=0, le=100)
    deadline: Optional[date] = None

class GoalUpdate(BaseSchema):
    """Schema for goal updates"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[GoalStatus] = None
    priority: Optional[GoalPriority] = None
    progress_percentage: Optional[int] = Field(None, ge=0, le=100)
    deadline: Optional[date] = None

class GoalResponse(BaseSchema, TimestampMixin):
    """Schema for goal response"""
    id: int
    user_id: int
    title: str
    description: Optional[str] = None
    status: GoalStatus
    priority: GoalPriority
    progress_percentage: int
    deadline: Optional[date] = None
    completed_at: Optional[datetime] = None
    user_name: Optional[str] = None

class GoalProgress(BaseSchema):
    """Schema for goal progress"""
    goal_id: int
    title: str
    progress_percentage: int
    status: GoalStatus
    priority: GoalPriority
    deadline: Optional[date] = None

# ========== Notification Schemas ==========

class NotificationCreate(BaseSchema):
    """Schema for notification creation"""
    user_id: int
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)
    notification_type: NotificationType = Field(default=NotificationType.INFO)
    action_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class NotificationResponse(BaseSchema, TimestampMixin):
    """Schema for notification response"""
    id: int
    user_id: int
    title: str
    message: str
    notification_type: NotificationType
    is_read: bool
    action_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    read_at: Optional[datetime] = None

# ========== Event Schemas ==========

class EventCreate(BaseSchema):
    """Schema for event creation"""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    event_type: EventType = Field(default=EventType.MEETING)
    location: Optional[str] = None
    start_time: datetime
    end_time: datetime
    all_day: bool = Field(default=False)
    participant_ids: List[int] = Field(default_factory=list)
    
    @validator('end_time')
    def validate_end_time(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('End time must be after start time')
        return v

class EventUpdate(BaseSchema):
    """Schema for event updates"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    event_type: Optional[EventType] = None
    location: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    all_day: Optional[bool] = None
    participant_ids: Optional[List[int]] = None

class EventResponse(BaseSchema, TimestampMixin):
    """Schema for event response"""
    id: int
    title: str
    description: Optional[str] = None
    event_type: EventType
    location: Optional[str] = None
    start_time: datetime
    end_time: datetime
    all_day: bool
    created_by_id: int
    participant_ids: List[int] = []
    created_by_name: Optional[str] = None
    participant_names: List[str] = []

# ========== Feedback Schemas ==========

class FeedbackCreate(BaseSchema):
    """Schema for feedback creation"""
    from_user_id: int
    to_user_id: int
    skill_id: int
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field(..., min_length=1)
    is_anonymous: bool = Field(default=False)

class FeedbackUpdate(BaseSchema):
    """Schema for feedback updates"""
    rating: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = Field(None, min_length=1)
    is_anonymous: Optional[bool] = None
    status: Optional[str] = None

class FeedbackResponse(BaseSchema, TimestampMixin):
    """Schema for feedback response"""
    id: int
    from_user_id: int
    to_user_id: int
    skill_id: int
    rating: int
    comment: str
    is_anonymous: bool
    status: str
    from_user_name: Optional[str] = None
    to_user_name: Optional[str] = None
    skill_name: Optional[str] = None

# ========== Report Schemas ==========

class ReportRequest(BaseSchema):
    """Schema for report generation request"""
    report_type: str = Field(..., description="Type of report: department, skill_gap, trend, user_progress")
    department_id: Optional[int] = None
    user_id: Optional[int] = None
    skill_ids: Optional[List[int]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    format: str = Field(default="csv", pattern="^(csv|json|pdf)$")
    
    @validator('report_type')
    def validate_report_type(cls, v):
        allowed_types = ["department", "skill_gap", "trend", "user_progress"]
        if v not in allowed_types:
            raise ValueError(f"Report type must be one of: {', '.join(allowed_types)}")
        return v

class ExportRequest(BaseSchema):
    """Schema for data export request"""
    export_type: str = Field(..., description="Type of export: users, assessments, skills, department_stats")
    department_id: Optional[int] = None
    user_id: Optional[int] = None
    role: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    format: str = Field(default="csv", pattern="^(csv|json)$")
    
    @validator('export_type')
    def validate_export_type(cls, v):
        allowed_types = ["users", "assessments", "skills", "department_stats"]
        if v not in allowed_types:
            raise ValueError(f"Export type must be one of: {', '.join(allowed_types)}")
        return v

class ReportResponse(BaseSchema):
    """Schema for report response"""
    report_type: str
    generated_at: datetime
    data: Dict[str, Any]
    download_url: Optional[str] = None

class DepartmentReport(BaseSchema):
    """Schema for department report"""
    department_id: int
    department_name: str
    period: Dict[str, datetime]
    statistics: Dict[str, Any]
    skill_coverage: List[Dict[str, Any]]
    top_performers: List[Dict[str, Any]]
    skill_gaps: List[Dict[str, Any]]

class SkillGapAnalysis(BaseSchema):
    """Schema for skill gap analysis"""
    department_id: int
    department_name: str
    required_skills: int
    covered_skills: int
    gap_percentage: float
    skill_details: List[Dict[str, Any]]
    recommendations: List[str]

class TrendAnalysis(BaseSchema):
    """Schema for trend analysis"""
    entity_id: int
    entity_name: str
    entity_type: str  # "user" or "department"
    period: Dict[str, datetime]
    trends: Dict[str, Any]
    data_points: List[Dict[str, Any]]

class UserProgressReport(BaseSchema):
    """Schema for user progress report"""
    user_id: int
    user_name: str
    period: Dict[str, datetime]
    skill_progress: Dict[str, Any]
    goal_progress: Dict[str, Any]
    assessments_history: List[Dict[str, Any]]
    recommendations: List[str]

# ========== Dashboard Schemas ==========

class DashboardStats(BaseSchema):
    """Schema for dashboard statistics"""
    user_id: int
    role: Role
    
    # User-specific stats
    total_skills: Optional[int] = None
    assessed_skills: Optional[int] = None
    pending_assessments: Optional[int] = None
    average_rating: Optional[float] = None
    required_skills: Optional[int] = None
    approved_required_skills: Optional[int] = None
    completion_rate: Optional[float] = None
    
    # Goal stats
    total_goals: Optional[int] = None
    completed_goals: Optional[int] = None
    in_progress_goals: Optional[int] = None
    
    # Manager-specific stats
    total_team_members: Optional[int] = None
    department_assessments: Optional[int] = None
    pending_reviews: Optional[int] = None
    average_department_rating: Optional[float] = None
    skill_coverage: Optional[float] = None
    team_goals: Optional[int] = None
    completed_team_goals: Optional[int] = None
    
    # Admin-specific stats
    total_users: Optional[int] = None
    total_departments: Optional[int] = None
    total_skills_global: Optional[int] = None
    total_assessments: Optional[int] = None
    pending_assessments_global: Optional[int] = None
    approved_assessments: Optional[int] = None
    average_company_rating: Optional[float] = None
    recent_users: Optional[int] = None
    recent_assessments: Optional[int] = None
    
    # Activity
    unread_notifications: Optional[int] = None
    upcoming_events: Optional[int] = None
    recent_feedback: Optional[int] = None
    department_notifications: Optional[int] = None
    department_events: Optional[int] = None
    
    # Charts data
    skill_progress: Optional[List[Dict[str, Any]]] = None
    goal_progress: Optional[List[Dict[str, Any]]] = None
    top_performers: Optional[List[Dict[str, Any]]] = None
    skill_gaps: Optional[List[Dict[str, Any]]] = None
    department_stats: Optional[List[Dict[str, Any]]] = None
    category_stats: Optional[List[Dict[str, Any]]] = None
    activity_trend: Optional[List[Dict[str, Any]]] = None

class UserDashboard(DashboardStats):
    """Schema for user dashboard"""
    pass

class ManagerDashboard(DashboardStats):
    """Schema for manager dashboard"""
    pass

class AdminDashboard(DashboardStats):
    """Schema for admin dashboard"""
    pass

class SkillProgress(BaseSchema):
    """Schema for skill progress"""
    category_id: int
    category_name: str
    total_skills: int
    assessed_skills: int
    progress_percentage: float
    color: str

# ========== System Schemas ==========

class SystemSettingCreate(BaseSchema):
    """Schema for system setting creation"""
    key: str = Field(..., min_length=1, max_length=100)
    value: Optional[str] = None
    description: Optional[str] = None
    category: str = Field(default="general")
    is_public: bool = Field(default=False)

class SystemSettingUpdate(BaseSchema):
    """Schema for system setting updates"""
    value: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    is_public: Optional[bool] = None

class SystemSettingResponse(BaseSchema, TimestampMixin):
    """Schema for system setting response"""
    id: int
    key: str
    value: Optional[str] = None
    description: Optional[str] = None
    category: str
    is_public: bool
    updated_by_name: Optional[str] = None

# ========== Pagination Schemas ==========
T = TypeVar('T')
class PaginatedResponse(BaseSchema, Generic[T]):  # ✅ Добавьте Generic[T]
    """Schema for paginated responses"""
    items: List[T]  # ✅ Используйте T вместо Any
    page: int
    per_page: int
    total: int
    total_pages: int
class PaginationParams(BaseSchema):
    """Schema for pagination parameters"""
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    sort_by: Optional[str] = None
    sort_order: str = Field(default="asc", pattern="^(asc|desc)$")

# ========== Search Schemas ==========

class SearchRequest(BaseSchema):
    """Schema for search requests"""
    query: str = Field(..., min_length=1, max_length=100)
    entity_type: Optional[str] = Field(None, pattern="^(user|skill|assessment|goal)$")
    filters: Optional[Dict[str, Any]] = None

class SearchResponse(BaseSchema):
    """Schema for search responses"""
    query: str
    entity_type: str
    total_results: int
    results: List[Dict[str, Any]]

# ========== Statistics Schemas ==========

class UserStats(BaseSchema):
    """Schema for user statistics"""
    user_id: int
    total_skills: int
    approved_skills: int
    pending_skills: int
    average_rating: float
    total_goals: int
    completed_goals: int
    performance_score: float
    last_assessment_date: Optional[datetime] = None

# ========== Validation Error Schemas ==========

class ValidationError(BaseSchema):
    """Schema for validation errors"""
    loc: List[str]
    msg: str
    type: str

class HTTPError(BaseSchema):
    """Schema for HTTP errors"""
    error: bool
    code: int
    message: str
    details: Optional[List[ValidationError]] = None
    path: str
    timestamp: str

# ========== Health Check Schemas ==========

class HealthCheck(BaseSchema):
    """Schema for health check response"""
    status: str
    service: str
    version: str
    timestamp: str
    database: str

# ========== Export all schemas ==========

__all__ = [
    # Authentication
    "UserLogin", "UserCreate", "UserUpdate", "UserResponse", "UserWithStats",
    "Token", "TokenData", "PasswordChange", "PasswordResetRequest", "PasswordReset",
    
    # Department
    "DepartmentCreate", "DepartmentUpdate", "DepartmentResponse", "DepartmentStats",
    
    # Skill Category
    "SkillCategoryCreate", "SkillCategoryUpdate", "SkillCategoryResponse",
    
    # Skill
    "SkillCreate", "SkillUpdate", "SkillResponse", "SkillWithStats",
    "CategoryWithSkills", "SkillMatrix",
    
    # Skill Assessment
    "SkillAssessmentCreate", "SkillAssessmentUpdate", "SkillAssessmentResponse",
    "AssessmentHistoryResponse", "AssessmentWithHistory", "AssessmentStats",
    
    # Comparison
    "ComparisonRequest", "ComparisonResult", "UserAssessment",
    
    # Goal
    "GoalCreate", "GoalUpdate", "GoalResponse", "GoalProgress",
    
    # Notification
    "NotificationCreate", "NotificationResponse",
    
    # Event
    "EventCreate", "EventUpdate", "EventResponse",
    
    # Feedback
    "FeedbackCreate", "FeedbackUpdate", "FeedbackResponse",
    
    # Report
    "ReportRequest", "ExportRequest", "ReportResponse", "DepartmentReport",
    "SkillGapAnalysis", "TrendAnalysis", "UserProgressReport",
    
    # Dashboard
    "DashboardStats", "UserDashboard", "ManagerDashboard", "AdminDashboard",
    "SkillProgress",
    
    # System
    "SystemSettingCreate", "SystemSettingUpdate", "SystemSettingResponse",
    
    # Pagination
    "PaginatedResponse", "PaginationParams",
    
    # Search
    "SearchRequest", "SearchResponse",
    
    # Statistics
    "UserStats",
    
    # Error
    "ValidationError", "HTTPError",
    
    # Health
    "HealthCheck",
    
    # Base
    "BaseSchema", "TimestampMixin",
]
