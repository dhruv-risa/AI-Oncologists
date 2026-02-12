import sys
import os
import json
import re
import requests
import base64
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from datetime import datetime
from io import BytesIO

# Add Backend to path for imports
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from Utils.Tabs.llmparser import llmresponsedetailed
from Utils.Tabs.lab_postprocessor import process_lab_data_for_ui
from Utils.logger_config import setup_logger, log_extraction_start, log_extraction_complete, log_extraction_output

# Setup logger
logger = setup_logger(__name__)

# Initialize Vertex AI
vertexai.init(project="prior-auth-portal-dev", location="us-central1")

extracted_instructions = (
    "Extract structured lab result data for a 'Patient Labs Dashboard' from the provided lab report. "
    "Scope: Analyze the SINGLE document provided and extract current values only. "

    "EXCLUSION RULE - CRITICAL: "
    "- IGNORE and DO NOT EXTRACT any data from MD notes, physician notes, clinical notes, progress notes, or consultation reports. "
    "- ONLY extract data from actual laboratory result reports, lab panels, and test result documents. "
    "- Focus solely on formal lab reports with test names, values, units, and reference ranges. "

    "MISSION: For EVERY biomarker listed (Tumor Markers, Complete Blood Count, and Metabolic Panel), extract: "
    "- The MOST RECENT value from this document with its unit, date, status, and reference range. "
    "- Use the 'Lab Resulted' or 'Resulted' date (NOT specimen collection date) when available. "

    "Targets: "
    "- TUMOR MARKERS: CEA, NSE, proGRP, CYFRA 21-1. "
    "- CBC: WBC, Hemoglobin, Platelets, ANC (if missing, use 'Segs#' or 'Polys, Abs'). "
    "- METABOLIC: Creatinine, ALT, AST, Total Bilirubin (may also be labeled as 'Bilirubin' or 'Bili')."

    "CLINICAL INTERPRETATION: "
    "Summarize abnormalities: Anemia (Hgb <13.5 M / <12.0 F), Hepatic (ALT/AST >40), Neutropenia (ANC <1.5)."
)

