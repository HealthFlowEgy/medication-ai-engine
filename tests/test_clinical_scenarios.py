"""
Egyptian AI Medication Validation Engine - Clinical Scenario Tests
Sprint 4: Comprehensive Testing Suite
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import datetime

from src.core.models import (
    Medication, PatientContext, DDISeverity,
    RenalImpairment, Prescription, PrescriptionItem
)
from src.core.drug_database import EgyptianDrugDatabase
from src.core.validation_service import MedicationValidationService
from src.dosing.calculator import DosingEngine, GFRCalculator


class TestClinicalScenarios:
    """Clinical scenario-based integration tests"""
    
    @pytest.fixture
    def clinical_db(self):
        """Setup database with clinically relevant medications"""
        db = EgyptianDrugDatabase()
        
        medications = [
            {"Id": 1001, "CommercialName": "Warfarin 5mg 28/Tab"},
            {"Id": 1010, "CommercialName": "Aspocid 75mg 30/Tab"},
            {"Id": 1020, "CommercialName": "Brufen 400mg 30/Tab"},
            {"Id": 1033, "CommercialName": "Lanoxin 0.25mg 30/Tab"},
            {"Id": 1034, "CommercialName": "Cordarone 200mg 30/Tab"},
            {"Id": 1040, "CommercialName": "Glucophage 500mg 50/Tab"},
            {"Id": 1050, "CommercialName": "Ciprobay 500mg 10/Tab"},
            {"Id": 1060, "CommercialName": "Cipralex 10mg 28/Tab"},
            {"Id": 1063, "CommercialName": "Tramadol 50mg 20/Cap"},
            {"Id": 1072, "CommercialName": "Zocor 20mg 28/Tab"},
            {"Id": 1054, "CommercialName": "Klacid 500mg 14/Tab"},
            {"Id": 1065, "CommercialName": "Neurontin 300mg 50/Cap"},
            {"Id": 1055, "CommercialName": "Garamycin 80mg 1/Amp"},
        ]
        
        for med_data in medications:
            med = Medication.from_egyptian_db(med_data)
            db._process_medication(med)
        
        db._loaded = True
        return db
    
    @pytest.fixture
    def validation_service(self, clinical_db):
        return MedicationValidationService(drug_db=clinical_db)
    
    def test_scenario_warfarin_aspirin_interaction(self, validation_service):
        """Warfarin + Aspirin = MAJOR bleeding risk"""
        patient = PatientContext(age=75, sex="M")
        items = [
            PrescriptionItem(medication_id=1001, medication_name="Warfarin", dose="5mg", frequency="daily"),
            PrescriptionItem(medication_id=1010, medication_name="Aspocid", dose="75mg", frequency="daily"),
        ]
        prescription = Prescription(id="TEST-001", patient=patient, items=items)
        result = validation_service.validate_prescription(prescription)
        
        assert result.has_major_interactions
    
    def test_scenario_digoxin_amiodarone_interaction(self, validation_service):
        """Digoxin + Amiodarone = MAJOR toxicity risk"""
        patient = PatientContext(age=70, sex="M")
        items = [
            PrescriptionItem(medication_id=1033, medication_name="Lanoxin", dose="0.25mg", frequency="daily"),
            PrescriptionItem(medication_id=1034, medication_name="Cordarone", dose="200mg", frequency="daily"),
        ]
        prescription = Prescription(id="TEST-002", patient=patient, items=items)
        result = validation_service.validate_prescription(prescription)
        
        assert result.has_major_interactions
    
    def test_scenario_metformin_renal_impairment(self, validation_service):
        """Metformin contraindicated in severe renal impairment"""
        patient = PatientContext(age=65, sex="M", gfr=20, renal_impairment=RenalImpairment.SEVERE)
        items = [
            PrescriptionItem(medication_id=1040, medication_name="Glucophage", dose="500mg", frequency="BID"),
        ]
        prescription = Prescription(id="TEST-003", patient=patient, items=items)
        result = validation_service.validate_prescription(prescription)
        
        assert not result.is_valid
        assert any(da.contraindicated for da in result.dosing_adjustments)
    
    def test_scenario_ssri_tramadol_serotonin(self, validation_service):
        """SSRI + Tramadol = Serotonin syndrome risk"""
        patient = PatientContext(age=45, sex="F")
        items = [
            PrescriptionItem(medication_id=1060, medication_name="Cipralex", dose="10mg", frequency="daily"),
            PrescriptionItem(medication_id=1063, medication_name="Tramadol", dose="50mg", frequency="QID"),
        ]
        prescription = Prescription(id="TEST-004", patient=patient, items=items)
        result = validation_service.validate_prescription(prescription)
        
        assert result.has_major_interactions
    
    def test_scenario_qt_prolongation(self, validation_service):
        """Amiodarone + Fluoroquinolone = QT prolongation"""
        patient = PatientContext(age=65, sex="M")
        items = [
            PrescriptionItem(medication_id=1034, medication_name="Cordarone", dose="200mg", frequency="daily"),
            PrescriptionItem(medication_id=1050, medication_name="Ciprobay", dose="500mg", frequency="BID"),
        ]
        prescription = Prescription(id="TEST-005", patient=patient, items=items)
        result = validation_service.validate_prescription(prescription)
        
        assert result.has_major_interactions
    
    def test_scenario_statin_macrolide(self, validation_service):
        """Simvastatin + Clarithromycin = Rhabdomyolysis risk"""
        patient = PatientContext(age=55, sex="M")
        items = [
            PrescriptionItem(medication_id=1072, medication_name="Zocor", dose="20mg", frequency="daily"),
            PrescriptionItem(medication_id=1054, medication_name="Klacid", dose="500mg", frequency="BID"),
        ]
        prescription = Prescription(id="TEST-006", patient=patient, items=items)
        result = validation_service.validate_prescription(prescription)
        
        assert len(result.interactions) > 0
    
    def test_scenario_pregnancy_warfarin(self, validation_service):
        """Warfarin contraindicated in pregnancy"""
        patient = PatientContext(age=28, sex="F", is_pregnant=True)
        items = [
            PrescriptionItem(medication_id=1001, medication_name="Warfarin", dose="5mg", frequency="daily"),
        ]
        prescription = Prescription(id="TEST-007", patient=patient, items=items)
        result = validation_service.validate_prescription(prescription)
        
        assert not result.is_valid
        assert len(result.contraindications) > 0
    
    def test_scenario_elderly_polypharmacy(self, validation_service):
        """Elderly patient warning for polypharmacy"""
        patient = PatientContext(age=80, sex="F")
        items = [
            PrescriptionItem(medication_id=1001, medication_name="Warfarin", dose="5mg", frequency="daily"),
            PrescriptionItem(medication_id=1033, medication_name="Lanoxin", dose="0.25mg", frequency="daily"),
            PrescriptionItem(medication_id=1040, medication_name="Glucophage", dose="500mg", frequency="BID"),
        ]
        prescription = Prescription(id="TEST-008", patient=patient, items=items)
        result = validation_service.validate_prescription(prescription)
        
        assert any("elderly" in w.lower() or "65" in w for w in result.warnings)


class TestPerformance:
    """Performance tests"""
    
    def test_validation_under_200ms(self):
        """Validation should complete in < 200ms"""
        import time
        
        db = EgyptianDrugDatabase()
        for i in range(100):
            med = Medication(id=i, commercial_name=f"Med{i} 100mg Tab")
            db._process_medication(med)
        db._loaded = True
        
        service = MedicationValidationService(drug_db=db)
        patient = PatientContext(age=50, sex="M")
        items = [PrescriptionItem(medication_id=i, medication_name=f"Med{i}", dose="100mg", frequency="daily") for i in range(10)]
        prescription = Prescription(id="perf-test", patient=patient, items=items)
        
        start = time.time()
        for _ in range(10):
            service.validate_prescription(prescription)
        elapsed = (time.time() - start) * 1000 / 10
        
        assert elapsed < 200, f"Validation took {elapsed}ms"


class TestEdgeCases:
    """Edge case tests"""
    
    def test_empty_prescription(self):
        db = EgyptianDrugDatabase()
        db._loaded = True
        service = MedicationValidationService(drug_db=db)
        
        prescription = Prescription(id="empty", patient=PatientContext(), items=[])
        result = service.validate_prescription(prescription)
        
        assert result.is_valid
    
    def test_extreme_gfr_values(self):
        assert GFRCalculator.classify_renal_function(0) == RenalImpairment.ESRD
        assert GFRCalculator.classify_renal_function(150) == RenalImpairment.NORMAL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
