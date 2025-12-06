from datetime import datetime, timedelta
from sqlalchemy import func, case, desc, asc, and_, or_
import json

from ..models import db, User, Skill, UserSkillRating, RatingHistory, SkillCategory


class RatingService:
    """Сервис для работы с оценками"""
    
    def create_or_update_rating(self, user_id, skill_id, self_score, notes=None):
        """Создание или обновление оценки навыка"""
        # Проверка существования оценки
        rating = UserSkillRating.query.filter_by(
            user_id=user_id,
            skill_id=skill_id
        ).first()
        
        if rating:
            # Обновление существующей оценки
            old_self_score = rating.self_score
            old_status = rating.status
            
            rating.self_score = self_score
            rating.self_assessment_date = datetime.utcnow()
            rating.status = 'pending'
            
            if notes is not None:
                rating.notes = notes
            
            # Запись в историю
            if old_self_score != self_score:
                history_entry = RatingHistory(
                    rating_id=rating.id,
                    user_id=user_id,
                    changed_by_id=user_id,
                    action='updated',
                    old_self_score=old_self_score,
                    new_self_score=self_score,
                    old_status=old_status,
                    new_status='pending',
                    notes=notes or ''
                )
                db.session.add(history_entry)
        else:
            # Создание новой оценки
            rating = UserSkillRating(
                user_id=user_id,
                skill_id=skill_id,
                self_score=self_score,
                self_assessment_date=datetime.utcnow(),
                notes=notes,
                status='pending'
            )
            db.session.add(rating)
            
            # Запись в историю
            history_entry = RatingHistory(
                rating_id=rating.id,
                user_id=user_id,
                changed_by_id=user_id,
                action='created',
                new_self_score=self_score,
                new_status='pending',
                notes=notes or ''
            )
            db.session.add(history_entry)
        
        db.session.commit()
        return rating
    
    def bulk_update_ratings(self, user_id, ratings_data):
        """Массовое обновление оценок"""
        results = {
            'created': [],
            'updated': [],
            'errors': []
        }
        
        for rating_data in ratings_data:
            try:
                rating = self.create_or_update_rating(
                    user_id=user_id,
                    skill_id=rating_data['skill_id'],
                    self_score=rating_data['self_score'],
                    notes=rating_data.get('notes')
                )
                
                if rating.id:
                    results['updated'].append(rating.id)
                else:
                    results['created'].append(rating.id)
                    
            except Exception as e:
                results['errors'].append({
                    'skill_id': rating_data.get('skill_id'),
                    'error': str(e)
                })
        
        return results
    
    def get_user_ratings(self, user_id):
        """Получение оценок пользователя"""
        ratings = UserSkillRating.query.filter_by(user_id=user_id).all()
        return [r.to_dict() for r in ratings]
    
    def get_user_profile(self, user_id):
        """Получение профиля пользователя с оценками"""
        user = User.query.get(user_id)
        if not user:
            raise ValueError('User not found')
        
        ratings = UserSkillRating.query.filter_by(user_id=user_id).all()
        
        # Группировка по категориям
        categories = {}
        for rating in ratings:
            skill = rating.skill
            if not skill or not skill.category:
                continue
            
            category_id = skill.category.id
            if category_id not in categories:
                categories[category_id] = {
                    'category': skill.category.to_dict(),
                    'skills': [],
                    'average_score': 0,
                    'skill_count': 0
                }
            
            categories[category_id]['skills'].append(rating.to_dict())
            categories[category_id]['skill_count'] += 1
        
        # Расчет средних оценок по категориям
        for category_data in categories.values():
            total_score = sum(r['effective_score'] for r in category_data['skills'])
            category_data['average_score'] = round(
                total_score / category_data['skill_count'], 2
            ) if category_data['skill_count'] > 0 else 0
        
        return {
            'user': user.to_dict(),
            'categories': list(categories.values()),
            'total_skills': len(ratings),
            'average_score': sum(r.effective_score for r in ratings) / len(ratings) if ratings else 0
        }
    
    def get_radar_chart_data(self, user_id):
        """Получение данных для радарной диаграммы"""
        ratings = UserSkillRating.query.filter_by(user_id=user_id).all()
        
        # Группировка по категориям
        category_scores = {}
        category_counts = {}
        
        for rating in ratings:
            skill = rating.skill
            if not skill or not skill.category:
                continue
            
            category_id = skill.category.id
            category_name = skill.category.name
            
            if category_id not in category_scores:
                category_scores[category_id] = 0
                category_counts[category_id] = 0
            
            category_scores[category_id] += rating.effective_score
            category_counts[category_id] += 1
        
        # Расчет средних оценок
        categories = []
        scores = []
        
        for category_id, total_score in category_scores.items():
            count = category_counts[category_id]
            if count > 0:
                category = SkillCategory.query.get(category_id)
                avg_score = total_score / count
                
                categories.append(category.name)
                scores.append(round(avg_score, 2))
        
        return {
            'categories': categories,
            'scores': scores,
            'max_score': 5,
            'min_score': 1
        }
    
    def get_rating_history(self, user_id, skill_id=None, start_date=None, end_date=None, limit=50, offset=0):
        """Получение истории изменений оценок"""
        query = RatingHistory.query.filter_by(user_id=user_id)
        
        if skill_id:
            # Фильтрация по навыку через связь с оценкой
            query = query.join(UserSkillRating).filter(
                UserSkillRating.skill_id == skill_id
            )
        
        if start_date:
            query = query.filter(RatingHistory.created_at >= start_date)
        
        if end_date:
            query = query.filter(RatingHistory.created_at <= end_date)
        
        total = query.count()
        entries = query.order_by(RatingHistory.created_at.desc()) \
                      .offset(offset).limit(limit).all()
        
        return {
            'entries': [e.to_dict() for e in entries],
            'total': total
        }
    
    def get_user_stats(self, user_id):
        """Получение статистики пользователя"""
        ratings = UserSkillRating.query.filter_by(user_id=user_id)
        total_ratings = ratings.count()
        
        if total_ratings == 0:
            return {
                'total_ratings': 0,
                'average_score': 0,
                'pending_count': 0,
                'confirmed_count': 0,
                'rejected_count': 0,
                'by_category': {},
                'last_assessment': None
            }
        
        # Статусы оценок
        pending_count = ratings.filter_by(status='pending').count()
        confirmed_count = ratings.filter_by(status='confirmed').count()
        rejected_count = ratings.filter_by(status='rejected').count()
        
        # Средняя оценка
        avg_score = ratings.with_entities(
            func.avg(UserSkillRating.effective_score)
        ).scalar() or 0
        
        # Распределение по категориям
        category_stats = {}
        category_query = db.session.query(
            SkillCategory.name,
            func.count(UserSkillRating.id).label('count'),
            func.avg(UserSkillRating.effective_score).label('avg_score')
        ).join(
            Skill, Skill.category_id == SkillCategory.id
        ).join(
            UserSkillRating, UserSkillRating.skill_id == Skill.id
        ).filter(
            UserSkillRating.user_id == user_id
        ).group_by(
            SkillCategory.id, SkillCategory.name
        ).all()
        
        for category_name, count, avg in category_query:
            category_stats[category_name] = {
                'count': count,
                'average_score': round(float(avg or 0), 2)
            }
        
        # Дата последней оценки
        last_assessment = ratings.order_by(
            UserSkillRating.updated_at.desc()
        ).first()
        
        return {
            'total_ratings': total_ratings,
            'average_score': round(float(avg_score), 2),
            'pending_count': pending_count,
            'confirmed_count': confirmed_count,
            'rejected_count': rejected_count,
            'by_category': category_stats,
            'last_assessment': last_assessment.updated_at.isoformat() if last_assessment else None
        }
    
    def search_employees_by_skills(self, filters, department_id=None):
        """Поиск сотрудников по навыкам"""
        # Построение запроса
        query = User.query.filter_by(is_active=True, role='employee')
        
        if department_id:
            query = query.filter_by(department_id=department_id)
        
        # Применение фильтров
        for i, skill_filter in enumerate(filters):
            skill_id = skill_filter['skill_id']
            operator = skill_filter['operator']
            value = skill_filter['value']
            
            # Подзапрос для фильтрации по навыку
            subquery = UserSkillRating.query.filter(
                UserSkillRating.user_id == User.id,
                UserSkillRating.skill_id == skill_id
            )
            
            # Применение оператора
            if operator == '=':
                subquery = subquery.filter(UserSkillRating.effective_score == value)
            elif operator == '>':
                subquery = subquery.filter(UserSkillRating.effective_score > value)
            elif operator == '<':
                subquery = subquery.filter(UserSkillRating.effective_score < value)
            elif operator == '>=':
                subquery = subquery.filter(UserSkillRating.effective_score >= value)
            elif operator == '<=':
                subquery = subquery.filter(UserSkillRating.effective_score <= value)
            elif operator == '!=':
                subquery = subquery.filter(UserSkillRating.effective_score != value)
            
            # Проверка существования оценки
            query = query.filter(subquery.exists())
        
        employees = query.all()
        
        # Добавление информации о навыках для каждого сотрудника
        result = []
        for employee in employees:
            employee_data = employee.to_dict()
            
            # Получение оценок сотрудника по фильтрованным навыкам
            skill_ratings = []
            for skill_filter in filters:
                rating = UserSkillRating.query.filter_by(
                    user_id=employee.id,
                    skill_id=skill_filter['skill_id']
                ).first()
                
                if rating:
                    skill = Skill.query.get(skill_filter['skill_id'])
                    skill_ratings.append({
                        'skill_id': skill.id,
                        'skill_name': skill.name,
                        'score': rating.effective_score,
                        'status': rating.status
                    })
            
            employee_data['skill_ratings'] = skill_ratings
            result.append(employee_data)
        
        return result
    
    def compare_employees(self, employee_ids, show_differences=False, category_id=None):
        """Сравнение нескольких сотрудников"""
        if len(employee_ids) < 2:
            raise ValueError('At least two employees required for comparison')
        
        # Получение сотрудников
        employees = User.query.filter(
            User.id.in_(employee_ids),
            User.is_active == True
        ).all()
        
        if len(employees) != len(employee_ids):
            raise ValueError('Some employees not found')
        
        # Получение навыков для сравнения
        skill_query = Skill.query.filter_by(is_active=True)
        if category_id:
            skill_query = skill_query.filter_by(category_id=category_id)
        
        skills = skill_query.all()
        
        # Сбор данных для сравнения
        comparison_data = []
        for skill in skills:
            skill_data = {
                'skill_id': skill.id,
                'skill_name': skill.name,
                'category_id': skill.category_id,
                'category_name': skill.category.name if skill.category else None,
                'employees': {}
            }
            
            # Получение оценок для каждого сотрудника
            all_scores = []
            for employee in employees:
                rating = UserSkillRating.query.filter_by(
                    user_id=employee.id,
                    skill_id=skill.id
                ).first()
                
                score = rating.effective_score if rating else None
                skill_data['employees'][employee.id] = {
                    'score': score,
                    'status': rating.status if rating else None,
                    'employee_name': employee.full_name
                }
                
                if score is not None:
                    all_scores.append(score)
            
            # Проверка различий
            if all_scores:
                skill_data['has_differences'] = len(set(all_scores)) > 1
            else:
                skill_data['has_differences'] = False
            
            # Добавление в результат, если нужно показывать различия
            if not show_differences or skill_data['has_differences']:
                comparison_data.append(skill_data)
        
        # Статистика сравнения
        comparison_stats = {
            'total_skills': len(comparison_data),
            'skills_with_differences': sum(1 for s in comparison_data if s['has_differences']),
            'employees': [e.to_dict() for e in employees]
        }
        
        return {
            'comparison': comparison_data,
            'stats': comparison_stats
        }
    
    def get_employee_dashboard(self, user_id):
        """Получение данных для дашборда сотрудника"""
        user = User.query.get(user_id)
        if not user:
            raise ValueError('User not found')
        
        stats = self.get_user_stats(user_id)
        
        # Последние уведомления
        from ..models import Notification
        notifications = Notification.query.filter_by(
            user_id=user_id
        ).order_by(
            Notification.created_at.desc()
        ).limit(5).all()
        
        # Последние изменения в оценках
        recent_changes = RatingHistory.query.filter_by(
            user_id=user_id
        ).order_by(
            RatingHistory.created_at.desc()
        ).limit(10).all()
        
        # Рекомендуемые для оценки навыки
        recommended_skills = []
        if user.department_id:
            from ..models import RequiredDepartmentSkill
            required_skills = RequiredDepartmentSkill.query.filter_by(
                department_id=user.department_id
            ).all()
            
            for req_skill in required_skills:
                # Проверяем, есть ли уже оценка
                existing_rating = UserSkillRating.query.filter_by(
                    user_id=user_id,
                    skill_id=req_skill.skill_id
                ).first()
                
                if not existing_rating or existing_rating.status == 'pending':
                    skill = req_skill.skill
                    if skill and skill.is_active:
                        recommended_skills.append({
                            'skill': skill.to_dict(),
                            'min_score': req_skill.min_score,
                            'priority': req_skill.priority
                        })
        
        return {
            'user': user.to_dict(),
            'stats': stats,
            'notifications': [n.to_dict() for n in notifications],
            'recent_changes': [c.to_dict() for c in recent_changes],
            'recommended_skills': recommended_skills[:5]  # Только 5 самых приоритетных
        }
    
    def get_manager_dashboard(self, manager_id):
        """Получение данных для дашборда менеджера"""
        from ..services.user_service import UserService
        user_service = UserService()
        
        # Получение подчиненных
        subordinates = user_service.get_subordinates(manager_id)
        subordinate_ids = [s.id for s in subordinates]
        
        # Статистика по подчиненным
        if subordinate_ids:
            ratings = UserSkillRating.query.filter(
                UserSkillRating.user_id.in_(subordinate_ids)
            )
            
            total_ratings = ratings.count()
            pending_ratings = ratings.filter_by(status='pending').count()
            
            # Средняя оценка по отделу
            avg_score = ratings.with_entities(
                func.avg(UserSkillRating.effective_score)
            ).scalar() or 0
            
            # Распределение по статусам
            status_stats = db.session.query(
                UserSkillRating.status,
                func.count(UserSkillRating.id).label('count')
            ).filter(
                UserSkillRating.user_id.in_(subordinate_ids)
            ).group_by(
                UserSkillRating.status
            ).all()
        else:
            total_ratings = 0
            pending_ratings = 0
            avg_score = 0
            status_stats = []
        
        # Последние оценки подчиненных
        recent_ratings = []
        if subordinate_ids:
            recent_ratings = UserSkillRating.query.filter(
                UserSkillRating.user_id.in_(subordinate_ids)
            ).order_by(
                UserSkillRating.updated_at.desc()
            ).limit(10).all()
        
        # Уведомления менеджера
        from ..models import Notification
        notifications = Notification.query.filter_by(
            user_id=manager_id
        ).order_by(
            Notification.created_at.desc()
        ).limit(5).all()
        
        return {
            'subordinate_count': len(subordinates),
            'total_ratings': total_ratings,
            'pending_approvals': pending_ratings,
            'average_score': round(float(avg_score), 2),
            'status_distribution': {status: count for status, count in status_stats},
            'recent_ratings': [r.to_dict() for r in recent_ratings],
            'notifications': [n.to_dict() for n in notifications],
            'subordinates': [s.to_dict() for s in subordinates[:10]]  # Только 10 последних
        }
    
    def get_department_stats(self, department_id):
        """Получение статистики по отделу"""
        from ..models import Department, RequiredDepartmentSkill
        
        department = Department.query.get(department_id)
        if not department:
            raise ValueError('Department not found')
        
        # Сотрудники отдела
        employees = department.employees.filter_by(is_active=True, role='employee').all()
        employee_ids = [e.id for e in employees]
        
        # Общая статистика
        stats = {
            'department': department.to_dict(),
            'employee_count': len(employees),
            'manager': department.manager.to_dict() if department.manager else None
        }
        
        if employee_ids:
            # Статистика по оценкам
            ratings = UserSkillRating.query.filter(
                UserSkillRating.user_id.in_(employee_ids)
            )
            
            total_ratings = ratings.count()
            avg_score = ratings.with_entities(
                func.avg(UserSkillRating.effective_score)
            ).scalar() or 0
            
            # Распределение по категориям
            category_stats = db.session.query(
                SkillCategory.name,
                func.count(UserSkillRating.id).label('count'),
                func.avg(UserSkillRating.effective_score).label('avg_score')
            ).join(
                Skill, Skill.category_id == SkillCategory.id
            ).join(
                UserSkillRating, UserSkillRating.skill_id == Skill.id
            ).filter(
                UserSkillRating.user_id.in_(employee_ids)
            ).group_by(
                SkillCategory.id, SkillCategory.name
            ).all()
            
            # Обязательные навыки отдела
            required_skills = RequiredDepartmentSkill.query.filter_by(
                department_id=department_id
            ).all()
            
            # Проверка выполнения требований
            compliance_stats = []
            for req_skill in required_skills:
                skill = req_skill.skill
                if not skill:
                    continue
                
                # Сколько сотрудников соответствуют требованию
                compliant_count = UserSkillRating.query.filter(
                    UserSkillRating.skill_id == req_skill.skill_id,
                    UserSkillRating.user_id.in_(employee_ids),
                    UserSkillRating.effective_score >= req_skill.min_score
                ).count()
                
                compliance_rate = (compliant_count / len(employees)) * 100 if employees else 0
                
                compliance_stats.append({
                    'skill_id': skill.id,
                    'skill_name': skill.name,
                    'min_score': req_skill.min_score,
                    'compliant_count': compliant_count,
                    'total_count': len(employees),
                    'compliance_rate': round(compliance_rate, 2)
                })
            
            stats.update({
                'total_ratings': total_ratings,
                'average_score': round(float(avg_score), 2),
                'category_stats': [
                    {
                        'category': name,
                        'count': count,
                        'average_score': round(float(avg_score or 0), 2)
                    }
                    for name, count, avg_score in category_stats
                ],
                'compliance_stats': compliance_stats,
                'top_skills': self._get_department_top_skills(department_id),
                'skill_gaps': self._get_department_skill_gaps(department_id)
            })
        
        return stats
    
    def _get_department_top_skills(self, department_id):
        """Получение топ-навыков отдела"""
        from sqlalchemy import func
        
        top_skills = db.session.query(
            Skill.name,
            func.count(UserSkillRating.id).label('rating_count'),
            func.avg(UserSkillRating.effective_score).label('avg_score')
        ).join(
            UserSkillRating, Skill.id == UserSkillRating.skill_id
        ).join(
            User, UserSkillRating.user_id == User.id
        ).filter(
            User.department_id == department_id,
            User.is_active == True,
            Skill.is_active == True
        ).group_by(
            Skill.id, Skill.name
        ).order_by(
            desc('avg_score')
        ).limit(10).all()
        
        return [
            {
                'skill_name': name,
                'rating_count': count,
                'average_score': round(float(avg_score or 0), 2)
            }
            for name, count, avg_score in top_skills
        ]
    
    def _get_department_skill_gaps(self, department_id):
        """Выявление пробелов в навыках отдела"""
        from ..models import RequiredDepartmentSkill
        
        gaps = []
        
        # Обязательные навыки отдела
        required_skills = RequiredDepartmentSkill.query.filter_by(
            department_id=department_id
        ).all()
        
        for req_skill in required_skills:
            skill = req_skill.skill
            if not skill:
                continue
            
            # Процент сотрудников, не соответствующих требованию
            employees = User.query.filter_by(
                department_id=department_id,
                is_active=True,
                role='employee'
            ).all()
            
            if not employees:
                continue
            
            non_compliant_count = 0
            for employee in employees:
                rating = UserSkillRating.query.filter_by(
                    user_id=employee.id,
                    skill_id=skill.id
                ).first()
                
                if not rating or rating.effective_score < req_skill.min_score:
                    non_compliant_count += 1
            
            gap_percentage = (non_compliant_count / len(employees)) * 100
            
            if gap_percentage > 30:  # Значительный пробел
                gaps.append({
                    'skill_id': skill.id,
                    'skill_name': skill.name,
                    'min_score': req_skill.min_score,
                    'non_compliant_count': non_compliant_count,
                    'total_employees': len(employees),
                    'gap_percentage': round(gap_percentage, 2)
                })
        
        return sorted(gaps, key=lambda x: x['gap_percentage'], reverse=True)
