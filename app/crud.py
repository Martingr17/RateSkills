"""
CRUD operations for SkillMatrix application
"""
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, asc, and_, or_, case
import logging

from app import models, schemas
from app.utils import paginate_query

logger = logging.getLogger(__name__)

# ========== User CRUD Operations ==========

def get_user(db: Session, user_id: int) -> Optional[models.User]:
    """Get user by ID"""
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_login(db: Session, login: str) -> Optional[models.User]:
    """Get user by login"""
    return db.query(models.User).filter(models.User.login == login).first()

def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    """Get user by email"""
    return db.query(models.User).filter(models.User.email == email).first()

def get_users(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    department_id: Optional[int] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None
) -> List[models.User]:
    """Get list of users with filtering"""
    query = db.query(models.User)
    
    if department_id:
        query = query.filter(models.User.department_id == department_id)
    
    if role:
        query = query.filter(models.User.role == role)
    
    if is_active is not None:
        query = query.filter(models.User.is_active == is_active)
    
    return query.offset(skip).limit(limit).all()

def create_user(db: Session, user_data: schemas.UserCreate) -> models.User:
    """Create new user"""
    from app.utils import generate_avatar_initials
    
    # Generate avatar initials
    avatar = generate_avatar_initials(user_data.full_name)
    
    db_user = models.User(
        login=user_data.login,
        email=user_data.email,
        full_name=user_data.full_name,
        avatar=avatar,
        department_id=user_data.department_id,
        position=user_data.position,
        role=user_data.role,
        phone=user_data.phone,
        hire_date=user_data.hire_date,
        salary=user_data.salary,
        bio=user_data.bio,
        is_active=True,
        created_at=datetime.utcnow()
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(
    db: Session,
    user_id: int,
    update_data: Dict[str, Any]
) -> Optional[models.User]:
    """Update user"""
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    from app.utils import generate_avatar_initials
    
    # If name changed, update avatar
    if 'full_name' in update_data and update_data['full_name'] != db_user.full_name:
        avatar = generate_avatar_initials(update_data['full_name'])
        update_data['avatar'] = avatar
    
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    db_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_user)
    return db_user

def delete_user(db: Session, user_id: int) -> bool:
    """Soft delete user (deactivate)"""
    db_user = get_user(db, user_id)
    if not db_user:
        return False
    
    db_user.is_active = False
    db_user.deactivated_at = datetime.utcnow()
    db.commit()
    return True

def change_user_password(db: Session, user_id: int, new_password_hash: str) -> bool:
    """Change user password"""
    db_user = get_user(db, user_id)
    if not db_user:
        return False
    
    db_user.password_hash = new_password_hash
    db_user.updated_at = datetime.utcnow()
    db.commit()
    return True

# ========== Department CRUD Operations ==========

def get_department(db: Session, department_id: int) -> Optional[models.Department]:
    """Get department by ID"""
    return db.query(models.Department).filter(models.Department.id == department_id).first()

def get_departments(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    manager_id: Optional[int] = None
) -> List[models.Department]:
    """Get list of departments"""
    query = db.query(models.Department)
    
    if manager_id:
        query = query.filter(models.Department.manager_id == manager_id)
    
    return query.offset(skip).limit(limit).all()

def create_department(
    db: Session,
    department_data: schemas.DepartmentCreate
) -> models.Department:
    """Create new department"""
    db_department = models.Department(**department_data.dict())
    db.add(db_department)
    db.commit()
    db.refresh(db_department)
    return db_department

def update_department(
    db: Session,
    department_id: int,
    update_data: Dict[str, Any]
) -> Optional[models.Department]:
    """Update department"""
    db_department = get_department(db, department_id)
    if not db_department:
        return None
    
    for field, value in update_data.items():
        setattr(db_department, field, value)
    
    db_department.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_department)
    return db_department

