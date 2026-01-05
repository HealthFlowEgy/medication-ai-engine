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

from src.nlp.arabic_processor import (
    ArabicDrugMatcher, ArabicPrescriptionParser, 
    is_arabic, ArabicDrugDatabase, get_arabic_search
)
from src.api.healthflow_adapter import HealthFlowAdapter, get_healthflow_adapter

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
    
    # Try to auto-load from processed JSON file
    json_paths = [
        "/app/data/processed/medications.json",
        "data/processed/medications.json",
        "/data/medications.json"
    ]
    
    drug_db = get_drug_database()
    for json_path in json_paths:
        try:
            import os
            if os.path.exists(json_path):
                count = drug_db.load_from_json(json_path)
                db_initialized = True
                logger.info(f"Auto-loaded {count} medications from {json_path}")
                break
        except Exception as e:
            logger.warning(f"Failed to auto-load from {json_path}: {e}")
    
    # Initialize validation service
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
            "dosing_rules_loaded": True,
            "arabic_nlp_enabled": True
        }
    }


# ============================================================================
# ARABIC NLP ENDPOINTS (Sprint 6)
# ============================================================================

class ArabicSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Arabic drug name to search")
    limit: int = Field(20, ge=1, le=100)


class ArabicPrescriptionRequest(BaseModel):
    prescription_text: str = Field(..., description="Arabic prescription text to parse")


