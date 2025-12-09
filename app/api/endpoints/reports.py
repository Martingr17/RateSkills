from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, and_, or_, case
import csv
import io
import json
import logging

from app.database import get_db
from app.models import (
    User, Department, Skill, SkillCategory, SkillAssessment,
    AssessmentHistory, Goal, Notification
)
from app.schemas import (
    ReportRequest, ExportRequest, ReportResponse,
    DepartmentReport, SkillGapAnalysis, TrendAnalysis,
    UserProgressReport
)
from app.api.endpoints.auth import get_current_active_user, check_admin_permission
# Измените импорт в reports.py на:
from app.utils import (
    generate_department_report,
    generate_skill_gap_analysis,
    generate_trend_analysis,
    generate_user_progress_report
)

router = APIRouter(prefix="/reports", tags=["reports"])
logger = logging.getLogger(__name__)

@router.post("/generate", response_model=ReportResponse)
async def generate_report(
    report_request: ReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_permission)
):
    """Generate various types of reports"""
    report_data = None
    
    if report_request.report_type == "department":
        report_data = await generate_department_report(
            report_request.department_id,
            report_request.start_date,
            report_request.end_date,
            db
        )
    
    elif report_request.report_type == "skill_gap":
        report_data = await generate_skill_gap_analysis(
            report_request.department_id,
            report_request.skill_ids,
            db
        )
    
    elif report_request.report_type == "trend":
        report_data = await generate_trend_analysis(
            report_request.department_id,
            report_request.skill_ids,
            report_request.start_date,
            report_request.end_date,
            db
        )
    
    elif report_request.report_type == "user_progress":
        report_data = await generate_user_progress_report(
            report_request.user_id,
            report_request.start_date,
            report_request.end_date,
            db
        )
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid report type"
        )
    
    return ReportResponse(
        report_type=report_request.report_type,
        generated_at=datetime.utcnow(),
        data=report_data
    )

