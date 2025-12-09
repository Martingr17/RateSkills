"""
SQLAlchemy database models for SkillMatrix application
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, 
    ForeignKey, Text, Enum, Table, JSON, func
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import expression
from sqlalchemy import UniqueConstraint
from datetime import datetime
import enum
import re

from app.database import Base

# Association tables for many-to-many relationships
skill_department_required = Table(
    'skill_department_required',
    Base.metadata,
    Column('skill_id', Integer, ForeignKey('skills.id'), primary_key=True),
    Column('department_id', Integer, ForeignKey('departments.id'), primary_key=True),
    Column('created_at', DateTime, default=datetime.utcnow)
)

event_participants = Table(
    'event_participants',
    Base.metadata,
    Column('event_id', Integer, ForeignKey('events.id'), primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('created_at', DateTime, default=datetime.utcnow)
)

# Enums
class Role(str, enum.Enum):
    """User roles"""
    EMPLOYEE = "employee"
    MANAGER = "manager"
    ADMIN = "admin"
    HR = "hr"
    DIRECTOR = "director"

class AssessmentStatus(str, enum.Enum):
    """Skill assessment statuses"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DRAFT = "draft"

class GoalStatus(str, enum.Enum):
    """Goal statuses"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"

class GoalPriority(str, enum.Enum):
    """Goal priorities"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class NotificationType(str, enum.Enum):
    """Notification types"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"

class EventType(str, enum.Enum):
    """Event types"""
    MEETING = "meeting"
    TRAINING = "training"
    REVIEW = "review"
    HOLIDAY = "holiday"
    OTHER = "other"

class User(Base):
    """User model for employees, managers, admins, etc."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    login = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    avatar = Column(String(10), default="??")
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    position = Column(String(100), nullable=False)
    role = Column(Enum(Role), default=Role.EMPLOYEE, nullable=False)
    phone = Column(String(20))
    hire_date = Column(DateTime, default=datetime.utcnow)
    salary = Column(Float)
    bio = Column(Text)
    performance_score = Column(Float, default=0.0)
    skills_required_rated = Column(Boolean, default=False)
    
    # Status and timestamps
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False)
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deactivated_at = Column(DateTime)
    
    # Security
    reset_token = Column(String(100), unique=True, index=True)
    reset_token_expiry = Column(DateTime)
    refresh_token = Column(String(255))
    refresh_token_expiry = Column(DateTime)
    api_key = Column(String(64), unique=True, index=True)
    api_key_expiry = Column(DateTime)
    
    # Relationships
    department = relationship("Department", back_populates="users")
    skill_assessments = relationship("SkillAssessment", back_populates="user", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    created_events = relationship("Event", back_populates="created_by", foreign_keys="Event.created_by_id")
    events = relationship("Event", secondary=event_participants, back_populates="participants")
    given_feedback = relationship("Feedback", back_populates="from_user", foreign_keys="Feedback.from_user_id")
    received_feedback = relationship("Feedback", back_populates="to_user", foreign_keys="Feedback.to_user_id")
    audit_logs = relationship("AuditLog", back_populates="user")
    
    # Manager relationships
    managed_department = relationship("Department", back_populates="manager", uselist=False, foreign_keys="Department.manager_id")
    
    # Validators
    @validates('email')
    def validate_email(self, key, email):
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise ValueError("Invalid email format")
        return email.lower()
    
    @validates('phone')
    def validate_phone(self, key, phone):
        if phone and not re.match(r'^[\+]?[0-9\s\-\(\)]{10,}$', phone):
            raise ValueError("Invalid phone number format")
        return phone
    
    def __repr__(self):
        return f"<User(id={self.id}, login='{self.login}', role='{self.role}')>"

class Department(Base):
    """Department model"""
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    code = Column(String(10), unique=True, nullable=False)  # e.g., "DEV", "HR", "SALES"
    description = Column(Text)
    manager_id = Column(Integer, ForeignKey("users.id"))
    color = Column(String(7), default="#6366f1")  # Hex color for UI
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    manager = relationship("User", back_populates="managed_department", foreign_keys=[manager_id])
    users = relationship("User", back_populates="department")
    skills_required = relationship("Skill", secondary=skill_department_required, back_populates="required_for_departments")
    
    def __repr__(self):
        return f"<Department(id={self.id}, name='{self.name}')>"

class SkillCategory(Base):
    """Skill category model (e.g., Frontend, Backend, Design)"""
    __tablename__ = "skill_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    icon = Column(String(50), default="fa-question")  # FontAwesome icon class
    color = Column(String(7), default="#6366f1")  # Hex color
    description = Column(Text)
    order = Column(Integer, default=0)  # For sorting
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    skills = relationship("Skill", back_populates="category", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<SkillCategory(id={self.id}, name='{self.name}')>"

class Skill(Base):
    """Skill model (e.g., JavaScript, Python, React)"""
    __tablename__ = "skills"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    category_id = Column(Integer, ForeignKey("skill_categories.id"), nullable=False)
    difficulty_level = Column(Integer, default=3)  # 1-5 scale
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    category = relationship("SkillCategory", back_populates="skills")
    assessments = relationship("SkillAssessment", back_populates="skill", cascade="all, delete-orphan")
    required_for_departments = relationship("Department", secondary=skill_department_required, back_populates="skills_required")
    feedback = relationship("Feedback", back_populates="skill", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Skill(id={self.id}, name='{self.name}')>"

class SkillAssessment(Base):
    """Skill assessment model (user's self-assessment)"""
    __tablename__ = "skill_assessments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=False)
    self_score = Column(Integer, nullable=False)  # 1-5 scale
    manager_score = Column(Integer)  # Manager's adjusted score
    status = Column(Enum(AssessmentStatus), default=AssessmentStatus.PENDING, nullable=False)
    comment = Column(Text)
    reject_reason = Column(Text)  # If rejected by manager
    
    # Timestamps
    assessed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    approved_by_id = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="skill_assessments", foreign_keys=[user_id])
    skill = relationship("Skill", back_populates="assessments")
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    history = relationship("AssessmentHistory", back_populates="assessment", cascade="all, delete-orphan")
    
    # Validators
    @validates('self_score', 'manager_score')
    def validate_score(self, key, score):
        if score is not None and (score < 1 or score > 5):
            raise ValueError("Score must be between 1 and 5")
        return score
    
    def __repr__(self):
        return f"<SkillAssessment(id={self.id}, user={self.user_id}, skill={self.skill_id}, score={self.self_score})>"

class AssessmentHistory(Base):
    """History of changes to skill assessments"""
    __tablename__ = "assessment_history"
    
    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("skill_assessments.id"), nullable=False)
    old_score = Column(Integer)  # Previous score
    new_score = Column(Integer)  # New score
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    change_type = Column(String(50), nullable=False)  # created, updated, approved, rejected
    comment = Column(Text)
    
    # Timestamps
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    assessment = relationship("SkillAssessment", back_populates="history")
    changed_by = relationship("User")
    
    def __repr__(self):
        return f"<AssessmentHistory(id={self.id}, assessment={self.assessment_id}, change='{self.change_type}')>"

class Goal(Base):
    """User goals model"""
    __tablename__ = "goals"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(Enum(GoalStatus), default=GoalStatus.NOT_STARTED, nullable=False)
    priority = Column(Enum(GoalPriority), default=GoalPriority.MEDIUM, nullable=False)
    progress_percentage = Column(Integer, default=0)  # 0-100
    
    # Dates
    deadline = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="goals")
    
    # Validators
    @validates('progress_percentage')
    def validate_progress(self, key, progress):
        if progress < 0 or progress > 100:
            raise ValueError("Progress must be between 0 and 100")
        return progress
    
    def __repr__(self):
        return f"<Goal(id={self.id}, title='{self.title}', status='{self.status}')>"

