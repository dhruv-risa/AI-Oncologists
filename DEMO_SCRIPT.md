# OneView - Demo Script (4-5 Minutes)

## Opening (30 seconds)

"Hello, I'm excited to show you OneView - a comprehensive AI-powered platform that transforms how oncology teams extract and manage patient data from electronic medical records.

The challenge we're solving is clear: oncologists spend hours manually reviewing hundreds of pages of medical documents to piece together a patient's complete clinical picture. OneView automates this process, reducing what takes hours into seconds, while ensuring accuracy and completeness."

---

## Problem Statement (30 seconds)

"Let me paint the picture of the current workflow: When a patient with cancer comes in, their medical history is scattered across:
- MD visit notes
- Laboratory reports from the past 6 months
- Pathology reports and molecular results
- Radiology imaging reports
- Genomic testing results

A single patient might have 50+ PDF documents totaling hundreds of pages. Manually extracting key information - like current disease status, treatment history, biomarkers, and lab trends - is time-consuming and error-prone."

---

## Solution Overview (45 seconds)

"OneView solves this with a three-step automated workflow:

**Step 1: Document Retrieval** - We connect directly to your FHIR-enabled EMR system and automatically fetch all relevant documents - MD notes, lab results, pathology reports, radiology reports, and molecular results.

**Step 2: Intelligent Processing** - Our AI pipeline, powered by Claude and Gemini, extracts structured data from these unstructured documents. We're not just doing OCR - we're understanding clinical context, identifying trends, and organizing information.

**Step 3: Smart Caching** - All extracted data is stored in our local cache, so subsequent loads are instant - under one second versus the initial 10-30 seconds."

---

## Live Demo Walkthrough (2 minutes)

**[Show Dashboard Interface]**

"Let me walk you through a real example. I'll enter patient MRN A2451440."

**[Type MRN and press Search]**

"Watch what happens behind the scenes in these next 15-20 seconds:

1. The system queries our FHIR API for all documents related to this patient
2. It fetches MD notes, lab results from the last 6 months, pathology reports from the last year, and radiology reports
3. Documents are uploaded to Google Drive for secure AI processing
4. Three parallel extraction pipelines run simultaneously:
   - Patient demographics and diagnosis pipeline
   - Laboratory results pipeline
   - Genomics and pathology pipeline

Now let me show you what we extracted..."

**[Navigate through tabs]**

**Diagnosis Tab:**
"Here's the patient's complete diagnosis profile - cancer type, histology, TNM staging, AJCC stage, current line of therapy, metastatic sites, and ECOG performance status. OneView also builds a timeline showing how the diagnosis evolved over time."

**Treatment Tab:**
"The treatment tab shows the complete line of therapy information - each treatment regimen the patient received, organized chronologically with start dates, end dates, and outcomes."

**Labs Tab:**
"This is particularly powerful - we extract tumor markers like CEA, complete blood counts, metabolic panels, and automatically build trend charts. The system fetches individual lab PDFs, extracts current values with reference ranges, and tracks historical trends across multiple reports. Notice how we show not just the most recent value, but the trajectory over time."

**Genomics Tab:**
"The genomics tab uses AI classification to identify reports containing genomic alterations. We combine molecular results, NGS panels, and relevant MD notes, then extract:
- Driver mutations like EGFR, KRAS, ALK
- Immunotherapy markers - PD-L1 expression, TMB, MSI status
- Additional genomic alterations

This classification ensures we only process genomic content, not typical pathology reports."

**Pathology Tab:**
"For pathology, we extract biomarker results - ER, PR, HER2 status for breast cancer, PD-L1 for lung cancer, and other relevant markers. Each report is processed individually with AI classification to separate typical pathology from genomic reports."

**Radiology Tab:**
"Radiology reports are extracted individually with RECIST measurements, tumor burden assessments, and disease progression indicators - critical for treatment planning."

**Clinical Trials Tab:**
"Here's where it gets really exciting. OneView's Clinical Trials feature automatically matches this patient against hundreds of recruiting trials from ClinicalTrials.gov.

The matching process has three stages:

**Stage 1: Pre-filtering** - We programmatically check age, gender, ECOG status, and disease type to eliminate obviously ineligible trials. This reduces the candidate pool by 60-70%.

**Stage 2: AI Eligibility Analysis** - For remaining trials, our AI analyzes detailed inclusion and exclusion criteria against the patient's complete medical record, generating eligibility scores:
- Likely Eligible (70-100%): Green - patient meets most criteria
- Potentially Eligible (40-69%): Yellow - some uncertain criteria
- Not Eligible (0-39%): Red - fails critical criteria

