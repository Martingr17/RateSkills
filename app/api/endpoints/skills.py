from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case
import logging

from app.database import get_db
from app.models import Skill, SkillCategory, SkillAssessment, User, Department
from app.schemas import (
    SkillCreate, SkillResponse, SkillUpdate,
    SkillCategoryCreate, SkillCategoryResponse, SkillCategoryUpdate,
    SkillWithStats, CategoryWithSkills, SkillMatrix
)
from app.api.endpoints.auth import get_current_active_user, check_admin_permission

router = APIRouter(prefix="/skills", tags=["skills"])
logger = logging.getLogger(__name__)

# ========== Skill Categories ==========

@router.get("/categories", response_model=List[SkillCategoryResponse])
async def get_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all skill categories"""
    categories = db.query(SkillCategory).order_by(SkillCategory.name).all()
    return categories

@router.get("/categories/{category_id}", response_model=SkillCategoryResponse)
async def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get skill category by ID"""
    category = db.query(SkillCategory).filter(SkillCategory.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    return category

@router.post("/categories", response_model=SkillCategoryResponse)
async def create_category(
    category_data: SkillCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_permission)
):
    """Create new skill category (Admin/HR only)"""
    # Check if category with same name exists
    existing = db.query(SkillCategory).filter(
        func.lower(SkillCategory.name) == func.lower(category_data.name)
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category with this name already exists"
        )
    
    category = SkillCategory(**category_data.dict())
    db.add(category)
    db.commit()
    db.refresh(category)
    
    return category

@router.put("/categories/{category_id}", response_model=SkillCategoryResponse)
async def update_category(
    category_id: int,
    category_update: SkillCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_permission)
):
    """Update skill category (Admin/HR only)"""
    category = db.query(SkillCategory).filter(SkillCategory.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Check if new name conflicts with existing
    if category_update.name and category_update.name != category.name:
        existing = db.query(SkillCategory).filter(
            func.lower(SkillCategory.name) == func.lower(category_update.name),
            SkillCategory.id != category_id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category with this name already exists"
            )
    
    # Update fields
    update_data = category_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)
    
    db.commit()
    db.refresh(category)
    
    return category

@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_permission)
):
    """Delete skill category (Admin only)"""
    category = db.query(SkillCategory).filter(SkillCategory.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Check if category has skills
    skill_count = db.query(Skill).filter(Skill.category_id == category_id).count()
    if skill_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete category with {skill_count} skills. Move skills first."
        )
    
    db.delete(category)
    db.commit()
    
    return {"message": "Category deleted successfully"}

@router.get("/categories/{category_id}/skills", response_model=CategoryWithSkills)
async def get_category_with_skills(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get category with all its skills"""
    category = db.query(SkillCategory).filter(SkillCategory.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    skills = db.query(Skill).filter(
        Skill.category_id == category_id
    ).order_by(Skill.name).all()
    
    return CategoryWithSkills(
        **category.__dict__,
        skills=skills
    )

# ========== Skills ==========

@router.get("/", response_model=List[SkillResponse])
async def get_skills(
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    required_for_department: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all skills with optional filtering"""
    query = db.query(Skill)
    
    if category_id:
        query = query.filter(Skill.category_id == category_id)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Skill.name.ilike(search_term)) |
            (Skill.description.ilike(search_term))
        )
    
    if required_for_department:
        query = query.filter(Skill.required_for_departments.any(id=required_for_department))
    
    skills = query.order_by(Skill.name).all()
    return skills

@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get skill by ID"""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found"
        )
    return skill

@router.get("/{skill_id}/stats", response_model=SkillWithStats)
async def get_skill_with_stats(
    skill_id: int,
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get skill with statistics"""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found"
        )
    
    # Get assessments for this skill
    query = db.query(SkillAssessment).filter(SkillAssessment.skill_id == skill_id)
    
    if department_id:
        query = query.join(User).filter(User.department_id == department_id)
    
    assessments = query.all()
    
    # Calculate statistics
    total_assessments = len(assessments)
    approved_assessments = [a for a in assessments if a.status == 'approved']
    
    avg_score = 0
    score_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    
    if approved_assessments:
        avg_score = sum(a.self_score for a in approved_assessments) / len(approved_assessments)
        for a in approved_assessments:
            score_distribution[a.self_score] += 1
    
    pending_count = len([a for a in assessments if a.status == 'pending'])
    
    # Get departments that require this skill
    requiring_departments = db.query(Department).filter(
        Department.id.in_(skill.required_for_departments)
    ).all() if skill.required_for_departments else []
    
    return SkillWithStats(
        **skill.__dict__,
        total_assessments=total_assessments,
        approved_assessments=len(approved_assessments),
        pending_assessments=pending_count,
        average_score=round(avg_score, 2),
        score_distribution=score_distribution,
        requiring_departments=[d.name for d in requiring_departments]
    )

