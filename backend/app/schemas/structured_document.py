"""
Pydantic schemas for structured medical document extraction
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import date


class PatientInfo(BaseModel):
    """Patient information extracted from medical document"""
    patient_id: str = Field(..., description="Unique patient identifier")
    name: Optional[str] = Field(None, description="Patient full name")
    dob: Optional[date] = Field(None, description="Date of birth (YYYY-MM-DD)")
    gender: Optional[str] = Field(None, description="Patient gender (M/F/Other)")
    insurance_policy_id: Optional[str] = Field(None, description="Insurance policy number")


class EncounterInfo(BaseModel):
    """Medical encounter/visit information"""
    encounter_id: str = Field(..., description="Unique encounter/visit identifier")
    admission_date: Optional[date] = Field(None, description="Admission date (YYYY-MM-DD)")
    discharge_date: Optional[date] = Field(None, description="Discharge date (YYYY-MM-DD)")
    visit_type: Optional[str] = Field(None, description="Type of visit (inpatient/outpatient/emergency)")
    department: Optional[str] = Field(None, description="Hospital department")


class ClaimInfo(BaseModel):
    """Insurance claim information"""
    claim_id: str = Field(..., description="Unique claim identifier")
    claim_amount: Optional[float] = Field(None, description="Total claim amount")
    approved_amount: Optional[float] = Field(None, description="Approved claim amount")
    status: Optional[str] = Field(None, description="Claim status (submitted/approved/rejected/pending)")
    insurer_name: Optional[str] = Field(None, description="Insurance company name")
    submission_date: Optional[date] = Field(None, description="Claim submission date (YYYY-MM-DD)")


class ConditionInfo(BaseModel):
    """Medical condition/diagnosis information"""
    condition_name: str = Field(..., description="Medical condition name")
    icd_code: Optional[str] = Field(None, description="ICD-10 diagnostic code")
    chronic: Optional[bool] = Field(None, description="Whether condition is chronic (only if explicitly stated)")


class HospitalInfo(BaseModel):
    """Hospital information"""
    hospital_id: Optional[str] = Field(None, description="Unique hospital identifier")
    name: Optional[str] = Field(None, description="Hospital name")
    city: Optional[str] = Field(None, description="Hospital city")


class StructuredMedicalDocument(BaseModel):
    """
    Complete structured medical document
    
    Validation ensures required IDs are present
    """
    patient: PatientInfo
    encounter: EncounterInfo
    claim: ClaimInfo
    conditions: List[ConditionInfo] = Field(default_factory=list, description="List of diagnosed conditions")
    hospital: HospitalInfo
    
    @validator('patient')
    def validate_patient_id(cls, v):
        """Ensure patient_id is present"""
        if not v.patient_id or not v.patient_id.strip():
            raise ValueError("patient_id is required and cannot be empty")
        return v
    
    @validator('encounter')
    def validate_encounter_id(cls, v):
        """Ensure encounter_id is present"""
        if not v.encounter_id or not v.encounter_id.strip():
            raise ValueError("encounter_id is required and cannot be empty")
        return v
    
    @validator('claim')
    def validate_claim_id(cls, v):
        """Ensure claim_id is present"""
        if not v.claim_id or not v.claim_id.strip():
            raise ValueError("claim_id is required and cannot be empty")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "patient": {
                    "patient_id": "P12345",
                    "name": "John Doe",
                    "dob": "1980-05-15",
                    "gender": "M",
                    "insurance_policy_id": "POL789456"
                },
                "encounter": {
                    "encounter_id": "ENC001",
                    "admission_date": "2026-01-15",
                    "discharge_date": "2026-01-17",
                    "visit_type": "inpatient",
                    "department": "Cardiology"
                },
                "claim": {
                    "claim_id": "CLM2026001",
                    "claim_amount": 50000.00,
                    "approved_amount": 45000.00,
                    "status": "approved",
                    "insurer_name": "National Health Insurance",
                    "submission_date": "2026-01-20"
                },
                "conditions": [
                    {
                        "condition_name": "Acute Myocardial Infarction",
                        "icd_code": "I21.0",
                        "chronic": False
                    }
                ],
                "hospital": {
                    "hospital_id": "HOSP001",
                    "name": "Apollo Hospital",
                    "city": "Mumbai"
                }
            }
        }
