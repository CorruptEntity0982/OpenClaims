"""
Document routes for PDF upload and management
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.patient import Patient
from app.models.document import Document, DocumentStatus
from app.schemas import DocumentResponse
from app.services.graph_service import graph_service
from app.services.s3_service import s3_service
from app.services.pdf_service import validate_pdf
from celery_worker import celery_app
import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    limit: int = 100,
    offset: int = 0,
    status: str | None = None,
    db: Session = Depends(get_db)
):
    """
    List all documents with optional filtering
    
    Query params:
    - limit: Maximum number of documents to return (default 100)
    - offset: Number of documents to skip (default 0)
    - status: Filter by document status (uploaded/processing/completed/failed)
    """
    query = db.query(Document)
    
    # Filter by status if provided
    if status:
        try:
            status_enum = DocumentStatus(status.lower())
            query = query.filter(Document.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {[s.value for s in DocumentStatus]}"
            )
    
    # Order by created_at descending (newest first)
    documents = query.order_by(Document.created_at.desc()).offset(offset).limit(limit).all()
    return documents


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


@router.get("/{document_id}/graph")
async def get_document_graph(
    document_id: str,
    db: Session = Depends(get_db),
):
    """
    Get graph data for a specific document using its structured patient_id.

    This looks up the document, reads `structured_data.patient.patient_id`,
    and then queries Neo4j for that clinical graph.
    """
    # Fetch the document and ensure structured data exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if not document.structured_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Structured data not available for this document",
        )

    patient_struct = document.structured_data.get("patient") or {}
    structured_patient_id = patient_struct.get("patient_id")

    if not structured_patient_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Structured patient_id missing from document data",
        )

    if not graph_service.driver:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph database is unavailable",
        )

    try:
        with graph_service.driver.session() as session:
            query = """
            MATCH path = (p:Patient {patient_id: $patient_id})-[*1..2]-(n)
            WITH p, collect(DISTINCT n) as nodes, collect(DISTINCT relationships(path)) as rels
            RETURN 
                p as patient_node,
                nodes,
                rels
            """

            result = session.run(query, patient_id=structured_patient_id)
            record = result.single()

            if not record:
                return {
                    "nodes": [],
                    "relationships": [],
                    "message": "No graph data found for this document",
                }

            formatted_nodes = []
            formatted_relationships = []

            patient_node = dict(record["patient_node"])
            formatted_nodes.append(
                {
                    "id": patient_node.get("patient_id"),
                    "label": "Patient",
                    "properties": patient_node,
                }
            )

            for node in record["nodes"]:
                node_dict = dict(node)
                node_labels = list(node.labels)
                node_id = (
                    node_dict.get("encounter_id")
                    or node_dict.get("claim_id")
                    or node_dict.get("condition_name")
                    or node_dict.get("name")
                )

                formatted_nodes.append(
                    {
                        "id": node_id,
                        "label": node_labels[0] if node_labels else "Unknown",
                        "properties": node_dict,
                    }
                )

            for rel_array in record["rels"]:
                for rel in rel_array:
                    formatted_relationships.append(
                        {
                            "source": rel.start_node.get("patient_id")
                            or rel.start_node.get("encounter_id")
                            or rel.start_node.get("claim_id")
                            or rel.start_node.get("condition_name")
                            or rel.start_node.get("name"),
                            "target": rel.end_node.get("encounter_id")
                            or rel.end_node.get("claim_id")
                            or rel.end_node.get("condition_name")
                            or rel.end_node.get("name"),
                            "type": rel.type,
                        }
                    )

            return {
                "nodes": formatted_nodes,
                "relationships": formatted_relationships,
            }
    except Exception as e:
        logger.error(f"Error fetching graph data for document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch graph data: {str(e)}",
        )


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
