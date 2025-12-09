from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, and_, or_, case
import logging

from app.database import get_db
from app.models import (
    User, Department, Skill, SkillCategory, SkillAssessment,
    Goal, Notification, Event, Feedback
)
from app.schemas import (
    DashboardStats, UserDashboard, ManagerDashboard,
    AdminDashboard, SkillProgress, GoalProgress,
    NotificationResponse, EventResponse, FeedbackResponse
)
from app.api.endpoints.auth import get_current_active_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
logger = logging.getLogger(__name__)

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get dashboard statistics based on user role"""
    
    if current_user.role in ['admin', 'hr', 'director']:
        return await _get_admin_dashboard_stats(current_user, db)
    elif current_user.role == 'manager':
        return await _get_manager_dashboard_stats(current_user, db)
    else:
        return await _get_user_dashboard_stats(current_user, db)

async def _get_user_dashboard_stats(user: User, db: Session) -> DashboardStats:
    """Get dashboard stats for regular employee"""
    
    # Get user assessments
    assessments = db.query(SkillAssessment).filter(
        SkillAssessment.user_id == user.id
    ).all()
    
    approved_assessments = [a for a in assessments if a.status == 'approved']
    pending_assessments = [a for a in assessments if a.status == 'pending']
    
    # Calculate stats
    total_skills = len(db.query(SkillAssessment).filter(
        SkillAssessment.user_id == user.id
    ).distinct(SkillAssessment.skill_id).all())
    
    avg_rating = 0
    if approved_assessments:
        avg_rating = sum(a.self_score for a in approved_assessments) / len(approved_assessments)
    
    # Get required skills for user's department
    required_skills = db.query(Skill).filter(
        Skill.required_for_departments.any(id=user.department_id)
    ).count()
    
    # Get approved required skills
    approved_required = 0
    for a in approved_assessments:
        skill = db.query(Skill).filter(Skill.id == a.skill_id).first()
        if skill and user.department_id in [d.id for d in skill.required_for_departments]:
            approved_required += 1
    
    # Get goals
    goals = db.query(Goal).filter(Goal.user_id == user.id).all()
    completed_goals = sum(1 for g in goals if g.status == 'completed')
    in_progress_goals = sum(1 for g in goals if g.status == 'in_progress')
    
    # Get notifications
    unread_notifications = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False
    ).count()
    
    # Get upcoming events
    upcoming_events = db.query(Event).filter(
        Event.participants.any(id=user.id),
        Event.start_time >= datetime.utcnow(),
        Event.start_time <= datetime.utcnow() + timedelta(days=7)
    ).count()
    
    # Get recent feedback
    recent_feedback = db.query(Feedback).filter(
        Feedback.to_user_id == user.id
    ).order_by(desc(Feedback.created_at)).limit(5).count()
    
    # Get skill progress by category
    skill_progress = []
    categories = db.query(SkillCategory).all()
    
    for category in categories:
        category_skills = db.query(Skill).filter(Skill.category_id == category.id).count()
        
        if category_skills > 0:
            user_category_assessments = db.query(SkillAssessment).join(Skill).filter(
                SkillAssessment.user_id == user.id,
                Skill.category_id == category.id,
                SkillAssessment.status == 'approved'
            ).count()
            
            progress_percentage = (user_category_assessments / category_skills) * 100
            
            skill_progress.append(SkillProgress(
                category_id=category.id,
                category_name=category.name,
                total_skills=category_skills,
                assessed_skills=user_category_assessments,
                progress_percentage=round(progress_percentage, 1),
                color=category.color
            ))
    
    # Get goal progress
    goal_progress_list = []
    for goal in goals[:5]:  # Limit to 5 goals
        goal_progress_list.append(GoalProgress(
            goal_id=goal.id,
            title=goal.title,
            progress_percentage=goal.progress_percentage,
            status=goal.status,
            priority=goal.priority,
            deadline=goal.deadline
        ))
    
    return DashboardStats(
        user_id=user.id,
        role=user.role,
        total_skills=total_skills,
        assessed_skills=len(approved_assessments),
        pending_assessments=len(pending_assessments),
        average_rating=round(avg_rating, 2),
        required_skills=required_skills,
        approved_required_skills=approved_required,
        completion_rate=round((approved_required / required_skills * 100) if required_skills > 0 else 0, 1),
        total_goals=len(goals),
        completed_goals=completed_goals,
        in_progress_goals=in_progress_goals,
        unread_notifications=unread_notifications,
        upcoming_events=upcoming_events,
        recent_feedback=recent_feedback,
        skill_progress=skill_progress,
        goal_progress=goal_progress_list
    )

async def _get_manager_dashboard_stats(user: User, db: Session) -> DashboardStats:
    """Get dashboard stats for manager"""
    
    # Get department users
    department_users = db.query(User).filter(
        User.department_id == user.department_id,
        User.is_active == True
    ).all()
    
    total_team_members = len(department_users) - 1  # Exclude manager
    
    # Get department assessments
    department_assessments = db.query(SkillAssessment).join(User).filter(
        User.department_id == user.department_id
    ).all()
    
    approved_assessments = [a for a in department_assessments if a.status == 'approved']
    pending_assessments = [a for a in department_assessments if a.status == 'pending']
    
    # Calculate department stats
    avg_department_rating = 0
    if approved_assessments:
        avg_department_rating = sum(a.self_score for a in approved_assessments) / len(approved_assessments)
    
    # Get required skills for department
    required_skills = db.query(Skill).filter(
        Skill.required_for_departments.any(id=user.department_id)
    ).count()
    
    # Calculate skill coverage
    covered_skills = set()
    for a in approved_assessments:
        skill = db.query(Skill).filter(Skill.id == a.skill_id).first()
        if skill and user.department_id in [d.id for d in skill.required_for_departments]:
            covered_skills.add(skill.id)
    
    skill_coverage = len(covered_skills) / required_skills * 100 if required_skills > 0 else 0
    
    # Get pending reviews
    pending_reviews = len(pending_assessments)
    
    # Get team goals
    team_goals = db.query(Goal).filter(
        Goal.user_id.in_([u.id for u in department_users])
    ).all()
    
    completed_team_goals = sum(1 for g in team_goals if g.status == 'completed')
    
    # Get notifications for department
    department_notifications = db.query(Notification).join(User).filter(
        User.department_id == user.department_id,
        Notification.is_read == False
    ).count()
    
    # Get department events
    department_events = db.query(Event).filter(
        Event.participants.any(User.department_id == user.department_id),
        Event.start_time >= datetime.utcnow(),
        Event.start_time <= datetime.utcnow() + timedelta(days=7)
    ).count()
    
    # Get top performers
    top_performers = []
    for team_user in department_users:
        if team_user.id == user.id:
            continue
        
        user_assessments = db.query(SkillAssessment).filter(
            SkillAssessment.user_id == team_user.id,
            SkillAssessment.status == 'approved'
        ).all()
        
        if user_assessments:
            user_avg = sum(a.self_score for a in user_assessments) / len(user_assessments)
            pending_count = len([a for a in department_assessments if a.user_id == team_user.id and a.status == 'pending'])
            
            top_performers.append({
                "user_id": team_user.id,
                "name": team_user.full_name,
                "position": team_user.position,
                "average_rating": round(user_avg, 2),
                "pending_assessments": pending_count
            })
    
    # Sort by average rating
    top_performers.sort(key=lambda x: x["average_rating"], reverse=True)
    top_performers = top_performers[:5]
    
    # Get skill gaps
    skill_gaps = []
    required_skills_list = db.query(Skill).filter(
        Skill.required_for_departments.any(id=user.department_id)
    ).all()
    
    for skill in required_skills_list[:5]:  # Limit to 5 skills
        skill_assessments = db.query(SkillAssessment).filter(
            SkillAssessment.skill_id == skill.id,
            SkillAssessment.status == 'approved'
        ).join(User).filter(User.department_id == user.department_id).all()
        
        avg_skill_score = 0
        if skill_assessments:
            avg_skill_score = sum(a.self_score for a in skill_assessments) / len(skill_assessments)
        
        skill_gaps.append({
            "skill_id": skill.id,
            "skill_name": skill.name,
            "average_score": round(avg_skill_score, 2),
            "users_assessed": len(skill_assessments),
            "target_score": 4.0
        })
    
    return DashboardStats(
        user_id=user.id,
        role=user.role,
        total_team_members=total_team_members,
        department_assessments=len(department_assessments),
        pending_reviews=pending_reviews,
        average_department_rating=round(avg_department_rating, 2),
        required_skills=required_skills,
        skill_coverage=round(skill_coverage, 1),
        team_goals=len(team_goals),
        completed_team_goals=completed_team_goals,
        department_notifications=department_notifications,
        department_events=department_events,
        top_performers=top_performers,
        skill_gaps=skill_gaps
    )

async def _get_admin_dashboard_stats(user: User, db: Session) -> DashboardStats:
    """Get dashboard stats for admin/HR"""
    
    # Company-wide stats
    total_users = db.query(User).filter(User.is_active == True).count()
    total_departments = db.query(Department).count()
    total_skills = db.query(Skill).count()
    
    # Assessment stats
    total_assessments = db.query(SkillAssessment).count()
    pending_assessments = db.query(SkillAssessment).filter(
        SkillAssessment.status == 'pending'
    ).count()
    
    approved_assessments = db.query(SkillAssessment).filter(
        SkillAssessment.status == 'approved'
    ).count()
    
    avg_company_rating = 0
    if approved_assessments > 0:
        avg_result = db.query(func.avg(SkillAssessment.self_score)).filter(
            SkillAssessment.status == 'approved'
        ).scalar()
        avg_company_rating = float(avg_result) if avg_result else 0
    
    # Recent activity (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_users = db.query(User).filter(User.created_at >= week_ago).count()
    recent_assessments = db.query(SkillAssessment).filter(
        SkillAssessment.assessed_at >= week_ago
    ).count()
    
    # Department statistics
    department_stats = []
    departments = db.query(Department).all()
    
    for dept in departments:
        dept_users = db.query(User).filter(
            User.department_id == dept.id,
            User.is_active == True
        ).count()
        
        dept_assessments = db.query(SkillAssessment).join(User).filter(
            User.department_id == dept.id,
            SkillAssessment.status == 'approved'
        ).count()
        
        dept_avg = 0
        if dept_assessments > 0:
            dept_avg_result = db.query(func.avg(SkillAssessment.self_score)).join(User).filter(
                User.department_id == dept.id,
                SkillAssessment.status == 'approved'
            ).scalar()
            dept_avg = float(dept_avg_result) if dept_avg_result else 0
        
        department_stats.append({
            "department_id": dept.id,
            "department_name": dept.name,
            "user_count": dept_users,
            "assessment_count": dept_assessments,
            "average_rating": round(dept_avg, 2)
        })
    
    # Skill category statistics
    category_stats = []
    categories = db.query(SkillCategory).all()
    
    for category in categories:
        cat_skills = db.query(Skill).filter(Skill.category_id == category.id).count()
        
        cat_assessments = db.query(SkillAssessment).join(Skill).filter(
            Skill.category_id == category.id,
            SkillAssessment.status == 'approved'
        ).count()
        
        cat_avg = 0
        if cat_assessments > 0:
            cat_avg_result = db.query(func.avg(SkillAssessment.self_score)).join(Skill).filter(
                Skill.category_id == category.id,
                SkillAssessment.status == 'approved'
            ).scalar()
            cat_avg = float(cat_avg_result) if cat_avg_result else 0
        
        category_stats.append({
            "category_id": category.id,
            "category_name": category.name,
            "skill_count": cat_skills,
            "assessment_count": cat_assessments,
            "average_rating": round(cat_avg, 2),
            "color": category.color
        })
    
    # System activity trend (last 30 days)
    trend_data = []
    for i in range(30, -1, -1):
        date = datetime.utcnow() - timedelta(days=i)
        date_start = datetime(date.year, date.month, date.day, 0, 0, 0)
        date_end = datetime(date.year, date.month, date.day, 23, 59, 59)
        
        daily_users = db.query(User).filter(
            User.created_at >= date_start,
            User.created_at <= date_end
        ).count()
        
        daily_assessments = db.query(SkillAssessment).filter(
            SkillAssessment.assessed_at >= date_start,
            SkillAssessment.assessed_at <= date_end
        ).count()
        
        trend_data.append({
            "date": date.date().isoformat(),
            "new_users": daily_users,
            "new_assessments": daily_assessments
        })
    
    return DashboardStats(
        user_id=user.id,
        role=user.role,
        total_users=total_users,
        total_departments=total_departments,
        total_skills=total_skills,
        total_assessments=total_assessments,
        pending_assessments=pending_assessments,
        approved_assessments=approved_assessments,
        average_company_rating=round(avg_company_rating, 2),
        recent_users=recent_users,
        recent_assessments=recent_assessments,
        department_stats=department_stats,
        category_stats=category_stats,
        activity_trend=trend_data
    )

@router.get("/notifications", response_model=List[NotificationResponse])
async def get_user_notifications(
    unread_only: bool = False,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get user notifications"""
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    
    if unread_only:
        query = query.filter(Notification.is_read == False)
    
    notifications = query.order_by(desc(Notification.created_at)).limit(limit).all()
    
    return notifications

