## Source : The most recent MD notes

import sys
import os
import requests

# Add Backend to path for imports
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from Utils.Tabs.llmparser import llmresponsedetailed
from Utils.logger_config import setup_logger, log_extraction_start, log_extraction_complete, log_extraction_output

# Setup logger
logger = setup_logger(__name__)

extracted_instructions_lot = (
    "Extract structured treatment data for a 'Lines of Therapy' timeline UI from the provided clinical notes. "
    "Scope: Include Systemic Therapy (Chemo, Immunotherapy, Targeted), Radiation Therapy, and major Surgeries. "
    "For each entry, extract:"
    "1. Line Title: The sequence number and main modality (e.g., 'Line 1 - Carboplatin' or 'Adjuvant - Radiation'). "
    "2. Status: 'Current', 'Past', or 'Planned'. "
    "3. Dates: Exact start and end dates. For Radiation, look for 'completed' dates. "
    "4. Regimen Display: The full string showing drug names with dosage, OR the radiation type/site (e.g., '70Gy to lung'). "
    "5. Cycles: The number of cycles (for drugs) or fractions (for radiation) if available. "
    "6. Toxicities: Specific side effects, including Grade if mentioned. "
    "7. Outcome Tag: Short clinical response code (e.g., 'Remission', 'Completed'). "
    "8. Discontinuation Reason: Why it stopped (e.g., 'Completed Course')."
)

description_lot = {
    "treatment_history": [
        {
            "header": {
                "line_number": "Integer (e.g., 1, 2) or 'Adjuvant'",
                "primary_drug_name": "Short name for the header title (e.g., 'Osimertinib')",
                "status_badge": "Current, Past, or Planned"
            },
            "dates": {
                "start_date": "YYYY-MM-DD",
                "end_date": "YYYY-MM-DD or 'Ongoing'",
                "display_text": "Formatted string like '01 Jun 2024 -> 01 Sep 2024'"
            },
            "regimen_details": {
                "display_name": "Full string with dosage for the body text (e.g., 'Osimertinib 80mg daily')"
            },
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
                "details": "Full description of outcome"
            },
            "reason_for_discontinuation": "Text explanation for the bottom section"
        }
    ]
}

extracted_instructions_timeline = (
    "Extract a high-level chronological timeline of major cancer-related events from the clinical notes. "
    "Scope: Include Systemic Therapies, Surgeries, Radiation, and significant diagnostic events (like progression). "
    "For each event, extract:"
    "1. Date Display: A concise date string. Use 'Mon YYYY' for single events (e.g., 'Jan 2025') or a range 'Mon-Mon YYYY' for continuous treatments (e.g., 'Jun-Sep 2024'). "
    "2. Title: The primary name of the intervention or event (e.g., 'Lobectomy', 'SRS - Brain Radiation', 'Carboplatin + Pemetrexed'). "
    "3. Subtitle: A very brief, 1-sentence summary of details, such as intent, cycle count, or outcome (e.g., 'Surgical resection', '4 cycles, progressed after completion'). "
    "Order the events reverse-chronologically (newest first)."
)

description_timeline = {
    "timeline_events": [
        {
            "date_display": "String for the left column (e.g., 'Jan 2025')",
            "title": "Bold header text (e.g., 'Lobectomy')",
            "subtitle": "Grey sub-text description (e.g., 'Surgical resection')",
            "event_type": "Optional category for icon selection (e.g., 'Surgery', 'Radiation', 'Systemic', 'Imaging')"
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

