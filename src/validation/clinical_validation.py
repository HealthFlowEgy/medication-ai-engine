"""
Egyptian AI Medication Validation Engine
Sprint 9-10: Clinical Validation & Pilot Launch

This module provides:
1. Clinical validation test framework
2. Performance benchmarking
3. Pilot pharmacy management
4. Launch readiness checklist
"""
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== Clinical Test Cases ====================

class ClinicalScenarioCategory(Enum):
    """Categories of clinical validation scenarios"""
    ANTICOAGULATION = "anticoagulation"
    CARDIAC = "cardiac"
    RENAL = "renal"
    HEPATIC = "hepatic"
    DIABETES = "diabetes"
    CNS = "cns"
    RESPIRATORY = "respiratory"
    INFECTION = "infection"
    ONCOLOGY = "oncology"
    PREGNANCY = "pregnancy"
    PEDIATRIC = "pediatric"
    GERIATRIC = "geriatric"


@dataclass
class ClinicalTestCase:
    """Clinical validation test case"""
    id: str
    name: str
    category: ClinicalScenarioCategory
    description: str
    
    # Patient context
    patient_age: int
    patient_sex: str
    patient_conditions: List[str]
    
    # Prescription
    medications: List[Dict[str, str]]
    
    # Expected results
    expected_interactions: List[Dict[str, str]]
    expected_contraindications: List[str]
    expected_dosing_adjustments: List[str]
    expected_status: str  # "valid", "warning", "blocked"
    
    # Metadata
    evidence_source: str
    priority: str  # "critical", "high", "medium", "low"
    
    # Optional fields with defaults
    patient_weight: Optional[float] = None
    patient_gfr: Optional[float] = None
    patient_pregnant: bool = False
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d["category"] = self.category.value
        return d


