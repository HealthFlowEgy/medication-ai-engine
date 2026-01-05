#!/usr/bin/env python3
"""
Egyptian AI Medication Validation Engine
Database Loader - Process Egyptian Drug Database

Usage:
    python load_database.py /path/to/cfgdrug.xlsx [--output processed_drugs.json]
"""
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.drug_database import EgyptianDrugDatabase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_and_process_database(
    input_path: str, 
    output_path: str = None,
    export_json: bool = True
):
    """
    Load Egyptian drug database from Excel and process it.
    
    Args:
        input_path: Path to cfgdrug.xlsx
        output_path: Optional output path for processed JSON
        export_json: Whether to export processed data to JSON
    """
    logger.info(f"Loading database from: {input_path}")
    
    # Initialize database
    db = EgyptianDrugDatabase()
    
    # Load from Excel
    count = db.load_from_excel(input_path)
    logger.info(f"Loaded {count} medications")
    
    # Get statistics
    stats = db.get_statistics()
    logger.info("Database Statistics:")
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")
    
    # Export to JSON if requested
    if export_json:
        if output_path is None:
            output_path = str(Path(input_path).parent / "processed_drugs.json")
        
        db.export_processed(output_path)
        logger.info(f"Exported processed database to: {output_path}")
    
    # Sample searches
    logger.info("\nSample Searches:")
    
    test_queries = ["paracetamol", "amoxicillin", "warfarin", "metformin", "januvia"]
    for query in test_queries:
        results = db.search(query, limit=3)
        logger.info(f"  '{query}': {len(results)} results")
        for r in results[:2]:
            logger.info(f"    - {r.commercial_name}")
    
    # High alert medications
    high_alert_count = sum(1 for mid in db.medications if db.is_high_alert(mid))
    logger.info(f"\nHigh-Alert Medications: {high_alert_count}")
    
    return db, stats


