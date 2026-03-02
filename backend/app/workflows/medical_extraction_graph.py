"""
LangGraph workflow for medical document structured extraction

Simple linear workflow:
START → extract_node → validate_node → END
"""
from typing import TypedDict, Optional, Dict
from langgraph.graph import StateGraph, END
from app.services.llm_service import llm_service
from app.schemas.structured_document import StructuredMedicalDocument
from pydantic import ValidationError
import logging

logger = logging.getLogger(__name__)


class ExtractionState(TypedDict):
    """State for the extraction workflow"""
    raw_text: str
    structured_data: Optional[Dict]
    validation_error: Optional[str]


def extract_node(state: ExtractionState) -> ExtractionState:
    """
    Node 1: Extract structured data from raw text using LLM
    
    Args:
        state: Current workflow state with raw_text
        
    Returns:
        Updated state with structured_data or error
    """
    logger.info("Extraction node: Starting LLM extraction")
    
    raw_text = state.get("raw_text", "")
    
    if not raw_text or not raw_text.strip():
        logger.error("Extraction node: No raw text provided")
        state["validation_error"] = "No raw text provided for extraction"
        return state
    
    # Call LLM service to extract structured data
    structured_data = llm_service.extract_structured_data(raw_text)
    
    if structured_data is None:
        logger.error("Extraction node: LLM extraction returned None")
        state["validation_error"] = "LLM extraction failed to return structured data"
        return state
    
    state["structured_data"] = structured_data
    logger.info("Extraction node: Successfully extracted structured data")
    
    return state


def validate_node(state: ExtractionState) -> ExtractionState:
    """
    Node 2: Validate extracted data using Pydantic schema
    
    Args:
        state: Current workflow state with structured_data
        
    Returns:
        Updated state with validation result
    """
    logger.info("Validation node: Starting Pydantic validation")
    
    structured_data = state.get("structured_data")
    
    if structured_data is None:
        error_msg = "Validation node: No structured data to validate"
        logger.error(error_msg)
        state["validation_error"] = error_msg
        return state
    
    try:
        # Validate using Pydantic model
        validated_doc = StructuredMedicalDocument(**structured_data)
        
        # Convert back to dict for storage
        state["structured_data"] = validated_doc.model_dump(mode='json')
        state["validation_error"] = None
        
        logger.info("Validation node: Data validated successfully")
        logger.info(f"Validated patient_id: {validated_doc.patient.patient_id}")
        logger.info(f"Validated encounter_id: {validated_doc.encounter.encounter_id}")
        logger.info(f"Validated claim_id: {validated_doc.claim.claim_id}")
        logger.info(f"Number of conditions: {len(validated_doc.conditions)}")
        
    except ValidationError as e:
        error_msg = f"Validation failed: {str(e)}"
        logger.error(f"Validation node: {error_msg}")
        state["validation_error"] = error_msg
        # Keep the structured_data for debugging purposes
    
    except Exception as e:
        error_msg = f"Unexpected validation error: {str(e)}"
        logger.error(f"Validation node: {error_msg}")
        state["validation_error"] = error_msg
    
    return state


def build_extraction_workflow() -> StateGraph:
    """
    Build the LangGraph workflow for medical extraction
    
    Returns:
        Compiled StateGraph ready for execution
    """
    # Create workflow
    workflow = StateGraph(ExtractionState)
    
    # Add nodes
    workflow.add_node("extract", extract_node)
    workflow.add_node("validate", validate_node)
    
    # Define edges (linear flow)
    workflow.set_entry_point("extract")
    workflow.add_edge("extract", "validate")
    workflow.add_edge("validate", END)
    
    # Compile workflow
    app = workflow.compile()
    
    logger.info("Medical extraction workflow built successfully")
    
    return app


def run_extraction_workflow(raw_text: str) -> tuple[Optional[Dict], Optional[str]]:
    """
    Execute the medical extraction workflow
    
    Args:
        raw_text: Raw text from medical document
        
    Returns:
        Tuple of (structured_data dict, error_message)
        - If successful: (structured_data, None)
        - If failed: (None, error_message)
    """
    logger.info("Starting medical extraction workflow")
    
    try:
        # Build workflow
        app = build_extraction_workflow()
        
        # Initialize state
        initial_state = {
            "raw_text": raw_text,
            "structured_data": None,
            "validation_error": None
        }
        
        # Run workflow
        final_state = app.invoke(initial_state)
        
        # Check results
        if final_state.get("validation_error"):
            error_msg = final_state["validation_error"]
            logger.error(f"Workflow failed: {error_msg}")
            return None, error_msg
        
        structured_data = final_state.get("structured_data")
        
        if structured_data is None:
            logger.error("Workflow completed but no structured data produced")
            return None, "Extraction workflow produced no data"
        
        logger.info("Workflow completed successfully")
        return structured_data, None
        
    except Exception as e:
        error_msg = f"Workflow execution failed: {str(e)}"
        logger.exception(error_msg)
        return None, error_msg
