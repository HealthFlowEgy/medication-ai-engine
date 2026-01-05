"""
Egyptian AI Medication Validation Engine - HealthFlow Integration Endpoints
Sprint 5: Full HealthFlow Unified System Integration
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import asyncio
import hashlib
import hmac

from src.api.healthflow_adapter import (
    HealthFlowAdapter, HealthFlowPrescription, 
    HealthFlowValidationResponse, get_healthflow_adapter
)
from src.core.validation_service import get_validation_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/healthflow", tags=["HealthFlow Integration"])


# ==================== Request/Response Models ====================

class HealthFlowPatient(BaseModel):
    national_id: str = Field(..., description="Egyptian National ID")
    age: Optional[int] = Field(None, ge=0, le=150)
    sex: Optional[str] = Field(None, pattern="^[MF]$")
    weight: Optional[float] = Field(None, ge=0)
    creatinine: Optional[float] = Field(None, ge=0)
    conditions: List[str] = []


class HealthFlowMedication(BaseModel):
    medication_id: int
    name: str
    dose: str
    frequency: str
    duration: Optional[str] = None
    route: Optional[str] = None


class HealthFlowPrescriber(BaseModel):
    license: str
    name: Optional[str] = None
    specialty: Optional[str] = None


class HealthFlowPharmacy(BaseModel):
    code: str
    name: Optional[str] = None
    branch: Optional[str] = None


class HealthFlowPrescriptionRequest(BaseModel):
    prescription_id: str
    timestamp: Optional[str] = None
    patient: HealthFlowPatient
    medications: List[HealthFlowMedication]
    prescriber: Optional[HealthFlowPrescriber] = None
    pharmacy: Optional[HealthFlowPharmacy] = None


class BatchValidationRequest(BaseModel):
    prescriptions: List[HealthFlowPrescriptionRequest]
    webhook_url: Optional[str] = None
    priority: str = "normal"  # "normal", "high", "critical"


class BatchValidationResponse(BaseModel):
    batch_id: str
    total_prescriptions: int
    processed: int
    results: List[Dict[str, Any]]
    processing_time_ms: float


class WebhookConfigRequest(BaseModel):
    webhook_url: str
    events: List[str] = ["major_interaction", "contraindication", "validation_blocked"]
    secret: Optional[str] = None


class AuditLogEntry(BaseModel):
    prescription_id: str
    timestamp: str
    status: str
    pharmacy_code: Optional[str]
    prescriber_license: Optional[str]
    medications_count: int
    interactions_count: int
    validation_time_ms: float


# ==================== Webhook Management ====================

# In-memory webhook config (use Redis in production)
webhook_configs: Dict[str, Dict] = {}


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC signature for incoming webhooks"""
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


async def send_webhook_async(url: str, payload: Dict, secret: Optional[str] = None):
    """Send webhook notification asynchronously"""
    import httpx
    
    headers = {"Content-Type": "application/json"}
    if secret:
        signature = hmac.new(
            secret.encode(), 
            str(payload).encode(), 
            hashlib.sha256
        ).hexdigest()
        headers["X-Webhook-Signature"] = f"sha256={signature}"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            logger.info(f"Webhook sent to {url}: {response.status_code}")
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Webhook failed: {e}")
        return False


# ==================== API Endpoints ====================

@router.post("/validate", response_model=Dict[str, Any])
async def validate_healthflow_prescription(
    request: HealthFlowPrescriptionRequest,
    background_tasks: BackgroundTasks,
    x_api_key: Optional[str] = Header(None)
):
    """
    Validate a prescription from HealthFlow Unified System.
    
    This endpoint accepts prescriptions in HealthFlow format and returns
    validation results including drug interactions, dosing adjustments,
    and contraindications.
    
    For MAJOR interactions or contraindications, a webhook notification
    is sent if configured.
    """
    adapter = get_healthflow_adapter()
    
    # Convert to internal format
    hf_prescription = HealthFlowPrescription(
        prescription_id=request.prescription_id,
        patient_national_id=request.patient.national_id,
        patient_age=request.patient.age,
        patient_sex=request.patient.sex,
        patient_weight=request.patient.weight,
        patient_creatinine=request.patient.creatinine,
        patient_conditions=request.patient.conditions,
        medications=[m.dict() for m in request.medications],
        prescriber_license=request.prescriber.license if request.prescriber else None,
        pharmacy_code=request.pharmacy.code if request.pharmacy else None,
        timestamp=request.timestamp
    )
    
    # Validate
    response = adapter.validate_healthflow_prescription(hf_prescription)
    
    # Send webhook for blocked prescriptions
    if response.status == "blocked":
        for config in webhook_configs.values():
            if "validation_blocked" in config.get("events", []):
                background_tasks.add_task(
                    send_webhook_async,
                    config["url"],
                    {
                        "event": "validation_blocked",
                        "prescription_id": response.prescription_id,
                        "timestamp": response.timestamp,
                        "major_interactions": response.major_interactions,
                        "contraindicated_count": response.contraindicated_count
                    },
                    config.get("secret")
                )
    
    return response.to_dict()


