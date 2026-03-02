"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from typing import Optional


# Patient Schemas
class PatientCreate(BaseModel):
    """Schema for creating a new patient"""
    name: str = Field(..., min_length=1, max_length=255, description="Patient's full name")
    email: EmailStr = Field(..., description="Valid email address")
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")


class PatientResponse(BaseModel):
    """Schema for patient response"""
    id: int
    name: str
    email: str
    username: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Document Schemas
class DocumentUpload(BaseModel):
    """Schema for document upload (validated after processing)"""
    patient_id: int = Field(..., gt=0, description="Patient ID")


class DocumentResponse(BaseModel):
    """Schema for document response"""
    id: int
    patient_id: int
    file_name: str
    s3_path: str
    file_size: Optional[int]
    page_count: Optional[int]
    uploaded_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
