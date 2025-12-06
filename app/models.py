from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates, relationship
import uuid

db = SQLAlchemy()

class TimestampMixin:
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class User(db.Model, TimestampMixin):
    """Модель пользователя"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    patronymic = db.Column(db.String(64))
    position = db.Column(db.String(100))
    role = db.Column(db.Enum('employee', 'manager', 'admin', name='user_roles'),
                    nullable=False, default='employee', index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    is_verified = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime)
    phone = db.Column(db.String(20))
    avatar_url = db.Column(db.String(500))

    # Внешние ключи
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), index=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)

    # Связи с ЯВНЫМ указанием foreign_keys
    department = relationship(
        'Department',
        back_populates='employees',
        foreign_keys=[department_id]
    )

    manager = relationship(
        'User',
        remote_side=[id],
        backref='subordinates',
        foreign_keys=[manager_id]
    )

    ratings = relationship(
        'UserSkillRating',
        back_populates='user',
        cascade='all, delete-orphan',
        lazy='dynamic',
        foreign_keys='UserSkillRating.user_id'  # ← ЯВНО
    )

    rating_history = relationship(
        'RatingHistory',
        back_populates='user',
        cascade='all, delete-orphan',
        foreign_keys='RatingHistory.user_id'  # ← ЯВНО
    )

    notifications = relationship(
        'Notification',
        back_populates='user',
        cascade='all, delete-orphan',
        foreign_keys='Notification.user_id'  # ← ЯВНО
    )


class Department(db.Model, TimestampMixin):
    """Модель отдела"""
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    code = db.Column(db.String(20), unique=True, index=True)

    # Внешние ключи
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Связи с ЯВНЫМ указанием foreign_keys
    employees = relationship(
        'User',
        back_populates='department',
        lazy='dynamic',
        foreign_keys='User.department_id'  # ← ЯВНО
    )

    manager = relationship(
        'User',
        foreign_keys=[manager_id],
        backref='managed_department'
    )

    required_skills = relationship(
        'RequiredDepartmentSkill',
        back_populates='department',
        cascade='all, delete-orphan'
    )


class UserSkillRating(db.Model, TimestampMixin):
    """Модель оценки навыка пользователя"""
    __tablename__ = 'user_skill_ratings'

    id = db.Column(db.Integer, primary_key=True)
    self_score = db.Column(db.Integer, nullable=False)
    manager_score = db.Column(db.Integer)
    final_score = db.Column(db.Integer)
    status = db.Column(db.Enum('pending', 'confirmed', 'rejected', 'adjusted',
                              name='rating_status'), default='pending')
    self_assessment_date = db.Column(db.DateTime)
    manager_assessment_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    manager_notes = db.Column(db.Text)

    # Внешние ключи
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=False, index=True)
    confirmed_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Связи с ЯВНЫМ указанием foreign_keys
    user = relationship(
        'User',
        back_populates='ratings',
        foreign_keys=[user_id]  # ← ЯВНО
    )

    skill = relationship(
        'Skill',
        back_populates='ratings'
    )

    confirmed_by_user = relationship(
        'User',
        foreign_keys=[confirmed_by]  # ← ЯВНО
    )

    history_entries = relationship(
        'RatingHistory',
        back_populates='rating',
        cascade='all, delete-orphan'
    )


class RatingHistory(db.Model, TimestampMixin):
    """Модель истории изменений оценок"""
    __tablename__ = 'rating_history'

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.Enum('created', 'updated', 'confirmed', 'rejected', 'adjusted',
                              name='rating_action'), nullable=False)
    old_self_score = db.Column(db.Integer)
    new_self_score = db.Column(db.Integer)
    old_manager_score = db.Column(db.Integer)
    new_manager_score = db.Column(db.Integer)
    old_final_score = db.Column(db.Integer)
    new_final_score = db.Column(db.Integer)
    old_status = db.Column(db.String(20))
    new_status = db.Column(db.String(20))
    notes = db.Column(db.Text)

    # Внешние ключи
    rating_id = db.Column(db.Integer, db.ForeignKey('user_skill_ratings.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    changed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Связи с ЯВНЫМ указанием foreign_keys
    rating = relationship(
        'UserSkillRating',
        back_populates='history_entries'
    )

    user = relationship(
        'User',
        back_populates='rating_history',
        foreign_keys=[user_id]  # ← ЯВНО
    )

    changed_by = relationship(
        'User',
        foreign_keys=[changed_by_id]  # ← ЯВНО
    )


class Notification(db.Model, TimestampMixin):
    """Модель уведомлений"""
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    type = db.Column(db.Enum('rating_confirmed', 'rating_rejected', 'rating_adjusted',
                            'new_assessment', 'manager_assigned', 'skill_required',
                            'report_ready', 'system', name='notification_type'),
                    nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    data = db.Column(JSONB)
    is_read = db.Column(db.Boolean, default=False, index=True)
    read_at = db.Column(db.DateTime)

    # Внешние ключи
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    rating_id = db.Column(db.Integer, db.ForeignKey('user_skill_ratings.id'))

    # Связи с ЯВНЫМ указанием foreign_keys
    user = relationship(
        'User',
        back_populates='notifications',
        foreign_keys=[user_id]  # ← ЯВНО
    )

    sender = relationship(
        'User',
        foreign_keys=[sender_id]  # ← ЯВНО
    )

    rating = relationship('UserSkillRating')


class SkillCategory(db.Model, TimestampMixin):
    """Модель категории навыков"""
    __tablename__ = 'skill_categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50), default='fa-code')
    color = db.Column(db.String(7), default='#3B82F6')

    skills = relationship('Skill', back_populates='category', lazy='dynamic')


class Skill(db.Model, TimestampMixin):
    """Модель навыка"""
    __tablename__ = 'skills'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, index=True)
    difficulty_level = db.Column(db.Enum('beginner', 'intermediate', 'advanced', 'expert',
                                        name='difficulty_level'), default='intermediate')

    category_id = db.Column(db.Integer, db.ForeignKey('skill_categories.id'), nullable=False)

    category = relationship('SkillCategory', back_populates='skills')

    ratings = relationship(
        'UserSkillRating',
        back_populates='skill',
        lazy='dynamic'
    )

    required_in_departments = relationship(
        'RequiredDepartmentSkill',
        back_populates='skill',
        cascade='all, delete-orphan'
    )


class RequiredDepartmentSkill(db.Model, TimestampMixin):
    """Модель обязательных навыков для отдела"""
    __tablename__ = 'required_department_skills'

    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=False, index=True)
    min_score = db.Column(db.Integer, default=3)
    priority = db.Column(db.Integer, default=1)
    is_required = db.Column(db.Boolean, default=True)

    department = relationship('Department', back_populates='required_skills')
    skill = relationship('Skill', back_populates='required_in_departments')


class Report(db.Model, TimestampMixin):
    """Модель отчетов"""
    __tablename__ = 'reports'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    type = db.Column(db.Enum('department_summary', 'employee_skills', 'skill_gap',
                            'trend_analysis', 'export', name='report_type'),
                    nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    parameters = db.Column(JSONB)
    file_url = db.Column(db.String(500))
    file_format = db.Column(db.Enum('csv', 'excel', 'pdf', 'json', name='file_format'))
    status = db.Column(db.Enum('pending', 'processing', 'completed', 'failed',
                              name='report_status'), default='pending')
    generated_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))

    creator = relationship('User', foreign_keys=[created_by])
    department = relationship('Department')


class AuditLog(db.Model, TimestampMixin):
    """Модель аудита действий пользователей"""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    entity_type = db.Column(db.String(50), index=True)
    entity_id = db.Column(db.Integer)
    old_values = db.Column(JSONB)
    new_values = db.Column(JSONB)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    user = relationship('User')