class Notification(Base):
    """Notification model for user alerts"""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(Enum(NotificationType), default=NotificationType.INFO, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    action_url = Column(String(500))  # URL for notification action
    notification_metadata = Column(JSON)  # Additional data
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    read_at = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="notifications")
    
    def __repr__(self):
        return f"<Notification(id={self.id}, user={self.user_id}, title='{self.title}')>"

class Event(Base):
    """Calendar event model"""
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    event_type = Column(Enum(EventType), default=EventType.MEETING, nullable=False)
    location = Column(String(255))
    
    # Dates
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    all_day = Column(Boolean, default=False)
    
    # Organizer
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    created_by = relationship("User", back_populates="created_events", foreign_keys=[created_by_id])
    participants = relationship("User", secondary=event_participants, back_populates="events")
    
    def __repr__(self):
        return f"<Event(id={self.id}, title='{self.title}', start='{self.start_time}')>"

class Feedback(Base):
    """Feedback model (peer reviews)"""
    __tablename__ = "feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5 scale
    comment = Column(Text, nullable=False)
    is_anonymous = Column(Boolean, default=False)
    status = Column(String(20), default="pending")  # pending, approved, rejected
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    from_user = relationship("User", back_populates="given_feedback", foreign_keys=[from_user_id])
    to_user = relationship("User", back_populates="received_feedback", foreign_keys=[to_user_id])
    skill = relationship("Skill", back_populates="feedback")
    
    # Validators
    @validates('rating')
    def validate_rating(self, key, rating):
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")
        return rating
    
    def __repr__(self):
        return f"<Feedback(id={self.id}, from={self.from_user_id}, to={self.to_user_id}, rating={self.rating})>"

