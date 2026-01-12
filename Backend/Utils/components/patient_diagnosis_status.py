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


def extract_diagnosis_status(pdf_url, model="claude-sonnet-4-0"):
    """
    Extract patient diagnosis and disease status from a PDF document.

    Args:
        pdf_url (str): URL to the PDF document (Google Drive or direct link)
        model (str): AI model to use for extraction (default: claude-sonnet-4-0)

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