@router.post("/export/csv")
async def export_to_csv(
    export_request: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Export data to CSV format"""
    
    if export_request.export_type == "users":
        data = await _export_users_data(export_request, db, current_user)
        filename = f"users_export_{datetime.utcnow().date()}.csv"
    
    elif export_request.export_type == "assessments":
        data = await _export_assessments_data(export_request, db, current_user)
        filename = f"assessments_export_{datetime.utcnow().date()}.csv"
    
    elif export_request.export_type == "skills":
        data = await _export_skills_data(export_request, db, current_user)
        filename = f"skills_export_{datetime.utcnow().date()}.csv"
    
    elif export_request.export_type == "department_stats":
        data = await _export_department_stats(export_request, db, current_user)
        filename = f"department_stats_{datetime.utcnow().date()}.csv"
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid export type"
        )
    
    # Create CSV response
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    if data and len(data) > 0:
        writer.writerow(data[0].keys())
        
        # Write data rows
        for row in data:
            writer.writerow(row.values())
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.post("/export/json")
async def export_to_json(
    export_request: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Export data to JSON format"""
    
    if export_request.export_type == "users":
        data = await _export_users_data(export_request, db, current_user)
    
    elif export_request.export_type == "assessments":
        data = await _export_assessments_data(export_request, db, current_user)
    
    elif export_request.export_type == "skills":
        data = await _export_skills_data(export_request, db, current_user)
    
    elif export_request.export_type == "department_stats":
        data = await _export_department_stats(export_request, db, current_user)
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid export type"
        )
    
    # Create JSON response
    export_data = {
        "export_type": export_request.export_type,
        "exported_at": datetime.utcnow().isoformat(),
        "total_records": len(data),
        "data": data
    }
    
    filename = f"{export_request.export_type}_export_{datetime.utcnow().date()}.json"
    
    return JSONResponse(
        content=export_data,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

async def _export_users_data(
    export_request: ExportRequest,
    db: Session,
    current_user: User
) -> List[Dict[str, Any]]:
    """Export users data to CSV"""
    query = db.query(User).options(
        joinedload(User.department)
    )
    
    if export_request.department_id:
        query = query.filter(User.department_id == export_request.department_id)
    
    if export_request.role:
        query = query.filter(User.role == export_request.role)
    
    users = query.all()
    
    data = []
    for user in users:
        # Get user stats
        assessments = db.query(SkillAssessment).filter(
            SkillAssessment.user_id == user.id,
            SkillAssessment.status == 'approved'
        ).all()
        
        avg_score = 0
        if assessments:
            avg_score = sum(a.self_score for a in assessments) / len(assessments)
        
        row = {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "login": user.login,
            "department": user.department.name if user.department else "",
            "position": user.position,
            "role": user.role,
            "hire_date": user.hire_date.isoformat() if user.hire_date else "",
            "phone": user.phone or "",
            "is_active": user.is_active,
            "total_skills_assessed": len(assessments),
            "average_skill_score": round(avg_score, 2),
            "last_login": user.last_login.isoformat() if user.last_login else "",
            "created_at": user.created_at.isoformat() if user.created_at else ""
        }
        data.append(row)
    
    return data

async def _export_assessments_data(
    export_request: ExportRequest,
    db: Session,
    current_user: User
) -> List[Dict[str, Any]]:
    """Export assessments data to CSV"""
    query = db.query(SkillAssessment).options(
        joinedload(SkillAssessment.user).joinedload(User.department),
        joinedload(SkillAssessment.skill).joinedload(Skill.category),
        joinedload(SkillAssessment.approved_by)
    )
    
    if export_request.department_id:
        query = query.join(User).filter(User.department_id == export_request.department_id)
    
    if export_request.start_date:
        query = query.filter(SkillAssessment.assessed_at >= export_request.start_date)
    
    if export_request.end_date:
        query = query.filter(SkillAssessment.assessed_at <= export_request.end_date)
    
    if export_request.status:
        query = query.filter(SkillAssessment.status == export_request.status)
    
    assessments = query.order_by(SkillAssessment.assessed_at.desc()).all()
    
    data = []
    for assessment in assessments:
        row = {
            "assessment_id": assessment.id,
            "user_id": assessment.user_id,
            "user_name": assessment.user.full_name,
            "department": assessment.user.department.name if assessment.user.department else "",
            "skill_id": assessment.skill_id,
            "skill_name": assessment.skill.name,
            "skill_category": assessment.skill.category.name if assessment.skill.category else "",
            "self_score": assessment.self_score,
            "manager_score": assessment.manager_score,
            "status": assessment.status,
            "comment": assessment.comment or "",
            "assessed_at": assessment.assessed_at.isoformat() if assessment.assessed_at else "",
            "approved_by": assessment.approved_by.full_name if assessment.approved_by else "",
            "approved_at": assessment.approved_at.isoformat() if assessment.approved_at else ""
        }
        data.append(row)
    
    return data

async def _export_skills_data(
    export_request: ExportRequest,
    db: Session,
    current_user: User
) -> List[Dict[str, Any]]:
    """Export skills data to CSV"""
    query = db.query(Skill).options(
        joinedload(Skill.category)
    )
    
    if export_request.department_id:
        # Get skills required for this department
        department = db.query(Department).filter(Department.id == export_request.department_id).first()
        if department:
            query = query.filter(Skill.required_for_departments.any(id=department.id))
    
    skills = query.order_by(Skill.name).all()
    
    data = []
    for skill in skills:
        # Get statistics
        assessments = db.query(SkillAssessment).filter(
            SkillAssessment.skill_id == skill.id,
            SkillAssessment.status == 'approved'
        ).all()
        
        avg_score = 0
        if assessments:
            avg_score = sum(a.self_score for a in assessments) / len(assessments)
        
        # Get requiring departments
        requiring_depts = [d.name for d in skill.required_for_departments] if skill.required_for_departments else []
        
        row = {
            "skill_id": skill.id,
            "skill_name": skill.name,
            "description": skill.description or "",
            "category": skill.category.name if skill.category else "",
            "difficulty_level": skill.difficulty_level,
            "total_assessments": len(assessments),
            "average_score": round(avg_score, 2),
            "requiring_departments": ", ".join(requiring_depts),
            "created_at": skill.created_at.isoformat() if skill.created_at else ""
        }
        data.append(row)
    
    return data

async def _export_department_stats(
    export_request: ExportRequest,
    db: Session,
    current_user: User
) -> List[Dict[str, Any]]:
    """Export department statistics to CSV"""
    query = db.query(Department)
    
    if export_request.department_id:
        query = query.filter(Department.id == export_request.department_id)
    
    departments = query.all()
    
    data = []
    for department in departments:
        # Get department statistics
        users = db.query(User).filter(
            User.department_id == department.id,
            User.is_active == True
        ).all()
        
        total_users = len(users)
        
        # Get assessments for this department
        assessments = db.query(SkillAssessment).join(User).filter(
            User.department_id == department.id,
            SkillAssessment.status == 'approved'
        ).all()
        
        total_assessments = len(assessments)
        
        avg_score = 0
        if assessments:
            avg_score = sum(a.self_score for a in assessments) / len(assessments)
        
        # Get required skills for this department
        required_skills = db.query(Skill).filter(
            Skill.required_for_departments.any(id=department.id)
        ).count()
        
        # Calculate skill coverage
        skill_coverage = 0
        if required_skills > 0:
            covered_skills = set()
            for assessment in assessments:
                skill = db.query(Skill).filter(Skill.id == assessment.skill_id).first()
                if skill and department.id in [d.id for d in skill.required_for_departments]:
                    covered_skills.add(skill.id)
            skill_coverage = len(covered_skills) / required_skills * 100
        
        row = {
            "department_id": department.id,
            "department_name": department.name,
            "manager_id": department.manager_id,
            "total_users": total_users,
            "total_assessments": total_assessments,
            "average_score": round(avg_score, 2),
            "required_skills": required_skills,
            "skill_coverage_percentage": round(skill_coverage, 1),
            "created_at": department.created_at.isoformat() if department.created_at else ""
        }
        data.append(row)
    
    return data

@router.get("/dashboard")
async def get_dashboard_report(
    time_range: str = Query("month", regex="^(day|week|month|quarter|year)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_permission)
):
    """Get dashboard statistics report"""
    
    # Calculate date range
    end_date = datetime.utcnow()
    if time_range == "day":
        start_date = end_date - timedelta(days=1)
    elif time_range == "week":
        start_date = end_date - timedelta(weeks=1)
    elif time_range == "month":
        start_date = end_date - timedelta(days=30)
    elif time_range == "quarter":
        start_date = end_date - timedelta(days=90)
    else:  # year
        start_date = end_date - timedelta(days=365)
    
    # Total statistics
    total_users = db.query(User).filter(User.is_active == True).count()
    total_departments = db.query(Department).count()
    total_skills = db.query(Skill).count()
    
    # Assessment statistics
    total_assessments = db.query(SkillAssessment).count()
    pending_assessments = db.query(SkillAssessment).filter(
        SkillAssessment.status == 'pending'
    ).count()
    
    approved_assessments = db.query(SkillAssessment).filter(
        SkillAssessment.status == 'approved'
    ).count()
    
    avg_score = 0
    if approved_assessments > 0:
        avg_score_result = db.query(
            func.avg(SkillAssessment.self_score)
        ).filter(SkillAssessment.status == 'approved').scalar()
        avg_score = float(avg_score_result) if avg_score_result else 0
    
    # Recent activity
    recent_assessments = db.query(SkillAssessment).filter(
        SkillAssessment.assessed_at >= start_date
    ).count()
    
    recent_users = db.query(User).filter(
        User.created_at >= start_date
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
        
        dept_avg_score = 0
        if dept_assessments > 0:
            score_result = db.query(
                func.avg(SkillAssessment.self_score)
            ).join(User).filter(
                User.department_id == dept.id,
                SkillAssessment.status == 'approved'
            ).scalar()
            dept_avg_score = float(score_result) if score_result else 0
        
        department_stats.append({
            "id": dept.id,
            "name": dept.name,
            "user_count": dept_users,
            "assessment_count": dept_assessments,
            "average_score": round(dept_avg_score, 2)
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
        
        cat_avg_score = 0
        if cat_assessments > 0:
            score_result = db.query(
                func.avg(SkillAssessment.self_score)
            ).join(Skill).filter(
                Skill.category_id == category.id,
                SkillAssessment.status == 'approved'
            ).scalar()
            cat_avg_score = float(score_result) if score_result else 0
        
        category_stats.append({
            "id": category.id,
            "name": category.name,
            "skill_count": cat_skills,
            "assessment_count": cat_assessments,
            "average_score": round(cat_avg_score, 2),
            "color": category.color
        })
    
    # Activity trend (last 30 days)
    trend_data = []
    for i in range(30, -1, -1):
        date = end_date - timedelta(days=i)
        date_start = datetime(date.year, date.month, date.day, 0, 0, 0)
        date_end = datetime(date.year, date.month, date.day, 23, 59, 59)
        
        daily_assessments = db.query(SkillAssessment).filter(
            SkillAssessment.assessed_at >= date_start,
            SkillAssessment.assessed_at <= date_end
        ).count()
        
        trend_data.append({
            "date": date.date().isoformat(),
            "assessments": daily_assessments
        })
    
    return {
        "time_range": time_range,
        "total_stats": {
            "users": total_users,
            "departments": total_departments,
            "skills": total_skills,
            "assessments": total_assessments,
            "pending_assessments": pending_assessments,
            "approved_assessments": approved_assessments,
            "average_score": round(avg_score, 2)
        },
        "recent_activity": {
            "assessments": recent_assessments,
            "new_users": recent_users
        },
        "department_stats": department_stats,
        "category_stats": category_stats,
        "activity_trend": trend_data,
        "generated_at": datetime.utcnow().isoformat()
    }