def delete_department(db: Session, department_id: int) -> bool:
    """Delete department"""
    db_department = get_department(db, department_id)
    if not db_department:
        return False
    
    db.delete(db_department)
    db.commit()
    return True

# ========== Skill Category CRUD Operations ==========

def get_skill_category(db: Session, category_id: int) -> Optional[models.SkillCategory]:
    """Get skill category by ID"""
    return db.query(models.SkillCategory).filter(models.SkillCategory.id == category_id).first()

def get_skill_categories(
    db: Session,
    skip: int = 0,
    limit: int = 100
) -> List[models.SkillCategory]:
    """Get list of skill categories"""
    return db.query(models.SkillCategory).offset(skip).limit(limit).all()

def create_skill_category(
    db: Session,
    category_data: schemas.SkillCategoryCreate
) -> models.SkillCategory:
    """Create new skill category"""
    db_category = models.SkillCategory(**category_data.dict())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

def update_skill_category(
    db: Session,
    category_id: int,
    update_data: Dict[str, Any]
) -> Optional[models.SkillCategory]:
    """Update skill category"""
    db_category = get_skill_category(db, category_id)
    if not db_category:
        return None
    
    for field, value in update_data.items():
        setattr(db_category, field, value)
    
    db.commit()
    db.refresh(db_category)
    return db_category

def delete_skill_category(db: Session, category_id: int) -> bool:
    """Delete skill category"""
    db_category = get_skill_category(db, category_id)
    if not db_category:
        return False
    
    # Check if category has skills
    skill_count = db.query(models.Skill).filter(
        models.Skill.category_id == category_id
    ).count()
    
    if skill_count > 0:
        raise ValueError(f"Cannot delete category with {skill_count} skills")
    
    db.delete(db_category)
    db.commit()
    return True

# ========== Skill CRUD Operations ==========

def get_skill(db: Session, skill_id: int) -> Optional[models.Skill]:
    """Get skill by ID"""
    return db.query(models.Skill).filter(models.Skill.id == skill_id).first()

def get_skills(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    category_id: Optional[int] = None,
    department_id: Optional[int] = None
) -> List[models.Skill]:
    """Get list of skills with filtering"""
    query = db.query(models.Skill)
    
    if category_id:
        query = query.filter(models.Skill.category_id == category_id)
    
    if department_id:
        query = query.filter(
            models.Skill.required_for_departments.any(id=department_id)
        )
    
    return query.offset(skip).limit(limit).all()

def create_skill(db: Session, skill_data: schemas.SkillCreate) -> models.Skill:
    """Create new skill"""
    db_skill = models.Skill(**skill_data.dict())
    db.add(db_skill)
    db.commit()
    db.refresh(db_skill)
    return db_skill

def update_skill(
    db: Session,
    skill_id: int,
    update_data: Dict[str, Any]
) -> Optional[models.Skill]:
    """Update skill"""
    db_skill = get_skill(db, skill_id)
    if not db_skill:
        return None
    
    # Handle many-to-many relationship for required departments
    if 'required_for_departments' in update_data:
        # Get department objects
        departments = db.query(models.Department).filter(
            models.Department.id.in_(update_data['required_for_departments'])
        ).all()
        
        if len(departments) != len(update_data['required_for_departments']):
            raise ValueError("One or more departments not found")
        
        update_data['required_for_departments'] = departments
    
    for field, value in update_data.items():
        setattr(db_skill, field, value)
    
    db.commit()
    db.refresh(db_skill)
    return db_skill

def delete_skill(db: Session, skill_id: int) -> bool:
    """Delete skill"""
    db_skill = get_skill(db, skill_id)
    if not db_skill:
        return False
    
    # Check if skill has assessments
    assessment_count = db.query(models.SkillAssessment).filter(
        models.SkillAssessment.skill_id == skill_id
    ).count()
    
    if assessment_count > 0:
        raise ValueError(f"Cannot delete skill with {assessment_count} assessments")
    
    db.delete(db_skill)
    db.commit()
    return True

