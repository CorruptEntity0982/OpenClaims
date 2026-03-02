"""
Document model for storing uploaded file information
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Float, Text, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base
import uuid
import enum
from datetime import datetime


class DocumentStatus(str, enum.Enum):
    """Document processing status"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    """Document model for PDFs uploaded by patients"""
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    patient_id = Column(String, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String, nullable=False)
    s3_key = Column(String, nullable=False)  # S3 key/path
    file_size = Column(Integer)  # Size in bytes
    page_count = Column(Integer)  # Number of pages
    
    # Processing status
    status = Column(Enum(DocumentStatus), nullable=False, default=DocumentStatus.UPLOADED, index=True)
    
    # Extracted content
    extracted_text = Column(Text, nullable=True)
    extraction_confidence = Column(Float, nullable=True)
    
    # Structured data extracted by LLM
    structured_data = Column(JSONB, nullable=True)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)

    # Relationship to patient
    patient = relationship("Patient", back_populates="documents")

    def __repr__(self):
        return f"<Document(id={self.id}, patient_id={self.patient_id}, status={self.status})>"