# Clinical validation test suite
CLINICAL_TEST_SUITE = [
    # ==================== Anticoagulation Scenarios ====================
    ClinicalTestCase(
        id="CLIN-001",
        name="Warfarin Triple Therapy",
        category=ClinicalScenarioCategory.ANTICOAGULATION,
        description="Post-MI patient on warfarin, aspirin, and clopidogrel - high bleeding risk",
        patient_age=68, patient_sex="M",
        patient_conditions=["atrial_fibrillation", "recent_MI", "coronary_stent"],
        patient_gfr=65,
        medications=[
            {"name": "Warfarin", "dose": "5mg", "frequency": "daily"},
            {"name": "Aspirin", "dose": "81mg", "frequency": "daily"},
            {"name": "Clopidogrel", "dose": "75mg", "frequency": "daily"},
        ],
        expected_interactions=[
            {"drug1": "warfarin", "drug2": "aspirin", "severity": "major"},
            {"drug1": "warfarin", "drug2": "clopidogrel", "severity": "major"},
        ],
        expected_contraindications=[],
        expected_dosing_adjustments=[],
        expected_status="blocked",
        evidence_source="ACC/AHA Guidelines 2020",
        priority="critical"
    ),
    
    ClinicalTestCase(
        id="CLIN-002",
        name="Warfarin + Fluconazole CYP Interaction",
        category=ClinicalScenarioCategory.ANTICOAGULATION,
        description="Patient on warfarin develops candidiasis requiring fluconazole",
        patient_age=72, patient_sex="F",
        patient_conditions=["atrial_fibrillation", "diabetes"],
        patient_gfr=55,
        medications=[
            {"name": "Warfarin", "dose": "3mg", "frequency": "daily"},
            {"name": "Fluconazole", "dose": "200mg", "frequency": "daily"},
        ],
        expected_interactions=[
            {"drug1": "warfarin", "drug2": "fluconazole", "severity": "major"},
        ],
        expected_contraindications=[],
        expected_dosing_adjustments=[],
        expected_status="blocked",
        evidence_source="Lexicomp Drug Interactions",
        priority="critical"
    ),
    
    # ==================== Cardiac Scenarios ====================
    ClinicalTestCase(
        id="CLIN-003",
        name="Digoxin + Amiodarone Toxicity",
        category=ClinicalScenarioCategory.CARDIAC,
        description="Heart failure patient on digoxin started on amiodarone for AF",
        patient_age=75, patient_sex="M",
        patient_conditions=["heart_failure", "atrial_fibrillation"],
        patient_gfr=45,
        medications=[
            {"name": "Digoxin", "dose": "0.25mg", "frequency": "daily"},
            {"name": "Amiodarone", "dose": "200mg", "frequency": "daily"},
            {"name": "Furosemide", "dose": "40mg", "frequency": "daily"},
        ],
        expected_interactions=[
            {"drug1": "digoxin", "drug2": "amiodarone", "severity": "major"},
        ],
        expected_contraindications=[],
        expected_dosing_adjustments=["digoxin: reduce dose 50%"],
        expected_status="blocked",
        evidence_source="ESC Heart Failure Guidelines",
        priority="critical"
    ),
    
    ClinicalTestCase(
        id="CLIN-004",
        name="QT Prolongation Combination",
        category=ClinicalScenarioCategory.CARDIAC,
        description="Patient on amiodarone prescribed ciprofloxacin for UTI",
        patient_age=65, patient_sex="M",
        patient_conditions=["atrial_fibrillation", "UTI"],
        patient_gfr=70,
        medications=[
            {"name": "Amiodarone", "dose": "200mg", "frequency": "daily"},
            {"name": "Ciprofloxacin", "dose": "500mg", "frequency": "BID"},
        ],
        expected_interactions=[
            {"drug1": "amiodarone", "drug2": "ciprofloxacin", "severity": "major"},
        ],
        expected_contraindications=[],
        expected_dosing_adjustments=[],
        expected_status="blocked",
        evidence_source="CredibleMeds QT Risk List",
        priority="critical"
    ),
    
    # ==================== Renal Scenarios ====================
    ClinicalTestCase(
        id="CLIN-005",
        name="Metformin in Severe CKD",
        category=ClinicalScenarioCategory.RENAL,
        description="Diabetic patient with CKD Stage 4 on metformin",
        patient_age=70, patient_sex="M",
        patient_conditions=["diabetes", "CKD_stage_4", "hypertension"],
        patient_gfr=22,
        medications=[
            {"name": "Metformin", "dose": "1000mg", "frequency": "BID"},
            {"name": "Lisinopril", "dose": "10mg", "frequency": "daily"},
        ],
        expected_interactions=[],
        expected_contraindications=["metformin contraindicated GFR<30"],
        expected_dosing_adjustments=["metformin: contraindicated"],
        expected_status="blocked",
        evidence_source="KDIGO CKD Guidelines",
        priority="critical"
    ),
    
    ClinicalTestCase(
        id="CLIN-006",
        name="Gentamicin Renal Dosing",
        category=ClinicalScenarioCategory.RENAL,
        description="Septic patient with moderate renal impairment needing gentamicin",
        patient_age=60, patient_sex="F",
        patient_conditions=["sepsis", "CKD_stage_3"],
        patient_gfr=38,
        medications=[
            {"name": "Gentamicin", "dose": "5mg/kg", "frequency": "Q8H"},
        ],
        expected_interactions=[],
        expected_contraindications=[],
        expected_dosing_adjustments=["gentamicin: extend interval to Q24-36H, TDM required"],
        expected_status="warning",
        evidence_source="IDSA Aminoglycoside Guidelines",
        priority="high"
    ),
    
    # ==================== CNS Scenarios ====================
    ClinicalTestCase(
        id="CLIN-007",
        name="Serotonin Syndrome Risk",
        category=ClinicalScenarioCategory.CNS,
        description="Patient on SSRI prescribed tramadol for pain",
        patient_age=45, patient_sex="F",
        patient_conditions=["depression", "fibromyalgia"],
        patient_gfr=90,
        medications=[
            {"name": "Escitalopram", "dose": "10mg", "frequency": "daily"},
            {"name": "Tramadol", "dose": "50mg", "frequency": "Q6H"},
        ],
        expected_interactions=[
            {"drug1": "escitalopram", "drug2": "tramadol", "severity": "major"},
        ],
        expected_contraindications=[],
        expected_dosing_adjustments=[],
        expected_status="blocked",
        evidence_source="Boyer & Shannon Serotonin Syndrome Criteria",
        priority="critical"
    ),
    
    ClinicalTestCase(
        id="CLIN-008",
        name="Opioid + Benzodiazepine CNS Depression",
        category=ClinicalScenarioCategory.CNS,
        description="Patient on morphine prescribed alprazolam for anxiety",
        patient_age=55, patient_sex="M",
        patient_conditions=["chronic_pain", "anxiety"],
        patient_gfr=85,
        medications=[
            {"name": "Morphine SR", "dose": "30mg", "frequency": "BID"},
            {"name": "Alprazolam", "dose": "0.5mg", "frequency": "TID"},
        ],
        expected_interactions=[
            {"drug1": "morphine", "drug2": "alprazolam", "severity": "major"},
        ],
        expected_contraindications=[],
        expected_dosing_adjustments=[],
        expected_status="blocked",
        evidence_source="FDA Black Box Warning",
        priority="critical"
    ),
    
    # ==================== Pregnancy Scenarios ====================
    ClinicalTestCase(
        id="CLIN-009",
        name="Pregnancy Contraindicated Medications",
        category=ClinicalScenarioCategory.PREGNANCY,
        description="Pregnant woman with DVT on warfarin",
        patient_age=28, patient_sex="F",
        patient_conditions=["DVT", "pregnant_first_trimester"],
        patient_gfr=95, patient_pregnant=True,
        medications=[
            {"name": "Warfarin", "dose": "5mg", "frequency": "daily"},
        ],
        expected_interactions=[],
        expected_contraindications=["warfarin: teratogenic - contraindicated in pregnancy"],
        expected_dosing_adjustments=[],
        expected_status="blocked",
        evidence_source="FDA Pregnancy Category X",
        priority="critical"
    ),
    
    # ==================== Diabetes Scenarios ====================
    ClinicalTestCase(
        id="CLIN-010",
        name="Sulfonylurea + Fluconazole Hypoglycemia",
        category=ClinicalScenarioCategory.DIABETES,
        description="Diabetic patient on glipizide develops fungal infection",
        patient_age=62, patient_sex="M",
        patient_conditions=["diabetes", "onychomycosis"],
        patient_gfr=60,
        medications=[
            {"name": "Glipizide", "dose": "10mg", "frequency": "daily"},
            {"name": "Fluconazole", "dose": "150mg", "frequency": "weekly"},
        ],
        expected_interactions=[
            {"drug1": "glipizide", "drug2": "fluconazole", "severity": "major"},
        ],
        expected_contraindications=[],
        expected_dosing_adjustments=[],
        expected_status="warning",
        evidence_source="ADA Standards of Care",
        priority="high"
    ),
    
    # ==================== Statin Scenarios ====================
    ClinicalTestCase(
        id="CLIN-011",
        name="Simvastatin + Clarithromycin Rhabdomyolysis",
        category=ClinicalScenarioCategory.INFECTION,
        description="Patient on simvastatin develops respiratory infection",
        patient_age=58, patient_sex="M",
        patient_conditions=["hyperlipidemia", "COPD_exacerbation"],
        patient_gfr=75,
        medications=[
            {"name": "Simvastatin", "dose": "40mg", "frequency": "daily"},
            {"name": "Clarithromycin", "dose": "500mg", "frequency": "BID"},
        ],
        expected_interactions=[
            {"drug1": "simvastatin", "drug2": "clarithromycin", "severity": "major"},
        ],
        expected_contraindications=["combination contraindicated"],
        expected_dosing_adjustments=[],
        expected_status="blocked",
        evidence_source="FDA Drug Safety Communication",
        priority="critical"
    ),
    
    # ==================== Geriatric Scenarios ====================
    ClinicalTestCase(
        id="CLIN-012",
        name="Elderly Polypharmacy High-Risk",
        category=ClinicalScenarioCategory.GERIATRIC,
        description="85-year-old on multiple high-risk medications",
        patient_age=85, patient_sex="F",
        patient_conditions=["atrial_fibrillation", "hypertension", "osteoarthritis", "insomnia"],
        patient_gfr=42,
        medications=[
            {"name": "Warfarin", "dose": "2mg", "frequency": "daily"},
            {"name": "Aspirin", "dose": "81mg", "frequency": "daily"},
            {"name": "Ibuprofen", "dose": "400mg", "frequency": "TID"},
            {"name": "Zolpidem", "dose": "10mg", "frequency": "at bedtime"},
        ],
        expected_interactions=[
            {"drug1": "warfarin", "drug2": "aspirin", "severity": "major"},
            {"drug1": "warfarin", "drug2": "ibuprofen", "severity": "major"},
        ],
        expected_contraindications=["NSAIDs: high risk in elderly on anticoagulation"],
        expected_dosing_adjustments=["zolpidem: max 5mg in elderly"],
        expected_status="blocked",
        evidence_source="Beers Criteria 2023",
        priority="critical"
    ),
]


