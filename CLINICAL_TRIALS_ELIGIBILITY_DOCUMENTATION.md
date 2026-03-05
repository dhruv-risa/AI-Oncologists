# Clinical Trials Eligibility Matching System — Technical Documentation

**Version:** 1.2
**Last Updated:** February 17, 2026
---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [System Architecture](#3-system-architecture)
4. [Data Extraction Pipeline](#4-data-extraction-pipeline)
5. [Clinical Trial Fetching](#5-clinical-trial-fetching)
6. [Eligibility Matching Engine](#6-eligibility-matching-engine)
7. [Unknown Criteria Analysis](#7-unknown-criteria-analysis)
8. [Optimization Work Done](#8-optimization-work-done)
9. [Results and Metrics](#9-results-and-metrics)
10. [Future Improvements](#10-future-improvements)
11. [API Reference](#11-api-reference)
12. [File Reference](#12-file-reference)

---

## 1. Executive Summary

The Clinical Trials Eligibility Matching System automates the work of a **Clinical Research Coordinator (CRC)** by matching oncology patients against recruiting clinical trials from ClinicalTrials.gov.

The system:
- Extracts structured patient data from unstructured medical records (PDFs) using AI
- Fetches recruiting trials from ClinicalTrials.gov API v2
- Evaluates each trial's inclusion/exclusion criteria against patient data using Gemini 2.0 Flash
- Pre-computes clinical facts (organ function, creatinine clearance, infection status) to reduce unknowns
- Provides a dashboard for CRCs to review matches and take action on remaining unknowns

**Current Performance (5 patients, 100 trials each):**
- 500 total eligibility computations, 0 errors
- Unknown criteria reduced from **32.3% to 23.7%** (26.1% reduction)
- Average computation time: ~140 seconds per patient (100 trials)

---

## 2. Problem Statement

### What a CRC Does Today (Manual Process)

1. Reviews a patient's medical record (demographics, diagnosis, labs, treatment history)
2. Searches ClinicalTrials.gov for relevant recruiting trials
3. Reads each trial's eligibility criteria (typically 15-30 criteria per trial)
4. Manually compares patient data against each criterion
5. Determines: eligible, not eligible, or needs more information
6. For unknowns — orders tests, asks the patient questions, or consults the physician

**Pain point:** This process takes **2-4 hours per patient per trial** and requires deep clinical knowledge.

### What Our System Does (Automated Process)

1. Extracts all patient data from PDFs into structured JSON (one-time, ~30 seconds)
2. Fetches 100 relevant trials automatically (batch sync, ~2 minutes)
3. AI evaluates all 100 trials simultaneously (~140 seconds per patient with 10 parallel workers)
4. Classifies each criterion as: MET, NOT MET, or UNKNOWN with confidence levels
5. Provides actionable resolution guides for unknown criteria

**Result:** Hours of manual work reduced to minutes, with detailed explanations for every determination.

---

## 3. System Architecture

```
                         ┌──────────────────────────┐
                         │     React Frontend        │
                         │  (Patient Dashboard)      │
                         │  - Clinical Trials Tab    │
                         │  - Trial Detail View      │
                         └───────────┬──────────────┘
                                     │ REST API
                                     ▼
                         ┌──────────────────────────┐
                         │     FastAPI Backend       │
                         │     (app.py)              │
                         │  - APScheduler (2 AM)     │
                         │  - Thread Pool (10)       │
                         └───────────┬──────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
    ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
    │  FHIR/EMR API    │  │ ClinicalTrials   │  │  Vertex AI       │
    │  (Patient PDFs)  │  │ .gov API v2      │  │  (Gemini 2.0     │
    │                  │  │ (Trial Data)     │  │   Flash)         │
    └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
             │                     │                      │
             ▼                     ▼                      ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                    SQLite Data Pool                          │
    │  - Patient data (JSON blobs by MRN)                         │
    │  - Cached trials (100 trials)                               │
    │  - Eligibility results (patient × trial matrix)             │
    └─────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| API Server | `Backend/app.py` (2,852 lines) | FastAPI endpoints, scheduler, CORS |
| Eligibility Engine | `Backend/Utils/Tabs/clinical_trials_tab.py` (2,436 lines) | Trial fetching, pre-filtering, LLM matching |
| Batch Engine | `Backend/Utils/batch_eligibility_engine.py` (532 lines) | Parallel computation, full sync orchestration |
| Data Pool | `Backend/data_pool.py` (1,090 lines) | SQLite caching for patients, trials, eligibility |
| Lab Extraction | `Backend/Utils/Tabs/lab_tab.py` (529 lines) | 40-biomarker extraction from lab PDFs |
| Comorbidities | `Backend/Utils/Tabs/comorbidities.py` (82 lines) | Comorbidities, ECOG, ROS, physical exam extraction |
| Demographics | `Backend/Utils/components/patient_demographics.py` (267 lines) | Patient demographics extraction |

---

## 4. Data Extraction Pipeline

Patient data is extracted from medical record PDFs using Gemini AI. Each extraction module targets a specific data domain.

### 4.1 Demographics Extraction

**Source:** MD Notes (most recent)
**Fields extracted:**
- Patient Name, MRN, DOB, Age, Gender
- Height, Weight (needed for Cockcroft-Gault creatinine clearance)
- Primary Oncologist, Last Visit Date

### 4.2 Lab Extraction (Expanded — 40 Biomarkers)

**Source:** Lab Result PDFs (last 6 months)
**File:** `Backend/Utils/Tabs/lab_tab.py`

The lab extraction was expanded from 12 to 40 biomarkers across 8 panels to reduce unknown criteria:

| Panel | Biomarkers |
|-------|------------|
| **Tumor Markers** | CEA, NSE, proGRP, CYFRA 21-1 |
| **CBC** | WBC, Hemoglobin, Platelets, ANC, MCV, RDW, Lymphocytes, Monocytes |
| **Metabolic Panel** | Sodium, Potassium, Chloride, CO2, Calcium, Phosphorus, Magnesium, Glucose, BUN, Creatinine, eGFR, Total Protein, Albumin, Uric Acid |
| **Liver Function** | ALT, AST, Total Bilirubin, Alkaline Phosphatase, LDH |
| **Coagulation** | INR, PT, aPTT |
| **Thyroid** | TSH, Free T4 |
| **Diabetes** | HbA1c |
| **Iron Studies** | Iron, Ferritin, TIBC |

Each biomarker stores: `value`, `unit`, `date`, `status`, `reference_range`, `source_context`.

### 4.3 Comorbidities & Functional Status

**Source:** MD Notes
**Fields extracted:**
- Comorbidities list (condition name, severity, clinical details, medications)
- ECOG Performance Status (score + description)
- Review of Systems (12 organ systems)
- Physical Examination findings (9 categories)

### 4.4 Other Extractions

| Tab | Data Extracted |
|-----|---------------|
| **Diagnosis** | Cancer type, histology, TNM staging, AJCC stage, metastatic sites, disease status |
| **Treatment** | Lines of therapy, regimen details, dates, response |
| **Genomics** | Mutations, biomarkers, NGS panel results |
| **Pathology** | Pathology summary, IHC results (ER, PR, HER2, PD-L1) |
| **Radiology** | Imaging findings, RECIST measurements, progression assessment |

---

## 5. Clinical Trial Fetching

### 5.1 Data Source

**API:** ClinicalTrials.gov API v2 (`https://clinicaltrials.gov/api/v2`)
**Status filter:** RECRUITING only
**Search strategy:** Broad queries across major cancer types

Default search queries (19 total):
- cancer, solid tumor, lung cancer, breast cancer, colorectal cancer, prostate cancer
- pancreatic cancer, melanoma, leukemia, lymphoma, ovarian cancer, bladder cancer
- kidney cancer, liver cancer, brain tumor, mesothelioma, sarcoma, myeloma
- immunotherapy, targeted therapy

### 5.2 Trial Data Structure

Each cached trial stores:
```
nct_id, title, status, phase, conditions, interventions,
brief_summary, eligibility_criteria_text, sex, minimum_age,
maximum_age, study_type, enrollment, locations, sponsor
```

### 5.3 Sync Mechanisms

| Mechanism | Trigger | Behavior |
|-----------|---------|----------|
| **Nightly Auto-Sync** | APScheduler cron at 2:00 AM | Fetches new trials + recomputes eligibility for all patients |
| **Startup Sync** | Server start (if cache empty) | Background thread triggers full sync |
| **Manual Sync** | Frontend "Sync Trials" button | `POST /api/trials/sync` |
| **New Patient** | When new patient is added | Auto-computes eligibility against all cached trials |

---

## 6. Eligibility Matching Engine

The matching engine is a 3-stage pipeline:

### Stage 1: Pre-Filtering (Programmatic)

**File:** `clinical_trials_tab.py` → `pre_filter_trial()`

Fast rule-based checks that eliminate obviously ineligible trials before any LLM calls:

| Check | Logic | Example |
|-------|-------|---------|
| **Age** | Patient age vs trial min/max age | Patient 65, trial requires 18-55 → EXCLUDE |
| **Gender** | Patient gender vs trial sex requirement | Male patient, trial FEMALE only → EXCLUDE |
| **ECOG** | Patient ECOG vs trial ECOG requirement | Patient ECOG 3, trial requires ≤1 → EXCLUDE |
| **Disease Type** | Cancer type match + non-oncology filter | Lung cancer patient, trial for diabetes → EXCLUDE |

The disease matching is nuanced:
- **Basket trials** (containing "solid tumor", "advanced cancer") match all cancer types
- **Non-oncology trials** are excluded unless they study the condition in a cancer context
- **Specific cancer trials** require the patient's cancer type to match

### Stage 2: Derived Clinical Facts (Python Pre-Computation)

**File:** `clinical_trials_tab.py` → `derive_clinical_facts()`

Before the LLM evaluates criteria, Python code pre-computes factual inferences from patient data. These are injected into the LLM prompt as verified facts it can cite directly.

**What gets computed:**

| Category | Derivation | Example Output |
|----------|-----------|----------------|
| **Reproductive Status** | Age + Gender | "Patient is a 65-year-old female — post-menopausal age (>=55). Not of childbearing potential." |
| **Blood Draw Capability** | Recent lab results exist | "Patient had blood successfully drawn and processed (most recent: 2025-12-15)." |
| **Life Expectancy** | ECOG + Disease Status | "ECOG 1: Patient is ambulatory and functional. Life expectancy typically > 6 months." |
| **Treatment History** | Count + Drug Names | "Patient has received 3 prior line(s) of therapy. Prior therapies include: carboplatin, pembrolizumab." |
| **Ambulatory Status** | Clinic Visit Dates | "Patient is attending clinic visits (last visit: 2025-12-20) — patient is ambulatory." |
| **Renal Function** | eGFR, Creatinine, Cockcroft-Gault | "RENAL FUNCTION: ADEQUATE — eGFR=72 mL/min (≥60). CREATININE: 0.9 mg/dL (0.69× ULN). CALCULATED CrCl: 78.3 mL/min" |
| **Hepatic Function** | ALT, AST, Bilirubin, ALP with ×ULN ratios | "HEPATIC FUNCTION: ADEQUATE — ALT=28 (0.8× ULN); AST=25 (0.71× ULN); Bilirubin=0.6 (0.5× ULN)" |
| **Hematologic Function** | WBC, Hgb, Platelets, ANC | "BONE MARROW: ADEQUATE — WBC=5.2; Hgb=13.1; Platelets=210; ANC=3.5" |
| **Coagulation** | INR, PT, aPTT | "COAGULATION: WITHIN NORMAL LIMITS — INR=1.0; PT=12.5 sec" |
| **Overall Organ Function** | Combined assessment | "OVERALL ORGAN FUNCTION: ADEQUATE — hepatic, renal, and hematologic all within acceptable limits." |
| **Infection Status** | Comorbidity scan for HIV, Hep, TB, Autoimmune | "NO HIV/AIDS documented. NO hepatitis documented. NO tuberculosis documented. NO autoimmune disease documented." |

**ULN (Upper Limit of Normal) Reference Values Used:**

| Biomarker | ULN | Source |
|-----------|-----|--------|
| Creatinine (Male) | 1.3 mg/dL | Standard clinical reference |
| Creatinine (Female) | 1.2 mg/dL | Standard clinical reference |
| ALT | 35 U/L | Standard clinical reference |
| AST | 35 U/L | Standard clinical reference |
| Total Bilirubin | 1.2 mg/dL | Standard clinical reference |
| ALP | 120 U/L | Standard clinical reference |

**Cockcroft-Gault Formula (Creatinine Clearance):**
```
CrCl = ((140 - Age) × Weight_kg) / (72 × Serum_Creatinine)
If female: CrCl × 0.85
```

### Stage 3: LLM Eligibility Analysis (Gemini 2.0 Flash)

**File:** `clinical_trials_tab.py` → `match_criteria_with_gemini()`

The LLM receives:
1. Full patient context (all extracted data formatted as text)
2. Pre-computed derived clinical facts
3. Trial criteria to evaluate (inclusion or exclusion)
4. Detailed prompt with inference rules

**Prompt Structure:**

```
PATIENT INFORMATION → [demographics, diagnosis, labs, treatment, comorbidities, etc.]

CLINICALLY DERIVED FACTS → [pre-computed organ function, infection status, etc.]

TRIAL CRITERIA TO EVALUATE → [numbered list of criteria]

INFERENCE RULES:
  - ALLOWED inferences (with citations required)
  - DOCUMENTED CLINICAL DATA sources to use
  - FORBIDDEN inferences (mark as UNKNOWN)
  - ADMINISTRATIVE criteria handling (based on ECOG)

RESPONSE FORMAT → JSON array with: criterion_text, patient_value, met, confidence, explanation
```

**LLM Output Per Criterion:**

```json
{
    "criterion_number": 1,
    "criterion_text": "Adequate hepatic function",
    "patient_value": "ALT=28 (0.8× ULN), AST=25 (0.71× ULN), Bilirubin=0.6 (0.5× ULN)",
    "met": true,
    "confidence": "high",
    "explanation": "Derived facts confirm HEPATIC FUNCTION: ADEQUATE. All values within normal limits."
}
```

**Met values for EXCLUSION criteria (note the inversion):**
- `met: true` → Patient HAS the condition → **INELIGIBLE** (excluded)
- `met: false` → Patient does NOT have the condition → **ELIGIBLE** (not excluded)
- `met: null` → Cannot determine → **UNKNOWN**

### Stage 4: Eligibility Scoring

After all criteria are evaluated, the system calculates an overall eligibility percentage:

```
Eligibility % = (criteria_met / total_evaluable_criteria) × 100
```

**Classification:**

| Category | Percentage | Meaning |
|----------|-----------|---------|
| **LIKELY_ELIGIBLE** | 70-100% | Patient meets most criteria, no exclusion flags |
| **POTENTIALLY_ELIGIBLE** | 40-69% | Patient may qualify, some unknowns |
| **NOT_ELIGIBLE** | 0-39% | Patient fails critical criteria |

### Batch Processing

**File:** `Backend/Utils/batch_eligibility_engine.py`

The batch engine processes the full patient × trial matrix:

- **ThreadPoolExecutor** with 10 parallel workers
- Each worker: pre-filter → build context → call Gemini → parse results → store
- Results stored in SQLite for instant retrieval
- Typical throughput: 100 trials per patient in ~140 seconds

---

## 7. Unknown Criteria Analysis

### What Are Unknowns?

When the LLM evaluates a criterion and the required information is not available in the patient's medical record, it returns `met: null` (UNKNOWN). This means we cannot determine eligibility for that specific criterion.

### Unknown Progression

| Stage | Total Unknowns | % Unknown | Reduction |
|-------|---------------|-----------|-----------|
| **Baseline** (before optimization) | 2,379 | 32.3% | — |
| **After Lab Re-extraction** (40 biomarkers) | 2,107 | 28.2% | 272 eliminated |
| **After Prompt Engineering** (derived facts) | 1,759 | 23.7% | 620 total eliminated (26.1%) |

### Unknown Categories

All remaining unknowns from eligible/potentially-eligible trials (89 unique criteria, 106 instances) fall into **3 resolution buckets:**

#### Bucket 1: Resolvable from Existing Data (~20%)
Answers exist in the chart but in a different format. Resolved by conversions or formulas.

| Example | What We Have | Resolution |
|---------|-------------|------------|
| KPS Score ≥ 70 | ECOG Score = 1 | KPS-ECOG conversion table: ECOG 1 = KPS 70-80 |
| Creatinine Clearance ≥ 60 | Age, Weight, Creatinine | Cockcroft-Gault formula |
| AST < 2.5× ULN | AST = 28 U/L | Compare to ULN (35): 28/35 = 0.8× → Meets criteria |
| BMI within range | Height + Weight | BMI = kg/m² |
| Prior treatment lines ≤ 3 | Treatment history | Count documented regimens |

**Who resolves:** CRC at their desk, 5-10 minutes
**Automation status:** Partially automated via `derive_clinical_facts()`. Can be fully automated by either adding more Python formulas or embedding a medical conversions reference in the LLM prompt.

#### Bucket 2: Resolvable at Point of Care (~42%)
Requires a brief clinical interaction at the next patient visit.

| Example | Resolution |
|---------|------------|
| ECOG Performance Status | 30-second bedside observation by clinician |
| Willing to use contraception | Ask the patient |
| Able to swallow oral tablets | Ask the patient |
| Life expectancy ≥ 12 weeks | Clinician judgment |
| No uncontrolled illness | Physician reviews current status |
| Recovered from prior treatment toxicities | Clinician checks at visit |
| No concurrent prohibited medications | Pharmacist/CRC reviews med list with patient |

**Who resolves:** CRC (patient questions) + treating physician (clinical assessments)
**Time:** 10-15 minutes at next scheduled visit

#### Bucket 3: Requires New Testing (~39%)
Specific diagnostic tests, imaging, or lab work not yet performed.

| Example | Test to Order |
|---------|--------------|
| LVEF ≥ 50% | Echocardiogram (1-2 days) |
| QTc < 470ms | 12-lead EKG (same day) |
| No CNS metastases | Brain MRI (2-3 days) |
| HIV negative | HIV serology (1-2 days) |
| Hepatitis B/C negative | Hep panel (1-2 days) |
| Measurable disease (RECIST) | CT/MRI within trial window |
| PD-L1 expression level | PD-L1 testing on biopsy tissue |

**Who resolves:** CRC flags → Physician orders → Lab/Radiology runs test
**Time:** 1-7 days depending on test

### Approach to Eliminate Bucket 1 Unknowns

Two complementary strategies:

**Strategy A — Python Pre-Computation (Current)**
`derive_clinical_facts()` in `clinical_trials_tab.py` runs before the LLM and pre-calculates:
- Organ function assessments with ×ULN ratios
- Creatinine clearance (Cockcroft-Gault)
- Infection status from comorbidity records
- Reproductive status from age/gender

Pros: Exact math, deterministic, fast
Cons: Requires code update for each new formula

**Strategy B — LLM Prompt Reference (Proposed)**
Embed a medical conversions reference table directly in the LLM prompt so it can calculate on the fly.

Pros: No code changes for new formulas, handles edge cases
Cons: LLMs can make arithmetic errors

**Recommended: Both together** — Python handles known common formulas precisely; LLM prompt handles edge cases as a safety net.

---

## 8. Optimization Work Done

### 8.1 Bug Fixes

**None.upper() Error (clinical_trials_tab.py:1229-1230)**

```python
# BEFORE (buggy) — caused 51 errors for patient A214065
patient_gender = demographics.get("Gender", demographics.get("Sex", "")).upper()
trial_sex = trial.get("sex", "ALL").upper()

# AFTER (fixed) — handles None values from database
patient_gender = (demographics.get("Gender") or demographics.get("Sex") or "").upper()
trial_sex = (trial.get("sex") or "ALL").upper()
```

Root cause: `demographics.get("Gender")` returned `None` (key exists, value is None). Python's `.get()` default is only used when the key is missing, not when the value is None. The `or` chain handles both cases.

### 8.2 Lab Extraction Expansion

Expanded from 12 biomarkers to 40 across 8 panels. This directly resolved 272 unknown criteria that previously said "NOT IN CONTEXT" because the lab values hadn't been extracted.

### 8.3 Derived Clinical Facts

Added `derive_clinical_facts()` function (270 lines) that pre-computes organ function, infection status, creatinine clearance, and other clinical inferences from existing patient data. This gave the LLM verified facts to cite instead of marking criteria as unknown.

### 8.4 Prompt Engineering

Restructured the LLM prompt with:
- **ALLOWED inferences** — explicitly listed what the LLM CAN determine from data
- **DOCUMENTED CLINICAL DATA** — pointed LLM to specific sections (ROS, Physical Exam, Labs, Derived Facts)
- **FORBIDDEN inferences** — narrowed to only truly undeterminable items (LVEF without echo, ECOG when not documented)
- **7 IMPORTANT RULES** — including "ALWAYS CHECK DERIVED FACTS FIRST" and "Lab-based criteria are NEVER unknown if values present"

### 8.5 Nightly Auto-Sync Scheduler

Added APScheduler for automatic trial syncing:
- **Cron job** at 2:00 AM daily — fetches new trials + recomputes eligibility
- **Startup sync** — if cache is empty, triggers background sync immediately
- **Thread-safe** — `_sync_lock` prevents concurrent syncs

---

## 9. Results and Metrics

### 9.1 Patient Results Summary

| Patient | MRN | Trials Evaluated | Errors | Time (sec) |
|---------|-----|-----------------|--------|------------|
| Talbot | A2406246 | 100 | 0 | 141.5 |
| Peterman | A214065 | 100 | 0 | 124.1 |
| Miller | A182478 | 100 | 0 | 191.7 |
| Finneman | A2451440 | 100 | 0 | 139.0 |
| Lacinak | A236987 | 100 | 0 | 143.8 |

### 9.2 Unknown Reduction Results

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Total criteria evaluated | 7,376 | 7,419 | — |
| Unknown criteria | 2,379 | 1,759 | -620 (26.1% reduction) |
| Unknown percentage | 32.3% | 23.7% | -8.6 percentage points |
| Eligible trial unknowns | — | 89 unique, 106 instances | Mapped to resolution guide |

### 9.3 Eligible Trials Unknown Breakdown

| Resolution Category | Count | % of Unknowns |
|--------------------|-------|---------------|
| Disease Assessment | 29 | 27.4% |
| Patient Question | 15 | 14.2% |
| Performance Status | 13 | 12.3% |
| Clinical Assessment | 10 | 9.4% |
| Treatment Plan | 9 | 8.5% |
| Lab/Testing | 8 | 7.5% |
| Administrative | 6 | 5.7% |
| Uncategorized | 6 | 5.7% |
| Treatment History | 4 | 3.8% |
| Cardiac Assessment | 4 | 3.8% |
| Imaging | 2 | 1.9% |

---

## 10. Future Improvements

### 10.1 Fully Automate Bucket 1 (Existing Data Conversions)

**Option A:** Add more formulas to `derive_clinical_facts()`:
- BMI calculation from height/weight
- BSA (Body Surface Area) from height/weight
- MELD score from bilirubin, INR, creatinine
- Child-Pugh score from albumin, bilirubin, INR, ascites, encephalopathy
- HCT-CI from comorbidities list

**Option B:** Embed a medical conversions reference in the LLM prompt so it can handle new formulas dynamically without code changes.

**Recommended:** Both together — Python for precision on known formulas, LLM for edge cases.

### 10.2 ECOG Score Resolution

3 of 5 patients have ECOG = "NA" (not documented in their PDFs). This is the single biggest source of unknowns. Resolution requires:
- Clinician performs a 30-second bedside assessment at next visit
- CRC enters the score into the system
- All ECOG-dependent criteria immediately resolve

### 10.3 Improve Trial Diversity

Current: 100 trials cached from broad cancer queries. Could expand to:
- Patient-specific queries based on cancer type + mutations
- More targeted queries for rare cancer subtypes
- Include ACTIVE_NOT_RECRUITING trials for pipeline awareness

---

## 11. API Reference

### Trial Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/trials/sync` | POST | Sync trials from ClinicalTrials.gov |
| `/api/trials/list` | GET | List all cached trials (paginated) |
| `/api/trials/{nct_id}` | GET | Get single trial details |
| `/api/trials/sync/status` | GET | Check sync status + scheduler info |

### Eligibility

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/eligibility/patient/{mrn}` | GET | Get all trial eligibility for a patient |
| `/api/eligibility/trial/{nct_id}` | GET | Get all patient eligibility for a trial |

### Patient Data

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/patient/all` | POST | Get complete patient data (cached) |
| `/api/patient/demographics` | POST | Get demographics only |
| `/api/tabs/lab` | POST | Get lab results |
| `/api/tabs/diagnosis` | POST | Get diagnosis info |
| `/api/tabs/treatment` | POST | Get treatment history |

### Sync Request Body

```json
{
  "background": true,
  "max_trials_per_query": 50,
  "limit_trials": 100
}
```

---

## 12. File Reference

### Core Files

| File | Lines | Purpose |
|------|-------|---------|
| `Backend/app.py` | 2,852 | FastAPI server, all endpoints, APScheduler, lifespan |
| `Backend/Utils/Tabs/clinical_trials_tab.py` | 2,436 | Trial fetching, pre-filtering, derive_clinical_facts(), LLM matching prompt |
| `Backend/Utils/batch_eligibility_engine.py` | 532 | ThreadPoolExecutor batch processing, full_sync() |
| `Backend/data_pool.py` | 1,090 | SQLite data pool — patient, trial, eligibility storage |

### Extraction Modules

| File | Lines | Purpose |
|------|-------|---------|
| `Backend/Utils/Tabs/lab_tab.py` | 529 | 40-biomarker lab extraction |
| `Backend/Utils/Tabs/comorbidities.py` | 82 | Comorbidities, ECOG, ROS, Physical Exam |
| `Backend/Utils/Tabs/diagnosis_tab.py` | 1,372 | Diagnosis details extraction |
| `Backend/Utils/Tabs/treatment_tab.py` | — | Treatment history extraction |
| `Backend/Utils/Tabs/genomics_tab.py` | 544 | Genomics/mutations extraction |
| `Backend/Utils/Tabs/pathology_tab.py` | 970 | Pathology report extraction |
| `Backend/Utils/Tabs/radiology_tab.py` | 871 | Radiology/imaging extraction |
| `Backend/Utils/components/patient_demographics.py` | 267 | Demographics extraction |

### Generated Reports

| File | Description |
|------|-------------|
| `Clinical_Trials_Eligibility_Report.xlsx` | Full eligibility report — 8 sheets (Summary, Eligible Trials, 5 patient details, All Trials Matrix) |
| `Unknown_Criteria_Resolution_Guide.xlsx` | 89 unique unknown criteria from eligible trials with resolution methods — 2 sheets |

### Key Functions Reference

| Function | File | Purpose |
|----------|------|---------|
| `fetch_trials_from_api()` | clinical_trials_tab.py | Fetches trials from ClinicalTrials.gov API v2 |
| `pre_filter_trial()` | clinical_trials_tab.py | Rule-based age/gender/ECOG/disease pre-filtering |
| `disease_matches_trial()` | clinical_trials_tab.py | Cancer type matching with basket trial support |
| `derive_clinical_facts()` | clinical_trials_tab.py | Pre-computes organ function, CrCl, infection status |
| `match_criteria_with_gemini()` | clinical_trials_tab.py | LLM-based criterion evaluation with structured prompt |
| `build_patient_context()` | clinical_trials_tab.py | Formats patient data as text for LLM |
| `process_single_trial()` | clinical_trials_tab.py | End-to-end single trial evaluation |
| `compute_eligibility_matrix()` | batch_eligibility_engine.py | Batch parallel computation of patient × trial matrix |
| `full_sync()` | batch_eligibility_engine.py | Fetches trials + computes eligibility for all patients |
| `scheduled_trial_sync()` | app.py | Nightly cron job function |

---

*This documentation reflects the system state as of February 17, 2026. For setup instructions, see README.md. For deployment, see DEPLOYMENT_GUIDE.md.*
