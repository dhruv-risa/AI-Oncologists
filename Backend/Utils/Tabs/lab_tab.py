import sys
import os

"""Sabke trends nahi aa rahe he in the json file"""


# Add Backend to path for imports
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from Utils.Tabs.llmparser import llmresponsedetailed
from Utils.Tabs.lab_postprocessor import process_lab_data_for_ui
from Utils.logger_config import setup_logger, log_extraction_start, log_extraction_complete, log_extraction_output

# Setup logger
logger = setup_logger(__name__)

extracted_instructions = (
    "Extract structured lab result data for a 'Patient Labs Dashboard' from provided clinical notes and lab reports. "
    "Scope: Analyze ALL documents provided, including historical reports from the last 6 months. "
    "Conflict Resolution: If data exists in both an MD Note and a Lab Report for the same date, prefer values in the MD Note. "

    "MISSION: For EVERY biomarker listed (Tumor Markers, CBC, and Metabolic Panel), you must extract: "
    "1. The 'Current' (most recent) value with its unit, date, status, and reference range. "
    "2. A 'Trend' array containing ALL HISTORICAL DATA POINTS from EVERY report provided. "

    "CRITICAL INSTRUCTIONS FOR TRENDS: "
    "- You will be given MULTIPLE reports with different dates (e.g., reports from Oct 2025, Sept 2025, Aug 2025, etc.). "
    "- For each biomarker, look through EVERY report and extract the value from EACH report as a SEPARATE entry in the 'trend' array. "
    "- DO NOT just copy the current value into the trend array. Instead, search each report for historical values. "
    "- If a biomarker appears in 5 different reports with 5 different dates, the trend array should have 5 entries. "
    "- Include the date, value, status (Normal/High/Low), and source context (e.g., 'Quest Lab Report Oct 2025') for each trend entry. "
    "- Order trend entries from oldest to newest date. "
    "- If a biomarker was never measured historically, the trend array can contain just the current value. "

    "Targets: "
    "- TUMOR MARKERS: CEA, NSE, proGRP, CYFRA 21-1. "
    "- CBC: WBC, Hemoglobin, Platelets, ANC (if missing, use 'Segs#' or 'Polys, Abs'). "
    "- METABOLIC: Creatinine, ALT, AST, Albumin. "

    "CLINICAL INTERPRETATION: "
    "Summarize abnormalities: Anemia (Hgb <13.5 M / <12.0 F), Hepatic (ALT/AST >40), Neutropenia (ANC <1.5)."
)

def biomarker_schema():
    return {
        "current": {
            "value": "Float or 'Pending' - The most recent value for this biomarker",
            "unit": "String - The unit of measurement (e.g., 'g/dL', 'Thousand/uL')",
            "date": "YYYY-MM-DD - Date of the most recent measurement",
            "status": "String (e.g., 'Normal', 'High', 'Low') - Status based on reference range",
            "reference_range": "String - The reference range for this biomarker"
        },
        "trend": [
            {
                "date": "YYYY-MM-DD - Date when this measurement was taken",
                "value": "Float - The measured value on this date",
                "status": "String - Status on this date (Normal/High/Low)",
                "source_context": "String - Which report this came from (e.g., 'Quest Lab Report Oct 2025')"
            },
            "IMPORTANT: This is an ARRAY that should contain MULTIPLE entries, one for EACH time this biomarker was measured across ALL the provided reports. If you have 5 reports spanning 6 months, and this biomarker was measured in all 5, you should have 5 separate entries here with different dates. DO NOT just include the current value - extract ALL historical values from EVERY report provided."
        ]
    }

description = {
    "tumor_markers": {
        "CEA": biomarker_schema(),
        "NSE": biomarker_schema(),
        "proGRP": biomarker_schema(),
        "CYFRA_21_1": biomarker_schema()
    },
    "complete_blood_count": {
        "WBC": biomarker_schema(),
        "Hemoglobin": biomarker_schema(),
        "Platelets": biomarker_schema(),
        "ANC": biomarker_schema()
    },
    "metabolic_panel": {
        "Creatinine": biomarker_schema(),
        "ALT": biomarker_schema(),
        "AST": biomarker_schema(),
        "Total Bilirubin": biomarker_schema()
    },
    "clinical_interpretation": [
        "String summary of abnormal findings and rules applied."
    ]
}

def extract_lab_info(pdf_url, return_raw=False):
    """
    Extract and process lab information from PDF.

    Args:
        pdf_url: URL to the PDF containing lab reports
        return_raw: If True, returns raw unprocessed data. If False (default), returns UI-ready data.

    Returns:
        Processed lab data ready for UI consumption (or raw data if return_raw=True)
    """
    log_extraction_start(logger, "Lab Tab", pdf_url)
    logger.info("🔄 Extracting full patient lab trends...")
    raw_data = llmresponsedetailed(
        pdf_url,
        extraction_instructions=extracted_instructions,
        description=description,
        config = {
        "start_page": 1,
        "end_page": 100,
        "batch_size": 15,
        "enable_batch_processing": True,
        "model": "claude-sonnet-4-0"
        }
    )

    log_extraction_output(logger, "Lab Raw Data", raw_data)

    if return_raw:
        return raw_data

    # Postprocess the data for UI
    logger.info("🔄 Postprocessing lab data for UI...")
    processed_data = process_lab_data_for_ui(raw_data)

    log_extraction_output(logger, "Lab Processed Data", processed_data)
    log_extraction_complete(logger, "Lab Tab", processed_data.keys() if isinstance(processed_data, dict) else None)

    return processed_data

if __name__ == "__main__":
    import json

    pdf_url = "https://drive.google.com/file/d/1QBbtidv39Bmv6lBqE8_FiiuygWWZhrjI/view?usp=sharing"
    lab_info = extract_lab_info(pdf_url)

    # Pretty print the processed data
    print("\n" + "="*80)
    print("PROCESSED LAB DATA FOR UI")
    print("="*80)
    print(json.dumps(lab_info, indent=2))

    # Optionally save to file
    # with open("processed_lab_data.json", "w") as f:
    #     json.dump(lab_info, f, indent=2)