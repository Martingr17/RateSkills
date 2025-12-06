from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
import pandas as pd
import json
from io import BytesIO
from datetime import datetime, timedelta

from ..models import db, User, Department, Skill, SkillCategory, UserSkillRating, Report, AuditLog
from ..schemas import (
    UserCreateSchema, UserUpdateSchema, SkillCreateSchema, SkillUpdateSchema,
    SkillCategoryCreateSchema, DepartmentCreateSchema, RequiredSkillCreateSchema,
    ReportRequestSchema
)
from ..services.user_service import UserService
from ..services.skill_service import SkillService
from ..services.rating_service import RatingService
from ..services.report_service import ReportService
from ..utils.csv_export import export_to_csv, export_to_excel
from ..utils.auth_utils import generate_password

admin_bp = Blueprint('admin', __name__)
user_service = UserService()
skill_service = SkillService()
rating_service = RatingService()
report_service = ReportService()

user_create_schema = UserCreateSchema()
user_update_schema = UserUpdateSchema()
skill_create_schema = SkillCreateSchema()
skill_update_schema = SkillUpdateSchema()
skill_category_create_schema = SkillCategoryCreateSchema()
department_create_schema = DepartmentCreateSchema()
required_skill_create_schema = RequiredSkillCreateSchema()
report_request_schema = ReportRequestSchema()


@admin_bp.route('/users', methods=['GET'])
@jwt_required()
def get_users():
    """Получение списка всех пользователей"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        # Параметры запроса
        search = request.args.get('search', '').strip()
        role = request.args.get('role')
        department_id = request.args.get('department_id', type=int)
        is_active = request.args.get('is_active', type=lambda v: v.lower() == 'true')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Построение запроса
        query = User.query
        
        if search:
            search_term = f'%{search}%'
            query = query.filter(
                or_(
                    User.username.ilike(search_term),
                    User.email.ilike(search_term),
                    User.first_name.ilike(search_term),
                    User.last_name.ilike(search_term),
                    User.full_name.ilike(search_term)
                )
            )
        
        if role:
            query = query.filter_by(role=role)
        
        if department_id:
            query = query.filter_by(department_id=department_id)
        
        if is_active is not None:
            query = query.filter_by(is_active=is_active)
        
        total = query.count()
        users = query.order_by(User.last_name, User.first_name) \
                    .offset(offset).limit(limit).all()
        
        return jsonify({
            'users': [u.to_dict() for u in users],
            'total': total,
            'limit': limit,
            'offset': offset
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get users', 'message': str(e)}), 500


@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    """Получение информации о пользователе"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'user': user.to_dict(include_ratings=True)
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get user', 'message': str(e)}), 500


