"""
Egyptian AI Medication Validation Engine
Tests for Sprints 7-10: ML-Enhanced DDI & Clinical Validation
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from src.ml.ensemble_ddi import (
    EnsembleDDIEngine, DDIPredictionModel, 
    DDI_KNOWLEDGE_BASE, get_ensemble_ddi_engine
)
from src.validation.clinical_validation import (
    CLINICAL_TEST_SUITE, ClinicalTestCase,
    PILOT_PHARMACIES, LAUNCH_CHECKLIST,
    get_launch_readiness_status
)


class TestDDIKnowledgeBase:
    """Test DDI knowledge base"""
    
    def test_knowledge_base_not_empty(self):
        """Knowledge base should have entries"""
        assert len(DDI_KNOWLEDGE_BASE) > 20
    
    def test_critical_interactions_present(self):
        """Critical interactions must be in knowledge base"""
        critical_pairs = [
            ("warfarin", "aspirin"),
            ("warfarin", "ibuprofen"),
            ("digoxin", "amiodarone"),
            ("simvastatin", "clarithromycin"),
        ]
        
        for drug1, drug2 in critical_pairs:
            found = (drug1, drug2) in DDI_KNOWLEDGE_BASE or (drug2, drug1) in DDI_KNOWLEDGE_BASE
            assert found, f"Missing critical interaction: {drug1} + {drug2}"
    
    def test_knowledge_base_has_required_fields(self):
        """Each entry should have required fields"""
        for key, knowledge in DDI_KNOWLEDGE_BASE.items():
            assert knowledge.severity in ["major", "moderate", "minor"]
            assert knowledge.mechanism
            assert knowledge.management
            assert 0 <= knowledge.confidence_score <= 1


class TestDDIPredictionModel:
    """Test ML prediction model"""
    
    @pytest.fixture
    def model(self):
        return DDIPredictionModel()
    
    def test_known_drug_embedding(self, model):
        """Known drugs should have embeddings"""
        emb = model.get_drug_embedding("warfarin")
        assert emb is not None
        assert len(emb) == 8
    
    def test_unknown_drug_embedding(self, model):
        """Unknown drugs return None"""
        emb = model.get_drug_embedding("unknowndrug123")
        assert emb is None
    
    def test_high_risk_prediction(self, model):
        """High-risk pairs should have high probability"""
        prob, severity = model.compute_interaction_probability("morphine", "diazepam")
        assert prob > 0.5
        assert severity in ["major", "moderate"]
    
    def test_same_class_detection(self, model):
        """Same drug class should show interaction risk"""
        prob, _ = model.compute_interaction_probability("ibuprofen", "diclofenac")
        assert prob > 0.4  # NSAIDs together


class TestEnsembleDDIEngine:
    """Test ensemble DDI engine"""
    
    @pytest.fixture
    def engine(self):
        return EnsembleDDIEngine()
    
    def test_rule_based_warfarin_aspirin(self, engine):
        """Rule-based detection for warfarin + aspirin"""
        pred = engine.predict_interaction("warfarin", "aspirin")
        
        assert pred.rule_based_match
        assert pred.final_severity == "major"
        assert pred.final_confidence > 0.9
    
    def test_brand_name_normalization(self, engine):
        """Should normalize brand to generic names"""
        pred = engine.predict_interaction("coumadin", "aspirin")  # coumadin = warfarin
        
        assert pred.final_severity == "major"
    
    def test_digoxin_amiodarone(self, engine):
        """Digoxin + Amiodarone interaction"""
        pred = engine.predict_interaction("digoxin", "amiodarone")
        
        assert pred.final_severity == "major"
        assert "digoxin" in pred.mechanism.lower() or "P-glycoprotein" in pred.mechanism
    
    def test_no_interaction(self, engine):
        """Non-interacting drugs should pass"""
        pred = engine.predict_interaction("paracetamol", "omeprazole")
        
        assert pred.final_severity in ["none", "minor"]
    
    def test_prescription_check(self, engine):
        """Check multiple medications"""
        medications = ["warfarin", "aspirin", "omeprazole", "metformin"]
        
        predictions = engine.check_prescription(medications)
        
        # Should find warfarin + aspirin interaction
        major_found = any(
            p.final_severity == "major" and 
            "warfarin" in p.drug1 and "aspirin" in p.drug2
            for p in predictions
        )
        assert major_found
    
    def test_novel_prediction_flagged(self, engine):
        """ML-only predictions should be flagged for review"""
        # Use a combination not in knowledge base but predicted by ML
        pred = engine.predict_interaction("fentanyl", "diazepam")
        
        if not pred.rule_based_match and pred.ml_probability > 0.5:
            assert pred.requires_review or pred.is_novel_prediction


class TestClinicalTestSuite:
    """Test clinical validation test suite"""
    
    def test_test_suite_not_empty(self):
        """Clinical test suite should have cases"""
        assert len(CLINICAL_TEST_SUITE) >= 10
    
    def test_critical_scenarios_present(self):
        """Must have critical priority test cases"""
        critical = [tc for tc in CLINICAL_TEST_SUITE if tc.priority == "critical"]
        assert len(critical) >= 5
    
    def test_categories_covered(self):
        """Multiple clinical categories should be covered"""
        categories = set(tc.category.value for tc in CLINICAL_TEST_SUITE)
        
        required = {"anticoagulation", "cardiac", "renal", "cns", "pregnancy"}
        assert required.issubset(categories)
    
    def test_test_case_structure(self):
        """Each test case should have required fields"""
        for tc in CLINICAL_TEST_SUITE:
            assert tc.id
            assert tc.name
            assert tc.patient_age > 0
            assert tc.patient_sex in ["M", "F"]
            assert len(tc.medications) > 0
            assert tc.expected_status in ["valid", "warning", "blocked"]


class TestPilotConfiguration:
    """Test pilot pharmacy configuration"""
    
    def test_pilot_pharmacies_configured(self):
        """Should have 5 pilot pharmacies"""
        assert len(PILOT_PHARMACIES) == 5
    
    def test_pharmacy_types_diverse(self):
        """Should have different pharmacy types"""
        types = set(p.type for p in PILOT_PHARMACIES)
        assert len(types) >= 2  # At least hospital and community
    
    def test_pharmacies_have_contact_info(self):
        """Each pharmacy should have contact information"""
        for pharmacy in PILOT_PHARMACIES:
            assert pharmacy.contact_name
            assert pharmacy.contact_email


class TestLaunchChecklist:
    """Test launch readiness checklist"""
    
    def test_checklist_not_empty(self):
        """Checklist should have items"""
        assert len(LAUNCH_CHECKLIST) >= 20
    
    def test_categories_covered(self):
        """All categories should be covered"""
        categories = set(item.category for item in LAUNCH_CHECKLIST)
        
        required = {"Technical", "Clinical", "Security", "Integration"}
        assert required.issubset(categories)
    
    def test_readiness_status_calculation(self):
        """Launch readiness status should calculate correctly"""
        status = get_launch_readiness_status()
        
        assert "overall" in status
        assert "by_category" in status
        assert status["overall"]["total_items"] == len(LAUNCH_CHECKLIST)
    
    def test_items_have_owners(self):
        """Each item should have an owner"""
        for item in LAUNCH_CHECKLIST:
            assert item.owner


class TestIntegration:
    """Integration tests for Sprint 7-10 features"""
    
    def test_ensemble_engine_singleton(self):
        """Singleton pattern should work"""
        engine1 = get_ensemble_ddi_engine()
        engine2 = get_ensemble_ddi_engine()
        
        assert engine1 is engine2
    
    def test_full_validation_with_ml(self):
        """Full validation should incorporate ML predictions"""
        engine = get_ensemble_ddi_engine()
        
        # High-risk prescription
        medications = [
            "warfarin", "aspirin", "ibuprofen", "amiodarone"
        ]
        
        predictions = engine.check_prescription(medications)
        
        # Should detect multiple major interactions
        major_count = sum(1 for p in predictions if p.final_severity == "major")
        assert major_count >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
