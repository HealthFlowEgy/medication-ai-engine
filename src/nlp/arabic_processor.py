"""
Egyptian AI Medication Validation Engine - Arabic NLP Module
Sprint 6: Arabic Language Support for Egyptian Healthcare
"""
import re
import logging
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== Arabic-English Drug Mappings ====================

# Common Egyptian medication names in Arabic with English equivalents
ARABIC_DRUG_MAPPINGS = {
    # Analgesics
    "باراسيتامول": "paracetamol",
    "بنادول": "panadol",
    "ابوبروفين": "ibuprofen",
    "بروفين": "brufen",
    "فولتارين": "voltaren",
    "كتافلام": "cataflam",
    "ديكلوفيناك": "diclofenac",
    "اسبرين": "aspirin",
    "اسبوسيد": "aspocid",
    
    # Antibiotics
    "اموكسيسيلين": "amoxicillin",
    "اموكسيل": "amoxil",
    "اوجمنتين": "augmentin",
    "سيبروفلوكساسين": "ciprofloxacin",
    "سيبروباي": "ciprobay",
    "ازيثرومايسين": "azithromycin",
    "زيثروماكس": "zithromax",
    "كلاريثرومايسين": "clarithromycin",
    "كلاسيد": "klacid",
    "فلاجيل": "flagyl",
    "ميترونيدازول": "metronidazole",
    
    # Cardiovascular
    "وارفارين": "warfarin",
    "ديجوكسين": "digoxin",
    "لانوكسين": "lanoxin",
    "اميودارون": "amiodarone",
    "كوردارون": "cordarone",
    "ليزينوبريل": "lisinopril",
    "زيستريل": "zestril",
    "اتينولول": "atenolol",
    "كونكور": "concor",
    "بيسوبرولول": "bisoprolol",
    "كلوبيدوجريل": "clopidogrel",
    "بلافيكس": "plavix",
    
    # Diabetes
    "ميتفورمين": "metformin",
    "جلوكوفاج": "glucophage",
    "جليميبيريد": "glimepiride",
    "اماريل": "amaryl",
    "سيتاجليبتين": "sitagliptin",
    "جانوفيا": "januvia",
    "جانوميت": "janumet",
    "انسولين": "insulin",
    
    # GI
    "اومبيرازول": "omeprazole",
    "نيكسيوم": "nexium",
    "ايزوميبرازول": "esomeprazole",
    "بانتوبرازول": "pantoprazole",
    "كونترولوك": "controloc",
    
    # CNS
    "ترامادول": "tramadol",
    "مورفين": "morphine",
    "ديازيبام": "diazepam",
    "فاليوم": "valium",
    "الزانكس": "xanax",
    "البرازولام": "alprazolam",
    "سيتالوبرام": "citalopram",
    "سيبراليكس": "cipralex",
    "جابابنتين": "gabapentin",
    "نيورونتين": "neurontin",
    
    # Statins
    "اتورفاستاتين": "atorvastatin",
    "ليبيتور": "lipitor",
    "روزوفاستاتين": "rosuvastatin",
    "كريستور": "crestor",
    "سيمفاستاتين": "simvastatin",
    "زوكور": "zocor",
    
    # Others
    "ليفوثيروكسين": "levothyroxine",
    "التروكسين": "eltroxin",
    "بريدنيزولون": "prednisolone",
    "ديكساميثازون": "dexamethasone",
    "سالبوتامول": "salbutamol",
    "فنتولين": "ventolin",
}

# Arabic dosage form terms
ARABIC_DOSAGE_FORMS = {
    "اقراص": "tablets",
    "قرص": "tablet",
    "حبوب": "pills",
    "كبسولات": "capsules",
    "كبسولة": "capsule",
    "شراب": "syrup",
    "محلول": "solution",
    "حقن": "injection",
    "امبول": "ampoule",
    "كريم": "cream",
    "مرهم": "ointment",
    "جل": "gel",
    "قطرة": "drops",
    "بخاخ": "spray",
    "استنشاق": "inhaler",
    "تحاميل": "suppositories",
    "لصقة": "patch",
    "معلق": "suspension",
    "فوار": "effervescent",
    "مسحوق": "powder",
}

