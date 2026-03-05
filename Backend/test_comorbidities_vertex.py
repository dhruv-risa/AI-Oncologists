"""
Test script for Comorbidities Extraction using Vertex AI SDK

This script demonstrates how to use the updated comorbidities extraction
that now uses Vertex AI SDK directly instead of the external API.
"""
import json
from Utils.Tabs.comorbidities import extract_comorbidities_status


def test_comorbidities_extraction():
    """Test comorbidities extraction with Vertex AI SDK."""

    # Example PDF URL (replace with your actual test URL)
    test_pdf_url = "https://drive.google.com/file/d/YOUR_FILE_ID_HERE/view?usp=drive_link"

    print("="*70)
    print("Testing Comorbidities Extraction with Vertex AI SDK")
    print("="*70)

    try:
        # Extract using Vertex AI SDK (default)
        print("\n[1] Testing with Vertex AI SDK (use_gemini=True)...")
        comorbidities_data = extract_comorbidities_status(
            pdf_url=test_pdf_url,
            use_gemini=True
        )

        print("\n✅ Extraction successful!")
        print("\nExtracted Data:")
        print(json.dumps(comorbidities_data, indent=2))

        # Verify structure
        assert 'comorbidities' in comorbidities_data, "Missing 'comorbidities' field"
        assert 'ecog_performance_status' in comorbidities_data, "Missing 'ecog_performance_status' field"

        print("\n✅ Data structure validation passed!")

    except Exception as e:
        print(f"\n❌ Error during extraction: {str(e)}")
        raise

    print("\n" + "="*70)
    print("Test completed successfully!")
    print("="*70)


def test_legacy_extraction():
    """Test comorbidities extraction with legacy API."""

    # Example PDF URL (replace with your actual test URL)
    test_pdf_url = "https://drive.google.com/file/d/YOUR_FILE_ID_HERE/view?usp=drive_link"

    print("="*70)
    print("Testing Comorbidities Extraction with Legacy API")
    print("="*70)

    try:
        # Extract using legacy API
        print("\n[1] Testing with Legacy API (use_gemini=False)...")
        comorbidities_data = extract_comorbidities_status(
            pdf_url=test_pdf_url,
            use_gemini=False
        )

        print("\n✅ Extraction successful!")
        print("\nExtracted Data:")
        print(json.dumps(comorbidities_data, indent=2))

    except Exception as e:
        print(f"\n❌ Error during extraction: {str(e)}")
        raise


if __name__ == "__main__":
    print("\n" + "="*70)
    print("COMORBIDITIES EXTRACTION TEST SUITE")
    print("="*70 + "\n")

    # Test with Vertex AI SDK
    test_comorbidities_extraction()

    # Optionally test legacy API
    # test_legacy_extraction()
