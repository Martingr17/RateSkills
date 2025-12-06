#!/usr/bin/env python3
"""
Скрипт для заполнения базы данных тестовыми данными
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import (
    User, Department, SkillCategory, Skill, 
    UserSkillRating, RequiredDepartmentSkill
)
from app.utils.auth_utils import hash_password
from datetime import datetime, timedelta
import random

def create_test_data():
    """Создание тестовых данных"""
    app = create_app('development')
    
    with app.app_context():
        # Очистка базы данных
        print("Clearing database...")
        db.drop_all()
        db.create_all()
        
        # Создание отделов
        print("Creating departments...")
        departments = [
            Department(name='IT Department', code='IT', description='Information Technology Department'),
            Department(name='HR Department', code='HR', description='Human Resources Department'),
            Department(name='Sales Department', code='SALES', description='Sales and Marketing Department'),
            Department(name='Finance Department', code='FIN', description='Finance Department'),
            Department(name='Operations Department', code='OPS', description='Operations Department')
        ]
        
        for dept in departments:
            db.session.add(dept)
        db.session.commit()
        
        # Создание категорий навыков
        print("Creating skill categories...")
        categories = [
            SkillCategory(name='Programming Languages', description='Programming languages and technologies', 
                         icon='fa-code', color='#3B82F6'),
            SkillCategory(name='Frameworks & Libraries', description='Development frameworks and libraries',
                         icon='fa-layer-group', color='#10B981'),
            SkillCategory(name='Databases', description='Database technologies',
                         icon='fa-database', color='#8B5CF6'),
            SkillCategory(name='DevOps & Tools', description='Development operations and tools',
                         icon='fa-tools', color='#F59E0B'),
            SkillCategory(name='Soft Skills', description='Soft skills and personal development',
                         icon='fa-comments', color='#EC4899'),
            SkillCategory(name='Project Management', description='Project management methodologies',
                         icon='fa-project-diagram', color='#6366F1')
        ]
        
        for cat in categories:
            db.session.add(cat)
        db.session.commit()
        
        # Создание навыков
        print("Creating skills...")
        skills_data = [
            # Programming Languages
            ('Python', 'Python programming language', 1, 'intermediate'),
            ('JavaScript', 'JavaScript programming language', 1, 'intermediate'),
            ('Java', 'Java programming language', 1, 'advanced'),
            ('C#', 'C# programming language', 1, 'intermediate'),
            ('Go', 'Go programming language', 1, 'beginner'),
            ('TypeScript', 'TypeScript programming language', 1, 'intermediate'),
            
            # Frameworks & Libraries
            ('React', 'React library for building user interfaces', 2, 'intermediate'),
            ('Vue.js', 'Vue.js progressive framework', 2, 'intermediate'),
            ('Django', 'Django web framework for Python', 2, 'advanced'),
            ('Spring Boot', 'Spring Boot framework for Java', 2, 'advanced'),
            ('.NET Core', '.NET Core framework', 2, 'intermediate'),
            ('Node.js', 'Node.js JavaScript runtime', 2, 'intermediate'),
            
            # Databases
            ('PostgreSQL', 'PostgreSQL relational database', 3, 'intermediate'),
            ('MySQL', 'MySQL relational database', 3, 'intermediate'),
            ('MongoDB', 'MongoDB NoSQL database', 3, 'intermediate'),
            ('Redis', 'Redis in-memory data store', 3, 'beginner'),
            ('Elasticsearch', 'Elasticsearch search engine', 3, 'advanced'),
            
            # DevOps & Tools
            ('Docker', 'Docker containerization platform', 4, 'intermediate'),
            ('Kubernetes', 'Kubernetes container orchestration', 4, 'advanced'),
            ('Git', 'Git version control system', 4, 'intermediate'),
            ('AWS', 'Amazon Web Services', 4, 'intermediate'),
            ('CI/CD', 'Continuous Integration/Continuous Deployment', 4, 'intermediate'),
            ('Linux', 'Linux operating system', 4, 'intermediate'),
            
            # Soft Skills
            ('Communication', 'Effective communication skills', 5, 'intermediate'),
            ('Teamwork', 'Collaboration and teamwork', 5, 'intermediate'),
            ('Problem Solving', 'Analytical and problem-solving skills', 5, 'advanced'),
            ('Leadership', 'Leadership and management skills', 5, 'advanced'),
            ('Time Management', 'Time management and organization', 5, 'intermediate'),
            ('Adaptability', 'Adaptability to change', 5, 'intermediate'),
            
            # Project Management
            ('Agile/Scrum', 'Agile and Scrum methodologies', 6, 'intermediate'),
            ('Project Planning', 'Project planning and estimation', 6, 'intermediate'),
            ('Risk Management', 'Risk identification and management', 6, 'advanced'),
            ('Stakeholder Management', 'Stakeholder communication and management', 6, 'intermediate')
        ]
        
        skills = []
        for name, description, category_id, difficulty in skills_data:
            skill = Skill(
                name=name,
                description=description,
                category_id=category_id,
                difficulty_level=difficulty,
                is_active=True
            )
            skills.append(skill)
            db.session.add(skill)
        db.session.commit()
        
        # Создание пользователей
        print("Creating users...")
        
        # Администратор
        admin = User(
            username='admin',
            email='admin@company.com',
            password_hash=hash_password('admin123'),
            first_name='Admin',
            last_name='System',
            position='System Administrator',
            role='admin',
            is_active=True,
            is_verified=True,
            department_id=departments[0].id,
            phone='+1234567890'
        )
        db.session.add(admin)
        
        # Менеджеры
        managers = [
            User(
                username='it_manager',
                email='it.manager@company.com',
                password_hash=hash_password('manager123'),
                first_name='John',
                last_name='Smith',
                position='IT Manager',
                role='manager',
                is_active=True,
                is_verified=True,
                department_id=departments[0].id,
                phone='+1234567891'
            ),
            User(
                username='hr_manager',
                email='hr.manager@company.com',
                password_hash=hash_password('manager123'),
                first_name='Sarah',
                last_name='Johnson',
                position='HR Manager',
                role='manager',
                is_active=True,
                is_verified=True,
                department_id=departments[1].id,
                phone='+1234567892'
            ),
            User(
                username='sales_manager',
                email='sales.manager@company.com',
                password_hash=hash_password('manager123'),
                first_name='Michael',
                last_name='Brown',
                position='Sales Manager',
                role='manager',
                is_active=True,
                is_verified=True,
                department_id=departments[2].id,
                phone='+1234567893'
            )
        ]
        
        for manager in managers:
            db.session.add(manager)
        
        # Назначение менеджеров отделам
        departments[0].manager_id = managers[0].id
        departments[1].manager_id = managers[1].id
        departments[2].manager_id = managers[2].id
        
        # Сотрудники
        first_names = ['Alex', 'Maria', 'David', 'Emma', 'James', 'Sophia', 'Robert', 'Olivia', 'William', 'Ava']
        last_names = ['Taylor', 'Wilson', 'Clark', 'Lewis', 'Walker', 'Hall', 'Allen', 'Young', 'King', 'Wright']
        positions = [
            'Software Developer', 'Senior Developer', 'DevOps Engineer', 'QA Engineer',
            'Frontend Developer', 'Backend Developer', 'Full Stack Developer',
            'HR Specialist', 'Recruiter', 'HR Manager Assistant',
            'Sales Representative', 'Account Manager', 'Sales Executive',
            'Financial Analyst', 'Accountant', 'Finance Manager'
        ]
        
        employees = []
        for i in range(30):
            dept_index = i % 5
            employee = User(
                username=f'employee{i+1}',
                email=f'employee{i+1}@company.com',
                password_hash=hash_password('employee123'),
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                position=random.choice(positions),
                role='employee',
                is_active=True,
                is_verified=True,
                department_id=departments[dept_index].id,
                manager_id=departments[dept_index].manager_id if dept_index < 3 else None,
                phone=f'+1234567{8000 + i}'
            )
            employees.append(employee)
            db.session.add(employee)
        
        db.session.commit()
        
        # Создание обязательных навыков для отделов
        print("Creating required department skills...")
        
        # IT Department обязательные навыки
        it_required_skills = [1, 2, 6, 7, 13, 16, 18]  # Python, JS, TypeScript, React, PostgreSQL, Docker, Git
        for skill_id in it_required_skills:
            req_skill = RequiredDepartmentSkill(
                department_id=departments[0].id,
                skill_id=skill_id,
                min_score=random.randint(3, 5),
                priority=random.randint(1, 3),
                is_required=True
            )
            db.session.add(req_skill)
        
        # HR Department обязательные навыки
        hr_required_skills = [25, 26, 27, 28, 29]  # Communication, Teamwork, Problem Solving, Leadership, Time Management
        for skill_id in hr_required_skills:
            req_skill = RequiredDepartmentSkill(
                department_id=departments[1].id,
                skill_id=skill_id,
                min_score=random.randint(3, 5),
                priority=random.randint(1, 3),
                is_required=True
            )
            db.session.add(req_skill)
        
        db.session.commit()
        
        # Создание оценок навыков
        print("Creating skill ratings...")
        
        for employee in employees:
            # Случайный выбор навыков для оценки
            num_skills = random.randint(5, 15)
            employee_skills = random.sample(skills, min(num_skills, len(skills)))
            
            for skill in employee_skills:
                # Определение оценки в зависимости от сложности навыка
                if skill.difficulty_level == 'beginner':
                    base_score = random.randint(3, 5)
                elif skill.difficulty_level == 'intermediate':
                    base_score = random.randint(2, 5)
                else:  # advanced или expert
                    base_score = random.randint(1, 4)
                
                # Добавление некоторой вариативности
                final_score = max(1, min(5, base_score + random.randint(-1, 1)))
                
                # Создание оценки
                rating = UserSkillRating(
                    user_id=employee.id,
                    skill_id=skill.id,
                    self_score=final_score,
                    manager_score=final_score + random.randint(-1, 1) if random.random() > 0.3 else None,
                    final_score=final_score,
                    status=random.choice(['pending', 'confirmed', 'confirmed', 'confirmed']),
                    self_assessment_date=datetime.utcnow() - timedelta(days=random.randint(1, 90)),
                    manager_assessment_date=datetime.utcnow() - timedelta(days=random.randint(1, 30)) if random.random() > 0.5 else None,
                    notes=f'Self assessment for {skill.name}',
                    manager_notes='Manager confirmed' if random.random() > 0.7 else None,
                    confirmed_by=employee.manager_id if random.random() > 0.5 and employee.manager_id else None
                )
                
                # Корректировка manager_score
                if rating.manager_score is not None:
                    rating.manager_score = max(1, min(5, rating.manager_score))
                
                db.session.add(rating)
        
        db.session.commit()
        
        print(f"Test data created successfully!")
        print(f"- Departments: {len(departments)}")
        print(f"- Categories: {len(categories)}")
        print(f"- Skills: {len(skills)}")
        print(f"- Users: {1 + len(managers) + len(employees)}")
        print(f"- Required Skills: {len(it_required_skills) + len(hr_required_skills)}")
        print(f"- Skill Ratings: {UserSkillRating.query.count()}")
        
        # Вывод информации для входа
        print("\n=== Login Information ===")
        print("Admin: username='admin', password='admin123'")
        print("IT Manager: username='it_manager', password='manager123'")
        print("HR Manager: username='hr_manager', password='manager123'")
        print("Sales Manager: username='sales_manager', password='manager123'")
        print("Employees: username='employee1' to 'employee30', password='employee123'")

if __name__ == '__main__':
    create_test_data()