# ========== Skill Assessment CRUD Operations ==========

def get_skill_assessment(
    db: Session,
    assessment_id: int
) -> Optional[models.SkillAssessment]:
    """Get skill assessment by ID"""
    return db.query(models.SkillAssessment).filter(
        models.SkillAssessment.id == assessment_id
    ).first()

def get_user_assessments(
    db: Session,
    user_id: int,
    skill_id: Optional[int] = None,
    status: Optional[str] = None
) -> List[models.SkillAssessment]:
    """Get skill assessments for user"""
    query = db.query(models.SkillAssessment).filter(
        models.SkillAssessment.user_id == user_id
    )
    
    if skill_id:
        query = query.filter(models.SkillAssessment.skill_id == skill_id)
    
    if status:
        query = query.filter(models.SkillAssessment.status == status)
    
    return query.order_by(desc(models.SkillAssessment.assessed_at)).all()

def create_skill_assessment(
    db: Session,
    assessment_data: schemas.SkillAssessmentCreate
) -> models.SkillAssessment:
    """Create new skill assessment"""
    db_assessment = models.SkillAssessment(
        **assessment_data.dict(),
        assessed_at=datetime.utcnow()
    )
    
    db.add(db_assessment)
    db.commit()
    db.refresh(db_assessment)
    
    # Create history entry
    history = models.AssessmentHistory(
        assessment_id=db_assessment.id,
        old_score=None,
        new_score=assessment_data.self_score,
        changed_by_id=assessment_data.user_id,
        change_type="created",
        comment="Initial self-assessment"
    )
    
    db.add(history)
    db.commit()
    
    return db_assessment

def update_skill_assessment(
    db: Session,
    assessment_id: int,
    update_data: Dict[str, Any],
    changed_by_id: int
) -> Optional[models.SkillAssessment]:
    """Update skill assessment and create history entry"""
    db_assessment = get_skill_assessment(db, assessment_id)
    if not db_assessment:
        return None
    
    old_score = db_assessment.self_score
    
    # Create history entry if score changed
    if 'self_score' in update_data and update_data['self_score'] != old_score:
        history = models.AssessmentHistory(
            assessment_id=assessment_id,
            old_score=old_score,
            new_score=update_data['self_score'],
            changed_by_id=changed_by_id,
            change_type="update",
            comment=update_data.get('comment', '')
        )
        db.add(history)
    
    for field, value in update_data.items():
        setattr(db_assessment, field, value)
    
    db_assessment.assessed_at = datetime.utcnow()
    db.commit()
    db.refresh(db_assessment)
    
    return db_assessment

def approve_assessment(
    db: Session,
    assessment_id: int,
    manager_id: int,
    comment: Optional[str] = None
) -> Optional[models.SkillAssessment]:
    """Approve skill assessment"""
    db_assessment = get_skill_assessment(db, assessment_id)
    if not db_assessment:
        return None
    
    # Create history entry
    history = models.AssessmentHistory(
        assessment_id=assessment_id,
        old_score=db_assessment.self_score,
        new_score=db_assessment.self_score,
        changed_by_id=manager_id,
        change_type="approved",
        comment=comment or "Approved by manager"
    )
    
    db_assessment.status = "approved"
    db_assessment.manager_score = db_assessment.self_score
    db_assessment.approved_by_id = manager_id
    db_assessment.approved_at = datetime.utcnow()
    
    db.add(history)
    db.commit()
    db.refresh(db_assessment)
    
    return db_assessment

def reject_assessment(
    db: Session,
    assessment_id: int,
    manager_id: int,
    reason: str
) -> Optional[models.SkillAssessment]:
    """Reject skill assessment"""
    db_assessment = get_skill_assessment(db, assessment_id)
    if not db_assessment:
        return None
    
    # Create history entry
    history = models.AssessmentHistory(
        assessment_id=assessment_id,
        old_score=db_assessment.self_score,
        new_score=db_assessment.self_score,
        changed_by_id=manager_id,
        change_type="rejected",
        comment=f"Rejected: {reason}"
    )
    
    db_assessment.status = "rejected"
    db_assessment.reject_reason = reason
    
    db.add(history)
    db.commit()
    db.refresh(db_assessment)
    
    return db_assessment