# ==================== Pilot Pharmacy Configuration ====================

@dataclass
class PilotPharmacy:
    """Pilot pharmacy configuration"""
    code: str
    name: str
    location: str
    type: str  # "hospital", "community", "chain"
    daily_prescriptions: int
    start_date: str
    contact_name: str
    contact_phone: str
    contact_email: str
    status: str = "pending"  # "pending", "active", "paused", "completed"
    
    # Metrics
    total_validations: int = 0
    total_blocked: int = 0
    total_warnings: int = 0
    false_positives_reported: int = 0
    pharmacist_overrides: int = 0


PILOT_PHARMACIES = [
    PilotPharmacy(
        code="PHR-HOSP-001",
        name="Cairo University Hospital Pharmacy",
        location="Cairo",
        type="hospital",
        daily_prescriptions=500,
        start_date="2026-02-01",
        contact_name="Dr. Ahmed Hassan",
        contact_phone="+20-2-XXXX-XXXX",
        contact_email="pharmacy@cu.edu.eg"
    ),
    PilotPharmacy(
        code="PHR-HOSP-002",
        name="Ain Shams University Hospital Pharmacy",
        location="Cairo",
        type="hospital",
        daily_prescriptions=450,
        start_date="2026-02-01",
        contact_name="Dr. Fatima Ali",
        contact_phone="+20-2-XXXX-XXXX",
        contact_email="pharmacy@asu.edu.eg"
    ),
    PilotPharmacy(
        code="PHR-COMM-001",
        name="Seif Pharmacy - Maadi Branch",
        location="Cairo - Maadi",
        type="community",
        daily_prescriptions=150,
        start_date="2026-02-15",
        contact_name="Dr. Omar Khaled",
        contact_phone="+20-2-XXXX-XXXX",
        contact_email="maadi@seifpharmacy.com"
    ),
    PilotPharmacy(
        code="PHR-CHAIN-001",
        name="El Ezaby Pharmacy - Heliopolis",
        location="Cairo - Heliopolis",
        type="chain",
        daily_prescriptions=200,
        start_date="2026-02-15",
        contact_name="Dr. Sara Mohamed",
        contact_phone="+20-2-XXXX-XXXX",
        contact_email="heliopolis@elezaby.com"
    ),
    PilotPharmacy(
        code="PHR-HOSP-003",
        name="Alexandria University Hospital Pharmacy",
        location="Alexandria",
        type="hospital",
        daily_prescriptions=400,
        start_date="2026-03-01",
        contact_name="Dr. Mahmoud Ibrahim",
        contact_phone="+20-3-XXXX-XXXX",
        contact_email="pharmacy@alexu.edu.eg"
    ),
]


