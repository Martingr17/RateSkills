"""
SkillMatrix Backend Application
A comprehensive skills assessment and management system
"""

__version__ = "3.0.0"
__author__ = "SkillMatrix Team"
__description__ = "Enterprise Skills Management System"

# Import main components for easier access
from app.main import app
from app.database import SessionLocal, engine, Base
from app.config import settings