"""
Egyptian AI Medication Validation Engine - DDI Engine
Sprint 1-2: Drug-Drug Interaction Detection
"""
import logging
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict
import json
from pathlib import Path

from src.core.models import DrugInteraction, DDISeverity, Medication

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Known high-risk drug interactions (subset for MVP)
# Format: (drug1, drug2, severity, mechanism, management)
CRITICAL_DDI_RULES = [
    # Anticoagulant interactions
    ("warfarin", "aspirin", DDISeverity.MAJOR, 
     "Increased bleeding risk due to combined antiplatelet and anticoagulant effects",
     "Avoid combination or monitor INR closely. Consider PPI for GI protection."),
    ("warfarin", "nsaid", DDISeverity.MAJOR,
     "NSAIDs inhibit platelet function and may cause GI bleeding",
     "Avoid NSAIDs if possible. If necessary, use lowest dose for shortest duration."),
    ("warfarin", "metronidazole", DDISeverity.MODERATE,
     "Metronidazole inhibits warfarin metabolism (CYP2C9)",
     "Monitor INR closely. May need warfarin dose reduction."),
    ("warfarin", "fluconazole", DDISeverity.MAJOR,
     "Fluconazole inhibits CYP2C9 and CYP3A4, increasing warfarin effect",
     "Reduce warfarin dose by 25-50%. Monitor INR frequently."),
    ("warfarin", "amiodarone", DDISeverity.MAJOR,
     "Amiodarone inhibits warfarin metabolism",
     "Reduce warfarin dose by 30-50%. Monitor INR weekly for 6 weeks."),
    
    # ACE inhibitor + Potassium
    ("ace_inhibitor", "potassium", DDISeverity.MAJOR,
     "Risk of severe hyperkalemia",
     "Monitor serum potassium closely. Avoid potassium supplements unless hypokalemic."),
    ("ace_inhibitor", "spironolactone", DDISeverity.MODERATE,
     "Additive hyperkalemia risk",
     "Monitor potassium, especially in renal impairment."),
    
    # QT prolongation combinations
    ("amiodarone", "fluoroquinolone", DDISeverity.MAJOR,
     "Additive QT prolongation risk - risk of torsades de pointes",
     "Avoid combination. If unavoidable, monitor QTc and electrolytes."),
    ("clarithromycin", "domperidone", DDISeverity.MAJOR,
     "QT prolongation risk",
     "Avoid combination. Use alternative antiemetic."),
    ("erythromycin", "cisapride", DDISeverity.MAJOR,
     "Severe QT prolongation - fatal arrhythmias reported",
     "Contraindicated combination."),
    
    # Serotonin syndrome
    ("ssri", "tramadol", DDISeverity.MAJOR,
     "Serotonin syndrome risk due to combined serotonergic activity",
     "Avoid combination or monitor for serotonin syndrome symptoms."),
    ("ssri", "maoi", DDISeverity.MAJOR,
     "Life-threatening serotonin syndrome",
     "Contraindicated. Require 2-week washout between medications."),
    ("ssri", "linezolid", DDISeverity.MAJOR,
     "Linezolid has MAO inhibitor activity - serotonin syndrome risk",
     "Avoid if possible. If necessary, monitor closely for 2 weeks."),
    
    # Metformin + Contrast
    ("metformin", "iodinated_contrast", DDISeverity.MAJOR,
     "Risk of lactic acidosis",
     "Hold metformin 48h before and after contrast. Resume after renal function confirmed stable."),
    
    # Digoxin interactions
    ("digoxin", "amiodarone", DDISeverity.MAJOR,
     "Amiodarone increases digoxin levels by 70-100%",
     "Reduce digoxin dose by 50%. Monitor levels."),
    ("digoxin", "verapamil", DDISeverity.MAJOR,
     "Verapamil increases digoxin levels and has additive AV node effects",
     "Reduce digoxin dose. Monitor for bradycardia."),
    ("digoxin", "clarithromycin", DDISeverity.MODERATE,
     "Macrolides increase digoxin levels via P-glycoprotein inhibition",
     "Monitor digoxin levels and for toxicity signs."),
    
    # Statins
    ("simvastatin", "clarithromycin", DDISeverity.MAJOR,
     "Risk of rhabdomyolysis due to CYP3A4 inhibition",
     "Use alternative statin (pravastatin, rosuvastatin) or antibiotic."),
    ("simvastatin", "itraconazole", DDISeverity.MAJOR,
     "Severe myopathy risk",
     "Contraindicated combination."),
    ("atorvastatin", "clarithromycin", DDISeverity.MODERATE,
     "Increased statin exposure",
     "Limit atorvastatin to 20mg daily. Monitor for myopathy."),
    
    # Theophylline
    ("theophylline", "ciprofloxacin", DDISeverity.MAJOR,
     "Ciprofloxacin inhibits theophylline metabolism",
     "Reduce theophylline dose by 30-50%. Monitor levels."),
    ("theophylline", "erythromycin", DDISeverity.MODERATE,
     "Macrolides increase theophylline levels",
     "Monitor theophylline levels."),
    
    # Lithium
    ("lithium", "nsaid", DDISeverity.MAJOR,
     "NSAIDs reduce lithium clearance, causing toxicity",
     "Avoid if possible. If necessary, monitor lithium levels closely."),
    ("lithium", "ace_inhibitor", DDISeverity.MAJOR,
     "ACE inhibitors reduce lithium clearance",
     "Monitor lithium levels. May need dose reduction."),
    ("lithium", "diuretic", DDISeverity.MODERATE,
     "Thiazides and loop diuretics can increase lithium levels",
     "Monitor lithium levels, especially when initiating diuretic."),
    
    # Methotrexate
    ("methotrexate", "nsaid", DDISeverity.MAJOR,
     "NSAIDs reduce methotrexate clearance, increasing toxicity",
     "Avoid combination with high-dose MTX. Monitor with low-dose."),
    ("methotrexate", "trimethoprim", DDISeverity.MAJOR,
     "Additive antifolate effects and reduced MTX clearance",
     "Avoid combination if possible. Monitor blood counts."),
    
    # Opioids
    ("opioid", "benzodiazepine", DDISeverity.MAJOR,
     "Additive CNS and respiratory depression",
     "Avoid combination if possible. Use lowest effective doses. Monitor closely."),
    ("opioid", "maoi", DDISeverity.MAJOR,
     "Risk of serotonin syndrome and respiratory depression",
     "Avoid meperidine. Use other opioids with extreme caution."),
    
    # Antidiabetics
    ("sulfonylurea", "fluconazole", DDISeverity.MODERATE,
     "Fluconazole inhibits sulfonylurea metabolism - hypoglycemia risk",
     "Monitor blood glucose closely. May need sulfonylurea dose reduction."),
]


