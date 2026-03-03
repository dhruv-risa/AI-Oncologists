import sys
import os
import json
import re
import requests
import base64
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from Backend.Utils.Tabs.llmparser import llmresponsedetailed
from datetime import datetime
from io import BytesIO

# Add Backend to path for imports
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from Backend.Utils.Tabs.lab_postprocessor import process_lab_data_for_ui
from Backend.Utils.logger_config import setup_logger, log_extraction_start, log_extraction_complete, log_extraction_output

# Setup logger
logger = setup_logger(__name__)

# Initialize Vertex AI
vertexai.init(project="prior-auth-portal-dev", location="us-central1")

extracted_instructions = (
    "Extract structured lab result data for a 'Patient Labs Dashboard' from the provided lab report. "
    "Scope: Analyze the SINGLE document provided and extract current values only. "

    "EXTRACTION SOURCE RULE: "
    "- Extract data from actual laboratory result reports, lab panels, and test result documents. "
    "- ALSO extract lab values documented in MD notes, physician notes, or progress notes if they contain specific lab values with numbers. "
    "- Focus on extracting ALL available lab values with test names, values, units, and reference ranges. "

    "MISSION: For EVERY biomarker listed below, extract: "
    "- The MOST RECENT value from this document with its unit, date, status, and reference range. "
    "- Use the 'Lab Resulted' or 'Resulted' date (NOT specimen collection date) when available. "

    "Targets: "
    "- TUMOR MARKERS: CEA, NSE, proGRP, CYFRA 21-1. "
    "- CBC: WBC, Hemoglobin, Platelets, ANC, MCV, RDW, Lymphocytes, Monocytes. "
    "- METABOLIC/CHEMISTRY: Sodium, Potassium, Chloride, CO2/Bicarbonate, Calcium, Phosphorus, Magnesium, "
    "  Glucose, BUN, Creatinine, eGFR, Total Protein, Albumin, Uric Acid. "
    "- LIVER FUNCTION: ALT, AST, Total Bilirubin, Alkaline Phosphatase, LDH. "
    "- COAGULATION: INR, PT, aPTT. "
    "- THYROID: TSH, Free T4. "
    "- DIABETES: HbA1c/Hemoglobin A1c. "
    "- IRON STUDIES: Iron, Ferritin, TIBC. "

    "CLINICAL INTERPRETATION: "
    "Summarize abnormalities: Anemia (Hgb <13.5 M / <12.0 F), Hepatic (ALT/AST >40), Neutropenia (ANC <1.5), "
    "Renal (Cr >1.2 or eGFR <60), Electrolyte abnormalities, Coagulopathy (INR >1.5), Thyroid dysfunction."
)

