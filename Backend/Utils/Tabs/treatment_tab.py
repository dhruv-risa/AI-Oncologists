## Source : The most recent MD notes

import sys
import os
import requests

# Add Backend to path for imports
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from Backend.Utils.Tabs.llmparser import llmresponsedetailed
from Backend.Utils.logger_config import setup_logger, log_extraction_start, log_extraction_complete, log_extraction_output

# Setup logger
logger = setup_logger(__name__)

extracted_instructions_lot = (
    "Extract structured treatment data for a 'Lines of Therapy' timeline UI from the provided clinical notes. "
    "Scope: Include Systemic Therapy (Chemo, Immunotherapy, Targeted), Radiation Therapy, and major Surgeries. "
    ""
    "CRITICAL: LINE NUMBERING RULES (READ CAREFULLY):"
    "- Line numbers are ONLY for SYSTEMIC therapies (chemotherapy, immunotherapy, targeted therapy)."
    "- Local therapies (radiation, surgery) that occur ALONE without concurrent systemic therapy should NOT be assigned a line number."
    "- If a patient receives ONLY radiation or ONLY surgery with NO systemic drugs, create a separate entry with systemic_regimen=null and line_number=null."
    "- If radiation/surgery occurs WITH or AFTER systemic therapy as consolidation/adjuvant, it can be part of that systemic line."
    ""
    "WHEN DOES THE LINE NUMBER CHANGE? (CRITICAL - READ CAREFULLY):"
    "- The line number should ONLY change when:"
    "  1. Disease Progression: The cancer grows despite the current treatment, requiring a switch to a new therapy."
    "  2. Complete Therapy Switch: The doctor stops the current drugs entirely and starts a COMPLETELY DIFFERENT type of therapy (e.g., switching from immunotherapy to targeted therapy, or to a different chemotherapy agent not part of the original regimen)."
    ""
    "WHEN DOES THE LINE NUMBER STAY THE SAME? (CRITICAL - READ CAREFULLY):"
    "- The line number should STAY THE SAME when:"
    "  1. Dosage Changes: If only the dosage or frequency of the SAME drugs is modified (e.g., dose reduction, dose escalation)."
    "  2. Minor Regimen Adjustments: If the core drugs remain the same but with minor schedule changes."
    "  3. Drug Holds/Resumptions: If a drug is temporarily held and then resumed (same line)."
    "  4. Adding/Removing One Component: If one drug is added or removed from a multi-drug regimen but the primary agent(s) continue."
    ""
    "HANDLING DOSAGE CHANGES IN THE UI (CRITICAL):"
    "- When there is a dosage change, dose reduction, or dose escalation of the SAME drugs:"
    "  1. Create a SEPARATE entry in the treatment_history array for the new dosage period."
    "  2. Keep the SAME line_number as before (do NOT increment it)."
    "  3. Update the start_date to when the new dosage began."
    "  4. In the outcome.details field (Clinical Details), use bullet point format (•) with MAX 3 points describing what changed and clinical observations."
    "  5. For the first entry (before the change), use outcome.details to describe the clinical reason that led to the modification."
    "  6. This allows the UI to show the dosage change as a visible event while maintaining the correct line number."
    ""
    "EXAMPLE: If a patient receives 'Carboplatin + Pemetrexed' at 500mg from Jan-Mar, then the dose is reduced to 400mg from Apr-Jun:"
    "- First entry: line_number=1, dates='Jan-Mar', systemic_regimen='Carboplatin + Pemetrexed', outcome.details='• Received standard dose initially\\n• Developed Grade 3 diarrhea\\n• Required dose reduction', reason_for_discontinuation='' (empty, not discontinued)"
    "- Second entry: line_number=1, dates='Apr-Jun', systemic_regimen='Carboplatin + Pemetrexed', outcome.details='• Dose reduced to 400mg\\n• Improved tolerance with minimal toxicity\\n• Disease remained stable', reason_for_discontinuation='' (empty unless actually discontinued)"
    ""
    "For each entry, extract:"
    "1. Line Title: "
    "   - The sequence number MUST be an integer (1, 2, 3, etc.) - NOT text like 'first', '1st', 'Line 1'. Extract only the numeric value."
    "   - For the main modality, use the primary drug name (e.g., 'Carboplatin', 'Osimertinib')."
    "   - IMPORTANT: If this entry has ONLY local therapy (radiation/surgery) and NO systemic regimen, set line_number to null."
    "2. Status: 'Current', 'Past', or 'Planned'. "
    "3. Dates: Exact start and end dates in DD MMM YYYY format (e.g., '27 Jan 2026', '13 Jan 2026'). For display_text, format as 'DD MMM YYYY -> DD MMM YYYY' or 'DD MMM YYYY -> Ongoing'. For Radiation, look for 'completed' dates."
    "4. TREATMENT SPLIT (CRITICAL - READ CAREFULLY):"
    "   You must separate systemic drug treatments from local modalities to ensure accurate Line of Therapy counting."
    "   - systemic_regimen: Extract ONLY drug-based anti-cancer therapies."
    "     * Include: Chemotherapy, Immunotherapy, Targeted Therapy."
    "     * Exclude: Radiation, Surgery, Pain meds, Supportive care."
    "     * Format: 'Drug names ONLY, separated by +' (e.g., 'Carboplatin + Pemetrexed', 'Osimertinib', 'Carboplatin + Pemetrexed + Pembrolizumab')."
    "     * DO NOT include dosages, routes (IV/PO), schedules, or treatment phases."
    "     * Keep it simple and concise - just the drug names."
    "     * If no systemic therapy, set to null."
    "   - local_therapy: Extract ONLY focal/local treatments."
    "     * Include: Radiation Therapy (WBRT, SBRT, SRS), Cancer-Directed Surgery (Lobectomy, Resection)."
    "     * Format: 'Type and site' (e.g., 'WBRT 30Gy', 'Right upper lobectomy')."
    "     * Exclude: Systemic drugs."
    "     * If no local therapy, set to null."
    "5. Cycles: The number of cycles (for drugs) or fractions (for radiation) if available. "
    "6. Toxicities: Specific side effects, including Grade if mentioned. "
    "7. Outcome Tag: Short clinical response code (e.g., 'Remission', 'Completed'). "
    "8. Clinical Details (outcome.details): Format as bullet points (•) with MAXIMUM 3 points. Include:"
    "   - How the patient responded to the medication (symptom improvement, disease control)"
    "   - Notable clinical observations during treatment"
    "   - Treatment tolerance and patient condition"
    "   - Any dose modifications and why they were made"
    "   DO NOT include imaging findings, biomarker changes, or the final reason for discontinuation."
    "   Example: '• Good tolerance with mild fatigue\\n• Symptom improvement noted after cycle 2\\n• Dose reduced due to Grade 2 nausea'"
    "9. Discontinuation Reason: Specifically WHY the treatment was stopped (e.g., 'Progressive Disease', 'Completed Planned Course', 'Grade 3 Toxicity'). Only for discontinued treatments. Leave empty for ongoing treatments."
    ""
    "CRITICAL FORMATTING RULES:"
    "- line_number: MUST be an integer (1, 2, 3) for systemic therapies, OR null for standalone local therapies"
    "- primary_drug_name: Drug name for systemic therapy, or therapy name for standalone local therapy (e.g., 'WBRT')"
    "- Distinguish strictly between 'systemic_regimen' (drugs) and 'local_therapy' (radiation/surgery)"
    "- DO NOT assign line numbers to standalone radiation or surgery without systemic therapy"
)