class DrugClassifier:
    """Map drug names to therapeutic classes for DDI checking"""
    
    DRUG_CLASSES = {
        "ace_inhibitor": [
            "lisinopril", "enalapril", "ramipril", "captopril", "perindopril",
            "quinapril", "benazepril", "fosinopril", "moexipril", "trandolapril"
        ],
        "arb": [
            "losartan", "valsartan", "irbesartan", "candesartan", "olmesartan",
            "telmisartan", "eprosartan", "azilsartan"
        ],
        "nsaid": [
            "ibuprofen", "diclofenac", "naproxen", "indomethacin", "piroxicam",
            "meloxicam", "celecoxib", "ketoprofen", "aspirin", "ketorolac",
            "brufen", "cataflam", "voltaren"
        ],
        "ssri": [
            "fluoxetine", "sertraline", "paroxetine", "citalopram", "escitalopram",
            "fluvoxamine"
        ],
        "opioid": [
            "morphine", "codeine", "tramadol", "fentanyl", "oxycodone",
            "hydrocodone", "hydromorphone", "meperidine", "methadone"
        ],
        "benzodiazepine": [
            "diazepam", "lorazepam", "alprazolam", "clonazepam", "midazolam",
            "temazepam", "oxazepam", "chlordiazepoxide"
        ],
        "statin": [
            "simvastatin", "atorvastatin", "rosuvastatin", "pravastatin",
            "lovastatin", "fluvastatin", "pitavastatin"
        ],
        "fluoroquinolone": [
            "ciprofloxacin", "levofloxacin", "moxifloxacin", "ofloxacin",
            "norfloxacin", "gatifloxacin"
        ],
        "maoi": [
            "phenelzine", "tranylcypromine", "isocarboxazid", "selegiline",
            "rasagiline"
        ],
        "sulfonylurea": [
            "glipizide", "glyburide", "glimepiride", "glibenclamide", "gliclazide"
        ],
        "potassium": [
            "potassium chloride", "potassium citrate", "potassium", "k-dur",
            "slow-k", "kay ciel"
        ],
        "diuretic": [
            "furosemide", "hydrochlorothiazide", "chlorthalidone", "bumetanide",
            "torsemide", "metolazone", "lasix"
        ],
    }
    
    @classmethod
    def get_drug_class(cls, drug_name: str) -> List[str]:
        """Get therapeutic classes for a drug"""
        drug_lower = drug_name.lower()
        classes = []
        
        for drug_class, members in cls.DRUG_CLASSES.items():
            for member in members:
                if member in drug_lower:
                    classes.append(drug_class)
                    break
        
        # Also return exact drug name for specific interactions
        return classes
    
    @classmethod
    def normalize_drug_name(cls, name: str) -> str:
        """Normalize drug name for matching"""
        import re
        # Remove dosage, form, count
        name = re.sub(r'\d+\s*(mg|g|ml|mcg|µg|%)', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\d+\s*/\s*(Tab|Cap|Amp|Sach)', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\b(Tab|Cap|Syrup|Amp|Cream|Gel|Oint|F\.C\.Tab)\b', '', name, flags=re.IGNORECASE)
        return ' '.join(name.lower().split())


