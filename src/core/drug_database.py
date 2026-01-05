"""
Egyptian AI Medication Validation Engine - Drug Database Processor
Sprint 1: Core Drug Database Processing
"""
import pandas as pd
import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import asdict
from collections import defaultdict

from src.core.models import Medication, DosageForm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EgyptianDrugDatabase:
    """Process and manage Egyptian medication database from EDA"""
    
    # Common Egyptian brand-to-generic mappings
    BRAND_TO_GENERIC = {
        "panadol": "paracetamol",
        "cataflam": "diclofenac",
        "augmentin": "amoxicillin/clavulanate",
        "flagyl": "metronidazole",
        "voltaren": "diclofenac",
        "aspocid": "aspirin",
        "brufen": "ibuprofen",
        "amoxil": "amoxicillin",
        "zithromax": "azithromycin",
        "glucophage": "metformin",
        "lasix": "furosemide",
        "lipitor": "atorvastatin",
        "nexium": "esomeprazole",
        "januvia": "sitagliptin",
        "janumet": "sitagliptin/metformin",
        "concor": "bisoprolol",
        "plavix": "clopidogrel",
        "coversyl": "perindopril",
        "adalat": "nifedipine",
        "lanoxin": "digoxin",
        "synthroid": "levothyroxine",
        "eltroxin": "levothyroxine",
        "ventolin": "salbutamol",
        "seretide": "fluticasone/salmeterol",
        "symbicort": "budesonide/formoterol",
        "klacid": "clarithromycin",
        "ciprobay": "ciprofloxacin",
        "tavanic": "levofloxacin",
        "zocor": "simvastatin",
        "crestor": "rosuvastatin",
        "cordarone": "amiodarone",
        "zestril": "lisinopril",
        "tritace": "ramipril",
        "aldactone": "spironolactone",
        "cipralex": "escitalopram",
        "prozac": "fluoxetine",
        "xanax": "alprazolam",
        "tegretol": "carbamazepine",
        "neurontin": "gabapentin",
        "amaryl": "glimepiride",
        "daonil": "glyburide",
        "diflucan": "fluconazole",
        "sporanox": "itraconazole",
        "motilium": "domperidone",
    }
    
    # High-alert medications requiring special attention
    HIGH_ALERT_DRUGS = {
        "warfarin", "heparin", "insulin", "digoxin", "methotrexate",
        "chemotherapy", "opioid", "morphine", "fentanyl", "potassium",
        "magnesium sulfate", "epinephrine", "norepinephrine", "dopamine",
        "amiodarone", "lidocaine", "propofol", "ketamine", "rocuronium"
    }
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self.medications: Dict[int, Medication] = {}
        self.name_index: Dict[str, List[int]] = defaultdict(list)
        self.generic_index: Dict[str, List[int]] = defaultdict(list)
        self.ingredient_index: Dict[str, List[int]] = defaultdict(list)
        self._loaded = False
    
    def load_from_json(self, filepath: str) -> int:
        """Load medications from processed JSON file"""
        logger.info(f"Loading medications from JSON: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        count = 0
        for med_data in data.get('medications', []):
            try:
                # Convert dosage_form string to enum
                dosage_form_str = med_data.get('dosage_form', 'other')
                try:
                    dosage_form = DosageForm(dosage_form_str)
                except ValueError:
                    dosage_form = DosageForm.OTHER
                
                med = Medication(
                    id=med_data['id'],
                    commercial_name=med_data['commercial_name'],
                    generic_name=med_data.get('generic_name'),
                    arabic_name=med_data.get('arabic_name'),
                    active_ingredients=med_data.get('active_ingredients', []),
                    strength=med_data.get('strength'),
                    strength_value=med_data.get('strength_value'),
                    strength_unit=med_data.get('strength_unit'),
                    dosage_form=dosage_form,
                    package_size=med_data.get('package_size'),
                    manufacturer=med_data.get('manufacturer'),
                    atc_code=med_data.get('atc_code'),
                    eda_registration=med_data.get('eda_registration'),
                    rxnorm_id=med_data.get('rxnorm_id'),
                    drugbank_id=med_data.get('drugbank_id'),
                    is_otc=med_data.get('is_otc', False),
                    is_controlled=med_data.get('is_controlled', False),
                )
                self._process_medication(med)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to parse medication: {med_data.get('commercial_name', 'Unknown')} - {e}")
        
        self._loaded = True
        logger.info(f"Loaded {count} medications from JSON")
        return count
    
    def load_from_excel(self, filepath: str) -> int:
        """Load medications from Egyptian database Excel file"""
        logger.info(f"Loading medications from {filepath}")
        
        df = pd.read_excel(filepath)
        count = 0
        
        for _, row in df.iterrows():
            try:
                med = Medication.from_egyptian_db(row.to_dict())
                self._process_medication(med)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to parse medication: {row.get('CommercialName', 'Unknown')} - {e}")
        
        self._loaded = True
        logger.info(f"Loaded {count} medications")
        return count
    
    def _process_medication(self, med: Medication) -> None:
        """Process and index a medication"""
        # Store medication
        self.medications[med.id] = med
        
        # Index by commercial name (normalized)
        name_key = self._normalize_name(med.commercial_name)
        self.name_index[name_key].append(med.id)
        
        # Extract and index potential generic name
        generic = self._extract_generic_name(med.commercial_name)
        if generic:
            med.generic_name = generic
            self.generic_index[generic.lower()].append(med.id)
        
        # Extract and index active ingredients
        ingredients = self._extract_ingredients(med.commercial_name)
        med.active_ingredients = ingredients
        for ing in ingredients:
            self.ingredient_index[ing.lower()].append(med.id)
    
    def _normalize_name(self, name: str) -> str:
        """Normalize medication name for searching"""
        # Remove special characters, lowercase
        normalized = re.sub(r'[^\w\s]', '', name.lower())
        # Remove common suffixes
        normalized = re.sub(r'\b(mg|gm|ml|tab|cap|syrup|amp|cream|gel|oint)\b', '', normalized)
        # Remove numbers
        normalized = re.sub(r'\d+', '', normalized)
        return ' '.join(normalized.split())
    
    def _extract_generic_name(self, commercial_name: str) -> Optional[str]:
        """Extract generic name from commercial name"""
        name_lower = commercial_name.lower()
        
        # Check known brand-to-generic mappings
        for brand, generic in self.BRAND_TO_GENERIC.items():
            if brand in name_lower:
                return generic
        
        # Check if name contains generic in parentheses (e.g., "Advil (Ibuprofen)")
        paren_match = re.search(r'\(([^)]+)\)', commercial_name)
        if paren_match:
            potential_generic = paren_match.group(1).strip()
            if not potential_generic.isdigit():
                return potential_generic.lower()
        
        return None
    
    def _extract_ingredients(self, commercial_name: str) -> List[str]:
        """Extract active ingredients from commercial name"""
        ingredients = []
        
        # Check for combination products (e.g., "50/1000mg")
        combo_pattern = r'(\d+)\s*/\s*(\d+)\s*mg'
        if re.search(combo_pattern, commercial_name):
            # This is likely a combination product
            pass
        
        # Check known brand mappings
        name_lower = commercial_name.lower()
        for brand, generic in self.BRAND_TO_GENERIC.items():
            if brand in name_lower:
                if '/' in generic:
                    ingredients.extend(generic.split('/'))
                else:
                    ingredients.append(generic)
        
        return ingredients
    
    def search(self, query: str, limit: int = 20) -> List[Medication]:
        """Search medications by name, generic, or ingredient"""
        query_lower = query.lower().strip()
        results = []
        seen_ids = set()
        
        # Exact name match first
        for med in self.medications.values():
            if query_lower in med.commercial_name.lower():
                if med.id not in seen_ids:
                    results.append(med)
                    seen_ids.add(med.id)
        
        # Generic name match
        for generic, ids in self.generic_index.items():
            if query_lower in generic:
                for med_id in ids:
                    if med_id not in seen_ids:
                        results.append(self.medications[med_id])
                        seen_ids.add(med_id)
        
        # Ingredient match
        for ingredient, ids in self.ingredient_index.items():
            if query_lower in ingredient:
                for med_id in ids:
                    if med_id not in seen_ids:
                        results.append(self.medications[med_id])
                        seen_ids.add(med_id)
        
        return results[:limit]
    
    def get_by_id(self, med_id: int) -> Optional[Medication]:
        """Get medication by ID"""
        return self.medications.get(med_id)
    
    def get_by_ids(self, med_ids: List[int]) -> List[Medication]:
        """Get multiple medications by IDs"""
        return [self.medications[mid] for mid in med_ids if mid in self.medications]
    
    def is_high_alert(self, med_id: int) -> bool:
        """Check if medication is high-alert"""
        med = self.medications.get(med_id)
        if not med:
            return False
        
        name_lower = med.commercial_name.lower()
        for drug in self.HIGH_ALERT_DRUGS:
            if drug in name_lower:
                return True
        
        if med.generic_name:
            for drug in self.HIGH_ALERT_DRUGS:
                if drug in med.generic_name.lower():
                    return True
        
        return False
    
    def get_similar_medications(self, med_id: int) -> List[Medication]:
        """Find similar medications (same generic, different brand)"""
        med = self.medications.get(med_id)
        if not med or not med.generic_name:
            return []
        
        similar_ids = self.generic_index.get(med.generic_name.lower(), [])
        return [self.medications[mid] for mid in similar_ids if mid != med_id]
    
    def export_processed(self, output_path: str) -> None:
        """Export processed database to JSON"""
        data = {
            "medications": [asdict(med) for med in self.medications.values()],
            "stats": {
                "total": len(self.medications),
                "with_generic": sum(1 for m in self.medications.values() if m.generic_name),
                "high_alert": sum(1 for mid in self.medications if self.is_high_alert(mid)),
            }
        }
        
        # Convert datetime objects to strings
        for med in data["medications"]:
            med["created_at"] = med["created_at"].isoformat()
            med["updated_at"] = med["updated_at"].isoformat()
            med["dosage_form"] = med["dosage_form"].value if hasattr(med["dosage_form"], 'value') else str(med["dosage_form"])
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Exported {len(self.medications)} medications to {output_path}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        form_counts = defaultdict(int)
        for med in self.medications.values():
            form_counts[med.dosage_form.value] += 1
        
        return {
            "total_medications": len(self.medications),
            "unique_generics": len(self.generic_index),
            "unique_ingredients": len(self.ingredient_index),
            "high_alert_count": sum(1 for mid in self.medications if self.is_high_alert(mid)),
            "dosage_form_distribution": dict(form_counts),
            "with_generic_mapping": sum(1 for m in self.medications.values() if m.generic_name),
        }


# Singleton instance
_drug_db: Optional[EgyptianDrugDatabase] = None

def get_drug_database() -> EgyptianDrugDatabase:
    """Get or create drug database singleton"""
    global _drug_db
    if _drug_db is None:
        _drug_db = EgyptianDrugDatabase()
    return _drug_db


def init_drug_database(excel_path: str) -> EgyptianDrugDatabase:
    """Initialize drug database from Excel file"""
    global _drug_db
    _drug_db = EgyptianDrugDatabase()
    _drug_db.load_from_excel(excel_path)
    return _drug_db
