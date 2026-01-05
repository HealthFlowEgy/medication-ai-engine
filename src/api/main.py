"""
Egyptian AI Medication Validation Engine - FastAPI REST API
Sprint 3-4: API Layer with Authentication
"""
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import os

from src.core.models import PatientContext, RenalImpairment, HepaticImpairment
from src.core.drug_database import init_drug_database, get_drug_database, init_drug_database_from_json
from src.core.validation_service import get_validation_service, MedicationValidationService
from src.core.models import Prescription, PrescriptionItem
from src.api.auth import (
    AuthResult, verify_api_key, require_api_key, require_admin_key,
    generate_api_key, revoke_api_key, list_api_keys, APIKeyInfo
)
from src.api.webhooks import get_webhook_manager, WebhookConfig, WebhookEventType

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


class GenerateKeyRequest(BaseModel):
    name: str
    access_level: str = "standard"
    rate_limit: int = 1000


# Create FastAPI app
app = FastAPI(
    title="Egyptian AI Medication Validation Engine",
    description="""AI-powered medication validation for drug interactions, dosing adjustments, and contraindication checking. 
    Optimized for Egyptian medications (EDA registry).
    
    ## Authentication
    
    This API requires authentication via API key. Include your API key in one of these ways:
    - Header: `X-API-Key: your-api-key`
    - Query parameter: `?api_key=your-api-key`
    
    ## Access Levels
    
    - **admin**: Full access including key management
    - **full**: Read and write access to all validation endpoints
    - **standard**: Standard access for pharmacy integrations
    - **readonly**: Read-only access for demo purposes
    """,
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
    
    # Try to auto-load medication database from JSON
    json_paths = [
        "/app/data/processed/medications.json",
        "/data/processed/medications.json",
        "data/processed/medications.json"
    ]
    
    for json_path in json_paths:
        try:
            if os.path.exists(json_path):
                init_drug_database_from_json(json_path)
                db_initialized = True
                logger.info(f"✅ Auto-loaded medication database from {json_path}")
                break
        except Exception as e:
            logger.warning(f"Failed to load from {json_path}: {e}")
    
    if not db_initialized:
        logger.warning("⚠️ Medication database not auto-loaded. Use /admin/load-database endpoint.")
    
    # Initialize validation service
    validation_service = get_validation_service()
    logger.info("Validation service initialized")
    
    # Log authentication mode
    if os.getenv("DISABLE_AUTH", "false").lower() == "true":
        logger.warning("⚠️ Authentication is DISABLED - Development mode")
    else:
        logger.info("✅ API Key authentication enabled")


# ==================== Public Endpoints (No Auth Required) ====================

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - public"""
    return {
        "name": "Egyptian AI Medication Validation Engine",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
        "authentication": "API key required for most endpoints"
    }


@app.get("/health", response_model=HealthCheckResponse, tags=["Health"])
async def health_check():
    """Health check endpoint - public"""
    drug_db = get_drug_database()
    return HealthCheckResponse(
        status="healthy" if db_initialized else "initializing",
        version="1.0.0",
        medications_loaded=len(drug_db.medications) if drug_db._loaded else 0,
        timestamp=datetime.now().isoformat()
    )


# ==================== Protected Endpoints (Auth Required) ====================

@app.post("/admin/load-database", tags=["Admin"])
async def load_database(
    filepath: str = "/data/cfgdrug.xlsx",
    auth: AuthResult = Depends(require_admin_key)
):
    """Load Egyptian drug database from Excel file - Admin only"""
    global db_initialized
    try:
        drug_db = init_drug_database(filepath)
        db_initialized = True
        logger.info(f"Database loaded by: {auth.client_name}")
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
    limit: int = Query(20, ge=1, le=100),
    auth: AuthResult = Depends(require_api_key)
):
    """Search medications by name, generic name, or ingredient"""
    results = validation_service.search_medications(q, limit)
    return results


@app.get("/medications/{medication_id}", tags=["Medications"])
async def get_medication(
    medication_id: int,
    auth: AuthResult = Depends(require_api_key)
):
    """Get detailed medication information"""
    info = validation_service.get_medication_info(medication_id)
    if not info:
        raise HTTPException(status_code=404, detail="Medication not found")
    return info


@app.post("/validate/prescription", response_model=ValidationResponse, tags=["Validation"])
async def validate_prescription(
    request: PrescriptionValidationRequest,
    auth: AuthResult = Depends(require_api_key)
):
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
    
    # Log validation
    logger.info(f"Prescription validated by {auth.client_name}: {result.prescription_id}")
    
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
async def quick_validate(
    request: QuickCheckRequest,
    auth: AuthResult = Depends(require_api_key)
):
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
async def check_interaction(
    request: InteractionCheckRequest,
    auth: AuthResult = Depends(require_api_key)
):
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
async def get_statistics(auth: AuthResult = Depends(require_api_key)):
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


# ==================== API Key Management (Admin Only) ====================

@app.post("/admin/keys/generate", tags=["API Keys"])
async def generate_new_api_key(
    request: GenerateKeyRequest,
    auth: AuthResult = Depends(require_admin_key)
):
    """Generate a new API key - Admin only"""
    new_key = generate_api_key(
        name=request.name,
        access_level=request.access_level,
        rate_limit=request.rate_limit
    )
    logger.info(f"New API key generated by {auth.client_name} for: {request.name}")
    return {
        "api_key": new_key,
        "name": request.name,
        "access_level": request.access_level,
        "rate_limit": request.rate_limit,
        "message": "Store this key securely - it cannot be retrieved later"
    }


@app.get("/admin/keys", tags=["API Keys"])
async def list_all_api_keys(auth: AuthResult = Depends(require_admin_key)):
    """List all API keys (masked) - Admin only"""
    return {"keys": list_api_keys()}


@app.delete("/admin/keys/{api_key}", tags=["API Keys"])
async def revoke_api_key_endpoint(
    api_key: str,
    auth: AuthResult = Depends(require_admin_key)
):
    """Revoke an API key - Admin only"""
    if revoke_api_key(api_key):
        logger.info(f"API key revoked by {auth.client_name}: {api_key[:20]}...")
        return {"status": "revoked", "key_prefix": api_key[:20] + "..."}
    raise HTTPException(status_code=404, detail="API key not found")


@app.get("/auth/verify", tags=["Authentication"])
async def verify_authentication(auth: AuthResult = Depends(verify_api_key)):
    """Verify API key and return access information"""
    return {
        "authenticated": auth.authenticated,
        "access_level": auth.access_level,
        "client_name": auth.client_name,
        "error": auth.error
    }


# ==================== Webhook Management ====================

class WebhookConfigRequest(BaseModel):
    name: str
    url: str
    secret: str
    events: List[str] = ["prescription.blocked", "interaction.major"]
    active: bool = True


class WebhookTestRequest(BaseModel):
    webhook_id: str
    test_payload: Optional[Dict[str, Any]] = None


@app.post("/webhooks/register", tags=["Webhooks"])
async def register_webhook(
    request: WebhookConfigRequest,
    auth: AuthResult = Depends(require_admin_key)
):
    """
    Register a new webhook endpoint for receiving alerts.
    
    Events available:
    - prescription.blocked: When a prescription is blocked due to critical issues
    - prescription.warning: When a prescription has warnings
    - interaction.major: When a major drug interaction is detected
    - contraindication.detected: When a contraindication is found
    - dosing.alert: When dosing adjustment is needed
    """
    webhook_manager = get_webhook_manager()
    
    webhook_id = f"wh-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    config = WebhookConfig(
        id=webhook_id,
        name=request.name,
        url=request.url,
        secret=request.secret,
        events=request.events,
        active=request.active
    )
    
    webhook_manager.register_webhook(config)
    logger.info(f"Webhook registered by {auth.client_name}: {request.name}")
    
    return {
        "status": "registered",
        "webhook_id": webhook_id,
        "name": request.name,
        "url": request.url,
        "events": request.events
    }


@app.get("/webhooks", tags=["Webhooks"])
async def list_webhooks(auth: AuthResult = Depends(require_admin_key)):
    """List all registered webhooks"""
    webhook_manager = get_webhook_manager()
    return {"webhooks": webhook_manager.list_webhooks()}


@app.delete("/webhooks/{webhook_id}", tags=["Webhooks"])
async def delete_webhook(
    webhook_id: str,
    auth: AuthResult = Depends(require_admin_key)
):
    """Delete a webhook configuration"""
    webhook_manager = get_webhook_manager()
    
    if webhook_manager.delete_webhook(webhook_id):
        return {"status": "deleted", "webhook_id": webhook_id}
    raise HTTPException(status_code=404, detail="Webhook not found")


@app.post("/webhooks/test", tags=["Webhooks"])
async def test_webhook(
    request: WebhookTestRequest,
    background_tasks: BackgroundTasks,
    auth: AuthResult = Depends(require_admin_key)
):
    """
    Send a test webhook to verify configuration.
    The test payload will be sent asynchronously.
    """
    webhook_manager = get_webhook_manager()
    
    if request.webhook_id not in webhook_manager.webhooks:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    test_payload = request.test_payload or {
        "prescription_id": "TEST-RX-001",
        "patient_id": "TEST-PATIENT",
        "status": "BLOCKED",
        "reason": "Test webhook - Major drug interaction detected",
        "test": True
    }
    
    async def send_test():
        webhook = webhook_manager.webhooks[request.webhook_id]
        await webhook_manager.send_webhook(
            webhook,
            "test.webhook",
            test_payload
        )
    
    background_tasks.add_task(send_test)
    
    return {
        "status": "test_queued",
        "webhook_id": request.webhook_id,
        "message": "Test webhook will be sent shortly"
    }


@app.get("/webhooks/deliveries", tags=["Webhooks"])
async def get_webhook_deliveries(
    webhook_id: Optional[str] = None,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    auth: AuthResult = Depends(require_admin_key)
):
    """Get webhook delivery history with optional filters"""
    webhook_manager = get_webhook_manager()
    
    deliveries = webhook_manager.get_delivery_history(
        webhook_id=webhook_id,
        event_type=event_type,
        status=status,
        limit=limit
    )
    
    return {
        "total": len(deliveries),
        "deliveries": deliveries
    }


@app.put("/webhooks/{webhook_id}", tags=["Webhooks"])
async def update_webhook(
    webhook_id: str,
    request: WebhookConfigRequest,
    auth: AuthResult = Depends(require_admin_key)
):
    """Update an existing webhook configuration"""
    webhook_manager = get_webhook_manager()
    
    updates = {
        "name": request.name,
        "url": request.url,
        "secret": request.secret,
        "events": request.events,
        "active": request.active
    }
    
    updated = webhook_manager.update_webhook(webhook_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    return {
        "status": "updated",
        "webhook_id": webhook_id,
        "name": request.name
    }


# Main entry point for running directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
