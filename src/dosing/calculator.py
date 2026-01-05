"""
Egyptian AI Medication Validation Engine - Dosing Calculator
Sprint 2-3: Renal and Hepatic Dose Adjustments
"""
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from src.core.models import (
    Medication, DosingAdjustment, PatientContext,
    RenalImpairment, HepaticImpairment
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GFRCalculator:
    """Calculate GFR/CrCl using standard formulas"""
    
    @staticmethod
    def cockcroft_gault(
        age: int, 
        weight_kg: float, 
        serum_creatinine: float, 
        is_female: bool
    ) -> float:
        """
        Calculate Creatinine Clearance using Cockcroft-Gault equation.
        Most commonly used for drug dosing adjustments.
        
        Args:
            age: Patient age in years
            weight_kg: Patient weight in kg
            serum_creatinine: Serum creatinine in mg/dL
            is_female: True if female
            
        Returns:
            CrCl in mL/min
        """
        if serum_creatinine <= 0:
            return 0
        
        crcl = ((140 - age) * weight_kg) / (72 * serum_creatinine)
        
        if is_female:
            crcl *= 0.85
        
        return round(crcl, 1)
    
    @staticmethod
    def ckd_epi(
        age: int,
        serum_creatinine: float,
        is_female: bool,
        is_black: bool = False
    ) -> float:
        """
        Calculate eGFR using CKD-EPI 2021 equation (race-free).
        
        Args:
            age: Patient age in years
            serum_creatinine: Serum creatinine in mg/dL
            is_female: True if female
            is_black: Deprecated - kept for backward compatibility
            
        Returns:
            eGFR in mL/min/1.73m²
        """
        import math
        
        if is_female:
            kappa = 0.7
            alpha = -0.241
            female_factor = 1.012
        else:
            kappa = 0.9
            alpha = -0.302
            female_factor = 1.0
        
        scr_kappa = serum_creatinine / kappa
        
        if scr_kappa <= 1:
            egfr = 142 * (scr_kappa ** alpha) * (0.9938 ** age) * female_factor
        else:
            egfr = 142 * (scr_kappa ** -1.200) * (0.9938 ** age) * female_factor
        
        return round(egfr, 1)
    
    @staticmethod
    def classify_renal_function(gfr: float) -> RenalImpairment:
        """Classify renal function based on GFR"""
        if gfr >= 90:
            return RenalImpairment.NORMAL
        elif gfr >= 60:
            return RenalImpairment.MILD
        elif gfr >= 30:
            return RenalImpairment.MODERATE
        elif gfr >= 15:
            return RenalImpairment.SEVERE
        else:
            return RenalImpairment.ESRD


class ChildPughCalculator:
    """Calculate Child-Pugh score for hepatic impairment"""
    
    @staticmethod
    def calculate_score(
        bilirubin: float,      # mg/dL
        albumin: float,        # g/dL
        inr: float,
        ascites: str,          # "none", "mild", "moderate_severe"
        encephalopathy: str    # "none", "grade_1_2", "grade_3_4"
    ) -> Tuple[int, HepaticImpairment]:
        """
        Calculate Child-Pugh score and classification.
        
        Returns:
            Tuple of (score, classification)
        """
        score = 0
        
        # Bilirubin
        if bilirubin < 2:
            score += 1
        elif bilirubin <= 3:
            score += 2
        else:
            score += 3
        
        # Albumin
        if albumin > 3.5:
            score += 1
        elif albumin >= 2.8:
            score += 2
        else:
            score += 3
        
        # INR
        if inr < 1.7:
            score += 1
        elif inr <= 2.3:
            score += 2
        else:
            score += 3
        
        # Ascites
        if ascites == "none":
            score += 1
        elif ascites == "mild":
            score += 2
        else:
            score += 3
        
        # Encephalopathy
        if encephalopathy == "none":
            score += 1
        elif encephalopathy == "grade_1_2":
            score += 2
        else:
            score += 3
        
        # Classification
        if score <= 6:
            classification = HepaticImpairment.CHILD_PUGH_A
        elif score <= 9:
            classification = HepaticImpairment.CHILD_PUGH_B
        else:
            classification = HepaticImpairment.CHILD_PUGH_C
        
        return score, classification


# Renal dosing adjustments for common medications
# Format: drug_name -> {renal_level: (dose_adjustment, notes)}
RENAL_DOSING_RULES = {
    # Antibiotics
    "amoxicillin": {
        RenalImpairment.MODERATE: ("250-500mg q12h", "Extend interval"),
        RenalImpairment.SEVERE: ("250-500mg q24h", "Once daily dosing"),
        RenalImpairment.ESRD: ("250-500mg q24h + post-HD dose", "Dialyzable - give after HD"),
    },
    "ciprofloxacin": {
        RenalImpairment.MODERATE: ("250-500mg q12h", "Reduce dose or extend interval"),
        RenalImpairment.SEVERE: ("250-500mg q18-24h", "Significant reduction needed"),
        RenalImpairment.ESRD: ("250-500mg q24h", "Give after dialysis"),
    },
    "levofloxacin": {
        RenalImpairment.MODERATE: ("250-500mg q24h", "Standard interval, may reduce dose"),
        RenalImpairment.SEVERE: ("250mg q24-48h", "Reduce dose and extend interval"),
        RenalImpairment.ESRD: ("250mg q48h", "Post-dialysis dosing"),
    },
    "gentamicin": {
        RenalImpairment.MILD: ("Use traditional dosing with monitoring", "Monitor levels closely"),
        RenalImpairment.MODERATE: ("Extend interval to q24-36h", "TDM required"),
        RenalImpairment.SEVERE: ("Extend interval to q48h", "TDM required - nephrotoxic"),
        RenalImpairment.ESRD: ("Re-dose based on levels after HD", "TDM required"),
    },
    "vancomycin": {
        RenalImpairment.MILD: ("15-20mg/kg q12h", "Monitor trough levels"),
        RenalImpairment.MODERATE: ("15-20mg/kg q24-48h", "TDM required"),
        RenalImpairment.SEVERE: ("15-20mg/kg q48-72h", "TDM required"),
        RenalImpairment.ESRD: ("15-25mg/kg loading, then based on levels", "Give after HD"),
    },
    "metronidazole": {
        RenalImpairment.SEVERE: ("Reduce dose by 50%", "Active metabolite accumulates"),
        RenalImpairment.ESRD: ("Reduce dose by 50%", "Not dialyzable"),
    },
    
    # Cardiovascular
    "atenolol": {
        RenalImpairment.MODERATE: ("25-50mg daily", "Reduce dose"),
        RenalImpairment.SEVERE: ("25mg daily or every other day", "Significant reduction"),
        RenalImpairment.ESRD: ("25-50mg after HD", "Dialyzable"),
    },
    "digoxin": {
        RenalImpairment.MILD: ("0.125-0.25mg daily", "Monitor levels"),
        RenalImpairment.MODERATE: ("0.0625-0.125mg daily", "Reduce dose significantly"),
        RenalImpairment.SEVERE: ("0.0625mg daily or every other day", "High toxicity risk"),
        RenalImpairment.ESRD: ("0.0625mg 3x/week", "Not dialyzable - very careful dosing"),
    },
    "lisinopril": {
        RenalImpairment.MODERATE: ("Start 2.5-5mg daily", "Titrate carefully"),
        RenalImpairment.SEVERE: ("Start 2.5mg daily", "May accumulate - watch K+"),
        RenalImpairment.ESRD: ("Start 2.5mg daily", "Dialyzable"),
    },
    "spironolactone": {
        RenalImpairment.MODERATE: ("Use with caution - monitor K+", "Risk of hyperkalemia"),
        RenalImpairment.SEVERE: ("Avoid if possible", "High hyperkalemia risk"),
        RenalImpairment.ESRD: ("Contraindicated", "Severe hyperkalemia risk"),
    },
    
    # Pain/Anti-inflammatory
    "morphine": {
        RenalImpairment.MODERATE: ("Reduce dose by 25-50%", "Active metabolite accumulates"),
        RenalImpairment.SEVERE: ("Reduce dose by 50-75%", "Use with extreme caution"),
        RenalImpairment.ESRD: ("Avoid - use fentanyl or hydromorphone", "Metabolite causes toxicity"),
    },
    "gabapentin": {
        RenalImpairment.MILD: ("300-600mg TID", "May need adjustment"),
        RenalImpairment.MODERATE: ("200-300mg BID", "Reduce dose"),
        RenalImpairment.SEVERE: ("100-300mg daily", "Significant reduction"),
        RenalImpairment.ESRD: ("100-300mg post-HD", "Give after dialysis"),
    },
    "nsaid": {
        RenalImpairment.MILD: ("Use lowest effective dose for shortest duration", "Monitor renal function"),
        RenalImpairment.MODERATE: ("Avoid if possible", "May worsen renal function"),
        RenalImpairment.SEVERE: ("Contraindicated", "High risk of AKI"),
        RenalImpairment.ESRD: ("Contraindicated", "No renal benefit, cardiovascular risk remains"),
    },
    
    # Diabetes
    "metformin": {
        RenalImpairment.MILD: ("No adjustment needed", "Monitor renal function"),
        RenalImpairment.MODERATE: ("Max 1000mg daily if GFR 30-45", "Do not start if GFR <45"),
        RenalImpairment.SEVERE: ("Contraindicated", "Lactic acidosis risk"),
        RenalImpairment.ESRD: ("Contraindicated", "Lactic acidosis risk"),
    },
    "glyburide": {
        RenalImpairment.MODERATE: ("Avoid - use glipizide instead", "Active metabolites accumulate"),
        RenalImpairment.SEVERE: ("Contraindicated", "Prolonged hypoglycemia risk"),
        RenalImpairment.ESRD: ("Contraindicated", "Use insulin"),
    },
    "sitagliptin": {
        RenalImpairment.MODERATE: ("50mg daily", "Reduce from 100mg"),
        RenalImpairment.SEVERE: ("25mg daily", "Further reduction"),
        RenalImpairment.ESRD: ("25mg daily", "Can be given regardless of HD timing"),
    },
    
    # Anticoagulants
    "enoxaparin": {
        RenalImpairment.SEVERE: ("1mg/kg once daily for treatment", "Reduce prophylaxis to 30mg daily"),
        RenalImpairment.ESRD: ("Avoid - use UFH", "Unpredictable accumulation"),
    },
    "rivaroxaban": {
        RenalImpairment.MODERATE: ("15mg daily for AF if GFR 15-50", "Reduce dose"),
        RenalImpairment.SEVERE: ("Avoid if GFR <15", "Limited data"),
        RenalImpairment.ESRD: ("Not recommended", "No data on HD patients"),
    },
    "dabigatran": {
        RenalImpairment.MODERATE: ("110mg BID if GFR 30-50", "Reduce dose"),
        RenalImpairment.SEVERE: ("Contraindicated", "GFR <30"),
        RenalImpairment.ESRD: ("Contraindicated", "No data"),
    },
}


class DosingEngine:
    """Dosing adjustment calculation engine"""
    
    def __init__(self):
        self.renal_rules = RENAL_DOSING_RULES
        logger.info(f"Dosing engine initialized with {len(self.renal_rules)} drug rules")
    
    def calculate_patient_gfr(self, patient: PatientContext) -> Optional[float]:
        """Calculate GFR for patient if possible"""
        if patient.gfr:
            return patient.gfr
        
        if (patient.age and patient.weight_kg and 
            patient.serum_creatinine and patient.sex):
            return GFRCalculator.cockcroft_gault(
                age=patient.age,
                weight_kg=patient.weight_kg,
                serum_creatinine=patient.serum_creatinine,
                is_female=patient.sex == "F"
            )
        
        return None
    
    def classify_renal_status(self, patient: PatientContext) -> RenalImpairment:
        """Determine renal impairment level"""
        if patient.renal_impairment != RenalImpairment.NORMAL:
            return patient.renal_impairment
        
        gfr = self.calculate_patient_gfr(patient)
        if gfr:
            return GFRCalculator.classify_renal_function(gfr)
        
        return RenalImpairment.NORMAL
    
    def get_renal_adjustment(
        self, 
        medication: Medication, 
        patient: PatientContext
    ) -> Optional[DosingAdjustment]:
        """Get renal dosing adjustment for a medication"""
        renal_status = self.classify_renal_status(patient)
        
        if renal_status == RenalImpairment.NORMAL:
            return None
        
        # Check for exact drug match
        drug_key = self._find_drug_key(medication)
        if not drug_key:
            return None
        
        adjustments = self.renal_rules.get(drug_key, {})
        
        if renal_status in adjustments:
            dose_info, notes = adjustments[renal_status]
            
            gfr = self.calculate_patient_gfr(patient)
            gfr_range = f"GFR: {gfr:.0f} mL/min" if gfr else None
            
            return DosingAdjustment(
                medication_id=medication.id,
                medication_name=medication.commercial_name,
                standard_dose="See package insert",
                adjusted_dose=dose_info,
                adjustment_reason=notes,
                impairment_type="renal",
                impairment_level=renal_status.value,
                gfr_range=gfr_range,
                monitoring_required=True,
                monitoring_parameters=self._get_monitoring_params(drug_key, renal_status),
                contraindicated="contraindicated" in dose_info.lower() or "avoid" in dose_info.lower(),
                source="Egyptian National Formulary / Renal Drug Handbook"
            )
        
        return None
    
    def _find_drug_key(self, medication: Medication) -> Optional[str]:
        """Find matching drug key in dosing rules"""
        # Check commercial name
        name_lower = medication.commercial_name.lower()
        for drug_key in self.renal_rules.keys():
            if drug_key in name_lower:
                return drug_key
        
        # Check generic name
        if medication.generic_name:
            generic_lower = medication.generic_name.lower()
            for drug_key in self.renal_rules.keys():
                if drug_key in generic_lower:
                    return drug_key
        
        # Check drug class (e.g., NSAIDs)
        if any(nsaid in name_lower for nsaid in ["ibuprofen", "diclofenac", "naproxen", 
                                                   "brufen", "cataflam", "voltaren"]):
            return "nsaid"
        
        return None
    
    def _get_monitoring_params(self, drug_key: str, renal_status: RenalImpairment) -> List[str]:
        """Get monitoring parameters for a drug"""
        monitoring = {
            "gentamicin": ["Trough and peak levels", "Serum creatinine", "Audiometry if prolonged use"],
            "vancomycin": ["Trough levels", "Serum creatinine", "CBC"],
            "digoxin": ["Digoxin level", "Potassium", "ECG"],
            "metformin": ["Lactic acid if symptomatic", "Serum creatinine", "B12 annually"],
            "enoxaparin": ["Anti-Xa levels if monitoring needed", "Platelets", "Signs of bleeding"],
            "spironolactone": ["Potassium", "Sodium", "Serum creatinine"],
            "lisinopril": ["Potassium", "Serum creatinine", "Blood pressure"],
        }
        
        return monitoring.get(drug_key, ["Serum creatinine", "Electrolytes"])
    
    def check_prescription(
        self, 
        medications: List[Medication], 
        patient: PatientContext
    ) -> List[DosingAdjustment]:
        """Check all medications in prescription for dosing adjustments"""
        adjustments = []
        
        for med in medications:
            renal_adj = self.get_renal_adjustment(med, patient)
            if renal_adj:
                adjustments.append(renal_adj)
        
        # Sort by severity (contraindicated first)
        adjustments.sort(key=lambda x: x.contraindicated, reverse=True)
        
        return adjustments


# Singleton instance
_dosing_engine: Optional[DosingEngine] = None

def get_dosing_engine() -> DosingEngine:
    """Get or create dosing engine singleton"""
    global _dosing_engine
    if _dosing_engine is None:
        _dosing_engine = DosingEngine()
    return _dosing_engine