# Arabic frequency terms
ARABIC_FREQUENCY_TERMS = {
    "مرة واحدة يوميا": "once daily",
    "مرة يوميا": "once daily",
    "مرتين يوميا": "twice daily",
    "ثلاث مرات يوميا": "three times daily",
    "اربع مرات يوميا": "four times daily",
    "كل ٨ ساعات": "every 8 hours",
    "كل ١٢ ساعة": "every 12 hours",
    "كل ٦ ساعات": "every 6 hours",
    "عند اللزوم": "as needed",
    "قبل النوم": "at bedtime",
    "صباحا": "in the morning",
    "مساء": "in the evening",
    "قبل الاكل": "before meals",
    "بعد الاكل": "after meals",
    "مع الاكل": "with meals",
}

# Arabic route of administration
ARABIC_ROUTES = {
    "بالفم": "oral",
    "فموي": "oral",
    "عن طريق الفم": "oral",
    "حقن عضلي": "intramuscular",
    "حقن وريدي": "intravenous",
    "تحت الجلد": "subcutaneous",
    "موضعي": "topical",
    "استنشاق": "inhalation",
    "شرجي": "rectal",
    "مهبلي": "vaginal",
    "عيني": "ophthalmic",
    "اذني": "otic",
    "انفي": "nasal",
}


# ==================== Arabic Text Utilities ====================

class ArabicTextProcessor:
    """Utilities for processing Arabic medical text"""
    
    # Arabic diacritics (tashkeel) to remove
    ARABIC_DIACRITICS = re.compile(r'[\u064B-\u065F\u0670]')
    
    # Arabic-Indic numerals mapping
    ARABIC_NUMERALS = {
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
    }
    
    @classmethod
    def normalize(cls, text: str) -> str:
        """Normalize Arabic text for matching"""
        if not text:
            return ""
        
        # Remove diacritics
        text = cls.ARABIC_DIACRITICS.sub('', text)
        
        # Normalize alef variations
        text = re.sub(r'[أإآا]', 'ا', text)
        
        # Normalize taa marbuta
        text = text.replace('ة', 'ه')
        
        # Normalize yaa
        text = text.replace('ى', 'ي')
        
        # Convert Arabic-Indic numerals to Western
        for ar, en in cls.ARABIC_NUMERALS.items():
            text = text.replace(ar, en)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    @classmethod
    def extract_numbers(cls, text: str) -> List[float]:
        """Extract numeric values from Arabic text"""
        # First normalize numerals
        normalized = text
        for ar, en in cls.ARABIC_NUMERALS.items():
            normalized = normalized.replace(ar, en)
        
        # Find all numbers (including decimals)
        pattern = r'(\d+(?:\.\d+)?)'
        matches = re.findall(pattern, normalized)
        
        return [float(m) for m in matches]
    
    @classmethod
    def is_arabic(cls, text: str) -> bool:
        """Check if text contains Arabic characters"""
        return bool(re.search(r'[\u0600-\u06FF]', text))
    
    @classmethod
    def transliterate_simple(cls, arabic_text: str) -> str:
        """Simple transliteration for search purposes"""
        # Basic mapping (not linguistically accurate, just for fuzzy matching)
        mapping = {
            'ا': 'a', 'ب': 'b', 'ت': 't', 'ث': 'th', 'ج': 'g',
            'ح': 'h', 'خ': 'kh', 'د': 'd', 'ذ': 'z', 'ر': 'r',
            'ز': 'z', 'س': 's', 'ش': 'sh', 'ص': 's', 'ض': 'd',
            'ط': 't', 'ظ': 'z', 'ع': 'a', 'غ': 'gh', 'ف': 'f',
            'ق': 'q', 'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n',
            'ه': 'h', 'و': 'w', 'ي': 'y', 'ء': '', 'ة': 'a',
        }
        
        result = []
        for char in arabic_text:
            result.append(mapping.get(char, char))
        
        return ''.join(result)


# ==================== Arabic Prescription Parser ====================

@dataclass
class ParsedPrescriptionItem:
    """Parsed prescription item from Arabic text"""
    original_text: str
    medication_name_ar: Optional[str] = None
    medication_name_en: Optional[str] = None
    dose_value: Optional[float] = None
    dose_unit: Optional[str] = None
    dosage_form: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    duration: Optional[str] = None
    confidence: float = 0.0


