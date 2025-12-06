"""
Маршруты для работы с навыками (доступны всем авторизованным пользователям)
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_, and_, func, desc, asc

from ..models import db, Skill, SkillCategory, UserSkillRating, User
from ..schemas import SkillCreateSchema, SkillUpdateSchema, SkillCategoryCreateSchema
from ..services.skill_service import SkillService
from ..auth import requires_roles, get_current_user

skill_bp = Blueprint('skill', __name__)
skill_service = SkillService()

skill_create_schema = SkillCreateSchema()
skill_update_schema = SkillUpdateSchema()
skill_category_create_schema = SkillCategoryCreateSchema()


@skill_bp.route('/categories', methods=['GET'])
@jwt_required()
def get_categories():
    """
    Получение списка всех категорий навыков

    Returns:
        JSON: Список категорий с навыками
    """
    try:
        current_user_id = get_jwt_identity()

        categories = skill_service.get_categories_with_skills(current_user_id)

        return jsonify({
            'success': True,
            'categories': categories,
            'count': len(categories)
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to get categories',
            'message': str(e)
        }), 500


@skill_bp.route('/categories/<int:category_id>', methods=['GET'])
@jwt_required()
def get_category(category_id):
    """
    Получение категории по ID с навыками

    Args:
        category_id (int): ID категории

    Returns:
        JSON: Категория с навыками
    """
    try:
        current_user_id = get_jwt_identity()

        category = SkillCategory.query.get(category_id)
        if not category:
            return jsonify({
                'success': False,
                'error': 'Category not found'
            }), 404

        # Получаем навыки категории с оценками пользователя
        skills = skill_service.get_skills_by_category(category_id, current_user_id)

        return jsonify({
            'success': True,
            'category': {
                'id': category.id,
                'name': category.name,
                'description': category.description,
                'icon': category.icon,
                'color': category.color,
                'created_at': category.created_at.isoformat(),
                'updated_at': category.updated_at.isoformat()
            },
            'skills': skills,
            'skill_count': len(skills)
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to get category',
            'message': str(e)
        }), 500


@skill_bp.route('/search', methods=['GET'])
@jwt_required()
def search_skills():
    """
    Поиск навыков по названию или описанию

    Query Parameters:
        q (str): Поисковый запрос
        category_id (int): Фильтр по категории
        difficulty (str): Фильтр по сложности
        limit (int): Ограничение количества результатов
        offset (int): Смещение

    Returns:
        JSON: Найденные навыки
    """
    try:
        current_user_id = get_jwt_identity()

        # Параметры запроса
        query = request.args.get('q', '').strip()
        category_id = request.args.get('category_id', type=int)
        difficulty = request.args.get('difficulty')
        limit = min(request.args.get('limit', 20, type=int), 100)
        offset = request.args.get('offset', 0, type=int)

        # Построение запроса
        search_query = Skill.query.filter_by(is_active=True)

        if query:
            search_term = f'%{query}%'
            search_query = search_query.filter(
                or_(
                    Skill.name.ilike(search_term),
                    Skill.description.ilike(search_term)
                )
            )

        if category_id:
            search_query = search_query.filter_by(category_id=category_id)

        if difficulty and difficulty in ['beginner', 'intermediate', 'advanced', 'expert']:
            search_query = search_query.filter_by(difficulty_level=difficulty)

        # Получаем общее количество
        total = search_query.count()

        # Получаем данные с пагинацией
        skills = search_query.order_by(Skill.name) \
                            .offset(offset).limit(limit).all()

        # Форматируем результат
        result_skills = []
        for skill in skills:
            skill_dict = skill.to_dict()

            # Получаем оценку пользователя
            rating = UserSkillRating.query.filter_by(
                user_id=current_user_id,
                skill_id=skill.id
            ).first()

            if rating:
                skill_dict['user_rating'] = rating.to_dict()
            else:
                skill_dict['user_rating'] = None

            result_skills.append(skill_dict)

        return jsonify({
            'success': True,
            'skills': result_skills,
            'total': total,
            'limit': limit,
            'offset': offset,
            'has_more': (offset + limit) < total
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Search failed',
            'message': str(e)
        }), 500


@skill_bp.route('/<int:skill_id>', methods=['GET'])
@jwt_required()
def get_skill(skill_id):
    """
    Получение информации о навыке

    Args:
        skill_id (int): ID навыка

    Returns:
        JSON: Информация о навыке
    """
    try:
        current_user_id = get_jwt_identity()

        skill = Skill.query.get(skill_id)
        if not skill or not skill.is_active:
            return jsonify({
                'success': False,
                'error': 'Skill not found'
            }), 404

        skill_dict = skill.to_dict()

        # Получаем оценку пользователя
        rating = UserSkillRating.query.filter_by(
            user_id=current_user_id,
            skill_id=skill.id
        ).first()

        if rating:
            skill_dict['user_rating'] = rating.to_dict()
        else:
            skill_dict['user_rating'] = None

        # Получаем статистику по навыку
        ratings = UserSkillRating.query.filter_by(skill_id=skill_id)
        total_ratings = ratings.count()

        if total_ratings > 0:
            avg_score = ratings.with_entities(
                func.avg(UserSkillRating.effective_score)
            ).scalar() or 0

            # Распределение оценок
            distribution = {}
            for score in range(1, 6):
                count = ratings.filter_by(final_score=score).count()
                distribution[score] = count
        else:
            avg_score = 0
            distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        # Проверяем, является ли навык обязательным для отдела пользователя
        from ..models import RequiredDepartmentSkill
        user = User.query.get(current_user_id)

        is_required = False
        min_required_score = None

        if user and user.department_id:
            required_skill = RequiredDepartmentSkill.query.filter_by(
                department_id=user.department_id,
                skill_id=skill_id
            ).first()

            if required_skill:
                is_required = required_skill.is_required
                min_required_score = required_skill.min_score

        return jsonify({
            'success': True,
            'skill': skill_dict,
            'stats': {
                'total_ratings': total_ratings,
                'average_score': round(float(avg_score), 2),
                'score_distribution': distribution
            },
            'is_required': is_required,
            'min_required_score': min_required_score
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to get skill',
            'message': str(e)
        }), 500


@skill_bp.route('/popular', methods=['GET'])
@jwt_required()
def get_popular_skills():
    """
    Получение самых популярных навыков (по количеству оценок)

    Query Parameters:
        limit (int): Ограничение количества
        category_id (int): Фильтр по категории

    Returns:
        JSON: Популярные навыки
    """
    try:
        limit = min(request.args.get('limit', 10, type=int), 50)
        category_id = request.args.get('category_id', type=int)

        skills = skill_service.get_popular_skills(limit)

        # Фильтрация по категории, если указана
        if category_id:
            skills = [s for s in skills if s.get('category_id') == category_id]

        return jsonify({
            'success': True,
            'skills': skills,
            'count': len(skills)
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to get popular skills',
            'message': str(e)
        }), 500


@skill_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_skills_stats():
    """
    Получение статистики по навыкам

    Returns:
        JSON: Статистика
    """
    try:
        # Общая статистика
        total_skills = Skill.query.filter_by(is_active=True).count()
        total_categories = SkillCategory.query.count()

        # Распределение по категориям
        category_stats = db.session.query(
            SkillCategory.name,
            func.count(Skill.id).label('skill_count')
        ).join(
            Skill, Skill.category_id == SkillCategory.id
        ).filter(
            Skill.is_active == True
        ).group_by(
            SkillCategory.id, SkillCategory.name
        ).all()

        # Распределение по сложности
        difficulty_stats = db.session.query(
            Skill.difficulty_level,
            func.count(Skill.id).label('skill_count')
        ).filter(
            Skill.is_active == True
        ).group_by(
            Skill.difficulty_level
        ).all()

        # Самые оцениваемые навыки
        top_rated_skills = db.session.query(
            Skill.name,
            func.count(UserSkillRating.id).label('rating_count'),
            func.avg(UserSkillRating.effective_score).label('avg_score')
        ).join(
            UserSkillRating, Skill.id == UserSkillRating.skill_id
        ).filter(
            Skill.is_active == True
        ).group_by(
            Skill.id, Skill.name
        ).order_by(
            desc('rating_count')
        ).limit(5).all()

        stats = {
            'total_skills': total_skills,
            'total_categories': total_categories,
            'categories': [
                {
                    'name': name,
                    'skill_count': count
                }
                for name, count in category_stats
            ],
            'difficulty_levels': [
                {
                    'level': level,
                    'skill_count': count
                }
                for level, count in difficulty_stats
            ],
            'top_rated_skills': [
                {
                    'name': name,
                    'rating_count': count,
                    'average_score': round(float(avg_score or 0), 2)
                }
                for name, count, avg_score in top_rated_skills
            ]
        }

        return jsonify({
            'success': True,
            'stats': stats
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to get skills stats',
            'message': str(e)
        }), 500


@skill_bp.route('/categories', methods=['POST'])
@jwt_required()
@requires_roles('admin')
def create_category():
    """
    Создание новой категории навыков (только для администраторов)

    Request Body:
        name (str): Название категории
        description (str): Описание
        icon (str): Иконка FontAwesome
        color (str): Цвет в HEX формате

    Returns:
        JSON: Созданная категория
    """
    try:
        current_user = get_current_user()

        # Валидация данных
        data = request.get_json()
        errors = skill_category_create_schema.validate(data)
        if errors:
            return jsonify({
                'success': False,
                'error': 'Validation error',
                'details': errors
            }), 400

        # Проверка уникальности
        if SkillCategory.query.filter_by(name=data['name']).first():
            return jsonify({
                'success': False,
                'error': 'Category with this name already exists'
            }), 409

        # Создание категории
        category = skill_service.create_category(**data)

        # Логирование
        from ..models import AuditLog
        audit_log = AuditLog(
            user_id=current_user.id,
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
            'success': True,
            'message': 'Category created successfully',
            'category': category.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to create category',
            'message': str(e)
        }), 500


@skill_bp.route('/categories/<int:category_id>', methods=['PUT'])
@jwt_required()
@requires_roles('admin')
def update_category(category_id):
    """
    Обновление категории навыков (только для администраторов)

    Args:
        category_id (int): ID категории

    Request Body:
        name (str): Название категории
        description (str): Описание
        icon (str): Иконка FontAwesome
        color (str): Цвет в HEX формате

    Returns:
        JSON: Обновленная категория
    """
    try:
        current_user = get_current_user()

        category = SkillCategory.query.get(category_id)
        if not category:
            return jsonify({
                'success': False,
                'error': 'Category not found'
            }), 404

        # Валидация данных
        data = request.get_json()
        errors = skill_category_create_schema.validate(data, partial=True)
        if errors:
            return jsonify({
                'success': False,
                'error': 'Validation error',
                'details': errors
            }), 400

        # Проверка уникальности имени
        if 'name' in data and data['name'] != category.name:
            if SkillCategory.query.filter_by(name=data['name']).first():
                return jsonify({
                    'success': False,
                    'error': 'Category with this name already exists'
                }), 409

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
            from ..models import AuditLog
            audit_log = AuditLog(
                user_id=current_user.id,
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
            'success': True,
            'message': 'Category updated successfully',
            'category': updated_category.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to update category',
            'message': str(e)
        }), 500


@skill_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@jwt_required()
@requires_roles('admin')
def delete_category(category_id):
    """
    Удаление категории навыков (только для администраторов)

    Args:
        category_id (int): ID категории

    Returns:
        JSON: Результат удаления
    """
    try:
        current_user = get_current_user()

        category = SkillCategory.query.get(category_id)
        if not category:
            return jsonify({
                'success': False,
                'error': 'Category not found'
            }), 404

        # Проверка наличия навыков в категории
        skill_count = category.skills.count()
        if skill_count > 0:
            return jsonify({
                'success': False,
                'error': 'Cannot delete category with skills',
                'skill_count': skill_count,
                'skills': [s.name for s in category.skills.limit(10)]
            }), 400

        # Логирование
        from ..models import AuditLog
        audit_log = AuditLog(
            user_id=current_user.id,
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
            'success': True,
            'message': 'Category deleted successfully'
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to delete category',
            'message': str(e)
        }), 500


@skill_bp.route('', methods=['POST'])
@jwt_required()
@requires_roles('admin')
def create_skill():
    """
    Создание нового навыка (только для администраторов)

    Request Body:
        name (str): Название навыка
        description (str): Описание
        category_id (int): ID категории
        difficulty_level (str): Уровень сложности
        is_active (bool): Активен ли навык

    Returns:
        JSON: Созданный навык
    """
    try:
        current_user = get_current_user()

        # Валидация данных
        data = request.get_json()
        errors = skill_create_schema.validate(data)
        if errors:
            return jsonify({
                'success': False,
                'error': 'Validation error',
                'details': errors
            }), 400

        # Проверка существования категории
        category = SkillCategory.query.get(data['category_id'])
        if not category:
            return jsonify({
                'success': False,
                'error': 'Category not found'
            }), 404

        # Проверка уникальности имени
        if Skill.query.filter_by(name=data['name']).first():
            return jsonify({
                'success': False,
                'error': 'Skill with this name already exists'
            }), 409

        # Создание навыка
        skill = skill_service.create_skill(**data)

        # Логирование
        from ..models import AuditLog
        audit_log = AuditLog(
            user_id=current_user.id,
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
            'success': True,
            'message': 'Skill created successfully',
            'skill': skill.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to create skill',
            'message': str(e)
        }), 500


@skill_bp.route('/<int:skill_id>', methods=['PUT'])
@jwt_required()
@requires_roles('admin')
def update_skill(skill_id):
    """
    Обновление навыка (только для администраторов)

    Args:
        skill_id (int): ID навыка

    Request Body:
        name (str): Название навыка
        description (str): Описание
        category_id (int): ID категории
        difficulty_level (str): Уровень сложности
        is_active (bool): Активен ли навык

    Returns:
        JSON: Обновленный навык
    """
    try:
        current_user = get_current_user()

        skill = Skill.query.get(skill_id)
        if not skill:
            return jsonify({
                'success': False,
                'error': 'Skill not found'
            }), 404

        # Валидация данных
        data = request.get_json()
        errors = skill_update_schema.validate(data, partial=True)
        if errors:
            return jsonify({
                'success': False,
                'error': 'Validation error',
                'details': errors
            }), 400

        # Проверка уникальности имени
        if 'name' in data and data['name'] != skill.name:
            if Skill.query.filter_by(name=data['name']).first():
                return jsonify({
                    'success': False,
                    'error': 'Skill with this name already exists'
                }), 409

        # Проверка существования категории
        if 'category_id' in data:
            category = SkillCategory.query.get(data['category_id'])
            if not category:
                return jsonify({
                    'success': False,
                    'error': 'Category not found'
                }), 404

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
            from ..models import AuditLog
            audit_log = AuditLog(
                user_id=current_user.id,
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
            'success': True,
            'message': 'Skill updated successfully',
            'skill': updated_skill.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to update skill',
            'message': str(e)
        }), 500


@skill_bp.route('/<int:skill_id>', methods=['DELETE'])
@jwt_required()
@requires_roles('admin')
def delete_skill(skill_id):
    """
    Удаление навыка (только для администраторов)

    Args:
        skill_id (int): ID навыка

    Returns:
        JSON: Результат удаления
    """
    try:
        current_user = get_current_user()

        skill = Skill.query.get(skill_id)
        if not skill:
            return jsonify({
                'success': False,
                'error': 'Skill not found'
            }), 404

        # Проверка наличия оценок
        rating_count = skill.ratings.count()
        if rating_count > 0:
            return jsonify({
                'success': False,
                'error': 'Cannot delete skill with ratings',
                'rating_count': rating_count
            }), 400

        # Логирование
        from ..models import AuditLog
        audit_log = AuditLog(
            user_id=current_user.id,
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
            'success': True,
            'message': 'Skill deleted successfully'
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to delete skill',
            'message': str(e)
        }), 500


@skill_bp.route('/<int:skill_id>/stats', methods=['GET'])
@jwt_required()
def get_skill_stats(skill_id):
    """
    Получение детальной статистики по навыку

    Args:
        skill_id (int): ID навыка

    Returns:
        JSON: Статистика навыка
    """
    try:
        stats = skill_service.get_skill_stats(skill_id)

        return jsonify({
            'success': True,
            'stats': stats
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to get skill stats',
            'message': str(e)
        }), 500


@skill_bp.route('/required/<int:department_id>', methods=['GET'])
@jwt_required()
def get_required_skills_for_department(department_id):
    """
    Получение обязательных навыков для отдела

    Args:
        department_id (int): ID отдела

    Returns:
        JSON: Обязательные навыки отдела
    """
    try:
        current_user_id = get_jwt_identity()

        from ..models import Department, RequiredDepartmentSkill

        # Проверка существования отдела
        department = Department.query.get(department_id)
        if not department:
            return jsonify({
                'success': False,
                'error': 'Department not found'
            }), 404

        # Получение обязательных навыков
        required_skills = skill_service.get_required_skills(department_id, current_user_id)

        return jsonify({
            'success': True,
            'department': {
                'id': department.id,
                'name': department.name,
                'code': department.code
            },
            'required_skills': required_skills,
            'count': len(required_skills)
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to get required skills',
            'message': str(e)
        }), 500


@skill_bp.route('/compare', methods=['GET'])
@jwt_required()
def compare_skills():
    """
    Сравнение нескольких навыков

    Query Parameters:
        skill_ids (str): ID навыков через запятую

    Returns:
        JSON: Сравнение навыков
    """
    try:
        skill_ids_str = request.args.get('skill_ids', '')
        if not skill_ids_str:
            return jsonify({
                'success': False,
                'error': 'Skill IDs are required'
            }), 400

        # Преобразуем строку ID в список
        try:
            skill_ids = [int(id.strip()) for id in skill_ids_str.split(',')]
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid skill IDs format'
            }), 400

        if len(skill_ids) < 2:
            return jsonify({
                'success': False,
                'error': 'At least 2 skills required for comparison'
            }), 400

        if len(skill_ids) > 10:
            return jsonify({
                'success': False,
                'error': 'Maximum 10 skills allowed for comparison'
            }), 400

        # Получаем навыки
        skills = Skill.query.filter(
            Skill.id.in_(skill_ids),
            Skill.is_active == True
        ).all()

        if len(skills) != len(skill_ids):
            return jsonify({
                'success': False,
                'error': 'Some skills not found'
            }), 404

        # Получаем статистику для каждого навыка
        comparison_data = []
        for skill in skills:
            stats = skill_service.get_skill_stats(skill.id)
            comparison_data.append({
                'skill': skill.to_dict(),
                'stats': stats
            })

        return jsonify({
            'success': True,
            'comparison': comparison_data,
            'count': len(comparison_data)
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to compare skills',
            'message': str(e)
        }), 500
