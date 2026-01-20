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


## What all is to be extracted from the relevant documents for the diagnosis tab
"""1. Header Details (Patient Summary)
primary_diagnosis: Non-Small Cell Lung Cancer (NSCLC)
histologic_type: Adenocarcinoma
diagnosis_date: March 12, 2023
initial_tnm_stage: T2aN1M0 (Stage IIB)
current_tnm_stage: T2aN2M1a (Stage IVA)
metastatic_status: Yes - Active metastases
metastatic_sites: Contralateral lung, pleural nodules
recurrence_status: Progressive disease

2. Stage Evolution Timeline
timeline_event_date: March 2023, June 2024, Current Status
timeline_stage_group: Stage IIB, Stage IVA, Stage IVA
timeline_tnm_status: T2aN1M0, T2aN2M1a, Metastatic
timeline_description: Initial diagnosis after biopsy, Disease progression detected, Multiple metastatic sites

3. Disease Course Duration (Footer)
duration_since_diagnosis: 21 months since initial diagnosis
duration_since_progression: 6 months since progression to metastatic disease
"""


pdf_url = ""


def extract_diagnosis_header_with_gemini(pdf_input):
    """
    Extract diagnosis header data using Vertex AI Gemini SDK.

    Args:
        pdf_input: Either bytes (PDF content) or URL/path to the PDF file

    Returns:
        Dictionary containing extracted diagnosis header data
    """
    # Handle both bytes and file path/URL inputs
    if isinstance(pdf_input, bytes):
        logger.info(f"📤 Using PDF bytes ({len(pdf_input)} bytes)")
        pdf_bytes = pdf_input
    elif pdf_input.startswith("http"):
        # Handle Google Drive URLs
        logger.info(f"📥 Downloading PDF from URL: {pdf_input}")
        if "drive.google.com" in pdf_input:
            match = re.search(r'/file/d/([^/]+)', pdf_input)
            if match:
                file_id = match.group(1)
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            else:
                raise ValueError("Could not extract file ID from Google Drive URL")
        else:
            download_url = pdf_input

        response = requests.get(download_url, allow_redirects=True)
        response.raise_for_status()
        pdf_bytes = response.content
        logger.info(f"✅ Downloaded {len(pdf_bytes)} bytes")
    else:
        # Assume it's a file path
        logger.info(f"📤 Reading PDF from path: {pdf_input}")
        with open(pdf_input, "rb") as f:
            pdf_bytes = f.read()

    # REFINED INSTRUCTIONS
    # Build prompt from extraction instructions and description

    extraction_instruction = ("Extract comprehensive clinical summary data for the patient's primary cancer diagnosis from the medical records."
    "1. CANCER IDENTIFICATION: Identify the primary cancer type (e.g., Non-Small Cell Lung Cancer, Pleural Mesothelioma) AND the specific histologic subtype (e.g., Adenocarcinoma, Epithelioid, Sarcomatoid). "
    "Check ALL document sections for histology: Pathology reports, Biopsy results, Diagnosis section, Clinical notes. The histology may be embedded in the diagnosis text. "
    "Extract the diagnosis date."
    "2. INITIAL STAGING: Find the staging information documented at the time of INITIAL/FIRST diagnosis. This is the baseline staging when the cancer was first identified. Look for terms like 'at diagnosis', 'initial presentation', or the earliest mentioned staging in the timeline."
    "3. CURRENT STAGING: Find the MOST RECENT or CURRENT staging information. This reflects the latest disease status. Look for terms like 'current', 'most recent', 'latest', 'now shows', 'restaging', 'progression', or dates closest to the document date. "
    "IMPORTANT: If no recent staging is explicitly mentioned (no restaging, no progression noted, no new TNM documented), this likely means the staging has NOT changed from initial diagnosis. In this case, use the same values from initial_staging for current_staging."
    "4. STAGING FORMAT - CRITICAL RULES:"
    " - TNM field: Extract ONLY the TNM classification (e.g., 'T2a N1 M0', 'T2aN1M0', 'T4N3M1c'). "
    "   Include all components (T, N, M) with their modifiers (prefixes like c/p/y and suffixes like letters/numbers). "
    "   ABSOLUTELY NEVER use the word 'Stage' in the TNM field. TNM is separate from stage."
    " - AJCC Stage field: Extract the full AJCC stage designation and it MUST start with 'Stage' (e.g., 'Stage IIB', 'Stage IVA', 'Stage 4', 'Stage IIIA'). "
    "   Include stage type prefix if mentioned (e.g., 'Pathologic Stage IIIA', 'Clinical Stage IB'). "
    "   The word 'Stage' is MANDATORY in this field."
    "5. DISEASE STATUS: Extract metastatic status (whether cancer has spread), specific metastatic sites (organs/locations), and recurrence/disease progression status."
    "6. KEY RULES:"
    " - If only one staging is documented in the record, use it for both initial_staging and current_staging."
    " - If no recent/current staging is mentioned and there's no documentation of progression or restaging, assume no change occurred and copy initial_staging to current_staging."
    " - If the document mentions 'upstaging', 'downstaging', 'progression', or 'restaging', ensure these changes are reflected in current_staging with the new TNM/stage values."
    " - Return null for any field not explicitly stated in the document."
    " - Do not infer or calculate values."
    "- If some data is not available then mention that the data is not available and do not hallucinate."
    ""
    "CRITICAL FORMATTING ENFORCEMENT:"
    "- TNM fields: NEVER EVER include 'Stage' - only T, N, M components"
    "- AJCC stage fields: ALWAYS start with 'Stage'"
    "Return as a JSON object matching the schema below.")



    description = {
    "primary_diagnosis": "The formal clinical name of the primary cancer. This should be the main cancer type being treated. Examples: 'Non-Small Cell Lung Cancer', 'Pleural Mesothelioma', 'Breast Carcinoma', 'Colorectal Adenocarcinoma'. Look in: Problem List, Diagnosis section, ICD-10 codes, Assessment section, or explicit diagnostic statements in clinical notes.",
    "histologic_type": "The specific microscopic cell type or histologic subtype documented in the medical record. This can come from pathology report, biopsy, or clinical diagnosis. Examples: 'Adenocarcinoma', 'Squamous cell carcinoma', 'Epithelioid', 'Sarcomatoid', 'Biphasic', 'Small cell', 'Large cell', 'Ductal carcinoma', 'Invasive lobular'. If the histology is embedded in the primary diagnosis (e.g., 'Epithelioid Pleural Mesothelioma'), extract just the histologic subtype ('Epithelioid'). Look in: Pathology section, Biopsy results, Diagnosis section, Clinical notes. Return null ONLY if absolutely no histologic information exists in the document.",
    "diagnosis_date": "The exact date when the cancer was first diagnosed in ISO format YYYY-MM-DD (e.g., '2023-03-15'). Look for phrases like 'diagnosed on', 'initial diagnosis date', or earliest mention of cancer detection.",
    "initial_staging": {
    "tnm": "CRITICAL: TNM classification ONLY - this field must NEVER contain the word 'Stage'. This is the T-N-M tumor staging classification at initial/first diagnosis. Format examples: 'T2a N1 M0', 'T2aN1M0', 'pT1c pN2 cM0', 'cT3 cN2 cM1a', 'T4 N3 M1c'. Include prefixes (c=clinical, p=pathologic, y=post-therapy) and all modifiers. The TNM field describes Tumor size (T), Node involvement (N), and Metastasis status (M). DO NOT put stage groups like 'Stage IV' or 'Stage IIB' here - those go in ajcc_stage field. If staging evolved from initial diagnosis, this should capture the EARLIEST TNM mentioned. Return null if no TNM is documented.",
    "ajcc_stage": "CRITICAL: AJCC stage group ONLY - this field must ALWAYS contain the word 'Stage'. Format examples: 'Stage IIB', 'Stage IIIA', 'Pathologic Stage IB', 'Clinical Stage IVA', 'Stage IV'. Include the stage type prefix (Clinical/Pathologic) if documented. This is the baseline stage when cancer was first found. DO NOT put TNM classifications like 'T2 N1 M0' here - those go in the tnm field."
    },
    "current_staging": {
    "tnm": "CRITICAL: TNM classification ONLY - this field must NEVER contain the word 'Stage'. This is the MOST RECENT T-N-M tumor staging classification. Format examples: 'T4 N3 M1c', 'cT2 cN1 cM1b', 'ypT0 ypN0 cM0', 'T2a N1 M0'. This should reflect the latest disease extent documented in the record with Tumor size (T), Node involvement (N), and Metastasis status (M). Look for most recent imaging, pathology, or clinical assessment. DO NOT put stage groups like 'Stage IV' or 'Stage IIA' here - those go in ajcc_stage field. Return null if no TNM is documented.",
    "ajcc_stage": "CRITICAL: AJCC stage group ONLY - this field must ALWAYS contain the word 'Stage'. This is the MOST RECENT stage group. Format examples: 'Stage IVB', 'Stage IIA', 'Clinical Stage IVA', 'Pathologic Stage IIIB', 'Stage IV'. This is the current or latest stage reflecting current disease status. If disease progressed or responded to treatment, this should show the updated stage. DO NOT put TNM classifications like 'T4 N3 M1c' here - those go in the tnm field."
    },
    "metastatic_status": "Clear statement of metastatic spread. Examples: 'Yes - Active metastases', 'No metastatic disease', 'Metastatic', 'Limited stage', 'Extensive stage', 'M0 - No distant metastasis'. This indicates if cancer has spread beyond the primary site.",
    "metastatic_sites": "Array of specific anatomical sites where metastases are present. Examples: ['Brain', 'Liver', 'Lung'], ['Bone', 'Lymph nodes'], ['Contralateral lung', 'Pleura']. Only include locations explicitly documented as metastatic. Return empty array if no metastases.",
    "recurrence_status": "Current disease behavior or progression state. Examples: 'Initial diagnosis - no prior cancer history', 'Progressive disease', 'Stable disease', 'Recurrent disease', 'Complete response', 'Partial response', 'Local recurrence', 'Distant recurrence'. This describes the disease trajectory."
    }
    GEMINI_PROMPT = f"""
    {extraction_instruction}

    OUTPUT SCHEMA (STRICT JSON):
    {json.dumps(description, indent=2)}

    CRITICAL FORMATTING VALIDATION RULES - YOU MUST FOLLOW THESE:
    1. TNM fields (initial_staging.tnm, current_staging.tnm): NEVER EVER include the word 'Stage'
       - Example of CORRECT format: "T2a N1 M0", "T4N3M1c"
       - Example of WRONG format: "Stage T2a N1 M0", "Stage IVA"
    2. AJCC Stage fields (initial_staging.ajcc_stage, current_staging.ajcc_stage): MUST ALWAYS start with 'Stage'
       - Example of CORRECT format: "Stage IVA", "Stage 4", "Stage IIB"
       - Example of WRONG format: "IVA", "4", "IIB"
    3. Before outputting JSON, verify each staging field follows these rules
    4. Return valid JSON only.
    """

    logger.info("🤖 Generating diagnosis header extraction with Vertex AI Gemini...")

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
        logger.info("✅ Gemini diagnosis header extraction complete")
    except Exception as e:
        logger.error(f"❌ API request failed: {e}")
        raise

    # Parse JSON response
    try:
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

        extracted_data = json.loads(response_text)
        logger.info("✅ JSON parsed successfully")
        return extracted_data

    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(f"❌ Failed to parse Gemini response: {e}")
        logger.error(f"Raw response text (first 500 chars): {response_text[:500] if 'response_text' in locals() else 'N/A'}")
        raise


