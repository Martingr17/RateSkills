from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
import logging

from app.database import get_db
from app.models import User, Department, SkillAssessment, Goal, Notification
from app.schemas import (
    UserCreate, UserResponse, UserUpdate, UserStats, 
    DepartmentStats, UserWithStats, PaginatedResponse
)
from app.api.endpoints.auth import get_current_active_user, check_admin_permission
from app.utils import Pagination
router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger(__name__)

@router.get("/", response_model=PaginatedResponse[UserResponse])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    department_id: Optional[int] = None,
    role: Optional[str] = None,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_permission)
):
    """Get list of users with pagination and filtering (Admin/HR only)"""
    query = db.query(User)
    
    # Apply filters
    if department_id:
        query = query.filter(User.department_id == department_id)
    
    if role:
        query = query.filter(User.role == role)
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                User.full_name.ilike(search_term),
                User.email.ilike(search_term),
                User.login.ilike(search_term),
                User.position.ilike(search_term)
            )
        )
    
    return paginate_query(query, skip, limit)

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get user by ID"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check permissions (users can see their own profile, managers can see team members)
    if (current_user.id != user_id and 
        current_user.role not in ['admin', 'hr', 'manager', 'director'] and
        current_user.department_id != user.department_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view this user"
        )
    
    return user

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_permission)
):
    """Update user (Admin/HR only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if trying to delete own account
    if user_id == current_user.id and user_update.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    # Update fields
    update_data = user_update.dict(exclude_unset=True)
    
    # If name changed, update avatar
    if 'full_name' in update_data and update_data['full_name'] != user.full_name:
        avatar = ''.join([name[0].upper() for name in update_data['full_name'].split()[:2]])
        update_data['avatar'] = avatar
    
    # Remove password field if present
    update_data.pop('password', None)
    
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    return user

@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_permission)
):
    """Delete user (Admin only)"""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # In production, we might want to soft delete
    # For now, we'll just deactivate
    user.is_active = False
    db.commit()
    
    return {"message": "User deactivated successfully"}

@router.get("/{user_id}/stats", response_model=UserStats)
async def get_user_stats(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get user statistics and skill assessments"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check permissions
    if (current_user.id != user_id and 
        current_user.role not in ['admin', 'hr', 'manager', 'director'] and
        current_user.department_id != user.department_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # Get skill assessments
    assessments = db.query(SkillAssessment).filter(
        SkillAssessment.user_id == user_id
    ).all()
    
    # Calculate stats
    approved_assessments = [a for a in assessments if a.status == 'approved']
    pending_assessments = [a for a in assessments if a.status == 'pending']
    
    total_skills = len(db.query(SkillAssessment).filter(
        SkillAssessment.user_id == user_id
    ).distinct(SkillAssessment.skill_id).all())
    
    avg_rating = 0
    if approved_assessments:
        avg_rating = sum(a.self_score for a in approved_assessments) / len(approved_assessments)
    
    # Get goals
    goals = db.query(Goal).filter(Goal.user_id == user_id).all()
    completed_goals = sum(1 for g in goals if g.status == 'completed')
    
    return UserStats(
        user_id=user_id,
        total_skills=total_skills,
        approved_skills=len(approved_assessments),
        pending_skills=len(pending_assessments),
        average_rating=round(avg_rating, 2),
        total_goals=len(goals),
        completed_goals=completed_goals,
        performance_score=user.performance_score or 0,
        last_assessment_date=max([a.assessed_at for a in assessments], default=None)
    )

@router.get("/department/{department_id}", response_model=List[UserWithStats])
async def get_department_users(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all users in a department with their stats"""
    # Check if department exists
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    # Check permissions (managers can only see their own department)
    if (current_user.role in ['employee', 'hr'] and 
        current_user.department_id != department_id and
        current_user.role not in ['admin', 'director']):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view this department"
        )
    
    users = db.query(User).filter(
        User.department_id == department_id,
        User.is_active == True
    ).all()
    
    result = []
    for user in users:
        # Get user stats
        assessments = db.query(SkillAssessment).filter(
            SkillAssessment.user_id == user.id
        ).all()
        
        approved_assessments = [a for a in assessments if a.status == 'approved']
        avg_rating = 0
        if approved_assessments:
            avg_rating = sum(a.self_score for a in approved_assessments) / len(approved_assessments)
        
        pending_assessments = len([a for a in assessments if a.status == 'pending'])
        
        result.append(UserWithStats(
            id=user.id,
            login=user.login,
            email=user.email,
            full_name=user.full_name,
            avatar=user.avatar,
            department_id=user.department_id,
            position=user.position,
            role=user.role,
            is_active=user.is_active,
            average_rating=round(avg_rating, 2),
            pending_assessments=pending_assessments,
            last_login=user.last_login
        ))
    
    return result

