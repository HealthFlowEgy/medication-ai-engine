-- Egyptian AI Medication Validation Engine
-- Database Initialization Script
-- PostgreSQL 15+

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search

-- Medications table (main drug database)
CREATE TABLE IF NOT EXISTS medications (
    id SERIAL PRIMARY KEY,
    eda_id INTEGER UNIQUE,
    commercial_name VARCHAR(500) NOT NULL,
    generic_name VARCHAR(500),
    arabic_name VARCHAR(500),
    active_ingredients TEXT[],
    strength VARCHAR(100),
    strength_value DECIMAL(10,4),
    strength_unit VARCHAR(20),
    dosage_form VARCHAR(50),
    package_size VARCHAR(100),
    manufacturer VARCHAR(200),
    atc_code VARCHAR(10),
    eda_registration VARCHAR(50),
    rxnorm_id VARCHAR(20),
    drugbank_id VARCHAR(20),
    is_otc BOOLEAN DEFAULT FALSE,
    is_controlled BOOLEAN DEFAULT FALSE,
    is_high_alert BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for fast searching
CREATE INDEX idx_medications_commercial_name ON medications USING gin(commercial_name gin_trgm_ops);
CREATE INDEX idx_medications_generic_name ON medications USING gin(generic_name gin_trgm_ops);
CREATE INDEX idx_medications_arabic_name ON medications USING gin(arabic_name gin_trgm_ops);
CREATE INDEX idx_medications_atc_code ON medications(atc_code);
CREATE INDEX idx_medications_drugbank_id ON medications(drugbank_id);

-- Drug-Drug Interactions table
CREATE TABLE IF NOT EXISTS drug_interactions (
    id SERIAL PRIMARY KEY,
    drug1_id INTEGER REFERENCES medications(id),
    drug2_id INTEGER REFERENCES medications(id),
    drug1_generic VARCHAR(200),
    drug2_generic VARCHAR(200),
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('major', 'moderate', 'minor', 'unknown')),
    interaction_type VARCHAR(100),
    mechanism TEXT,
    clinical_effect TEXT,
    management TEXT,
    evidence_level INTEGER CHECK (evidence_level BETWEEN 1 AND 4),
    source VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(drug1_id, drug2_id)
);

CREATE INDEX idx_ddi_drug1 ON drug_interactions(drug1_id);
CREATE INDEX idx_ddi_drug2 ON drug_interactions(drug2_id);
CREATE INDEX idx_ddi_severity ON drug_interactions(severity);

-- Renal dosing adjustments
CREATE TABLE IF NOT EXISTS renal_dosing (
    id SERIAL PRIMARY KEY,
    medication_id INTEGER REFERENCES medications(id),
    generic_name VARCHAR(200),
    renal_stage VARCHAR(20) NOT NULL,
    gfr_min DECIMAL(5,1),
    gfr_max DECIMAL(5,1),
    dose_adjustment TEXT NOT NULL,
    notes TEXT,
    monitoring_required BOOLEAN DEFAULT FALSE,
    monitoring_parameters TEXT[],
    contraindicated BOOLEAN DEFAULT FALSE,
    source VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_renal_medication ON renal_dosing(medication_id);
CREATE INDEX idx_renal_generic ON renal_dosing(generic_name);
CREATE INDEX idx_renal_stage ON renal_dosing(renal_stage);

-- Hepatic dosing adjustments
CREATE TABLE IF NOT EXISTS hepatic_dosing (
    id SERIAL PRIMARY KEY,
    medication_id INTEGER REFERENCES medications(id),
    generic_name VARCHAR(200),
    child_pugh_class CHAR(1) CHECK (child_pugh_class IN ('A', 'B', 'C')),
    dose_adjustment TEXT NOT NULL,
    notes TEXT,
    monitoring_required BOOLEAN DEFAULT FALSE,
    contraindicated BOOLEAN DEFAULT FALSE,
    source VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_hepatic_medication ON hepatic_dosing(medication_id);
CREATE INDEX idx_hepatic_class ON hepatic_dosing(child_pugh_class);

-- Contraindications
CREATE TABLE IF NOT EXISTS contraindications (
    id SERIAL PRIMARY KEY,
    medication_id INTEGER REFERENCES medications(id),
    generic_name VARCHAR(200),
    condition_name VARCHAR(200) NOT NULL,
    severity VARCHAR(20) CHECK (severity IN ('absolute', 'relative')),
    reason TEXT,
    alternative_medications TEXT[],
    source VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_contraind_medication ON contraindications(medication_id);
CREATE INDEX idx_contraind_condition ON contraindications(condition_name);

-- Validation audit log
CREATE TABLE IF NOT EXISTS validation_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prescription_id VARCHAR(100),
    patient_id VARCHAR(100),
    pharmacy_id VARCHAR(100),
    prescriber_id VARCHAR(100),
    medications_checked INTEGER,
    interactions_found INTEGER,
    dosing_adjustments INTEGER,
    is_valid BOOLEAN,
    validation_time_ms DECIMAL(10,2),
    request_payload JSONB,
    response_payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_validation_log_prescription ON validation_log(prescription_id);
CREATE INDEX idx_validation_log_pharmacy ON validation_log(pharmacy_id);
CREATE INDEX idx_validation_log_created ON validation_log(created_at);

-- API usage statistics
CREATE TABLE IF NOT EXISTS api_statistics (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    endpoint VARCHAR(100) NOT NULL,
    request_count INTEGER DEFAULT 0,
    avg_response_time_ms DECIMAL(10,2),
    error_count INTEGER DEFAULT 0,
    UNIQUE(date, endpoint)
);

-- Functions for updating timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to relevant tables
CREATE TRIGGER update_medications_updated_at
    BEFORE UPDATE ON medications
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ddi_updated_at
    BEFORE UPDATE ON drug_interactions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (adjust for your setup)
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO medai;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO medai;

COMMENT ON TABLE medications IS 'Egyptian medications from EDA registry';
COMMENT ON TABLE drug_interactions IS 'Drug-drug interaction database';
COMMENT ON TABLE renal_dosing IS 'Renal dose adjustment rules';
COMMENT ON TABLE hepatic_dosing IS 'Hepatic dose adjustment rules';
COMMENT ON TABLE validation_log IS 'Audit log of all prescription validations';