class DDIEngine:
    """Drug-Drug Interaction Detection Engine"""
    
    def __init__(self):
        self.rules = self._load_rules()
        self.interaction_cache: Dict[Tuple[int, int], List[DrugInteraction]] = {}
        logger.info(f"DDI Engine initialized with {len(self.rules)} rules")
    
    def _load_rules(self) -> Dict[Tuple[str, str], List[Tuple]]:
        """Load and index DDI rules"""
        rules = defaultdict(list)
        
        for rule in CRITICAL_DDI_RULES:
            drug1, drug2, severity, mechanism, management = rule
            # Index both directions
            rules[(drug1, drug2)].append(rule)
            rules[(drug2, drug1)].append((drug2, drug1, severity, mechanism, management))
        
        return rules
    
    def check_pair(self, med1: Medication, med2: Medication) -> List[DrugInteraction]:
        """Check for interactions between two medications"""
        interactions = []
        
        # Get drug classes and names to check
        identifiers1 = self._get_identifiers(med1)
        identifiers2 = self._get_identifiers(med2)
        
        checked = set()
        
        for id1 in identifiers1:
            for id2 in identifiers2:
                if (id1, id2) in checked or (id2, id1) in checked:
                    continue
                checked.add((id1, id2))
                
                # Check both directions
                for key in [(id1, id2), (id2, id1)]:
                    if key in self.rules:
                        for rule in self.rules[key]:
                            interaction = DrugInteraction(
                                drug1_id=med1.id,
                                drug2_id=med2.id,
                                drug1_name=med1.commercial_name,
                                drug2_name=med2.commercial_name,
                                severity=rule[2],
                                interaction_type=f"{rule[0]}-{rule[1]}",
                                mechanism=rule[3],
                                management=rule[4],
                                evidence_level=1,
                                source="HealthFlow DDI Rules v1.0"
                            )
                            interactions.append(interaction)
                            break  # Only add once per rule type
        
        return interactions
    
    def _get_identifiers(self, med: Medication) -> Set[str]:
        """Get all identifiers for a medication (name, generic, classes)"""
        identifiers = set()
        
        # Normalized commercial name
        norm_name = DrugClassifier.normalize_drug_name(med.commercial_name)
        identifiers.add(norm_name)
        
        # Generic name
        if med.generic_name:
            identifiers.add(med.generic_name.lower())
        
        # Active ingredients
        for ing in med.active_ingredients:
            identifiers.add(ing.lower())
        
        # Drug classes
        name_to_check = med.generic_name or med.commercial_name
        classes = DrugClassifier.get_drug_class(name_to_check)
        identifiers.update(classes)
        
        return identifiers
    
    def check_prescription(self, medications: List[Medication]) -> List[DrugInteraction]:
        """Check all pairs in a prescription for interactions"""
        all_interactions = []
        
        for i, med1 in enumerate(medications):
            for med2 in medications[i+1:]:
                interactions = self.check_pair(med1, med2)
                all_interactions.extend(interactions)
        
        # Sort by severity (major first)
        all_interactions.sort(key=lambda x: x.severity.value if hasattr(x.severity, 'value') else str(x.severity), reverse=True)
        
        return all_interactions
    
    def get_interaction_summary(self, interactions: List[DrugInteraction]) -> Dict:
        """Get summary of interactions"""
        summary = {
            "total": len(interactions),
            "by_severity": {"major": 0, "moderate": 0, "minor": 0, "unknown": 0},
            "requires_action": False,
            "interactions": []
        }
        
        for inter in interactions:
            sev = inter.severity.value if hasattr(inter.severity, 'value') else str(inter.severity)
            summary["by_severity"][sev] = summary["by_severity"].get(sev, 0) + 1
            
            if inter.severity == DDISeverity.MAJOR:
                summary["requires_action"] = True
            
            summary["interactions"].append({
                "drugs": f"{inter.drug1_name} + {inter.drug2_name}",
                "severity": sev,
                "mechanism": inter.mechanism,
                "management": inter.management
            })
        
        return summary


# Singleton instance
_ddi_engine: Optional[DDIEngine] = None

def get_ddi_engine() -> DDIEngine:
    """Get or create DDI engine singleton"""
    global _ddi_engine
    if _ddi_engine is None:
        _ddi_engine = DDIEngine()
    return _ddi_engine