def extract_diagnosis_evolution_with_gemini(pdf_input):
    """
    Extract diagnosis evolution timeline data using Vertex AI Gemini SDK.

    Args:
        pdf_input: Either bytes (PDF content) or URL/path to the PDF file

    Returns:
        Dictionary containing extracted diagnosis evolution timeline data
    """
    # Handle both bytes and file path/URL inputs
    if isinstance(pdf_input, bytes):
        logger.info(f"📤 Using PDF bytes ({len(pdf_input)} bytes)")
        pdf_bytes = pdf_input
    elif pdf_input.startswith("http"):
        logger.info(f"📥 Downloading PDF from URL: {pdf_input}")
        if "drive.google.com" in pdf_input:
            match = re.search(r'/file/d/([^/]+)', pdf_input)
            if match:
                file_id = match.group(1)
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            else:
                raise ValueError("Could not extract file ID from Google Drive URL")
        else:
            download_url = pdf_input

        response = requests.get(download_url, allow_redirects=True)
        response.raise_for_status()
        pdf_bytes = response.content
        logger.info(f"✅ Downloaded {len(pdf_bytes)} bytes")
    else:
        logger.info(f"📤 Reading PDF from path: {pdf_input}")
        with open(pdf_input, "rb") as f:
            pdf_bytes = f.read()

    extraction_instruction = """
    Extract a Treatment and Stage Evolution Timeline for the patient.

    Create a new timeline entry ONLY when there is a major oncologic transition, including:
    1. Initial cancer diagnosis
    2. Objective disease progression that is a change in recurrence status explicitly mentioned in the document
    3. Explicitly documented AJCC stage or TNM change
    4. Major anti-cancer treatment strategy change, including start, stop, switch, or hold of chemotherapy, immunotherapy, targeted therapy, cancer-directed surgery, or cancer-directed radiation therapy

    Do NOT create timeline entries for routine follow-ups, supportive care, symptom management, pain medications, steroids, labs, vitals, or dose adjustments without a change in oncologic intent.

    FOR EACH TIMELINE ENTRY, YOU MUST EXTRACT THE FOLLOWING REQUIRED FIELDS:

    1. DATE: Extract the date or timeframe when this oncologic phase began (e.g., 'June 2024', 'March 12, 2023', 'Jan 2025')

    2. STAGE INFORMATION (CRITICAL - DO NOT OMIT):
       - stage_header: Extract the AJCC stage at this time point. MUST start with 'Stage'.
         Format examples: 'Stage IIB', 'Stage IVA', 'Stage IIIA', 'Stage IVB', 'Stage 4'
         * Look for phrases like "Stage IVA", "AJCC Stage IIB", "Clinical Stage IIIA", "Pathologic Stage IB"
         * CRITICAL: The word 'Stage' is MANDATORY. If you find 'IVA', output 'Stage IVA'. If you find '4', output 'Stage 4'.
         * If the stage is mentioned in relation to this time point, extract it
         * If no stage is explicitly mentioned for this time point, use the most recently mentioned stage from earlier in the timeline
         * If absolutely no stage information is available in the document, set to null

       - tnm_status: Extract the complete TNM classification at this time point. NEVER include the word 'Stage'.
         Format examples: 'T2aN1M0', 'T4N3M1c', 'cT3N2M1a' (NOT 'Stage T2aN1M0')
         * Include ONLY TNM components (T, N, M) with prefixes (c=clinical, p=pathologic, y=post-therapy) and modifiers
         * CRITICAL: NEVER put the word 'Stage' in this field. It should only have T, N, M components.
         * Look for TNM staging mentioned in imaging reports, pathology reports, or staging assessments
         * If no TNM is explicitly mentioned for this time point, use the most recently mentioned TNM from earlier in the timeline
         * If absolutely no TNM information is available in the document, set to null

    3. DISEASE STATUS (REQUIRED): Each timeline entry must include exactly one disease status from the following:
       - 'Initial diagnosis' - Use for the first cancer diagnosis
       - 'Disease progression' - Use when disease has worsened or spread (new metastases, tumor growth, etc.)
       - 'Recurrence' - Use when cancer returns after remission
       - 'Stable disease' - Use ONLY if explicitly stated or imaging clearly reports no progression/unchanged disease
       - 'Remission' - Use when cancer is in remission or complete/partial response

    4. REGIMEN: Include only anti-cancer treatments in the regimen field.
       Exclude supportive medications such as pain medications, steroids for symptom control, antibiotics, anti-emetics, or non-oncologic drugs.
       If treatment is paused or stopped, clearly indicate this (e.g., "Durvalumab on hold").

    5. KEY FINDINGS: For each timeline entry, extract 2 to 3 key findings that directly justify why this entry exists, such as imaging results, pathology findings, or explicit clinical conclusions.
       These Key findings should be basically the summary of the patients pathology, imaging, and molecular findings at that time point.
       You should not mention the reports as such just the findings suffice.
       Do NOT include symptoms, subjective improvement, or non-decisive details.
       Ensure the number of key findings does not exceed 3.

    6. TOXICITIES: Extract treatment-related toxicities only if explicitly documented and clearly attributable to anti-cancer therapy.
       Do NOT infer CTCAE grades.
       If a grade is not stated, return null.

    CRITICAL REQUIREMENTS:
    - Every timeline entry MUST have stage_header and tnm_status populated (use most recent if not explicitly mentioned)
    - stage_header MUST start with 'Stage' (e.g., 'Stage IVA', 'Stage 4')
    - tnm_status MUST NOT contain the word 'Stage' (e.g., 'T4N3M1c', NOT 'Stage T4N3M1c')
    - Ensure timeline entries are ordered chronologically
    - Do not merge separate oncologic phases into a single entry
    - Return only valid JSON matching the expected schema
    - Do not include explanations, assumptions, or additional commentary

    """

    description = {
        "timeline": [
            {
                "date_label": "String (e.g., 'June 2024' or 'Jan 2025'). The specific date this phase began.",
                "stage_header": "String. REQUIRED. The AJCC stage at this time point - MUST start with 'Stage' (e.g., 'Stage IIB', 'Stage IVA', 'Stage IVB', 'Stage 4'). If you extract 'IVA', format it as 'Stage IVA'. If you extract '4', format it as 'Stage 4'. If not explicitly mentioned for this event, use the most recently mentioned stage. Set to null only if absolutely no stage information exists in the entire document.",
                "tnm_status": "String. REQUIRED. The TNM classification at this time point - MUST NOT contain 'Stage' (e.g., 'T2aN2M1a', 'T4N3M1c', 'cT3N2M1a'). Only include T, N, M components with prefixes/modifiers. If not explicitly mentioned for this event, use the most recently mentioned TNM. Set to null only if absolutely no TNM information exists in the entire document.",
                "disease_status": "String. REQUIRED. MUST be one of: 'Initial diagnosis', 'Disease progression', 'Recurrence', 'Stable disease', 'Remission'.",
                "regimen": "String. The ANTI-CANCER treatment regimen ONLY for this phase. Include: chemotherapy drugs (e.g., 'Carboplatin + Pemetrexed'), immunotherapy (e.g., 'Pembrolizumab', 'Opdivo + Yervoy'), targeted therapy (e.g., 'Osimertinib'), surgery (e.g., 'Lobectomy'), or radiation therapy. EXCLUDE: pain medications, anti-nausea drugs, supportive care medications, and all non-cancer treatments.",
                "key_findings": [
                    "String. Critical finding 1 (e.g., 'New contralateral lung nodules (2.1cm)').",
                    "String. Critical finding 2 (e.g., 'Pleural effusion with positive cytology').",
                    "String. Critical finding 3 (e.g., 'PD-L1 expression 85%').",
                    "String. Critical finding 4 (optional).",
                    "String. Critical finding 5 (optional)."
                ],
                "toxicities": [
                    {
                        "effect": "String (e.g., 'Neutropenia')",
                        "grade": "String (e.g., 'Grade 3')"
                    }
                ],
                "summary_count_check": "Integer. Hard verification of how many findings are listed (Must be between 3 and 5).",
                "Justification": "String. Why have you selected this as a timeline entry - what major oncologic transition occurred at this point."
            }
        ]
    }

    GEMINI_PROMPT = f"""
You are a deterministic clinical data extraction engine for oncology medical records.

{extraction_instruction}

OUTPUT SCHEMA (STRICT):
{json.dumps(description, indent=2)}

FINAL VALIDATION CHECKLIST - VERIFY BEFORE RETURNING:
1. All timeline events are in chronological order
2. All required fields are present for each timeline entry
3. CRITICAL: stage_header fields start with 'Stage' (e.g., 'Stage IVA', NOT 'IVA')
4. CRITICAL: tnm_status fields do NOT contain 'Stage' (e.g., 'T4N3M1c', NOT 'Stage T4N3M1c')
5. Use null for fields not documented rather than inferring

OUTPUT FORMAT:
Return VALID JSON ONLY.
No explanations.
No markdown code blocks.
No commentary.
Just the JSON object following the schema above.
"""

    logger.info("🤖 Generating diagnosis evolution timeline extraction with Vertex AI Gemini...")

    model = GenerativeModel("gemini-2.5-flash")
    doc_part = Part.from_data(data=pdf_bytes, mime_type="application/pdf")

    try:
        response = model.generate_content(
            [doc_part, GEMINI_PROMPT],
            generation_config={
                "temperature": 0,
                "top_p": 1
            }
        )
        logger.info("✅ Gemini diagnosis evolution extraction complete")
    except Exception as e:
        logger.error(f"❌ API request failed: {e}")
        raise

    try:
        response_text = response.text.strip()
        logger.info(f"📄 Extracted response text ({len(response_text)} chars)")

        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, response_text)

        if match:
            response_text = match.group(1).strip()
            logger.info("🧹 Cleaned markdown code blocks from response using regex")
        else:
            response_text = response_text.strip()
            logger.info("ℹ️  No markdown code blocks found, using response as is")

        extracted_data = json.loads(response_text)
        logger.info("✅ JSON parsed successfully")
        return extracted_data

    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(f"❌ Failed to parse Gemini response: {e}")
        logger.error(f"Raw response text (first 500 chars): {response_text[:500] if 'response_text' in locals() else 'N/A'}")
        raise


