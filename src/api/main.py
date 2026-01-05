"""
Egyptian AI Medication Validation Engine - FastAPI REST API
Sprint 3-4: API Layer
"""
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from src.core.models import PatientContext, RenalImpairment, HepaticImpairment
from src.core.drug_database import init_drug_database, get_drug_database
from src.core.validation_service import get_validation_service, MedicationValidationService
from src.core.models import Prescription, PrescriptionItem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for API
class PatientContextRequest(BaseModel):
    age: Optional[int] = Field(None, ge=0, le=150)
    weight_kg: Optional[float] = Field(None, ge=0, le=500)
    height_cm: Optional[float] = Field(None, ge=0, le=300)
    sex: Optional[str] = Field(None, pattern="^[MF]$")
    serum_creatinine: Optional[float] = Field(None, ge=0)
    gfr: Optional[float] = Field(None, ge=0)
    renal_impairment: Optional[str] = "normal"
    hepatic_impairment: Optional[str] = "none"
    allergies: List[str] = []
    conditions: List[str] = []
    is_pregnant: bool = False
    is_breastfeeding: bool = False


class PrescriptionItemRequest(BaseModel):
    medication_id: int
    dose: str = ""
    frequency: str = ""
    duration: Optional[str] = None
    route: Optional[str] = None
    instructions: Optional[str] = None


class PrescriptionValidationRequest(BaseModel):
    prescription_id: Optional[str] = None
    patient: PatientContextRequest = PatientContextRequest()
    medications: List[PrescriptionItemRequest]
    prescriber_id: Optional[str] = None
    pharmacy_id: Optional[str] = None


class QuickCheckRequest(BaseModel):
    medication_ids: List[int]
    patient: Optional[PatientContextRequest] = None


class InteractionCheckRequest(BaseModel):
    medication1_id: int
    medication2_id: int


class InteractionResponse(BaseModel):
    drug1_name: str
    drug2_name: str
    severity: str
    mechanism: str
    management: str


class ValidationResponse(BaseModel):
    is_valid: bool
    prescription_id: Optional[str]
    medications_validated: int
    interactions: List[Dict[str, Any]]
    dosing_adjustments: List[Dict[str, Any]]
    contraindications: List[str]
    warnings: List[str]
    recommendations: List[str]
    validation_time_ms: float
    validated_at: str


class MedicationSearchResponse(BaseModel):
    id: int
    commercial_name: str
    generic_name: Optional[str]
    dosage_form: str
    strength: Optional[str]
    is_high_alert: bool


class HealthCheckResponse(BaseModel):
    status: str
    version: str
    medications_loaded: int
    timestamp: str