description_lot = {
    "treatment_history": [
        {
            "header": {
                "line_number": "CRITICAL: Integer (e.g., 1, 2, 3) for systemic therapy lines ONLY, or null for standalone local therapy. Extract the numeric line number only for systemic treatments. For standalone radiation/surgery without concurrent systemic drugs, set to null. For adjuvant therapy, use 1 if it's the first systemic treatment.",
                "primary_drug_name": "Short name for the header title. For systemic therapy: drug name (e.g., 'Osimertinib', 'Carboplatin'). For standalone local therapy: therapy name (e.g., 'WBRT', 'Lobectomy').",
                "status_badge": "Current, Past, or Planned"
            },
            "dates": {
                "start_date": "YYYY-MM-DD",
                "end_date": "YYYY-MM-DD or 'Ongoing'",
                "display_text": "Formatted string like '27 Jan 2026 -> Ongoing' or '13 Jan 2026 -> 23 Jan 2026' (format: DD MMM YYYY -> DD MMM YYYY or DD MMM YYYY -> Ongoing)"
            },
            "systemic_regimen": "String. Drug names ONLY, separated by + (e.g., 'Carboplatin + Pemetrexed', 'Osimertinib', 'Carboplatin + Pemetrexed + Pembrolizumab'). DO NOT include dosages, routes, or schedules. Set to null if only surgery/radiation.",
            "local_therapy": "String. Focal treatments ONLY. Include Radiation (e.g., 'WBRT 30Gy', 'SBRT to lung') or Surgery (e.g., 'Right upper lobectomy'). Set to null if none occurred.",
            "cycles_data": {
                "completed": "Number of cycles completed (e.g., 4)",
                "planned": "Number of cycles planned (e.g., 6)",
                "display_text": "String representation (e.g., '4 of 6 planned')"
            },
            "toxicities": [
                {
                    "grade": "String (e.g., 'Grade 2')",
                    "name": "String (e.g., 'Diarrhea')",
                    "display_tag": "Combined string for the UI chip (e.g., 'Grade 2: Diarrhea')"
                }
            ],
            "outcome": {
                "response_tag": "Short code for the red/green badge (e.g., 'Partial Response (PR)', 'Progressive Disease (PD)')",
                "details": "CLINICAL DETAILS: Format as bullet points (•) with MAXIMUM 3 points. Include: (1) How the patient responded to the medication (clinical response, symptom improvement, disease control), (2) Notable clinical observations during treatment, (3) Treatment tolerance and patient's overall condition, (4) Any dose modifications and their rationale. Do NOT include imaging findings or biomarker changes. Example format: '• Good tolerance with mild fatigue\n• Symptom improvement noted after cycle 2\n• Dose reduced due to Grade 2 nausea'. This should capture relevant clinical information EXCEPT the final reason for discontinuation (which goes in reason_for_discontinuation field)."
            },
            "reason_for_discontinuation": "Text explanation specifically for WHY the treatment was stopped (e.g., 'Progressive disease', 'Completed planned course', 'Intolerable toxicity'). Leave this field for discontinued treatments only. For ongoing treatments, set to null or empty string."
        }
    ]
}