@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Mark notification as read"""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    notification.is_read = True
    notification.read_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Notification marked as read"}

@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Mark all user notifications as read"""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({"is_read": True, "read_at": datetime.utcnow()})
    
    db.commit()
    
    return {"message": "All notifications marked as read"}

@router.get("/events", response_model=List[EventResponse])
async def get_user_events(
    upcoming_only: bool = True,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get user events"""
    query = db.query(Event).filter(Event.participants.any(id=current_user.id))
    
    if upcoming_only:
        query = query.filter(Event.start_time >= datetime.utcnow())
    
    events = query.order_by(Event.start_time).limit(limit).all()
    
    return events

@router.get("/feedback", response_model=List[FeedbackResponse])
async def get_user_feedback(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get feedback for user"""
    feedback = db.query(Feedback).options(
        joinedload(Feedback.from_user),
        joinedload(Feedback.skill)
    ).filter(
        Feedback.to_user_id == current_user.id
    ).order_by(desc(Feedback.created_at)).limit(limit).all()
    
    return feedback

@router.get("/skill-progress")
async def get_skill_progress(
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get detailed skill progress for current user"""
    
    query = db.query(Skill).options(
        joinedload(Skill.category),
        joinedload(Skill.assessments)
    )
    
    if category_id:
        query = query.filter(Skill.category_id == category_id)
    
    skills = query.all()
    
    progress_data = []
    for skill in skills:
        # Get user's assessment for this skill
        assessment = db.query(SkillAssessment).filter(
            SkillAssessment.user_id == current_user.id,
            SkillAssessment.skill_id == skill.id
        ).first()
        
        # Check if skill is required for user's department
        is_required = current_user.department_id in [d.id for d in skill.required_for_departments]
        
        progress_data.append({
            "skill_id": skill.id,
            "skill_name": skill.name,
            "category": skill.category.name if skill.category else "",
            "category_color": skill.category.color if skill.category else "",
            "difficulty_level": skill.difficulty_level,
            "is_required": is_required,
            "self_score": assessment.self_score if assessment else 0,
            "manager_score": assessment.manager_score if assessment else None,
            "status": assessment.status if assessment else "not_assessed",
            "comment": assessment.comment if assessment else "",
            "last_assessed": assessment.assessed_at.isoformat() if assessment and assessment.assessed_at else None
        })
    
    return progress_data

@router.get("/comparison/{user_id}")
async def compare_with_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Compare current user with another user"""
    
    # Check if target user exists
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check permissions
    if (current_user.role in ['employee'] and 
        current_user.id != user_id and
        current_user.department_id != target_user.department_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only compare with users in your department"
        )
    
    # Get common skills assessments
    current_user_assessments = db.query(SkillAssessment).filter(
        SkillAssessment.user_id == current_user.id,
        SkillAssessment.status == 'approved'
    ).all()
    
    target_user_assessments = db.query(SkillAssessment).filter(
        SkillAssessment.user_id == user_id,
        SkillAssessment.status == 'approved'
    ).all()
    
    # Create skill ID to assessment mapping
    current_skills = {a.skill_id: a for a in current_user_assessments}
    target_skills = {a.skill_id: a for a in target_user_assessments}
    
    # Find common skills
    common_skill_ids = set(current_skills.keys()) & set(target_skills.keys())
    
    comparison_data = []
    for skill_id in common_skill_ids:
        skill = db.query(Skill).filter(Skill.id == skill_id).first()
        if not skill:
            continue
        
        current_assessment = current_skills[skill_id]
        target_assessment = target_skills[skill_id]
        
        comparison_data.append({
            "skill_id": skill_id,
            "skill_name": skill.name,
            "category": skill.category.name if skill.category else "",
            "current_user_score": current_assessment.self_score,
            "target_user_score": target_assessment.self_score,
            "score_difference": round(current_assessment.self_score - target_assessment.self_score, 2)
        })
    
    # Calculate averages
    current_avg = sum(a.self_score for a in current_user_assessments) / len(current_user_assessments) if current_user_assessments else 0
    target_avg = sum(a.self_score for a in target_user_assessments) / len(target_user_assessments) if target_user_assessments else 0
    
    return {
        "current_user": {
            "id": current_user.id,
            "name": current_user.full_name,
            "average_score": round(current_avg, 2),
            "total_skills": len(current_user_assessments)
        },
        "target_user": {
            "id": target_user.id,
            "name": target_user.full_name,
            "average_score": round(target_avg, 2),
            "total_skills": len(target_user_assessments)
        },
        "common_skills_count": len(common_skill_ids),
        "comparison_data": sorted(comparison_data, key=lambda x: abs(x["score_difference"]), reverse=True)
    }