def delete_skill_assessment(db: Session, assessment_id: int) -> bool:
    """Delete skill assessment"""
    db_assessment = get_skill_assessment(db, assessment_id)
    if not db_assessment:
        return False
    
    # Delete history first
    db.query(models.AssessmentHistory).filter(
        models.AssessmentHistory.assessment_id == assessment_id
    ).delete()
    
    db.delete(db_assessment)
    db.commit()
    return True

# ========== Goal CRUD Operations ==========

def get_goal(db: Session, goal_id: int) -> Optional[models.Goal]:
    """Get goal by ID"""
    return db.query(models.Goal).filter(models.Goal.id == goal_id).first()

def get_user_goals(
    db: Session,
    user_id: int,
    status: Optional[str] = None,
    priority: Optional[str] = None
) -> List[models.Goal]:
    """Get goals for user"""
    query = db.query(models.Goal).filter(models.Goal.user_id == user_id)
    
    if status:
        query = query.filter(models.Goal.status == status)
    
    if priority:
        query = query.filter(models.Goal.priority == priority)
    
    return query.order_by(
        case(
            (models.Goal.priority == "high", 1),
            (models.Goal.priority == "medium", 2),
            (models.Goal.priority == "low", 3),
            else_=4
        ),
        models.Goal.deadline
    ).all()

def create_goal(db: Session, goal_data: schemas.GoalCreate) -> models.Goal:
    """Create new goal"""
    db_goal = models.Goal(**goal_data.dict())
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    return db_goal

def update_goal(
    db: Session,
    goal_id: int,
    update_data: Dict[str, Any]
) -> Optional[models.Goal]:
    """Update goal"""
    db_goal = get_goal(db, goal_id)
    if not db_goal:
        return None
    
    for field, value in update_data.items():
        setattr(db_goal, field, value)
    
    # If progress is 100%, mark as completed
    if 'progress_percentage' in update_data and update_data['progress_percentage'] == 100:
        db_goal.status = "completed"
        db_goal.completed_at = datetime.utcnow()
    
    db_goal.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_goal)
    return db_goal

def delete_goal(db: Session, goal_id: int) -> bool:
    """Delete goal"""
    db_goal = get_goal(db, goal_id)
    if not db_goal:
        return False
    
    db.delete(db_goal)
    db.commit()
    return True

# ========== Notification CRUD Operations ==========

def get_notification(db: Session, notification_id: int) -> Optional[models.Notification]:
    """Get notification by ID"""
    return db.query(models.Notification).filter(models.Notification.id == notification_id).first()

def get_user_notifications(
    db: Session,
    user_id: int,
    unread_only: bool = False,
    limit: int = 50
) -> List[models.Notification]:
    """Get notifications for user"""
    query = db.query(models.Notification).filter(
        models.Notification.user_id == user_id
    )
    
    if unread_only:
        query = query.filter(models.Notification.is_read == False)
    
    return query.order_by(desc(models.Notification.created_at)).limit(limit).all()

def create_notification(
    db: Session,
    notification_data: schemas.NotificationCreate
) -> models.Notification:
    """Create new notification"""
    db_notification = models.Notification(**notification_data.dict())
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    return db_notification

def mark_notification_read(db: Session, notification_id: int) -> bool:
    """Mark notification as read"""
    db_notification = get_notification(db, notification_id)
    if not db_notification:
        return False
    
    db_notification.is_read = True
    db_notification.read_at = datetime.utcnow()
    db.commit()
    return True

