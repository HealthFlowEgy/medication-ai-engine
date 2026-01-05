# 🏥 Egyptian AI Medication Validation Engine

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)]()

AI-powered medication validation system for Egyptian healthcare, designed for integration with the HealthFlow Unified System.

## 🎯 Features

- **Drug-Drug Interaction (DDI) Detection**: Real-time identification of harmful drug combinations
- **Renal Dose Adjustments**: Automated GFR-based dosing recommendations
- **Hepatic Dose Adjustments**: Child-Pugh score-based adjustments
- **Egyptian Drug Database**: 47,292 medications from EDA registry
- **Arabic Language Support**: Arabic drug name search and prescription parsing
- **High-Alert Warnings**: Special alerts for dangerous medications
- **HealthFlow Integration**: REST API for seamless integration

## 🚀 Quick Start

### Using Docker (Recommended)

```bash
# Clone repository
git clone https://github.com/healthflow/medication-ai-engine.git
cd medication-ai-engine

# Copy your drug database
cp /path/to/cfgdrug.xlsx data/

# Start services
./scripts/quickstart.sh

# Or manually:
docker-compose up -d
curl -X POST "http://localhost:8000/admin/load-database?filepath=/data/cfgdrug.xlsx"
```

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Start server
uvicorn src.api.main:app --reload
```

## 📚 API Documentation

Once running, access Swagger documentation at: `http://localhost:8000/docs`

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/validate/prescription` | POST | Full prescription validation |
| `/validate/quick` | POST | Quick validation by medication IDs |
| `/validate/interaction` | POST | Check interaction between two drugs |
| `/medications/search` | GET | Search medications by name |
| `/medications/{id}` | GET | Get medication details |
| `/health` | GET | Service health check |

### Example: Validate Prescription

```bash
curl -X POST "http://localhost:8000/validate/prescription" \
  -H "Content-Type: application/json" \
  -d '{
    "patient": {
      "age": 65,
      "weight_kg": 70,
      "sex": "M",
      "gfr": 35,
      "conditions": ["diabetes"]
    },
    "medications": [
      {"medication_id": 103473, "dose": "100mg", "frequency": "daily"},
      {"medication_id": 103862, "dose": "500mg", "frequency": "BID"}
    ]
  }'
```

### Example Response

```json
{
  "is_valid": false,
  "medications_validated": 2,
  "interactions": [
    {
      "drug1": "Warfarin 5mg",
      "drug2": "Aspirin 100mg",
      "severity": "major",
      "mechanism": "Increased bleeding risk...",
      "management": "Avoid combination or monitor INR closely..."
    }
  ],
  "dosing_adjustments": [
    {
      "medication": "Metformin 500mg",
      "adjusted_dose": "Contraindicated",
      "reason": "Lactic acidosis risk",
      "contraindicated": true
    }
  ],
  "warnings": [
    "🔴 1 MAJOR drug interaction(s) detected - review required",
    "❌ 1 medication(s) contraindicated for patient's renal function"
  ],
  "recommendations": [
    "AVOID Metformin - Lactic acidosis risk. Consider alternatives."
  ],
  "validation_time_ms": 45.2
}
```

## 🏗️ Architecture

```
medication-ai-engine/
├── src/
│   ├── api/            # FastAPI REST endpoints
│   ├── core/           # Core validation logic
│   │   ├── models.py       # Data models
│   │   ├── drug_database.py # Egyptian drug DB
│   │   ├── ddi_engine.py    # DDI detection
│   │   └── validation_service.py
│   ├── dosing/         # Dosing calculators
│   └── nlp/            # Arabic NLP (future)
├── data/               # Drug databases
├── models/             # ML models (future)
├── tests/              # Test suite
├── docker/             # Docker configs
└── docs/               # Documentation
```

## 📊 Egyptian Drug Database

The system uses the official EDA (Egyptian Drug Authority) medication registry:

- **Total Medications**: 47,292
- **Tablets**: 6,663 (14.1%)
- **Capsules**: 3,186 (6.7%)
- **Injections/Ampoules**: 3,675 (7.8%)
- **Creams**: 2,008 (4.2%)
- **Syrups**: 1,016 (2.1%)

## 🔒 DDI Rules Coverage

### Current Rules (30+ critical interactions)
- Anticoagulants (Warfarin, NOACs)
- NSAIDs
- ACE Inhibitors + Potassium
- QT-Prolonging combinations
- Serotonin Syndrome risks
- Statin + CYP3A4 inhibitors
- Opioid + Benzodiazepine
- Methotrexate interactions
- Lithium interactions

### Planned Expansion
- DDInter integration (236,834 DDIs)
- ML-based novel interaction prediction

## 🩺 Renal Dosing Coverage

Dose adjustments available for:
- Antibiotics: Amoxicillin, Ciprofloxacin, Levofloxacin, Gentamicin, Vancomycin
- Cardiovascular: Atenolol, Digoxin, Lisinopril, Spironolactone
- Pain: Morphine, Gabapentin, NSAIDs
- Diabetes: Metformin, Glyburide, Sitagliptin
- Anticoagulants: Enoxaparin, Rivaroxaban, Dabigatran

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test
pytest tests/test_validation.py::TestDDIEngine -v
```

## 📈 Performance

| Metric | Target | Current |
|--------|--------|---------|
| Validation Latency | <200ms | ~50ms |
| DDI Check (10 meds) | <100ms | ~30ms |
| Medication Search | <50ms | ~10ms |
| Database Load | <30s | ~15s |

## 🚢 Deployment

### DigitalOcean (Existing HealthFlow Infrastructure)

```bash
# Build image
docker build -t medication-ai:v1.0.0 .

# Push to registry
docker tag medication-ai:v1.0.0 registry.digitalocean.com/healthflow/medication-ai:v1.0.0
docker push registry.digitalocean.com/healthflow/medication-ai:v1.0.0

# Deploy
kubectl apply -f k8s/
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql://localhost/medication_ai` |
| `REDIS_URL` | Redis connection | `redis://localhost:6379/0` |
| `HEALTHFLOW_API_URL` | HealthFlow API URL | - |
| `HEALTHFLOW_API_KEY` | HealthFlow API Key | - |
| `LOG_LEVEL` | Logging level | `INFO` |

## 📋 Roadmap

- [x] Sprint 0: Project setup & data models
- [x] Sprint 1: DDI engine MVP
- [x] Sprint 2: Dosing calculator
- [x] Sprint 3: REST API
- [ ] Sprint 4: Testing & refinement
- [ ] Sprint 5: HealthFlow integration
- [ ] Sprint 6: Arabic NLP
- [ ] Sprint 7: ML-enhanced DDI
- [ ] Sprint 8: Production hardening
- [ ] Sprint 9: Clinical validation
- [ ] Sprint 10: Pilot & launch

## 🤝 Contributing

This is a proprietary project for HealthFlow Group. Contact the development team for contribution guidelines.

## 📄 License

Proprietary - HealthFlow Group © 2026

## 📞 Support

- **Technical Issues**: tech@healthflow.eg
- **Clinical Questions**: clinical@healthflow.eg
- **Integration Support**: integration@healthflow.eg

---

Built with ❤️ for Egyptian Healthcare
