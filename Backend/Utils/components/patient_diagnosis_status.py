"""
Patient Diagnosis Status Extraction Module

Extracts clinical disease information from patient medical documents:
- Cancer type
- Histology
- Diagnosis date
- TNM classification
- AJCC stage
- Line of therapy
- Metastatic sites
- ECOG performance status
- Current disease status


Source: Most recent MD Notes
"""
import requests
import json
import re
import vertexai
from vertexai.generative_models import GenerativeModel, Part

# Initialize Vertex AI
vertexai.init(project="prior-auth-portal-dev", location="us-central1")


def extract_diagnosis_status_with_gemini(pdf_input):
    """
    Extract patient diagnosis status using Vertex AI Gemini SDK.

    Args:
        pdf_input: Either bytes (PDF content) or URL/path to the PDF file

    Returns:
        Dictionary containing extracted diagnosis status data
    """
    # Handle both bytes and file path/URL inputs
    if isinstance(pdf_input, bytes):
        pdf_bytes = pdf_input
    elif pdf_input.startswith("http"):
        # Handle Google Drive URLs
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
    else:
        # Assume it's a file path
        with open(pdf_input, "rb") as f:
            pdf_bytes = f.read()

    extraction_instructions = (
    "Extract a comprehensive clinical disease summary for the patient from the medical document. "
    "ONLY extract information that is explicitly stated in the document.\n\n"
    "FOCUS AREAS:\n"
    "1. PRIMARY CANCER: Identify the primary cancer that is explicitly diagnosed and documented as active or primary. "
    "Look in Problem List, Diagnosis section, ICD codes, and Assessment sections. "
    "Do NOT treat suspected, possible, concerning, or differential diagnoses as confirmed primary cancer.\n"
    "2. HISTOLOGY: Carefully extract the histologic subtype from pathology reports, biopsy results, or clinical diagnosis. "
    "Check ALL sections: Pathology, Biopsy, Diagnosis, Clinical notes. The histology may be embedded in the cancer diagnosis "
    "(e.g., 'Epithelioid Mesothelioma' contains histology 'Epithelioid'). Extract it even if found within other text.\n"
    "3. DIAGNOSIS DATE: Extract the date when the primary cancer was first officially diagnosed or coded "
    "(not when it was suspected or under evaluation). Use ISO format YYYY-MM-DD.\n"
    "4. STAGING – Extract TWO separate staging assessments:\n"
    "   A. INITIAL STAGING: Staging explicitly documented at first diagnosis or presentation.\n"
    "   B. CURRENT STAGING: Most recent staging explicitly documented in the record.\n"
    "   For both, extract TNM (with prefixes and modifiers) and AJCC stage ONLY if explicitly stated.\n"
    "   CRITICAL FORMATTING:\n"
    "   - TNM field: NEVER include the word 'Stage'. Only T, N, M components (e.g., 'T2a N1 M0', 'T4N3M1c')\n"
    "   - AJCC Stage field: MUST ALWAYS include 'Stage' prefix (e.g., 'Stage IVB', 'Stage 4', 'Stage IIIA')\n"
    "5. TREATMENT STATUS: Current line of therapy MUST be an integer (1, 2, 3) NOT text ('first line', 'Line 1').\n"
    "6. METASTATIC DISEASE: Identify confirmed metastatic disease and list explicitly documented metastatic sites only.\n"
    "7. PERFORMANCE STATUS: ECOG score (0–4) if explicitly documented.\n"
    "8. DISEASE STATUS: Current disease behavior if explicitly described by the clinician.\n\n"
    "CRITICAL FORMATTING RULES:\n"
    "- line_of_therapy MUST be an integer (1, 2, 3) NOT a string\n"
    "- TNM fields NEVER contain the word 'Stage'\n"
    "- AJCC stage fields ALWAYS start with 'Stage'\n"
    "- Do NOT infer, calculate, or assume values.\n"
    "- Do NOT upgrade suspected or possible diagnoses into confirmed diagnoses.\n"
    "- If only one staging assessment is documented, use it for both initial_staging and current_staging.\n"
    "- Return null for fields not explicitly documented."
)


    description = {
    "cancer_type": (
        "Primary cancer type that is EXPLICITLY DIAGNOSED and documented as the active or primary malignancy. "
        "Use the official diagnosis, problem list entry, or ICD description. "
        "Examples: 'Non-Small Cell Lung Cancer', 'Pleural Mesothelioma', 'Breast Carcinoma', 'Malignant neoplasm of left lung'. USE FULL FORMS OF THE TEXTS ONLY"
        "Look in: Problem List, Diagnosis section, ICD-10 codes, Assessment section, or explicit diagnostic statements. "
        "⚠️ Do NOT use suspected, possible, concerning, or differential diagnoses as the primary cancer."
    ),

    "histology": (
        "Specific histologic subtype documented in the medical record. "
        "This can come from: pathology report, biopsy results, surgical specimen, cytology, or clinical diagnosis. "
        "Examples: 'Adenocarcinoma', 'Squamous cell carcinoma', 'Epithelioid mesothelioma', 'Sarcomatoid mesothelioma', "
        "'Biphasic mesothelioma', 'Small cell carcinoma', 'Large cell carcinoma', 'Invasive ductal carcinoma'. "
        "Look in: Pathology section, Biopsy results, Diagnosis section (may be part of primary diagnosis), Clinical notes. "
        "⚠️ If the histology is embedded in the cancer type (e.g., 'Epithelioid Pleural Mesothelioma'), extract just the histologic subtype ('Epithelioid'). "
        "⚠️ Return null ONLY if absolutely no histologic information is available anywhere in the document."
    ),

    "diagnosis_date": (
        "Date when the primary cancer was first officially diagnosed or coded. "
        "Use diagnosis tables, ICD-coded entries, or explicit statements of diagnosis. "
        "⚠️ Do NOT use imaging suspicion or concern dates. "
        "Format: ISO 'YYYY-MM-DD'."
    ),

    "initial_staging": {
        "tnm": (
            "TNM classification at INITIAL or BASELINE diagnosis, ONLY if explicitly documented. "
            "Include prefixes (c/p/y) and modifiers exactly as written. "
            "⚠️ Do NOT infer TNM from imaging or narrative descriptions."
        ),
        "ajcc_stage": (
            "AJCC stage at INITIAL diagnosis if explicitly documented. "
            "Must include the word 'Stage' (e.g., 'Stage IIIA', 'Clinical Stage IVB'). "
            "⚠️ Do NOT infer stage from metastatic descriptions."
        )
    },

    "current_staging": {
        "tnm": (
            "MOST RECENT documented TNM classification reflecting current disease extent. "
            "Only extract if explicitly stated in the document. "
            "⚠️ Do NOT calculate or infer TNM."
        ),
        "ajcc_stage": (
            "MOST RECENT documented AJCC stage reflecting current disease status. "
            "Must include the word 'Stage'. "
            "⚠️ Do NOT infer stage progression."
        )
    },

    "line_of_therapy": (
        "Current line of systemic therapy as an INTEGER value ONLY (1 = first line, 2 = second line, etc.). "
        "CRITICAL: Must be a numeric integer, NOT a string. Extract only the number. "
        "Examples: 1, 2, 3, 4 (NOT 'Line 1', '1st line', 'first', etc.). "
        "Only extract if explicitly stated. "
        "⚠️ Return null if not documented."
    ),

    "metastatic_sites": (
        "List of anatomical sites explicitly documented as metastatic disease. "
        "Examples: ['Bone', 'Liver', 'Brain', 'Muscle', 'Lymph nodes']. "
        "⚠️ Do NOT include suspicious or indeterminate sites. "
        "Return [] if no metastatic disease is explicitly confirmed."
    ),

    "ecog_status": (
        "ECOG performance status score (0–4) if explicitly documented. "
        "Examples: 'ECOG 1', 'Performance status 2'. "
        "⚠️ Do NOT infer from functional descriptions."
    ),

    "disease_status": (
        "Clinician-documented current disease behavior. "
        "Examples: 'Active disease', 'Progressive disease', 'Stable disease'. "
        "⚠️ Return null if not explicitly stated."
    )
}


    GEMINI_PROMPT = f"""
You are a deterministic clinical data extraction engine for oncology diagnosis status.

{extraction_instructions}

OUTPUT SCHEMA (STRICT):
{json.dumps(description, indent=2)}

FINAL VALIDATION CHECKLIST - VERIFY BEFORE RETURNING:
1. All fields in the schema are present in the output (use null if not found)
2. Dates are in YYYY-MM-DD format where applicable
3. CRITICAL: line_of_therapy is an INTEGER (1, 2, 3) NOT a string ('Line 1', 'first')
4. CRITICAL: TNM fields (initial_staging.tnm, current_staging.tnm) NEVER contain 'Stage'
5. CRITICAL: AJCC stage fields (initial_staging.ajcc_stage, current_staging.ajcc_stage) ALWAYS start with 'Stage'

OUTPUT FORMAT:
Return VALID JSON ONLY.
No explanations.
No markdown code blocks.
No commentary.
Just the JSON object following the schema above.
"""

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
    except Exception as e:
        raise Exception(f"Gemini API request failed: {e}")

    # Parse JSON response
    try:
        response_text = response.text.strip()

        # Use regex to extract JSON from markdown code blocks
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, response_text)

        if match:
            response_text = match.group(1).strip()
        else:
            response_text = response_text.strip()

        extracted_data = json.loads(response_text)
        return extracted_data

    except (json.JSONDecodeError, AttributeError) as e:
        raise Exception(f"Failed to parse Gemini response: {e}")


