"""
PDF validation utilities
"""
from pypdf import PdfReader
from io import BytesIO
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def validate_pdf(file_content: bytes, max_pages: int = 40) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Validate PDF file
    
    Args:
        file_content: PDF file content as bytes
        max_pages: Maximum allowed pages (default 40)
        
    Returns:
        Tuple of (is_valid, page_count, error_message)
    """
    try:
        # Create PDF reader from bytes
        pdf_reader = PdfReader(BytesIO(file_content))
        page_count = len(pdf_reader.pages)
        
        # Validate page count
        if page_count == 0:
            return False, 0, "PDF file is empty"
        
        if page_count > max_pages:
            return False, page_count, f"PDF exceeds maximum allowed pages ({max_pages})"
        
        return True, page_count, None
        
    except Exception as e:
        logger.error(f"PDF validation error: {str(e)}")
        return False, None, f"Invalid PDF file: {str(e)}"


def get_pdf_page_count(file_content: bytes) -> Optional[int]:
    """
    Get page count from PDF
    
    Args:
        file_content: PDF file content as bytes
        
    Returns:
        Number of pages or None if error
    """
    try:
        pdf_reader = PdfReader(BytesIO(file_content))
        return len(pdf_reader.pages)
    except Exception as e:
        logger.error(f"Failed to get PDF page count: {str(e)}")
        return None
