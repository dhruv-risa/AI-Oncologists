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
    "Analyze the radiology reports to populate the 'RECIST Measurements', 'Impression', and 'Additional Findings' sections. "

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

    "- Dates: Identify the label/date for both baselines (e.g., 'March 2023' and 'January 2025'). "

    "SECTION 3: ADDITIONAL FINDINGS "
    "- Extract any other clinically relevant findings beyond the impression and target lesions. "
    "- This includes: new lesions not tracked as targets, changes in non-target lesions, incidental findings, "
    "  anatomical changes (pleural effusions, ascites, lymphadenopathy), or any other significant observations. "
    "- Present as an array of distinct findings (similar to impression format). "
    "- Examples: ['New small right pleural effusion', 'Stable hepatic metastases in segments 6 and 7', "
    "  'No significant change in mediastinal or hilar lymphadenopathy']"
    "- Only extract the top 3-5 most clinically relevant additional findings to avoid overload."
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
    },

    "additional_findings": "Array of strings - Each clinically relevant finding beyond impression and target lesions as a separate item. Include new non-target lesions, changes in non-target lesions, incidental findings, anatomical changes (pleural effusions, ascites, lymphadenopathy), and other significant observations. (e.g., ['New small right pleural effusion', 'Stable hepatic metastases in segments 6 and 7', 'No significant change in mediastinal or hilar lymphadenopathy'])"
}


