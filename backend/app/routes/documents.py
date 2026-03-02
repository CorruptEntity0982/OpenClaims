"""
Document routes for PDF upload and management
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.patient import Patient
from app.models.document import Document
from app.schemas import DocumentResponse
from app.services.s3_service import s3_service
from app.services.pdf_service import validate_pdf
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    patient_id: int = Form(..., description="Patient ID"),
    file: UploadFile = File(..., description="PDF file to upload"),
    db: Session = Depends(get_db)
):
    """
    Upload a PDF document for a patient
    
    Validates:
    - File is PDF format
    - PDF has 0-40 pages
    - Patient exists
    
    Uploads to S3 and stores metadata in database
    """
    try:
        # Validate patient exists
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found"
            )
        
        # Validate file type
        if file.content_type != "application/pdf":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are allowed"
            )
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Validate file size (e.g., max 50MB)
        max_size = 50 * 1024 * 1024  # 50MB
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds maximum allowed size (50MB)"
            )
        
        # Validate PDF and page count
        is_valid, page_count, error_msg = validate_pdf(file_content, max_pages=40)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg or "Invalid PDF file"
            )
        
        # Upload to S3
        s3_path = s3_service.upload_file(
            file_content=file_content,
            file_name=file.filename,
            patient_id=patient_id,
            content_type="application/pdf"
        )
        
        if not s3_path:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload file to S3"
            )
        
        # Create database record
        new_document = Document(
            patient_id=patient_id,
            file_name=file.filename,
            s3_path=s3_path,
            file_size=file_size,
            page_count=page_count
        )
        
        db.add(new_document)
        db.commit()
        db.refresh(new_document)
        
        logger.info(
            f"Uploaded document: {file.filename} ({page_count} pages) "
            f"for patient {patient_id} (Doc ID: {new_document.id})"
        )
        
        return new_document
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Get document information by ID"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    return document


@router.get("/patient/{patient_id}", response_model=list[DocumentResponse])
async def get_patient_documents(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """Get all documents for a specific patient"""
    # Verify patient exists
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {patient_id} not found"
        )
    
    documents = db.query(Document).filter(Document.patient_id == patient_id).all()
    return documents
