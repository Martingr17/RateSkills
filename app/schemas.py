"""
Схемы для валидации данных
"""

from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from .models import db, User, Department, Skill, UserSkillRating
from datetime import datetime


# Простые функции валидации
def validate_email(email):
    if not email:
        return False
    return '@' in email and '.' in email.split('@')[1]

def validate_phone(phone):
    if not phone:
        return True
    phone_str = str(phone)
    digits = ''.join(filter(str.isdigit, phone_str))
    return len(digits) >= 10


class LoginSchema(Schema):
    """Схема для входа в систему"""
    username = fields.String(required=True, validate=validate.Length(min=3, max=64))
    password = fields.String(required=True, validate=validate.Length(min=6))


class UserCreateSchema(Schema):
    """Схема для создания пользователя"""
    username = fields.String(required=True, validate=[
        validate.Length(min=3, max=64),
        validate.Regexp(r'^[a-zA-Z0-9_.-]+$', error='Username can only contain letters, numbers, dots, underscores and hyphens')
    ])
    email = fields.Email(required=True, validate=[validate.Length(max=120)])
    password = fields.String(required=True, validate=validate.Length(min=6))
    confirm_password = fields.String(required=True)
    first_name = fields.String(required=True, validate=validate.Length(min=2, max=64))
    last_name = fields.String(required=True, validate=validate.Length(min=2, max=64))
    patronymic = fields.String(validate=validate.Length(max=64))
    position = fields.String(validate=validate.Length(max=100))
    role = fields.String(validate=validate.OneOf(['employee', 'manager', 'admin']))
    department_id = fields.Integer()
    manager_id = fields.Integer()
    phone = fields.String(validate=[validate.Length(max=20)])

    @validates_schema
    def validate_passwords(self, data, **kwargs):
        """Проверка совпадения паролей"""
        if data.get('password') != data.get('confirm_password'):
            raise ValidationError('Passwords do not match', 'confirm_password')


class UserUpdateSchema(Schema):
    """Схема для обновления пользователя"""
    email = fields.Email(validate=[validate.Length(max=120)])
    first_name = fields.String(validate=validate.Length(min=2, max=64))
    last_name = fields.String(validate=validate.Length(min=2, max=64))
    patronymic = fields.String(validate=validate.Length(max=64))
    position = fields.String(validate=validate.Length(max=100))
    role = fields.String(validate=validate.OneOf(['employee', 'manager', 'admin']))
    department_id = fields.Integer()
    manager_id = fields.Integer()
    phone = fields.String(validate=[validate.Length(max=20)])
    is_active = fields.Boolean()
    avatar_url = fields.Url()


class SkillCreateSchema(Schema):
    """Схема для создания навыка"""
    name = fields.String(required=True, validate=validate.Length(min=2, max=100))
    description = fields.String(validate=validate.Length(max=1000))
    category_id = fields.Integer(required=True)
    difficulty_level = fields.String(
        validate=validate.OneOf(['beginner', 'intermediate', 'advanced', 'expert'])
    )
    is_active = fields.Boolean()


class SkillUpdateSchema(Schema):
    """Схема для обновления навыка"""
    name = fields.String(validate=validate.Length(min=2, max=100))
    description = fields.String(validate=validate.Length(max=1000))
    category_id = fields.Integer()
    difficulty_level = fields.String(
        validate=validate.OneOf(['beginner', 'intermediate', 'advanced', 'expert'])
    )
    is_active = fields.Boolean()