# ==================== Launch Readiness Checklist ====================

@dataclass
class ChecklistItem:
    """Launch readiness checklist item"""
    id: str
    category: str
    description: str
    owner: str
    due_date: str
    status: str = "pending"  # "pending", "in_progress", "completed", "blocked"
    notes: str = ""


LAUNCH_CHECKLIST = [
    # Technical Readiness
    ChecklistItem("TECH-001", "Technical", "All 49+ unit tests passing", "Dev Team", "2026-01-15", "completed"),
    ChecklistItem("TECH-002", "Technical", "Performance < 200ms for validation", "Dev Team", "2026-01-15", "completed"),
    ChecklistItem("TECH-003", "Technical", "Kubernetes deployment tested", "DevOps", "2026-01-20", "in_progress"),
    ChecklistItem("TECH-004", "Technical", "Monitoring dashboards configured", "DevOps", "2026-01-20", "in_progress"),
    ChecklistItem("TECH-005", "Technical", "Alerting rules validated", "DevOps", "2026-01-22", "pending"),
    ChecklistItem("TECH-006", "Technical", "Backup and recovery tested", "DevOps", "2026-01-25", "pending"),
    ChecklistItem("TECH-007", "Technical", "SSL/TLS certificates configured", "DevOps", "2026-01-20", "completed"),
    ChecklistItem("TECH-008", "Technical", "API rate limiting tested", "Dev Team", "2026-01-18", "completed"),
    
    # Clinical Validation
    ChecklistItem("CLIN-001", "Clinical", "Clinical test suite executed (12 scenarios)", "Clinical Team", "2026-01-25", "in_progress"),
    ChecklistItem("CLIN-002", "Clinical", "Egyptian Medical Syndicate review", "Regulatory", "2026-02-01", "pending"),
    ChecklistItem("CLIN-003", "Clinical", "EDA formulary alignment verified", "Clinical Team", "2026-01-28", "pending"),
    ChecklistItem("CLIN-004", "Clinical", "False positive rate < 1%", "Clinical Team", "2026-01-30", "pending"),
    ChecklistItem("CLIN-005", "Clinical", "DDI rules reviewed by clinical pharmacist", "Clinical Team", "2026-01-22", "in_progress"),
    
    # Security
    ChecklistItem("SEC-001", "Security", "Penetration testing completed", "Security", "2026-01-25", "pending"),
    ChecklistItem("SEC-002", "Security", "HIPAA/data protection compliance review", "Legal", "2026-01-28", "pending"),
    ChecklistItem("SEC-003", "Security", "API authentication implemented", "Dev Team", "2026-01-18", "completed"),
    ChecklistItem("SEC-004", "Security", "Audit logging validated", "Dev Team", "2026-01-20", "completed"),
    
    # Integration
    ChecklistItem("INT-001", "Integration", "HealthFlow API integration tested", "Dev Team", "2026-01-22", "in_progress"),
    ChecklistItem("INT-002", "Integration", "Webhook delivery confirmed", "Dev Team", "2026-01-22", "completed"),
    ChecklistItem("INT-003", "Integration", "Batch processing validated", "Dev Team", "2026-01-20", "completed"),
    
    # Operations
    ChecklistItem("OPS-001", "Operations", "On-call rotation established", "DevOps", "2026-01-28", "pending"),
    ChecklistItem("OPS-002", "Operations", "Runbooks documented", "DevOps", "2026-01-25", "in_progress"),
    ChecklistItem("OPS-003", "Operations", "SLA defined (99.9% uptime)", "Management", "2026-01-20", "completed"),
    
    # Pilot
    ChecklistItem("PILOT-001", "Pilot", "Pilot pharmacies onboarded (5)", "Operations", "2026-02-01", "in_progress"),
    ChecklistItem("PILOT-002", "Pilot", "Pharmacist training completed", "Training", "2026-02-05", "pending"),
    ChecklistItem("PILOT-003", "Pilot", "Feedback mechanism established", "Product", "2026-01-28", "completed"),
    ChecklistItem("PILOT-004", "Pilot", "Escalation process defined", "Operations", "2026-01-25", "completed"),
]


