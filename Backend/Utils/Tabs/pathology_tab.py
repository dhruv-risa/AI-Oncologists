
## Source for pathology header = The selected Pathology Report
import sys
import os
import json
import re
import requests
import vertexai
from vertexai.generative_models import GenerativeModel, Part


# Add Backend to path for imports
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from Backend.Utils.Tabs.llmparser import llmresponsedetailed
from Backend.Utils.logger_config import setup_logger, log_extraction_start, log_extraction_complete, log_extraction_output

# Setup logger
logger = setup_logger(__name__)

# Initialize Vertex AI
vertexai.init(project="prior-auth-portal-dev", location="us-central1")

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


def classify_pathology_report_with_gemini(pdf_input):
    """
    Classify a pathology report as either 'GENOMIC_ALTERATIONS' or 'TYPICAL_PATHOLOGY' using Vertex AI Gemini.

    Args:
        pdf_input: Either bytes (PDF content), local path to PDF file, or Google Drive URL

    Returns:
        Dictionary with classification results:
        {
            "category": "GENOMIC_ALTERATIONS" or "TYPICAL_PATHOLOGY",
            "confidence": "high", "medium", or "low",
            "reasoning": "Brief explanation",
            "key_indicators": ["list", "of", "indicators"]
        }
    """
    logger.info("🔍 Starting pathology report classification with Vertex AI Gemini...")

    # Handle different input types and get PDF bytes
    if isinstance(pdf_input, bytes):
        logger.info(f"📤 Using PDF bytes ({len(pdf_input)} bytes)")
        pdf_bytes = pdf_input
    elif isinstance(pdf_input, str):
        if "drive.google.com" in pdf_input:
            # Handle Google Drive URLs
            logger.info(f"📥 Downloading PDF from Google Drive: {pdf_input}")
            match = re.search(r'/file/d/([^/]+)', pdf_input)
            if match:
                file_id = match.group(1)
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            else:
                raise ValueError("Could not extract file ID from Google Drive URL")

            response = requests.get(download_url, allow_redirects=True)
            response.raise_for_status()
            pdf_bytes = response.content
            logger.info(f"✅ Downloaded {len(pdf_bytes)} bytes")
        else:
            # Assume it's a local file path
            logger.info(f"📤 Reading PDF from local path: {pdf_input}")
            with open(pdf_input, "rb") as f:
                pdf_bytes = f.read()
    else:
        raise ValueError("pdf_input must be bytes, a local file path, or a Google Drive URL")

    logger.info(f"✅ PDF ready for processing ({len(pdf_bytes)} bytes)")

    # Classification prompt
    CLASSIFICATION_PROMPT = """
You are an Expert Medical Report Classifier. Your task is to classify this pathology report into one of three categories.

========================
CLASSIFICATION CATEGORIES
========================

1. GENOMIC_ALTERATIONS
   Reports primarily focused on:
   - Next-Generation Sequencing (NGS) results
   - Molecular profiling or genetic testing panels
   - Gene mutations, variants, alterations, or copy number variations
   - Companion diagnostic tests for targeted therapies
   - Tumor mutational burden (TMB) or microsatellite instability (MSI) testing
   - Examples: 'FoundationOne CDx', 'Guardant360', 'Tempus xT', 'Caris MI', any NGS panel report
   - Reports that list multiple genes and their mutation status

2. TYPICAL_PATHOLOGY
   Standard pathology reports focused on:
   - Histopathological examination of tissue/cytology specimens
   - Surgical pathology reports (resections, biopsies, excisions)
   - Cytology reports (FNA, fluid analysis, Pap smears)
   - Immunohistochemistry (IHC) staining results as part of diagnostic workup (NOT genomic testing)
   - Morphological descriptions, tumor grading, staging, margins
   - Flow cytometry for cell surface markers (NOT genomic alterations)
   - Examples: Surgical pathology reports, biopsy reports, cytology reports, resection specimens

3. NO_TEST_PERFORMED
   Reports where no pathology or genomic testing was conducted:
   - Reports explicitly stating "test not performed", "specimen inadequate", or "insufficient tissue"
   - Administrative documents, scheduling notes, or requisition forms without results
   - Cancelled tests or incomplete reports
   - Reports with only clinical information but no test results
   - Examples: "Biopsy cancelled", "Insufficient sample", "Test not performed due to..."

========================
CLASSIFICATION RULES
========================

- If the report is primarily about genomic/molecular testing results with gene panels → GENOMIC_ALTERATIONS
- If the report is primarily about tissue examination, morphology, and histological diagnosis → TYPICAL_PATHOLOGY
- If the report explicitly states no test was performed, insufficient sample, or cancelled → NO_TEST_PERFORMED
- When in doubt, consider the MAIN PURPOSE of the report:
  * Does it describe tissue under microscope? → TYPICAL_PATHOLOGY
  * Does it list gene mutations from sequencing? → GENOMIC_ALTERATIONS
  * Does it state test was not performed or sample inadequate? → NO_TEST_PERFORMED
- IHC markers (like PD-L1, HER2) in a standard pathology report = TYPICAL_PATHOLOGY
  (Diagnostic IHC is different from genomic sequencing)
- Reports with sections like "Specimen", "Gross Description", "Microscopic Examination" → TYPICAL_PATHOLOGY
- Reports with sections like "Genomic Findings", "Variants Detected", "Gene Panel Results" → GENOMIC_ALTERATIONS
- Reports stating "test not performed", "insufficient tissue", "cancelled", "inadequate sample" → NO_TEST_PERFORMED

========================
OUTPUT FORMAT
========================

Return VALID JSON ONLY with this exact structure:
{
  "category": "GENOMIC_ALTERATIONS" or "TYPICAL_PATHOLOGY" or "NO_TEST_PERFORMED",
  "confidence": "high" or "medium" or "low",
  "reasoning": "1-2 sentence explanation for why you classified it this way",
  "key_indicators": ["2-4 key phrases from the report that support this classification"]
}

No explanations outside the JSON.
No markdown code blocks.
No commentary.
Just the JSON object.
"""

    logger.info("🤖 Requesting classification from Vertex AI Gemini...")

    # Initialize model
    model = GenerativeModel("gemini-2.5-flash")

    # Wrap PDF bytes in Part object
    doc_part = Part.from_data(data=pdf_bytes, mime_type="application/pdf")

    # Make API request
    try:
        response = model.generate_content(
            [doc_part, CLASSIFICATION_PROMPT],
            generation_config={
                "temperature": 0,
                "top_p": 1
            }
        )
        logger.info("✅ Gemini classification complete")
    except Exception as e:
        logger.error(f"❌ API request failed: {e}")
        raise

    # Parse JSON response
    try:
        # Extract text from the Vertex AI response
        response_text = response.text.strip()

        logger.info(f"📄 Extracted response text ({len(response_text)} chars)")

        # Clean markdown code blocks if present (handles both ``` and ''')
        # Try triple backticks first (with or without 'json' label)
        json_pattern_backticks = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern_backticks, response_text)

        if match:
            response_text = match.group(1).strip()
            logger.info("🧹 Cleaned markdown code blocks (backticks) from response")
        else:
            # Try triple single quotes
            json_pattern_quotes = r"'''(?:json)?\s*([\s\S]*?)\s*'''"
            match = re.search(json_pattern_quotes, response_text)
            if match:
                response_text = match.group(1).strip()
                logger.info("🧹 Cleaned markdown code blocks (single quotes) from response")
            else:
                response_text = response_text.strip()
                logger.info("ℹ️  No markdown code blocks found, using response as is")

        classification = json.loads(response_text)
        logger.info(f"📊 Classification Result: {classification['category']} (confidence: {classification['confidence']})")
        logger.info(f"💡 Reasoning: {classification['reasoning']}")

        return classification

    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error(f"❌ Failed to parse Gemini classification response: {e}")
        logger.error(f"Raw response (first 500 chars): {response_text[:500]}")
        raise