def extract_diagnosis_status(pdf_url, model="claude-sonnet-4-0", use_gemini=True):
    """
    Extract patient diagnosis and disease status from a PDF document.

    Args:
        pdf_url (str): URL to the PDF document (Google Drive or direct link)
        model (str): AI model to use for extraction (default: claude-sonnet-4-0) - only used when use_gemini=False
        use_gemini (bool): If True (default), uses Vertex AI Gemini SDK. If False, uses legacy API.

    Returns:
        dict: Extracted diagnosis data containing:
            - cancer_type: Primary cancer diagnosis
            - histology: Histologic subtype
            - diagnosis_date: Initial diagnosis date (ISO format)
            - tnm_classification: Tumor staging in TNM format
            - ajcc_stage: AJCC stage
            - line_of_therapy: Current line of therapy
            - metastatic_sites: List of metastatic sites
            - ecog_status: ECOG performance status score
            - disease_status: Current disease status

    Raises:
        Exception: If API call fails or returns an error
    """
    if use_gemini:
        # Gemini pipeline
        return extract_diagnosis_status_with_gemini(pdf_url)
    else:
        # Legacy pipeline using REST API
        url = "https://apis-dev.risalabs.ai/ai-service/commons/pdf-extraction/extract"

        payload = {
            "pdf_url": pdf_url,
            "extraction_instructions": (
                "Extract comprehensive clinical disease summary for the patient from the medical document."
                "FOCUS AREAS:"
                "1. PRIMARY CANCER: Identify the main cancer type (e.g., Non-Small Cell Lung Cancer, Breast Cancer) and specific histology (e.g., Adenocarcinoma, Ductal carcinoma)."
                "2. DIAGNOSIS DATE: Find the initial date when this cancer was first diagnosed (ISO format YYYY-MM-DD)."
                "3. STAGING - Extract TWO separate staging assessments:"
                "   A. INITIAL STAGING: The staging at first diagnosis/presentation (baseline staging when cancer was discovered)"
                "      - Look for terms like: 'at diagnosis', 'initial staging', 'at presentation', earliest documented staging"
                "   B. CURRENT STAGING: The most recent/latest staging assessment (current disease extent)"
                "      - Look for terms like: 'current', 'most recent', 'latest', 'now', closest to document date"
                "   For both, extract:"
                "      - TNM: Complete T, N, M components with prefixes (c/p/y) and modifiers"
                "      - AJCC Stage: Full stage designation with 'Stage' prefix (e.g., Stage IIA, Stage IVB)"
                "4. TREATMENT STATUS: Current line of therapy number if mentioned (e.g., 1st line, 2nd line)."
                "5. METASTATIC DISEASE: Identify if cancer has spread and list all specific metastatic sites/organs."
                "6. PERFORMANCE STATUS: ECOG score (0-4) if documented."
                "7. DISEASE STATUS: Current disease behavior (e.g., Stable, Progressive, Responding, Active)."
                ""
                "IMPORTANT RULES:"
                "- If only one staging is documented, use it for both initial_staging and current_staging."
                "- Include 'Stage' prefix in stage names (e.g., 'Stage IIB' not 'IIB')."
                "- Format TNM with spaces between components (e.g., 'T2a N1 M0' or 'T2aN1M0')."
                "- Return null for fields not explicitly stated in the document."
                "- Do not infer or calculate values."
                ""
                "Return the output strictly as a JSON object matching the schema."
            ),
            "metadata": {
                "description": {
                    "cancer_type": "Primary cancer type explicitly mentioned. Examples: 'Non-Small Cell Lung Cancer', 'Breast Carcinoma', 'Colorectal Adenocarcinoma'. This is the main cancer being treated.",
                    "histology": "Specific histologic subtype from pathology. Examples: 'Adenocarcinoma', 'Squamous cell carcinoma', 'Ductal carcinoma in situ', 'Invasive lobular carcinoma'. This describes the cell type.",
                    "diagnosis_date": "Date when cancer was first diagnosed. Format: ISO date 'YYYY-MM-DD' (e.g., '2023-03-15'). Look for 'diagnosed on', 'initial diagnosis', earliest cancer detection date.",
                    "initial_staging": {
                        "tnm": "TNM classification at INITIAL/FIRST diagnosis. This is the baseline staging when cancer was discovered. Format examples: 'T2a N1 M0', 'pT1c pN2 cM0', 'cT3 cN0 cM0'. Include T, N, M components with prefixes (c=clinical, p=pathologic) and modifiers. Look for earliest staging mentioned or terms like 'at diagnosis', 'initial staging'.",
                        "ajcc_stage": "AJCC stage at INITIAL diagnosis. This is the starting/baseline stage. Format examples: 'Stage IIB', 'Pathologic Stage IIIA', 'Clinical Stage IA'. Must include 'Stage' prefix. Include stage type (Clinical/Pathologic) if mentioned. This reflects disease extent at first detection."
                    },
                    "current_staging": {
                        "tnm": "MOST RECENT TNM classification. This reflects the latest disease assessment. Format examples: 'T4 N3 M1c', 'cT2 cN1 cM1b', 'ypT0 ypN0 cM0'. Include all components with current prefixes. Look for most recent imaging/assessment or terms like 'current', 'most recent', 'now shows'.",
                        "ajcc_stage": "MOST RECENT AJCC stage. This is the current/latest stage. Format examples: 'Stage IVB', 'Clinical Stage IVA', 'Stage IIIB'. Must include 'Stage' prefix. This reflects current disease status. If disease progressed (e.g., from Stage II to Stage IV), this should show the updated stage."
                    },
                    "line_of_therapy": "Current line of therapy as a number. Examples: 1, 2, 3. First-line = 1, Second-line = 2, etc. Only include if explicitly stated (e.g., 'on second-line therapy', '3rd line treatment'). Return null if not mentioned.",
                    "metastatic_sites": "Array of specific organs/locations where metastases are documented. Examples: ['Liver', 'Bone', 'Brain'], ['Lung', 'Lymph nodes'], ['Contralateral breast']. Only include sites explicitly identified as metastatic. Return empty array [] if no metastases or if M0 staging.",
                    "ecog_status": "ECOG performance status score (0-4). Examples: '0', '1', '2', '3', '4', 'ECOG 1', 'PS 2'. This measures patient's functional ability. Only include if explicitly documented. Return null if not mentioned.",
                    "disease_status": "Current clinical disease status/behavior. Examples: 'Active disease', 'Progressive disease', 'Stable disease', 'Responding to treatment', 'Complete response', 'Partial response', 'No evidence of disease'. This describes current disease state and trajectory. Similar to RECIST response categories."
                }
            },
            "config": {
                "model": model,
                "batch_size": 1,
                "enable_batch_processing": False
            },
            "response_type": "string"
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer {{bearerToken}}"
        }

        response = requests.post(url, headers=headers, json=payload)

        # Parse the response
        try:
            response_data = json.loads(response.text)
            # Extract the actual data from the response
            extracted_data = response_data.get('extracted_data', response_data)

            # If extracted_data is a string, parse it as JSON
            if isinstance(extracted_data, str):
                extracted_data = json.loads(extracted_data)

            return extracted_data
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse response: {response.text}")


def main():
    """Main function for standalone execution."""
    # Default PDF URL for testing
    pdf_url = "https://drive.google.com/file/d/1JhR4wwWUZ6cjrwt8sIY1XSz7tjx65JK1/view?usp=drive_link"

    print("Extracting patient diagnosis and disease status...")
    diagnosis = extract_diagnosis_status(pdf_url)
    print(json.dumps(diagnosis, indent=2))


if __name__ == "__main__":
    main()