def extract_diagnosis_footer_with_gemini(pdf_input):
    """
    Extract diagnosis footer data using Vertex AI Gemini SDK.

    Args:
        pdf_input: Either bytes (PDF content) or URL/path to the PDF file

    Returns:
        Dictionary containing extracted diagnosis footer data
    """
    if isinstance(pdf_input, bytes):
        logger.info(f"📤 Using PDF bytes ({len(pdf_input)} bytes)")
        pdf_bytes = pdf_input
    elif pdf_input.startswith("http"):
        logger.info(f"📥 Downloading PDF from URL: {pdf_input}")
        if "drive.google.com" in pdf_input:
            match = re.search(r'/file/d/([^/]+)', pdf_input)
            if match:
                file_id = match.group(1)
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            else:
                raise ValueError("Could not extract file ID from Google Drive URL")
        else:
            download_url = pdf_input

        response = requests.get(download_url, allow_redirects=True)
        response.raise_for_status()
        pdf_bytes = response.content
        logger.info(f"✅ Downloaded {len(pdf_bytes)} bytes")
    else:
        logger.info(f"📤 Reading PDF from path: {pdf_input}")
        with open(pdf_input, "rb") as f:
            pdf_bytes = f.read()

    extraction_instruction = ("Extract temporal information about the patient's cancer diagnosis and disease progression. "
                                    "Identify the date of the first cancer diagnosis and calculate the total duration from that date to the document signature date or current date mentioned in the document. "
                                    "Identify the date of the most recent disease progression event (e.g., new metastases detected, disease advancement, or new primary diagnosis) and calculate the duration from that progression date to the document signature date. "
                                    "If there is no documented progression, set duration_since_progression to 'N/A'. "
                                    "Return the output strictly as a JSON object matching the schema described. "
                                    "Express durations in human-readable format (e.g., '14 months', '3 months', '2 years'). "
                                    "Do not infer values; if a value is not explicitly stated, return null.")

    description = {
                        "duration_since_diagnosis": "Total time from first ever diagnosis to the document signature date in human-readable format (e.g., '14 months', '2 years').",
                        "duration_since_progression": "Time elapsed from the most recent progression or new primary event to the document signature date in human-readable format (e.g., '3 months', '6 weeks'). Use 'N/A' if no progression is documented.",
                        "reference_dates": {
                            "initial_diagnosis_date": "The date of the first cancer diagnosis in ISO format (YYYY-MM-DD) or partial format (YYYY-MM).",
                            "last_progression_date": "The date of the most recent disease progression event in ISO format (YYYY-MM-DD) or partial format (YYYY-MM). Use null if no progression."
                        }
                    }

    GEMINI_PROMPT = f"""
You are a deterministic clinical data extraction engine for oncology medical records.

{extraction_instruction}

OUTPUT SCHEMA (STRICT):
{json.dumps(description, indent=2)}

FINAL VALIDATION:
- Ensure all fields in the schema are present in the output
- Use null for fields not explicitly documented
- Express durations in human-readable format

OUTPUT FORMAT:
Return VALID JSON ONLY.
No explanations.
No markdown code blocks.
No commentary.
Just the JSON object following the schema above.
"""

    logger.info("🤖 Generating diagnosis footer extraction with Vertex AI Gemini...")

    model = GenerativeModel("gemini-2.5-flash")
    doc_part = Part.from_data(data=pdf_bytes, mime_type="application/pdf")

    try:
        response = model.generate_content(
            [doc_part, GEMINI_PROMPT],
            generation_config={
                "temperature": 0,
                "top_p": 1
            }
        )
        logger.info("✅ Gemini diagnosis footer extraction complete")
    except Exception as e:
        logger.error(f"❌ API request failed: {e}")
        raise

    try:
        response_text = response.text.strip()
        logger.info(f"📄 Extracted response text ({len(response_text)} chars)")

        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, response_text)

        if match:
            response_text = match.group(1).strip()
            logger.info("🧹 Cleaned markdown code blocks from response using regex")
        else:
            response_text = response_text.strip()
            logger.info("ℹ️  No markdown code blocks found, using response as is")

        extracted_data = json.loads(response_text)
        logger.info("✅ JSON parsed successfully")
        return extracted_data

    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(f"❌ Failed to parse Gemini response: {e}")
        logger.error(f"Raw response text (first 500 chars): {response_text[:500] if 'response_text' in locals() else 'N/A'}")
        raise