@app.get("/arabic/search", tags=["Arabic NLP"])
async def search_arabic(
    q: str = Query(..., min_length=1, description="Arabic drug name"),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Search medications using Arabic drug names.
    Supports Arabic characters and translates to English equivalents.
    """
    drug_db = get_drug_database()
    
    if not drug_db._loaded:
        raise HTTPException(status_code=503, detail="Database not loaded")
    
    # Check if query contains Arabic
    arabic_search = get_arabic_search()
    if is_arabic(q):
        # Use Arabic-enhanced search
        search_results = arabic_search.search(q, limit)
        # Convert search results to medication objects
        results = []
        for sr in search_results:
            med = drug_db.get_medication(sr.get('id', 0))
            if med:
                results.append(med)
    else:
        # Fall back to standard search
        results = drug_db.search(q, limit)
    
    return [
        {
            "id": med.id,
            "commercial_name": med.commercial_name,
            "generic_name": med.generic_name,
            "arabic_name": arabic_search.translate_drug_name(med.commercial_name),
            "dosage_form": med.dosage_form.value,
            "strength": med.strength
        }
        for med in results
    ]


@app.post("/arabic/parse-prescription", tags=["Arabic NLP"])
async def parse_arabic_prescription(request: ArabicPrescriptionRequest):
    """
    Parse Arabic prescription text and extract medications.
    Returns structured data with English equivalents.
    """
    parser = ArabicPrescriptionParser()
    result = parser.parse(request.prescription_text)
    
    return {
        "original_text": result["original_text"],
        "medications_found": len(result["medications"]),
        "medications": result["medications"],
        "instructions": result.get("instructions", [])
    }


@app.get("/arabic/translate/{drug_name}", tags=["Arabic NLP"])
async def translate_drug(drug_name: str, to_arabic: bool = True):
    """
    Translate drug name between Arabic and English.
    
    Args:
        drug_name: Drug name to translate
        to_arabic: If true, translate English to Arabic. Otherwise Arabic to English.
    """
    from src.nlp.arabic_processor import translate_drug_name
    
    translation = translate_drug_name(drug_name, to_arabic=to_arabic)
    
    if translation:
        return {
            "input": drug_name,
            "translation": translation,
            "direction": "en_to_ar" if to_arabic else "ar_to_en"
        }
    else:
        return {
            "input": drug_name,
            "translation": None,
            "error": "Translation not found"
        }


# ============================================================================
# HEALTHFLOW INTEGRATION ENDPOINTS (Sprint 5)
# ============================================================================

class HealthFlowWebhookConfig(BaseModel):
    webhook_url: str = Field(..., description="URL to send validation alerts")
    api_key: Optional[str] = Field(None, description="Optional API key for webhook auth")
    alert_on_major: bool = Field(True, description="Send alerts for MAJOR interactions")
    alert_on_contraindicated: bool = Field(True, description="Send alerts for contraindicated meds")


@app.post("/healthflow/validate", tags=["HealthFlow Integration"])
async def healthflow_validate(request: dict):
    """
    Validate prescription in HealthFlow format.
    
    This endpoint accepts the HealthFlow Unified System prescription format
    and returns validation results in HealthFlow-compatible format.
    """
    adapter = get_healthflow_adapter()
    
    try:
        result = adapter.validate_from_json(request)
        return result
    except Exception as e:
        logger.error(f"HealthFlow validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/healthflow/webhook/configure", tags=["HealthFlow Integration"])
async def configure_healthflow_webhook(config: HealthFlowWebhookConfig):
    """
    Configure webhook for HealthFlow alerts.
    
    When prescriptions with MAJOR interactions or contraindicated medications
    are detected, alerts will be sent to the configured webhook URL.
    """
    # In production, this would persist to database
    return {
        "status": "configured",
        "webhook_url": config.webhook_url,
        "alert_on_major": config.alert_on_major,
        "alert_on_contraindicated": config.alert_on_contraindicated
    }


@app.get("/healthflow/status", tags=["HealthFlow Integration"])
async def healthflow_status():
    """Get HealthFlow integration status"""
    return {
        "integration_enabled": True,
        "api_version": "1.0.0",
        "supported_formats": ["healthflow_v1", "fhir_r4"],
        "features": {
            "ddi_detection": True,
            "dosing_adjustment": True,
            "arabic_support": True,
            "webhook_alerts": True
        }
    }


# ==================== Arabic NLP Endpoints ====================

@app.post("/arabic/parse", tags=["Arabic NLP"])
async def parse_arabic_prescription(text: str):
    """
    Parse Arabic prescription text into structured data.
    
    Extracts medication names, doses, frequencies, and routes from
    Arabic prescription text.
    """
    from src.nlp.arabic_processor import get_arabic_parser
    
    parser = get_arabic_parser()
    results = parser.parse_prescription(text)
    
    return {
        "parsed_items": [
            {
                "original_text": r.original_text,
                "medication_arabic": r.medication_name_ar,
                "medication_english": r.medication_name_en,
                "dose": f"{r.dose_value} {r.dose_unit}" if r.dose_value else None,
                "form": r.dosage_form,
                "frequency": r.frequency,
                "route": r.route,
                "confidence": r.confidence
            }
            for r in results
        ],
        "total_items": len(results)
    }


@app.get("/arabic/search", tags=["Arabic NLP"])
async def search_arabic_medications(
    q: str = Query(..., min_length=2, description="Arabic or English search query"),
    limit: int = Query(10, ge=1, le=50)
):
    """
    Search medications in Arabic or English.
    
    Supports Arabic drug names like 'باراسيتامول' and returns
    both Arabic and English names.
    """
    from src.nlp.arabic_processor import get_arabic_search
    
    search = get_arabic_search()
    results = search.search(q, limit)
    
    return {
        "query": q,
        "results": results,
        "count": len(results)
    }


@app.get("/arabic/translate", tags=["Arabic NLP"])
async def translate_drug_name(name: str):
    """
    Translate drug name between Arabic and English.
    """
    from src.nlp.arabic_processor import get_arabic_search, ArabicTextProcessor
    
    search = get_arabic_search()
    
    is_arabic = ArabicTextProcessor.is_arabic(name)
    translation = search.translate_drug_name(name)
    
    return {
        "input": name,
        "input_language": "arabic" if is_arabic else "english",
        "translation": translation,
        "output_language": "english" if is_arabic else "arabic"
    }


# Include HealthFlow integration routes
try:
    from src.api.healthflow_routes import router as healthflow_router
    app.include_router(healthflow_router)
    logger.info("HealthFlow integration routes loaded")
except ImportError as e:
    logger.warning(f"HealthFlow routes not available: {e}")


# Main entry point for running directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
