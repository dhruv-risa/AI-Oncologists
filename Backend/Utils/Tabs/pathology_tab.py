
## Source for pathology header = The selected Pathology Report
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

extracted_instructions = (
    "Role: Act as an Expert Clinical Data Abstractor. Extract structured data from the pathology report for a patient dashboard.\n\n"
    "1. HEADER & ALERTING:\n"
    "   - Report ID: Extract the primary Accession Number.\n"
    "   - Alert Banner: Analyze the final diagnosis. Priority: Malignancy > Suspicious/Atypical > Benign.\n"
    "     * Headline: Short summary (e.g., 'Invasive Carcinoma Detected' or 'Benign Findings').\n"
    "     * Subtext: Key actionable note (e.g., 'High-grade features noted' or 'Routine follow-up').\n\n"
    "2. DIAGNOSIS (The 'Truth'):\n"
    "   - Extract the FINAL DIAGNOSIS section. Do not include 'Clinical History' or 'Gross Description'.\n"
    "   - formatting: Split the diagnosis into clean, distinct bullet points. Remove disclaimer footers.\n\n"
    "3. PROCEDURE & SITE:\n"
    "   - Procedure Type: Classify strictly as 'Surgical Resection' (lobectomy, wedge, mastectomy) OR 'Biopsy/FNA' (core needle, fluid cytology).\n"
    "   - Site: The specific anatomical origin (e.g., 'Upper Lobe, Right Lung').\n\n"
    "4. DATES (Strict ISO 8601: YYYY-MM-DD):\n"
    "   - Biopsy_Date: Use 'Date of Collection' or 'Date of Procedure'. If missing, use 'Date Received'.\n"
    "   - Surgery_Date: Only populate if Procedure Type is 'Surgical Resection'. Otherwise, strictly return 'Not applicable'.\n\n"
    "5. PROGNOSTIC DETAILS:\n"
    "   - Tumor Grade: Look for 'Grade', 'Differentiation' (e.g., 'Well differentiated' = G1). If not found, return 'Not applicable'.\n"
    "   - Margin Status: Required for Resections. Look for 'Margins involved' or 'uninvolved'. For Biopsies, return 'Not applicable'."
)

description = {
    "pathology_report": {
        "header": {
            "report_id": "String (e.g., 'FNHAM25-00235')",
            "alert_banner": {
                "headline": "String. Max 5 words. The most critical takeaway.",
                "subtext": "String. Context or recommendation. (e.g., 'Correlate with radiology')"
            }
        },
        "diagnosis_section": {
            "full_diagnosis": "List[String]. Each distinct diagnostic finding as a separate string.",
            "procedure_category": "Enum['Surgical Resection', 'Biopsy/FNA', 'Other']",
            "procedure_original_text": "String. The raw procedure name from the report (e.g., 'US Guided Fine Needle Aspiration')"
        },
        "details": {
            "biopsy_site": "String. Anatomical location only (e.g., 'Right Adrenal Gland')",
            "biopsy_date": "String (YYYY-MM-DD). The collection date.",
            "surgery_date": "String (YYYY-MM-DD) or 'Not applicable'.",
            "tumor_grade": "String. Histologic grade (e.g., 'Grade 2' or 'Poorly Differentiated').",
            "margin_status": "String. (e.g., 'Negative for malignancy', 'Focally involved')."
        }
    }
}

extracted_instructions_hist_ihc = (
    "Extract advanced pathology features for a 'Morphology & Biomarker' card.\n\n"
    "1. MORPHOLOGY (Context-Dependent):\n"
    "   - IF Resection/Core Biopsy: Focus on TISSUE architecture. Extract: Histologic patterns (acinar, solid, lepidic), Lymphovascular Invasion (LVI), Perineural Invasion (PNI), and Necrosis.\n"
    "   - IF Cytology/FNA: Focus on CELLULAR features. Extract: Nuclear characteristics (molding, chromatin, nucleoli), background (necrosis, mucin), and cohesiveness.\n\n"
    "2. IHC MARKERS (Structured Extraction):\n"
    "   - Split combined lists (e.g., 'CK7 and TTF1 are positive' -> Extract as two separate objects).\n"
    "   - Status: Must be 'Positive', 'Negative', 'Equivocal', or 'Focal'.\n"
    "   - Details: Combine Intensity (Weak/Moderate/Strong) and Quantity (Percentage %) into this string. If unknown, use 'Further details not mentioned in the report'.\n\n"
    "3. INTERPRETATION TAGS:\n"
    "   - Generate 3-5 tags representing the 'Diagnostic Signature'.\n"
    "   - Prioritize: Histologic Subtype (e.g., 'Adenocarcinoma'), Driver Status (e.g., 'EGFR Detected'), or High-Risk features (e.g., 'High Grade')."
)

description_hist_ihc = {
    "pathology_combined": {
        "morphology_column": {
            "title": "String. 'Histopathologic Features' (for tissue) or 'Cytopathologic Features' (for fluid/FNA)",
            "items": [
                "String. Short, distinct observation. (e.g., 'Cribriform architecture present', 'Prominent nucleoli')"
            ]
        },
        "ihc_column": {
            "title": "Immunohistochemistry",
            "markers": [
                {
                    "name": "String. Standardized Marker Name (e.g., 'TTF-1', 'PD-L1', 'Ki-67')",
                    "status_label": "Enum['Positive', 'Negative', 'Equivocal', 'Focal']",
                    "details": "String. (e.g., 'Strong nuclear staining, >80%' or 'Weak intensity')",
                    "raw_text": "String. The exact phrase from report for verification."
                }
            ]
        },
        "keywords": [
            "String. Short chips. Max 25 chars each. (e.g., 'Non-Small Cell', 'PD-L1 >50%')"
        ]
    }
}



def pathology_info(pdf_url):
    log_extraction_start(logger, "Pathology Tab - Summary", pdf_url)

    config = {
        "start_page": 1,
        "end_page": 30,
        "batch_size": 3,
        "enable_batch_processing": True,
        "model": "gpt-5"
    }

    logger.info("🔄 Extracting pathology summary (1/2)...")
    patient_pathology_summary = llmresponsedetailed(pdf_url, extraction_instructions= extracted_instructions, description=description, config=config)
    log_extraction_output(logger, "Pathology Summary", patient_pathology_summary)
    log_extraction_complete(logger, "Pathology Summary", patient_pathology_summary.keys() if isinstance(patient_pathology_summary, dict) else None)

    logger.info("🔄 Extracting pathology markers (2/2)...")
    patient_pathology_markers = llmresponsedetailed(pdf_url, extraction_instructions= extracted_instructions_hist_ihc, description=description_hist_ihc, config=config)
    log_extraction_output(logger, "Pathology Markers", patient_pathology_markers)
    log_extraction_complete(logger, "Pathology Markers", patient_pathology_markers.keys() if isinstance(patient_pathology_markers, dict) else None)

    # patient_pathology_markers = ""
    return patient_pathology_summary, patient_pathology_markers


# if __name__ == "__main__":
#     pdf_url = "https://drive.google.com/file/d/1lM7ztKs6_M1wu6sqjPpEKXE_iKZZK4MB/view"
#     pathology_summary, pathology_markers = pathology_info(pdf_url)
#     print("PATHOLOGY SUMMARY:")
#     print(json.dumps(pathology_summary, indent=2))
#     print("\nPATHOLOGY MARKERS & FEATURES:")
#     print(json.dumps(pathology_markers, indent=2))

#     pdf_url_2="https://drive.google.com/file/d/19PA7sLq_MNuH8cTbbCpLNMN8Hnb1v_oU/view?usp=sharing"