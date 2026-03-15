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
import json
import re
import requests
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from datetime import datetime

# Add Backend to path for imports
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from Backend.Utils.Tabs.llmparser import llmresponsedetailed
from Backend.Utils.logger_config import setup_logger

# Setup logger
logger = setup_logger(__name__)

# Initialize Vertex AI
vertexai.init(project=os.environ.get("VERTEX_PROJECT", "rapids-platform"), location="us-central1")


def extract_comorbidities_with_gemini(pdf_input):
    """
    Extract comorbidities data using Vertex AI Gemini SDK.

    Args:
        pdf_input: Either bytes (PDF content), URL (string), or local path to the PDF file

    Returns:
        Dictionary containing extracted comorbidities data
    """
    # Handle bytes, URLs, and file path inputs
    if isinstance(pdf_input, bytes):
        logger.info(f"📤 Using PDF bytes ({len(pdf_input)} bytes)")
        pdf_bytes = pdf_input
    elif isinstance(pdf_input, str):
        if pdf_input.startswith("/api/documents/"):
            # Handle Firebase Storage paths
            logger.info(f"📥 Downloading PDF from Firebase Storage: {pdf_input}")
            try:
                from Backend.storage_uploader import download_pdf_bytes_from_url
            except ModuleNotFoundError:
                from storage_uploader import download_pdf_bytes_from_url
            pdf_bytes = download_pdf_bytes_from_url(pdf_input)
            logger.info(f"✅ Downloaded {len(pdf_bytes)} bytes")
        elif "drive.google.com" in pdf_input:
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
        elif pdf_input.startswith(('http://', 'https://')):
            # Handle other URLs
            logger.info(f"📤 Downloading PDF from URL: {pdf_input[:80]}...")
            response = requests.get(pdf_input)
            if response.status_code != 200:
                raise ValueError(f"Failed to download PDF from URL. Status code: {response.status_code}")
            pdf_bytes = response.content
            logger.info(f"📤 Downloaded {len(pdf_bytes):,} bytes ({len(pdf_bytes)/1024:.1f} KB)")
        else:
            # Assume it's a local file path
            logger.info(f"📤 Reading PDF from path: {pdf_input}")
            with open(pdf_input, "rb") as f:
                pdf_bytes = f.read()
    else:
        raise ValueError(f"Invalid pdf_input type: {type(pdf_input)}. Expected bytes or string.")

    GEMINI_PROMPT = """
You are a clinical data extraction engine specializing in patient comorbidities and performance status.

========================
MISSION
========================

Extract structured information regarding the patient's medical comorbidities and functional status from the provided clinical document.

For each comorbidity:
- Identify specific condition names
- Extract their severity or stage
- Document relevant clinical history details
- List any associated medications

Additionally, extract the ECOG Performance Status score and its description.

========================
TARGET DATA
========================

COMORBIDITIES:
For each condition, extract:
- condition_name: Name of the medical condition or chronic disease (e.g., Hypertension). DO NOT include cancer-related diagnoses.
- severity: Severity level if explicitly stated (e.g., Mild, Moderate, Stage III)
- clinical_details: Brief relevant history or context (e.g., "History of partial gastrectomy for ulcer disease")
- associated_medications: List of medications linked to this specific condition if identifiable

ECOG PERFORMANCE STATUS:
- Extract ONLY the numerical ECOG score (0-4) as an integer
- Do NOT extract the description

========================
CRITICAL EXTRACTION RULES
========================

1. COMORBIDITY RULE
   - Only extract NON-CANCER medical conditions
   - Include chronic diseases, past surgeries, and ongoing conditions
   - Do not include cancer diagnoses or cancer-related complications

2. SEVERITY RULE
   - Extract severity only if explicitly stated in the document
   - Use null if not mentioned
   - Examples: "Mild", "Moderate", "Severe", "Stage III", "Class II"

3. MEDICATION LINKING
   - Only associate medications if clearly linked to the condition in the document
   - Do not guess or infer medication-condition relationships
   - Use an empty list if no medications are explicitly linked

4. ECOG EXTRACTION
   - Extract ONLY the numerical score (0, 1, 2, 3, or 4) as an integer
   - DO NOT include the word "ECOG" or any description text
   - Examples: If document says "ECOG 1", extract: 1 (just the number)
   - If document says "ECOG performance status is 2", extract: 2 (just the number)
   - Use null if ECOG status is not mentioned

5. NULL POLICY
   - If a field is missing or unclear, set to null
   - Do NOT guess or infer missing information
   - It's better to have null than incorrect data

========================
OUTPUT SCHEMA (STRICT)
========================

{
  "comorbidities": [
    {
      "condition_name": "<string>",
      "severity": "<string or null>",
      "clinical_details": "<string or null>",
      "associated_medications": ["<string>", "<string>"] or []
    }
  ],
  "ecog_performance_status": {
    "score": <integer 0-4 or null>,
    "description": "<string or null>"
  }
}

========================
EXAMPLES
========================

Example 1:
Input: "Patient has history of hypertension (controlled), type 2 diabetes mellitus on metformin. ECOG performance status is 1."
Output:
{
  "comorbidities": [
    {
      "condition_name": "Hypertension",
      "severity": "Controlled",
      "clinical_details": null,
      "associated_medications": []
    },
    {
      "condition_name": "Type 2 Diabetes Mellitus",
      "severity": null,
      "clinical_details": null,
      "associated_medications": ["Metformin"]
    }
  ],
  "ecog_performance_status": {
    "score": 1,
    "description": "Restricted in physically strenuous activity but ambulatory and able to carry out work of a light or sedentary nature"
  }
}

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
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, response_text)

        if match:
            response_text = match.group(1).strip()
            logger.info("🧹 Cleaned markdown code blocks from response using regex")
        else:
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
        error_file = f"gemini_error_comorbidities_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(error_file, "w") as f:
            f.write("="*80 + "\n")
            f.write("GEMINI RAW RESPONSE - COMORBIDITIES\n")
            f.write("="*80 + "\n\n")
            f.write(str(response))
        logger.error(f"💾 Saved raw response to: {error_file}")
        raise


def extract_comorbidities_status(pdf_bytes=None, pdf_url=None, use_gemini=True):
    """
    Extract comorbidities and performance status from clinical notes.

    Args:
        pdf_bytes: PDF content as bytes (primary input, already fetched MD notes)
        pdf_url: URL to the PDF (optional, used if pdf_bytes not provided)
        use_gemini: If True (default), uses Vertex AI Gemini. If False, uses Risa's LLM parser.

    Returns:
        Dictionary containing comorbidities and ECOG performance status
    """
    if pdf_bytes is None and pdf_url is None:
        raise ValueError("Either pdf_bytes or pdf_url must be provided")

    logger.info("🔄 Extracting comorbidities and performance status...")

    if use_gemini:
        # Gemini pipeline - use bytes directly or fetch from URL
        logger.info("🤖 Using Vertex AI Gemini pipeline")
        if pdf_bytes is not None:
            logger.info(f"📄 Using provided PDF bytes ({len(pdf_bytes)} bytes)")
            comorbidities_data = extract_comorbidities_with_gemini(pdf_bytes)
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
            comorbidities_data = extract_comorbidities_with_gemini(pdf_bytes)
    else:
        # Legacy pipeline using Risa's LLM parser (requires URL)
        if pdf_url is None:
            raise ValueError("pdf_url is required when use_gemini=False")
        logger.info("📝 Using Risa's LLM parser pipeline")

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

    logger.info("✅ Comorbidities extraction complete")
    return comorbidities_data