def mark_all_notifications_read(db: Session, user_id: int) -> bool:
    """Mark all user notifications as read"""
    db.query(models.Notification).filter(
        models.Notification.user_id == user_id,
        models.Notification.is_read == False
    ).update({
        "is_read": True,
        "read_at": datetime.utcnow()
    })
    
    db.commit()
    return True

def delete_notification(db: Session, notification_id: int) -> bool:
    """Delete notification"""
    db_notification = get_notification(db, notification_id)
    if not db_notification:
        return False
    
    db.delete(db_notification)
    db.commit()
    return True

# ========== Statistics and Reporting ==========

def get_user_stats(db: Session, user_id: int) -> Dict[str, Any]:
    """Get comprehensive statistics for user"""
    from sqlalchemy import func
    
    # Get assessments
    assessments = db.query(models.SkillAssessment).filter(
        models.SkillAssessment.user_id == user_id
    ).all()
    
    approved_assessments = [a for a in assessments if a.status == 'approved']
    pending_assessments = [a for a in assessments if a.status == 'pending']
    
    # Calculate average score
    avg_score = 0
    if approved_assessments:
        avg_score = sum(a.self_score for a in approved_assessments) / len(approved_assessments)
    
    # Get goals
    goals = db.query(models.Goal).filter(models.Goal.user_id == user_id).all()
    completed_goals = sum(1 for g in goals if g.status == 'completed')
    
    # Get required skills for user's department
    user = get_user(db, user_id)
    required_skills = db.query(models.Skill).filter(
        models.Skill.required_for_departments.any(id=user.department_id)
    ).count() if user else 0
    
    # Get approved required skills
    approved_required = 0
    for a in approved_assessments:
        skill = get_skill(db, a.skill_id)
        if skill and user and user.department_id in [d.id for d in skill.required_for_departments]:
            approved_required += 1
    
    return {
        "user_id": user_id,
        "total_assessments": len(assessments),
        "approved_assessments": len(approved_assessments),
        "pending_assessments": len(pending_assessments),
        "average_score": round(avg_score, 2),
        "total_goals": len(goals),
        "completed_goals": completed_goals,
        "required_skills": required_skills,
        "approved_required_skills": approved_required,
        "completion_rate": round((approved_required / required_skills * 100) if required_skills > 0 else 0, 1)
    }

def get_department_stats(db: Session, department_id: int) -> Dict[str, Any]:
    """Get comprehensive statistics for department"""
    from sqlalchemy import func
    
    # Get department users
    users = db.query(models.User).filter(
        models.User.department_id == department_id,
        models.User.is_active == True
    ).all()
    
    total_users = len(users)
    
    # Get department assessments
    assessments = db.query(models.SkillAssessment).join(models.User).filter(
        models.User.department_id == department_id
    ).all()
    
    total_assessments = len(assessments)
    approved_assessments = [a for a in assessments if a.status == 'approved']
    
    # Calculate average score
    avg_score = 0
    if approved_assessments:
        avg_score = sum(a.self_score for a in approved_assessments) / len(approved_assessments)
    
    # Get required skills for department
    required_skills = db.query(models.Skill).filter(
        models.Skill.required_for_departments.any(id=department_id)
    ).count()
    
    # Calculate skill coverage
    covered_skills = set()
    for a in approved_assessments:
        skill = get_skill(db, a.skill_id)
        if skill and department_id in [d.id for d in skill.required_for_departments]:
            covered_skills.add(skill.id)
    
    skill_coverage = len(covered_skills) / required_skills * 100 if required_skills > 0 else 0
    
    # Get pending assessments
    pending_assessments = len([a for a in assessments if a.status == 'pending'])
    
    return {
        "department_id": department_id,
        "total_users": total_users,
        "total_assessments": total_assessments,
        "approved_assessments": len(approved_assessments),
        "pending_assessments": pending_assessments,
        "average_score": round(avg_score, 2),
        "required_skills": required_skills,
        "covered_skills": len(covered_skills),
        "skill_coverage": round(skill_coverage, 1)
    }

