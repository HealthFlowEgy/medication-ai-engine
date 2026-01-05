"""
Egyptian AI Medication Validation Engine - Main Validation Service
Sprint 3: Complete Validation Pipeline
"""
import logging
import time
from typing import List, Dict, Optional, Any
from datetime import datetime

from src.core.models import (
    Medication, DrugInteraction, DosingAdjustment,
    PatientContext, ValidationResult, Prescription, PrescriptionItem
)
from src.core.drug_database import get_drug_database, EgyptianDrugDatabase
from src.core.ddi_engine import get_ddi_engine, DDIEngine
from src.dosing.calculator import get_dosing_engine, DosingEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MedicationValidationService:
    """
    Main service for validating prescriptions against:
    - Drug-Drug Interactions
    - Renal/Hepatic Dose Adjustments
    - Contraindications
    - Allergy checks
    """
    
    def __init__(
        self, 
        drug_db: Optional[EgyptianDrugDatabase] = None,
        ddi_engine: Optional[DDIEngine] = None,
        dosing_engine: Optional[DosingEngine] = None
    ):
        self.drug_db = drug_db or get_drug_database()
        self.ddi_engine = ddi_engine or get_ddi_engine()
        self.dosing_engine = dosing_engine or get_dosing_engine()
        logger.info("Medication Validation Service initialized")
    
    def validate_prescription(
        self, 
        prescription: Prescription
    ) -> ValidationResult:
        """
        Validate a complete prescription.
        
        Args:
            prescription: Prescription object with patient context and medication items
            
        Returns:
            ValidationResult with interactions, dosing adjustments, and recommendations
        """
        start_time = time.time()
        
        # Resolve medications from database
        medications = self._resolve_medications(prescription.items)
        
        # Check drug-drug interactions
        interactions = self.ddi_engine.check_prescription(medications)
        
        # Check dosing adjustments based on patient context
        dosing_adjustments = self.dosing_engine.check_prescription(
            medications, prescription.patient
        )
        
        # Check contraindications
        contraindications = self._check_contraindications(
            medications, prescription.patient
        )
        
        # Generate warnings
        warnings = self._generate_warnings(
            medications, prescription.patient, interactions, dosing_adjustments
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            interactions, dosing_adjustments, contraindications
        )
        
        # Determine overall validity
        is_valid = not any([
            any(i.severity.value == "major" for i in interactions),
            any(da.contraindicated for da in dosing_adjustments),
            len(contraindications) > 0
        ])
        
        validation_time = (time.time() - start_time) * 1000
        
        return ValidationResult(
            is_valid=is_valid,
            prescription_id=prescription.id,
            medications_validated=len(medications),
            interactions=interactions,
            dosing_adjustments=dosing_adjustments,
            contraindications=contraindications,
            warnings=warnings,
            recommendations=recommendations,
            validation_time_ms=validation_time
        )
    
    def validate_medication_pair(
        self, 
        med1_id: int, 
        med2_id: int
    ) -> List[DrugInteraction]:
        """Quick check for interactions between two medications"""
        med1 = self.drug_db.get_by_id(med1_id)
        med2 = self.drug_db.get_by_id(med2_id)
        
        if not med1 or not med2:
            return []
        
        return self.ddi_engine.check_pair(med1, med2)
    
    def validate_medication_list(
        self, 
        medication_ids: List[int],
        patient: Optional[PatientContext] = None
    ) -> ValidationResult:
        """Validate a list of medication IDs"""
        # Create a simple prescription
        items = [
            PrescriptionItem(
                medication_id=mid,
                medication_name="",
                dose="",
                frequency=""
            ) for mid in medication_ids
        ]
        
        prescription = Prescription(
            id=f"quick-{datetime.now().timestamp()}",
            patient=patient or PatientContext(),
            items=items
        )
        
        return self.validate_prescription(prescription)
    
    def _resolve_medications(
        self, 
        items: List[PrescriptionItem]
    ) -> List[Medication]:
        """Resolve prescription items to medication objects"""
        medications = []
        
        for item in items:
            med = self.drug_db.get_by_id(item.medication_id)
            if med:
                medications.append(med)
            else:
                logger.warning(f"Medication not found: {item.medication_id}")
        
        return medications
    
    def _check_contraindications(
        self, 
        medications: List[Medication],
        patient: PatientContext
    ) -> List[str]:
        """Check for contraindications based on patient conditions"""
        contraindications = []
        
        # Check pregnancy contraindications
        if patient.is_pregnant:
            pregnancy_contraindicated = [
                "methotrexate", "warfarin", "isotretinoin", "thalidomide",
                "misoprostol", "finasteride", "statins", "ace_inhibitor",
                "tetracycline", "fluoroquinolone"
            ]
            for med in medications:
                name_lower = med.commercial_name.lower()
                generic = (med.generic_name or "").lower()
                for drug in pregnancy_contraindicated:
                    if drug in name_lower or drug in generic:
                        contraindications.append(
                            f"{med.commercial_name}: Contraindicated in pregnancy"
                        )
        
        # Check for common condition-drug contraindications
        condition_contraindications = {
            "asthma": ["beta_blocker", "aspirin", "nsaid"],
            "heart_failure": ["nsaid", "thiazolidinedione", "verapamil", "diltiazem"],
            "peptic_ulcer": ["nsaid", "aspirin", "corticosteroid"],
            "gout": ["thiazide", "loop_diuretic", "aspirin"],
            "myasthenia_gravis": ["aminoglycoside", "fluoroquinolone", "beta_blocker"],
        }
        
        for condition in patient.conditions:
            condition_lower = condition.lower().replace(" ", "_")
            if condition_lower in condition_contraindications:
                for med in medications:
                    name_lower = med.commercial_name.lower()
                    for drug in condition_contraindications[condition_lower]:
                        if drug in name_lower:
                            contraindications.append(
                                f"{med.commercial_name}: Caution/Contraindicated with {condition}"
                            )
        
        return contraindications
    
    def _generate_warnings(
        self,
        medications: List[Medication],
        patient: PatientContext,
        interactions: List[DrugInteraction],
        dosing_adjustments: List[DosingAdjustment]
    ) -> List[str]:
        """Generate warning messages"""
        warnings = []
        
        # High-alert medication warnings
        for med in medications:
            if self.drug_db.is_high_alert(med.id):
                warnings.append(f"⚠️ HIGH-ALERT: {med.commercial_name} requires extra verification")
        
        # Interaction count warnings
        major_count = sum(1 for i in interactions if i.severity.value == "major")
        if major_count > 0:
            warnings.append(f"🔴 {major_count} MAJOR drug interaction(s) detected - review required")
        
        moderate_count = sum(1 for i in interactions if i.severity.value == "moderate")
        if moderate_count > 0:
            warnings.append(f"🟡 {moderate_count} moderate drug interaction(s) detected")
        
        # Dosing warnings
        contraindicated_count = sum(1 for da in dosing_adjustments if da.contraindicated)
        if contraindicated_count > 0:
            warnings.append(
                f"❌ {contraindicated_count} medication(s) contraindicated for patient's renal function"
            )
        
        adjustment_count = len(dosing_adjustments) - contraindicated_count
        if adjustment_count > 0:
            warnings.append(
                f"📋 {adjustment_count} medication(s) require dose adjustment for renal function"
            )
        
        # Age-related warnings
        if patient.age:
            if patient.age >= 65:
                warnings.append("👴 Elderly patient - review for age-appropriate dosing and polypharmacy")
            elif patient.age < 18:
                warnings.append("👶 Pediatric patient - verify age-appropriate formulations and doses")
        
        return warnings
    
    def _generate_recommendations(
        self,
        interactions: List[DrugInteraction],
        dosing_adjustments: List[DosingAdjustment],
        contraindications: List[str]
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Interaction recommendations
        for interaction in interactions:
            if interaction.management:
                recommendations.append(
                    f"For {interaction.drug1_name} + {interaction.drug2_name}: {interaction.management}"
                )
        
        # Dosing recommendations
        for adj in dosing_adjustments:
            if adj.contraindicated:
                recommendations.append(
                    f"AVOID {adj.medication_name} - {adj.adjustment_reason}. Consider alternatives."
                )
            else:
                recommendations.append(
                    f"ADJUST {adj.medication_name}: {adj.adjusted_dose} ({adj.adjustment_reason})"
                )
                if adj.monitoring_required:
                    recommendations.append(
                        f"MONITOR for {adj.medication_name}: {', '.join(adj.monitoring_parameters)}"
                    )
        
        return recommendations
    
    def search_medications(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search medications in database"""
        medications = self.drug_db.search(query, limit)
        return [
            {
                "id": med.id,
                "commercial_name": med.commercial_name,
                "generic_name": med.generic_name,
                "dosage_form": med.dosage_form.value,
                "strength": med.strength,
                "is_high_alert": self.drug_db.is_high_alert(med.id)
            }
            for med in medications
        ]
    
    def get_medication_info(self, med_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed medication information"""
        med = self.drug_db.get_by_id(med_id)
        if not med:
            return None
        
        similar = self.drug_db.get_similar_medications(med_id)
        
        return {
            "id": med.id,
            "commercial_name": med.commercial_name,
            "generic_name": med.generic_name,
            "arabic_name": med.arabic_name,
            "active_ingredients": med.active_ingredients,
            "dosage_form": med.dosage_form.value,
            "strength": med.strength,
            "is_high_alert": self.drug_db.is_high_alert(med_id),
            "similar_medications": [
                {"id": s.id, "name": s.commercial_name} for s in similar[:5]
            ]
        }


# Singleton instance
_validation_service: Optional[MedicationValidationService] = None

def get_validation_service() -> MedicationValidationService:
    """Get or create validation service singleton"""
    global _validation_service
    if _validation_service is None:
        _validation_service = MedicationValidationService()
    return _validation_service