@admin_bp.route('/users', methods=['POST'])
@jwt_required()
def create_user():
    """Создание нового пользователя"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        # Валидация данных
        data = request.get_json()
        errors = user_create_schema.validate(data)
        if errors:
            return jsonify({'error': 'Validation error', 'details': errors}), 400
        
        # Генерация пароля, если не указан
        if not data.get('password'):
            password = generate_password()
            data['password'] = password
            data['confirm_password'] = password
        
        # Создание пользователя
        user = user_service.create_user(**data)
        
        # Логирование
        audit_log = AuditLog(
            user_id=current_user_id,
            action='admin_user_created',
            entity_type='user',
            entity_id=user.id,
            new_values={
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'department_id': user.department_id
            },
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'message': 'User created successfully',
            'user': user.to_dict(),
            'generated_password': data['password'] if 'generated_password' in locals() else None
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create user', 'message': str(e)}), 500


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    """Обновление пользователя"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Валидация данных
        data = request.get_json()
        errors = user_update_schema.validate(data)
        if errors:
            return jsonify({'error': 'Validation error', 'details': errors}), 400
        
        # Сохранение старых значений
        old_values = {
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'department_id': user.department_id,
            'is_active': user.is_active
        }
        
        # Обновление пользователя
        updated_user = user_service.update_user(user_id, **data)
        
        # Логирование
        new_values = {}
        for key in old_values:
            if key in data and data[key] != old_values[key]:
                new_values[key] = data[key]
        
        if new_values:
            audit_log = AuditLog(
                user_id=current_user_id,
                action='admin_user_updated',
                entity_type='user',
                entity_id=user_id,
                old_values=old_values,
                new_values=new_values,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'message': 'User updated successfully',
            'user': updated_user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update user', 'message': str(e)}), 500


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    """Удаление пользователя"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        if current_user_id == user_id:
            return jsonify({'error': 'Cannot delete yourself'}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Логирование перед удалением
        audit_log = AuditLog(
            user_id=current_user_id,
            action='admin_user_deleted',
            entity_type='user',
            entity_id=user_id,
            old_values={
                'username': user.username,
                'email': user.email,
                'role': user.role
            },
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        
        # Удаление пользователя
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({
            'message': 'User deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete user', 'message': str(e)}), 500


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@jwt_required()
def reset_user_password(user_id):
    """Сброс пароля пользователя"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Генерация нового пароля
        new_password = generate_password()
        user.password_hash = hash_password(new_password)
        
        # Логирование
        audit_log = AuditLog(
            user_id=current_user_id,
            action='admin_password_reset',
            entity_type='user',
            entity_id=user_id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Password reset successfully',
            'new_password': new_password
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to reset password', 'message': str(e)}), 500


@admin_bp.route('/skills/categories', methods=['GET'])
@jwt_required()
def get_skill_categories():
    """Получение списка категорий навыков"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        categories = skill_service.get_all_categories()
        
        return jsonify({
            'categories': categories
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get categories', 'message': str(e)}), 500


@admin_bp.route('/skills/categories', methods=['POST'])
@jwt_required()
def create_skill_category():
    """Создание категории навыков"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        # Валидация данных
        data = request.get_json()
        errors = skill_category_create_schema.validate(data)
        if errors:
            return jsonify({'error': 'Validation error', 'details': errors}), 400
        
        # Проверка уникальности
        if SkillCategory.query.filter_by(name=data['name']).first():
            return jsonify({'error': 'Category with this name already exists'}), 409
        
        # Создание категории
        category = skill_service.create_category(**data)
        
        # Логирование
        audit_log = AuditLog(
            user_id=current_user_id,
            action='skill_category_created',
            entity_type='skill_category',
            entity_id=category.id,
            new_values={'name': category.name, 'icon': category.icon},
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'message': 'Category created successfully',
            'category': category.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create category', 'message': str(e)}), 500


@admin_bp.route('/skills/categories/<int:category_id>', methods=['PUT'])
@jwt_required()
def update_skill_category(category_id):
    """Обновление категории навыков"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        category = SkillCategory.query.get(category_id)
        if not category:
            return jsonify({'error': 'Category not found'}), 404
        
        # Валидация данных
        data = request.get_json()
        errors = skill_category_create_schema.validate(data, partial=True)
        if errors:
            return jsonify({'error': 'Validation error', 'details': errors}), 400
        
        # Проверка уникальности имени
        if 'name' in data and data['name'] != category.name:
            if SkillCategory.query.filter_by(name=data['name']).first():
                return jsonify({'error': 'Category with this name already exists'}), 409
        
        # Сохранение старых значений
        old_values = {
            'name': category.name,
            'description': category.description,
            'icon': category.icon,
            'color': category.color
        }
        
        # Обновление категории
        updated_category = skill_service.update_category(category_id, **data)
        
        # Логирование
        new_values = {}
        for key in old_values:
            if key in data and data[key] != old_values[key]:
                new_values[key] = data[key]
        
        if new_values:
            audit_log = AuditLog(
                user_id=current_user_id,
                action='skill_category_updated',
                entity_type='skill_category',
                entity_id=category_id,
                old_values=old_values,
                new_values=new_values,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Category updated successfully',
            'category': updated_category.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update category', 'message': str(e)}), 500


@admin_bp.route('/skills/categories/<int:category_id>', methods=['DELETE'])
@jwt_required()
def delete_skill_category(category_id):
    """Удаление категории навыков"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        category = SkillCategory.query.get(category_id)
        if not category:
            return jsonify({'error': 'Category not found'}), 404
        
        # Проверка наличия навыков в категории
        skill_count = category.skills.count()
        if skill_count > 0:
            return jsonify({
                'error': 'Cannot delete category with skills',
                'skill_count': skill_count,
                'skills': [s.name for s in category.skills.limit(10)]
            }), 400
        
        # Логирование
        audit_log = AuditLog(
            user_id=current_user_id,
            action='skill_category_deleted',
            entity_type='skill_category',
            entity_id=category_id,
            old_values={'name': category.name},
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        
        # Удаление категории
        db.session.delete(category)
        db.session.commit()
        
        return jsonify({
            'message': 'Category deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete category', 'message': str(e)}), 500


@admin_bp.route('/skills', methods=['POST'])
@jwt_required()
def create_skill():
    """Создание навыка"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        # Валидация данных
        data = request.get_json()
        errors = skill_create_schema.validate(data)
        if errors:
            return jsonify({'error': 'Validation error', 'details': errors}), 400
        
        # Проверка существования категории
        category = SkillCategory.query.get(data['category_id'])
        if not category:
            return jsonify({'error': 'Category not found'}), 404
        
        # Проверка уникальности имени
        if Skill.query.filter_by(name=data['name']).first():
            return jsonify({'error': 'Skill with this name already exists'}), 409
        
        # Создание навыка
        skill = skill_service.create_skill(**data)
        
        # Логирование
        audit_log = AuditLog(
            user_id=current_user_id,
            action='skill_created',
            entity_type='skill',
            entity_id=skill.id,
            new_values={
                'name': skill.name,
                'category_id': skill.category_id,
                'difficulty_level': skill.difficulty_level
            },
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'message': 'Skill created successfully',
            'skill': skill.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create skill', 'message': str(e)}), 500


@admin_bp.route('/skills/<int:skill_id>', methods=['PUT'])
@jwt_required()
def update_skill(skill_id):
    """Обновление навыка"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        skill = Skill.query.get(skill_id)
        if not skill:
            return jsonify({'error': 'Skill not found'}), 404
        
        # Валидация данных
        data = request.get_json()
        errors = skill_update_schema.validate(data, partial=True)
        if errors:
            return jsonify({'error': 'Validation error', 'details': errors}), 400
        
        # Проверка уникальности имени
        if 'name' in data and data['name'] != skill.name:
            if Skill.query.filter_by(name=data['name']).first():
                return jsonify({'error': 'Skill with this name already exists'}), 409
        
        # Проверка существования категории
        if 'category_id' in data:
            category = SkillCategory.query.get(data['category_id'])
            if not category:
                return jsonify({'error': 'Category not found'}), 404
        
        # Сохранение старых значений
        old_values = {
            'name': skill.name,
            'description': skill.description,
            'category_id': skill.category_id,
            'difficulty_level': skill.difficulty_level,
            'is_active': skill.is_active
        }
        
        # Обновление навыка
        updated_skill = skill_service.update_skill(skill_id, **data)
        
        # Логирование
        new_values = {}
        for key in old_values:
            if key in data and data[key] != old_values[key]:
                new_values[key] = data[key]
        
        if new_values:
            audit_log = AuditLog(
                user_id=current_user_id,
                action='skill_updated',
                entity_type='skill',
                entity_id=skill_id,
                old_values=old_values,
                new_values=new_values,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Skill updated successfully',
            'skill': updated_skill.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update skill', 'message': str(e)}), 500


@admin_bp.route('/skills/<int:skill_id>', methods=['DELETE'])
@jwt_required()
def delete_skill(skill_id):
    """Удаление навыка"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        skill = Skill.query.get(skill_id)
        if not skill:
            return jsonify({'error': 'Skill not found'}), 404
        
        # Проверка наличия оценок
        rating_count = skill.ratings.count()
        if rating_count > 0:
            return jsonify({
                'error': 'Cannot delete skill with ratings',
                'rating_count': rating_count
            }), 400
        
        # Логирование
        audit_log = AuditLog(
            user_id=current_user_id,
            action='skill_deleted',
            entity_type='skill',
            entity_id=skill_id,
            old_values={'name': skill.name},
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        
        # Удаление навыка
        db.session.delete(skill)
        db.session.commit()
        
        return jsonify({
            'message': 'Skill deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete skill', 'message': str(e)}), 500


@admin_bp.route('/departments', methods=['GET'])
@jwt_required()
def get_departments():
    """Получение списка отделов"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        departments = Department.query.all()
        
        return jsonify({
            'departments': [d.to_dict() for d in departments]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get departments', 'message': str(e)}), 500


@admin_bp.route('/departments', methods=['POST'])
@jwt_required()
def create_department():
    """Создание отдела"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        # Валидация данных
        data = request.get_json()
        errors = department_create_schema.validate(data)
        if errors:
            return jsonify({'error': 'Validation error', 'details': errors}), 400
        
        # Проверка уникальности
        if Department.query.filter_by(name=data['name']).first():
            return jsonify({'error': 'Department with this name already exists'}), 409
        
        if Department.query.filter_by(code=data['code']).first():
            return jsonify({'error': 'Department with this code already exists'}), 409
        
        # Проверка менеджера
        if 'manager_id' in data:
            manager = User.query.get(data['manager_id'])
            if not manager or manager.role != 'manager':
                return jsonify({'error': 'Manager not found or not a manager'}), 404
        
        # Создание отдела
        department = Department(
            name=data['name'],
            description=data.get('description'),
            code=data['code'],
            manager_id=data.get('manager_id')
        )
        db.session.add(department)
        
        # Логирование
        audit_log = AuditLog(
            user_id=current_user_id,
            action='department_created',
            entity_type='department',
            entity_id=department.id,
            new_values={'name': department.name, 'code': department.code},
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Department created successfully',
            'department': department.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create department', 'message': str(e)}), 500


@admin_bp.route('/departments/<int:department_id>/required-skills', methods=['POST'])
@jwt_required()
def add_required_skill(department_id):
    """Добавление обязательного навыка для отдела"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        # Проверка существования отдела
        department = Department.query.get(department_id)
        if not department:
            return jsonify({'error': 'Department not found'}), 404
        
        # Валидация данных
        data = request.get_json()
        errors = required_skill_create_schema.validate(data)
        if errors:
            return jsonify({'error': 'Validation error', 'details': errors}), 400
        
        # Проверка существования навыка
        skill = Skill.query.get(data['skill_id'])
        if not skill:
            return jsonify({'error': 'Skill not found'}), 404
        
        # Проверка дублирования
        existing = RequiredDepartmentSkill.query.filter_by(
            department_id=department_id,
            skill_id=data['skill_id']
        ).first()
        
        if existing:
            return jsonify({'error': 'Skill already required for this department'}), 409
        
        # Создание обязательного навыка
        required_skill = RequiredDepartmentSkill(
            department_id=department_id,
            skill_id=data['skill_id'],
            min_score=data.get('min_score', 3),
            priority=data.get('priority', 1),
            is_required=data.get('is_required', True)
        )
        db.session.add(required_skill)
        
        # Логирование
        audit_log = AuditLog(
            user_id=current_user_id,
            action='required_skill_added',
            entity_type='required_department_skill',
            entity_id=required_skill.id,
            new_values={
                'department_id': department_id,
                'skill_id': data['skill_id'],
                'min_score': required_skill.min_score
            },
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Required skill added successfully',
            'required_skill': required_skill.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to add required skill', 'message': str(e)}), 500


@admin_bp.route('/export/users', methods=['GET'])
@jwt_required()
def export_users():
    """Экспорт пользователей в CSV"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        # Получение данных
        users = User.query.all()
        
        # Создание CSV
        csv_data = export_to_csv(users, [
            ('ID', 'id'),
            ('Username', 'username'),
            ('Email', 'email'),
            ('Full Name', 'full_name'),
            ('Position', 'position'),
            ('Role', 'role'),
            ('Department', 'department.name'),
            ('Manager', 'manager.full_name'),
            ('Active', 'is_active'),
            ('Created', 'created_at')
        ])
        
        return send_file(
            csv_data,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'users_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
        )
        
    except Exception as e:
        return jsonify({'error': 'Export failed', 'message': str(e)}), 500


@admin_bp.route('/export/skills', methods=['GET'])
@jwt_required()
def export_skills():
    """Экспорт навыков в CSV"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        # Получение данных
        skills = Skill.query.join(SkillCategory).all()
        
        # Создание CSV
        csv_data = export_to_csv(skills, [
            ('ID', 'id'),
            ('Name', 'name'),
            ('Description', 'description'),
            ('Category', 'category.name'),
            ('Difficulty', 'difficulty_level'),
            ('Active', 'is_active'),
            ('Created', 'created_at')
        ])
        
        return send_file(
            csv_data,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'skills_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
        )
        
    except Exception as e:
        return jsonify({'error': 'Export failed', 'message': str(e)}), 500


@admin_bp.route('/export/ratings', methods=['GET'])
@jwt_required()
def export_ratings():
    """Экспорт оценок в CSV"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        # Параметры фильтрации
        department_id = request.args.get('department_id', type=int)
        user_id = request.args.get('user_id', type=int)
        skill_id = request.args.get('skill_id', type=int)
        
        # Построение запроса
        query = UserSkillRating.query \
            .join(User) \
            .join(Skill)
        
        if department_id:
            query = query.filter(User.department_id == department_id)
        
        if user_id:
            query = query.filter(UserSkillRating.user_id == user_id)
        
        if skill_id:
            query = query.filter(UserSkillRating.skill_id == skill_id)
        
        ratings = query.all()
        
        # Создание CSV
        csv_data = export_to_csv(ratings, [
            ('User ID', 'user_id'),
            ('User Name', 'user.full_name'),
            ('Skill ID', 'skill_id'),
            ('Skill Name', 'skill.name'),
            ('Self Score', 'self_score'),
            ('Manager Score', 'manager_score'),
            ('Final Score', 'final_score'),
            ('Status', 'status'),
            ('Confirmed By', 'confirmed_by_user.full_name'),
            ('Self Assessment Date', 'self_assessment_date'),
            ('Manager Assessment Date', 'manager_assessment_date'),
            ('Created', 'created_at'),
            ('Updated', 'updated_at')
        ])
        
        return send_file(
            csv_data,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'ratings_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
        )
        
    except Exception as e:
        return jsonify({'error': 'Export failed', 'message': str(e)}), 500


@admin_bp.route('/reports', methods=['POST'])
@jwt_required()
def create_report():
    """Создание отчета"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        # Валидация данных
        data = request.get_json()
        errors = report_request_schema.validate(data)
        if errors:
            return jsonify({'error': 'Validation error', 'details': errors}), 400
        
        # Создание отчета
        report = report_service.create_report(
            report_type=data['type'],
            created_by=current_user_id,
            parameters=data,
            file_format=data.get('file_format', 'excel')
        )
        
        # Запуск генерации отчета в фоне
        from ..tasks import generate_report_task
        generate_report_task.delay(report.id)
        
        return jsonify({
            'message': 'Report generation started',
            'report': report.to_dict()
        }), 202
        
    except Exception as e:
        return jsonify({'error': 'Failed to create report', 'message': str(e)}), 500


@admin_bp.route('/reports/<uuid:report_uuid>/download', methods=['GET'])
@jwt_required()
def download_report(report_uuid):
    """Скачивание отчета"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        report = Report.query.filter_by(uuid=report_uuid).first()
        if not report:
            return jsonify({'error': 'Report not found'}), 404
        
        if report.status != 'completed' or not report.file_url:
            return jsonify({'error': 'Report not ready for download'}), 400
        
        # Проверка срока действия отчета
        if report.expires_at and report.expires_at < datetime.utcnow():
            return jsonify({'error': 'Report has expired'}), 410
        
        # Возврат файла
        return send_file(
            report.file_url,
            as_attachment=True,
            download_name=f'{report.name}_{datetime.utcnow().strftime("%Y%m%d")}.{report.file_format}'
        )
        
    except Exception as e:
        return jsonify({'error': 'Download failed', 'message': str(e)}), 500


@admin_bp.route('/audit-logs', methods=['GET'])
@jwt_required()
def get_audit_logs():
    """Получение логов аудита"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        # Параметры запроса
        user_id = request.args.get('user_id', type=int)
        action = request.args.get('action')
        entity_type = request.args.get('entity_type')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Построение запроса
        query = AuditLog.query
        
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        if action:
            query = query.filter_by(action=action)
        
        if entity_type:
            query = query.filter_by(entity_type=entity_type)
        
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        total = query.count()
        logs = query.order_by(AuditLog.created_at.desc()) \
                   .offset(offset).limit(limit).all()
        
        return jsonify({
            'logs': [log.to_dict() for log in logs],
            'total': total,
            'limit': limit,
            'offset': offset
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get audit logs', 'message': str(e)}), 500


@admin_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_admin_dashboard():
    """Получение дашборда администратора"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        dashboard_data = {
            'user_stats': {
                'total': User.query.count(),
                'active': User.query.filter_by(is_active=True).count(),
                'employees': User.query.filter_by(role='employee').count(),
                'managers': User.query.filter_by(role='manager').count(),
                'admins': User.query.filter_by(role='admin').count()
            },
            'skill_stats': {
                'total': Skill.query.count(),
                'active': Skill.query.filter_by(is_active=True).count(),
                'categories': SkillCategory.query.count()
            },
            'rating_stats': {
                'total': UserSkillRating.query.count(),
                'pending': UserSkillRating.query.filter_by(status='pending').count(),
                'confirmed': UserSkillRating.query.filter_by(status='confirmed').count(),
                'rejected': UserSkillRating.query.filter_by(status='rejected').count()
            },
            'department_stats': {
                'total': Department.query.count(),
                'with_manager': Department.query.filter(Department.manager_id.isnot(None)).count()
            },
            'recent_activity': [
                log.to_dict() for log in AuditLog.query
                .order_by(AuditLog.created_at.desc())
                .limit(10)
                .all()
            ]
        }
        
        return jsonify({
            'dashboard': dashboard_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get dashboard', 'message': str(e)}), 500
