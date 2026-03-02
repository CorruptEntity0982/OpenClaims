"""
Patient routes for user registration and management
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.models.patient import Patient
from app.schemas import PatientCreate, PatientResponse
from app.services.auth_service import hash_password
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("/", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    patient_data: PatientCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new patient account
    
    Validates:
    - Email is unique and valid format
    - Username is unique
    - Password is at least 8 characters
    
    Returns created patient information (without password)
    """
    try:
        # Check if email already exists
        existing_patient = db.query(Patient).filter(Patient.email == patient_data.email).first()
        if existing_patient:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Check if username already exists
        existing_username = db.query(Patient).filter(Patient.username == patient_data.username).first()
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        
        # Create new patient with hashed password
        new_patient = Patient(
            name=patient_data.name,
            email=patient_data.email,
            username=patient_data.username,
            password_hash=hash_password(patient_data.password)
        )
        
        db.add(new_patient)
        db.commit()
        db.refresh(new_patient)
        
        logger.info(f"Created new patient: {new_patient.username} (ID: {new_patient.id})")
        return new_patient
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already exists"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating patient: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create patient account"
        )


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """Get patient information by ID"""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    return patient
