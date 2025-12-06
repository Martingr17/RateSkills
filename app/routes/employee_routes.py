from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, case, desc, asc
from datetime import datetime, timedelta
import json

from ..models import db, User, Skill, SkillCategory, UserSkillRating, RatingHistory, RequiredDepartmentSkill, Notification
from ..schemas import RatingCreateSchema, BulkRatingUpdateSchema
from ..services.rating_service import RatingService
from ..services.skill_service import SkillService
from ..utils.notifications import send_notification

employee_bp = Blueprint('employee', __name__)
rating_service = RatingService()
skill_service = SkillService()

rating_create_schema = RatingCreateSchema()
bulk_rating_update_schema = BulkRatingUpdateSchema()


@employee_bp.route('/skills', methods=['GET'])
@jwt_required()
def get_skills():
    """Получение списка навыков с категориями"""
    try:
        current_user_id = get_jwt_identity()
        
        # Получение категорий с навыками
        categories = skill_service.get_categories_with_skills(current_user_id)
        
        return jsonify({
            'categories': categories
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get skills', 'message': str(e)}), 500


@employee_bp.route('/skills/<int:category_id>', methods=['GET'])
@jwt_required()
def get_skills_by_category(category_id):
    """Получение навыков по категории"""
    try:
        current_user_id = get_jwt_identity()
        
        skills = skill_service.get_skills_by_category(category_id, current_user_id)
        
        return jsonify({
            'skills': skills
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get skills', 'message': str(e)}), 500


@employee_bp.route('/skills/search', methods=['GET'])
@jwt_required()
def search_skills():
    """Поиск навыков"""
    try:
        current_user_id = get_jwt_identity()
        query = request.args.get('q', '').strip()
        category_id = request.args.get('category_id', type=int)
        
        skills = skill_service.search_skills(query, category_id, current_user_id)
        
        return jsonify({
            'skills': skills
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Search failed', 'message': str(e)}), 500


@employee_bp.route('/ratings', methods=['GET'])
@jwt_required()
def get_ratings():
    """Получение оценок текущего пользователя"""
    try:
        current_user_id = get_jwt_identity()
        
        ratings = rating_service.get_user_ratings(current_user_id)
        
        return jsonify({
            'ratings': ratings
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get ratings', 'message': str(e)}), 500


@employee_bp.route('/ratings', methods=['POST'])
@jwt_required()
def create_rating():
    """Создание/обновление оценки навыка"""
    try:
        current_user_id = get_jwt_identity()
        
        # Валидация данных
        data = request.get_json()
        errors = rating_create_schema.validate(data)
        if errors:
            return jsonify({'error': 'Validation error', 'details': errors}), 400
        
        # Проверка существования навыка
        skill = Skill.query.get(data['skill_id'])
        if not skill or not skill.is_active:
            return jsonify({'error': 'Skill not found or inactive'}), 404
        
        # Создание/обновление оценки
        rating = rating_service.create_or_update_rating(
            user_id=current_user_id,
            skill_id=data['skill_id'],
            self_score=data['self_score'],
            notes=data.get('notes')
        )
        
        # Отправка уведомления руководителю (если есть)
        user = User.query.get(current_user_id)
        if user.manager_id:
            notification = Notification(
                user_id=user.manager_id,
                type='new_assessment',
                title='Новая оценка навыка',
                message=f'{user.full_name} оценил навык "{skill.name}" на {data["self_score"]} баллов',
                data={
                    'user_id': current_user_id,
                    'user_name': user.full_name,
                    'skill_id': skill.id,
                    'skill_name': skill.name,
                    'rating_id': rating.id,
                    'score': data['self_score']
                }
            )
            db.session.add(notification)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Rating saved successfully',
            'rating': rating.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to save rating', 'message': str(e)}), 500


@employee_bp.route('/ratings/bulk', methods=['POST'])
@jwt_required()
def bulk_update_ratings():
    """Массовое обновление оценок"""
    try:
        current_user_id = get_jwt_identity()
        
        # Валидация данных
        data = request.get_json()
        errors = bulk_rating_update_schema.validate(data)
        if errors:
            return jsonify({'error': 'Validation error', 'details': errors}), 400
        
        # Обновление оценок
        results = rating_service.bulk_update_ratings(current_user_id, data['ratings'])
        
        return jsonify({
            'message': f'Successfully updated {len(results["updated"])} ratings',
            'results': results
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Bulk update failed', 'message': str(e)}), 500


@employee_bp.route('/ratings/required', methods=['GET'])
@jwt_required()
def get_required_skills():
    """Получение обязательных навыков для отдела"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user.department_id:
            return jsonify({'required_skills': []}), 200
        
        required_skills = skill_service.get_required_skills(user.department_id, current_user_id)
        
        return jsonify({
            'required_skills': required_skills
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get required skills', 'message': str(e)}), 500


@employee_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Получение профиля с радарной диаграммой"""
    try:
        current_user_id = get_jwt_identity()
        
        profile = rating_service.get_user_profile(current_user_id)
        
        return jsonify({
            'profile': profile
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get profile', 'message': str(e)}), 500


@employee_bp.route('/profile/radar-data', methods=['GET'])
@jwt_required()
def get_radar_data():
    """Получение данных для радарной диаграммы"""
    try:
        current_user_id = get_jwt_identity()
        
        radar_data = rating_service.get_radar_chart_data(current_user_id)
        
        return jsonify({
            'radar_data': radar_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get radar data', 'message': str(e)}), 500


@employee_bp.route('/history', methods=['GET'])
@jwt_required()
def get_rating_history():
    """Получение истории изменений оценок"""
    try:
        current_user_id = get_jwt_identity()
        
        # Параметры фильтрации
        skill_id = request.args.get('skill_id', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Преобразование дат
        if start_date:
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        history = rating_service.get_rating_history(
            user_id=current_user_id,
            skill_id=skill_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )
        
        return jsonify({
            'history': history['entries'],
            'total': history['total'],
            'limit': limit,
            'offset': offset
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get history', 'message': str(e)}), 500


@employee_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_stats():
    """Получение статистики пользователя"""
    try:
        current_user_id = get_jwt_identity()
        
        stats = rating_service.get_user_stats(current_user_id)
        
        return jsonify({
            'stats': stats
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get stats', 'message': str(e)}), 500


@employee_bp.route('/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    """Получение уведомлений пользователя"""
    try:
        current_user_id = get_jwt_identity()
        
        # Параметры
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        limit = request.args.get('limit', 20, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        query = Notification.query.filter_by(user_id=current_user_id)
        
        if unread_only:
            query = query.filter_by(is_read=False)
        
        total = query.count()
        notifications = query.order_by(Notification.created_at.desc()) \
                            .offset(offset).limit(limit).all()
        
        return jsonify({
            'notifications': [n.to_dict() for n in notifications],
            'total': total,
            'unread_count': Notification.query.filter_by(
                user_id=current_user_id, is_read=False
            ).count(),
            'limit': limit,
            'offset': offset
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get notifications', 'message': str(e)}), 500


@employee_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@jwt_required()
def mark_notification_read(notification_id):
    """Отметить уведомление как прочитанное"""
    try:
        current_user_id = get_jwt_identity()
        
        notification = Notification.query.filter_by(
            id=notification_id, user_id=current_user_id
        ).first()
        
        if not notification:
            return jsonify({'error': 'Notification not found'}), 404
        
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Notification marked as read'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to mark notification as read', 'message': str(e)}), 500


@employee_bp.route('/notifications/read-all', methods=['POST'])
@jwt_required()
def mark_all_notifications_read():
    """Отметить все уведомления как прочитанные"""
    try:
        current_user_id = get_jwt_identity()
        
        Notification.query.filter_by(user_id=current_user_id, is_read=False) \
            .update({'is_read': True, 'read_at': datetime.utcnow()})
        
        db.session.commit()
        
        return jsonify({
            'message': 'All notifications marked as read'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to mark notifications as read', 'message': str(e)}), 500


@employee_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard():
    """Получение данных для дашборда сотрудника"""
    try:
        current_user_id = get_jwt_identity()
        
        dashboard_data = rating_service.get_employee_dashboard(current_user_id)
        
        return jsonify({
            'dashboard': dashboard_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get dashboard data', 'message': str(e)}), 500