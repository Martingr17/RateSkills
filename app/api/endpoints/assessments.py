from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, and_, or_
import logging

from app.database import get_db
from app.models import (
    SkillAssessment, AssessmentHistory, User, Skill, 
    SkillCategory, Department, Notification
)
from app.schemas import (
    SkillAssessmentCreate, SkillAssessmentResponse, SkillAssessmentUpdate,
    AssessmentHistoryResponse, AssessmentStats, AssessmentWithHistory,
    ComparisonRequest, ComparisonResult, UserAssessment
)
from app.api.endpoints.auth import get_current_active_user, check_manager_permission

router = APIRouter(prefix="/assessments", tags=["assessments"])
logger = logging.getLogger(__name__)

@router.get("/", response_model=List[SkillAssessmentResponse])
async def get_assessments(
    user_id: Optional[int] = None,
    skill_id: Optional[int] = None,
    status: Optional[str] = None,
    department_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get skill assessments with filtering"""
    query = db.query(SkillAssessment).options(
        joinedload(SkillAssessment.user),
        joinedload(SkillAssessment.skill).joinedload(Skill.category)
    )
    
    # Apply filters
    if user_id:
        query = query.filter(SkillAssessment.user_id == user_id)
    
    if skill_id:
        query = query.filter(SkillAssessment.skill_id == skill_id)
    
    if status:
        query = query.filter(SkillAssessment.status == status)
    
    if start_date:
        query = query.filter(SkillAssessment.assessed_at >= start_date)
    
    if end_date:
        query = query.filter(SkillAssessment.assessed_at <= end_date)
    
    # Department filter (for managers)
    if department_id:
        query = query.join(User).filter(User.department_id == department_id)
    
    # Permissions check
    if current_user.role in ['employee']:
        # Employees can only see their own assessments
        if user_id and user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only view your own assessments"
            )
        if not user_id:
            query = query.filter(SkillAssessment.user_id == current_user.id)
    
    elif current_user.role in ['manager']:
        # Managers can only see assessments in their department
        if department_id and department_id != current_user.department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only view assessments in your department"
            )
        if not department_id and not user_id:
            query = query.join(User).filter(User.department_id == current_user.department_id)
    
    assessments = query.order_by(desc(SkillAssessment.assessed_at)).all()
    return assessments

@router.get("/{assessment_id}", response_model=AssessmentWithHistory)
async def get_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get assessment by ID with history"""
    assessment = db.query(SkillAssessment).options(
        joinedload(SkillAssessment.user),
        joinedload(SkillAssessment.skill).joinedload(Skill.category),
        joinedload(SkillAssessment.history)
    ).filter(SkillAssessment.id == assessment_id).first()
    
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    # Check permissions
    if (current_user.id != assessment.user_id and 
        current_user.role in ['employee']):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own assessments"
        )
    
    if (current_user.role in ['manager'] and 
        current_user.department_id != assessment.user.department_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view assessments in your department"
        )
    
    return assessment

