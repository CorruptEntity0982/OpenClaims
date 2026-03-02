"""
Database models package
Import all models here to ensure they are registered with SQLAlchemy Base
"""
from app.database import Base
from app.models.patient import Patient
from app.models.document import Document

__all__ = ["Base", "Patient", "Document"]
