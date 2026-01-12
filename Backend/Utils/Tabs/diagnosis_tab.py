import sys
import os
import json

# Add Backend to path for imports
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from Utils.Tabs.llmparser import llmresponsedetailed
from Utils.logger_config import setup_logger, log_extraction_start, log_extraction_complete, log_extraction_output

# Setup logger
logger = setup_logger(__name__)


## What all is to be extracted from the relevant documents for the diagnosis tab
"""1. Header Details (Patient Summary)
primary_diagnosis: Non-Small Cell Lung Cancer (NSCLC)
histologic_type: Adenocarcinoma
diagnosis_date: March 12, 2023
initial_tnm_stage: T2aN1M0 (Stage IIB)
current_tnm_stage: T2aN2M1a (Stage IVA)
metastatic_status: Yes - Active metastases
metastatic_sites: Contralateral lung, pleural nodules
recurrence_status: Progressive disease

2. Stage Evolution Timeline
timeline_event_date: March 2023, June 2024, Current Status
timeline_stage_group: Stage IIB, Stage IVA, Stage IVA
timeline_tnm_status: T2aN1M0, T2aN2M1a, Metastatic
timeline_description: Initial diagnosis after biopsy, Disease progression detected, Multiple metastatic sites

3. Disease Course Duration (Footer)
duration_since_diagnosis: 21 months since initial diagnosis
duration_since_progression: 6 months since progression to metastatic disease
"""


pdf_url = ""

