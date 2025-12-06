from sqlalchemy import func, case, desc, asc
from ..models import db, Skill, SkillCategory, UserSkillRating, RequiredDepartmentSkill


class SkillService:
    """Сервис для работы с навыками"""
    
    def get_all_categories(self):
        """Получение всех категорий с навыками"""
        categories = SkillCategory.query.all()
        return [self._category_to_dict(cat) for cat in categories]
    
    def get_categories_with_skills(self, user_id):
        """Получение категорий с навыками и оценками пользователя"""
        categories = SkillCategory.query.all()
        result = []
        
        for category in categories:
            category_dict = self._category_to_dict(category)
            
            # Получение навыков категории с оценками пользователя
            skills = Skill.query.filter_by(
                category_id=category.id, 
                is_active=True
            ).all()
            
            skills_data = []
            for skill in skills:
                skill_dict = skill.to_dict()
                
                # Получение оценки пользователя
                rating = UserSkillRating.query.filter_by(
                    user_id=user_id,
                    skill_id=skill.id
                ).first()
                
                if rating:
                    skill_dict['user_rating'] = rating.to_dict()
                else:
                    skill_dict['user_rating'] = None
                
                skills_data.append(skill_dict)
            
            category_dict['skills'] = skills_data
            result.append(category_dict)
        
        return result
    
    def get_skills_by_category(self, category_id, user_id):
        """Получение навыков по категории с оценками пользователя"""
        skills = Skill.query.filter_by(
            category_id=category_id, 
            is_active=True
        ).all()
        
        result = []
        for skill in skills:
            skill_dict = skill.to_dict()
            
            rating = UserSkillRating.query.filter_by(
                user_id=user_id,
                skill_id=skill.id
            ).first()
            
            if rating:
                skill_dict['user_rating'] = rating.to_dict()
            else:
                skill_dict['user_rating'] = None
            
            result.append(skill_dict)
        
        return result
    
    def search_skills(self, query, category_id=None, user_id=None):
        """Поиск навыков"""
        search_query = Skill.query.filter_by(is_active=True)
        
        if query:
            search_query = search_query.filter(
                or_(
                    Skill.name.ilike(f'%{query}%'),
                    Skill.description.ilike(f'%{query}%')
                )
            )
        
        if category_id:
            search_query = search_query.filter_by(category_id=category_id)
        
        skills = search_query.all()
        result = []
        
        for skill in skills:
            skill_dict = skill.to_dict()
            
            if user_id:
                rating = UserSkillRating.query.filter_by(
                    user_id=user_id,
                    skill_id=skill.id
                ).first()
                
                if rating:
                    skill_dict['user_rating'] = rating.to_dict()
                else:
                    skill_dict['user_rating'] = None
            
            result.append(skill_dict)
        
        return result
    
    def get_required_skills(self, department_id, user_id):
        """Получение обязательных навыков отдела с оценками пользователя"""
        required_skills = RequiredDepartmentSkill.query.filter_by(
            department_id=department_id,
            is_required=True
        ).all()
        
        result = []
        for req_skill in required_skills:
            skill = req_skill.skill
            if not skill or not skill.is_active:
                continue
            
            skill_dict = skill.to_dict()
            skill_dict['required_info'] = {
                'min_score': req_skill.min_score,
                'priority': req_skill.priority
            }
            
            # Получение оценки пользователя
            rating = UserSkillRating.query.filter_by(
                user_id=user_id,
                skill_id=skill.id
            ).first()
            
            if rating:
                skill_dict['user_rating'] = rating.to_dict()
            else:
                skill_dict['user_rating'] = None
            
            result.append(skill_dict)
        
        return result
    
    def create_category(self, **kwargs):
        """Создание категории навыков"""
        category = SkillCategory(**kwargs)
        db.session.add(category)
        db.session.commit()
        return category
    
    def update_category(self, category_id, **kwargs):
        """Обновление категории навыков"""
        category = SkillCategory.query.get(category_id)
        if not category:
            raise ValueError('Category not found')
        
        for key, value in kwargs.items():
            if hasattr(category, key):
                setattr(category, key, value)
        
        db.session.commit()
        return category
    
    def create_skill(self, **kwargs):
        """Создание навыка"""
        skill = Skill(**kwargs)
        db.session.add(skill)
        db.session.commit()
        return skill
    
    def update_skill(self, skill_id, **kwargs):
        """Обновление навыка"""
        skill = Skill.query.get(skill_id)
        if not skill:
            raise ValueError('Skill not found')
        
        for key, value in kwargs.items():
            if hasattr(skill, key):
                setattr(skill, key, value)
        
        db.session.commit()
        return skill
    
    def _category_to_dict(self, category):
        """Преобразование категории в словарь"""
        return {
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'icon': category.icon,
            'color': category.color,
            'skill_count': category.skills.filter_by(is_active=True).count(),
            'created_at': category.created_at.isoformat(),
            'updated_at': category.updated_at.isoformat()
        }
    
    def get_skill_stats(self, skill_id):
        """Получение статистики по навыку"""
        skill = Skill.query.get(skill_id)
        if not skill:
            raise ValueError('Skill not found')
        
        ratings = UserSkillRating.query.filter_by(skill_id=skill_id)
        
        # Базовая статистика
        total_ratings = ratings.count()
        
        if total_ratings == 0:
            return {
                'skill': skill.to_dict(),
                'total_ratings': 0,
                'average_score': 0,
                'score_distribution': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            }
        
        # Средняя оценка
        avg_score = db.session.query(
            func.avg(UserSkillRating.final_score)
        ).filter_by(skill_id=skill_id).scalar() or 0
        
        # Распределение оценок
        distribution = {}
        for score in range(1, 6):
            count = ratings.filter_by(final_score=score).count()
            distribution[score] = count
        
        return {
            'skill': skill.to_dict(),
            'total_ratings': total_ratings,
            'average_score': round(float(avg_score), 2),
            'score_distribution': distribution
        }
    
    def get_popular_skills(self, limit=10):
        """Получение самых популярных навыков"""
        skills = db.session.query(
            Skill,
            func.count(UserSkillRating.id).label('rating_count'),
            func.avg(UserSkillRating.final_score).label('avg_score')
        ).join(
            UserSkillRating, Skill.id == UserSkillRating.skill_id
        ).filter(
            Skill.is_active == True
        ).group_by(
            Skill.id
        ).order_by(
            desc('rating_count')
        ).limit(limit).all()
        
        result = []
        for skill, rating_count, avg_score in skills:
            skill_dict = skill.to_dict()
            skill_dict['rating_count'] = rating_count
            skill_dict['average_score'] = round(float(avg_score or 0), 2)
            result.append(skill_dict)
        
        return result