def biomarker_schema():
    return {
        "value": "Float or 'Pending' or null - The most recent value for this biomarker in this document",
        "unit": "String - The unit of measurement (e.g., 'g/dL', 'Thousand/uL')",
        "date": "YYYY-MM-DD - Date of the measurement (use Lab Resulted date)",
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
        "ANC": biomarker_schema(),
        "MCV": biomarker_schema(),
        "RDW": biomarker_schema(),
        "Lymphocytes": biomarker_schema(),
        "Monocytes": biomarker_schema()
    },
    "metabolic_panel": {
        "Sodium": biomarker_schema(),
        "Potassium": biomarker_schema(),
        "Chloride": biomarker_schema(),
        "CO2": biomarker_schema(),
        "Calcium": biomarker_schema(),
        "Phosphorus": biomarker_schema(),
        "Magnesium": biomarker_schema(),
        "Glucose": biomarker_schema(),
        "BUN": biomarker_schema(),
        "Creatinine": biomarker_schema(),
        "eGFR": biomarker_schema(),
        "Total_Protein": biomarker_schema(),
        "Albumin": biomarker_schema(),
        "Uric_Acid": biomarker_schema()
    },
    "liver_function": {
        "ALT": biomarker_schema(),
        "AST": biomarker_schema(),
        "Total_Bilirubin": biomarker_schema(),
        "Alkaline_Phosphatase": biomarker_schema(),
        "LDH": biomarker_schema()
    },
    "coagulation": {
        "INR": biomarker_schema(),
        "PT": biomarker_schema(),
        "aPTT": biomarker_schema()
    },
    "thyroid": {
        "TSH": biomarker_schema(),
        "Free_T4": biomarker_schema()
    },
    "diabetes": {
        "HbA1c": biomarker_schema()
    },
    "iron_studies": {
        "Iron": biomarker_schema(),
        "Ferritin": biomarker_schema(),
        "TIBC": biomarker_schema()
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

Extract structured lab result data from the provided document.
Scope: Analyze THIS document only and extract the most recent values.
IMPORTANT: Extract lab values from ALL sources in this document including formal lab reports,
lab panels, AND lab values documented within MD notes or progress notes.

For EVERY biomarker listed below, extract:
- The most recent value with its unit, date, status, reference range, and source context.

========================
TARGET BIOMARKERS
========================

TUMOR MARKERS:
- CEA (Carcinoembryonic Antigen)
- NSE (Neuron-Specific Enolase)
- proGRP (Pro-Gastrin-Releasing Peptide)
- CYFRA 21-1 (Cytokeratin 19 Fragment)

COMPLETE BLOOD COUNT (CBC):
- WBC (White Blood Cell Count)
- Hemoglobin (Hgb)
- Platelets
- ANC (Absolute Neutrophil Count) - if missing, use 'Segs#' or 'Polys, Abs'
- MCV (Mean Corpuscular Volume)
- RDW (Red Cell Distribution Width)
- Lymphocytes (Absolute or %)
- Monocytes (Absolute or %)

METABOLIC PANEL / CHEMISTRY:
- Sodium (Na)
- Potassium (K)
- Chloride (Cl)
- CO2 / Bicarbonate (HCO3)
- Calcium (Ca)
- Phosphorus
- Magnesium (Mg)
- Glucose
- BUN (Blood Urea Nitrogen)
- Creatinine (Cr)
- eGFR (Estimated Glomerular Filtration Rate)
- Total Protein
- Albumin
- Uric Acid

LIVER FUNCTION:
- ALT (Alanine Aminotransferase / SGPT)
- AST (Aspartate Aminotransferase / SGOT)
- Total Bilirubin (also look for "Bilirubin", "Bili", "T. Bili", "Total Bili")
- Alkaline Phosphatase (Alk Phos, ALP)
- LDH (Lactate Dehydrogenase)

COAGULATION:
- INR (International Normalized Ratio)
- PT (Prothrombin Time)
- aPTT (Activated Partial Thromboplastin Time)

THYROID:
- TSH (Thyroid Stimulating Hormone)
- Free T4 (Free Thyroxine)

DIABETES:
- HbA1c (Hemoglobin A1c, Glycated Hemoglobin)

IRON STUDIES:
- Iron (Serum Iron)
- Ferritin
- TIBC (Total Iron Binding Capacity)

========================
CRITICAL EXTRACTION RULES
========================

1. DATE RULE (MANDATORY)
   - Use ONLY "Lab Resulted" or "Resulted" dates for lab values
   - Ignore specimen collection dates unless no resulted date exists
   - Date format: YYYY-MM-DD

2. VALUE EXTRACTION RULE
   - Extract the MOST RECENT measurement for each biomarker from THIS document
   - Must include: value, unit, date, status, reference_range, source_context
   - If same test appears multiple times in this document, use the most recent resulted date

3. STATUS DETERMINATION
   - Normal: Within reference range
   - High: Above reference range
   - Low: Below reference range
   - Use 'Pending' if not yet available

4. VALUE FIDELITY RULE
   - Preserve numeric values EXACTLY as shown
   - Preserve original units (e.g., 'g/dL', 'K/uL', 'ng/mL', 'U/L', 'mg/dL')
   - DO NOT round, normalize, or convert

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

7. BIOMARKER NAME VARIATIONS RULE
   - Total Bilirubin: "Total Bilirubin", "Bilirubin", "Bili", "T. Bili", "Total Bili", "Bilirubin, Total"
   - ANC: "ANC", "Absolute Neutrophil Count", "Segs#", "Polys, Abs", "Neutrophils, Absolute"
   - Alkaline Phosphatase: "Alk Phos", "ALP", "Alkaline Phosphatase"
   - eGFR: "eGFR", "GFR", "Estimated GFR", "Est. GFR"
   - HbA1c: "HbA1c", "Hemoglobin A1c", "A1c", "Glycated Hemoglobin", "Glycohemoglobin"
   - TSH: "TSH", "Thyroid Stimulating Hormone"
   - Free T4: "Free T4", "FT4", "Free Thyroxine"
   - LDH: "LDH", "Lactate Dehydrogenase", "LD"
   - Always map variations to the standardized names in the output schema

========================
OUTPUT SCHEMA (STRICT)
========================

{
  "tumor_markers": {
    "CEA": { "value": <float or null>, "unit": "<string>", "date": "YYYY-MM-DD", "status": "<Normal|High|Low|Pending>", "reference_range": "<string>", "source_context": "<string>" },
    "NSE": { <same structure> },
    "proGRP": { <same structure> },
    "CYFRA_21_1": { <same structure> }
  },
  "complete_blood_count": {
    "WBC": { <same structure> },
    "Hemoglobin": { <same structure> },
    "Platelets": { <same structure> },
    "ANC": { <same structure> },
    "MCV": { <same structure> },
    "RDW": { <same structure> },
    "Lymphocytes": { <same structure> },
    "Monocytes": { <same structure> }
  },
  "metabolic_panel": {
    "Sodium": { <same structure> },
    "Potassium": { <same structure> },
    "Chloride": { <same structure> },
    "CO2": { <same structure> },
    "Calcium": { <same structure> },
    "Phosphorus": { <same structure> },
    "Magnesium": { <same structure> },
    "Glucose": { <same structure> },
    "BUN": { <same structure> },
    "Creatinine": { <same structure> },
    "eGFR": { <same structure> },
    "Total_Protein": { <same structure> },
    "Albumin": { <same structure> },
    "Uric_Acid": { <same structure> }
  },
  "liver_function": {
    "ALT": { <same structure> },
    "AST": { <same structure> },
    "Total_Bilirubin": { <same structure> },
    "Alkaline_Phosphatase": { <same structure> },
    "LDH": { <same structure> }
  },
  "coagulation": {
    "INR": { <same structure> },
    "PT": { <same structure> },
    "aPTT": { <same structure> }
  },
  "thyroid": {
    "TSH": { <same structure> },
    "Free_T4": { <same structure> }
  },
  "diabetes": {
    "HbA1c": { <same structure> }
  },
  "iron_studies": {
    "Iron": { <same structure> },
    "Ferritin": { <same structure> },
    "TIBC": { <same structure> }
  },
  "clinical_interpretation": [
    "<Summary of ALL abnormal findings from this document>",
    "Include: Anemia, Hepatic dysfunction, Neutropenia, Renal impairment, Electrolyte abnormalities, Coagulopathy, Thyroid dysfunction, Iron deficiency"
  ]
}

========================
CLINICAL INTERPRETATION
========================

Provide a summary including ALL of:
- Anemia status: Hemoglobin <13.5 g/dL (Male) or <12.0 g/dL (Female)
- Hepatic function: ALT/AST >40 U/L, Alk Phos elevation, Bilirubin elevation
- Neutropenia: ANC <1.5 K/uL
- Renal function: Creatinine >1.2 mg/dL, eGFR <60
- Electrolyte abnormalities: Na, K, Ca, Mg outside normal ranges
- Coagulopathy: INR >1.5
- Thyroid: TSH outside 0.4-4.0 range
- Iron deficiency: Low ferritin or iron
- Any tumor marker elevations
- Any other clinically significant abnormalities

========================
FINAL VALIDATION
========================

Before returning output:
- Ensure ALL categories and biomarkers are present in the output (even if null)
- Ensure dates are in YYYY-MM-DD format
- Ensure all numeric values are preserved exactly as shown
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
    model = GenerativeModel("gemini-2.5-flash")

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

    # Postprocess the data for UI
    logger.info("🔄 Postprocessing lab data for UI...")
    processed_data = process_lab_data_for_ui(raw_data)

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