# Create FastAPI app
app = FastAPI(
    title="Egyptian AI Medication Validation Engine",
    description="AI-powered medication validation for drug interactions, dosing adjustments, and contraindication checking. Optimized for Egyptian medications (EDA registry).",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
validation_service: Optional[MedicationValidationService] = None
db_initialized = False


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global validation_service, db_initialized
    logger.info("Starting Egyptian AI Medication Validation Engine...")
    
    # Initialize drug database (will be loaded separately via /admin/load-database)
    validation_service = get_validation_service()
    logger.info("Validation service initialized")


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint"""
    return {
        "name": "Egyptian AI Medication Validation Engine",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthCheckResponse, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    drug_db = get_drug_database()
    return HealthCheckResponse(
        status="healthy" if db_initialized else "initializing",
        version="1.0.0",
        medications_loaded=len(drug_db.medications) if drug_db._loaded else 0,
        timestamp=datetime.now().isoformat()
    )


@app.post("/admin/load-database", tags=["Admin"])
async def load_database(filepath: str = "/data/cfgdrug.xlsx"):
    """Load Egyptian drug database from Excel file"""
    global db_initialized
    try:
        drug_db = init_drug_database(filepath)
        db_initialized = True
        return {
            "status": "success",
            "medications_loaded": len(drug_db.medications),
            "statistics": drug_db.get_statistics()
        }
    except Exception as e:
        logger.error(f"Failed to load database: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/medications/search", response_model=List[MedicationSearchResponse], tags=["Medications"])
async def search_medications(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, ge=1, le=100)
):
    """Search medications by name, generic name, or ingredient"""
    results = validation_service.search_medications(q, limit)
    return results


@app.get("/medications/{medication_id}", tags=["Medications"])
async def get_medication(medication_id: int):
    """Get detailed medication information"""
    info = validation_service.get_medication_info(medication_id)
    if not info:
        raise HTTPException(status_code=404, detail="Medication not found")
    return info


@app.post("/validate/prescription", response_model=ValidationResponse, tags=["Validation"])
async def validate_prescription(request: PrescriptionValidationRequest):
    """
    Validate a complete prescription for drug interactions and dosing adjustments.
    
    This is the main validation endpoint that checks:
    - Drug-Drug Interactions (DDI)
    - Renal/Hepatic Dose Adjustments
    - Contraindications based on patient conditions
    - High-alert medication warnings
    """
    # Convert request to internal models
    patient = PatientContext(
        age=request.patient.age,
        weight_kg=request.patient.weight_kg,
        height_cm=request.patient.height_cm,
        sex=request.patient.sex,
        serum_creatinine=request.patient.serum_creatinine,
        gfr=request.patient.gfr,
        renal_impairment=RenalImpairment(request.patient.renal_impairment),
        hepatic_impairment=HepaticImpairment(request.patient.hepatic_impairment),
        allergies=request.patient.allergies,
        conditions=request.patient.conditions,
        is_pregnant=request.patient.is_pregnant,
        is_breastfeeding=request.patient.is_breastfeeding
    )
    
    items = [
        PrescriptionItem(
            medication_id=med.medication_id,
            medication_name="",
            dose=med.dose,
            frequency=med.frequency,
            duration=med.duration,
            route=med.route,
            instructions=med.instructions
        )
        for med in request.medications
    ]
    
    prescription = Prescription(
        id=request.prescription_id or f"rx-{datetime.now().timestamp()}",
        patient=patient,
        items=items,
        prescriber_id=request.prescriber_id,
        pharmacy_id=request.pharmacy_id
    )
    
    # Validate
    result = validation_service.validate_prescription(prescription)
    
    # Convert to response
    return ValidationResponse(
        is_valid=result.is_valid,
        prescription_id=result.prescription_id,
        medications_validated=result.medications_validated,
        interactions=[
            {
                "drug1": i.drug1_name,
                "drug2": i.drug2_name,
                "severity": i.severity.value,
                "mechanism": i.mechanism,
                "management": i.management,
                "evidence_level": i.evidence_level
            }
            for i in result.interactions
        ],
        dosing_adjustments=[
            {
                "medication": da.medication_name,
                "standard_dose": da.standard_dose,
                "adjusted_dose": da.adjusted_dose,
                "reason": da.adjustment_reason,
                "impairment_type": da.impairment_type,
                "impairment_level": da.impairment_level,
                "monitoring_required": da.monitoring_required,
                "monitoring_parameters": da.monitoring_parameters,
                "contraindicated": da.contraindicated
            }
            for da in result.dosing_adjustments
        ],
        contraindications=result.contraindications,
        warnings=result.warnings,
        recommendations=result.recommendations,
        validation_time_ms=result.validation_time_ms,
        validated_at=result.validated_at.isoformat()
    )


@app.post("/validate/quick", response_model=ValidationResponse, tags=["Validation"])
async def quick_validate(request: QuickCheckRequest):
    """
    Quick validation of medication IDs without full prescription context.
    Useful for real-time checking during prescription entry.
    """
    patient = None
    if request.patient:
        patient = PatientContext(
            age=request.patient.age,
            weight_kg=request.patient.weight_kg,
            sex=request.patient.sex,
            serum_creatinine=request.patient.serum_creatinine,
            gfr=request.patient.gfr,
            renal_impairment=RenalImpairment(request.patient.renal_impairment or "normal"),
        )
    
    result = validation_service.validate_medication_list(
        request.medication_ids,
        patient
    )
    
    return ValidationResponse(
        is_valid=result.is_valid,
        prescription_id=result.prescription_id,
        medications_validated=result.medications_validated,
        interactions=[
            {
                "drug1": i.drug1_name,
                "drug2": i.drug2_name,
                "severity": i.severity.value,
                "mechanism": i.mechanism,
                "management": i.management,
                "evidence_level": i.evidence_level
            }
            for i in result.interactions
        ],
        dosing_adjustments=[
            {
                "medication": da.medication_name,
                "adjusted_dose": da.adjusted_dose,
                "reason": da.adjustment_reason,
                "contraindicated": da.contraindicated
            }
            for da in result.dosing_adjustments
        ],
        contraindications=result.contraindications,
        warnings=result.warnings,
        recommendations=result.recommendations,
        validation_time_ms=result.validation_time_ms,
        validated_at=result.validated_at.isoformat()
    )


@app.post("/validate/interaction", response_model=List[InteractionResponse], tags=["Validation"])
async def check_interaction(request: InteractionCheckRequest):
    """
    Check for interactions between two specific medications.
    Returns empty list if no interactions found.
    """
    interactions = validation_service.validate_medication_pair(
        request.medication1_id,
        request.medication2_id
    )
    
    return [
        InteractionResponse(
            drug1_name=i.drug1_name,
            drug2_name=i.drug2_name,
            severity=i.severity.value,
            mechanism=i.mechanism,
            management=i.management
        )
        for i in interactions
    ]


@app.get("/statistics", tags=["Admin"])
async def get_statistics():
    """Get database and service statistics"""
    drug_db = get_drug_database()
    if not drug_db._loaded:
        return {"status": "database_not_loaded"}
    
    return {
        "database": drug_db.get_statistics(),
        "service": {
            "ddi_rules_loaded": True,
            "dosing_rules_loaded": True
        }
    }


# Main entry point for running directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