# ==================== Validation Runner ====================

class ClinicalValidationRunner:
    """Execute clinical validation test suite"""
    
    def __init__(self, validation_service):
        self.validation_service = validation_service
        self.results = []
    
    def run_test(self, test_case: ClinicalTestCase) -> Dict:
        """Run a single clinical test case"""
        from src.core.models import PatientContext, Prescription, PrescriptionItem, RenalImpairment
        
        # Build patient context
        renal_status = RenalImpairment.NORMAL
        if test_case.patient_gfr:
            if test_case.patient_gfr < 15:
                renal_status = RenalImpairment.ESRD
            elif test_case.patient_gfr < 30:
                renal_status = RenalImpairment.SEVERE
            elif test_case.patient_gfr < 60:
                renal_status = RenalImpairment.MODERATE
            elif test_case.patient_gfr < 90:
                renal_status = RenalImpairment.MILD
        
        patient = PatientContext(
            age=test_case.patient_age,
            sex=test_case.patient_sex,
            weight_kg=test_case.patient_weight,
            gfr=test_case.patient_gfr,
            renal_impairment=renal_status,
            conditions=test_case.patient_conditions,
            is_pregnant=test_case.patient_pregnant
        )
        
        # Build prescription
        items = [
            PrescriptionItem(
                medication_id=i,
                medication_name=med["name"],
                dose=med["dose"],
                frequency=med["frequency"]
            )
            for i, med in enumerate(test_case.medications)
        ]
        
        prescription = Prescription(
            id=test_case.id,
            patient=patient,
            items=items
        )
        
        # Validate
        result = self.validation_service.validate_prescription(prescription)
        
        # Determine actual status
        if not result.is_valid or result.has_major_interactions:
            actual_status = "blocked"
        elif len(result.interactions) > 0 or len(result.warnings) > 0:
            actual_status = "warning"
        else:
            actual_status = "valid"
        
        # Check if test passed
        passed = actual_status == test_case.expected_status
        
        # Check interactions detected
        expected_major = [i for i in test_case.expected_interactions if i["severity"] == "major"]
        actual_major = [i for i in result.interactions if i.severity.value == "major"]
        
        interactions_correct = len(actual_major) >= len(expected_major)
        
        test_result = {
            "test_id": test_case.id,
            "test_name": test_case.name,
            "category": test_case.category.value,
            "priority": test_case.priority,
            "passed": passed and interactions_correct,
            "expected_status": test_case.expected_status,
            "actual_status": actual_status,
            "expected_major_interactions": len(expected_major),
            "actual_major_interactions": len(actual_major),
            "validation_time_ms": result.validation_time_ms,
            "details": {
                "interactions": [
                    {"drug1": i.drug1_name, "drug2": i.drug2_name, "severity": i.severity.value}
                    for i in result.interactions
                ],
                "warnings": result.warnings,
                "contraindications": result.contraindications
            }
        }
        
        self.results.append(test_result)
        return test_result
    
    def run_all_tests(self) -> Dict:
        """Run all clinical test cases"""
        self.results = []
        
        for test_case in CLINICAL_TEST_SUITE:
            try:
                self.run_test(test_case)
            except Exception as e:
                self.results.append({
                    "test_id": test_case.id,
                    "test_name": test_case.name,
                    "passed": False,
                    "error": str(e)
                })
        
        # Summary
        total = len(self.results)
        passed = sum(1 for r in self.results if r.get("passed", False))
        failed = total - passed
        
        critical_tests = [r for r in self.results if r.get("priority") == "critical"]
        critical_passed = sum(1 for r in critical_tests if r.get("passed", False))
        
        return {
            "summary": {
                "total_tests": total,
                "passed": passed,
                "failed": failed,
                "pass_rate": f"{(passed/total)*100:.1f}%",
                "critical_tests": len(critical_tests),
                "critical_passed": critical_passed,
                "all_critical_passed": critical_passed == len(critical_tests)
            },
            "results": self.results,
            "timestamp": datetime.now().isoformat()
        }