class UserPreference(Base):
    """User preferences/settings model"""
    __tablename__ = "user_preferences"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key = Column(String(100), nullable=False)
    value = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")

    # ✅ ПРАВИЛЬНО: используем UniqueConstraint
    __table_args__ = (
        UniqueConstraint('user_id', 'key', name='unique_user_key'),
    )

    def __repr__(self):
        return f"<UserPreference(id={self.id}, user={self.user_id}, key='{self.key}')>"

class AuditLog(Base):
    """Audit log for tracking system activities"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(50), nullable=False)  # CREATE, UPDATE, DELETE, LOGIN, etc.
    entity_type = Column(String(50), nullable=False)  # User, Skill, Assessment, etc.
    entity_id = Column(Integer)
    endpoint = Column(String(500), nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    request_body = Column(Text)
    response_status = Column(Integer)
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', user={self.user_id})>"

class Report(Base):
    """Generated reports model"""
    __tablename__ = "reports"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    report_type = Column(String(50), nullable=False)  # department, skill_gap, trend, etc.
    format = Column(String(10), default="csv")  # csv, json, pdf
    parameters = Column(JSON)  # Report parameters
    generated_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # File information
    file_path = Column(String(500))
    file_size = Column(Integer)
    download_count = Column(Integer, default=0)
    
    # Timestamps
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime)  # For automatic cleanup
    
    # Relationships
    generated_by = relationship("User")
    
    def __repr__(self):
        return f"<Report(id={self.id}, name='{self.name}', type='{self.report_type}')>"

class SystemSetting(Base):
    """System configuration settings"""
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    description = Column(Text)
    category = Column(String(50), default="general")
    is_public = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by_id = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    updated_by = relationship("User")
    
    def __repr__(self):
        return f"<SystemSetting(id={self.id}, key='{self.key}')>"

# Export all models
__all__ = [
    "User",
    "Department", 
    "SkillCategory",
    "Skill",
    "SkillAssessment",
    "AssessmentHistory",
    "Goal",
    "Notification",
    "Event",
    "Feedback",
    "UserPreference",
    "AuditLog",
    "Report",
    "SystemSetting",
    "Role",
    "AssessmentStatus",
    "GoalStatus",
    "GoalPriority",
    "NotificationType",
    "EventType",
]
