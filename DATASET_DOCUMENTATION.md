# AI-Oncologists SQLite Dataset Documentation

## Overview
This document describes the comprehensive patient dataset stored in the SQLite database (`data_pool.db`) for the AI-Oncologists project. The dataset contains structured clinical data for **11 cancer patients**, processed through multi-modal document extraction using Vertex AI Gemini 2.5 Flash.

---

## Database Schema

### Table: `patient_data_pool`

| Column | Type | Description |
|--------|------|-------------|
| `mrn` | TEXT (PRIMARY KEY) | Medical Record Number - unique patient identifier |
| `data` | TEXT (JSON) | Complete patient data as structured JSON blob |
| `created_at` | TIMESTAMP | Initial record creation timestamp |
| `updated_at` | TIMESTAMP | Last modification timestamp |

### Patient IDs (11 Patients)
- 2511180119
- 2512120056
- 319864
- 4006762
- 4028657
- 4034659
- 4121934
- 4125731
- 4173898
- 443455
- 451358

---

## Data Structure: 18 Key Components

Each patient record is a JSON object containing 18 comprehensive data categories extracted from multiple medical document types (MD notes, pathology reports, lab reports, genomics reports, and radiology reports).

---

## 1. `success` (Boolean)
- **Description**: Validation flag indicating successful data extraction
- **Purpose**: Error handling and data quality assurance
- **Values**: `true` or `false`

---

## 2. `mrn` (String)
- **Description**: Medical Record Number (patient identifier)
- **Purpose**: Primary key for patient lookup and record linking
- **Format**: Alphanumeric string (e.g., "2511180119", "319864")

---

## 3. `demographics` (Object)

### Source Document
**Most recent MD notes**

### Extraction Prompt Summary
Extracts basic patient information using deterministic clinical data extraction with temperature=0.

### Fields Extracted
- **Patient Name**: Full legal name
- **MRN**: Medical Record Number (redundant with top-level mrn)
- **Date of Birth**: MM/DD/YYYY format
- **Age**: Calculated age in years (current date minus DOB)
- **Gender**: Male/Female/Other
- **Height**: Various formats (e.g., "68in", "5 feet 7 inches")
- **Weight**: Various formats (e.g., "200lb")
- **Primary Oncologist**: Assigned treating physician
- **Last Visit**: Most recent clinical visit date (MM/DD/YYYY)

### Key Extraction Rules
- Uses "Date of Visit", "Encounter Date", or document date for Last Visit
- Age calculated dynamically based on current date
- Null returned for any field not explicitly stated

### Model Used
**Vertex AI Gemini 2.5 Flash** (temperature=0, top_p=1)

---

## 4. `diagnosis` (Object)

### Source Document
**Most recent MD notes**

### Extraction Prompt Summary
Comprehensive clinical disease summary extraction with strict formatting rules for TNM/staging. Uses industry-standard oncology terminology.

### Fields Extracted
- **cancer_type**: Primary cancer diagnosis (full medical terminology with proper spacing)
  - Examples: "Pulmonary adenocarcinoma", "Non-Small Cell Lung Cancer"

- **histology**: Specific histologic subtype
  - Examples: "Adenocarcinoma", "Squamous cell carcinoma", "Epithelioid"

- **diagnosis_date**: ISO format YYYY-MM-DD

- **initial_staging**: Staging at first diagnosis
  - `tnm`: TNM classification (NEVER includes "Stage" - e.g., "T2a N1 M0")
  - `ajcc_stage`: AJCC stage (ALWAYS includes "Stage" - e.g., "Stage IVA")

- **current_staging**: Most recent staging
  - `tnm`: Current TNM (e.g., "T4 N3 M1c")
  - `ajcc_stage`: Current AJCC stage (e.g., "Stage IV M1a")

- **line_of_therapy**: Current treatment line as INTEGER (1, 2, 3)

- **metastatic_sites**: Array of organ/location names (e.g., ["Pleura", "Bone"])

- **ecog_status**: Performance status score (0-4)

- **disease_status**: Standardized oncology terminology
  - RECIST-based: "Complete Response (CR)", "Partial Response (PR)", "Stable Disease (SD)", "Progressive Disease (PD)"
  - Clinical: "Newly Diagnosed", "Active Disease", "Responding to Treatment", "Recurrent Disease", "Remission"

### Critical Formatting Rules
1. TNM fields NEVER contain "Stage"
2. AJCC stage fields ALWAYS start with "Stage"
3. line_of_therapy MUST be integer, not string
4. disease_status uses industry-standard terminology
5. Primary organ never listed as metastatic site

