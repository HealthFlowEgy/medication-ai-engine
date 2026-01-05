"""
Egyptian AI Medication Validation Engine - Arabic NLP Tests
Sprint 6: Arabic Language Support Tests
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from src.nlp.arabic_processor import (
    ArabicTextProcessor, ArabicPrescriptionParser,
    ArabicSearchEnhancer, ARABIC_DRUG_MAPPINGS
)


class TestArabicTextProcessor:
    """Test Arabic text processing utilities"""
    
    def test_normalize_removes_diacritics(self):
        """Test diacritic removal"""
        processor = ArabicTextProcessor()
        text_with_diacritics = "بَارَاسِيتَامُول"
        normalized = processor.normalize(text_with_diacritics)
        assert "َ" not in normalized
    
    def test_normalize_alef_variations(self):
        """Test alef normalization"""
        processor = ArabicTextProcessor()
        assert processor.normalize("أموكسيسيلين") == processor.normalize("اموكسيسيلين")
        assert processor.normalize("إنسولين") == processor.normalize("انسولين")
    
    def test_is_arabic_detection(self):
        """Test Arabic text detection"""
        assert ArabicTextProcessor.is_arabic("باراسيتامول")
        assert ArabicTextProcessor.is_arabic("Paracetamol باراسيتامول")
        assert not ArabicTextProcessor.is_arabic("Paracetamol")
        assert not ArabicTextProcessor.is_arabic("500mg")
    
    def test_extract_numbers_western(self):
        """Test number extraction from Western numerals"""
        numbers = ArabicTextProcessor.extract_numbers("500mg tablet")
        assert 500 in numbers
    
    def test_extract_numbers_arabic_indic(self):
        """Test number extraction from Arabic-Indic numerals"""
        numbers = ArabicTextProcessor.extract_numbers("٥٠٠ مجم")
        assert 500 in numbers
    
    def test_transliteration(self):
        """Test simple transliteration"""
        result = ArabicTextProcessor.transliterate_simple("باراسيتامول")
        assert "b" in result
        assert "a" in result


class TestArabicPrescriptionParser:
    """Test Arabic prescription parsing"""
    
    @pytest.fixture
    def parser(self):
        return ArabicPrescriptionParser()
    
    def test_parse_simple_prescription(self, parser):
        """Test parsing simple Arabic prescription"""
        text = "باراسيتامول ٥٠٠ مجم اقراص مرتين يوميا"
        result = parser.parse_line(text)
        
        assert result.medication_name_en == "paracetamol"
        assert result.dose_value == 500
        assert result.dose_unit == "mg"
        assert result.dosage_form == "tablets"
        assert result.frequency == "twice daily"
    
    def test_parse_brufen_prescription(self, parser):
        """Test parsing Brufen prescription"""
        text = "بروفين 400 مجم قرص ثلاث مرات يوميا بعد الاكل"
        result = parser.parse_line(text)
        
        assert result.medication_name_en == "brufen"
        assert result.dose_value == 400
        assert "daily" in result.frequency
    
    def test_parse_augmentin(self, parser):
        """Test parsing Augmentin"""
        text = "اوجمنتين 1 جم اقراص مرتين يوميا لمدة اسبوع"
        result = parser.parse_line(text)
        
        assert result.medication_name_en == "augmentin"
    
    def test_parse_with_route(self, parser):
        """Test parsing prescription with route"""
        text = "انسولين 10 وحدات تحت الجلد قبل الاكل"
        result = parser.parse_line(text)
        
        assert result.medication_name_en == "insulin"
        assert result.route == "subcutaneous"
    
    def test_parse_multi_line_prescription(self, parser):
        """Test parsing multiple prescription items"""
        text = """1. باراسيتامول 500 مجم مرتين يوميا
        2. اوجمنتين 1 جم مرتين يوميا
        3. نيكسيوم 40 مجم قبل الاكل"""
        
        results = parser.parse_prescription(text)
        
        assert len(results) >= 2
        medications = [r.medication_name_en for r in results]
        assert "paracetamol" in medications
    
    def test_confidence_scoring(self, parser):
        """Test confidence scoring"""
        # Complete prescription should have high confidence
        complete = "باراسيتامول 500 مجم اقراص مرتين يوميا بالفم"
        result1 = parser.parse_line(complete)
        
        # Incomplete should have lower confidence
        incomplete = "دواء غير معروف"
        result2 = parser.parse_line(incomplete)
        
        assert result1.confidence > result2.confidence


class TestArabicSearchEnhancer:
    """Test Arabic search functionality"""
    
    @pytest.fixture
    def search(self):
        return ArabicSearchEnhancer()
    
    def test_search_arabic_drug_name(self, search):
        """Test searching with Arabic drug name"""
        results = search.search("باراسيتامول")
        
        assert len(results) > 0
        assert results[0]["english_name"] == "paracetamol"
    
    def test_search_partial_arabic(self, search):
        """Test partial Arabic name search"""
        results = search.search("بارا")
        
        # Should find paracetamol
        english_names = [r["english_name"] for r in results]
        assert any("paracetamol" in name for name in english_names)
    
    def test_search_english_returns_arabic(self, search):
        """Test English search returns Arabic name"""
        results = search.search("paracetamol")
        
        assert len(results) > 0
        assert results[0]["arabic_name"] == "باراسيتامول"
    
    def test_translate_arabic_to_english(self, search):
        """Test translation Arabic to English"""
        english = search.translate_drug_name("وارفارين")
        assert english == "warfarin"
    
    def test_translate_english_to_arabic(self, search):
        """Test translation English to Arabic"""
        arabic = search.translate_drug_name("warfarin")
        assert arabic == "وارفارين"
    
    def test_search_brand_name_arabic(self, search):
        """Test searching Arabic brand names"""
        results = search.search("فولتارين")
        
        assert len(results) > 0
        assert results[0]["english_name"] == "voltaren"


class TestArabicDrugMappings:
    """Test the drug mapping dictionary"""
    
    def test_common_drugs_mapped(self):
        """Test common drugs are in mapping"""
        common_drugs = [
            "باراسيتامول", "اموكسيسيلين", "وارفارين",
            "ميتفورمين", "اتورفاستاتين"
        ]
        
        for drug in common_drugs:
            normalized = ArabicTextProcessor.normalize(drug)
            found = any(
                normalized in ArabicTextProcessor.normalize(k) 
                for k in ARABIC_DRUG_MAPPINGS.keys()
            )
            assert found, f"Drug {drug} not found in mappings"
    
    def test_mapping_coverage(self):
        """Test sufficient mapping coverage"""
        # Should have at least 50 drug mappings
        assert len(ARABIC_DRUG_MAPPINGS) >= 50


class TestIntegrationScenarios:
    """Integration tests for Arabic NLP"""
    
    def test_real_prescription_scenario(self):
        """Test real-world prescription scenario"""
        parser = ArabicPrescriptionParser()
        
        # Typical Egyptian prescription
        prescription = """
        الاسم: محمد احمد
        التاريخ: 2026/01/05
        
        1- باراسيتامول 500 مجم قرص كل 6 ساعات عند الحاجة
        2- اوجمنتين 1 جم قرص مرتين يوميا لمدة 7 ايام
        3- موتيليوم 10 مجم قرص 3 مرات يوميا قبل الاكل
        """
        
        results = parser.parse_prescription(prescription)
        
        # Should extract at least 2 medications
        assert len(results) >= 2
        
        # Check first medication
        paracetamol = next(
            (r for r in results if r.medication_name_en == "paracetamol"), 
            None
        )
        assert paracetamol is not None
        assert paracetamol.dose_value == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