@router.post("/", response_model=SkillAssessmentResponse)
async def create_assessment(
    assessment_data: SkillAssessmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create new skill assessment (self-assessment)"""
    # Check if skill exists
    skill = db.query(Skill).filter(Skill.id == assessment_data.skill_id).first()
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found"
        )
    
    # Check if user is trying to assess someone else
    if assessment_data.user_id != current_user.id and current_user.role in ['employee']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only create assessments for yourself"
        )
    
    # Check for existing assessment
    existing = db.query(SkillAssessment).filter(
        SkillAssessment.user_id == assessment_data.user_id,
        SkillAssessment.skill_id == assessment_data.skill_id
    ).first()
    
    if existing:
        # Update existing assessment
        old_score = existing.self_score
        
        # Create history entry
        history = AssessmentHistory(
            assessment_id=existing.id,
            old_score=old_score,
            new_score=assessment_data.self_score,
            changed_by_id=current_user.id,
            change_type="self_update",
            comment=assessment_data.comment
        )
        
        # Update assessment
        existing.self_score = assessment_data.self_score
        existing.comment = assessment_data.comment
        existing.status = "pending"  # Reset to pending when self-updated
        existing.assessed_at = datetime.utcnow()
        
        db.add(history)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        
        return existing
    
    # Create new assessment
    assessment = SkillAssessment(
        user_id=assessment_data.user_id,
        skill_id=assessment_data.skill_id,
        self_score=assessment_data.self_score,
        manager_score=None,
        status="pending",
        comment=assessment_data.comment,
        assessed_at=datetime.utcnow()
    )
    
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    
    # Create initial history entry
    history = AssessmentHistory(
        assessment_id=assessment.id,
        old_score=None,
        new_score=assessment_data.self_score,
        changed_by_id=current_user.id,
        change_type="created",
        comment="Initial self-assessment"
    )
    
    db.add(history)
    db.commit()
    
    # Load relationships for response
    db.refresh(assessment)
    assessment.user = db.query(User).filter(User.id == assessment.user_id).first()
    assessment.skill = skill
    
    return assessment

@router.put("/{assessment_id}", response_model=SkillAssessmentResponse)
async def update_assessment(
    assessment_id: int,
    assessment_update: SkillAssessmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update assessment (manager approval/rejection or self-update)"""
    assessment = db.query(SkillAssessment).filter(SkillAssessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    # Check permissions
    is_self_update = current_user.id == assessment.user_id
    is_manager_update = current_user.role in ['manager', 'admin', 'hr', 'director']
    
    if not (is_self_update or is_manager_update):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # If manager update, check department
    if is_manager_update and current_user.role == 'manager':
        user = db.query(User).filter(User.id == assessment.user_id).first()
        if user.department_id != current_user.department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only manage assessments in your department"
            )
    
    old_score = assessment.self_score
    old_status = assessment.status
    
    # Create history entry
    change_type = "manager_update" if is_manager_update else "self_update"
    
    history = AssessmentHistory(
        assessment_id=assessment_id,
        old_score=old_score,
        new_score=assessment_update.self_score if assessment_update.self_score else old_score,
        changed_by_id=current_user.id,
        change_type=change_type,
        comment=assessment_update.comment or f"Updated by {current_user.role}"
    )
    
    # Update assessment
    update_data = assessment_update.dict(exclude_unset=True)
    
    # If manager is setting status to approved/rejected
    if is_manager_update and 'status' in update_data:
        if update_data['status'] == 'approved':
            assessment.manager_score = assessment.self_score
            assessment.approved_by_id = current_user.id
            assessment.approved_at = datetime.utcnow()
            
            # Create notification for user
            notification = Notification(
                user_id=assessment.user_id,
                title="Оценка подтверждена",
                message=f"Ваш навык {assessment.skill.name} был подтвержден менеджером",
                notification_type="success",
                is_read=False
            )
            db.add(notification)
            
        elif update_data['status'] == 'rejected':
            # Create notification for user
            notification = Notification(
                user_id=assessment.user_id,
                title="Оценка отклонена",
                message=f"Ваш навык {assessment.skill.name} был отклонен. Причина: {assessment_update.comment or 'Не указана'}",
                notification_type="error",
                is_read=False
            )
            db.add(notification)
    
    for field, value in update_data.items():
        setattr(assessment, field, value)
    
    assessment.assessed_at = datetime.utcnow()
    
    db.add(history)
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    
    # Load relationships for response
    assessment.user = db.query(User).filter(User.id == assessment.user_id).first()
    assessment.skill = db.query(Skill).filter(Skill.id == assessment.skill_id).first()
    
    return assessment

@router.delete("/{assessment_id}")
async def delete_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete assessment (admin/self only)"""
    assessment = db.query(SkillAssessment).filter(SkillAssessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    # Check permissions
    if (current_user.id != assessment.user_id and 
        current_user.role not in ['admin', 'hr']):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only delete your own assessments"
        )
    
    # Delete history first
    db.query(AssessmentHistory).filter(AssessmentHistory.assessment_id == assessment_id).delete()
    
    # Delete assessment
    db.delete(assessment)
    db.commit()
    
    return {"message": "Assessment deleted successfully"}

@router.get("/user/{user_id}/stats", response_model=AssessmentStats)
async def get_user_assessment_stats(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get assessment statistics for user"""
    # Check permissions
    if (current_user.id != user_id and 
        current_user.role in ['employee']):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own stats"
        )
    
    assessments = db.query(SkillAssessment).filter(SkillAssessment.user_id == user_id).all()
    
    approved = [a for a in assessments if a.status == 'approved']
    pending = [a for a in assessments if a.status == 'pending']
    rejected = [a for a in assessments if a.status == 'rejected']
    
    avg_score = 0
    if approved:
        avg_score = sum(a.self_score for a in approved) / len(approved)
    
    # Get required skills for user's department
    user = db.query(User).filter(User.id == user_id).first()
    required_skills = db.query(Skill).filter(
        Skill.required_for_departments.any(id=user.department_id)
    ).count()
    
    # Get approved required skills
    approved_required = 0
    for a in approved:
        skill = db.query(Skill).filter(Skill.id == a.skill_id).first()
        if skill and user.department_id in [d.id for d in skill.required_for_departments]:
            approved_required += 1
    
    return AssessmentStats(
        user_id=user_id,
        total_assessments=len(assessments),
        approved_assessments=len(approved),
        pending_assessments=len(pending),
        rejected_assessments=len(rejected),
        average_score=round(avg_score, 2),
        required_skills=required_skills,
        approved_required_skills=approved_required,
        completion_rate=round((approved_required / required_skills * 100) if required_skills > 0 else 0, 1)
    )