extracted_instructions_timeline = (
    "Extract a high-level chronological timeline of major cancer-related events from the clinical notes. "
    "Scope: Include Systemic Therapies, Surgeries, Radiation, and significant diagnostic/imaging events. "
    "For each event, extract:"
    "1. Date Display: A concise date string. Use 'Mon YYYY' for single events (e.g., 'Jan 2025') or a range 'Mon-Mon YYYY' for continuous treatments (e.g., 'Jun-Sep 2024'). "
    "2. TREATMENT SPLIT (CRITICAL):"
    "   - systemic_regimen: Extract ONLY drug-based anti-cancer therapies."
    "     * Include: Chemotherapy, Immunotherapy, Targeted Therapy."
    "     * Format: 'Drug names' (e.g., 'Carboplatin + Pemetrexed + Pembrolizumab', 'Osimertinib')."
    "     * If no systemic therapy, set to null."
    "   - local_therapy: Extract ONLY focal/local treatments."
    "     * Include: Radiation Therapy (WBRT, SBRT, SRS), Cancer-Directed Surgery (Lobectomy, Resection)."
    "     * Format: Detailed description with specifics (e.g., 'Whole brain radiation with hippocampal sparing for 10 brain metastases', 'Right upper lobectomy with mediastinal lymph node dissection')."
    "     * If no local therapy, set to null."
    "3. Event Type: Categorize the event for display purposes (e.g., 'Systemic', 'Radiation', 'Surgery', 'Imaging'). "
    "4. Details - CONTEXT-SPECIFIC EXTRACTION (CRITICAL):"
    "   Extract clinically meaningful details based on the event type:"
    "   "
    "   FOR SYSTEMIC THERAPY:"
    "   - Cycle information (e.g., 'Cycle 1 initiated, next cycle scheduled for [date]')"
    "   - Treatment intent (e.g., 'Neoadjuvant', 'Adjuvant', 'Palliative', 'Maintenance')"
    "   - Response assessment if available (e.g., 'Partial response after 4 cycles', 'Disease progression')"
    "   - Reason for discontinuation if stopped (e.g., 'Completed planned course', 'Progressive disease', 'Toxicity')"
    "   "
    "   FOR RADIATION THERAPY:"
    "   - Dose and fractionation (e.g., '30 Gy in 10 fractions', '60 Gy total dose')"
    "   - Treatment site and extent (e.g., 'for 10 brain metastases', 'to primary tumor bed')"
    "   - Technique if mentioned (e.g., 'with hippocampal sparing', 'stereotactic')"
    "   - Intent (e.g., 'palliative', 'curative', 'adjuvant')"
    "   "
    "   FOR SURGERY:"
    "   - Procedure specifics (e.g., 'with mediastinal lymph node dissection', 'wedge resection')"
    "   - Pathology confirmation (e.g., 'confirmed poorly differentiated NSCLC', 'margins negative')"
    "   - Molecular findings if available (e.g., 'KRAS G12C mutated', 'EGFR exon 19 deletion')"
    "   - Outcome (e.g., 'successful resection', 'R0 resection achieved')"
    "   "
    "   FOR IMAGING/DIAGNOSTIC EVENTS:"
    "   - Imaging modality (e.g., 'Brain MRI', 'PET CT', 'Chest CT')"
    "   - Key findings (e.g., 'revealed at least 5 metastatic lesions', 'showed extensive disease')"
    "   - Disease extent (e.g., 'to lymph nodes, adrenals, peritoneum, and bones')"
    "   - Response assessment if comparing to prior (e.g., 'decreased from baseline', 'new lesions identified')"
    "   - Lesion details (e.g., 'simulation identified 10 lesions for treatment')"
    "   "
    "   Format as a single concise sentence containing the most clinically relevant information for that event type. "
    "   "
    "Order the events reverse-chronologically (newest first)."
)

