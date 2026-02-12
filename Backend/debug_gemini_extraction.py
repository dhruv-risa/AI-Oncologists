#!/usr/bin/env python3
"""
Debug script to inspect what Gemini is extracting from the PDF
"""

import json
import sys
import os
import re
import requests
import vertexai
from vertexai.generative_models import GenerativeModel, Part

# Add Backend to path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Initialize Vertex AI
vertexai.init(project="prior-auth-portal-dev", location="us-central1")

def download_pdf(pdf_url):
    """Download PDF from URL"""
    print(f"📥 Downloading PDF from: {pdf_url}")

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
    print(f"✅ Downloaded {len(pdf_bytes)} bytes")
    return pdf_bytes

def test_simple_extraction(pdf_bytes):
    """Test with a very simple prompt to see if Gemini can read the PDF at all"""
    print("\n" + "="*80)
    print("TEST 1: Simple Content Extraction")
    print("="*80)

    simple_prompt = """Please analyze this PDF and tell me:
1. How many pages does it contain?
2. What type of document is this? (lab report, medical record, etc.)
3. List any lab test names you can find (just the test names, not values)
4. List any dates you can find
5. List any numeric values you can find

Just provide a simple text summary, not JSON."""

    model = GenerativeModel("gemini-2.5-pro")
    doc_part = Part.from_data(data=pdf_bytes, mime_type="application/pdf")

    try:
        response = model.generate_content(
            [doc_part, simple_prompt],
            generation_config={"temperature": 0, "top_p": 1}
        )

        print("\n📄 GEMINI RESPONSE:")
        print("-" * 80)
        print(response.text)
        print("-" * 80)
        return response.text

    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_structured_extraction(pdf_bytes):
    """Test with the actual structured prompt"""
    print("\n" + "="*80)
    print("TEST 2: Structured Lab Extraction")
    print("="*80)

    # Use the actual prompt from lab_tab.py but ask for verbose output
    prompt = """Extract lab data from this PDF.

IMPORTANT: If you cannot find a specific biomarker, explicitly note WHY you couldn't find it.
For example, if "CEA" is not in the document, say "CEA: Not found in document"

Target biomarkers:
- Tumor Markers: CEA, NSE, proGRP, CYFRA 21-1
- CBC: WBC, Hemoglobin, Platelets, ANC
- Metabolic: Creatinine, ALT, AST, Total Bilirubin

Return a JSON with this structure:
{
  "extraction_status": "brief description of what you found",
  "tumor_markers": {
    "CEA": {"value": <value or null>, "found": <true/false>, "reason": "explanation"},
    "NSE": {"value": <value or null>, "found": <true/false>, "reason": "explanation"},
    "proGRP": {"value": <value or null>, "found": <true/false>, "reason": "explanation"},
    "CYFRA_21_1": {"value": <value or null>, "found": <true/false>, "reason": "explanation"}
  },
  "complete_blood_count": {
    "WBC": {"value": <value or null>, "unit": <unit or null>, "found": <true/false>, "reason": "explanation"},
    "Hemoglobin": {"value": <value or null>, "unit": <unit or null>, "found": <true/false>, "reason": "explanation"},
    "Platelets": {"value": <value or null>, "unit": <unit or null>, "found": <true/false>, "reason": "explanation"},
    "ANC": {"value": <value or null>, "unit": <unit or null>, "found": <true/false>, "reason": "explanation"}
  },
  "metabolic_panel": {
    "Creatinine": {"value": <value or null>, "unit": <unit or null>, "found": <true/false>, "reason": "explanation"},
    "ALT": {"value": <value or null>, "unit": <unit or null>, "found": <true/false>, "reason": "explanation"},
    "AST": {"value": <value or null>, "unit": <unit or null>, "found": <true/false>, "reason": "explanation"},
    "Total Bilirubin": {"value": <value or null>, "unit": <unit or null>, "found": <true/false>, "reason": "explanation"}
  }
}"""

    model = GenerativeModel("gemini-2.5-pro")
    doc_part = Part.from_data(data=pdf_bytes, mime_type="application/pdf")

    try:
        response = model.generate_content(
            [doc_part, prompt],
            generation_config={"temperature": 0, "top_p": 1}
        )

        response_text = response.text.strip()
        print("\n📄 RAW GEMINI RESPONSE:")
        print("-" * 80)
        print(response_text)
        print("-" * 80)

        # Try to parse JSON
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, response_text)

        if match:
            response_text = match.group(1).strip()
            print("\n🧹 Extracted JSON from code block")

        try:
            data = json.loads(response_text)
            print("\n✅ JSON PARSED SUCCESSFULLY:")
            print("-" * 80)
            print(json.dumps(data, indent=2))
            print("-" * 80)
            return data
        except json.JSONDecodeError as e:
            print(f"\n❌ JSON parsing failed: {e}")
            print("Response is not valid JSON")
            return None

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main debug function"""
    # Get PDF URL from command line or use default
    if len(sys.argv) > 1:
        pdf_url = sys.argv[1]
    else:
        # Use the URL from the logs
        pdf_url = "https://drive.google.com/file/d/1XFfqxeZL6im7pO8pD-3eZvNrOgxid4B-/view?usp=drive_link"

    print("="*80)
    print("GEMINI PDF EXTRACTION DEBUG TOOL")
    print("="*80)
    print(f"\nPDF URL: {pdf_url}\n")

    # Download PDF
    try:
        pdf_bytes = download_pdf(pdf_url)
    except Exception as e:
        print(f"❌ Failed to download PDF: {e}")
        return

    # Test 1: Simple extraction to verify Gemini can read the PDF
    simple_result = test_simple_extraction(pdf_bytes)

    if not simple_result:
        print("\n⚠️  Gemini could not read the PDF at all. The PDF might be:")
        print("   • Corrupted")
        print("   • Image-based (scanned) without OCR")
        print("   • Password protected")
        print("   • Empty")
        return

    # Test 2: Structured extraction with verbose error messages
    structured_result = test_structured_extraction(pdf_bytes)

    if not structured_result:
        print("\n⚠️  Gemini could read the PDF but couldn't parse the response as JSON")
        return

    # Analyze results
    print("\n" + "="*80)
    print("ANALYSIS")
    print("="*80)

    print("\n📊 Extraction Summary:")
    print(f"Status: {structured_result.get('extraction_status', 'Unknown')}")

    for panel_name in ['tumor_markers', 'complete_blood_count', 'metabolic_panel']:
        if panel_name in structured_result:
            print(f"\n{panel_name.replace('_', ' ').title()}:")
            for biomarker, data in structured_result[panel_name].items():
                found = data.get('found', False)
                value = data.get('value')
                reason = data.get('reason', 'No reason provided')

                if found:
                    print(f"  ✅ {biomarker}: {value} - {reason}")
                else:
                    print(f"  ❌ {biomarker}: Not found - {reason}")

    print("\n" + "="*80)

if __name__ == "__main__":
    main()
