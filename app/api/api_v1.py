from fastapi import APIRouter

from app.api.endpoints import (
    auth, users, skills, assessments, reports, dashboard
)

api_router = APIRouter(prefix="/api/v1")

# Include all endpoint routers
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(skills.router)
api_router.include_router(assessments.router)
api_router.include_router(reports.router)
api_router.include_router(dashboard.router)

# Health check endpoint
@api_router.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "version": "3.0.0",
        "service": "skillmatrix-backend"
    }

# Root endpoint
@api_router.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Welcome to SkillMatrix API v3.0",
        "version": "3.0.0",
        "docs": "/api/v1/docs",
        "endpoints": {
            "auth": "/api/v1/auth",
            "users": "/api/v1/users",
            "skills": "/api/v1/skills",
            "assessments": "/api/v1/assessments",
            "reports": "/api/v1/reports",
            "dashboard": "/api/v1/dashboard"
        }
    }