### Model Used
**Vertex AI Gemini 2.5 Flash** (temperature=0, top_p=1)

---

## 5. `comorbidities` (Object)

### Source Document
**Most recent MD notes**

### Extraction Prompt Summary
Extracts non-cancer medical conditions and functional status.

### Fields Extracted
- **comorbidities**: Array of condition objects
  - `condition_name`: Medical condition name (excludes cancer diagnoses)
  - `severity`: Severity level (Mild/Moderate/Severe)
  - `clinical_details`: Relevant history/context
  - `associated_medications`: Array of medications for this condition

- **ecog_performance_status**
  - `score`: Numerical score (0-4)
  - `description`: Textual definition of activity level

### Key Extraction Rules
- Cancer-related diagnoses excluded
- Only explicitly stated conditions included
- Medications linked to specific conditions when identifiable

---

## 6. `treatment_tab_info_LOT` (Object)
**Lines of Therapy View**

### Source Document
**Most recent MD notes**

### Extraction Prompt Summary
Structured treatment history with critical line numbering rules. Distinguishes systemic therapy from local therapy.

### Fields Extracted
- **treatment_history**: Array of treatment line objects
  - **header**
    - `line_number`: INTEGER for systemic therapy, null for standalone local therapy
    - `primary_drug_name`: Drug name (e.g., "Carboplatin") or therapy name (e.g., "WBRT")
    - `status_badge`: "Current", "Past", or "Planned"

  - **dates**
    - `start_date`: YYYY-MM-DD
    - `end_date`: YYYY-MM-DD or "Ongoing"
    - `display_text`: "DD MMM YYYY -> DD MMM YYYY" or "DD MMM YYYY -> Ongoing"

  - **systemic_regimen**: Drug names only, separated by + (e.g., "Carboplatin + Pemetrexed + Pembrolizumab")
    - NO dosages, routes, or schedules

  - **local_therapy**: Radiation/surgery details (e.g., "WBRT 30Gy", "Right upper lobectomy")

  - **cycles_data**
    - `completed`: Number completed
    - `planned`: Number planned
    - `display_text`: "X of Y planned"

  - **toxicities**: Array of side effects
    - `grade`: Grade level
    - `name`: Toxicity name
    - `display_tag`: Combined display string

  - **outcome**
    - `response_tag`: Short code (e.g., "Partial Response (PR)")
    - `details**: Clinical details as bullet points (MAX 3 points) describing patient response, observations, tolerance

  - **reason_for_discontinuation**: Why treatment stopped (empty for ongoing)

### Critical Line Numbering Rules
1. Line numbers ONLY for systemic therapies
2. Line changes when:
   - Disease progression occurs
   - Complete therapy switch to different drug class
3. Line STAYS SAME when:
   - Dosage changes
   - Drug holds/resumptions
   - Adding/removing one component
4. Standalone radiation/surgery gets line_number=null

### Dosage Change Handling
- Create separate entry for new dosage period
- Keep same line_number
- Use outcome.details to describe change rationale

---

## 7. `treatment_tab_info_timeline` (Object)
**Timeline View**

### Source Document
**Most recent MD notes**

### Extraction Prompt Summary
High-level chronological timeline of major cancer events (reverse chronological order).

### Fields Extracted
- **timeline_events**: Array of event objects
  - `date_display`: "Mon YYYY" or "Mon-Mon YYYY"
  - `systemic_regimen`: Drug names (e.g., "Carboplatin + Pemetrexed + Pembrolizumab")
  - `local_therapy`: Detailed radiation/surgery description
  - `details`: Context-specific clinical details
    - For Systemic: Cycle info, intent, response
    - For Radiation: Dose, fractionation, technique
    - For Surgery: Procedure specifics, pathology findings
    - For Imaging: Key findings, disease extent
  - `event_type`: "Systemic", "Radiation", "Surgery", "Imaging"

---

## 8. `diagnosis_header` (Object)

### Source Document
**Most recent MD notes**

### Extraction Prompt Summary
Comprehensive cancer diagnosis summary with proper medical terminology formatting.

### Fields Extracted
- `primary_diagnosis`: Full cancer name with proper spacing (e.g., "Non-Small Cell Lung Cancer")
- `histologic_type`: Specific cell type (e.g., "Adenocarcinoma")
- `diagnosis_date`: ISO format YYYY-MM-DD
- `initial_staging`: TNM and AJCC at diagnosis
- `current_staging`: Most recent TNM and AJCC
- `metastatic_status`: Clear statement (e.g., "Yes - Active metastases")
- `metastatic_sites`: Array of spread locations (excludes primary organ)
- `recurrence_status`: Disease trajectory description

### Key Rules
- If no recent staging update, current_staging copies initial_staging
- Primary organ never listed as metastatic site
- TNM never contains "Stage", AJCC always contains "Stage"

### Model Used
**Vertex AI Gemini 2.5 Flash** (temperature=0)

---

## 9. `diagnosis_evolution_timeline` (Object)

### Source Document
**Most recent MD notes**

### Extraction Prompt Summary
Stage evolution and disease progression timeline with date normalization.

### Fields Extracted
- **timeline**: Array of progression events
  - `date_label`: Normalized dates (e.g., "December 2025", "January 2023")
  - `event_description`: What happened
  - `stage_info`: Stage at that time
  - `clinical_details`: Supporting information

### Date Normalization
Automatically converts vague dates:
- "Late 2025" → "December 2025"
- "Early 2023" → "January 2023"
- "Mid-2024" → "June 2024"
- "Late 2025 - Early 2026" → "December 2025"

---

## 10. `diagnosis_footer` (Object)

### Source Document
**Most recent MD notes**

### Fields Extracted
- Additional diagnosis context
- Duration calculations
- Supporting notes

---

## 11. `lab_info` (Object)

### Source Document
**Laboratory result reports** (NOT MD notes)

### Extraction Prompt Summary
Structured lab extraction from formal lab reports only. Extracts most recent values with clinical interpretation.

### Target Biomarkers

#### Tumor Markers
- CEA (Carcinoembryonic Antigen)
- NSE (Neuron-Specific Enolase)
- proGRP (Pro-Gastrin-Releasing Peptide)
- CYFRA 21-1 (Cytokeratin 19 Fragment)

#### Complete Blood Count (CBC)
- WBC (White Blood Cell Count)
- Hemoglobin
- Platelets
- ANC (Absolute Neutrophil Count) - or use Segs#/Polys, Abs

#### Metabolic Panel
- Creatinine
- ALT (Alanine Aminotransferase)
- AST (Aspartate Aminotransferase)
- Total Bilirubin

### For Each Biomarker
- `value`: Float or "Pending" or null
- `unit`: Measurement unit (e.g., "g/dL")
- `date`: YYYY-MM-DD (uses "Lab Resulted" date, NOT collection date)
- `status`: "Normal", "High", "Low"
- `reference_range`: Normal range string
- `source_context`: Document reference

### Clinical Interpretation Rules
- Anemia: Hgb <13.5 (M) or <12.0 (F)
- Hepatic dysfunction: ALT/AST >40
- Neutropenia: ANC <1.5

### CRITICAL Exclusion Rule
- IGNORE MD notes, physician notes, clinical notes
- ONLY extract from formal lab result reports

### Post-Processing
Data processed through `lab_postprocessor.py` for UI formatting and trend analysis.

### Model Used
**Vertex AI Gemini 2.5 Flash** (temperature=0)

---

## 12. `lab_reports` (Array)

### Description
Links to raw laboratory report documents on Google Drive.

### Content
Array of Google Drive URLs for complete lab test results.

---

## 13. `genomic_info` (Object)

### Source Document
**Genomic testing reports or MD visit notes**

### Extraction Prompt Summary
Clinically relevant molecular and genomic profiling extraction by an "Expert Molecular Pathologist". Focuses on actionable findings.

### Critical Focus Areas

#### 1. Driver Mutations (MANDATORY - 9 key drivers)
For EACH driver, always report:
- **Status**: "Detected" or "Not detected"
- **Details**: Specific variant or "Not detected"
- **Is_target**: True ONLY if explicitly marked as actionable/targetable

**Nine Key Drivers:**
- EGFR
- ALK
- ROS1
- KRAS
- BRAF
- MET
- RET
- HER2
- NTRK

#### 2. Biomarkers & Immunotherapy Markers
- PD-L1 Expression (value + scoring metric)
- Tumor Mutational Burden (TMB)
- Microsatellite Instability (MSI) status

#### 3. Additional Genomic Alterations
Only clinically relevant alterations included (FDA-approved targets, guideline-recommended, or clinical trial relevant).

### Clinical Relevance Definition
Alterations included ONLY if:
- FDA-approved drug target
- NCCN/ESMO guideline-recommended
- Enrolling clinical trial available
- Prognostic biomarker affecting management

### Model Used
**Vertex AI Gemini 2.5 Flash** (temperature=0)

---

## 14. `genomics_reports` (Array)

### Description
Links to genomic testing report documents on Google Drive.

### Content
Array of Google Drive URLs for full sequencing results and molecular testing.

---

## 15. `pathology_summary` (Object)

### Source Document
**Selected pathology report**

### Extraction Prompt Summary
Expert clinical data abstraction from pathology reports with proper formatting and concise summarization.

### Fields Extracted

#### Header & Alerting
- **report_id**: Accession number
- **alert_banner**
  - `headline`: 5-word critical takeaway (e.g., "Invasive Carcinoma Detected")
  - `subtext`: Actionable note (e.g., "High-grade features noted")

#### Diagnosis Section
- **full_diagnosis**: Array of 5-7 KEY bullet points (LIMIT enforced)
  - Proper capitalization (not all caps)
  - Grouped related findings
  - Focus: Primary diagnosis, tumor characteristics, nodal status, margins, critical immunostains

- **procedure_category**: "Surgical Resection" OR "Biopsy/FNA"
- **procedure_original_text**: Raw procedure name from report

#### Details
- **biopsy_site**: Anatomical location
- **biopsy_date**: YYYY-MM-DD (collection date)
- **surgery_date**: YYYY-MM-DD or "Not applicable"
- **tumor_grade**: Histologic grade (e.g., "Grade 2")
- **margin_status**: For resections (e.g., "Negative for malignancy")

### Formatting Rules
- Use ISO 8601 dates: YYYY-MM-DD
- Procedure Type strictly classified as Surgical Resection or Biopsy/FNA
- Surgery_Date = "Not applicable" for biopsies

### Model Used
**Vertex AI Gemini 2.5 Flash** (temperature=0)

---

## 16. `pathology_markers` (Object)

### Source Document
**Selected pathology report**

### Extraction Prompt Summary
Advanced pathology features for morphology and biomarker analysis. Context-dependent extraction based on specimen type.

### Fields Extracted

#### Morphology (Context-Dependent)
- **IF Resection/Core Biopsy**: Tissue architecture
  - Histologic patterns (acinar, solid, lepidic)
  - Lymphovascular Invasion (LVI)
  - Perineural Invasion (PNI)
  - Necrosis

- **IF Cytology/FNA**: Cellular features
  - Nuclear characteristics (molding, chromatin, nucleoli)
  - Background (necrosis, mucin)
  - Cohesiveness

#### IHC Markers (Structured)
For each marker:
- **name**: Standardized marker name (e.g., "TTF-1", "PD-L1", "Ki-67")
- **status**: "Positive", "Negative", "Equivocal", or "Focal"
- **details**: Combined intensity (Weak/Moderate/Strong) and quantity (%)
  - Default: "Further details not mentioned in the report"

**Special Handling**: Combined lists split into separate objects
- Example: "CK7 and TTF1 are positive" → Extract as TWO separate marker objects

#### Interpretation Tags
- 3-5 tags representing "Diagnostic Signature"
- Prioritize: Histologic subtype, Driver status, High-risk features

---

## 17. `pathology_reports` (Array)

### Description
Links to pathology report documents on Google Drive.

### Content
Array of Google Drive URLs for biopsy and tissue analysis documents.

---

## 18. `radiology_reports` (Array)

### Source Document
**Radiology imaging reports**

### Extraction Prompt Summary
Multi-section extraction covering report summary, RECIST measurements (dual-baseline tracking), impression, and additional findings.

### Section 1: Report Summary
- **study_type**: Modality and body part (e.g., "CT Chest with contrast")
- **study_date**: Current exam date
- **overall_response**: Disease status (e.g., "Partial Response (PR)")
- **prior_comparison**: Prior exam date for comparison

### Section 2: RECIST Measurements (Dual-Baseline Tracking)
**Critical Feature**: Compares current scan against TWO historical baselines simultaneously

- **Baseline A**: Initial Diagnosis (e.g., Post-surgery/March 2023)
- **Baseline B**: Current Treatment (e.g., January 2025)

For each target lesion:
- Lesion name
- Size in Baseline A vs current → % change
- Size in Baseline B vs current → % change

**Sum Row**: Sum of Diameters (SOD) for both baselines vs current SOD with % changes

### Section 3: Impression
- Array of distinct findings from impression section
- Each finding as separate bullet point
- Split by periods, semicolons, or new lines

### Section 4: Additional Findings
- Top 3-5 most clinically relevant findings beyond impression/targets
- Includes: New lesions, non-target changes, incidental findings, anatomical changes

### Content
Array of Google Drive URLs for CT, MRI, PET scan results and radiologist interpretations.

### Model Used
**Vertex AI Gemini 2.5 Flash** (temperature=0)

---

## Data Processing Pipeline

### 1. Document Sources (demo_data.json)
For each patient MRN:
- `md_notes`: Array of MD note URLs (typically 2)
- `pathology`: Array of pathology report URLs (1-7)
- `radiology`: Array of radiology report URLs (1-8)
- `genomics`: Array of genomics report URLs (1-6)
- `lab_results`: Array of lab report URLs (5-11)

### 2. Extraction Process
- **Model**: Vertex AI Gemini 2.5 Flash
- **Temperature**: 0 (deterministic)
- **Input**: PDF bytes from Google Drive URLs
- **Output**: Structured JSON matching schemas
- **Validation**: Strict schema enforcement with formatting rules

### 3. Post-Processing
- Lab data: `lab_postprocessor.py` for UI formatting
- Timeline dates: Automatic normalization of vague dates
- Data validation: Type checking and null handling

### 4. Storage
- SQLite database: `data_pool.db`
- Table: `patient_data_pool`
- Access: DataPool Python class with CRUD operations

---

## Access Methods (Python API)

### DataPool Class Methods

```python
from Backend.data_pool import get_data_pool

