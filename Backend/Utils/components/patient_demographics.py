"""
Patient Demographics Extraction Module

Extracts demographic information from patient medical documents:
- Name
- MRN number
- Date of Birth (Age)
- Gender
- Height
- Weight
- Primary Oncologist
- Last Visit date


Source : Most recent MD notes
"""
import sys
import os
import json
import re
import requests
import vertexai
from vertexai.generative_models import GenerativeModel, Part
import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
sys.path.append(PROJECT_ROOT)

from Utils.components import parser

# Initialize Vertex AI
vertexai.init(project=os.environ.get("VERTEX_PROJECT", "rapids-platform"), location="us-central1")


def normalize_patient_name(name):
    """
    Normalize patient name to have proper capitalization:
    First letter uppercase, rest lowercase for each part of the name.

    Handles formats like:
    - "COSTANZO, ROBERT" -> "Costanzo, Robert"
    - "john doe" -> "John Doe"
    - "SMITH-JONES, MARY ANNE" -> "Smith-Jones, Mary Anne"

    Args:
        name (str): The patient name to normalize

    Returns:
        str: Normalized name with proper capitalization
    """
    if not name or not isinstance(name, str):
        return name

    # Split by comma first to handle "Last, First" format
    parts = name.split(',')
    normalized_parts = []

    for part in parts:
        # Handle each part (could be first name, last name, etc.)
        # Split by spaces and hyphens but keep the separators
        words = []
        for word in part.strip().split():
            # Handle hyphenated names like "Smith-Jones"
            if '-' in word:
                hyphenated = '-'.join([w.capitalize() for w in word.split('-')])
                words.append(hyphenated)
            else:
                words.append(word.capitalize())
        normalized_parts.append(' '.join(words))

    return ', '.join(normalized_parts)


def extract_demographics_with_gemini(pdf_input):
    """
    Extract patient demographics using Vertex AI Gemini SDK.

    Args:
        pdf_input: Either bytes (PDF content) or URL/path to the PDF file

    Returns:
        Dictionary containing extracted demographics data
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
        "Extract the following patient demographic and clinical information from the medical document:"
        "1. Patient Name - Full legal name"
        "2. MRN - Medical Record Number"
        "3. Date of Birth - Patient's birth date in MM/DD/YYYY format"
        f"4. Age - Current age in years You can calculate age based on DOB if needed. Current date is {datetime.datetime.now().strftime('%m/%d/%Y')}."
        "5. Gender - Male/Female/Other"
        "6. Height - In feet and inches or cm"
        "7. Weight - In pounds or kg"
        "8. Primary Oncologist - Name of the primary treating oncologist"
        "9. Last Visit - The date of the most recent clinical visit/appointment documented in this note. "
        "This should be the date of THIS appointment/encounter, typically found in the note header or date of service. "
        "Format as a readable date (e.g., 'January 15, 2024' or '01/15/2024'). "
        "Look for terms like 'Date of Visit', 'Encounter Date', 'Visit Date', 'Date of Service', or the document date."
        "10. Allergies - Extract ALL documented allergies including drug allergies, food allergies, environmental allergies. "
        "Look for 'Allergies', 'Drug Allergies', 'NKDA', 'No Known Drug Allergies', 'NKA', 'No Known Allergies'. "
        "If 'NKDA' or 'No Known Drug Allergies' is stated, record that explicitly."
        "11. Vital Signs - Extract ALL vital signs: Blood Pressure (systolic/diastolic), Heart Rate, "
        "Respiratory Rate, Temperature, Oxygen Saturation (SpO2/O2 sat). Look in 'Vitals', 'Vital Signs' section."
        "12. Social History - Extract smoking status (current/former/never, pack-years if available), "
        "alcohol use (frequency/amount), drug/substance use, occupation. Look in 'Social History' section."
        "13. PHQ-9 Score - Extract the PHQ-9 depression screening score if documented. "
        "Look for 'PHQ-9', 'PHQ9', 'depression screening'. Extract both the numeric score and interpretation."
        "14. Vaccination Status - Extract any documented vaccination information including "
        "flu/influenza, pneumonia/pneumococcal, COVID-19, shingles/zoster. "
        "Look for 'Immunizations', 'Vaccinations', 'Health Maintenance' sections."
    )

    GEMINI_PROMPT = f"""
You are a deterministic clinical data extraction engine for patient demographics and clinical information.

{extraction_instructions}