def extract_pathology_summary_with_gemini_api(pdf_input):
    """
    Extract pathology summary using Vertex AI Gemini.

    Args:
        pdf_input: Either bytes (PDF content), local path to PDF file, or Google Drive URL

    Returns:
        Dictionary containing extracted pathology summary data
    """
    logger.info("🔄 Extracting pathology summary using Vertex AI Gemini...")

    # Handle different input types and get PDF bytes
    if isinstance(pdf_input, bytes):
        logger.info(f"📤 Using PDF bytes ({len(pdf_input)} bytes)")
        pdf_bytes = pdf_input
    elif isinstance(pdf_input, str):
        if "drive.google.com" in pdf_input:
            # Handle Google Drive URLs
            logger.info(f"📥 Downloading PDF from Google Drive: {pdf_input}")
            match = re.search(r'/file/d/([^/]+)', pdf_input)
            if match:
                file_id = match.group(1)
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            else:
                raise ValueError("Could not extract file ID from Google Drive URL")

            response = requests.get(download_url, allow_redirects=True)
            response.raise_for_status()
            pdf_bytes = response.content
            logger.info(f"✅ Downloaded {len(pdf_bytes)} bytes")
        else:
            # Assume it's a local file path
            logger.info(f"📤 Reading PDF from local path: {pdf_input}")
            with open(pdf_input, "rb") as f:
                pdf_bytes = f.read()
    else:
        raise ValueError("pdf_input must be bytes, a local file path, or a Google Drive URL")

    logger.info(f"✅ PDF ready for processing ({len(pdf_bytes)} bytes)")

    # Create detailed prompt for pathology summary extraction
    EXTRACTION_PROMPT = f"""
You are an Expert Clinical Data Abstractor specialized in extracting structured pathology data for patient dashboards.

========================
YOUR MISSION
========================

{extracted_instructions}

========================
OUTPUT SCHEMA (STRICT - MUST FOLLOW EXACTLY)
========================

You must return a JSON object that EXACTLY matches this structure:

{json.dumps(description, indent=2)}

========================
DETAILED EXTRACTION RULES & EXAMPLES
========================

1. REPORT ID EXTRACTION
   Rule: Extract the primary Accession Number from the report header
   Examples:
   - "Accession #: FNHAM25-00235" → "FNHAM25-00235"
   - "Case Number: S23-12345" → "S23-12345"

2. ALERT BANNER CREATION
   Rule: Analyze the final diagnosis to determine severity and create appropriate alert
   Priority Hierarchy: Malignancy > Suspicious/Atypical > Benign

   Examples:
   - Malignant case:
     headline: "Invasive Carcinoma Detected"
     subtext: "High-grade features noted, urgent oncology referral"

   - Suspicious case:
     headline: "Atypical Cells Present"
     subtext: "Recommend molecular testing and close follow-up"

   - Benign case:
     headline: "Benign Findings"
     subtext: "Routine follow-up recommended"

3. DIAGNOSIS EXTRACTION
   Rule: Extract ONLY the FINAL DIAGNOSIS section. Exclude clinical history, gross description, and disclaimers

   Format: Clean, distinct bullet points

   Example Input:
   "FINAL DIAGNOSIS:
   A. Right upper lobe, lung, wedge resection:
      - Invasive adenocarcinoma, moderately differentiated
      - Tumor size: 2.5 cm
      - Margins negative for tumor
   B. Hilar lymph nodes (3): No evidence of malignancy"

   Example Output:
   [
     "Right upper lobe, lung, wedge resection: Invasive adenocarcinoma, moderately differentiated",
     "Tumor size: 2.5 cm",
     "Margins negative for tumor",
     "Hilar lymph nodes (3): No evidence of malignancy"
   ]

4. PROCEDURE CLASSIFICATION
   Rule: Classify strictly into TWO categories based on the procedure type

   Category 1: "Surgical Resection"
   Includes: Lobectomy, Pneumonectomy, Wedge resection, Mastectomy, Excision, Nephrectomy, etc.

   Category 2: "Biopsy/FNA"
   Includes: Core needle biopsy, Fine needle aspiration, Punch biopsy, Endoscopic biopsy, Fluid cytology

   Examples:
   - "Wedge resection, right lung" → "Surgical Resection"
   - "US guided fine needle aspiration" → "Biopsy/FNA"
   - "Core needle biopsy of breast" → "Biopsy/FNA"

5. ANATOMICAL SITE
   Rule: Extract the specific anatomical location with laterality

   Examples:
   - "Right upper lobe, lung" → "Upper Lobe, Right Lung"
   - "Left breast, upper outer quadrant" → "Left Breast, Upper Outer Quadrant"
   - "Right adrenal gland" → "Right Adrenal Gland"

6. DATE EXTRACTION (CRITICAL - ISO 8601 FORMAT)
   Rule: Use YYYY-MM-DD format strictly

   Biopsy_Date:
   - Priority 1: "Date of Collection" or "Date of Procedure"
   - Priority 2: "Date Received" (if collection date not available)

   Surgery_Date:
   - ONLY populate if procedure_category is "Surgical Resection"
   - If procedure is Biopsy/FNA, use "Not applicable"

   Examples:
   - "Date of Procedure: 01/15/2024" → "2024-01-15"
   - "Received: January 15, 2024" → "2024-01-15"

7. TUMOR GRADE
   Rule: Look for grade or differentiation terms

   Mapping:
   - "Well differentiated" → "Grade 1 (Well differentiated)"
   - "Moderately differentiated" → "Grade 2 (Moderately differentiated)"
   - "Poorly differentiated" → "Grade 3 (Poorly differentiated)"
   - "Grade 2/3" → "Grade 2-3"
   - If not found → "Not applicable"

8. MARGIN STATUS
   Rule: Required for Surgical Resections, indicate tumor involvement at surgical edges

   Examples:
   - "Margins negative for malignancy" → "Negative for malignancy"
   - "Focally positive at bronchial margin" → "Focally positive at bronchial margin"
   - For Biopsies → "Not applicable"

========================
QUALITY CHECKS BEFORE SUBMISSION
========================

1. ✓ All required fields populated (use "Not applicable" for missing, not null)
2. ✓ All dates in YYYY-MM-DD format
3. ✓ Diagnosis is a list of strings, not a single paragraph
4. ✓ procedure_category is exactly "Surgical Resection" OR "Biopsy/FNA"
5. ✓ Alert banner headline is 5 words or less
6. ✓ No clinical history or gross description in diagnosis
7. ✓ Surgery_date is "Not applicable" if procedure is not a resection

========================
OUTPUT FORMAT
========================

Return VALID JSON ONLY.
No explanations outside the JSON.
No markdown code blocks (no ```)
No commentary or preamble.
Just the pure JSON object following the schema above.
"""

    logger.info("🤖 Requesting pathology summary extraction from Vertex AI Gemini...")

    # Initialize model
    model = GenerativeModel("gemini-2.5-flash")

    # Wrap PDF bytes in Part object
    doc_part = Part.from_data(data=pdf_bytes, mime_type="application/pdf")

    # Make API request
    try:
        response = model.generate_content(
            [doc_part, EXTRACTION_PROMPT],
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
        # Extract text from the Vertex AI response
        response_text = response.text.strip()

        logger.info(f"📄 Extracted response text ({len(response_text)} chars)")

        # Clean markdown code blocks if present
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, response_text)

        if match:
            response_text = match.group(1).strip()
            logger.info("🧹 Cleaned markdown code blocks from response")
        else:
            response_text = response_text.strip()
            logger.info("ℹ  No markdown code blocks found, using response as is")

        # Parse JSON
        extracted_data = json.loads(response_text)
        logger.info("✅ Pathology summary parsed successfully")
        return extracted_data

    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error(f"❌ Failed to parse Gemini response: {e}")
        logger.error(f"Raw response (first 500 chars): {response_text[:500]}")
        raise


