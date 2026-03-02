"""
Document model for storing uploaded file information
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class Document(Base):
    """Document model for PDFs uploaded by patients"""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String, nullable=False)
    s3_path = Column(String, nullable=False)  # Full S3 path/key
    file_size = Column(Integer)  # Size in bytes
    page_count = Column(Integer)  # Number of pages in PDF
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship to patient
    patient = relationship("Patient", back_populates="documents")

    def __repr__(self):
        return f"<Document(id={self.id}, patient_id={self.patient_id}, file_name={self.file_name})>"