def extract_radiology_summary_with_gemini_api(pdf_input):
    """
    Extract radiology report summary using Vertex AI SDK.

    Args:
        pdf_input: Either bytes (PDF content), local path to PDF file, or Google Drive URL

    Returns:
        Dictionary containing extracted radiology summary data
    """
    logger.info("🔄 Extracting radiology summary using Vertex AI SDK...")

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

    # Create detailed prompt for radiology summary extraction
    EXTRACTION_PROMPT = f"""
You are an Expert Radiological Data Abstractor specialized in extracting structured radiology report data for oncology patient dashboards.

========================
YOUR MISSION
========================

{extracted_instructions_summary}

========================
OUTPUT SCHEMA (STRICT - MUST FOLLOW EXACTLY)
========================

You must return a JSON object that EXACTLY matches this structure:

{json.dumps(description_summary, indent=2)}

========================
DETAILED EXTRACTION RULES & EXAMPLES
========================

1. STUDY TYPE EXTRACTION
   Rule: Extract the specific imaging modality including contrast information and body region

   Examples:
   - "CT CHEST WITH CONTRAST" → "CT Chest with contrast"
   - "PET/CT WHOLE BODY" → "PET/CT Whole Body"
   - "MRI BRAIN WITHOUT AND WITH CONTRAST" → "MRI Brain without and with contrast"
   - "CHEST X-RAY, PA AND LATERAL" → "Chest X-Ray, PA and Lateral"

   Key Points:
   - Include contrast information (with contrast, without contrast)
   - Include body region (Chest, Abdomen, Brain, etc.)
   - Standardize capitalization (proper case, not all caps)

2. STUDY DATE EXTRACTION
   Rule: Extract the date when the current imaging study was performed

   Format: Use natural date format (e.g., "December 8, 2024" or "12/08/2024")

   Location: Look in:
   - Report header section
   - "Exam Date" or "Study Date" field
   - "Date of Service" field

   Examples:
   - "Exam Date: 12/08/2024" → "December 8, 2024"
   - "Study performed on: 08-Dec-2024" → "December 8, 2024"
   - "Date of Service: 2024-12-08" → "December 8, 2024"

3. OVERALL RESPONSE ASSESSMENT
   Rule: Extract the radiologist's overall assessment of disease status following RECIST criteria

   Standard Response Categories:
   - "Complete Response (CR)" - Complete disappearance of all target lesions
   - "Partial Response (PR)" - ≥30% decrease in sum of diameters of target lesions
   - "Stable Disease (SD)" - Neither sufficient shrinkage for PR nor increase for PD
   - "Progressive Disease (PD)" - ≥20% increase in sum of diameters or new lesions
   - "Mixed Response" - Some lesions responding while others progressing

   Examples:
   - "Overall assessment: Partial response to therapy" → "Partial Response (PR)"
   - "Interval decrease in tumor burden consistent with response" → "Partial Response (PR)"
   - "Stable disease compared to prior" → "Stable Disease (SD)"
   - "Progression of disease with new metastases" → "Progressive Disease (PD)"
   - "Impression: Interval improvement" → "Partial Response (PR)"

   Key Points:
   - Look in the "Impression" or "Conclusion" section
   - Map narrative descriptions to standard RECIST categories
   - Include the abbreviation in parentheses (PR, SD, PD, CR)
   - If no clear assessment, use "Not specified" (but try to infer from findings)

4. PRIOR COMPARISON DATE
   Rule: Extract the date of the specific prior imaging study used for comparison

   Location: Look for:
   - "Comparison" section in report header
   - "Prior study dated:" phrase
   - "Compared to [date]" in findings

   Examples:
   - "Comparison: CT Chest dated 09/10/2024" → "September 10, 2024"
   - "Prior study from 2024-09-10 for comparison" → "September 10, 2024"
   - "Compared to exam dated 10-Sep-2024" → "September 10, 2024"

   Special Cases:
   - If multiple prior studies mentioned, use the one explicitly stated as the comparison
   - If no prior comparison, use "No prior available" or "Baseline study"

========================
QUALITY CHECKS BEFORE SUBMISSION
========================

1. ✓ Study type includes modality, body region, and contrast details
2. ✓ Study date is in readable format (Month DD, YYYY or MM/DD/YYYY)
3. ✓ Overall response is mapped to RECIST category with abbreviation
4. ✓ Prior comparison date is in the same format as study date
5. ✓ All fields are populated (use "Not specified" for truly missing data)
6. ✓ No extraneous text or explanations in the values

========================
EDGE CASES
========================

- If this is a baseline/initial study: prior_comparison = "Baseline study"
- If overall response cannot be determined: overall_response = "Findings noted, see impression"
- If study type is complex: Include all relevant modalities (e.g., "PET/CT Chest, Abdomen, Pelvis")

========================
OUTPUT FORMAT
========================

Return VALID JSON ONLY.
No explanations outside the JSON.
No markdown code blocks (no ```)
No commentary or preamble.
Just the pure JSON object following the schema above.
"""

    logger.info("🤖 Requesting radiology summary extraction using Vertex AI SDK...")

    # Initialize model
    model = GenerativeModel("gemini-2.5-flash")

    # Wrap PDF bytes in Part object
    pdf_part = Part.from_data(data=pdf_bytes, mime_type="application/pdf")

    # Make API request
    try:
        response = model.generate_content(
            [pdf_part, EXTRACTION_PROMPT],
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

        extracted_data = json.loads(response_text)
        logger.info("✅ Radiology summary parsed successfully")
        return extracted_data

    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(f"❌ Failed to parse response: {e}")
        logger.error(f"Raw response text (first 500 chars): {response_text[:500] if 'response_text' in locals() else 'N/A'}")
        raise


def extract_radiology_imp_recist_with_gemini_api(pdf_input):
    """
    Extract radiology impression and RECIST measurements using Vertex AI SDK.

    Args:
        pdf_input: Either bytes (PDF content), local path to PDF file, or Google Drive URL

    Returns:
        Dictionary containing extracted impression and RECIST data
    """
    logger.info("🔄 Extracting radiology impression & RECIST using Vertex AI SDK...")

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

    # Create detailed prompt for impression and RECIST extraction
    EXTRACTION_PROMPT = f"""
You are an Expert Radiological Data Abstractor specialized in extracting structured RECIST measurements and clinical impressions from radiology reports for precision oncology dashboards.

========================
YOUR MISSION
========================

{extracted_instructions_imp_RECIST}

========================
OUTPUT SCHEMA (STRICT - MUST FOLLOW EXACTLY)
========================

You must return a JSON object that EXACTLY matches this structure:

{json.dumps(description_imp_RECIST, indent=2)}

========================
DETAILED EXTRACTION RULES & EXAMPLES
========================

1. IMPRESSION EXTRACTION
   Rule: Extract each distinct clinical finding from the Impression/Conclusion section as a separate array item

   Splitting Rules:
   - Split on periods (.) when they separate complete thoughts
   - Split on semicolons (;)
   - Split on numbered/bulleted lists
   - Keep related phrases together (don't split mid-sentence)

   Examples:

   Input: "Partial response to therapy. Decrease in size of primary RUL mass from 3.5 cm to 2.1 cm.
   New small right pleural effusion. Stable mediastinal lymphadenopathy."

   Output:
   [
     "Partial response to therapy",
     "Decrease in size of primary RUL mass from 3.5 cm to 2.1 cm",
     "New small right pleural effusion",
     "Stable mediastinal lymphadenopathy"
   ]

   Input: "1. Interval decrease in size of target lesions consistent with partial response.
   2. No new metastatic lesions identified.
   3. Recommend continued surveillance."

   Output:
   [
     "Interval decrease in size of target lesions consistent with partial response",
     "No new metastatic lesions identified",
     "Recommend continued surveillance"
   ]

   Key Points:
   - Remove numbering/bullets from the text
   - Keep each finding as a complete, readable statement
   - Preserve clinical terminology and measurements
   - Do NOT include other sections like "Clinical History" or "Technique"

2. RECIST MEASUREMENTS - DUAL BASELINE TRACKING

   CRITICAL CONCEPT: This is NOT a simple before/after comparison. You must track TWO different historical baselines:

   Baseline A - "Initial Diagnosis":
   - The state of disease at original diagnosis
   - Often labeled as "Post-surgery", "Baseline", "Initial scan", or a specific early date
   - Example: "March 2023 post-surgical baseline"

   Baseline B - "Current Treatment":
   - The state of disease when current therapy started
   - Often labeled as "Pre-treatment scan", "Treatment baseline", or recent date
   - Example: "January 2025 pre-immunotherapy"

   FOR EACH TARGET LESION:
   You must extract THREE measurements:
   1. Size at Initial Diagnosis baseline
   2. Size at Current Treatment baseline
   3. Current size (from this report)

   Then calculate TWO percentage changes:
   - % change from Initial Diagnosis to Current
   - % change from Current Treatment to Current

   EXAMPLE EXTRACTION WALKTHROUGH:

   Report Text:
   "RUL mass: Currently measures 2.1 cm.
   At initial diagnosis (March 2023 post-op), this measured 3.5 cm.
   At start of current immunotherapy (January 2025), this measured 3.2 cm.
   This represents 40% decrease from initial diagnosis and 34% decrease from treatment start."

   Extracted Lesion Object:
   {{
     "lesion_name": "RUL mass",
     "initial_diagnosis_data": {{
       "baseline_val": "3.5 cm",
       "change_percentage": "-40%"
     }},
     "current_treatment_data": {{
       "baseline_val": "3.2 cm",
       "change_percentage": "-34%"
     }}
   }}

3. LESION NAME STANDARDIZATION

   Use clear, anatomically precise names:
   - "RUL mass" (Right Upper Lobe mass)
   - "Liver segment 6 metastasis"
   - "Mediastinal lymph nodes"
   - "LUL nodule" (Left Upper Lobe nodule)

   Avoid vague names like "Lesion 1" unless that's the only identifier in the report

4. CALCULATING PERCENTAGE CHANGES

   Formula: ((Current - Baseline) / Baseline) × 100

   Examples:
   - Baseline 4.0 cm → Current 2.8 cm: ((2.8 - 4.0) / 4.0) × 100 = -30%
   - Baseline 2.5 cm → Current 3.2 cm: ((3.2 - 2.5) / 2.5) × 100 = +28%

   Formatting:
   - Include the sign (+ for increase, - for decrease)
   - Round to whole numbers or one decimal place
   - Examples: "-30%", "+28%", "-12.5%", "0%"

5. SUM OF DIAMETERS (SOD) ROW

   The "Sum" row aggregates all target lesions:

   Initial Diagnosis SOD: Sum of all lesions at initial baseline
   Current Treatment SOD: Sum of all lesions at treatment baseline
   Current SOD: Sum of all current measurements

   Example:
   If you have 3 lesions:
   - RUL mass: Initial 3.5 cm, Treatment 3.2 cm, Current 2.1 cm
   - LLL nodule: Initial 2.8 cm, Treatment 2.5 cm, Current 1.9 cm
   - Mediastinal LN: Initial 1.8 cm, Treatment 1.7 cm, Current 1.3 cm

   Sum Row:
   {{
     "lesion_name": "Sum",
     "initial_diagnosis_data": {{
       "baseline_val": "8.1 cm",        // 3.5 + 2.8 + 1.8
       "change_percentage": "-35%"       // ((5.3 - 8.1) / 8.1) × 100
     }},
     "current_treatment_data": {{
       "baseline_val": "7.4 cm",         // 3.2 + 2.5 + 1.7
       "change_percentage": "-28%"       // ((5.3 - 7.4) / 7.4) × 100
     }}
   }}

6. COLUMN HEADERS / BASELINE LABELS

   Extract clear labels for each baseline column:

   initial_diagnosis_label:
   - Should capture the timeframe and context
   - Examples:
     * "Initial Diagnosis March 2023"
     * "Post-Op Baseline May 2022"
     * "Original Scan 06/15/2023"

   current_treatment_label:
   - Should capture when current therapy started
   - Examples:
     * "Current Treatment January 2025"
     * "Pre-Immunotherapy 01/10/2025"
     * "Treatment Start December 2024"

7. ADDITIONAL FINDINGS EXTRACTION

   Rule: Extract other clinically relevant observations not covered in the impression or target lesion measurements as an array of distinct findings

   What to Include:
   - New lesions that are not being tracked as target lesions
   - Changes in non-target lesions (stable, increased, decreased)
   - Incidental findings (cysts, nodules, calcifications)
   - Anatomical changes: pleural effusions, pericardial effusions, ascites
   - Lymphadenopathy outside tracked nodes
   - Changes in normal organs (liver, spleen, kidneys)
   - Bone findings, soft tissue changes
   - Vascular findings
   - Post-treatment changes (radiation fibrosis, surgical changes)

   What to EXCLUDE:
   - Information already in the impression array
   - Measurements already in the RECIST table
   - Normal/unremarkable findings unless specifically compared to prior
   - Technical details about the scan itself

   Format:
   - Present as an array of distinct findings (similar to impression format)
   - Each finding should be a separate string in the array
   - Use proper medical terminology
   - Include anatomical locations
   - Note if findings are new, stable, improved, or worsened
   - Keep each finding concise but complete

   Examples:

   Example 1:
   [
     "New small right pleural effusion",
     "Stable hepatic metastases in segments 6 and 7 measuring up to 1.2 cm",
     "No significant interval change in mediastinal or hilar lymphadenopathy",
     "Small amount of pericardial effusion, unchanged from prior"
   ]

   Example 2:
   [
     "Multiple subcentimeter pulmonary nodules in bilateral lower lobes, stable",
     "Left adrenal nodule measuring 1.8 cm, slightly increased from 1.5 cm on prior study",
     "No new bone lesions",
     "Stable lytic lesion in L3 vertebral body"
   ]

   Example 3:
   [
     "Interval development of small bilateral pleural effusions",
     "Stable appearance of post-surgical changes in the right upper lobe",
     "No pathologic lymphadenopathy in the abdomen or pelvis",
     "Unchanged appearance of benign-appearing renal cysts bilaterally"
   ]

   Special Cases:
   - If no additional findings: Return ["No significant additional findings beyond those noted in impression"]
   - If baseline study: Return ["Baseline study - see impression for complete findings"]
   - Be specific with anatomical locations and measurements when available
   - Split compound findings into separate array items for clarity

========================
HANDLING EDGE CASES
========================

1. Only ONE baseline mentioned:
   - If report only compares to one prior scan
   - Use that scan for BOTH baselines (duplicate the data)
   - Label both appropriately or use "Baseline" for initial and "Prior scan" for current

2. No baseline measurements:
   - If this is the first scan (baseline study)
   - Return empty lesions array: []
   - Set labels to: "Baseline study - no prior comparison"

3. New lesions appearing:
   - If a lesion appears for the first time on current scan
   - Use "Not present" or "0 cm" for baseline values
   - Calculate percentage as "New lesion" instead of a number

4. Mixed units (cm vs mm):
   - Convert all to the same unit (preferably cm)
   - Example: "15 mm" → "1.5 cm"

5. Non-target lesions:
   - Focus ONLY on target lesions (measurable lesions tracked over time) in the RECIST table
   - Include non-target lesions and their changes in the additional_findings section

========================
QUALITY CHECKS BEFORE SUBMISSION
========================

1. ✓ Impression is an array of distinct strings (not a single paragraph)
2. ✓ Each lesion has both initial_diagnosis_data and current_treatment_data
3. ✓ All percentage changes include sign (+ or -)
4. ✓ Sum row calculations are mathematically correct
5. ✓ Column headers are descriptive with dates/context
6. ✓ Lesion names are anatomically clear
7. ✓ All measurements have units (cm)
8. ✓ No extraneous text or explanations in the data
9. ✓ Additional findings is an array of distinct strings (similar to impression)
10. ✓ Additional findings does not duplicate impression or RECIST data

========================
OUTPUT FORMAT
========================

Return VALID JSON ONLY.
No explanations outside the JSON.
No markdown code blocks (no ```)
No commentary or preamble.
Just the pure JSON object following the schema above.
"""

    logger.info("🤖 Requesting radiology impression & RECIST extraction using Vertex AI SDK...")

    # Initialize model
    model = GenerativeModel("gemini-2.5-flash")

    # Wrap PDF bytes in Part object
    pdf_part = Part.from_data(data=pdf_bytes, mime_type="application/pdf")

    # Make API request
    try:
        response = model.generate_content(
            [pdf_part, EXTRACTION_PROMPT],
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

        extracted_data = json.loads(response_text)
        logger.info("✅ Radiology impression & RECIST parsed successfully")
        return extracted_data

    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(f"❌ Failed to parse response: {e}")
        logger.error(f"Raw response text (first 500 chars): {response_text[:500] if 'response_text' in locals() else 'N/A'}")
        raise


def radiology_info(pdf_url_only_report, use_gemini_api=False):
    """
    Extract radiology information from a radiology report PDF.

    This function supports two extraction approaches controlled by the use_gemini_api toggle:

    1. Legacy approach (use_gemini_api=False): Uses llmresponsedetailed with GPT-5
    2. Vertex AI SDK approach (use_gemini_api=True): Uses Vertex AI SDK with Gemini 2.5 Flash

    Args:
        pdf_url_only_report (str): URL to the radiology report PDF (Google Drive URL or local path)
        use_gemini_api (bool): Toggle for extraction approach
            - False (default): Use legacy llmresponsedetailed approach with GPT-5
            - True: Use Vertex AI SDK with Gemini for extraction

    Returns:
        tuple: (patient_radiology_summary, patient_radiology_imp_RECIST)
            - patient_radiology_summary (dict): Extracted radiology summary including:
                - study_type (imaging modality)
                - study_date (date of current scan)
                - overall_response (RECIST response assessment)
                - prior_comparison (date of comparison scan)
            - patient_radiology_imp_RECIST (dict): Extracted impression and RECIST including:
                - impression (array of clinical findings)
                - recist_measurements (dual baseline RECIST tracking)
    """
    log_extraction_start(logger, "Radiology Tab - Summary", pdf_url_only_report)

    logger.info("="*80)
    logger.info("RADIOLOGY REPORT EXTRACTION")
    logger.info("="*80)

    # Toggle between extraction approaches
    if use_gemini_api:
        logger.info("🔧 Using Vertex AI SDK approach for extraction")

        # Extract Report Summary using Vertex AI SDK
        logger.info("🔄 Extracting radiology summary (1/2) via Vertex AI SDK...")
        patient_radiology_summary = extract_radiology_summary_with_gemini_api(pdf_url_only_report)
        log_extraction_output(logger, "Radiology Summary", patient_radiology_summary)
        log_extraction_complete(logger, "Radiology Summary", patient_radiology_summary.keys() if isinstance(patient_radiology_summary, dict) else None)

        # Extract Impression and RECIST using Vertex AI SDK
        logger.info("🔄 Extracting radiology impression & RECIST (2/2) via Vertex AI SDK...")
        patient_radiology_imp_RECIST = extract_radiology_imp_recist_with_gemini_api(pdf_url_only_report)
        log_extraction_output(logger, "Radiology Impression & RECIST", patient_radiology_imp_RECIST)
        log_extraction_complete(logger, "Radiology Impression & RECIST", patient_radiology_imp_RECIST.keys() if isinstance(patient_radiology_imp_RECIST, dict) else None)

    else:
        logger.info("🔧 Using legacy llmresponsedetailed approach (GPT-5) for extraction")

        config = {
            "start_page": 1,
            "end_page": 30,
            "batch_size": 3,
            "enable_batch_processing": True,
            "model": "gpt-5"
        }

        # Extract Report Summary (Header data) using legacy approach
        logger.info("🔄 Extracting radiology summary (1/2) via llmresponsedetailed...")
        patient_radiology_summary = llmresponsedetailed(
            pdf_url_only_report,
            extraction_instructions=extracted_instructions_summary,
            description=description_summary,
            config=config
        )
        log_extraction_output(logger, "Radiology Summary", patient_radiology_summary)
        log_extraction_complete(logger, "Radiology Summary", patient_radiology_summary.keys() if isinstance(patient_radiology_summary, dict) else None)

        # Extract Impression and Complex RECIST Table using legacy approach
        logger.info("🔄 Extracting radiology impression & RECIST (2/2) via llmresponsedetailed...")
        patient_radiology_imp_RECIST = llmresponsedetailed(
            pdf_url_only_report,
            extraction_instructions=extracted_instructions_imp_RECIST,
            description=description_imp_RECIST,
            config=config
        )
        log_extraction_output(logger, "Radiology Impression & RECIST", patient_radiology_imp_RECIST)
        log_extraction_complete(logger, "Radiology Impression & RECIST", patient_radiology_imp_RECIST.keys() if isinstance(patient_radiology_imp_RECIST, dict) else None)

    logger.info("="*80)
    logger.info("✅ RADIOLOGY EXTRACTION COMPLETE")
    logger.info("="*80)

    return patient_radiology_summary, patient_radiology_imp_RECIST



def extract_radiology_details_from_report(radiology_url, use_gemini_api=False):
    """
    Extract radiology details from a single report.

    This function extracts:
    1. Basic report summary (study type, date, overall response) from radiology report
    2. Impression and RECIST measurements from radiology report

    Args:
        radiology_url (str): Google Drive URL for the radiology report
        use_gemini_api (bool): Toggle for extraction approach
            - False (default): Use legacy llmresponsedetailed approach with GPT-5
            - True: Use Vertex AI SDK with Gemini for extraction

    Returns:
        Tuple of (radiology_summary, radiology_imp_RECIST)
    """
    return radiology_info(
        pdf_url_only_report=radiology_url,
        use_gemini_api=use_gemini_api
    )


if __name__ == "__main__":
    # Example usage
    pdf_url = "https://drive.google.com/file/d/1quio3qBXAFFOmoIQV3D8-q2Ye66VvfUK/view?usp=drive_link"

    # Using Vertex AI SDK approach (recommended)
    print("="*80)
    print("EXTRACTING WITH VERTEX AI SDK")
    print("="*80)
    summary, imp_recist = radiology_info(
        pdf_url_only_report=pdf_url,
        use_gemini_api=True
    )
    print("Radiology Summary:")
    print(json.dumps(summary, indent=2))
    print("\nRadiology Impression & RECIST:")
    print(json.dumps(imp_recist, indent=2))

    # Using legacy approach (optional)
    # print("="*80)
    # print("EXTRACTING WITH LEGACY APPROACH")
    # print("="*80)
    # summary_legacy, imp_recist_legacy = radiology_info(
    #     pdf_url_only_report=pdf_url,
    #     use_gemini_api=False
    # )
    # print("Radiology Summary:")
    # print(json.dumps(summary_legacy, indent=2))
    # print("\nRadiology Impression & RECIST:")
    # print(json.dumps(imp_recist_legacy, indent=2))