pool = get_data_pool()

# Store patient data
pool.store_patient_data(mrn="2511180119", data=patient_dict)

# Retrieve patient data
patient = pool.get_patient_data(mrn="2511180119")

# List all patients with summaries
all_patients = pool.list_all_patients()

# Check existence
exists = pool.patient_exists(mrn="2511180119")

# Delete patient
pool.delete_patient_data(mrn="2511180119")

# Clear entire pool
pool.clear_pool()
```

---

## Key Features

### 1. Date Normalization
Automatically normalizes vague timeline dates:
- "Late 2025" → "December 2025"
- "Early 2023" → "January 2023"
- "Mid-2024" → "June 2024"

### 2. Validation & Error Handling
- Input validation for MRN and data integrity
- Null handling for missing fields
- Schema enforcement for all extractions

### 3. Metadata Tracking
- `created_at`: Initial creation timestamp
- `updated_at`: Last modification timestamp
- `pool_updated_at`: Added to data on retrieval

### 4. Migration Ready
- SQLite with easy PostgreSQL migration path
- Singleton pattern for consistent access
- Table existence checks before operations

---

## Use Cases

1. **Training AI Models**: Multimodal oncology decision support
2. **Algorithm Validation**: Treatment recommendation validation
3. **Clinical Pathway Analysis**: Treatment pattern recognition
4. **Outcome Prediction**: Response and survival modeling
5. **Knowledge Extraction**: Clinical trial matching
6. **Quality Assurance**: Data completeness verification

---

## Data Quality Standards

### Extraction Principles
1. **Deterministic**: Temperature=0 for reproducibility
2. **Explicit Only**: No inference or calculation
3. **Standardized**: Industry-standard oncology terminology
4. **Validated**: Schema enforcement and type checking
5. **Null-Safe**: Returns null for missing data, never hallucinates

### Formatting Standards
- Dates: ISO 8601 (YYYY-MM-DD)
- TNM: Never contains "Stage"
- AJCC Stage: Always contains "Stage"
- Line of Therapy: Integer (1, 2, 3)
- Disease Status: RECIST or clinical standard terms

---

## Technical Specifications

- **Database**: SQLite 3
- **File Location**: `/Backend/data_pool.db`
- **LLM Model**: Vertex AI Gemini 2.5 Flash
- **Project**: prior-auth-portal-dev
- **Region**: us-central1
- **Total Patients**: 11
- **Average Documents per Patient**: 15-30
- **JSON Size per Patient**: ~50-100 KB

---

## Contact & Validation

For questions about the dataset structure, extraction methodology, or validation procedures, please refer to:
- Source code: `/Backend/Utils/`
- Main processing: `/Backend/main.py`
- API endpoints: `/Backend/app.py`
- Data model: `/Backend/data_pool.py`

---

**Document Version**: 1.0
**Last Updated**: February 2026
**Dataset Version**: v1.0 (11 patients)