def generate_sample_database(output_path: str = "data/sample_drugs.json"):
    """Generate a sample database for testing when real data is unavailable."""
    
    sample_medications = [
        # Analgesics
        {"Id": 100001, "CommercialName": "Panadol 500mg 24/Tab"},
        {"Id": 100002, "CommercialName": "Panadol Extra 500mg 24/Tab"},
        {"Id": 100003, "CommercialName": "Brufen 400mg 30/Tab"},
        {"Id": 100004, "CommercialName": "Brufen 600mg 20/Tab"},
        {"Id": 100005, "CommercialName": "Cataflam 50mg 20/Tab"},
        {"Id": 100006, "CommercialName": "Voltaren 75mg 10/Amp"},
        
        # Antibiotics
        {"Id": 100010, "CommercialName": "Augmentin 1gm 14/Tab"},
        {"Id": 100011, "CommercialName": "Augmentin 625mg 14/Tab"},
        {"Id": 100012, "CommercialName": "Amoxil 500mg 12/Cap"},
        {"Id": 100013, "CommercialName": "Ciprobay 500mg 10/Tab"},
        {"Id": 100014, "CommercialName": "Tavanic 500mg 7/Tab"},
        {"Id": 100015, "CommercialName": "Flagyl 500mg 20/Tab"},
        {"Id": 100016, "CommercialName": "Zithromax 500mg 3/Tab"},
        
        # Cardiovascular
        {"Id": 100020, "CommercialName": "Concor 5mg 30/Tab"},
        {"Id": 100021, "CommercialName": "Concor 10mg 30/Tab"},
        {"Id": 100022, "CommercialName": "Zestril 10mg 28/Tab"},
        {"Id": 100023, "CommercialName": "Tritace 5mg 28/Tab"},
        {"Id": 100024, "CommercialName": "Plavix 75mg 28/Tab"},
        {"Id": 100025, "CommercialName": "Aspocid 75mg 30/Tab"},
        {"Id": 100026, "CommercialName": "Warfarin 5mg 28/Tab"},
        {"Id": 100027, "CommercialName": "Xarelto 20mg 28/Tab"},
        {"Id": 100028, "CommercialName": "Lanoxin 0.25mg 30/Tab"},
        {"Id": 100029, "CommercialName": "Cordarone 200mg 30/Tab"},
        
        # Diabetes
        {"Id": 100030, "CommercialName": "Glucophage 500mg 50/Tab"},
        {"Id": 100031, "CommercialName": "Glucophage 850mg 30/Tab"},
        {"Id": 100032, "CommercialName": "Glucophage XR 1000mg 30/Tab"},
        {"Id": 100033, "CommercialName": "Januvia 100mg 28/Tab"},
        {"Id": 100034, "CommercialName": "Janumet 50/1000mg 56/Tab"},
        {"Id": 100035, "CommercialName": "Amaryl 2mg 30/Tab"},
        {"Id": 100036, "CommercialName": "Daonil 5mg 30/Tab"},
        
        # GI
        {"Id": 100040, "CommercialName": "Nexium 40mg 14/Tab"},
        {"Id": 100041, "CommercialName": "Nexium 20mg 14/Tab"},
        {"Id": 100042, "CommercialName": "Controloc 40mg 14/Tab"},
        {"Id": 100043, "CommercialName": "Motilium 10mg 30/Tab"},
        
        # Respiratory
        {"Id": 100050, "CommercialName": "Ventolin Inhaler 100mcg"},
        {"Id": 100051, "CommercialName": "Seretide 250/25 Diskus"},
        {"Id": 100052, "CommercialName": "Symbicort 160/4.5 Turbuhaler"},
        
        # CNS
        {"Id": 100060, "CommercialName": "Cipralex 10mg 28/Tab"},
        {"Id": 100061, "CommercialName": "Prozac 20mg 28/Cap"},
        {"Id": 100062, "CommercialName": "Xanax 0.5mg 30/Tab"},
        {"Id": 100063, "CommercialName": "Rivotril 0.5mg 30/Tab"},
        {"Id": 100064, "CommercialName": "Tegretol 200mg 50/Tab"},
        {"Id": 100065, "CommercialName": "Neurontin 300mg 50/Cap"},
        {"Id": 100066, "CommercialName": "Tramadol 50mg 20/Cap"},
        
        # Lipid Lowering
        {"Id": 100070, "CommercialName": "Lipitor 20mg 30/Tab"},
        {"Id": 100071, "CommercialName": "Lipitor 40mg 30/Tab"},
        {"Id": 100072, "CommercialName": "Crestor 10mg 28/Tab"},
        {"Id": 100073, "CommercialName": "Zocor 20mg 28/Tab"},
        
        # Thyroid
        {"Id": 100080, "CommercialName": "Eltroxin 50mcg 100/Tab"},
        {"Id": 100081, "CommercialName": "Eltroxin 100mcg 100/Tab"},
        
        # Steroids
        {"Id": 100090, "CommercialName": "Deltacortril 5mg 50/Tab"},
        {"Id": 100091, "CommercialName": "Decadron 0.5mg 20/Tab"},
        
        # Anticoagulation
        {"Id": 100100, "CommercialName": "Clexane 40mg 2/Syringe"},
        {"Id": 100101, "CommercialName": "Clexane 60mg 2/Syringe"},
        
        # Pain Management
        {"Id": 100110, "CommercialName": "MST 30mg 20/Tab"},
        {"Id": 100111, "CommercialName": "Fentanyl 25mcg/hr Patch"},
        
        # Diuretics
        {"Id": 100120, "CommercialName": "Lasix 40mg 20/Tab"},
        {"Id": 100121, "CommercialName": "Aldactone 25mg 20/Tab"},
        
        # Antibiotics - Aminoglycosides
        {"Id": 100130, "CommercialName": "Garamycin 80mg 1/Amp"},
        {"Id": 100131, "CommercialName": "Vancomycin 500mg Vial"},
        
        # Antifungals
        {"Id": 100140, "CommercialName": "Diflucan 150mg 1/Cap"},
        {"Id": 100141, "CommercialName": "Sporanox 100mg 4/Cap"},
    ]
    
    db = EgyptianDrugDatabase()
    
    from src.core.models import Medication
    for med_data in sample_medications:
        med = Medication.from_egyptian_db(med_data)
        db._process_medication(med)
    
    db._loaded = True
    
    # Export
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    db.export_processed(output_path)
    
    logger.info(f"Generated sample database with {len(sample_medications)} medications")
    logger.info(f"Saved to: {output_path}")
    
    return db


def main():
    parser = argparse.ArgumentParser(
        description="Load and process Egyptian drug database"
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Path to cfgdrug.xlsx (or 'sample' to generate sample data)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output path for processed JSON"
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Skip JSON export"
    )
    
    args = parser.parse_args()
    
    if args.input == "sample" or args.input is None:
        logger.info("Generating sample database for development...")
        output = args.output or "data/processed/sample_drugs.json"
        generate_sample_database(output)
    else:
        load_and_process_database(
            args.input,
            args.output,
            export_json=not args.no_export
        )


if __name__ == "__main__":
    main()