class SkillCategoryCreateSchema(Schema):
    """Схема для создания категории навыков"""
    name = fields.String(required=True, validate=validate.Length(min=2, max=100))
    description = fields.String(validate=validate.Length(max=500))
    icon = fields.String(validate=validate.Length(max=50))
    color = fields.String(validate=validate.Regexp(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'))


class RatingCreateSchema(Schema):
    """Схема для создания оценки навыка"""
    skill_id = fields.Integer(required=True)
    self_score = fields.Integer(required=True, validate=validate.Range(min=1, max=5))
    notes = fields.String(validate=validate.Length(max=1000))

    @validates_schema
    def validate_score(self, data, **kwargs):
        """Валидация оценки"""
        if data.get('self_score') not in [1, 2, 3, 4, 5]:
            raise ValidationError('Score must be between 1 and 5')


class RatingUpdateSchema(Schema):
    """Схема для обновления оценки"""
    self_score = fields.Integer(validate=validate.Range(min=1, max=5))
    manager_score = fields.Integer(validate=validate.Range(min=1, max=5))
    notes = fields.String(validate=validate.Length(max=1000))
    manager_notes = fields.String(validate=validate.Length(max=1000))
    status = fields.String(validate=validate.OneOf(['pending', 'confirmed', 'rejected', 'adjusted']))


class BulkRatingUpdateSchema(Schema):
    """Схема для массового обновления оценок"""
    ratings = fields.List(
        fields.Nested(RatingCreateSchema),
        required=True,
        validate=validate.Length(min=1, max=100)
    )


class DepartmentCreateSchema(Schema):
    """Схема для создания отдела"""
    name = fields.String(required=True, validate=validate.Length(min=2, max=100))
    description = fields.String(validate=validate.Length(max=500))
    code = fields.String(required=True, validate=[
        validate.Length(min=2, max=20),
        validate.Regexp(r'^[A-Z0-9_-]+$', error='Code can only contain uppercase letters, numbers, underscores and hyphens')
    ])
    manager_id = fields.Integer()


class RequiredSkillCreateSchema(Schema):
    """Схема для создания обязательного навыка"""
    department_id = fields.Integer(required=True)
    skill_id = fields.Integer(required=True)
    min_score = fields.Integer(validate=validate.Range(min=1, max=5))
    priority = fields.Integer(validate=validate.Range(min=1, max=5))
    is_required = fields.Boolean()


class EmployeeFilterSchema(Schema):
    """Схема для фильтрации сотрудников по навыкам"""
    skills = fields.List(
        fields.Dict(keys=fields.String(), values=fields.Raw()),
        required=True,
        validate=validate.Length(min=1, max=10)
    )

    @validates_schema
    def validate_skills(self, data, **kwargs):
        """Валидация фильтра навыков"""
        for skill_filter in data.get('skills', []):
            if 'skill_id' not in skill_filter:
                raise ValidationError('Each skill filter must have skill_id')
            if 'operator' not in skill_filter:
                raise ValidationError('Each skill filter must have operator')
            if 'value' not in skill_filter:
                raise ValidationError('Each skill filter must have value')

            operator = skill_filter.get('operator')
            if operator not in ['=', '>', '<', '>=', '<=', '!=']:
                raise ValidationError(f'Invalid operator: {operator}')

            value = skill_filter.get('value')
            if not isinstance(value, (int, float)) or value < 1 or value > 5:
                raise ValidationError('Value must be a number between 1 and 5')


class ComparisonRequestSchema(Schema):
    """Схема для сравнения сотрудников"""
    employee_ids = fields.List(
        fields.Integer(),
        required=True,
        validate=validate.Length(min=2, max=10)
    )
    show_differences = fields.Boolean()
    category_id = fields.Integer()


class ReportRequestSchema(Schema):
    """Схема для создания отчета"""
    type = fields.String(required=True, validate=validate.OneOf([
        'department_summary', 'employee_skills', 'skill_gap', 'trend_analysis'
    ]))
    department_id = fields.Integer()
    start_date = fields.Date()
    end_date = fields.Date()
    skill_ids = fields.List(fields.Integer())
    file_format = fields.String(validate=validate.OneOf(['csv', 'excel', 'pdf']))


class NotificationSchema(Schema):
    """Схема для уведомлений"""
    type = fields.String(required=True)
    title = fields.String(required=True, validate=validate.Length(max=200))
    message = fields.String(required=True)
    data = fields.Dict()
    user_id = fields.Integer(required=True)


# Простые схемы для моделей (без SQLAlchemyAutoSchema)
class UserSchema(Schema):
    class Meta:
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'patronymic',
                 'full_name', 'position', 'role', 'department_id', 'manager_id',
                 'is_active', 'phone', 'created_at', 'updated_at')

    full_name = fields.String(dump_only=True)


class SkillSchema(Schema):
    class Meta:
        fields = ('id', 'name', 'description', 'category_id', 'is_active',
                 'difficulty_level', 'created_at', 'updated_at')


class SkillCategorySchema(Schema):
    class Meta:
        fields = ('id', 'name', 'description', 'icon', 'color', 'created_at', 'updated_at')


class UserSkillRatingSchema(Schema):
    class Meta:
        fields = ('id', 'user_id', 'skill_id', 'self_score', 'manager_score',
                 'final_score', 'status', 'notes', 'manager_notes',
                 'self_assessment_date', 'manager_assessment_date', 'created_at', 'updated_at')

    effective_score = fields.Integer(dump_only=True)


class DepartmentSchema(Schema):
    class Meta:
        fields = ('id', 'name', 'description', 'code', 'manager_id',
                 'created_at', 'updated_at')


class NotificationSchema(Schema):
    class Meta:
        fields = ('id', 'type', 'title', 'message', 'data', 'is_read',
                 'user_id', 'sender_id', 'rating_id', 'created_at')


class ReportSchema(Schema):
    class Meta:
        fields = ('id', 'type', 'name', 'description', 'parameters', 'file_url',
                 'file_format', 'status', 'created_by', 'department_id',
                 'created_at', 'updated_at')
