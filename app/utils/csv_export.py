import csv
import io
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import class_mapper


def export_to_csv(objects, columns):
    """
    Экспорт объектов в CSV
    
    Args:
        objects: Список объектов SQLAlchemy
        columns: Список кортежей (заголовок, атрибут)
    
    Returns:
        BytesIO объект с CSV данными
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Заголовки
    headers = [col[0] for col in columns]
    writer.writerow(headers)
    
    # Данные
    for obj in objects:
        row = []
        for _, attr_path in columns:
            value = get_nested_attr(obj, attr_path)
            
            # Форматирование дат
            if isinstance(value, datetime):
                value = value.strftime('%Y-%m-%d %H:%M:%S')
            elif value is None:
                value = ''
            
            row.append(str(value))
        
        writer.writerow(row)
    
    # Возврат как BytesIO
    output.seek(0)
    return io.BytesIO(output.getvalue().encode('utf-8'))


def export_to_excel(objects, columns, sheet_name='Data'):
    """
    Экспорт объектов в Excel
    
    Args:
        objects: Список объектов SQLAlchemy
        columns: Список кортежей (заголовок, атрибут)
        sheet_name: Имя листа
    
    Returns:
        BytesIO объект с Excel данными
    """
    # Подготовка данных
    data = []
    for obj in objects:
        row = {}
        for header, attr_path in columns:
            value = get_nested_attr(obj, attr_path)
            
            # Форматирование дат
            if isinstance(value, datetime):
                value = value.strftime('%Y-%m-%d %H:%M:%S')
            
            row[header] = value
        
        data.append(row)
    
    # Создание DataFrame
    df = pd.DataFrame(data)
    
    # Создание Excel файла в памяти
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        # Автонастройка ширины столбцов
        worksheet = writer.sheets[sheet_name]
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    return output


def get_nested_attr(obj, attr_path):
    """
    Получение вложенного атрибута по пути
    
    Args:
        obj: Объект
        attr_path: Путь к атрибуту (например, 'user.department.name')
    
    Returns:
        Значение атрибута или None
    """
    if not attr_path:
        return None
    
    parts = attr_path.split('.')
    current = obj
    
    for part in parts:
        if current is None:
            return None
        
        if hasattr(current, part):
            current = getattr(current, part)
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    
    return current


def export_department_report(department_id):
    """
    Экспорт отчета по отделу
    
    Args:
        department_id: ID отдела
    
    Returns:
        DataFrame с отчетом
    """
    from ..models import db, Department, User, Skill, UserSkillRating, SkillCategory
    
    # Получение данных отдела
    department = Department.query.get(department_id)
    if not department:
        raise ValueError('Department not found')
    
    # Получение сотрудников отдела
    employees = User.query.filter_by(
        department_id=department_id,
        is_active=True,
        role='employee'
    ).all()
    
    # Подготовка данных для отчета
    report_data = []
    
    for employee in employees:
        # Получение оценок сотрудника
        ratings = UserSkillRating.query.filter_by(user_id=employee.id).all()
        
        for rating in ratings:
            skill = rating.skill
            if not skill:
                continue
            
            report_data.append({
                'Employee ID': employee.id,
                'Employee Name': employee.full_name,
                'Position': employee.position,
                'Skill ID': skill.id,
                'Skill Name': skill.name,
                'Category': skill.category.name if skill.category else '',
                'Self Score': rating.self_score,
                'Manager Score': rating.manager_score,
                'Final Score': rating.final_score,
                'Status': rating.status,
                'Last Updated': rating.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                'Department': department.name
            })
    
    # Создание DataFrame
    df = pd.DataFrame(report_data)
    
    # Добавление сводной статистики
    if not df.empty:
        # Статистика по категориям
        category_stats = df.groupby('Category').agg({
            'Final Score': 'mean',
            'Skill ID': 'count'
        }).round(2).reset_index()
        category_stats.columns = ['Category', 'Average Score', 'Skill Count']
        
        # Статистика по сотрудникам
        employee_stats = df.groupby('Employee Name').agg({
            'Final Score': 'mean',
            'Skill ID': 'count'
        }).round(2).reset_index()
        employee_stats.columns = ['Employee', 'Average Score', 'Skill Count']
        
        return {
            'detailed': df,
            'category_stats': category_stats,
            'employee_stats': employee_stats,
            'department': department.name,
            'employee_count': len(employees),
            'total_skills': len(df['Skill ID'].unique()),
            'average_score': df['Final Score'].mean().round(2)
        }
    
    return None


def generate_comprehensive_report():
    """
    Генерация комплексного отчета по всей системе
    
    Returns:
        Dict с различными отчетами
    """
    from ..models import db, User, Department, Skill, UserSkillRating
    
    reports = {}
    
    # 1. Отчет по пользователям
    users = User.query.all()
    user_data = [{
        'ID': u.id,
        'Username': u.username,
        'Email': u.email,
        'Full Name': u.full_name,
        'Role': u.role,
        'Department': u.department.name if u.department else '',
        'Active': u.is_active,
        'Last Login': u.last_login.strftime('%Y-%m-%d %H:%M:%S') if u.last_login else ''
    } for u in users]
    
    reports['users'] = pd.DataFrame(user_data)
    
    # 2. Отчет по навыкам
    skills = Skill.query.filter_by(is_active=True).all()
    skill_data = []
    
    for skill in skills:
        ratings = UserSkillRating.query.filter_by(skill_id=skill.id).all()
        
        if ratings:
            avg_score = sum(r.effective_score for r in ratings) / len(ratings)
        else:
            avg_score = 0
        
        skill_data.append({
            'ID': skill.id,
            'Name': skill.name,
            'Category': skill.category.name if skill.category else '',
            'Description': skill.description,
            'Difficulty': skill.difficulty_level,
            'Rating Count': len(ratings),
            'Average Score': round(avg_score, 2),
            'Active': skill.is_active
        })
    
    reports['skills'] = pd.DataFrame(skill_data)
    
    # 3. Отчет по отделам
    departments = Department.query.all()
    dept_data = []
    
    for dept in departments:
        employees = dept.employees.filter_by(is_active=True, role='employee').all()
        employee_count = len(employees)
        
        if employee_count > 0:
            employee_ids = [e.id for e in employees]
            ratings = UserSkillRating.query.filter(
                UserSkillRating.user_id.in_(employee_ids)
            ).all()
            
            if ratings:
                avg_score = sum(r.effective_score for r in ratings) / len(ratings)
            else:
                avg_score = 0
        else:
            avg_score = 0
        
        dept_data.append({
            'ID': dept.id,
            'Name': dept.name,
            'Code': dept.code,
            'Description': dept.description,
            'Manager': dept.manager.full_name if dept.manager else '',
            'Employee Count': employee_count,
            'Average Score': round(avg_score, 2)
        })
    
    reports['departments'] = pd.DataFrame(dept_data)
    
    # 4. Детальный отчет по оценкам
    all_ratings = UserSkillRating.query.all()
    rating_data = [{
        'ID': r.id,
        'User ID': r.user_id,
        'User Name': r.user.full_name if r.user else '',
        'Skill ID': r.skill_id,
        'Skill Name': r.skill.name if r.skill else '',
        'Self Score': r.self_score,
        'Manager Score': r.manager_score,
        'Final Score': r.final_score,
        'Status': r.status,
        'Self Assessment Date': r.self_assessment_date.strftime('%Y-%m-%d %H:%M:%S') if r.self_assessment_date else '',
        'Manager Assessment Date': r.manager_assessment_date.strftime('%Y-%m-%d %H:%M:%S') if r.manager_assessment_date else '',
        'Confirmed By': r.confirmed_by_user.full_name if r.confirmed_by_user else '',
        'Created': r.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'Updated': r.updated_at.strftime('%Y-%m-%d %H:%M:%S')
    } for r in all_ratings]
    
    reports['ratings'] = pd.DataFrame(rating_data)
    
    return reports
