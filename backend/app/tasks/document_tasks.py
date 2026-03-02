"""
Celery tasks for document processing
"""
from celery import Task
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.document import Document, DocumentStatus
from app.services.textract_service import textract_service
from app.workflows.medical_extraction_graph import run_extraction_workflow
from app.schemas.structured_document import StructuredMedicalDocument
from app.services.graph_service import graph_service
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task with database session management"""
    _db = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


def process_document(document_id: str):
    """
    Process uploaded document: extract text, structure data, ingest into graph
    
    Workflow:
    1. Fetch document from DB
    2. Update status → "processing"
    3. Extract text using Textract (file is already in S3)
    4. Run LangGraph extraction workflow to get structured data
    5. Store structured data in DB
    6. Ingest structured data into Neo4j graph
    7. Update status → "completed"
    8. Handle errors → status "failed"
    
    Args:
        document_id: UUID of the document to process
    """
    db = SessionLocal()
    
    try:
        logger.info(f"Starting document processing: {document_id}")
        
        # 1. Fetch document from database
        document = db.query(Document).filter(Document.id == document_id).first()
        
        if not document:
            logger.error(f"Document not found: {document_id}")
            return
        
        # 2. Update status to processing
        document.status = DocumentStatus.PROCESSING
        db.commit()
        logger.info(f"Document {document_id} status updated to PROCESSING")
        
        # 3. Extract text using Textract (document is already in S3)
        extracted_text, confidence, error_msg = textract_service.extract_text_from_s3(
            s3_key=document.s3_key
        )
        
        if error_msg:
            # Extraction failed
            logger.error(f"Textract extraction failed for {document_id}: {error_msg}")
            document.status = DocumentStatus.FAILED
            document.error_message = f"Textract failed: {error_msg}"
            document.processed_at = datetime.utcnow()
            db.commit()
            return
        
        # Store extracted text
        document.extracted_text = extracted_text
        document.extraction_confidence = confidence
        db.commit()
        
        logger.info(
            f"Textract completed for {document_id}. "
            f"Extracted {len(extracted_text) if extracted_text else 0} characters"
        )
        
        # 4. Run LangGraph extraction workflow to get structured data
        logger.info(f"Starting LangGraph structured extraction for {document_id}")
        structured_data, extraction_error = run_extraction_workflow(extracted_text)
        
        if extraction_error:
            # LLM extraction failed
            logger.error(f"LangGraph extraction failed for {document_id}: {extraction_error}")
            document.status = DocumentStatus.FAILED
            document.error_message = f"Structured extraction failed: {extraction_error}"
            document.processed_at = datetime.utcnow()
            db.commit()
            return
        
        # 5. Store structured data in database
        document.structured_data = structured_data
        db.commit()
        
        logger.info(f"Structured data extracted and stored for {document_id}")
        
        # 6. Ingest structured data into Neo4j graph
        logger.info(f"Starting Neo4j graph ingestion for {document_id}")
        
        try:
            # Parse structured data into Pydantic model
            structured_doc = StructuredMedicalDocument(**structured_data)
            
            # Ingest into Neo4j
            ingestion_success = graph_service.ingest_structured_document(structured_doc)
            
            if not ingestion_success:
                logger.warning(f"Neo4j ingestion reported failure for {document_id}, but continuing...")
                # Don't fail the entire task if Neo4j ingestion fails
                # The data is already in Postgres
            else:
                logger.info(f"Successfully ingested {document_id} into Neo4j graph")
                
        except Exception as graph_error:
            logger.error(f"Neo4j ingestion error for {document_id}: {str(graph_error)}")
            # Continue - don't fail the task if graph ingestion fails
            # The structured data is still in Postgres
        
        # 7. Update status to completed
        document.status = DocumentStatus.COMPLETED
        document.processed_at = datetime.utcnow()
        db.commit()
        
        logger.info(
            f"Document {document_id} processing completed successfully. "
            f"Textract confidence: {confidence:.2f}%" if confidence else "N/A"
        )
        
    except Exception as e:
        # Handle unexpected errors
        error_msg = f"Unexpected error processing document: {str(e)}"
        logger.exception(error_msg)
        
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                document.status = DocumentStatus.FAILED
                document.error_message = error_msg
                document.processed_at = datetime.utcnow()
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update document status after error: {db_error}")
    
    finally:
        db.close()