class ArabicPrescriptionParser:
    """Parse Arabic prescription text into structured data"""
    
    def __init__(self):
        self.text_processor = ArabicTextProcessor()
        
        # Build reverse mappings for lookup
        self._build_lookup_tables()
    
    def _build_lookup_tables(self):
        """Build efficient lookup tables"""
        # Arabic drug name to English
        self.ar_to_en_drug = {
            self.text_processor.normalize(k): v 
            for k, v in ARABIC_DRUG_MAPPINGS.items()
        }
        
        # Normalized dosage forms
        self.ar_to_en_form = {
            self.text_processor.normalize(k): v 
            for k, v in ARABIC_DOSAGE_FORMS.items()
        }
        
        # Normalized frequencies
        self.ar_to_en_freq = {
            self.text_processor.normalize(k): v 
            for k, v in ARABIC_FREQUENCY_TERMS.items()
        }
        
        # Normalized routes
        self.ar_to_en_route = {
            self.text_processor.normalize(k): v 
            for k, v in ARABIC_ROUTES.items()
        }
    
    def parse_line(self, text: str) -> ParsedPrescriptionItem:
        """Parse a single prescription line"""
        result = ParsedPrescriptionItem(original_text=text)
        normalized = self.text_processor.normalize(text)
        confidence_factors = []
        
        # Extract medication name
        drug_name = self._extract_drug_name(normalized)
        if drug_name:
            result.medication_name_ar = drug_name[0]
            result.medication_name_en = drug_name[1]
            confidence_factors.append(0.4)
        
        # Extract dose
        dose = self._extract_dose(text)
        if dose:
            result.dose_value = dose[0]
            result.dose_unit = dose[1]
            confidence_factors.append(0.2)
        
        # Extract dosage form
        form = self._extract_dosage_form(normalized)
        if form:
            result.dosage_form = form
            confidence_factors.append(0.15)
        
        # Extract frequency
        freq = self._extract_frequency(normalized)
        if freq:
            result.frequency = freq
            confidence_factors.append(0.15)
        
        # Extract route
        route = self._extract_route(normalized)
        if route:
            result.route = route
            confidence_factors.append(0.1)
        
        result.confidence = sum(confidence_factors)
        return result
    
    def _extract_drug_name(self, normalized_text: str) -> Optional[Tuple[str, str]]:
        """Extract drug name from normalized text"""
        # Check for known Arabic drug names
        for ar_name, en_name in self.ar_to_en_drug.items():
            if ar_name in normalized_text:
                return (ar_name, en_name)
        
        return None
    
    def _extract_dose(self, text: str) -> Optional[Tuple[float, str]]:
        """Extract dose value and unit"""
        # Common patterns: "500 مجم", "500mg", "٥٠٠ مجم"
        patterns = [
            r'(\d+(?:\.\d+)?)\s*(مجم|ملجم|جم|مج|mg|g|mcg|ml)',
            r'([٠-٩]+(?:\.[٠-٩]+)?)\s*(مجم|ملجم|جم|مج)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value_str = match.group(1)
                unit = match.group(2)
                
                # Convert Arabic numerals
                for ar, en in ArabicTextProcessor.ARABIC_NUMERALS.items():
                    value_str = value_str.replace(ar, en)
                
                # Normalize unit
                unit_mapping = {
                    'مجم': 'mg', 'ملجم': 'mg', 'مج': 'mg',
                    'جم': 'g', 'مل': 'ml'
                }
                unit = unit_mapping.get(unit, unit.lower())
                
                return (float(value_str), unit)
        
        return None
    
    def _extract_dosage_form(self, normalized_text: str) -> Optional[str]:
        """Extract dosage form"""
        for ar_form, en_form in self.ar_to_en_form.items():
            if ar_form in normalized_text:
                return en_form
        return None
    
    def _extract_frequency(self, normalized_text: str) -> Optional[str]:
        """Extract frequency/timing"""
        for ar_freq, en_freq in self.ar_to_en_freq.items():
            if ar_freq in normalized_text:
                return en_freq
        
        # Check for numeric patterns
        numeric_patterns = [
            (r'(\d+)\s*مرات?\s*يوميا', lambda m: f"{m.group(1)} times daily"),
            (r'كل\s*(\d+)\s*ساع', lambda m: f"every {m.group(1)} hours"),
        ]
        
        for pattern, formatter in numeric_patterns:
            match = re.search(pattern, normalized_text)
            if match:
                return formatter(match)
        
        return None
    
    def _extract_route(self, normalized_text: str) -> Optional[str]:
        """Extract route of administration"""
        for ar_route, en_route in self.ar_to_en_route.items():
            if ar_route in normalized_text:
                return en_route
        return None
    
    def parse_prescription(self, text: str) -> List[ParsedPrescriptionItem]:
        """Parse a full prescription with multiple items"""
        # Split by common delimiters (newlines, numbers at start)
        lines = re.split(r'\n|(?=\d+[\.\-\)]\s)', text)
        lines = [l.strip() for l in lines if l.strip()]
        
        results = []
        for line in lines:
            if len(line) > 3:  # Skip very short lines
                parsed = self.parse_line(line)
                if parsed.medication_name_en or parsed.confidence > 0.2:
                    results.append(parsed)
        
        return results


# ==================== Arabic Search Enhancer ====================

class ArabicSearchEnhancer:
    """Enhance drug search with Arabic language support"""
    
    def __init__(self):
        self.text_processor = ArabicTextProcessor()
        self.parser = ArabicPrescriptionParser()
        
        # Build search index
        self._build_search_index()
    
    def _build_search_index(self):
        """Build search index with normalized terms"""
        self.search_index = {}
        
        for ar_name, en_name in ARABIC_DRUG_MAPPINGS.items():
            normalized = self.text_processor.normalize(ar_name)
            self.search_index[normalized] = {
                "arabic": ar_name,
                "english": en_name,
                "transliterated": self.text_processor.transliterate_simple(ar_name)
            }
    
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Search for medications supporting Arabic and English"""
        results = []
        
        if self.text_processor.is_arabic(query):
            # Arabic query
            normalized_query = self.text_processor.normalize(query)
            
            for normalized_name, info in self.search_index.items():
                if normalized_query in normalized_name or normalized_name in normalized_query:
                    results.append({
                        "arabic_name": info["arabic"],
                        "english_name": info["english"],
                        "match_type": "arabic",
                        "score": 1.0 if normalized_query == normalized_name else 0.8
                    })
        else:
            # English query - search in English names and transliterations
            query_lower = query.lower()
            
            for normalized_name, info in self.search_index.items():
                if (query_lower in info["english"].lower() or 
                    query_lower in info["transliterated"]):
                    results.append({
                        "arabic_name": info["arabic"],
                        "english_name": info["english"],
                        "match_type": "english",
                        "score": 1.0 if query_lower == info["english"].lower() else 0.7
                    })
        
        # Sort by score and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
    
    def translate_drug_name(self, name: str) -> Optional[str]:
        """Translate drug name between Arabic and English"""
        if self.text_processor.is_arabic(name):
            # Arabic to English
            normalized = self.text_processor.normalize(name)
            for ar_norm, info in self.search_index.items():
                if ar_norm == normalized or ar_norm in normalized:
                    return info["english"]
        else:
            # English to Arabic
            name_lower = name.lower()
            for ar_norm, info in self.search_index.items():
                if info["english"].lower() == name_lower:
                    return info["arabic"]
        
        return None


# ==================== Integration with Drug Database ====================

def enhance_drug_database_with_arabic(drug_db):
    """Add Arabic search capability to drug database"""
    enhancer = ArabicSearchEnhancer()
    parser = ArabicPrescriptionParser()
    
    # Patch the search method
    original_search = drug_db.search
    
    def enhanced_search(query: str, limit: int = 20):
        # Check if query is Arabic
        if ArabicTextProcessor.is_arabic(query):
            # First try to translate to English
            english_name = enhancer.translate_drug_name(query)
            if english_name:
                return original_search(english_name, limit)
        
        # Fall back to original search
        return original_search(query, limit)
    
    drug_db.search = enhanced_search
    drug_db.arabic_enhancer = enhancer
    drug_db.arabic_parser = parser
    
    return drug_db


# Singleton instances
_arabic_parser: Optional[ArabicPrescriptionParser] = None
_arabic_search: Optional[ArabicSearchEnhancer] = None


def get_arabic_parser() -> ArabicPrescriptionParser:
    global _arabic_parser
    if _arabic_parser is None:
        _arabic_parser = ArabicPrescriptionParser()
    return _arabic_parser


def get_arabic_search() -> ArabicSearchEnhancer:
    global _arabic_search
    if _arabic_search is None:
        _arabic_search = ArabicSearchEnhancer()
    return _arabic_search


# Module-level convenience functions and aliases
def is_arabic(text: str) -> bool:
    """Check if text contains Arabic characters"""
    return ArabicTextProcessor.is_arabic(text)


def translate_drug_name(name: str) -> Optional[str]:
    """Translate drug name between Arabic and English"""
    search = get_arabic_search()
    return search.translate_drug_name(name)


# Aliases for backward compatibility
ArabicDrugMatcher = ArabicSearchEnhancer
ArabicDrugDatabase = ArabicSearchEnhancer