@router.post("/", response_model=SkillResponse)
async def create_skill(
    skill_data: SkillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_permission)
):
    """Create new skill (Admin/HR only)"""
    # Check if skill with same name exists
    existing = db.query(Skill).filter(
        func.lower(Skill.name) == func.lower(skill_data.name)
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Skill with this name already exists"
        )
    
    # Check if category exists
    if skill_data.category_id:
        category = db.query(SkillCategory).filter(SkillCategory.id == skill_data.category_id).first()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category not found"
            )
    
    skill = Skill(**skill_data.dict())
    db.add(skill)
    db.commit()
    db.refresh(skill)
    
    return skill

@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: int,
    skill_update: SkillUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_permission)
):
    """Update skill (Admin/HR only)"""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found"
        )
    
    # Check if new name conflicts with existing
    if skill_update.name and skill_update.name != skill.name:
        existing = db.query(Skill).filter(
            func.lower(Skill.name) == func.lower(skill_update.name),
            Skill.id != skill_id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Skill with this name already exists"
            )
    
    # Update fields
    update_data = skill_update.dict(exclude_unset=True)
    
    # Handle required_for_departments
    if 'required_for_departments' in update_data:
        # Get department objects
        departments = db.query(Department).filter(
            Department.id.in_(update_data['required_for_departments'])
        ).all()
        
        if len(departments) != len(update_data['required_for_departments']):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more departments not found"
            )
        
        update_data['required_for_departments'] = departments
    
    for field, value in update_data.items():
        setattr(skill, field, value)
    
    db.commit()
    db.refresh(skill)
    
    return skill

@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_permission)
):
    """Delete skill (Admin only)"""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found"
        )
    
    # Check if skill has assessments
    assessment_count = db.query(SkillAssessment).filter(SkillAssessment.skill_id == skill_id).count()
    if assessment_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete skill with {assessment_count} assessments"
        )
    
    db.delete(skill)
    db.commit()
    
    return {"message": "Skill deleted successfully"}

@router.get("/matrix", response_model=SkillMatrix)
async def get_skill_matrix(
    department_id: Optional[int] = None,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get skill matrix with department requirements"""
    # Get all skills
    query = db.query(Skill)
    
    if category_id:
        query = query.filter(Skill.category_id == category_id)
    
    skills = query.order_by(Skill.name).all()
    
    # Get all departments
    departments = db.query(Department).order_by(Department.name).all()
    
    # Build matrix
    matrix = {}
    for skill in skills:
        matrix[skill.id] = {
            "skill": skill,
            "departments": {}
        }
        for department in departments:
            is_required = department in skill.required_for_departments
            matrix[skill.id]["departments"][department.id] = is_required
    
    return SkillMatrix(
        skills=skills,
        departments=departments,
        matrix=matrix
    )

@router.get("/required/{department_id}", response_model=List[SkillResponse])
async def get_required_skills_for_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get skills required for specific department"""
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    # Check permissions
    if (current_user.role in ['employee'] and 
        current_user.department_id != department_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view required skills for your own department"
        )
    
    skills = db.query(Skill).filter(
        Skill.required_for_departments.any(id=department_id)
    ).order_by(Skill.name).all()
    
    return skills

@router.post("/{skill_id}/required/{department_id}")
async def add_skill_requirement(
    skill_id: int,
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_permission)
):
    """Add skill requirement for department (Admin/HR only)"""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    department = db.query(Department).filter(Department.id == department_id).first()
    
    if not skill or not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill or department not found"
        )
    
    if department not in skill.required_for_departments:
        skill.required_for_departments.append(department)
        db.commit()
    
    return {"message": "Skill requirement added successfully"}

@router.delete("/{skill_id}/required/{department_id}")
async def remove_skill_requirement(
    skill_id: int,
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_permission)
):
    """Remove skill requirement for department (Admin/HR only)"""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    department = db.query(Department).filter(Department.id == department_id).first()
    
    if not skill or not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill or department not found"
        )
    
    if department in skill.required_for_departments:
        skill.required_for_departments.remove(department)
        db.commit()
    
    return {"message": "Skill requirement removed successfully"}