def get_skill_stats(db: Session, skill_id: int) -> Dict[str, Any]:
    """Get statistics for skill"""
    from sqlalchemy import func
    
    # Get assessments for this skill
    assessments = db.query(models.SkillAssessment).filter(
        models.SkillAssessment.skill_id == skill_id
    ).all()
    
    total_assessments = len(assessments)
    approved_assessments = [a for a in assessments if a.status == 'approved']
    
    # Calculate average score
    avg_score = 0
    if approved_assessments:
        avg_score = sum(a.self_score for a in approved_assessments) / len(approved_assessments)
    
    # Score distribution
    score_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for a in approved_assessments:
        score_distribution[a.self_score] += 1
    
    # Get departments that require this skill
    skill = get_skill(db, skill_id)
    requiring_departments = [d.name for d in skill.required_for_departments] if skill else []
    
    return {
        "skill_id": skill_id,
        "total_assessments": total_assessments,
        "approved_assessments": len(approved_assessments),
        "average_score": round(avg_score, 2),
        "score_distribution": score_distribution,
        "requiring_departments": requiring_departments
    }

def get_company_stats(db: Session) -> Dict[str, Any]:
    """Get company-wide statistics"""
    from sqlalchemy import func
    
    # Basic counts
    total_users = db.query(models.User).filter(models.User.is_active == True).count()
    total_departments = db.query(models.Department).count()
    total_skills = db.query(models.Skill).count()
    total_assessments = db.query(models.SkillAssessment).count()
    
    # Assessment status counts
    pending_assessments = db.query(models.SkillAssessment).filter(
        models.SkillAssessment.status == 'pending'
    ).count()
    
    approved_assessments = db.query(models.SkillAssessment).filter(
        models.SkillAssessment.status == 'approved'
    ).count()
    
    # Average score
    avg_score_result = db.query(func.avg(models.SkillAssessment.self_score)).filter(
        models.SkillAssessment.status == 'approved'
    ).scalar()
    
    avg_score = float(avg_score_result) if avg_score_result else 0
    
    # Recent activity (last 30 days)
    month_ago = datetime.utcnow() - timedelta(days=30)
    recent_users = db.query(models.User).filter(
        models.User.created_at >= month_ago
    ).count()
    
    recent_assessments = db.query(models.SkillAssessment).filter(
        models.SkillAssessment.assessed_at >= month_ago
    ).count()
    
    return {
        "total_users": total_users,
        "total_departments": total_departments,
        "total_skills": total_skills,
        "total_assessments": total_assessments,
        "pending_assessments": pending_assessments,
        "approved_assessments": approved_assessments,
        "average_score": round(avg_score, 2),
        "recent_users": recent_users,
        "recent_assessments": recent_assessments
    }

# ========== Search Operations ==========

def search_users(
    db: Session,
    query: str,
    department_id: Optional[int] = None,
    role: Optional[str] = None,
    limit: int = 20
) -> List[models.User]:
    """Search users by name, email, or position"""
    from sqlalchemy import or_
    
    search_term = f"%{query}%"
    
    q = db.query(models.User).filter(
        models.User.is_active == True,
        or_(
            models.User.full_name.ilike(search_term),
            models.User.email.ilike(search_term),
            models.User.position.ilike(search_term)
        )
    )
    
    if department_id:
        q = q.filter(models.User.department_id == department_id)
    
    if role:
        q = q.filter(models.User.role == role)
    
    return q.limit(limit).all()

def search_skills(
    db: Session,
    query: str,
    category_id: Optional[int] = None,
    limit: int = 20
) -> List[models.Skill]:
    """Search skills by name or description"""
    from sqlalchemy import or_
    
    search_term = f"%{query}%"
    
    q = db.query(models.Skill).filter(
        or_(
            models.Skill.name.ilike(search_term),
            models.Skill.description.ilike(search_term)
        )
    )
    
    if category_id:
        q = q.filter(models.Skill.category_id == category_id)
    
    return q.limit(limit).all()

