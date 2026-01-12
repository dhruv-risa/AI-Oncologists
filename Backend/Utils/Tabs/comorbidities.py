"""
Patient Comorbidities Status Extraction Module

Extracted comorbidities and functional data containing:
            - comorbidities (list[dict]): A list of objects containing:
                - condition_name: Name of the medical condition.
                - severity: Severity or stage (e.g., 'Stage IIIA', 'Moderate').
                - control_status: Current status (e.g., 'Stable', 'Controlled').
                - clinical_details: Supporting history or surgical notes.
                - associated_medications: List of drugs linked to the condition.
            - ecog_performance_status (dict):
                - score: Numerical ECOG score (0-4).
                - description: Textual definition of the patient's activity level.
"""
import sys
import os

# Add Backend to path for imports
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from Utils.Tabs.llmparser import llmresponsedetailed


def extract_comorbidities_status(pdf_url):
    description = {
                "comorbidities": [
                    {
                    "condition_name": "Name of the medical condition or chronic disease (e.g., Hypertension). This should not include cancer-related diagnoses.",
                    "severity": "Severity level of the condition if explicitly stated (e.g., Mild, Moderate).",
                    "clinical_details": "Brief relevant history or context (e.g., History of partial gastrectomy for ulcer disease).",
                    "associated_medications": "List of medications linked to this specific condition if identifiable."
                    }
                ],
                "ecog_performance_status": {
                    "score": "The numerical ECOG score (0-4).",
                    "description": "The textual definition of the score as documented in the record."
                }
            }

    extraction_instructions = (
                "Extract structured information regarding the patient's medical comorbidities and functional status. "
                "Identify specific condition names, their severity or stage, relevant clinical history details, "
                "and any associated medications. Additionally, extract the ECOG Performance Status score and its description. "
                "Return the output strictly as a JSON object matching the described schema. "
                "Do not infer values that are not explicitly stated. If a value is not present, return null."
            )

    comorbidities_data = llmresponsedetailed(pdf_url, extraction_instructions=extraction_instructions, description=description)
    return comorbidities_data