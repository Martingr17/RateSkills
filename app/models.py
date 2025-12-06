from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates
import uuid
from . import db

class TimestampMixin:
    """Миксин для добавления временных меток"""
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class Department(db.Model, TimestampMixin):
    """Модель отдела"""
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    code = db.Column(db.String(20), unique=True, index=True)  # Код отдела
    
    # Связи
    employees = db.relationship('User', back_populates='department', lazy='dynamic')
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    manager = db.relationship('User', foreign_keys=[manager_id], backref='managed_department')
    required_skills = db.relationship('RequiredDepartmentSkill', back_populates='department', 
                                     cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Department {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'code': self.code,
            'manager_id': self.manager_id,
            'employee_count': self.employees.count(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class SkillCategory(db.Model, TimestampMixin):
    """Модель категории навыков"""
    __tablename__ = 'skill_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50), default='fa-code')  # Иконка FontAwesome
    color = db.Column(db.String(7), default='#3B82F6')  # HEX цвет
    
    # Связи
    skills = db.relationship('Skill', back_populates='category', lazy='dynamic')
    
    def __repr__(self):
        return f'<SkillCategory {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'color': self.color,
            'skill_count': self.skills.count(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class Skill(db.Model, TimestampMixin):
    """Модель навыка"""
    __tablename__ = 'skills'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, index=True)
    difficulty_level = db.Column(db.Enum('beginner', 'intermediate', 'advanced', 'expert', 
                                        name='difficulty_level'), default='intermediate')
    
    # Внешние ключи
    category_id = db.Column(db.Integer, db.ForeignKey('skill_categories.id'), nullable=False)
    
    # Связи
    category = db.relationship('SkillCategory', back_populates='skills')
    ratings = db.relationship('UserSkillRating', back_populates='skill', lazy='dynamic')
    required_in_departments = db.relationship('RequiredDepartmentSkill', 
                                             back_populates='skill', 
                                             cascade='all, delete-orphan')
    
    # Индексы
    __table_args__ = (
        db.Index('idx_skill_category', 'category_id', 'is_active'),
    )
    
    def __repr__(self):
        return f'<Skill {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category_id': self.category_id,
            'category': self.category.to_dict() if self.category else None,
            'is_active': self.is_active,
            'difficulty_level': self.difficulty_level,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


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
    patronymic = db.Column(db.String(64))  # Отчество
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
    
    # Связи
    department = db.relationship('Department', back_populates='employees')
    manager = db.relationship('User', remote_side=[id], backref='subordinates')
    ratings = db.relationship('UserSkillRating', back_populates='user', 
                            cascade='all, delete-orphan', lazy='dynamic')
    rating_history = db.relationship('RatingHistory', back_populates='user', 
                                   cascade='all, delete-orphan')
    notifications = db.relationship('Notification', back_populates='user', 
                                  foreign_keys='Notification.user_id',
                                  cascade='all, delete-orphan')
    
    # Индексы
    __table_args__ = (
        db.Index('idx_user_department_role', 'department_id', 'role', 'is_active'),
    )
    
    @hybrid_property
    def full_name(self):
        """Полное имя пользователя"""
        if self.patronymic:
            return f'{self.last_name} {self.first_name} {self.patronymic}'
        return f'{self.last_name} {self.first_name}'
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def to_dict(self, include_ratings=False):
        """Преобразование пользователя в словарь"""
        data = {
            'id': self.id,
            'uuid': str(self.uuid),
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'patronymic': self.patronymic,
            'full_name': self.full_name,
            'position': self.position,
            'role': self.role,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'phone': self.phone,
            'avatar_url': self.avatar_url,
            'department_id': self.department_id,
            'manager_id': self.manager_id,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        if include_ratings:
            data['ratings'] = [rating.to_dict() for rating in self.ratings]
            
        return data


class UserSkillRating(db.Model, TimestampMixin):
    """Модель оценки навыка пользователя"""
    __tablename__ = 'user_skill_ratings'
    
    id = db.Column(db.Integer, primary_key=True)
    self_score = db.Column(db.Integer, nullable=False)  # Самооценка 1-5
    manager_score = db.Column(db.Integer)  # Оценка руководителя 1-5
    final_score = db.Column(db.Integer)  # Финальная оценка (подтвержденная)
    status = db.Column(db.Enum('pending', 'confirmed', 'rejected', 'adjusted', 
                              name='rating_status'), default='pending')
    self_assessment_date = db.Column(db.DateTime)
    manager_assessment_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)  # Комментарии пользователя
    manager_notes = db.Column(db.Text)  # Комментарии руководителя
    
    # Внешние ключи
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=False, index=True)
    confirmed_by = db.Column(db.Integer, db.ForeignKey('users.id'))  # Кто подтвердил
    
    # Связи
    user = db.relationship('User', back_populates='ratings', foreign_keys=[user_id])
    skill = db.relationship('Skill', back_populates='ratings')
    confirmed_by_user = db.relationship('User', foreign_keys=[confirmed_by])
    history_entries = db.relationship('RatingHistory', back_populates='rating', 
                                     cascade='all, delete-orphan')
    
    # Ограничения
    __table_args__ = (
        db.UniqueConstraint('user_id', 'skill_id', name='unique_user_skill'),
        db.CheckConstraint('self_score >= 1 AND self_score <= 5', name='check_self_score'),
        db.CheckConstraint('manager_score >= 1 AND manager_score <= 5', name='check_manager_score'),
        db.CheckConstraint('final_score >= 1 AND final_score <= 5', name='check_final_score'),
        db.Index('idx_user_skill_status', 'user_id', 'skill_id', 'status'),
    )
    
    @validates('self_score', 'manager_score', 'final_score')
    def validate_score(self, key, value):
        """Валидация оценки (1-5)"""
        if value is not None and (value < 1 or value > 5):
            raise ValueError(f'{key} must be between 1 and 5')
        return value
    
    @hybrid_property
    def effective_score(self):
        """Эффективная оценка (самооценка или подтвержденная)"""
        if self.final_score:
            return self.final_score
        return self.self_score
    
    def __repr__(self):
        return f'<UserSkillRating user:{self.user_id} skill:{self.skill_id} score:{self.effective_score}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'skill_id': self.skill_id,
            'skill_name': self.skill.name if self.skill else None,
            'skill_category': self.skill.category.name if self.skill and self.skill.category else None,
            'self_score': self.self_score,
            'manager_score': self.manager_score,
            'final_score': self.final_score,
            'effective_score': self.effective_score,
            'status': self.status,
            'notes': self.notes,
            'manager_notes': self.manager_notes,
            'self_assessment_date': self.self_assessment_date.isoformat() if self.self_assessment_date else None,
            'manager_assessment_date': self.manager_assessment_date.isoformat() if self.manager_assessment_date else None,
            'confirmed_by': self.confirmed_by,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


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
    
    # Связи
    rating = db.relationship('UserSkillRating', back_populates='history_entries')
    user = db.relationship('User', back_populates='rating_history', foreign_keys=[user_id])
    changed_by = db.relationship('User', foreign_keys=[changed_by_id])
    
    def __repr__(self):
        return f'<RatingHistory rating:{self.rating_id} action:{self.action}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'rating_id': self.rating_id,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else None,
            'changed_by_id': self.changed_by_id,
            'changed_by_name': self.changed_by.full_name if self.changed_by else None,
            'action': self.action,
            'old_self_score': self.old_self_score,
            'new_self_score': self.new_self_score,
            'old_manager_score': self.old_manager_score,
            'new_manager_score': self.new_manager_score,
            'old_final_score': self.old_final_score,
            'new_final_score': self.new_final_score,
            'old_status': self.old_status,
            'new_status': self.new_status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat()
        }


class RequiredDepartmentSkill(db.Model, TimestampMixin):
    """Модель обязательных навыков для отдела"""
    __tablename__ = 'required_department_skills'
    
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=False, index=True)
    min_score = db.Column(db.Integer, default=3)  # Минимальная требуемая оценка
    priority = db.Column(db.Integer, default=1)  # Приоритет навыка (1-высокий, 5-низкий)
    is_required = db.Column(db.Boolean, default=True)
    
    # Связи
    department = db.relationship('Department', back_populates='required_skills')
    skill = db.relationship('Skill', back_populates='required_in_departments')
    
    # Ограничения
    __table_args__ = (
        db.UniqueConstraint('department_id', 'skill_id', name='unique_department_skill'),
        db.CheckConstraint('min_score >= 1 AND min_score <= 5', name='check_min_score'),
        db.CheckConstraint('priority >= 1 AND priority <= 5', name='check_priority'),
    )
    
    def __repr__(self):
        return f'<RequiredDepartmentSkill dept:{self.department_id} skill:{self.skill_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'department_id': self.department_id,
            'skill_id': self.skill_id,
            'skill_name': self.skill.name if self.skill else None,
            'min_score': self.min_score,
            'priority': self.priority,
            'is_required': self.is_required,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


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
    data = db.Column(JSONB)  # Дополнительные данные в JSON
    is_read = db.Column(db.Boolean, default=False, index=True)
    read_at = db.Column(db.DateTime)
    
    # Внешние ключи
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # Кто отправил уведомление
    rating_id = db.Column(db.Integer, db.ForeignKey('user_skill_ratings.id'))
    
    # Связи
    user = db.relationship('User', back_populates='notifications', foreign_keys=[user_id])
    sender = db.relationship('User', foreign_keys=[sender_id])
    rating = db.relationship('UserSkillRating')
    
    def __repr__(self):
        return f'<Notification {self.type} for user:{self.user_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'uuid': str(self.uuid),
            'type': self.type,
            'title': self.title,
            'message': self.message,
            'data': self.data,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'user_id': self.user_id,
            'sender_id': self.sender_id,
            'sender_name': self.sender.full_name if self.sender else None,
            'rating_id': self.rating_id,
            'created_at': self.created_at.isoformat()
        }


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
    parameters = db.Column(JSONB)  # Параметры отчета
    file_url = db.Column(db.String(500))  # URL к файлу отчета
    file_format = db.Column(db.Enum('csv', 'excel', 'pdf', 'json', name='file_format'))
    status = db.Column(db.Enum('pending', 'processing', 'completed', 'failed', 
                              name='report_status'), default='pending')
    generated_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)  # Время жизни отчета
    
    # Внешние ключи
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    
    # Связи
    creator = db.relationship('User', foreign_keys=[created_by])
    department = db.relationship('Department')
    
    def __repr__(self):
        return f'<Report {self.name} ({self.type})>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'uuid': str(self.uuid),
            'type': self.type,
            'name': self.name,
            'description': self.description,
            'parameters': self.parameters,
            'file_url': self.file_url,
            'file_format': self.file_format,
            'status': self.status,
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_by': self.created_by,
            'creator_name': self.creator.full_name if self.creator else None,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


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
    
    # Внешние ключи
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Связи
    user = db.relationship('User')
    
    def __repr__(self):
        return f'<AuditLog {self.action} by user:{self.user_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'action': self.action,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'old_values': self.old_values,
            'new_values': self.new_values,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else None,
            'created_at': self.created_at.isoformat()
        }