def diagnosis_extraction(pdf_input, use_gemini=True):
    """
    Extract diagnosis information from a PDF document.

    Args:
        pdf_input: Either bytes (PDF content), URL, or file path
        use_gemini: Whether to use Gemini pipeline (default: True)

    Returns:
        Tuple of (diagnosis_header, diagnosis_evolution_timeline, diagnosis_footer)
    """

    extraction_instruction_header =  ("Extract comprehensive clinical summary data for the patient's primary cancer diagnosis from the medical records."
                            "1. CANCER IDENTIFICATION: Identify the primary cancer type (e.g., Non-Small Cell Lung Cancer), specific histology (e.g., Adenocarcinoma), and the initial diagnosis date."
                            "2. INITIAL STAGING: Find the staging information documented at the time of INITIAL/FIRST diagnosis. This is the baseline staging when the cancer was first identified. Look for terms like 'at diagnosis', 'initial presentation', or the earliest mentioned staging in the timeline."
                            "3. CURRENT STAGING: Find the MOST RECENT or CURRENT staging information. This reflects the latest disease status. Look for terms like 'current', 'most recent', 'latest', 'now shows', 'restaging', 'progression', or dates closest to the document date. "
                            "IMPORTANT: If no recent staging is explicitly mentioned (no restaging, no progression noted, no new TNM documented), this likely means the staging has NOT changed from initial diagnosis. In this case, use the same values from initial_staging for current_staging."
                            "4. STAGING FORMAT: For both initial and current staging, extract:"
                            "   - TNM: The complete TNM classification (e.g., 'T2a N1 M0' or 'T2aN1M0'). Include all components (T, N, M) with their modifiers (prefixes like c/p/y and suffixes like letters/numbers). NEVER use the word 'Stage' in this field."
                            "   - AJCC Stage: The full AJCC stage designation (e.g., 'Stage IIB', 'Stage IVA', 'Pathologic Stage IIIA', 'Clinical Stage IB'). Include stage type prefix if mentioned. MUST contain the word 'Stage'."
                            "5. DISEASE STATUS: Extract metastatic status (whether cancer has spread), specific metastatic sites (organs/locations), and recurrence/disease progression status."
                            "6. KEY RULES:"
                            "   - If only one staging is documented in the record, use it for both initial_staging and current_staging."
                            "   - If no recent/current staging is mentioned and there's no documentation of progression or restaging, assume no change occurred and copy initial_staging to current_staging."
                            "   - If the document mentions 'upstaging', 'downstaging', 'progression', or 'restaging', ensure these changes are reflected in current_staging with the new TNM/stage values."
                            "   - Return null for any field not explicitly stated in the document."
                            "   - Do not infer or calculate values."
                            "Return as a JSON object matching the schema below.")

    description_header = {
                "primary_diagnosis": "The formal clinical name of the primary cancer (e.g., 'Non-Small Cell Lung Cancer', 'Breast Carcinoma'). This should be the main cancer type being treated.",
                "histologic_type": "The specific microscopic cell type from pathology report (e.g., 'Adenocarcinoma', 'Squamous cell carcinoma', 'Ductal carcinoma'). This describes the cellular characteristics of the cancer.",
                "diagnosis_date": "The exact date when the cancer was first diagnosed in ISO format YYYY-MM-DD (e.g., '2023-03-15'). Look for phrases like 'diagnosed on', 'initial diagnosis date', or earliest mention of cancer detection.",
                "initial_staging": {
                    "tnm": "CRITICAL: TNM classification ONLY - NEVER EVER include 'Stage'. This is the T-N-M tumor staging classification at initial/first diagnosis. Format examples: 'T2a N1 M0', 'T2aN1M0', 'pT1c pN2 cM0', 'cT3 cN2 cM1a', 'T4 N3 M1c'. Include prefixes (c=clinical, p=pathologic, y=post-therapy) and all modifiers. The TNM field describes Tumor size (T), Node involvement (N), and Metastasis status (M). ABSOLUTELY DO NOT put stage groups like 'Stage IV' or 'Stage IIB' here - those go in ajcc_stage field. If staging evolved from initial diagnosis, this should capture the EARLIEST TNM mentioned. Return null if no TNM is documented.",
                    "ajcc_stage": "CRITICAL: AJCC stage group ONLY - MUST ALWAYS start with 'Stage'. Format examples: 'Stage IIB', 'Stage IIIA', 'Stage IB', 'Stage IVA', 'Stage IV', 'Stage 4'. Include stage type prefix if documented (e.g., 'Pathologic Stage IB', 'Clinical Stage IVA'). This is the baseline stage when cancer was first found. ABSOLUTELY DO NOT put TNM classifications like 'T2 N1 M0' here - those go in the tnm field."
                },
                "current_staging": {
                    "tnm": "CRITICAL: TNM classification ONLY - NEVER EVER include 'Stage'. This is the MOST RECENT T-N-M tumor staging classification. Format examples: 'T4 N3 M1c', 'cT2 cN1 cM1b', 'ypT0 ypN0 cM0', 'T2a N1 M0'. This should reflect the latest disease extent documented in the record with Tumor size (T), Node involvement (N), and Metastasis status (M). Look for most recent imaging, pathology, or clinical assessment. ABSOLUTELY DO NOT put stage groups like 'Stage IV' or 'Stage IIA' here - those go in ajcc_stage field. Return null if no TNM is documented.",
                    "ajcc_stage": "CRITICAL: AJCC stage group ONLY - MUST ALWAYS start with 'Stage'. This is the MOST RECENT stage group. Format examples: 'Stage IVB', 'Stage IIA', 'Stage IVA', 'Stage IIIB', 'Stage IV', 'Stage 4'. Include stage type prefix if documented (e.g., 'Clinical Stage IVA', 'Pathologic Stage IIIB'). This is the current or latest stage reflecting current disease status. If disease progressed or responded to treatment, this should show the updated stage. ABSOLUTELY DO NOT put TNM classifications like 'T4 N3 M1c' here - those go in the tnm field."
                },
                "metastatic_status": "Clear statement of metastatic spread. Examples: 'Yes - Active metastases', 'No metastatic disease', 'Metastatic', 'Limited stage', 'Extensive stage', 'M0 - No distant metastasis'. This indicates if cancer has spread beyond the primary site.",
                "metastatic_sites": "Array of specific anatomical sites where metastases are present. Give all the sites mentioned in the document given. Examples: ['Brain', 'Liver', 'Lung'], ['Bone', 'Lymph nodes'], ['Contralateral lung', 'Pleura']. Only include locations explicitly documented as metastatic. Return empty array if no metastases.",
                "recurrence_status": "Current disease behavior or progression state. Examples: 'Initial diagnosis - no prior cancer history', 'Progressive disease', 'Stable disease', 'Recurrent disease', 'Complete response', 'Partial response', 'Local recurrence', 'Distant recurrence'. This describes the disease trajectory."
                }

    extraction_instruction_evolution_timeline = (
            "Extract a comprehensive chronological timeline of the patient's cancer diagnosis, staging changes, treatment history, and disease evolution."
            "OBJECTIVE: Create a complete timeline showing how the patient's cancer has progressed or responded over time, including all staging changes, treatments administered, and clinical findings."
            ""
            "FOR EACH DISTINCT TIME POINT in the patient's journey, extract the following:"
            ""
            "1. DATE/TIMEFRAME:"
            "   - Capture the specific date, month/year, or timeframe (e.g., 'March 2023', 'June 15, 2024', '2022-11', 'Current Status')."
            "   - If this is the most recent entry, label it as 'Current Status' or use the most recent date mentioned."
            "   - Ensure dates are in chronological order from earliest to most recent."
            ""
            "2. STAGE INFORMATION:"
            "   - timeline_stage_group: The AJCC stage at this time point (e.g., 'Stage IIB', 'Stage IVA', 'Stage IB'). Include stage type if mentioned (e.g., 'Pathologic Stage IIIA', 'Clinical Stage IVB')."
            "   - timeline_tnm_status: The complete TNM classification at this time point (e.g., 'T2a N1 M0', 'T4 N3 M1c', 'pT1c pN0 cM0'). Include all components with prefixes and modifiers."
            "   - If staging hasn't changed from previous entry, still include the same staging information."
            ""
            "3. CLINICAL DESCRIPTION:"
            "   - timeline_description: Brief description of what happened at this time point. Examples: 'Initial diagnosis after biopsy', 'Disease progression detected on CT', 'Complete response to chemotherapy', 'Local recurrence identified', 'Metastatic disease progression', 'Stable disease on follow-up'."
            ""
            "4. TREATMENT INFORMATION:"
            "   - regimen: The ANTI-CANCER treatment regimen ONLY. Extract chemotherapy, immunotherapy, targeted therapy, surgery, or radiation therapy. Include drug names with doses if available."
            "     Examples: 'Right upper lobectomy', 'Carboplatin AUC 5 + Pemetrexed 500mg/m2', 'Osimertinib 80mg daily', 'Pembrolizumab 200mg Q3W', 'Radiation therapy 60 Gy', 'No treatment - surveillance'."
            "   - EXCLUDE: Pain medications, anti-nausea drugs, supportive care medications, symptom management, and all non-cancer treatments."
            "   - If no cancer treatment was given, explicitly state 'Surveillance' or 'No active treatment'."
            ""
            "5. TOXICITIES:"
            "   - Extract all treatment-related side effects with their severity grades."
            "   - Format: [{\"effect\": \"Neutropenia\", \"grade\": \"Grade 3\"}, {\"effect\": \"Fatigue\", \"grade\": \"Grade 2\"}]"
            "   - Include CTCAE grade if mentioned (Grade 1-5) or severity descriptors (Mild, Moderate, Severe)."
            "   - If no toxicities are documented, return an empty array."
            ""
            "6. DISEASE FINDINGS:"
            "   - Extract ALL clinical, pathology, imaging, and molecular findings documented at this time point."
            "   - Return as an array of distinct findings, each as a separate string."
            "   - Include:"
            "     * Imaging findings: tumor size, number of lesions, location, measurements (e.g., '3 brain metastases measuring 5-8mm on MRI', 'Primary tumor decreased from 4cm to 2.5cm')"
            "     * Pathology findings: biopsy results, histology, grade (e.g., 'Biopsy confirmed adenocarcinoma', 'Well-differentiated tumor grade')"
            "     * Molecular/genomic findings: mutations, biomarkers, test results (e.g., 'EGFR exon 19 deletion detected', 'PD-L1 TPS 85%', 'ALK fusion positive')"
            "     * Clinical findings: symptoms, physical exam, performance status (e.g., 'ECOG 1', 'New onset seizures', 'Weight loss 10 pounds')"
            "     * Disease progression/response markers: RECIST criteria, tumor markers (e.g., 'Progressive disease per RECIST 1.1', 'CEA increased from 5 to 45')"
            "   - Format example: [\"Primary tumor 4.2cm in RUL\", \"No lymph node involvement\", \"EGFR exon 19 deletion\", \"PD-L1 50%\"]"
            ""
            "KEY GUIDELINES:"
            "- Create timeline entries for: initial diagnosis, staging changes, treatment starts, disease progression/response events, and current status."
            "- Each time point should be a distinct entry in the array, ordered chronologically."
            "- Include at least: initial diagnosis entry and current status entry."
            "- If staging changed over time (e.g., upstaging from Stage II to Stage IV), ensure this is captured with separate timeline entries."
            "- If specific information is not documented for a time point, use null for that field rather than inferring."
            ""
            "Return all timeline events in chronological order in the 'stage_evolution_timeline' array."
        )

    description_evolution_timeline = {
        "stage_evolution_timeline": [
            {
                "timeline_event_date": "The date, month/year, or timeframe for this event. Format examples: 'March 2023', '2024-06-15', 'June 2024', 'Current Status'. Use 'Current Status' for the most recent entry. Ensure chronological ordering.",
                "timeline_stage_group": "The AJCC stage group at this time point - MUST start with 'Stage'. Format examples: 'Stage IIB', 'Stage IVA', 'Stage IIIA', 'Stage IB', 'Stage IVB', 'Stage 4'. If you extract 'IVA', format as 'Stage IVA'. Include stage type prefix if documented (e.g., 'Pathologic Stage IIIA', 'Clinical Stage IB'). The word 'Stage' is MANDATORY.",
                "timeline_tnm_status": "The complete TNM classification at this time point - MUST NOT include 'Stage'. Format examples: 'T2a N1 M0', 'T2aN1M0', 'cT4 cN3 cM1c', 'pT1c pN0 cM0', 'T3 N2 M1a'. Include ONLY T, N, M components with prefixes (c/p/y) and modifiers. Do NOT put the word 'Stage' here.",
                "timeline_description": "Brief clinical summary of what occurred at this time point. Examples: 'Initial diagnosis after CT-guided biopsy', 'Disease progression with new brain metastases', 'Partial response to chemotherapy', 'Surgical resection completed', 'Stable disease on maintenance therapy', 'Complete metabolic response on PET scan'.",
                "regimen": "The ANTI-CANCER treatment regimen ONLY administered at or after this time point. Include: chemotherapy (e.g., 'Carboplatin AUC 5 + Pemetrexed 500mg/m2 Q3W'), immunotherapy (e.g., 'Pembrolizumab 200mg IV Q3W'), targeted therapy (e.g., 'Osimertinib 80mg PO daily'), surgery (e.g., 'Right upper lobectomy with lymph node dissection'), or radiation (e.g., 'Radiation 60 Gy in 30 fractions'). EXCLUDE: pain medications, anti-nausea drugs, supportive care, and non-cancer treatments. Include drug names, doses, routes, and frequency when available. If no cancer treatment, state 'Surveillance - no active treatment'.",
                "toxicities": [
                    {
                        "effect": "The specific toxicity or adverse effect name. Examples: 'Neutropenia', 'Diarrhea', 'Fatigue', 'Rash', 'Neuropathy', 'Nausea', 'Anemia', 'Thrombocytopenia'.",
                        "grade": "The severity grade using CTCAE grading. Format examples: 'Grade 1', 'Grade 2', 'Grade 3', 'Grade 4', 'Mild', 'Moderate', 'Severe'. Must include 'Grade' prefix for numeric grades."
                    }
                ],
                "disease_findings": "Array of distinct clinical findings at this time point. Each finding should be a separate string. Include imaging results (tumor size, location, measurements), pathology results (cell type, grade, margins), molecular findings (mutations, biomarkers), clinical observations (symptoms, exam findings), and progression/response indicators. Format example: ['Primary mass 4.2cm x 3.8cm in right upper lobe', 'Mediastinal lymphadenopathy largest 2cm', 'No distant metastases on PET-CT', 'EGFR exon 19 deletion detected', 'PD-L1 expression 60%', 'ECOG performance status 1']. Return empty array if no findings documented."
            }
        ]
    }

    extraction_instruction_footer = ("Extract temporal information about the patient's cancer diagnosis and disease progression. "
                                    "Identify the date of the first cancer diagnosis and calculate the total duration from that date to the document signature date or current date mentioned in the document. "
                                    "Identify the date of the most recent disease progression event (e.g., new metastases detected, disease advancement, or new primary diagnosis) and calculate the duration from that progression date to the document signature date. "
                                    "If there is no documented progression, set duration_since_progression to 'N/A'. "
                                    "Return the output strictly as a JSON object matching the schema described. "
                                    "Express durations in human-readable format (e.g., '14 months', '3 months', '2 years'). "
                                    "Do not infer values; if a value is not explicitly stated, return null.")
    description_footer = {
                        "duration_since_diagnosis": "Total time from first ever diagnosis to the document signature date in human-readable format (e.g., '14 months', '2 years').",
                        "duration_since_progression": "Time elapsed from the most recent progression or new primary event to the document signature date in human-readable format (e.g., '3 months', '6 weeks'). Use 'N/A' if no progression is documented.",
                        "reference_dates": {
                            "initial_diagnosis_date": "The date of the first cancer diagnosis in ISO format (YYYY-MM-DD) or partial format (YYYY-MM).",
                            "last_progression_date": "The date of the most recent disease progression event in ISO format (YYYY-MM-DD) or partial format (YYYY-MM). Use null if no progression."
                        }
                    }

    log_extraction_start(logger, "Diagnosis Tab (3 components)", str(pdf_input)[:100] if isinstance(pdf_input, bytes) else pdf_input)

    # Convert URL/path to bytes once to avoid multiple downloads
    pdf_bytes = None
    if isinstance(pdf_input, bytes):
        logger.info(f"📤 Using provided PDF bytes ({len(pdf_input)} bytes)")
        pdf_bytes = pdf_input
    elif isinstance(pdf_input, str) and pdf_input.startswith("http"):
        # Download once for all three extractions
        logger.info(f"📥 Downloading PDF once from URL: {pdf_input}")
        if "drive.google.com" in pdf_input:
            match = re.search(r'/file/d/([^/]+)', pdf_input)
            if match:
                file_id = match.group(1)
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            else:
                raise ValueError("Could not extract file ID from Google Drive URL")
        else:
            download_url = pdf_input

        response = requests.get(download_url, allow_redirects=True)
        response.raise_for_status()
        pdf_bytes = response.content
        logger.info(f"✅ Downloaded {len(pdf_bytes)} bytes (will reuse for all 3 extractions)")
    elif isinstance(pdf_input, str):
        # Assume it's a file path
        logger.info(f"📤 Reading PDF once from path: {pdf_input}")
        with open(pdf_input, "rb") as f:
            pdf_bytes = f.read()
        logger.info(f"✅ Read {len(pdf_bytes)} bytes (will reuse for all 3 extractions)")
    else:
        raise ValueError("pdf_input must be bytes, URL string, or file path string")

    if use_gemini:
        # Gemini pipeline - pass bytes to avoid multiple downloads
        logger.info("🤖 Using Vertex AI Gemini pipeline")

        logger.info("🔄 Extracting patient diagnosis header data (1/3)...")
        diagnosis_header = extract_diagnosis_header_with_gemini(pdf_bytes)
        log_extraction_output(logger, "Diagnosis Header", diagnosis_header)
        log_extraction_complete(logger, "Diagnosis Header", diagnosis_header.keys() if isinstance(diagnosis_header, dict) else None)

        logger.info("🔄 Extracting patient diagnosis stage evolution data (2/3)...")
        diagnosis_evolution_timeline = extract_diagnosis_evolution_with_gemini(pdf_bytes)
        log_extraction_output(logger, "Diagnosis Evolution Timeline", diagnosis_evolution_timeline)
        log_extraction_complete(logger, "Diagnosis Evolution Timeline", diagnosis_evolution_timeline.keys() if isinstance(diagnosis_evolution_timeline, dict) else None)

        logger.info("🔄 Extracting patient diagnosis footer data (3/3)...")
        diagnosis_footer = extract_diagnosis_footer_with_gemini(pdf_bytes)
        log_extraction_output(logger, "Diagnosis Footer", diagnosis_footer)
        log_extraction_complete(logger, "Diagnosis Footer", diagnosis_footer.keys() if isinstance(diagnosis_footer, dict) else None)
    else:
        # Legacy pipeline using llmresponsedetailed
        logger.info("📝 Using legacy llmresponsedetailed pipeline")

        logger.info("🔄 Extracting patient diagnosis header data (1/3)...")
        diagnosis_header = llmresponsedetailed(pdf_url, extraction_instructions= extraction_instruction_header, description=description_header)
        log_extraction_output(logger, "Diagnosis Header", diagnosis_header)
        log_extraction_complete(logger, "Diagnosis Header", diagnosis_header.keys() if isinstance(diagnosis_header, dict) else None)

        logger.info("🔄 Extracting patient diagnosis stage evolution data (2/3)...")
        diagnosis_evolution_timeline = llmresponsedetailed(pdf_url, extraction_instructions=extraction_instruction_evolution_timeline, description=description_evolution_timeline)
        log_extraction_output(logger, "Diagnosis Evolution Timeline", diagnosis_evolution_timeline)
        log_extraction_complete(logger, "Diagnosis Evolution Timeline", diagnosis_evolution_timeline.keys() if isinstance(diagnosis_evolution_timeline, dict) else None)

        logger.info("🔄 Extracting patient diagnosis footer data (3/3)...")
        diagnosis_footer = llmresponsedetailed(pdf_url, extraction_instructions=extraction_instruction_footer, description=description_footer)
        log_extraction_output(logger, "Diagnosis Footer", diagnosis_footer)
        log_extraction_complete(logger, "Diagnosis Footer", diagnosis_footer.keys() if isinstance(diagnosis_footer, dict) else None)

    return diagnosis_header, diagnosis_evolution_timeline, diagnosis_footer


# diagnosis_info = diagnosis_extraction(pdf_url = "https://drive.google.com/file/d/1reIZIz8TOcOHhXheWZUszN5nfOqr0bQ-/view?usp=sharing")
# print(json.dumps(diagnosis_info, indent=2))