def biomarker_schema():
    return {
        "value": "Float or 'Pending' or null - The most recent value for this biomarker in this document",
        "unit": "String - The unit of measurement (e.g., 'g/dL', 'Thousand/uL')",
        "date": "MM/DD/YYYY - Date of the measurement (use Lab Resulted date)",
        "status": "String (e.g., 'Normal', 'High', 'Low') - Status based on reference range",
        "reference_range": "String - The reference range for this biomarker",
        "source_context": "String - Brief description of source (e.g., 'Lab Report Page 1')"
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

def extract_with_gemini(pdf_input):
    """
    Extract lab data using Vertex AI Gemini SDK.

    Args:
        pdf_input: Either bytes (PDF content) or local path to the PDF file

    Returns:
        Dictionary containing extracted lab data
    """

    # Handle both bytes and file path inputs
    if isinstance(pdf_input, bytes):
        logger.info(f"📤 Using PDF bytes ({len(pdf_input)} bytes)")
        pdf_bytes = pdf_input
    else:
        # Assume it's a file path
        logger.info(f"📤 Reading PDF from path: {pdf_input}")
        with open(pdf_input, "rb") as f:
            pdf_bytes = f.read()

    # Simplified extraction prompt for single document processing
    GEMINI_PROMPT = """
You are a deterministic clinical laboratory data extraction engine for a Patient Labs Dashboard.

========================
MISSION
========================

Extract structured lab result data from the provided SINGLE lab report document.
Scope: Analyze THIS document only and extract the most recent values.

For EVERY biomarker listed below, extract:
- The most recent value with its unit, date, status, reference range, and source context.

========================
TARGET BIOMARKERS WITH STANDARD UNITS
========================

TUMOR MARKERS:
- CEA (Carcinoembryonic Antigen) → Standard unit: ng/mL
- NSE (Neuron-Specific Enolase) → Standard unit: ng/mL
- proGRP (Pro-Gastrin-Releasing Peptide) → Standard unit: pg/mL
- CYFRA 21-1 (Cytokeratin 19 Fragment) → Standard unit: ng/mL

COMPLETE BLOOD COUNT (CBC):
- WBC (White Blood Cell Count) → Standard unit: 10^3/μL (also written as K/μL, Thousand/μL)
- Hemoglobin (Hgb) → Standard unit: g/dL
- Platelets → Standard unit: 10^3/μL (also written as K/μL, Thousand/μL)
- ANC (Absolute Neutrophil Count) → Standard unit: 10^3/μL (also written as K/μL, Thousand/μL)
  * If missing, use 'Segs#', 'Polys, Abs', or 'Neutrophils, Absolute'

METABOLIC PANEL:
- Creatinine → Standard unit: mg/dL
- ALT (Alanine Aminotransferase) → Standard unit: U/L
- AST (Aspartate Aminotransferase) → Standard unit: U/L
- Total Bilirubin → Standard unit: mg/dL
  * CRITICAL: Also appears as "Total Bili", "Bilirubin", "Bili", "T. Bili", "T Bili", "Bilirubin Total", "Bilirubin, Total"

========================
CRITICAL EXTRACTION RULES
========================

1. DATE RULE (MANDATORY)
   - For the date field, use the report date (the date of the lab report document itself)
   - The report date is typically found at the top of the document as "Date:", "Report Date:", "Lab Date:", "Collection Date:", "Specimen Date:", or similar
   - Look for dates near patient information or document headers
   - CRITICAL: DO NOT use the patient's date of birth (DOB) - this is typically much older (e.g., from the 1940s-1980s)
   - DO NOT use admission dates or other non-lab dates
   - If multiple dates exist, prefer the most recent date that appears to be the report/lab date
   - Format: YYYY-MM-DD
   - IMPORTANT: All lab values from the same report should use the same report date

2. VALUE EXTRACTION RULE
   - Extract the MOST RECENT measurement for each biomarker from THIS document
   - Must include: value, unit, date, status, reference_range, source_context
   - If same test appears multiple times in this document, use the most recent resulted date

3. STATUS DETERMINATION
   - Normal: Within reference range
   - High: Above reference range
   - Low: Below reference range
   - Use 'Pending' if not yet available

4. UNIT STANDARDIZATION RULE (CRITICAL FOR CONSISTENCY)
   - ALWAYS convert values to the standard units specified above
   - Common conversions needed:
     * WBC/Platelets/ANC: If unit shows "10*3/uL", "10^3/uL", "10**3/uL", "K/uL", or "Thousand/uL" → Keep value AS-IS, output unit as "10^3/μL"
     * WBC/Platelets/ANC: If unit shows "/uL" or "cells/μL" (NO thousands indicator) → Divide value by 1000, output unit as "10^3/μL"
     * Hemoglobin: If unit shows "g/L" → Divide value by 10, output unit as "g/dL"
     * Hemoglobin: If unit shows "mg/dL" → Divide value by 1000, output unit as "g/dL"
     * Creatinine: If unit shows "μmol/L" or "umol/L" → Divide value by 88.4, output unit as "mg/dL"
     * Total Bilirubin: If unit shows "μmol/L" or "umol/L" → Divide value by 17.1, output unit as "mg/dL"
     * Tumor markers: If unit differs from standard → Convert to standard unit
   - CRITICAL: Recognize "10*3" (asterisk), "10^3" (caret), "10**3" (double asterisk) all mean 10³ (thousands)
   - If value is already in standard unit, keep it unchanged
   - Round converted values to 2 decimal places
   - Preserve all digits for values already in standard units

5. NULL POLICY
   - If value is missing or unclear, set to null
   - If biomarker is not found in this report, still include it with null values
   - DO NOT guess or infer missing information

6. SOURCE CONTEXT RULE (CRITICAL FOR PRIORITIZATION)
   - Include document type and location in the source_context field
   - Document type MUST be one of these (in priority order):
     * 'LAB_REPORT' - Official laboratory result reports (HIGHEST PRIORITY)
     * 'LAB_PANEL' - Lab panel summaries with resulted dates
     * 'LAB_SUMMARY' - Lab value summaries
     * 'MD_NOTE' - Lab values mentioned in physician notes (LOWEST PRIORITY)
   - Format: '<DOCUMENT_TYPE> - <location details>'
   - Examples:
     * 'LAB_REPORT - Page 1 CBC Panel'
     * 'LAB_PANEL - Page 2 Comprehensive Metabolic Panel'
     * 'MD_NOTE - Progress Note mentioning recent labs'
   - This prioritization helps when multiple measurements exist for the same date

7. BIOMARKER NAME VARIATIONS RULE (CRITICAL)
   - Total Bilirubin may appear as: "Total Bili", "Total Bilirubin", "Bilirubin", "Bili", "T. Bili", "T Bili", "Bilirubin Total", "Bilirubin, Total", "TBIL"
   - When you find ANY of these variations (especially "Total Bili"), extract it as "Total Bilirubin" in the output schema
   - ANC may appear as: "ANC", "Absolute Neutrophil Count", "Segs#", "Polys, Abs", "Neutrophils, Absolute"
   - Always map variations to the standardized names in the output schema
   - Case-insensitive matching should be applied to all variations

========================
OUTPUT SCHEMA (STRICT)
========================

IMPORTANT: All values MUST be converted to standard units as specified above.

{
  "tumor_markers": {
    "CEA": {
      "value": <float or "Pending" or null> (converted to standard unit if needed),
      "unit": "ng/mL" (MUST be standard unit),
      "date": "YYYY-MM-DD",
      "status": "<Normal|High|Low|Pending>",
      "reference_range": "<string>",
      "source_context": "<string>"
    },
    "NSE": { <same structure> },
    "proGRP": { <same structure> },
    "CYFRA_21_1": { <same structure> }
  },
  "complete_blood_count": {
    "WBC": { <same structure> },
    "Hemoglobin": { <same structure> },
    "Platelets": { <same structure> },
    "ANC": { <same structure> }
  },
  "metabolic_panel": {
    "Creatinine": { <same structure> },
    "ALT": { <same structure> },
    "AST": { <same structure> },
    "Total Bilirubin": { <same structure> }
  },
  "clinical_interpretation": [
    "<Summary of abnormal findings from this document>",
    "Rules applied:",
    "- Anemia: Hemoglobin <13.5 (M) or <12.0 (F)",
    "- Hepatic dysfunction: ALT or AST >40 U/L",
    "- Neutropenia: ANC <1.5 K/uL",
    "- Include other significant abnormalities found"
  ]
}

========================
CLINICAL INTERPRETATION
========================

Provide a summary including:
- Anemia status: Hemoglobin <13.5 g/dL (Male) or <12.0 g/dL (Female)
- Hepatic function: ALT/AST >40 U/L indicates elevation
- Neutropenia: ANC <1.5 K/uL
- Any tumor marker elevations
- Any other clinically significant abnormalities

========================
UNIT CONVERSION EXAMPLES
========================

Example 1: WBC shows "44.52" with unit "10*3/uL" in report
→ Extract: value = 44.52, unit = "10^3/μL" (NO conversion needed, asterisk means already in thousands)

Example 2: WBC shows "6850" with unit "/μL" in report
→ Extract: value = 6.85, unit = "10^3/μL" (CONVERTED: 6850 ÷ 1000 = 6.85)

Example 3: Hemoglobin shows "112" with unit "g/L" in report
→ Extract: value = 11.2, unit = "g/dL" (CONVERTED: 112 ÷ 10 = 11.2)

Example 4: Creatinine shows "88" with unit "μmol/L" in report
→ Extract: value = 1.0, unit = "mg/dL" (CONVERTED: 88 ÷ 88.4 ≈ 1.0)

Example 5: Platelets shows "185 K/uL" in report
→ Extract: value = 185, unit = "10^3/μL" (NO conversion needed, K means thousands)

========================
FINAL VALIDATION
========================

Before returning output:
- Ensure ALL target biomarkers are present in the output (even if null)
- Ensure dates are in YYYY-MM-DD format
- Ensure all values are in STANDARD UNITS (converted if necessary)
- Ensure unit strings match the standard formats exactly (e.g., "10^3/μL" not "10*3/uL")
- Ensure schema consistency with all required fields

========================
OUTPUT FORMAT
========================

Return VALID JSON ONLY.
No explanations.
No markdown code blocks.
No commentary.
Just the JSON object following the schema above.
"""

    logger.info("🤖 Generating extraction with Vertex AI Gemini...")

    # Initialize the model
    model = GenerativeModel("gemini-2.5-pro")

    # Wrap PDF bytes in Part object
    doc_part = Part.from_data(data=pdf_bytes, mime_type="application/pdf")

    # Make API request
    try:
        response = model.generate_content(
            [doc_part, GEMINI_PROMPT],
            generation_config={
                "temperature": 0,
                "top_p": 1
            }
        )
        logger.info("✅ Gemini extraction complete")
    except Exception as e:
        logger.error(f"❌ API request failed: {e}")
        raise

    # Parse JSON response
    try:
        # Extract text from the response
        response_text = response.text.strip()
        logger.info(f"📄 Extracted response text ({len(response_text)} chars)")

        # Use regex to extract JSON from markdown code blocks
        # Pattern matches: ```json ... ``` or ``` ... ```
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, response_text)

        if match:
            # Extract JSON from code block
            response_text = match.group(1).strip()
            logger.info("🧹 Cleaned markdown code blocks from response using regex")
        else:
            # No code blocks found, use as is
            response_text = response_text.strip()
            logger.info("ℹ️  No markdown code blocks found, using response as is")

        # Parse JSON
        extracted_data = json.loads(response_text)
        logger.info("✅ JSON parsed successfully")
        return extracted_data

    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(f"❌ Failed to parse Gemini response: {e}")
        logger.error(f"Raw response text (first 500 chars): {response_text[:500] if 'response_text' in locals() else 'N/A'}")

        # Save the raw response for debugging
        error_file = f"gemini_error_response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(error_file, "w") as f:
            f.write("="*80 + "\n")
            f.write("GEMINI RAW RESPONSE\n")
            f.write("="*80 + "\n\n")
            f.write(str(response))
        logger.error(f"💾 Saved raw response to: {error_file}")
        raise

