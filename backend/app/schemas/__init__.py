"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from typing import Optional
from uuid import UUID


# Patient Schemas
class PatientCreate(BaseModel):
    """Schema for creating a new patient"""
    name: str = Field(..., min_length=1, max_length=255, description="Patient's full name")
    email: EmailStr = Field(..., description="Valid email address")
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    password: str = Field(..., min_length=8, max_length=72, description="Password (8-72 characters)")


class PatientResponse(BaseModel):
    """Schema for patient response"""
    id: str
    name: str
    email: str
    username: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Document Schemas
class DocumentUpload(BaseModel):
    """Schema for document upload (validated after processing)"""
    patient_id: str = Field(..., description="Patient UUID")


class DocumentResponse(BaseModel):
    """Schema for document response"""
    id: UUID
    patient_id: str
    file_name: str
    s3_key: str
    file_size: Optional[int] = None
    page_count: Optional[int] = None
    status: str
    extracted_text: Optional[str] = None
    extraction_confidence: Optional[float] = None
    error_message: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
