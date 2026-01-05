"""
Egyptian AI Medication Validation Engine - Configuration Settings
HealthFlow Group © 2026
"""
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"

# Database settings
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/medication_ai")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# API Settings
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_PREFIX = "/api/v1"
API_TITLE = "Egyptian Medication Validation AI Engine"
API_VERSION = "1.0.0"

# Model settings
DDI_MODEL_PATH = MODELS_DIR / "ddi_ensemble"
NER_MODEL_PATH = MODELS_DIR / "drug_ner"
ARABIC_NER_MODEL = "aubmindlab/bert-base-arabertv2"
BIO_BERT_MODEL = "dmis-lab/biobert-base-cased-v1.2"
CLINICAL_BERT_DDI = "ltmai/Bio_ClinicalBERT_DDI_finetuned"

# DDI Severity Levels
DDI_SEVERITY = {
    "MAJOR": 3,      # Avoid combination - high risk
    "MODERATE": 2,   # Use with caution - monitoring required
    "MINOR": 1,      # Minimal risk - awareness only
    "UNKNOWN": 0     # Not yet classified
}

# Egyptian Drug Authority (EDA) Integration
EDA_REGISTRY_URL = "https://eservices.edaegypt.gov.eg"
EDA_UPDATE_INTERVAL_DAYS = 7

# Dosing Adjustment Thresholds
RENAL_THRESHOLDS = {
    "NORMAL": {"gfr_min": 90, "gfr_max": float("inf")},
    "MILD": {"gfr_min": 60, "gfr_max": 89},
    "MODERATE": {"gfr_min": 30, "gfr_max": 59},
    "SEVERE": {"gfr_min": 15, "gfr_max": 29},
    "ESRD": {"gfr_min": 0, "gfr_max": 14}
}

HEPATIC_CHILD_PUGH = {
    "A": {"score_min": 5, "score_max": 6},
    "B": {"score_min": 7, "score_max": 9},
    "C": {"score_min": 10, "score_max": 15}
}

# Cache TTL (seconds)
CACHE_TTL_DDI = 3600        # 1 hour
CACHE_TTL_DRUG_INFO = 86400  # 24 hours
CACHE_TTL_DOSING = 1800      # 30 minutes

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# HealthFlow Integration
HEALTHFLOW_API_URL = os.getenv("HEALTHFLOW_API_URL", "https://api.healthflow.eg")
HEALTHFLOW_API_KEY = os.getenv("HEALTHFLOW_API_KEY", "")

# Feature Flags
ENABLE_ARABIC_NLP = True
ENABLE_DDI_AI = True
ENABLE_DOSING_CALC = True
ENABLE_AUDIT_LOG = True