OUTPUT FORMAT:
Return VALID JSON ONLY with the following fields:
{{
  "Patient Name": "string - Full legal name",
  "MRN": "string - Medical Record Number",
  "Date of Birth": "string - MM/DD/YYYY format",
  "Age": "number - Age in years",
  "Gender": "string - Male/Female/Other",
  "Height": "string - Height in feet and inches or cm",
  "Weight": "string - Weight in pounds or kg",
  "Primary Oncologist": "string - Name of primary treating oncologist",
  "Last Visit": "string - Date of most recent clinical visit",
  "Allergies": {{
    "has_allergies": "boolean - true if patient has documented allergies, false if NKDA/NKA",
    "allergy_status": "string - 'NKDA', 'NKA', 'No Known Allergies', or 'Allergies Present'",
    "allergy_list": ["string - Each individual allergy with reaction if documented"]
  }},
  "Vital Signs": {{
    "blood_pressure_systolic": "number or null - Systolic BP in mmHg",
    "blood_pressure_diastolic": "number or null - Diastolic BP in mmHg",
    "heart_rate": "number or null - Heart rate in bpm",
    "respiratory_rate": "number or null - Respiratory rate per minute",
    "temperature": "number or null - Temperature in F or C (include unit)",
    "temperature_unit": "string - 'F' or 'C'",
    "oxygen_saturation": "number or null - SpO2 percentage",
    "pain_score": "number or null - Pain scale score if documented"
  }},
  "Social History": {{
    "smoking_status": "string - 'Current smoker', 'Former smoker', 'Never smoker', or null",
    "smoking_details": "string - Pack-years, quit date, etc. or null",
    "alcohol_use": "string - Description of alcohol use or 'None' or null",
    "drug_use": "string - Description or 'None' or 'Denies' or null",
    "occupation": "string or null"
  }},
  "PHQ9": {{
    "score": "number or null - PHQ-9 numeric score",
    "interpretation": "string or null - e.g., 'Minimal depression', 'No depression'"
  }},
  "Vaccination": {{
    "flu": "string or null - Flu vaccination status/date",
    "pneumonia": "string or null - Pneumococcal vaccination status/date",
    "covid": "string or null - COVID-19 vaccination status/date",
    "shingles": "string or null - Shingles/Zoster vaccination status/date",
    "other": "string or null - Any other vaccinations documented"
  }}
}}

IMPORTANT:
- Use null for any field not explicitly stated in the document
- Do not infer or calculate values
- For allergies: if document says 'NKDA' or 'No Known Drug Allergies', set has_allergies=false and allergy_status='NKDA'
- For vital signs: extract the numeric values only, preserving units
- For social history: capture smoking pack-years if mentioned
- No explanations
- No markdown code blocks
- No commentary
- Just the JSON object
"""

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

        # Normalize patient name to proper capitalization
        if 'Patient Name' in extracted_data and extracted_data['Patient Name']:
            extracted_data['Patient Name'] = normalize_patient_name(extracted_data['Patient Name'])

        return extracted_data

    except (json.JSONDecodeError, AttributeError) as e:
        raise Exception(f"Failed to parse Gemini response: {e}")


def extract_patient_demographics(pdf_url, use_gemini=True):
    """
    Extract patient demographics from a PDF document.

    Args:
        pdf_url (str): URL to the PDF document (Google Drive or direct link)
        use_gemini (bool): If True (default), uses Vertex AI Gemini SDK. If False, uses legacy parser.

    Returns:
        dict: Extracted demographics data containing:
            - Patient Name
            - MRN
            - Date of Birth
            - Age
            - Gender
            - Height
            - Weight
            - Primary Oncologist
            - Last Visit date

    Raises:
        Exception: If API call fails or returns an error
    """
    if use_gemini:
        # Gemini pipeline
        return extract_demographics_with_gemini(pdf_url)
    else:
        # Legacy pipeline using parser.llmresponse
        extraction_instructions = (
            "Extract the following patient demographic and clinical information from the medical document:"
            "1. Patient Name - Full legal name"
            "2. MRN - Medical Record Number"
            "3. Date of Birth - Patient's birth date in MM/DD/YYYY format"
            "4. Age - Current age in years"
            "5. Gender - Male/Female/Other"
            "6. Height - In feet and inches or cm"
            "7. Weight - In pounds or kg"
            "8. Primary Oncologist - Name of the primary treating oncologist"
            "9. Last Visit - The date of the most recent clinical visit/appointment documented in this note. "
            "This should be the date of THIS appointment/encounter, typically found in the note header or date of service. "
            "Format as a readable date (e.g., 'January 15, 2024' or '01/15/2024'). "
            "Look for terms like 'Date of Visit', 'Encounter Date', 'Visit Date', 'Date of Service', or the document date."
            "10. Allergies - drug allergies, food allergies, NKDA status"
            "11. Vital Signs - BP, HR, RR, Temp, O2 sat"
            "12. Social History - smoking, alcohol, drugs, occupation"
            "13. PHQ-9 Score - depression screening score"
            "14. Vaccination Status - flu, pneumonia, COVID, shingles"
        )

        response = parser.llmresponse(pdfurl=pdf_url, extraction_instructions=extraction_instructions)

        # Parse the response
        try:
            response_data = json.loads(response.text)
            extracted_data = response_data.get('response', response_data)

            # Normalize patient name to proper capitalization
            if 'Patient Name' in extracted_data and extracted_data['Patient Name']:
                extracted_data['Patient Name'] = normalize_patient_name(extracted_data['Patient Name'])

            return extracted_data
        except json.JSONDecodeError:
            raise Exception(f"Failed to parse response: {response.text}")


def main():
    """Main function for standalone execution."""
    # Default PDF URL for testing
    pdf_url = "https://drive.google.com/file/d/1JhR4wwWUZ6cjrwt8sIY1XSz7tjx65JK1/view?usp=drive_link"

    print("Extracting patient demographics...")
    demographics = extract_patient_demographics(pdf_url)
    print(json.dumps(demographics, indent=2))


if __name__ == "__main__":
    main()