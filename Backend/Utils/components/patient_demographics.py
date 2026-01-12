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

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
sys.path.append(PROJECT_ROOT)

from Backend.Utils.components import parser


def extract_patient_demographics(pdf_url):
    """
    Extract patient demographics from a PDF document.

    Args:
        pdf_url (str): URL to the PDF document (Google Drive or direct link)

    Returns:
        dict: Extracted demographics data containing:
            - Patient Name
            - MRN number
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
    extraction_instructions = (
        "Extract the following patient demographic information from the medical document:"
        "1. Patient Name - Full legal name"
        "2. MRN number - Medical Record Number"
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