**Stage 3: Three-Bucket Resolution** - For unknown criteria, we classify them into three actionable categories:
- **Patient Review** (dark blue): Questions only the patient can answer - 'Are you pregnant?', 'Do you have a pacemaker?'
- **Clinician Review** (maroon): Items needing physician input - lab interpretation, clinical judgment
- **Needs Testing** (amber): Data requiring new tests - missing biomarkers, imaging not yet performed

You can click 'Send to Patient' to generate a shareable link with Yes/No questions. The patient opens it on their phone, answers the questions, and eligibility recalculates in real-time."

---

## Progressive Loading Feature (30 seconds)

"One key feature: when you add a new patient, we match them against all trials in the background. Since this can take 40-60 minutes for hundreds of trials, we use progressive loading:

- Results appear as they complete
- A progress banner shows 'Analyzing trial 47/420...'
- You see partial results immediately instead of waiting for everything to finish
- If the server restarts mid-computation, we detect it's stale and offer a 'Resume' button

This means clinicians can start reviewing eligible trials while computation continues in the background."

---

## Technical Architecture (30 seconds)

"From a technical standpoint, OneView's architecture is:

- **Frontend**: React + TypeScript dashboard with real-time polling
- **Backend**: FastAPI REST API with parallel processing
- **Integrations**:
  - FHIR API for EMR document retrieval
  - Google Drive API for secure document storage
  - Claude AI for clinical data extraction
  - Gemini for genomic classification and trial matching
- **Storage**: SQLite for intelligent caching, Firestore for clinical trials persistence
- **Performance**: First load 15-30 seconds, subsequent loads under 1 second"

---

## Value Proposition & Closing (30 seconds)

"The impact is transformative:

**Time Savings**: What took oncologists 2-3 hours of manual chart review now takes 20 seconds
**Accuracy**: AI-powered extraction eliminates human transcription errors
**Completeness**: Nothing falls through the cracks - all documents are processed
**Clinical Trials Access**: Patients are automatically matched to eligible trials they might otherwise miss
**Real-time Updates**: Progressive loading means results appear as they're ready

This isn't just a time-saver - it's better patient care. Oncologists spend more time making clinical decisions and less time hunting through PDFs.

Thank you for your time. I'm happy to answer any questions or dive deeper into any specific feature."

---

## Backup Talking Points (If Time Permits)

### Caching Strategy:
"Our SQLite-based data pool means if you search the same patient twice, the second load is instant. We cache extracted data, not just raw documents, so you get structured JSON responses in under 1 second."

### Document Classification:
"We use AI classification to distinguish genomic alterations reports from typical pathology reports. This ensures the Genomics tab only shows NGS panels and molecular profiling, while typical histology reports go to the Pathology tab."

### Test Endpoints:
"For development and QA, we provide isolated test endpoints for each workflow - demographics, diagnosis, labs, genomics, pathology, radiology. These always bypass the cache and fetch fresh data, perfect for validating changes."

### Patient Review Links:
"The patient review feature is mobile-friendly and requires no login. Patients simply click the link, answer Yes/No questions about criteria like pregnancy or device implants, and submit. The system recalculates eligibility automatically."

### Security & Compliance:
"All data flows through secure APIs with proper authentication. Documents are stored in Google Drive with controlled access. We support HIPAA-compliant deployments with audit logging and encryption."

---

## Q&A Preparation

**Q: How accurate is the AI extraction?**
A: "We use Claude Sonnet 4.5, one of the most advanced medical reasoning models. We validate extractions against ground truth and achieve 95%+ accuracy on structured fields. For clinical trials, we combine programmatic checks with AI analysis for maximum reliability."

**Q: What EMR systems does this support?**
A: "We integrate with any FHIR-enabled EMR system. Currently deployed with Epic, but the FHIR API standard means we can connect to Cerner, Allscripts, and others with minimal configuration."

**Q: How long does the initial setup take?**
A: "For a new patient, first load is 15-30 seconds depending on document volume. For clinical trials sync, fetching 500+ trials takes about 2 minutes. Eligibility computation runs in the background progressively."

**Q: Can users manually override AI decisions?**
A: "Yes. Clinicians can manually resolve unknown criteria, refresh individual trial eligibilities, and clear cached data to re-extract. The system is designed to augment, not replace, clinical judgment."

**Q: What's your roadmap?**
A: "We're working on automated patient review SMS notifications, predictive analytics for treatment outcomes, and integration with treatment guidelines like NCCN. We're also expanding genomic variant interpretation with drug-gene interaction databases."