@router.get("/search/skills", response_model=List[UserWithStats])
async def search_users_by_skill(
    skill_id: int = Query(..., description="Skill ID to search for"),
    min_level: int = Query(3, ge=1, le=5, description="Minimum skill level"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Search users by skill and minimum level"""
    # Get users with this skill at specified level
    assessments = db.query(SkillAssessment).filter(
        SkillAssessment.skill_id == skill_id,
        SkillAssessment.self_score >= min_level,
        SkillAssessment.status == 'approved'
    ).all()
    
    user_ids = [a.user_id for a in assessments]
    
    if not user_ids:
        return []
    
    # Get users
    users = db.query(User).filter(
        User.id.in_(user_ids),
        User.is_active == True
    ).all()
    
    # Prepare response with stats
    result = []
    for user in users:
        # Get the specific assessment for this skill
        assessment = next((a for a in assessments if a.user_id == user.id), None)
        
        # Get other stats
        user_assessments = db.query(SkillAssessment).filter(
            SkillAssessment.user_id == user.id,
            SkillAssessment.status == 'approved'
        ).all()
        
        avg_rating = 0
        if user_assessments:
            avg_rating = sum(a.self_score for a in user_assessments) / len(user_assessments)
        
        result.append(UserWithStats(
            id=user.id,
            login=user.login,
            email=user.email,
            full_name=user.full_name,
            avatar=user.avatar,
            department_id=user.department_id,
            position=user.position,
            role=user.role,
            is_active=user.is_active,
            average_rating=round(avg_rating, 2),
            skill_score=assessment.self_score if assessment else 0,
            last_login=user.last_login
        ))
    
    return sorted(result, key=lambda x: x.skill_score, reverse=True)

@router.get("/me/team", response_model=List[UserWithStats])
async def get_my_team(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get users in current user's department (for managers)"""
    if current_user.role not in ['manager', 'admin', 'hr', 'director']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers can view team members"
        )
    
    users = db.query(User).filter(
        User.department_id == current_user.department_id,
        User.id != current_user.id,
        User.is_active == True
    ).all()
    
    result = []
    for user in users:
        # Get user stats
        assessments = db.query(SkillAssessment).filter(
            SkillAssessment.user_id == user.id
        ).all()
        
        approved_assessments = [a for a in assessments if a.status == 'approved']
        avg_rating = 0
        if approved_assessments:
            avg_rating = sum(a.self_score for a in approved_assessments) / len(approved_assessments)
        
        pending_assessments = len([a for a in assessments if a.status == 'pending'])
        
        result.append(UserWithStats(
            id=user.id,
            login=user.login,
            email=user.email,
            full_name=user.full_name,
            avatar=user.avatar,
            department_id=user.department_id,
            position=user.position,
            role=user.role,
            is_active=user.is_active,
            average_rating=round(avg_rating, 2),
            pending_assessments=pending_assessments,
            last_login=user.last_login
        ))
    
    return result

@router.post("/{user_id}/notify")
async def send_notification_to_user(
    user_id: int,
    title: str,
    message: str,
    notification_type: str = "info",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Send notification to user (for managers/admins)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check permissions
    if (current_user.role not in ['admin', 'hr', 'manager', 'director'] and
        current_user.department_id != user.department_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # Create notification
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        is_read=False
    )
    
    db.add(notification)
    db.commit()
    
    return {"message": "Notification sent successfully", "notification_id": notification.id}
