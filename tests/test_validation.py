"""
Egyptian AI Medication Validation Engine - Test Suite
Sprint 0-2: Core Functionality Tests
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import datetime

from src.core.models import (
    Medication, PatientContext, DrugInteraction, DDISeverity,
    RenalImpairment, DosageForm, Prescription, PrescriptionItem
)
from src.core.drug_database import EgyptianDrugDatabase
from src.core.ddi_engine import DDIEngine, DrugClassifier
from src.dosing.calculator import DosingEngine, GFRCalculator


class TestGFRCalculator:
    """Test GFR calculation functions"""
    
    def test_cockcroft_gault_male(self):
        """Test CrCl calculation for male patient"""
        crcl = GFRCalculator.cockcroft_gault(
            age=65,
            weight_kg=70,
            serum_creatinine=1.2,
            is_female=False
        )
        assert 55 < crcl < 65  # Expected ~60 mL/min
    
    def test_cockcroft_gault_female(self):
        """Test CrCl calculation for female patient"""
        crcl = GFRCalculator.cockcroft_gault(
            age=65,
            weight_kg=60,
            serum_creatinine=1.0,
            is_female=True
        )
        assert 45 < crcl < 55  # Should be lower due to female factor
    
    def test_ckd_epi(self):
        """Test CKD-EPI eGFR calculation"""
        egfr = GFRCalculator.ckd_epi(
            age=50,
            serum_creatinine=1.0,
            is_female=False
        )
        assert 80 < egfr < 100
    
    def test_renal_classification(self):
        """Test GFR classification"""
        assert GFRCalculator.classify_renal_function(95) == RenalImpairment.NORMAL
        assert GFRCalculator.classify_renal_function(70) == RenalImpairment.MILD
        assert GFRCalculator.classify_renal_function(45) == RenalImpairment.MODERATE
        assert GFRCalculator.classify_renal_function(20) == RenalImpairment.SEVERE
        assert GFRCalculator.classify_renal_function(10) == RenalImpairment.ESRD


class TestDrugClassifier:
    """Test drug classification"""
    
    def test_classify_nsaid(self):
        """Test NSAID classification"""
        classes = DrugClassifier.get_drug_class("Brufen 400mg")
        assert "nsaid" in classes
    
    def test_classify_ace_inhibitor(self):
        """Test ACE inhibitor classification"""
        classes = DrugClassifier.get_drug_class("Lisinopril 10mg")
        assert "ace_inhibitor" in classes
    
    def test_classify_statin(self):
        """Test statin classification"""
        classes = DrugClassifier.get_drug_class("Lipitor Atorvastatin 20mg")
        assert "statin" in classes


class TestDrugDatabase:
    """Test drug database operations"""
    
    @pytest.fixture
    def sample_db(self):
        """Create sample database for testing"""
        db = EgyptianDrugDatabase()
        
        # Add sample medications
        sample_meds = [
            {"Id": 1, "CommercialName": "Brufen 400mg 30/Tab"},
            {"Id": 2, "CommercialName": "Warfarin 5mg 28/Tab"},
            {"Id": 3, "CommercialName": "Aspirin 100mg 30/Tab"},
            {"Id": 4, "CommercialName": "Lisinopril 10mg 28/Tab"},
            {"Id": 5, "CommercialName": "Metformin 500mg 30/Tab"},
            {"Id": 6, "CommercialName": "Ciprofloxacin 500mg 10/Tab"},
            {"Id": 7, "CommercialName": "Amiodarone 200mg 30/Tab"},
        ]
        
        for med_data in sample_meds:
            med = Medication.from_egyptian_db(med_data)
            db._process_medication(med)
        
        db._loaded = True
        return db
    
    def test_search_by_name(self, sample_db):
        """Test medication search"""
        results = sample_db.search("brufen")
        assert len(results) > 0
        assert any("Brufen" in r.commercial_name for r in results)
    
    def test_get_by_id(self, sample_db):
        """Test get medication by ID"""
        med = sample_db.get_by_id(1)
        assert med is not None
        assert "Brufen" in med.commercial_name
    
    def test_parse_dosage_form(self, sample_db):
        """Test dosage form parsing"""
        med = sample_db.get_by_id(1)
        assert med.dosage_form == DosageForm.TABLET


class TestDDIEngine:
    """Test Drug-Drug Interaction detection"""
    
    @pytest.fixture
    def ddi_engine(self):
        return DDIEngine()
    
    @pytest.fixture
    def warfarin(self):
        return Medication(
            id=1,
            commercial_name="Warfarin 5mg 28/Tab",
            generic_name="warfarin"
        )
    
    @pytest.fixture
    def aspirin(self):
        return Medication(
            id=2,
            commercial_name="Aspirin 100mg 30/Tab",
            generic_name="aspirin"
        )
    
    @pytest.fixture
    def ibuprofen(self):
        return Medication(
            id=3,
            commercial_name="Brufen 400mg 30/Tab",
            generic_name="ibuprofen"
        )
    
    def test_warfarin_aspirin_interaction(self, ddi_engine, warfarin, aspirin):
        """Test detection of warfarin-aspirin interaction"""
        interactions = ddi_engine.check_pair(warfarin, aspirin)
        assert len(interactions) > 0
        assert any(i.severity == DDISeverity.MAJOR for i in interactions)
    
    def test_warfarin_nsaid_interaction(self, ddi_engine, warfarin, ibuprofen):
        """Test detection of warfarin-NSAID interaction"""
        interactions = ddi_engine.check_pair(warfarin, ibuprofen)
        assert len(interactions) > 0
        assert any(i.severity == DDISeverity.MAJOR for i in interactions)
    
    def test_no_interaction(self, ddi_engine):
        """Test medications without interactions"""
        med1 = Medication(id=100, commercial_name="Paracetamol 500mg")
        med2 = Medication(id=101, commercial_name="Omeprazole 20mg")
        
        interactions = ddi_engine.check_pair(med1, med2)
        # May or may not have interactions, just ensure no error
        assert isinstance(interactions, list)
    
    def test_prescription_check(self, ddi_engine, warfarin, aspirin, ibuprofen):
        """Test checking multiple medications"""
        meds = [warfarin, aspirin, ibuprofen]
        interactions = ddi_engine.check_prescription(meds)
        
        # Should find multiple interactions
        assert len(interactions) >= 2  # warfarin+aspirin and warfarin+nsaid


class TestDosingEngine:
    """Test dosing adjustment engine"""
    
    @pytest.fixture
    def dosing_engine(self):
        return DosingEngine()
    
    def test_metformin_severe_renal(self, dosing_engine):
        """Test metformin contraindication in severe renal impairment"""
        med = Medication(
            id=1,
            commercial_name="Metformin 500mg 30/Tab",
            generic_name="metformin"
        )
        patient = PatientContext(
            age=70,
            weight_kg=70,
            sex="M",
            serum_creatinine=3.0,  # High - indicates renal impairment
            gfr=20  # Severe
        )
        
        adjustment = dosing_engine.get_renal_adjustment(med, patient)
        assert adjustment is not None
        assert adjustment.contraindicated
    
    def test_ciprofloxacin_moderate_renal(self, dosing_engine):
        """Test ciprofloxacin dose adjustment in moderate renal impairment"""
        med = Medication(
            id=2,
            commercial_name="Ciprofloxacin 500mg 10/Tab",
            generic_name="ciprofloxacin"
        )
        patient = PatientContext(
            gfr=40,  # Moderate impairment
            renal_impairment=RenalImpairment.MODERATE
        )
        
        adjustment = dosing_engine.get_renal_adjustment(med, patient)
        assert adjustment is not None
        assert not adjustment.contraindicated
        assert "q12h" in adjustment.adjusted_dose.lower()


class TestIntegration:
    """Integration tests"""
    
    def test_full_validation_workflow(self):
        """Test complete prescription validation workflow"""
        from src.core.validation_service import MedicationValidationService
        from src.core.drug_database import EgyptianDrugDatabase
        
        # Setup
        db = EgyptianDrugDatabase()
        sample_meds = [
            {"Id": 1, "CommercialName": "Warfarin 5mg 28/Tab"},
            {"Id": 2, "CommercialName": "Aspocid 100mg 30/Tab"},  # Aspirin
            {"Id": 3, "CommercialName": "Metformin 500mg 30/Tab"},
        ]
        for med_data in sample_meds:
            med = Medication.from_egyptian_db(med_data)
            db._process_medication(med)
        db._loaded = True
        
        # Create service
        service = MedicationValidationService(drug_db=db)
        
        # Create prescription
        patient = PatientContext(
            age=65,
            weight_kg=70,
            sex="M",
            gfr=25,  # Severe renal impairment
            conditions=[]
        )
        
        items = [
            PrescriptionItem(medication_id=1, medication_name="Warfarin", dose="5mg", frequency="daily"),
            PrescriptionItem(medication_id=2, medication_name="Aspocid", dose="100mg", frequency="daily"),
            PrescriptionItem(medication_id=3, medication_name="Metformin", dose="500mg", frequency="BID"),
        ]
        
        prescription = Prescription(
            id="test-rx-001",
            patient=patient,
            items=items
        )
        
        # Validate
        result = service.validate_prescription(prescription)
        
        # Assertions
        assert result.medications_validated == 3
        assert len(result.interactions) > 0  # Warfarin + Aspirin
        assert result.has_major_interactions
        assert len(result.warnings) > 0
        assert len(result.recommendations) > 0
        assert result.validation_time_ms > 0


def run_tests():
    """Run all tests"""
    print("=" * 60)
    print("Egyptian AI Medication Validation Engine - Test Suite")
    print("=" * 60)
    
    # Run with pytest
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_tests()