@router.post("/compare", response_model=List[ComparisonResult])
async def compare_assessments(
    comparison_request: ComparisonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Compare assessments between users or departments"""
    if not comparison_request.user_ids and not comparison_request.department_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either user_ids or department_ids"
        )
    
    results = []
    
    # Compare by user IDs
    if comparison_request.user_ids:
        for user_id in comparison_request.user_ids:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                continue
            
            # Check permissions for managers
            if (current_user.role == 'manager' and 
                user.department_id != current_user.department_id):
                continue
            
            # Get assessments for this user
            assessments = db.query(SkillAssessment).filter(
                SkillAssessment.user_id == user_id,
                SkillAssessment.status == 'approved'
            ).all()
            
            skill_scores = {}
            for assessment in assessments:
                skill_scores[assessment.skill_id] = assessment.self_score
            
            results.append(ComparisonResult(
                entity_id=user_id,
                entity_name=user.full_name,
                entity_type="user",
                skill_scores=skill_scores,
                average_score=sum(skill_scores.values()) / len(skill_scores) if skill_scores else 0
            ))
    
    # Compare by department IDs
    elif comparison_request.department_ids:
        for dept_id in comparison_request.department_ids:
            department = db.query(Department).filter(Department.id == dept_id).first()
            if not department:
                continue
            
            # Check permissions for managers
            if (current_user.role == 'manager' and 
                dept_id != current_user.department_id):
                continue
            
            # Get average scores for department
            query = db.query(
                SkillAssessment.skill_id,
                func.avg(SkillAssessment.self_score).label('avg_score')
            ).join(User).filter(
                User.department_id == dept_id,
                SkillAssessment.status == 'approved'
            ).group_by(SkillAssessment.skill_id)
            
            department_scores = query.all()
            
            skill_scores = {row.skill_id: round(row.avg_score, 2) for row in department_scores}
            
            results.append(ComparisonResult(
                entity_id=dept_id,
                entity_name=department.name,
                entity_type="department",
                skill_scores=skill_scores,
                average_score=sum(skill_scores.values()) / len(skill_scores) if skill_scores else 0
            ))
    
    return results

@router.get("/pending", response_model=List[SkillAssessmentResponse])
async def get_pending_assessments(
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_manager_permission)
):
    """Get pending assessments for manager review"""
    query = db.query(SkillAssessment).options(
        joinedload(SkillAssessment.user),
        joinedload(SkillAssessment.skill).joinedload(Skill.category)
    ).filter(SkillAssessment.status == 'pending')
    
    # For managers, only show their department
    if current_user.role == 'manager':
        query = query.join(User).filter(User.department_id == current_user.department_id)
    elif department_id and current_user.role in ['admin', 'hr', 'director']:
        query = query.join(User).filter(User.department_id == department_id)
    
    assessments = query.order_by(SkillAssessment.assessed_at).all()
    return assessments

@router.post("/{assessment_id}/approve")
async def approve_assessment(
    assessment_id: int,
    comment: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_manager_permission)
):
    """Approve assessment (manager action)"""
    return await _update_assessment_status(
        assessment_id, "approved", comment, current_user, db
    )

@router.post("/{assessment_id}/reject")
async def reject_assessment(
    assessment_id: int,
    comment: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_manager_permission)
):
    """Reject assessment (manager action)"""
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comment is required when rejecting"
        )
    
    return await _update_assessment_status(
        assessment_id, "rejected", comment, current_user, db
    )

async def _update_assessment_status(
    assessment_id: int,
    status: str,
    comment: str,
    current_user: User,
    db: Session
):
    """Helper function to update assessment status"""
    assessment = db.query(SkillAssessment).filter(SkillAssessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    # Check permissions
    if current_user.role == 'manager':
        user = db.query(User).filter(User.id == assessment.user_id).first()
        if user.department_id != current_user.department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only manage assessments in your department"
            )
    
    # Create history entry
    history = AssessmentHistory(
        assessment_id=assessment_id,
        old_score=assessment.self_score,
        new_score=assessment.self_score,
        changed_by_id=current_user.id,
        change_type=f"manager_{status}",
        comment=comment or f"{status.capitalize()} by manager"
    )
    
    # Update assessment
    assessment.status = status
    assessment.comment = comment or assessment.comment
    
    if status == 'approved':
        assessment.manager_score = assessment.self_score
        assessment.approved_by_id = current_user.id
        assessment.approved_at = datetime.utcnow()
    
    # Create notification
    notification_type = "success" if status == 'approved' else "error"
    notification_title = "Оценка подтверждена" if status == 'approved' else "Оценка отклонена"
    notification_message = f"Ваш навык {assessment.skill.name} был {status}."
    
    if comment and status == 'rejected':
        notification_message += f" Причина: {comment}"
    
    notification = Notification(
        user_id=assessment.user_id,
        title=notification_title,
        message=notification_message,
        notification_type=notification_type,
        is_read=False
    )
    
    db.add(history)
    db.add(notification)
    db.commit()
    
    return {"message": f"Assessment {status} successfully"}