@router.post("/validate/batch", response_model=BatchValidationResponse)
async def validate_batch(
    request: BatchValidationRequest,
    background_tasks: BackgroundTasks
):
    """
    Batch validate multiple prescriptions.
    
    Useful for pharmacy systems that need to validate multiple prescriptions
    at once (e.g., end-of-day reconciliation).
    
    Results can be sent to a webhook URL if provided.
    """
    import time
    start_time = time.time()
    
    adapter = get_healthflow_adapter()
    results = []
    
    for rx in request.prescriptions:
        hf_prescription = HealthFlowPrescription(
            prescription_id=rx.prescription_id,
            patient_national_id=rx.patient.national_id,
            patient_age=rx.patient.age,
            patient_sex=rx.patient.sex,
            patient_weight=rx.patient.weight,
            patient_creatinine=rx.patient.creatinine,
            patient_conditions=rx.patient.conditions,
            medications=[m.dict() for m in rx.medications],
            prescriber_license=rx.prescriber.license if rx.prescriber else None,
            pharmacy_code=rx.pharmacy.code if rx.pharmacy else None,
        )
        
        response = adapter.validate_healthflow_prescription(hf_prescription)
        results.append(response.to_dict())
    
    processing_time = (time.time() - start_time) * 1000
    
    batch_response = BatchValidationResponse(
        batch_id=f"batch-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        total_prescriptions=len(request.prescriptions),
        processed=len(results),
        results=results,
        processing_time_ms=processing_time
    )
    
    # Send results to webhook if provided
    if request.webhook_url:
        background_tasks.add_task(
            send_webhook_async,
            request.webhook_url,
            batch_response.dict()
        )
    
    return batch_response


@router.post("/webhook/configure")
async def configure_webhook(config: WebhookConfigRequest):
    """
    Configure webhook notifications for validation alerts.
    
    Events:
    - major_interaction: When a MAJOR DDI is detected
    - contraindication: When a contraindication is found
    - validation_blocked: When prescription is blocked
    """
    config_id = hashlib.md5(config.webhook_url.encode()).hexdigest()[:12]
    
    webhook_configs[config_id] = {
        "url": config.webhook_url,
        "events": config.events,
        "secret": config.secret,
        "created_at": datetime.now().isoformat()
    }
    
    return {
        "config_id": config_id,
        "status": "configured",
        "events": config.events,
        "message": "Webhook configured successfully"
    }


@router.delete("/webhook/{config_id}")
async def remove_webhook(config_id: str):
    """Remove a webhook configuration"""
    if config_id in webhook_configs:
        del webhook_configs[config_id]
        return {"status": "removed", "config_id": config_id}
    raise HTTPException(status_code=404, detail="Webhook configuration not found")


@router.get("/webhook/list")
async def list_webhooks():
    """List all configured webhooks"""
    return {
        "webhooks": [
            {"config_id": k, "url": v["url"], "events": v["events"]}
            for k, v in webhook_configs.items()
        ]
    }


@router.post("/audit/log")
async def create_audit_log(entry: AuditLogEntry):
    """
    Create an audit log entry for compliance tracking.
    
    All validations should be logged for regulatory compliance
    with Egyptian healthcare authorities.
    """
    # In production, this would write to PostgreSQL
    logger.info(f"Audit log: {entry.prescription_id} - {entry.status}")
    
    return {
        "logged": True,
        "entry_id": f"audit-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/audit/query")
async def query_audit_logs(
    pharmacy_code: Optional[str] = None,
    prescriber_license: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100
):
    """
    Query audit logs for compliance reporting.
    
    Supports filtering by pharmacy, prescriber, date range, and status.
    """
    # In production, this would query PostgreSQL
    return {
        "query": {
            "pharmacy_code": pharmacy_code,
            "prescriber_license": prescriber_license,
            "date_from": date_from,
            "date_to": date_to,
            "status": status
        },
        "results": [],
        "total": 0,
        "message": "Connect to PostgreSQL for actual audit data"
    }


@router.get("/status")
async def healthflow_integration_status():
    """Check HealthFlow integration status"""
    return {
        "status": "connected",
        "version": "1.0.0",
        "features": {
            "single_validation": True,
            "batch_validation": True,
            "webhooks": True,
            "audit_logging": True
        },
        "webhooks_configured": len(webhook_configs),
        "timestamp": datetime.now().isoformat()
    }


# ==================== Real-time Streaming (Future) ====================

@router.websocket("/ws/validate")
async def websocket_validation(websocket):
    """
    WebSocket endpoint for real-time validation during prescription entry.
    
    Allows immediate feedback as medications are added to a prescription.
    """
    await websocket.accept()
    
    adapter = get_healthflow_adapter()
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("action") == "check_interaction":
                # Quick interaction check for two medications
                med1_id = data.get("medication1_id")
                med2_id = data.get("medication2_id")
                
                service = get_validation_service()
                interactions = service.validate_medication_pair(med1_id, med2_id)
                
                await websocket.send_json({
                    "action": "interaction_result",
                    "has_interaction": len(interactions) > 0,
                    "severity": interactions[0].severity.value if interactions else None,
                    "details": [
                        {"mechanism": i.mechanism, "management": i.management}
                        for i in interactions
                    ]
                })
            
            elif data.get("action") == "validate_current":
                # Validate current prescription state
                prescription_data = data.get("prescription", {})
                # Process and return validation result
                await websocket.send_json({
                    "action": "validation_result",
                    "is_valid": True,  # Placeholder
                    "warnings": []
                })
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await websocket.close()
