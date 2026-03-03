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

from Backend.Utils.Tabs.llmparser import llmresponsedetailed


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
                },
                "review_of_systems": {
                    "constitutional": "String - Findings for constitutional symptoms (fever, weight loss, fatigue, night sweats) or 'Negative' or null",
                    "cardiovascular": "String - Findings for cardiovascular (chest pain, palpitations, edema, syncope) or 'Negative' or null",
                    "respiratory": "String - Findings for respiratory (cough, dyspnea, wheezing, hemoptysis) or 'Negative' or null",
                    "gastrointestinal": "String - Findings for GI (nausea, vomiting, diarrhea, constipation, abdominal pain, blood in stool) or 'Negative' or null",
                    "neurological": "String - Findings for neuro (headache, dizziness, weakness, numbness, seizures, vision changes) or 'Negative' or null",
                    "musculoskeletal": "String - Findings for MSK (joint pain, muscle pain, back pain, swelling) or 'Negative' or null",
                    "endocrine": "String - Findings for endocrine (thyroid issues, diabetes symptoms, heat/cold intolerance) or 'Negative' or null",
                    "hematologic": "String - Findings for hematologic (easy bruising, bleeding, lymphadenopathy) or 'Negative' or null",
                    "dermatologic": "String - Findings for skin (rash, lesions, itching, wounds) or 'Negative' or null",
                    "psychiatric": "String - Findings for psychiatric (depression, anxiety, insomnia, suicidal ideation) or 'Negative' or null",
                    "genitourinary": "String - Findings for GU (urinary frequency, hematuria, incontinence) or 'Negative' or null",
                    "other": "String - Any other ROS findings not covered above or null"
                },
                "physical_exam": {
                    "general_appearance": "String - General appearance description or null",
                    "heent": "String - Head, eyes, ears, nose, throat findings or null",
                    "cardiovascular_exam": "String - Heart exam findings (rhythm, murmurs, etc.) or null",
                    "respiratory_exam": "String - Lung exam findings (breath sounds, wheezes, etc.) or null",
                    "abdominal_exam": "String - Abdominal exam findings (tenderness, masses, etc.) or null",
                    "extremities": "String - Extremity findings (edema, cyanosis, clubbing) or null",
                    "neurological_exam": "String - Neurological exam findings or null",
                    "skin_exam": "String - Skin exam findings or null",
                    "lymph_nodes": "String - Lymph node exam findings (lymphadenopathy, location) or null"
                }
            }

    extraction_instructions = (
                "Extract structured information regarding the patient's medical comorbidities, functional status, "
                "review of systems (ROS), and physical examination findings. "
                "Identify specific condition names, their severity or stage, relevant clinical history details, "
                "and any associated medications. Additionally, extract the ECOG Performance Status score and its description. "
                "REVIEW OF SYSTEMS: Look for the 'Review of Systems' or 'ROS' section. For each organ system, "
                "extract whether findings are positive (describe them) or negative. If the section says 'negative' "
                "or 'unremarkable' for a system, record 'Negative'. "
                "PHYSICAL EXAM: Look for 'Physical Examination', 'Physical Exam', or 'PE' section. "
                "Extract findings for each body system examined. "
                "Return the output strictly as a JSON object matching the described schema. "
                "Do not infer values that are not explicitly stated. If a value is not present, return null."
            )

    comorbidities_data = llmresponsedetailed(pdf_url, extraction_instructions=extraction_instructions, description=description)
    return comorbidities_data