"""
Egyptian AI Medication Validation Engine - HealthFlow Integration
Sprint 5: Connect to HealthFlow Unified System
"""
import logging
import httpx
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict

from src.core.models import (
    Prescription, PrescriptionItem, PatientContext,
    ValidationResult, DrugInteraction, DDISeverity
)
from src.core.validation_service import get_validation_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class HealthFlowPrescription:
    """HealthFlow Unified System prescription format"""
    prescription_id: str
    patient_national_id: str
    patient_age: Optional[int] = None
    patient_sex: Optional[str] = None
    patient_weight: Optional[float] = None
    patient_creatinine: Optional[float] = None
    patient_conditions: List[str] = None
    medications: List[Dict[str, Any]] = None
    prescriber_license: Optional[str] = None
    pharmacy_code: Optional[str] = None
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        self.patient_conditions = self.patient_conditions or []
        self.medications = self.medications or []


@dataclass
class HealthFlowValidationResponse:
    """Response format for HealthFlow integration"""
    prescription_id: str
    status: str  # "valid", "warning", "blocked"
    validation_code: str
    timestamp: str
    
    # Interaction summary
    has_major_interactions: bool
    interaction_count: int
    major_interactions: List[Dict[str, str]]
    
    # Dosing summary
    has_dosing_issues: bool
    contraindicated_count: int
    adjustment_count: int
    dosing_alerts: List[Dict[str, str]]
    
    # Actions
    warnings: List[str]
    recommendations: List[str]
    
    # Performance
    validation_time_ms: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HealthFlowAdapter:
    """
    Adapter to connect Medication AI Engine with HealthFlow Unified System.
    Handles prescription format conversion and webhook notifications.
    """
    
    def __init__(
        self, 
        healthflow_url: str = None,
        healthflow_api_key: str = None,
        webhook_url: str = None
    ):
        self.healthflow_url = healthflow_url
        self.healthflow_api_key = healthflow_api_key
        self.webhook_url = webhook_url
        self.validation_service = get_validation_service()
        
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={"Authorization": f"Bearer {healthflow_api_key}"} if healthflow_api_key else {}
        )
        
        logger.info("HealthFlow Adapter initialized")
    
    def convert_healthflow_prescription(
        self, 
        hf_prescription: HealthFlowPrescription
    ) -> Prescription:
        """Convert HealthFlow format to internal Prescription format"""
        
        # Build patient context
        patient = PatientContext(
            age=hf_prescription.patient_age,
            weight_kg=hf_prescription.patient_weight,
            sex=hf_prescription.patient_sex,
            serum_creatinine=hf_prescription.patient_creatinine,
            conditions=hf_prescription.patient_conditions or []
        )
        
        # Convert medications
        items = []
        for med in hf_prescription.medications:
            item = PrescriptionItem(
                medication_id=med.get("medication_id", 0),
                medication_name=med.get("name", ""),
                dose=med.get("dose", ""),
                frequency=med.get("frequency", ""),
                duration=med.get("duration"),
                route=med.get("route"),
                instructions=med.get("instructions")
            )
            items.append(item)
        
        return Prescription(
            id=hf_prescription.prescription_id,
            patient=patient,
            items=items,
            prescriber_id=hf_prescription.prescriber_license,
            pharmacy_id=hf_prescription.pharmacy_code
        )
    
    def convert_validation_result(
        self,
        result: ValidationResult,
        prescription_id: str
    ) -> HealthFlowValidationResponse:
        """Convert internal ValidationResult to HealthFlow response format"""
        
        # Determine status
        if result.has_major_interactions or any(da.contraindicated for da in result.dosing_adjustments):
            status = "blocked"
            validation_code = "REVIEW_REQUIRED"
        elif len(result.interactions) > 0 or len(result.dosing_adjustments) > 0:
            status = "warning"
            validation_code = "APPROVED_WITH_WARNINGS"
        else:
            status = "valid"
            validation_code = "APPROVED"
        
        # Format major interactions for HealthFlow
        major_interactions = [
            {
                "drug1": i.drug1_name,
                "drug2": i.drug2_name,
                "severity": "MAJOR",
                "mechanism": i.mechanism[:200] if i.mechanism else "",
                "action": i.management[:200] if i.management else ""
            }
            for i in result.interactions
            if i.severity == DDISeverity.MAJOR
        ]
        
        # Format dosing alerts
        dosing_alerts = [
            {
                "medication": da.medication_name,
                "issue": "CONTRAINDICATED" if da.contraindicated else "ADJUSTMENT_NEEDED",
                "current_dose": da.standard_dose,
                "recommended": da.adjusted_dose,
                "reason": da.adjustment_reason
            }
            for da in result.dosing_adjustments
        ]
        
        return HealthFlowValidationResponse(
            prescription_id=prescription_id,
            status=status,
            validation_code=validation_code,
            timestamp=datetime.now().isoformat(),
            has_major_interactions=result.has_major_interactions,
            interaction_count=len(result.interactions),
            major_interactions=major_interactions,
            has_dosing_issues=len(result.dosing_adjustments) > 0,
            contraindicated_count=sum(1 for da in result.dosing_adjustments if da.contraindicated),
            adjustment_count=len(result.dosing_adjustments),
            dosing_alerts=dosing_alerts,
            warnings=result.warnings,
            recommendations=result.recommendations,
            validation_time_ms=result.validation_time_ms
        )
    
    def validate_healthflow_prescription(
        self,
        hf_prescription: HealthFlowPrescription
    ) -> HealthFlowValidationResponse:
        """
        Main entry point for HealthFlow prescription validation.
        
        Args:
            hf_prescription: Prescription in HealthFlow format
            
        Returns:
            HealthFlowValidationResponse with validation results
        """
        # Convert to internal format
        prescription = self.convert_healthflow_prescription(hf_prescription)
        
        # Validate
        result = self.validation_service.validate_prescription(prescription)
        
        # Convert back to HealthFlow format
        response = self.convert_validation_result(result, hf_prescription.prescription_id)
        
        return response
    
    async def send_webhook_notification(
        self,
        response: HealthFlowValidationResponse
    ) -> bool:
        """Send webhook notification to HealthFlow for critical alerts"""
        
        if not self.webhook_url:
            logger.warning("Webhook URL not configured")
            return False
        
        # Only send webhooks for blocked prescriptions or major interactions
        if response.status != "blocked":
            return True
        
        payload = {
            "event": "PRESCRIPTION_VALIDATION_ALERT",
            "prescription_id": response.prescription_id,
            "status": response.status,
            "validation_code": response.validation_code,
            "timestamp": response.timestamp,
            "alerts": {
                "major_interactions": response.major_interactions,
                "contraindicated_medications": [
                    a for a in response.dosing_alerts if a["issue"] == "CONTRAINDICATED"
                ]
            },
            "action_required": True
        }
        
        try:
            resp = await self.http_client.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if resp.status_code == 200:
                logger.info(f"Webhook sent for prescription {response.prescription_id}")
                return True
            else:
                logger.error(f"Webhook failed: {resp.status_code} - {resp.text}")
                return False
                
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return False
    
    async def fetch_patient_context(
        self,
        national_id: str
    ) -> Optional[PatientContext]:
        """
        Fetch patient context from HealthFlow system.
        Used to enrich prescription validation with patient history.
        """
        if not self.healthflow_url or not self.healthflow_api_key:
            return None
        
        try:
            resp = await self.http_client.get(
                f"{self.healthflow_url}/patients/{national_id}/context"
            )
            
            if resp.status_code == 200:
                data = resp.json()
                return PatientContext(
                    age=data.get("age"),
                    weight_kg=data.get("weight"),
                    sex=data.get("sex"),
                    serum_creatinine=data.get("latest_creatinine"),
                    gfr=data.get("latest_gfr"),
                    conditions=data.get("active_conditions", []),
                    allergies=data.get("allergies", []),
                    current_medications=data.get("current_medication_ids", [])
                )
            
        except Exception as e:
            logger.error(f"Failed to fetch patient context: {e}")
        
        return None
    
    def validate_from_json(self, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate prescription from JSON payload (for API usage).
        
        Args:
            json_data: HealthFlow prescription JSON
            
        Returns:
            Validation response as dictionary
        """
        hf_prescription = HealthFlowPrescription(
            prescription_id=json_data.get("prescription_id", ""),
            patient_national_id=json_data.get("patient", {}).get("national_id", ""),
            patient_age=json_data.get("patient", {}).get("age"),
            patient_sex=json_data.get("patient", {}).get("sex"),
            patient_weight=json_data.get("patient", {}).get("weight"),
            patient_creatinine=json_data.get("patient", {}).get("creatinine"),
            patient_conditions=json_data.get("patient", {}).get("conditions", []),
            medications=json_data.get("medications", []),
            prescriber_license=json_data.get("prescriber", {}).get("license"),
            pharmacy_code=json_data.get("pharmacy", {}).get("code"),
            timestamp=json_data.get("timestamp")
        )
        
        response = self.validate_healthflow_prescription(hf_prescription)
        return response.to_dict()


# Singleton instance
_adapter: Optional[HealthFlowAdapter] = None

def get_healthflow_adapter(
    healthflow_url: str = None,
    healthflow_api_key: str = None,
    webhook_url: str = None
) -> HealthFlowAdapter:
    """Get or create HealthFlow adapter singleton"""
    global _adapter
    if _adapter is None:
        _adapter = HealthFlowAdapter(healthflow_url, healthflow_api_key, webhook_url)
    return _adapter


# Example HealthFlow prescription format
EXAMPLE_HEALTHFLOW_PRESCRIPTION = {
    "prescription_id": "RX-2026-001234",
    "timestamp": "2026-01-05T14:30:00Z",
    "patient": {
        "national_id": "29001011234567",
        "age": 65,
        "sex": "M",
        "weight": 75,
        "creatinine": 2.1,
        "conditions": ["diabetes", "hypertension"]
    },
    "medications": [
        {
            "medication_id": 103473,
            "name": "Januvia 100mg",
            "dose": "100mg",
            "frequency": "once daily",
            "duration": "30 days"
        },
        {
            "medication_id": 100005,
            "name": "Cataflam 50mg",
            "dose": "50mg",
            "frequency": "twice daily",
            "duration": "7 days"
        }
    ],
    "prescriber": {
        "license": "MED-12345",
        "name": "Dr. Ahmed Hassan"
    },
    "pharmacy": {
        "code": "PHR-001",
        "name": "HealthFlow Pharmacy"
    }
}