def extract_lab_info(pdf_url=None, pdf_bytes=None, return_raw=False, use_gemini=True):
    """
    Extract and process lab information from PDF.

    Args:
        pdf_url: URL to the PDF containing lab reports (optional if pdf_bytes provided)
        pdf_bytes: PDF content as bytes (optional if pdf_url provided)
        return_raw: If True, returns raw unprocessed data. If False (default), returns UI-ready data.
        use_gemini: If True (default), uses Gemini pipeline. If False, uses legacy llmresponsedetailed (requires pdf_url).

    Returns:
        Processed lab data ready for UI consumption (or raw data if return_raw=True)
    """
    if pdf_bytes is None and pdf_url is None:
        raise ValueError("Either pdf_url or pdf_bytes must be provided")

    log_extraction_start(logger, "Lab Tab", pdf_url or f"PDF bytes ({len(pdf_bytes)} bytes)")
    logger.info("🔄 Extracting full patient lab trends...")

    if use_gemini:
        # Gemini pipeline - use bytes directly or fetch from URL
        logger.info("🤖 Using Gemini pipeline")
        if pdf_bytes is not None:
            logger.info(f"📄 Using provided PDF bytes ({len(pdf_bytes)} bytes)")
            raw_data = extract_with_gemini(pdf_bytes)
        else:
            logger.info(f"📥 Downloading PDF from URL: {pdf_url}")

            # Handle Google Drive URLs
            if "drive.google.com" in pdf_url:
                match = re.search(r'/file/d/([^/]+)', pdf_url)
                if match:
                    file_id = match.group(1)
                    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                else:
                    raise ValueError("Could not extract file ID from Google Drive URL")
            else:
                download_url = pdf_url

            response = requests.get(download_url, allow_redirects=True)
            response.raise_for_status()
            pdf_bytes = response.content
            logger.info(f"✅ Downloaded {len(pdf_bytes)} bytes")
            raw_data = extract_with_gemini(pdf_bytes)
    else:
        # Legacy pipeline using llmresponsedetailed (requires URL)
        if pdf_url is None:
            raise ValueError("pdf_url is required when use_gemini=False")
        logger.info("📝 Using legacy llmresponsedetailed pipeline")
        raw_data = llmresponsedetailed(
            pdf_url,
            extraction_instructions=extracted_instructions,
            description=description,
            config = {
            "start_page": 1,
            "end_page": 30,
            "batch_size": 1,
            "enable_batch_processing": True,
            "model": "gpt-5"
            }
        )

    log_extraction_output(logger, "Lab Raw Data", raw_data)

    if return_raw:
        return raw_data

    # Postprocess the data for UI (without AI refinement - done at consolidated level)
    logger.info("🔄 Postprocessing lab data for UI...")
    processed_data = process_lab_data_for_ui(raw_data, use_ai_refinement=False)

    log_extraction_output(logger, "Lab Processed Data", processed_data)
    log_extraction_complete(logger, "Lab Tab", processed_data.keys() if isinstance(processed_data, dict) else None)

    return processed_data

if __name__ == "__main__":
    import json

    pdf_url = "https://drive.google.com/file/d/1mmQC5a-REJ6ON_KTF0O9Qb2M_FKRmTQ9/view"
    lab_info = extract_lab_info(pdf_url)

    # Pretty print the processed data
    print("\n" + "="*80)
    print("PROCESSED LAB DATA FOR UI")
    print("="*80)
    print(json.dumps(lab_info, indent=2))

    # Optionally save to file
    # with open("processed_lab_data.json", "w") as f:
    #     json.dump(lab_info, f, indent=2)