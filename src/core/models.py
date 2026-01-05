"""
Egyptian AI Medication Validation Engine - Data Models
Sprint 0: Foundation Data Structures
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
import re


class DosageForm(Enum):
    TABLET = "tablet"
    CAPSULE = "capsule"
    SYRUP = "syrup"
    INJECTION = "injection"
    AMPOULE = "ampoule"
    CREAM = "cream"
    GEL = "gel"
    OINTMENT = "ointment"
    DROP = "drop"
    SUSPENSION = "suspension"
    SOLUTION = "solution"
    SUPPOSITORY = "suppository"
    INHALER = "inhaler"
    PATCH = "patch"
    POWDER = "powder"
    OTHER = "other"


class DDISeverity(Enum):
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"
    UNKNOWN = "unknown"


class RenalImpairment(Enum):
    NORMAL = "normal"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    ESRD = "esrd"


class HepaticImpairment(Enum):
    NONE = "none"
    CHILD_PUGH_A = "child_pugh_a"
    CHILD_PUGH_B = "child_pugh_b"
    CHILD_PUGH_C = "child_pugh_c"


@dataclass
class Medication:
    """Egyptian medication from EDA database"""
    id: int
    commercial_name: str
    generic_name: Optional[str] = None
    arabic_name: Optional[str] = None
    active_ingredients: List[str] = field(default_factory=list)
    strength: Optional[str] = None
    strength_value: Optional[float] = None
    strength_unit: Optional[str] = None
    dosage_form: DosageForm = DosageForm.OTHER
    package_size: Optional[str] = None
    manufacturer: Optional[str] = None
    atc_code: Optional[str] = None
    eda_registration: Optional[str] = None
    rxnorm_id: Optional[str] = None
    drugbank_id: Optional[str] = None
    is_otc: bool = False
    is_controlled: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_egyptian_db(cls, row: Dict[str, Any]) -> "Medication":
        """Parse medication from Egyptian database row"""
        commercial_name = row.get("CommercialName", "")
        parsed = cls._parse_commercial_name(commercial_name)
        
        return cls(
            id=row.get("Id", 0),
            commercial_name=commercial_name,
            strength=parsed.get("strength"),
            strength_value=parsed.get("strength_value"),
            strength_unit=parsed.get("strength_unit"),
            dosage_form=parsed.get("dosage_form", DosageForm.OTHER),
            package_size=parsed.get("package_size"),
        )
    
    @staticmethod
    def _parse_commercial_name(name: str) -> Dict[str, Any]:
        """Extract structured data from commercial name"""
        result = {}
        
        # Extract strength (e.g., "500mg", "125mg/5ml")
        strength_pattern = r'(\d+(?:\.\d+)?)\s*(mg|g|ml|mcg|µg|iu|%)'
        strength_match = re.search(strength_pattern, name, re.IGNORECASE)
        if strength_match:
            result["strength_value"] = float(strength_match.group(1))
            result["strength_unit"] = strength_match.group(2).lower()
            result["strength"] = strength_match.group(0)
        
        # Extract package size (e.g., "30/Tab", "100ml")
        package_patterns = [
            r'(\d+)\s*/\s*(Tab|Cap|Amp|Sach)',
            r'(\d+)\s*ml\s*(Syrup|Susp|Drop|Solution)?',
            r'(\d+)\s*gm?\s*(Cream|Gel|Oint)',
        ]
        for pattern in package_patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                result["package_size"] = match.group(0)
                break
        
        # Determine dosage form
        form_mapping = {
            r'\bTab\b|\bTablet\b|F\.C\.Tab': DosageForm.TABLET,
            r'\bCap\b|\bCapsule\b': DosageForm.CAPSULE,
            r'\bSyrup\b|\bSyr\b': DosageForm.SYRUP,
            r'\bAmp\b|\bAmpoule\b': DosageForm.AMPOULE,
            r'\bInj\b|\bInjection\b|\bVial\b': DosageForm.INJECTION,
            r'\bCream\b|\bCrm\b': DosageForm.CREAM,
            r'\bGel\b|\bEmulgel\b': DosageForm.GEL,
            r'\bOint\b|\bOintment\b': DosageForm.OINTMENT,
            r'\bDrop\b': DosageForm.DROP,
            r'\bSusp\b|\bSuspension\b': DosageForm.SUSPENSION,
            r'\bSolution\b|\bSol\b': DosageForm.SOLUTION,
            r'\bSupp\b|\bSuppository\b': DosageForm.SUPPOSITORY,
            r'\bInhaler\b|\bMDI\b|\bDiskus\b|\bTurbuhaler\b': DosageForm.INHALER,
            r'\bPatch\b': DosageForm.PATCH,
            r'\bPowder\b|\bSach\b': DosageForm.POWDER,
        }
        
        for pattern, form in form_mapping.items():
            if re.search(pattern, name, re.IGNORECASE):
                result["dosage_form"] = form
                break
        
        return result


@dataclass
class DrugInteraction:
    """Drug-Drug Interaction record"""
    id: Optional[int] = None
    drug1_id: int = 0
    drug2_id: int = 0
    drug1_name: str = ""
    drug2_name: str = ""
    severity: DDISeverity = DDISeverity.UNKNOWN
    interaction_type: str = ""
    mechanism: str = ""
    clinical_effect: str = ""
    management: str = ""
    evidence_level: int = 0  # 1=Label, 2=Study, 3=Case Report, 4=Theoretical
    source: str = ""
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class DosingAdjustment:
    """Dosing adjustment recommendation"""
    medication_id: int
    medication_name: str
    standard_dose: str
    adjusted_dose: str
    adjustment_reason: str
    impairment_type: str  # "renal" or "hepatic"
    impairment_level: str
    gfr_range: Optional[str] = None
    child_pugh_class: Optional[str] = None
    monitoring_required: bool = False
    monitoring_parameters: List[str] = field(default_factory=list)
    contraindicated: bool = False
    source: str = ""


@dataclass
class PatientContext:
    """Patient information for personalized validation"""
    age: Optional[int] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    sex: Optional[str] = None  # "M" or "F"
    serum_creatinine: Optional[float] = None  # mg/dL
    gfr: Optional[float] = None  # mL/min/1.73m²
    renal_impairment: RenalImpairment = RenalImpairment.NORMAL
    hepatic_impairment: HepaticImpairment = HepaticImpairment.NONE
    child_pugh_score: Optional[int] = None
    allergies: List[str] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    current_medications: List[int] = field(default_factory=list)
    is_pregnant: bool = False
    is_breastfeeding: bool = False


@dataclass
class ValidationResult:
    """Result of medication validation"""
    is_valid: bool
    prescription_id: Optional[str] = None
    medications_validated: int = 0
    interactions: List[DrugInteraction] = field(default_factory=list)
    dosing_adjustments: List[DosingAdjustment] = field(default_factory=list)
    contraindications: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    validation_time_ms: float = 0
    validated_at: datetime = field(default_factory=datetime.now)
    
    @property
    def has_major_interactions(self) -> bool:
        return any(i.severity == DDISeverity.MAJOR for i in self.interactions)
    
    @property
    def interaction_count(self) -> Dict[str, int]:
        counts = {"major": 0, "moderate": 0, "minor": 0}
        for i in self.interactions:
            if i.severity == DDISeverity.MAJOR:
                counts["major"] += 1
            elif i.severity == DDISeverity.MODERATE:
                counts["moderate"] += 1
            elif i.severity == DDISeverity.MINOR:
                counts["minor"] += 1
        return counts


@dataclass 
class PrescriptionItem:
    """Single medication in a prescription"""
    medication_id: int
    medication_name: str
    dose: str
    frequency: str
    duration: Optional[str] = None
    route: Optional[str] = None
    instructions: Optional[str] = None


@dataclass
class Prescription:
    """Full prescription for validation"""
    id: str
    patient: PatientContext
    items: List[PrescriptionItem]
    prescriber_id: Optional[str] = None
    pharmacy_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