def extract_pathology_markers_with_gemini_api(pdf_input):
    """
    Extract pathology markers (IHC and morphology) using Vertex AI Gemini.

    Args:
        pdf_input: Either bytes (PDF content), local path to PDF file, or Google Drive URL

    Returns:
        Dictionary containing extracted pathology markers data
    """
    logger.info("🔄 Extracting pathology markers using Vertex AI Gemini...")

    # Handle different input types and get PDF bytes
    if isinstance(pdf_input, bytes):
        logger.info(f"📤 Using PDF bytes ({len(pdf_input)} bytes)")
        pdf_bytes = pdf_input
    elif isinstance(pdf_input, str):
        if "drive.google.com" in pdf_input:
            # Handle Google Drive URLs
            logger.info(f"📥 Downloading PDF from Google Drive: {pdf_input}")
            match = re.search(r'/file/d/([^/]+)', pdf_input)
            if match:
                file_id = match.group(1)
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            else:
                raise ValueError("Could not extract file ID from Google Drive URL")

            response = requests.get(download_url, allow_redirects=True)
            response.raise_for_status()
            pdf_bytes = response.content
            logger.info(f"✅ Downloaded {len(pdf_bytes)} bytes")
        else:
            # Assume it's a local file path
            logger.info(f"📤 Reading PDF from local path: {pdf_input}")
            with open(pdf_input, "rb") as f:
                pdf_bytes = f.read()
    else:
        raise ValueError("pdf_input must be bytes, a local file path, or a Google Drive URL")

    logger.info(f"✅ PDF ready for processing ({len(pdf_bytes)} bytes)")

    # Create detailed prompt for pathology markers extraction
    EXTRACTION_PROMPT = f"""
You are an Expert Pathologist specialized in extracting advanced morphologic features and immunohistochemistry (IHC) biomarkers from pathology reports for precision oncology dashboards.

========================
OUTPUT SCHEMA (STRICT - MUST FOLLOW EXACTLY)
========================

You must return a JSON object that EXACTLY matches this structure:

{json.dumps(description_hist_ihc, indent=2)}

========================
DETAILED EXTRACTION RULES & EXAMPLES
========================

1. MORPHOLOGY COLUMN - CONTEXT-DEPENDENT EXTRACTION

   A. FOR TISSUE SAMPLES (Resections/Core Biopsies):
      Focus: TISSUE ARCHITECTURE and HISTOLOGIC PATTERNS

      What to extract:
      - Growth patterns: Acinar, Solid, Papillary, Lepidic, Micropapillary, Cribriform
      - Invasion features: Lymphovascular invasion (LVI), Perineural invasion (PNI)
      - Necrosis: Present or absent, extent
      - Stromal reaction: Desmoplasia, inflammation
      - Cell arrangements: Glandular formation, nesting, trabecular
      Top 5 most relevant features only

      Examples:
      - "Predominant acinar pattern with focal solid areas"
      - "Lymphovascular invasion present"
      - "Extensive central necrosis"
      - "Desmoplastic stromal reaction"

   B. FOR CYTOLOGY/FNA SAMPLES:
      Focus: CELLULAR and NUCLEAR CHARACTERISTICS

      What to extract:
      - Nuclear features: Size, molding, chromatin pattern, nucleoli prominence
      - Cellular cohesion: Loosely cohesive vs tight clusters
      - Background: Necrosis, mucin, blood
      - Cell morphology: Pleomorphism, mitotic figures

      Examples:
      - "Cells show prominent nucleoli"
      - "Nuclear molding present"
      - "Loosely cohesive cell clusters"
      - "Necrotic background debris"
      - "High nuclear-to-cytoplasmic ratio"

   Title Assignment:
   - Tissue → "Histopathologic Features"
   - Cytology/FNA → "Cytopathologic Features"

2. IHC MARKERS - STRUCTURED EXTRACTION

   Critical Rule: SPLIT COMBINED MARKERS
   Example: "CK7 and TTF1 are positive" → Extract as TWO separate marker objects

   Marker Structure Requirements:
   - name: Use standardized marker names (TTF-1, not TTF1; PD-L1, not PDL1)
   - status_label: Must be EXACTLY one of: 'Positive', 'Negative', 'Equivocal', 'Focal'
   - details: Combine intensity + quantity (percentage)
   - raw_text: Exact phrase from report for verification

   Common Markers and Standardized Names:
   - TTF-1 (Thyroid Transcription Factor)
   - CK7, CK20 (Cytokeratins)
   - PD-L1 (Programmed Death-Ligand 1)
   - Ki-67 (Proliferation marker)
   - ALK, ROS1, EGFR (Driver markers)
   - p40, p63, Napsin A

   Status Determination:
   - "Positive" / "Strongly positive" / "Diffusely positive" → Positive
   - "Negative" / "Non-reactive" → Negative
   - "Focal positivity" / "Patchy" → Focal
   - "Equivocal" / "Indeterminate" → Equivocal

   Intensity & Quantity Examples:
   - "Strong nuclear staining in >80% of tumor cells" → "Strong intensity, >80%"
   - "Weak cytoplasmic positivity" → "Weak intensity"
   - "Moderate staining in 50-60%" → "Moderate intensity, 50-60%"
   - "Further details not mentioned" → "Further details not mentioned in the report"

   Full Examples:
   {{
     "name": "TTF-1",
     "status_label": "Positive",
     "details": "Strong nuclear staining, >90%",
     "raw_text": "TTF-1 shows strong nuclear positivity in >90% of tumor cells"
   }}

   {{
     "name": "PD-L1",
     "status_label": "Positive",
     "details": "Tumor Proportion Score (TPS) 60%",
     "raw_text": "PD-L1 (22C3) TPS 60%"
   }}

   {{
     "name": "ALK",
     "status_label": "Negative",
     "details": "No rearrangement detected",
     "raw_text": "ALK (D5F3): Negative for rearrangement"
   }}

3. INTERPRETATION KEYWORDS - DIAGNOSTIC SIGNATURE

   Purpose: Generate 3-5 concise tags representing the diagnostic essence

   Priority Order:
   1. Histologic Subtype (e.g., "Adenocarcinoma", "Squamous Cell", "Small Cell")
   2. Driver Status (e.g., "EGFR Mutant", "ALK+", "PD-L1 High")
   3. High-Risk Features (e.g., "High Grade", "LVI Present", "Poorly Differentiated")
   4. Molecular Signatures (e.g., "TTF-1+", "CK7+/CK20-")

   Character Limit: Maximum 25 characters per tag

   Examples:
   For Lung Adenocarcinoma with PD-L1 high:
   [
     "Adenocarcinoma",
     "PD-L1 >50%",
     "TTF-1 Positive",
     "Moderately Diff.",
     "LVI Present"
   ]

   For Triple-Negative Breast Cancer:
   [
     "Invasive Ductal Ca",
     "Triple Negative",
     "High Grade",
     "Ki-67 High"
   ]

========================
QUALITY CHECKS BEFORE SUBMISSION
========================

1. ✓ Morphology title matches specimen type (Histopathologic vs Cytopathologic)
2. ✓ Morphology items are short, distinct observations (not full sentences)
3. ✓ Combined IHC markers split into separate objects
4. ✓ All IHC status_label values are: Positive, Negative, Equivocal, or Focal
5. ✓ IHC raw_text provided for verification
6. ✓ Keywords are 3-5 tags, each ≤25 characters
7. ✓ Keywords prioritize diagnostic subtype and biomarkers

========================
SPECIAL HANDLING
========================

If report states "IHC not performed" or "Pending":
- Return empty markers array: []
- Note in morphology: "Immunohistochemistry pending" or "Not performed"

If only partial IHC available:
- Extract available markers only
- Do not infer or guess missing markers

========================
OUTPUT FORMAT
========================

Return VALID JSON ONLY.
No explanations outside the JSON.
No markdown code blocks (no ```)
No commentary or preamble.
Just the pure JSON object following the schema above.
"""

    logger.info("🤖 Requesting pathology markers extraction from Vertex AI Gemini...")

    # Initialize model
    model = GenerativeModel("gemini-2.5-flash")

    # Wrap PDF bytes in Part object
    doc_part = Part.from_data(data=pdf_bytes, mime_type="application/pdf")

    # Make API request
    try:
        response = model.generate_content(
            [doc_part, EXTRACTION_PROMPT],
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
        # Extract text from the Vertex AI response
        response_text = response.text.strip()

        logger.info(f"📄 Extracted response text ({len(response_text)} chars)")

        # Clean markdown code blocks if present
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, response_text)

        if match:
            response_text = match.group(1).strip()
            logger.info("🧹 Cleaned markdown code blocks from response")
        else:
            response_text = response_text.strip()
            logger.info("ℹ️  No markdown code blocks found, using response as is")

        # Parse JSON
        extracted_data = json.loads(response_text)
        logger.info("✅ Pathology markers parsed successfully")
        return extracted_data

    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error(f"❌ Failed to parse Gemini response: {e}")
        logger.error(f"Raw response (first 500 chars): {response_text[:500]}")
        raise


