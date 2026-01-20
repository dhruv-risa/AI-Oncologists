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

from Backend.Utils.components import parser

# Initialize Vertex AI
vertexai.init(project="prior-auth-portal-dev", location="us-central1")


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
        "Extract the following patient demographic information from the medical document:"
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
    )

    GEMINI_PROMPT = f"""
You are a deterministic clinical data extraction engine for patient demographics.

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
  "Last Visit": "string - Date of most recent clinical visit"
}}

IMPORTANT:
- Use null for any field not explicitly stated in the document
- Do not infer or calculate values
- No explanations
- No markdown code blocks
- No commentary
- Just the JSON object
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
            "Extract the following patient demographic information from the medical document:"
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
        )

        response = parser.llmresponse(pdfurl=pdf_url, extraction_instructions=extraction_instructions)

        # Parse the response
        try:
            response_data = json.loads(response.text)
            return response_data.get('response', response_data)
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