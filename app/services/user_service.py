from datetime import datetime
from sqlalchemy import or_, and_, func
from ..models import db, User, Department, AuditLog
from ..utils.auth_utils import hash_password


class UserService:
    """Сервис для работы с пользователями"""
    
    def get_user_by_username(self, username):
        """Получение пользователя по username"""
        return User.query.filter_by(username=username).first()
    
    def get_user_by_email(self, email):
        """Получение пользователя по email"""
        return User.query.filter_by(email=email).first()
    
    def create_user(self, **kwargs):
        """Создание нового пользователя"""
        password = kwargs.pop('password', None)
        confirm_password = kwargs.pop('confirm_password', None)
        
        if password:
            kwargs['password_hash'] = hash_password(password)
        
        user = User(**kwargs)
        db.session.add(user)
        db.session.commit()
        
        return user
    
    def update_user(self, user_id, **kwargs):
        """Обновление пользователя"""
        user = User.query.get(user_id)
        if not user:
            raise ValueError('User not found')
        
        # Обновление полей
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        db.session.commit()
        return user
    
    def update_last_login(self, user_id):
        """Обновление времени последнего входа"""
        user = User.query.get(user_id)
        if user:
            user.last_login = datetime.utcnow()
            db.session.commit()
    
    def get_subordinates(self, manager_id):
        """Получение подчиненных менеджера"""
        return User.query.filter_by(manager_id=manager_id, is_active=True).all()
    
    def get_department_employees(self, department_id):
        """Получение сотрудников отдела"""
        return User.query.filter_by(
            department_id=department_id, 
            is_active=True,
            role='employee'
        ).all()
    
    def can_view_employee(self, current_user, employee_id):
        """Проверка прав доступа к просмотру сотрудника"""
        if current_user.role == 'admin':
            return True
        
        if current_user.role == 'manager':
            employee = User.query.get(employee_id)
            if not employee:
                return False
            
            # Менеджер может видеть сотрудников своего отдела и своих подчиненных
            if employee.department_id == current_user.department_id:
                return True
            
            # Проверка подчиненности (рекурсивно)
            def is_subordinate(manager_id, target_id):
                subordinates = User.query.filter_by(manager_id=manager_id, is_active=True).all()
                for sub in subordinates:
                    if sub.id == target_id:
                        return True
                    if is_subordinate(sub.id, target_id):
                        return True
                return False
            
            return is_subordinate(current_user.id, employee_id)
        
        # Сотрудник может видеть только себя
        return current_user.id == employee_id
    
    def can_manage_employee(self, current_user, employee_id):
        """Проверка прав доступа к управлению сотрудником"""
        if current_user.role == 'admin':
            return True
        
        if current_user.role == 'manager':
            employee = User.query.get(employee_id)
            if not employee:
                return False
            
            # Менеджер может управлять сотрудниками своего отдела
            return employee.department_id == current_user.department_id
        
        return False
    
    def search_users(self, search_term, role=None, department_id=None, limit=50):
        """Поиск пользователей"""
        query = User.query.filter_by(is_active=True)
        
        if search_term:
            search_term = f'%{search_term}%'
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
        
        return query.limit(limit).all()
    
    def deactivate_user(self, user_id):
        """Деактивация пользователя"""
        user = User.query.get(user_id)
        if user:
            user.is_active = False
            db.session.commit()
            return True
        return False
    
    def activate_user(self, user_id):
        """Активация пользователя"""
        user = User.query.get(user_id)
        if user:
            user.is_active = True
            db.session.commit()
            return True
        return False
    
    def change_user_role(self, user_id, new_role):
        """Изменение роли пользователя"""
        if new_role not in ['employee', 'manager', 'admin']:
            raise ValueError('Invalid role')
        
        user = User.query.get(user_id)
        if user:
            user.role = new_role
            db.session.commit()
            return True
        return False
    
    def assign_manager(self, user_id, manager_id):
        """Назначение менеджера пользователю"""
        user = User.query.get(user_id)
        manager = User.query.get(manager_id)
        
        if not user or not manager or manager.role != 'manager':
            raise ValueError('Invalid user or manager')
        
        user.manager_id = manager_id
        db.session.commit()
        return True
    
    def get_user_dashboard_data(self, user_id):
        """Получение данных для дашборда пользователя"""
        user = User.query.get(user_id)
        if not user:
            raise ValueError('User not found')
        
        # Статистика по оценкам
        ratings = UserSkillRating.query.filter_by(user_id=user_id)
        total_ratings = ratings.count()
        pending_ratings = ratings.filter_by(status='pending').count()
        confirmed_ratings = ratings.filter_by(status='confirmed').count()
        
        # Последние оценки
        recent_ratings = ratings.order_by(
            UserSkillRating.updated_at.desc()
        ).limit(5).all()
        
        # Обязательные навыки
        required_skills_count = 0
        if user.department_id:
            required_skills = RequiredDepartmentSkill.query.filter_by(
                department_id=user.department_id
            ).count()
        
        return {
            'user': user.to_dict(),
            'stats': {
                'total_ratings': total_ratings,
                'pending_ratings': pending_ratings,
                'confirmed_ratings': confirmed_ratings,
                'required_skills': required_skills_count
            },
            'recent_ratings': [r.to_dict() for r in recent_ratings]
        }