def pathology_info(pdf_url, use_gemini_api=False):
    """
    Extract pathology information from a pathology report PDF.

    This function supports two extraction approaches controlled by the use_gemini_api toggle:

    1. Legacy approach (use_gemini_api=False): Uses llmresponsedetailed with GPT-5
    2. Gemini REST API approach (use_gemini_api=True): Uses direct Gemini API calls

    Pipeline:
    1. Classify report type (GENOMIC_ALTERATIONS vs TYPICAL_PATHOLOGY)
    2. If GENOMIC_ALTERATIONS: Skip extraction, route to Genomic Tab
    3. If TYPICAL_PATHOLOGY: Extract summary and markers using selected approach

    Args:
        pdf_url (str): URL to the pathology report PDF (Google Drive URL or local path)
        use_gemini_api (bool): Toggle for extraction approach
            - False (default): Use legacy llmresponsedetailed approach with GPT-5
            - True: Use Gemini REST API for extraction

    Returns:
        tuple: (patient_pathology_summary, patient_pathology_markers)
            - patient_pathology_summary (dict): Extracted pathology summary including:
                - header (report_id, alert_banner)
                - diagnosis_section (full_diagnosis, procedure_category)
                - details (biopsy_site, dates, tumor_grade, margin_status)
            - patient_pathology_markers (dict): Extracted markers including:
                - morphology_column (histopathologic/cytopathologic features)
                - ihc_column (IHC markers with status and details)
                - keywords (diagnostic signature tags)

            For GENOMIC_ALTERATIONS reports:
                Returns (classification_info, None)
    """
    log_extraction_start(logger, "Pathology Tab - Summary", pdf_url)

    # Step 1: Classify the report using Gemini
    logger.info("="*80)
    logger.info("STEP 1: CLASSIFYING PATHOLOGY REPORT TYPE")
    logger.info("="*80)

    try:
        classification = classify_pathology_report_with_gemini(pdf_url)

        logger.info(f"📋 Report Type: {classification['category']}")
        logger.info(f"🎯 Confidence: {classification['confidence']}")
        logger.info(f"💭 Reasoning: {classification['reasoning']}")
        logger.info(f"🔑 Key Indicators: {', '.join(classification['key_indicators'])}")

    except Exception as e:
        logger.error(f"❌ Classification failed: {e}")
        logger.warning("⚠️  Defaulting to TYPICAL_PATHOLOGY classification")
        classification = {
            "category": "TYPICAL_PATHOLOGY",
            "confidence": "low",
            "reasoning": "Classification failed, defaulting to typical pathology",
            "key_indicators": []
        }

    # Step 2: Handle based on classification
    if classification['category'] == 'GENOMIC_ALTERATIONS':
        logger.info("="*80)
        logger.info("🧬 GENOMIC ALTERATIONS REPORT DETECTED")
        logger.info("="*80)
        logger.info("✅ This report will be stored for the Genomic Tab pipeline")
        logger.info("⏭️  Skipping typical pathology extraction")

        # Return classification info with a special marker for genomic reports
        result = {
            "report_type": "GENOMIC_ALTERATIONS",
            "classification": classification,
            "message": "This report contains genomic alterations data and should be processed by the Genomic Tab pipeline",
            "pdf_url": pdf_url
        }

        return result, None

    elif classification['category'] == 'NO_TEST_PERFORMED':
        logger.info("="*80)
        logger.info("⚠️  NO TEST PERFORMED DETECTED")
        logger.info("="*80)
        logger.info("ℹ️  This report indicates no test was performed")
        logger.info("⏭️  Skipping extraction")

        # Return classification info with a special marker
        result = {
            "report_type": "NO_TEST_PERFORMED",
            "classification": classification,
            "message": "This report indicates no test was performed or insufficient sample",
            "pdf_url": pdf_url
        }

        return result, None

    # Step 3: Proceed with typical pathology extraction
    logger.info("="*80)
    logger.info("STEP 2: EXTRACTING TYPICAL PATHOLOGY DATA")
    logger.info("="*80)
    logger.info("📊 This is a typical pathology report, proceeding with full extraction")

    # Toggle between extraction approaches
    if use_gemini_api:
        logger.info("🔧 Using Gemini REST API approach for extraction")

        # Extract using Gemini API
        logger.info("🔄 Extracting pathology summary (1/2) via Gemini API...")
        patient_pathology_summary = extract_pathology_summary_with_gemini_api(pdf_url)

        # Add classification metadata to the summary
        if isinstance(patient_pathology_summary, dict):
            patient_pathology_summary['report_type'] = 'TYPICAL_PATHOLOGY'
            patient_pathology_summary['classification'] = classification

        log_extraction_output(logger, "Pathology Summary", patient_pathology_summary)
        log_extraction_complete(logger, "Pathology Summary", patient_pathology_summary.keys() if isinstance(patient_pathology_summary, dict) else None)

        logger.info("🔄 Extracting pathology markers (2/2) via Gemini API...")
        patient_pathology_markers = extract_pathology_markers_with_gemini_api(pdf_url)
        log_extraction_output(logger, "Pathology Markers", patient_pathology_markers)
        log_extraction_complete(logger, "Pathology Markers", patient_pathology_markers.keys() if isinstance(patient_pathology_markers, dict) else None)

    else:
        logger.info("🔧 Using legacy llmresponsedetailed approach (GPT-5) for extraction")

        config = {
            "start_page": 1,
            "end_page": 30,
            "batch_size": 3,
            "enable_batch_processing": True,
            "model": "gpt-5"
        }

        logger.info("🔄 Extracting pathology summary (1/2) via llmresponsedetailed...")
        patient_pathology_summary = llmresponsedetailed(pdf_url, extraction_instructions= extracted_instructions, description=description, config=config)

        # Add classification metadata to the summary
        if isinstance(patient_pathology_summary, dict):
            patient_pathology_summary['report_type'] = 'TYPICAL_PATHOLOGY'
            patient_pathology_summary['classification'] = classification

        log_extraction_output(logger, "Pathology Summary", patient_pathology_summary)
        log_extraction_complete(logger, "Pathology Summary", patient_pathology_summary.keys() if isinstance(patient_pathology_summary, dict) else None)

        logger.info("🔄 Extracting pathology markers (2/2) via llmresponsedetailed...")
        patient_pathology_markers = llmresponsedetailed(pdf_url, extraction_instructions= extracted_instructions_hist_ihc, description=description_hist_ihc, config=config)
        log_extraction_output(logger, "Pathology Markers", patient_pathology_markers)
        log_extraction_complete(logger, "Pathology Markers", patient_pathology_markers.keys() if isinstance(patient_pathology_markers, dict) else None)

    logger.info("="*80)
    logger.info("✅ TYPICAL PATHOLOGY EXTRACTION COMPLETE")
    logger.info("="*80)

    return patient_pathology_summary, patient_pathology_markers


# if __name__ == "__main__":
#     pdf_url = "https://drive.google.com/file/d/1lM7ztKs6_M1wu6sqjPpEKXE_iKZZK4MB/view"
#     pathology_summary, pathology_markers = pathology_info(pdf_url)
#     print("PATHOLOGY SUMMARY:")
#     print(json.dumps(pathology_summary, indent=2))
#     print("\nPATHOLOGY MARKERS & FEATURES:")
#     print(json.dumps(pathology_markers, indent=2))

#     pdf_url_2="https://drive.google.com/file/d/19PA7sLq_MNuH8cTbbCpLNMN8Hnb1v_oU/view?usp=sharing"