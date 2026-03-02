"""
Document routes for PDF upload and management
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.patient import Patient
from app.models.document import Document, DocumentStatus
from app.schemas import DocumentResponse
from app.services.s3_service import s3_service
from app.services.pdf_service import validate_pdf
from celery_worker import celery_app
import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    patient_id: str = Form(..., description="Patient UUID"),
    file: UploadFile = File(..., description="PDF file to upload"),
    db: Session = Depends(get_db)
):
    """
    Upload a PDF document for a patient
    
    Validates:
    - File is PDF format
    - PDF has 0-40 pages
    - Patient exists
    
    Uploads to S3, stores metadata in database, and enqueues Celery task for Textract processing
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
        s3_key = s3_service.upload_file(
            file_content=file_content,
            file_name=file.filename,
            patient_id=patient_id,
            content_type="application/pdf"
        )
        
        if not s3_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload file to S3"
            )
        
        # Create database record with UUID and initial status
        new_document = Document(
            patient_id=patient_id,
            file_name=file.filename,
            s3_key=s3_key,
            file_size=file_size,
            page_count=page_count,
            status=DocumentStatus.UPLOADED
        )
        
        db.add(new_document)
        db.commit()
        db.refresh(new_document)
        
        # Get the generated document ID
        document_id = str(new_document.id)
        
        # Enqueue Celery task for Textract processing
        celery_app.send_task("process_document", args=[document_id])
        
        logger.info(
            f"Uploaded document: {file.filename} ({page_count} pages) "
            f"for patient {patient_id} (Doc ID: {document_id}). Celery task enqueued."
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
    document_id: str,
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
    patient_id: str,
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