def get_launch_readiness_status() -> Dict:
    """Calculate overall launch readiness"""
    total = len(LAUNCH_CHECKLIST)
    completed = sum(1 for item in LAUNCH_CHECKLIST if item.status == "completed")
    in_progress = sum(1 for item in LAUNCH_CHECKLIST if item.status == "in_progress")
    pending = sum(1 for item in LAUNCH_CHECKLIST if item.status == "pending")
    blocked = sum(1 for item in LAUNCH_CHECKLIST if item.status == "blocked")
    
    # Group by category
    by_category = {}
    for item in LAUNCH_CHECKLIST:
        if item.category not in by_category:
            by_category[item.category] = {"total": 0, "completed": 0}
        by_category[item.category]["total"] += 1
        if item.status == "completed":
            by_category[item.category]["completed"] += 1
    
    return {
        "overall": {
            "total_items": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending,
            "blocked": blocked,
            "completion_rate": f"{(completed/total)*100:.1f}%",
            "ready_for_launch": blocked == 0 and pending == 0
        },
        "by_category": {
            cat: f"{stats['completed']}/{stats['total']}" 
            for cat, stats in by_category.items()
        },
        "blockers": [
            {"id": item.id, "description": item.description, "owner": item.owner}
            for item in LAUNCH_CHECKLIST if item.status == "blocked"
        ],
        "pending_critical": [
            {"id": item.id, "description": item.description, "due_date": item.due_date}
            for item in LAUNCH_CHECKLIST 
            if item.status == "pending" and item.category in ["Clinical", "Security"]
        ]
    }