def diagnosis_extraction(pdf_url):

    extraction_instruction_header =  ("Extract comprehensive clinical summary data for the patient's primary cancer diagnosis from the medical records."
                            "1. CANCER IDENTIFICATION: Identify the primary cancer type (e.g., Non-Small Cell Lung Cancer), specific histology (e.g., Adenocarcinoma), and the initial diagnosis date."
                            "2. INITIAL STAGING: Find the staging information documented at the time of INITIAL/FIRST diagnosis. This is the baseline staging when the cancer was first identified. Look for terms like 'at diagnosis', 'initial presentation', or the earliest mentioned staging in the timeline."
                            "3. CURRENT STAGING: Find the MOST RECENT or CURRENT staging information. This reflects the latest disease status. Look for terms like 'current', 'most recent', 'latest', 'now shows', or dates closest to the document date."
                            "4. STAGING FORMAT: For both initial and current staging, extract:"
                            "   - TNM: The complete TNM classification (e.g., 'T2a N1 M0' or 'T2aN1M0'). Include all components (T, N, M) with their modifiers (prefixes like c/p/y and suffixes like letters/numbers)."
                            "   - AJCC Stage: The full AJCC stage designation (e.g., 'Stage IIB', 'Stage IVA', 'Pathologic Stage IIIA', 'Clinical Stage IB'). Include stage type prefix if mentioned."
                            "5. DISEASE STATUS: Extract metastatic status (whether cancer has spread), specific metastatic sites (organs/locations), and recurrence/disease progression status."
                            "6. KEY RULES:"
                            "   - If only one staging is documented in the record, use it for both initial_staging and current_staging."
                            "   - If the document mentions 'upstaging', 'downstaging', 'progression', or 'restaging', ensure these are reflected in current_staging."
                            "   - Return null for any field not explicitly stated in the document."
                            "   - Do not infer or calculate values."
                            "Return as a JSON object matching the schema below.")

    description_header = {
                "primary_diagnosis": "The formal clinical name of the primary cancer (e.g., 'Non-Small Cell Lung Cancer', 'Breast Carcinoma'). This should be the main cancer type being treated.",
                "histologic_type": "The specific microscopic cell type from pathology report (e.g., 'Adenocarcinoma', 'Squamous cell carcinoma', 'Ductal carcinoma'). This describes the cellular characteristics of the cancer.",
                "diagnosis_date": "The exact date when the cancer was first diagnosed in ISO format YYYY-MM-DD (e.g., '2023-03-15'). Look for phrases like 'diagnosed on', 'initial diagnosis date', or earliest mention of cancer detection.",
                "initial_staging": {
                    "tnm": "The TNM classification at initial/first diagnosis. Format examples: 'T2a N1 M0', 'T2aN1M0', 'pT1c pN2 cM0', 'cT3 cN2 cM1a'. Include prefixes (c=clinical, p=pathologic, y=post-therapy) and all modifiers. If staging evolved from initial diagnosis, this should capture the EARLIEST staging mentioned.",
                    "ajcc_stage": "The AJCC stage group at initial diagnosis. Format examples: 'Stage IIB', 'Stage IIIA', 'Pathologic Stage IB', 'Clinical Stage IVA'. Include the stage type prefix (Clinical/Pathologic) if documented. This is the baseline stage when cancer was first found."
                },
                "current_staging": {
                    "tnm": "The MOST RECENT TNM classification. Format examples: 'T4 N3 M1c', 'cT2 cN1 cM1b', 'ypT0 ypN0 cM0'. This should reflect the latest disease extent documented in the record. Look for most recent imaging, pathology, or clinical assessment.",
                    "ajcc_stage": "The MOST RECENT AJCC stage group. Format examples: 'Stage IVB', 'Stage IIA', 'Clinical Stage IVA', 'Pathologic Stage IIIB'. This is the current or latest stage reflecting current disease status. If disease progressed or responded to treatment, this should show the updated stage."
                },
                "metastatic_status": "Clear statement of metastatic spread. Examples: 'Yes - Active metastases', 'No metastatic disease', 'Metastatic', 'Limited stage', 'Extensive stage', 'M0 - No distant metastasis'. This indicates if cancer has spread beyond the primary site.",
                "metastatic_sites": "Array of specific anatomical sites where metastases are present. Examples: ['Brain', 'Liver', 'Lung'], ['Bone', 'Lymph nodes'], ['Contralateral lung', 'Pleura']. Only include locations explicitly documented as metastatic. Return empty array if no metastases.",
                "recurrence_status": "Current disease behavior or progression state. Examples: 'Initial diagnosis - no prior cancer history', 'Progressive disease', 'Stable disease', 'Recurrent disease', 'Complete response', 'Partial response', 'Local recurrence', 'Distant recurrence'. This describes the disease trajectory."
                }

    extraction_instruction_evolution_timeline = (
            "Extract a comprehensive chronological timeline of the patient's cancer diagnosis, staging changes, treatment history, and disease evolution."
            "OBJECTIVE: Create a complete timeline showing how the patient's cancer has progressed or responded over time, including all staging changes, treatments administered, and clinical findings."
            ""
            "FOR EACH DISTINCT TIME POINT in the patient's journey, extract the following:"
            ""
            "1. DATE/TIMEFRAME:"
            "   - Capture the specific date, month/year, or timeframe (e.g., 'March 2023', 'June 15, 2024', '2022-11', 'Current Status')."
            "   - If this is the most recent entry, label it as 'Current Status' or use the most recent date mentioned."
            "   - Ensure dates are in chronological order from earliest to most recent."
            ""
            "2. STAGE INFORMATION:"
            "   - timeline_stage_group: The AJCC stage at this time point (e.g., 'Stage IIB', 'Stage IVA', 'Stage IB'). Include stage type if mentioned (e.g., 'Pathologic Stage IIIA', 'Clinical Stage IVB')."
            "   - timeline_tnm_status: The complete TNM classification at this time point (e.g., 'T2a N1 M0', 'T4 N3 M1c', 'pT1c pN0 cM0'). Include all components with prefixes and modifiers."
            "   - If staging hasn't changed from previous entry, still include the same staging information."
            ""
            "3. CLINICAL DESCRIPTION:"
            "   - timeline_description: Brief description of what happened at this time point. Examples: 'Initial diagnosis after biopsy', 'Disease progression detected on CT', 'Complete response to chemotherapy', 'Local recurrence identified', 'Metastatic disease progression', 'Stable disease on follow-up'."
            ""
            "4. TREATMENT INFORMATION:"
            "   - regimen: The specific treatment, drug regimen, or procedure administered. Include drug names with doses if available."
            "     Examples: 'Right upper lobectomy', 'Carboplatin AUC 5 + Pemetrexed 500mg/m2', 'Osimertinib 80mg daily', 'Pembrolizumab 200mg Q3W', 'Radiation therapy 60 Gy', 'No treatment - surveillance'."
            "   - If no treatment was given, explicitly state 'Surveillance' or 'No active treatment'."
            ""
            "5. TOXICITIES:"
            "   - Extract all treatment-related side effects with their severity grades."
            "   - Format: [{\"effect\": \"Neutropenia\", \"grade\": \"Grade 3\"}, {\"effect\": \"Fatigue\", \"grade\": \"Grade 2\"}]"
            "   - Include CTCAE grade if mentioned (Grade 1-5) or severity descriptors (Mild, Moderate, Severe)."
            "   - If no toxicities are documented, return an empty array."
            ""
            "6. DISEASE FINDINGS:"
            "   - Extract ALL clinical, pathology, imaging, and molecular findings documented at this time point."
            "   - Return as an array of distinct findings, each as a separate string."
            "   - Include:"
            "     * Imaging findings: tumor size, number of lesions, location, measurements (e.g., '3 brain metastases measuring 5-8mm on MRI', 'Primary tumor decreased from 4cm to 2.5cm')"
            "     * Pathology findings: biopsy results, histology, grade (e.g., 'Biopsy confirmed adenocarcinoma', 'Well-differentiated tumor grade')"
            "     * Molecular/genomic findings: mutations, biomarkers, test results (e.g., 'EGFR exon 19 deletion detected', 'PD-L1 TPS 85%', 'ALK fusion positive')"
            "     * Clinical findings: symptoms, physical exam, performance status (e.g., 'ECOG 1', 'New onset seizures', 'Weight loss 10 pounds')"
            "     * Disease progression/response markers: RECIST criteria, tumor markers (e.g., 'Progressive disease per RECIST 1.1', 'CEA increased from 5 to 45')"
            "   - Format example: [\"Primary tumor 4.2cm in RUL\", \"No lymph node involvement\", \"EGFR exon 19 deletion\", \"PD-L1 50%\"]"
            ""
            "KEY GUIDELINES:"
            "- Create timeline entries for: initial diagnosis, staging changes, treatment starts, disease progression/response events, and current status."
            "- Each time point should be a distinct entry in the array, ordered chronologically."
            "- Include at least: initial diagnosis entry and current status entry."
            "- If staging changed over time (e.g., upstaging from Stage II to Stage IV), ensure this is captured with separate timeline entries."
            "- If specific information is not documented for a time point, use null for that field rather than inferring."
            ""
            "Return all timeline events in chronological order in the 'stage_evolution_timeline' array."
        )

    description_evolution_timeline = {
        "stage_evolution_timeline": [
            {
                "timeline_event_date": "The date, month/year, or timeframe for this event. Format examples: 'March 2023', '2024-06-15', 'June 2024', 'Current Status'. Use 'Current Status' for the most recent entry. Ensure chronological ordering.",
                "timeline_stage_group": "The AJCC stage group at this time point. Format examples: 'Stage IIB', 'Stage IVA', 'Pathologic Stage IIIA', 'Clinical Stage IB', 'Stage IVB'. Must include 'Stage' prefix. Include stage type (Clinical/Pathologic) if documented.",
                "timeline_tnm_status": "The complete TNM classification at this time point. Format examples: 'T2a N1 M0', 'T2aN1M0', 'cT4 cN3 cM1c', 'pT1c pN0 cM0', 'T3 N2 M1a'. Include all components (T, N, M) with prefixes (c/p/y) and modifiers.",
                "timeline_description": "Brief clinical summary of what occurred at this time point. Examples: 'Initial diagnosis after CT-guided biopsy', 'Disease progression with new brain metastases', 'Partial response to chemotherapy', 'Surgical resection completed', 'Stable disease on maintenance therapy', 'Complete metabolic response on PET scan'.",
                "regimen": "The specific treatment administered at or after this time point. Examples: 'Carboplatin AUC 5 + Pemetrexed 500mg/m2 Q3W', 'Osimertinib 80mg PO daily', 'Right upper lobectomy with lymph node dissection', 'Pembrolizumab 200mg IV Q3W', 'Radiation 60 Gy in 30 fractions', 'Surveillance - no active treatment'. Include drug names, doses, routes, and frequency when available.",
                "toxicities": [
                    {
                        "effect": "The specific toxicity or adverse effect name. Examples: 'Neutropenia', 'Diarrhea', 'Fatigue', 'Rash', 'Neuropathy', 'Nausea', 'Anemia', 'Thrombocytopenia'.",
                        "grade": "The severity grade using CTCAE grading. Format examples: 'Grade 1', 'Grade 2', 'Grade 3', 'Grade 4', 'Mild', 'Moderate', 'Severe'. Must include 'Grade' prefix for numeric grades."
                    }
                ],
                "disease_findings": "Array of distinct clinical findings at this time point. Each finding should be a separate string. Include imaging results (tumor size, location, measurements), pathology results (cell type, grade, margins), molecular findings (mutations, biomarkers), clinical observations (symptoms, exam findings), and progression/response indicators. Format example: ['Primary mass 4.2cm x 3.8cm in right upper lobe', 'Mediastinal lymphadenopathy largest 2cm', 'No distant metastases on PET-CT', 'EGFR exon 19 deletion detected', 'PD-L1 expression 60%', 'ECOG performance status 1']. Return empty array if no findings documented."
            }
        ]
    }

    extraction_instruction_footer = ("Extract temporal information about the patient's cancer diagnosis and disease progression. "
                                    "Identify the date of the first cancer diagnosis and calculate the total duration from that date to the document signature date or current date mentioned in the document. "
                                    "Identify the date of the most recent disease progression event (e.g., new metastases detected, disease advancement, or new primary diagnosis) and calculate the duration from that progression date to the document signature date. "
                                    "If there is no documented progression, set duration_since_progression to 'N/A'. "
                                    "Return the output strictly as a JSON object matching the schema described. "
                                    "Express durations in human-readable format (e.g., '14 months', '3 months', '2 years'). "
                                    "Do not infer values; if a value is not explicitly stated, return null.")
    description_footer = {
                        "duration_since_diagnosis": "Total time from first ever diagnosis to the document signature date in human-readable format (e.g., '14 months', '2 years').",
                        "duration_since_progression": "Time elapsed from the most recent progression or new primary event to the document signature date in human-readable format (e.g., '3 months', '6 weeks'). Use 'N/A' if no progression is documented.",
                        "reference_dates": {
                            "initial_diagnosis_date": "The date of the first cancer diagnosis in ISO format (YYYY-MM-DD) or partial format (YYYY-MM).",
                            "last_progression_date": "The date of the most recent disease progression event in ISO format (YYYY-MM-DD) or partial format (YYYY-MM). Use null if no progression."
                        }
                    }

    log_extraction_start(logger, "Diagnosis Tab (3 components)", pdf_url)

    logger.info("🔄 Extracting patient diagnosis header data (1/3)...")
    diagnosis_header = llmresponsedetailed(pdf_url, extraction_instructions= extraction_instruction_header, description=description_header)
    log_extraction_output(logger, "Diagnosis Header", diagnosis_header)
    log_extraction_complete(logger, "Diagnosis Header", diagnosis_header.keys() if isinstance(diagnosis_header, dict) else None)

    logger.info("🔄 Extracting patient diagnosis stage evolution data (2/3)...")
    diagnosis_evolution_timeline = llmresponsedetailed(pdf_url, extraction_instructions=extraction_instruction_evolution_timeline, description=description_evolution_timeline)
    log_extraction_output(logger, "Diagnosis Evolution Timeline", diagnosis_evolution_timeline)
    log_extraction_complete(logger, "Diagnosis Evolution Timeline", diagnosis_evolution_timeline.keys() if isinstance(diagnosis_evolution_timeline, dict) else None)

    logger.info("🔄 Extracting patient diagnosis footer data (3/3)...")
    diagnosis_footer = llmresponsedetailed(pdf_url, extraction_instructions=extraction_instruction_footer, description=description_footer)
    log_extraction_output(logger, "Diagnosis Footer", diagnosis_footer)
    log_extraction_complete(logger, "Diagnosis Footer", diagnosis_footer.keys() if isinstance(diagnosis_footer, dict) else None)

    return diagnosis_header, diagnosis_evolution_timeline, diagnosis_footer


# diagnosis_info = diagnosis_extraction(pdf_url = "https://drive.google.com/file/d/1reIZIz8TOcOHhXheWZUszN5nfOqr0bQ-/view?usp=sharing")
# print(json.dumps(diagnosis_info, indent=2))