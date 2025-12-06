from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_, and_, func, desc, asc
import json

from ..models import db, User, Department, Skill, UserSkillRating, RatingHistory, Notification
from ..schemas import RatingUpdateSchema, EmployeeFilterSchema, ComparisonRequestSchema
from ..services.rating_service import RatingService
from ..services.user_service import UserService
from ..utils.notifications import send_notification

manager_bp = Blueprint('manager', __name__)
rating_service = RatingService()
user_service = UserService()

rating_update_schema = RatingUpdateSchema()
employee_filter_schema = EmployeeFilterSchema()
comparison_request_schema = ComparisonRequestSchema()


@manager_bp.route('/employees', methods=['GET'])
@jwt_required()
def get_employees():
    """Получение списка сотрудников отдела"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role not in ['manager', 'admin']:
            return jsonify({'error': 'Access denied'}), 403
        
        # Параметры запроса
        search = request.args.get('search', '').strip()
        department_id = request.args.get('department_id', type=int)
        role = request.args.get('role')
        limit = request.args.get('limit', 20, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Определение отдела для менеджера
        if current_user.role == 'manager':
            if current_user.department_id:
                department_id = current_user.department_id
            else:
                return jsonify({'error': 'Manager has no department assigned'}), 400
        
        # Построение запроса
        query = User.query.filter_by(is_active=True)
        
        if department_id:
            query = query.filter_by(department_id=department_id)
        
        if role:
            query = query.filter_by(role=role)
        else:
            query = query.filter(User.role.in_(['employee', 'manager']))
        
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
        
        total = query.count()
        employees = query.order_by(User.last_name, User.first_name) \
                        .offset(offset).limit(limit).all()
        
        return jsonify({
            'employees': [e.to_dict() for e in employees],
            'total': total,
            'limit': limit,
            'offset': offset
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get employees', 'message': str(e)}), 500


@manager_bp.route('/employees/<int:employee_id>', methods=['GET'])
@jwt_required()
def get_employee(employee_id):
    """Получение профиля сотрудника"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        # Проверка прав доступа
        if not user_service.can_view_employee(current_user, employee_id):
            return jsonify({'error': 'Access denied'}), 403
        
        employee = User.query.get(employee_id)
        if not employee:
            return jsonify({'error': 'Employee not found'}), 404
        
        # Получение профиля с оценками
        profile = rating_service.get_user_profile(employee_id)
        
        return jsonify({
            'employee': employee.to_dict(),
            'profile': profile
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get employee profile', 'message': str(e)}), 500


@manager_bp.route('/employees/<int:employee_id>/ratings', methods=['GET'])
@jwt_required()
def get_employee_ratings(employee_id):
    """Получение оценок сотрудника"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        # Проверка прав доступа
        if not user_service.can_view_employee(current_user, employee_id):
            return jsonify({'error': 'Access denied'}), 403
        
        ratings = rating_service.get_user_ratings(employee_id)
        
        return jsonify({
            'ratings': ratings
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get employee ratings', 'message': str(e)}), 500


@manager_bp.route('/employees/<int:employee_id>/ratings/<int:rating_id>', methods=['PUT'])
@jwt_required()
def update_employee_rating(employee_id, rating_id):
    """Корректировка оценки сотрудника"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        # Проверка прав доступа
        if not user_service.can_manage_employee(current_user, employee_id):
            return jsonify({'error': 'Access denied'}), 403
        
        # Получение оценки
        rating = UserSkillRating.query.get(rating_id)
        if not rating or rating.user_id != employee_id:
            return jsonify({'error': 'Rating not found'}), 404
        
        # Валидация данных
        data = request.get_json()
        errors = rating_update_schema.validate(data)
        if errors:
            return jsonify({'error': 'Validation error', 'details': errors}), 400
        
        # Сохранение старых значений для истории
        old_values = {
            'manager_score': rating.manager_score,
            'manager_notes': rating.manager_notes,
            'status': rating.status
        }
        
        # Обновление оценки
        if 'manager_score' in data:
            rating.manager_score = data['manager_score']
            rating.manager_assessment_date = datetime.utcnow()
        
        if 'manager_notes' in data:
            rating.manager_notes = data['manager_notes']
        
        if 'status' in data:
            rating.status = data['status']
            if data['status'] == 'confirmed':
                rating.final_score = rating.manager_score or rating.self_score
                rating.confirmed_by = current_user_id
            elif data['status'] == 'rejected':
                rating.final_score = None
        
        # Запись в историю
        history_entry = RatingHistory(
            rating_id=rating.id,
            user_id=employee_id,
            changed_by_id=current_user_id,
            action='adjusted',
            old_manager_score=old_values['manager_score'],
            new_manager_score=rating.manager_score,
            old_status=old_values['status'],
            new_status=rating.status,
            notes=data.get('manager_notes', '')
        )
        db.session.add(history_entry)
        
        # Отправка уведомления сотруднику
        employee = User.query.get(employee_id)
        skill = Skill.query.get(rating.skill_id)
        
        notification = Notification(
            user_id=employee_id,
            type='rating_adjusted',
            title='Оценка скорректирована',
            message=f'{current_user.full_name} скорректировал вашу оценку навыка "{skill.name}"',
            data={
                'rating_id': rating.id,
                'skill_id': skill.id,
                'skill_name': skill.name,
                'old_score': old_values['manager_score'],
                'new_score': rating.manager_score,
                'manager_id': current_user_id,
                'manager_name': current_user.full_name
            },
            sender_id=current_user_id
        )
        db.session.add(notification)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Rating updated successfully',
            'rating': rating.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update rating', 'message': str(e)}), 500


@manager_bp.route('/employees/<int:employee_id>/ratings/<int:rating_id>/confirm', methods=['POST'])
@jwt_required()
def confirm_rating(employee_id, rating_id):
    """Подтверждение оценки сотрудника"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        # Проверка прав доступа
        if not user_service.can_manage_employee(current_user, employee_id):
            return jsonify({'error': 'Access denied'}), 403
        
        rating = UserSkillRating.query.get(rating_id)
        if not rating or rating.user_id != employee_id:
            return jsonify({'error': 'Rating not found'}), 404
        
        # Сохранение старых значений
        old_status = rating.status
        
        # Подтверждение оценки
        rating.status = 'confirmed'
        rating.final_score = rating.manager_score or rating.self_score
        rating.confirmed_by = current_user_id
        
        # Запись в историю
        history_entry = RatingHistory(
            rating_id=rating.id,
            user_id=employee_id,
            changed_by_id=current_user_id,
            action='confirmed',
            old_status=old_status,
            new_status='confirmed',
            notes='Оценка подтверждена руководителем'
        )
        db.session.add(history_entry)
        
        # Отправка уведомления
        employee = User.query.get(employee_id)
        skill = Skill.query.get(rating.skill_id)
        
        notification = Notification(
            user_id=employee_id,
            type='rating_confirmed',
            title='Оценка подтверждена',
            message=f'{current_user.full_name} подтвердил вашу оценку навыка "{skill.name}"',
            data={
                'rating_id': rating.id,
                'skill_id': skill.id,
                'skill_name': skill.name,
                'score': rating.final_score,
                'manager_id': current_user_id,
                'manager_name': current_user.full_name
            },
            sender_id=current_user_id
        )
        db.session.add(notification)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Rating confirmed successfully',
            'rating': rating.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to confirm rating', 'message': str(e)}), 500


@manager_bp.route('/employees/search-by-skills', methods=['POST'])
@jwt_required()
def search_employees_by_skills():
    """Поиск сотрудников по навыкам"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role not in ['manager', 'admin']:
            return jsonify({'error': 'Access denied'}), 403
        
        # Валидация данных
        data = request.get_json()
        errors = employee_filter_schema.validate(data)
        if errors:
            return jsonify({'error': 'Validation error', 'details': errors}), 400
        
        # Поиск сотрудников
        employees = rating_service.search_employees_by_skills(
            filters=data['skills'],
            department_id=current_user.department_id if current_user.role == 'manager' else None
        )
        
        return jsonify({
            'employees': employees
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Search failed', 'message': str(e)}), 500


@manager_bp.route('/compare', methods=['POST'])
@jwt_required()
def compare_employees():
    """Сравнение нескольких сотрудников"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role not in ['manager', 'admin']:
            return jsonify({'error': 'Access denied'}), 403
        
        # Валидация данных
        data = request.get_json()
        errors = comparison_request_schema.validate(data)
        if errors:
            return jsonify({'error': 'Validation error', 'details': errors}), 400
        
        # Проверка прав доступа к сотрудникам
        if current_user.role == 'manager':
            for employee_id in data['employee_ids']:
                if not user_service.can_view_employee(current_user, employee_id):
                    return jsonify({'error': f'Access denied to employee {employee_id}'}), 403
        
        # Сравнение сотрудников
        comparison = rating_service.compare_employees(
            employee_ids=data['employee_ids'],
            show_differences=data.get('show_differences', False),
            category_id=data.get('category_id')
        )
        
        return jsonify({
            'comparison': comparison
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Comparison failed', 'message': str(e)}), 500


@manager_bp.route('/notifications', methods=['GET'])
@jwt_required()
def get_manager_notifications():
    """Получение уведомлений для менеджера"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role not in ['manager', 'admin']:
            return jsonify({'error': 'Access denied'}), 403
        
        # Получение уведомлений о новых оценках подчиненных
        notifications = Notification.query.filter(
            Notification.user_id == current_user_id,
            Notification.type.in_(['new_assessment', 'rating_adjusted', 'rating_confirmed'])
        ).order_by(Notification.created_at.desc()).limit(50).all()
        
        return jsonify({
            'notifications': [n.to_dict() for n in notifications]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get notifications', 'message': str(e)}), 500


@manager_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_manager_dashboard():
    """Получение дашборда менеджера"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role not in ['manager', 'admin']:
            return jsonify({'error': 'Access denied'}), 403
        
        dashboard_data = rating_service.get_manager_dashboard(current_user_id)
        
        return jsonify({
            'dashboard': dashboard_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get dashboard', 'message': str(e)}), 500


@manager_bp.route('/pending-approvals', methods=['GET'])
@jwt_required()
def get_pending_approvals():
    """Получение оценок, требующих подтверждения"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role not in ['manager', 'admin']:
            return jsonify({'error': 'Access denied'}), 403
        
        # Определение подчиненных
        if current_user.role == 'manager':
            subordinate_ids = [u.id for u in user_service.get_subordinates(current_user_id)]
            if not subordinate_ids:
                return jsonify({'pending_approvals': []}), 200
            
            pending_ratings = UserSkillRating.query.filter(
                UserSkillRating.user_id.in_(subordinate_ids),
                UserSkillRating.status == 'pending'
            ).order_by(UserSkillRating.updated_at.desc()).all()
        else:
            # Администратор видит все ожидающие оценки
            pending_ratings = UserSkillRating.query.filter_by(status='pending') \
                .order_by(UserSkillRating.updated_at.desc()).all()
        
        return jsonify({
            'pending_approvals': [r.to_dict() for r in pending_ratings]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get pending approvals', 'message': str(e)}), 500


@manager_bp.route('/department-stats', methods=['GET'])
@jwt_required()
def get_department_stats():
    """Получение статистики по отделу"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if current_user.role not in ['manager', 'admin']:
            return jsonify({'error': 'Access denied'}), 403
        
        department_id = request.args.get('department_id', current_user.department_id, type=int)
        
        if not department_id:
            return jsonify({'error': 'Department ID is required'}), 400
        
        # Проверка прав доступа к отделу
        if current_user.role == 'manager' and department_id != current_user.department_id:
            return jsonify({'error': 'Access denied to this department'}), 403
        
        stats = rating_service.get_department_stats(department_id)
        
        return jsonify({
            'stats': stats
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get department stats', 'message': str(e)}), 500