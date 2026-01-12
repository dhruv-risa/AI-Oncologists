import sys
import os

# Add Backend to path for imports
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from Utils.Tabs.llmparser import llmresponsedetailed
import json

# -------------------------------------------------------------------------
# SECTION 1: REPORT SUMMARY
# UI Requirements: Study Type, Study Date, Overall Response, Prior Comparison
# -------------------------------------------------------------------------

extracted_instructions_summary = (
    "Analyze the provided radiology report header and findings to extract four specific fields for the 'Report Summary' card: "
    "1. Study Type: The specific imaging modality (e.g., CT Chest with contrast). "
    "2. Study Date: The date of the current exam. "
    "3. Overall Response: The overall disease status assessment (e.g., 'Partial Response (PR)', 'Stable Disease', 'Progressive Disease'). "
    "4. Prior Comparison: The date of the specific prior exam used for comparison."
)

description_summary = {
    "report_summary": {
        "study_type": "String - The modality and body part (e.g., 'CT Chest with contrast')",
        "study_date": "String - Date of the current scan (e.g., 'December 8, 2024')",
        "overall_response": "String - The summary response status (e.g., 'Partial Response (PR)')",
        "prior_comparison": "String - Date of the prior scan used for comparison (e.g., 'September 10, 2024')"
    }
}

# -------------------------------------------------------------------------
# SECTION 2: RECIST & IMPRESSION
# UI Requirements: Impression Text, Dual-Baseline RECIST Table (Initial vs Current Tx)
# -------------------------------------------------------------------------

extracted_instructions_imp_RECIST = (
    "Analyze the radiology reports to populate the 'RECIST Measurements' and 'Impression' sections. "

    "SECTION 1: IMPRESSION "
    "- Extract the 'Impression' section as an array of distinct findings. "
    "- Each finding should be a separate bullet point (e.g., ['Partial response to therapy', 'Decrease in size of primary lesion', 'New pleural effusion']). "
    "- If the impression contains multiple findings or observations separated by periods, semicolons, or new lines, split them into separate array items. "

    "SECTION 2: RECIST MEASUREMENTS (CRITICAL: DUAL BASELINE TRACKING) "
    "- You must extract lesion data comparing the CURRENT scan against TWO different historical baselines simultaneously: "
    "   A. 'Initial Diagnosis' Baseline: The state of disease at original diagnosis (e.g., Post-surgery/March 2023). "
    "   B. 'Current Treatment' Baseline: The state of disease at the start of the current drug therapy (e.g., January 2025). "

    "- For EACH target lesion (e.g., RUL mass, LUL nodule, Lymph Nodes): "
    "   1. Extract the Lesion Name. "
    "   2. Find its size in the 'Initial Diagnosis' baseline and calculate the % change vs current size. "
    "   3. Find its size in the 'Current Treatment' baseline and calculate the % change vs current size. "

    "- Calculate the 'Sum' row: "
    "   - Sum of Diameters (SOD) for Initial Baseline vs Current SOD -> % Change. "
    "   - Sum of Diameters (SOD) for Current Treatment Baseline vs Current SOD -> % Change. "

    "- Dates: Identify the label/date for both baselines (e.g., 'March 2023' and 'January 2025')."
)

description_imp_RECIST = {
    "impression": "Array of strings - Each distinct finding from the impression section as a separate item (e.g., ['Partial response to therapy', 'Decrease in size of primary lesion', 'New pleural effusion'])",

    "recist_measurements": {
        "column_headers": {
            "initial_diagnosis_label": "String - Label/Date for the first baseline (e.g., 'Initial Diagnosis March 2023')",
            "current_treatment_label": "String - Label/Date for the second baseline (e.g., 'Current Treatment January 2025')"
        },
        "lesions": [
            {
                "lesion_name": "String - Name of the lesion (e.g., 'RUL mass')",
                "initial_diagnosis_data": {
                    "baseline_val": "String - Measurement at initial diagnosis (e.g., '3.5 cm')",
                    "change_percentage": "String - Percentage change vs current (e.g., '-40%')"
                },
                "current_treatment_data": {
                    "baseline_val": "String - Measurement at start of current treatment (e.g., '3.2 cm')",
                    "change_percentage": "String - Percentage change vs current (e.g., '-34%')"
                }
            },
            "Extract ONE object per target lesion found."
        ],
        "sum_row": {
            "lesion_name": "String - Always 'Sum'",
            "initial_diagnosis_data": {
                "baseline_val": "String - Total SOD at initial diagnosis (e.g., '8.1 cm')",
                "change_percentage": "String - Total % change (e.g., '-35%')"
            },
            "current_treatment_data": {
                "baseline_val": "String - Total SOD at current treatment start (e.g., '7.4 cm')",
                "change_percentage": "String - Total % change (e.g., '-28%')"
            }
        }
    }
}

def radiology_info(pdf_url_only_report):
    # Extract Report Summary (Header data)
    patient_radiology_summary = llmresponsedetailed(
        pdf_url_only_report,
        extraction_instructions=extracted_instructions_summary,
        description=description_summary
    )

    # Extract Impression and Complex RECIST Table
    patient_radiology_imp_RECIST = llmresponsedetailed(
        pdf_url_only_report,
        extraction_instructions=extracted_instructions_imp_RECIST,
        description=description_imp_RECIST
    )

    return patient_radiology_summary, patient_radiology_imp_RECIST



def extract_radiology_details_from_report(radiology_url):
    """
    Extract radiology details from a single report.

    This function extracts:
    1. Basic report summary (study type, date, overall response) from radiology report
    2. Impression and RECIST measurements from radiology report

    Args:
        radiology_url (str): Google Drive URL for the radiology report

    Returns:
        Tuple of (radiology_summary, radiology_imp_RECIST)
    """
    return radiology_info(
        pdf_url_only_report=radiology_url
    )


if __name__ == "__main__":
    # Example usage
    summary, imp_recist = radiology_info(
        pdf_url_only_report="https://drive.google.com/file/d/1quio3qBXAFFOmoIQV3D8-q2Ye66VvfUK/view?usp=drive_link"
    )
    print("Radiology Summary:")
    print(json.dumps(summary, indent=2))
    print("\nRadiology Impression & RECIST:")
    print(json.dumps(imp_recist, indent=2))