def find_users_by_skill(
    db: Session,
    skill_id: int,
    min_score: int = 3,
    department_id: Optional[int] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Find users who have a specific skill at minimum level"""
    from sqlalchemy import func
    
    # Get assessments for this skill
    q = db.query(models.SkillAssessment).filter(
        models.SkillAssessment.skill_id == skill_id,
        models.SkillAssessment.self_score >= min_score,
        models.SkillAssessment.status == 'approved'
    )
    
    if department_id:
        q = q.join(models.User).filter(models.User.department_id == department_id)
    
    assessments = q.all()
    
    # Get user details
    result = []
    for assessment in assessments:
        user = get_user(db, assessment.user_id)
        if user:
            # Get user's average score for all skills
            user_assessments = db.query(models.SkillAssessment).filter(
                models.SkillAssessment.user_id == user.id,
                models.SkillAssessment.status == 'approved'
            ).all()
            
            avg_score = 0
            if user_assessments:
                avg_score = sum(a.self_score for a in user_assessments) / len(user_assessments)
            
            result.append({
                "user_id": user.id,
                "full_name": user.full_name,
                "position": user.position,
                "department": user.department.name if user.department else "",
                "skill_score": assessment.self_score,
                "average_score": round(avg_score, 2),
                "assessed_at": assessment.assessed_at
            })
    
    # Sort by skill score descending
    result.sort(key=lambda x: x["skill_score"], reverse=True)
    
    return result[:limit]

# ========== Comparison Operations ==========

def compare_users(
    db: Session,
    user_ids: List[int],
    skill_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    """Compare multiple users based on their skill assessments"""
    result = {}
    
    for user_id in user_ids:
        user = get_user(db, user_id)
        if not user:
            continue
        
        # Get assessments for this user
        query = db.query(models.SkillAssessment).filter(
            models.SkillAssessment.user_id == user_id,
            models.SkillAssessment.status == 'approved'
        )
        
        if skill_ids:
            query = query.filter(models.SkillAssessment.skill_id.in_(skill_ids))
        
        assessments = query.all()
        
        # Create skill score mapping
        skill_scores = {a.skill_id: a.self_score for a in assessments}
        
        # Calculate average
        avg_score = sum(skill_scores.values()) / len(skill_scores) if skill_scores else 0
        
        result[user_id] = {
            "user": user,
            "skill_scores": skill_scores,
            "average_score": round(avg_score, 2),
            "total_skills": len(skill_scores)
        }
    
    return result

def compare_departments(
    db: Session,
    department_ids: List[int],
    skill_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    """Compare multiple departments based on skill assessments"""
    result = {}
    
    for dept_id in department_ids:
        department = get_department(db, dept_id)
        if not department:
            continue
        
        # Get assessments for this department
        query = db.query(
            models.SkillAssessment.skill_id,
            func.avg(models.SkillAssessment.self_score).label('avg_score')
        ).join(models.User).filter(
            models.User.department_id == dept_id,
            models.SkillAssessment.status == 'approved'
        )
        
        if skill_ids:
            query = query.filter(models.SkillAssessment.skill_id.in_(skill_ids))
        
        department_scores = query.group_by(models.SkillAssessment.skill_id).all()
        
        # Create skill score mapping
        skill_scores = {row.skill_id: round(row.avg_score, 2) for row in department_scores}
        
        # Calculate average
        avg_score = sum(skill_scores.values()) / len(skill_scores) if skill_scores else 0
        
        result[dept_id] = {
            "department": department,
            "skill_scores": skill_scores,
            "average_score": round(avg_score, 2),
            "total_skills": len(skill_scores)
        }
    
    return result

# ========== Import/Export Operations ==========

def export_user_data(db: Session, user_id: int) -> Dict[str, Any]:
    """Export all data for a user"""
    user = get_user(db, user_id)
    if not user:
        return {}
    
    # Get user assessments with skill details
    assessments = db.query(models.SkillAssessment).options(
        joinedload(models.SkillAssessment.skill).joinedload(models.Skill.category)
    ).filter(models.SkillAssessment.user_id == user_id).all()
    
    # Get user goals
    goals = get_user_goals(db, user_id)
    
    # Get user notifications
    notifications = get_user_notifications(db, user_id, limit=100)
    
    # Get feedback received
    feedback = db.query(models.Feedback).options(
        joinedload(models.Feedback.from_user),
        joinedload(models.Feedback.skill)
    ).filter(models.Feedback.to_user_id == user_id).all()
    
    return {
        "user": {
            "id": user.id,
            "login": user.login,
            "email": user.email,
            "full_name": user.full_name,
            "position": user.position,
            "department": user.department.name if user.department else "",
            "role": user.role,
            "hire_date": user.hire_date.isoformat() if user.hire_date else None,
            "phone": user.phone,
            "bio": user.bio,
            "created_at": user.created_at.isoformat() if user.created_at else None
        },
        "assessments": [
            {
                "skill": a.skill.name,
                "category": a.skill.category.name if a.skill.category else "",
                "self_score": a.self_score,
                "manager_score": a.manager_score,
                "status": a.status,
                "comment": a.comment,
                "assessed_at": a.assessed_at.isoformat() if a.assessed_at else None,
                "approved_at": a.approved_at.isoformat() if a.approved_at else None
            }
            for a in assessments
        ],
        "goals": [
            {
                "title": g.title,
                "description": g.description,
                "status": g.status,
                "priority": g.priority,
                "progress_percentage": g.progress_percentage,
                "deadline": g.deadline.isoformat() if g.deadline else None,
                "created_at": g.created_at.isoformat() if g.created_at else None
            }
            for g in goals
        ],
        "statistics": get_user_stats(db, user_id),
        "exported_at": datetime.utcnow().isoformat()
    }

def export_department_data(db: Session, department_id: int) -> Dict[str, Any]:
    """Export all data for a department"""
    department = get_department(db, department_id)
    if not department:
        return {}
    
    # Get department users
    users = db.query(models.User).filter(
        models.User.department_id == department_id,
        models.User.is_active == True
    ).all()
    
    # Get department statistics
    stats = get_department_stats(db, department_id)
    
    # Get required skills for department
    required_skills = db.query(models.Skill).filter(
        models.Skill.required_for_departments.any(id=department_id)
    ).all()
    
    # Get skill coverage
    skill_coverage = []
    for skill in required_skills:
        # Get users with this skill
        assessments = db.query(models.SkillAssessment).filter(
            models.SkillAssessment.skill_id == skill.id,
            models.SkillAssessment.status == 'approved'
        ).join(models.User).filter(models.User.department_id == department_id).all()
        
        avg_score = 0
        if assessments:
            avg_score = sum(a.self_score for a in assessments) / len(assessments)
        
        skill_coverage.append({
            "skill": skill.name,
            "category": skill.category.name if skill.category else "",
            "users_assessed": len(assessments),
            "average_score": round(avg_score, 2),
            "required_level": skill.difficulty_level
        })
    
    return {
        "department": {
            "id": department.id,
            "name": department.name,
            "description": department.description,
            "manager": department.manager.full_name if department.manager else "",
            "created_at": department.created_at.isoformat() if department.created_at else None
        },
        "users": [
            {
                "id": u.id,
                "full_name": u.full_name,
                "position": u.position,
                "email": u.email,
                "hire_date": u.hire_date.isoformat() if u.hire_date else None
            }
            for u in users
        ],
        "statistics": stats,
        "required_skills": [
            {
                "skill": s.name,
                "category": s.category.name if s.category else "",
                "description": s.description,
                "difficulty_level": s.difficulty_level
            }
            for s in required_skills
        ],
        "skill_coverage": skill_coverage,
        "exported_at": datetime.utcnow().isoformat()
    }