description_timeline = {
    "timeline_events": [
        {
            "date_display": "String for the left column (e.g., 'Jan 2025', 'Dec 2025')",
            "systemic_regimen": "String. Drug-based treatments ONLY. Include Chemo, Immuno, Targeted therapy (e.g., 'Carboplatin + Pemetrexed + Pembrolizumab', 'Osimertinib'). Set to null if only surgery/radiation/imaging.",
            "local_therapy": "String. Focal treatments ONLY with detailed description. For Radiation: include type and site (e.g., 'Whole brain radiation with hippocampal sparing for 10 brain metastases', 'SBRT to lung lesion'). For Surgery: include procedure and site (e.g., 'Right upper lobectomy with mediastinal lymph node dissection', 'Wedge resection of lung nodule'). Set to null if none occurred.",
            "details": "String. Context-specific clinical details based on event type: For Systemic - cycle info, response, intent (e.g., 'Cycle 1 initiated, next cycle scheduled for Feb 17, 2026'). For Radiation - dose, fractionation, extent (e.g., '30 Gy in 10 fractions, palliative intent'). For Surgery - pathology findings, molecular results (e.g., 'Biopsy confirmed poorly differentiated NSCLC, KRAS G12C mutated'). For Imaging - key findings, disease extent (e.g., 'Brain MRI revealed at least 5 metastatic lesions, simulation identified 10 lesions'). Make it clinically meaningful and specific.",
            "event_type": "String. Category for display (e.g., 'Systemic', 'Radiation', 'Surgery', 'Imaging'). This helps the UI show appropriate styling/icons."
        }
    ]
}

def extract_treatment_tab_info(pdf_url):
    log_extraction_start(logger, "Treatment Tab (2 components)", pdf_url)

    logger.info("🔄 Extracting treatment lines of therapy (1/2)...")
    patient_treatment_lot = llmresponsedetailed(pdf_url, extraction_instructions=extracted_instructions_lot, description=description_lot)
    log_extraction_output(logger, "Treatment LOT", patient_treatment_lot)
    log_extraction_complete(logger, "Treatment LOT", patient_treatment_lot.keys() if isinstance(patient_treatment_lot, dict) else None)

    logger.info("🔄 Extracting treatment timeline (2/2)...")
    patient_treatment_timeline = llmresponsedetailed(pdf_url, extraction_instructions=extracted_instructions_timeline, description=description_timeline)
    log_extraction_output(logger, "Treatment Timeline", patient_treatment_timeline)
    log_extraction_complete(logger, "Treatment Timeline", patient_treatment_timeline.keys() if isinstance(patient_treatment_timeline, dict) else None)

    return patient_treatment_lot, patient_treatment_timeline

