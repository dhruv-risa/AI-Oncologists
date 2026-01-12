"""
Verification Script for Radiology Report Extraction

This script tests the radiology report extraction pipeline at the backend level.
It will:
1. Fetch radiology reports from FHIR
2. Combine each report with latest and initial MD notes
3. Upload to Google Drive
4. Extract radiology details using AI
5. Display the results

Usage:
    python verify_radiology_extraction.py
"""

import sys
import os
import json

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
sys.path.append(PROJECT_ROOT)

from Backend.bytes_extractor import upload_individual_radiology_reports_with_MD_notes_to_drive, get_md_notes
from Backend.Utils.Tabs.radiology_tab import extract_radiology_details_from_report


def print_separator(title=""):
    """Print a formatted separator line."""
    if title:
        print(f"\n{'='*80}")
        print(f"  {title}")
        print(f"{'='*80}\n")
    else:
        print(f"{'='*80}\n")


def verify_radiology_extraction(mrn: str):
    """
    Verify radiology report extraction for a given MRN.

    Args:
        mrn (str): Patient's Medical Record Number
    """
    print_separator(f"RADIOLOGY EXTRACTION VERIFICATION FOR MRN: {mrn}")

    # Step 1: Test MD note fetching
    print_separator("STEP 1: Testing MD Note Fetching")

    try:
        print("Fetching latest MD note...")
        latest_md = get_md_notes(mrn, most_recent_only=True, initial_only=False)
        if latest_md:
            print("✓ Latest MD note found:")
            print(f"  Date: {latest_md['date']}")
            print(f"  Type: {latest_md['document_type']}")
            print(f"  Description: {latest_md['description']}")
        else:
            print("✗ No latest MD note found")

        print("\nFetching initial MD note...")
        initial_md = get_md_notes(mrn, most_recent_only=False, initial_only=True)
        if initial_md:
            print("✓ Initial MD note found:")
            print(f"  Date: {initial_md['date']}")
            print(f"  Type: {initial_md['document_type']}")
            print(f"  Description: {initial_md['description']}")
        else:
            print("✗ No initial MD note found")

    except Exception as e:
        print(f"✗ Error fetching MD notes: {str(e)}")
        return

    # Step 2: Upload radiology reports with MD notes
    print_separator("STEP 2: Uploading Radiology Reports with MD Notes")

    try:
        print("Extracting and uploading radiology reports...")
        radiology_reports = upload_individual_radiology_reports_with_MD_notes_to_drive(mrn=mrn)

        if not radiology_reports:
            print("✗ No radiology reports found")
            return

        print(f"✓ Successfully uploaded {len(radiology_reports)} radiology report(s)\n")

        # Display basic info for each report
        for idx, report in enumerate(radiology_reports, 1):
            print(f"Report {idx}:")
            print(f"  Date: {report['date']}")
            print(f"  Type: {report['document_type']}")
            print(f"  Description: {report['description']}")
            print(f"  Has Latest MD Note: {report['has_latest_md_note']}")
            print(f"  Has Initial MD Note: {report['has_initial_md_note']}")
            print(f"  Radiology Only URL: {report['drive_url']}")
            print(f"  Combined with MD URL: {report['drive_url_with_MD']}")
            print()

    except Exception as e:
        print(f"✗ Error uploading radiology reports: {str(e)}")
        import traceback
        traceback.print_exc()
        return

    # Step 3: Extract radiology details using AI
    print_separator("STEP 3: Extracting Radiology Details Using AI")

    detailed_reports = []

    for idx, report in enumerate(radiology_reports, 1):
        print(f"\nProcessing Report {idx}/{len(radiology_reports)}...")
        print(f"  Document ID: {report['document_id']}")

        try:
            # Extract radiology information
            radiology_summary, radiology_imp_RECIST = extract_radiology_details_from_report(
                radiology_url=report['drive_url'],
                combined_with_md_url=report['drive_url_with_MD']
            )

            print("  ✓ Successfully extracted radiology details")

            detailed_reports.append({
                "report_metadata": {
                    "drive_url": report['drive_url'],
                    "drive_url_with_MD": report['drive_url_with_MD'],
                    "date": report['date'],
                    "document_type": report['document_type'],
                    "description": report['description'],
                    "document_id": report['document_id'],
                },
                "radiology_summary": radiology_summary,
                "radiology_imp_RECIST": radiology_imp_RECIST
            })

        except Exception as e:
            print(f"  ✗ Error extracting details: {str(e)}")
            import traceback
            traceback.print_exc()
            continue

    # Step 4: Display extracted details
    print_separator("STEP 4: Extracted Radiology Details")

    if not detailed_reports:
        print("✗ No radiology details were successfully extracted")
        return

    print(f"Successfully extracted details for {len(detailed_reports)} report(s)\n")

    for idx, report in enumerate(detailed_reports, 1):
        print(f"\n{'='*60}")
        print(f"REPORT {idx}")
        print(f"{'='*60}")

        print("\nMETADATA:")
        print(f"  Date: {report['report_metadata']['date']}")
        print(f"  Type: {report['report_metadata']['document_type']}")
        print(f"  Document ID: {report['report_metadata']['document_id']}")

        print("\nRADIOLOGY SUMMARY:")
        print(json.dumps(report['radiology_summary'], indent=2))

        print("\nRADIOLOGY IMPRESSION & RECIST:")
        print(json.dumps(report['radiology_imp_RECIST'], indent=2))

    # Step 5: Summary
    print_separator("VERIFICATION SUMMARY")

    print(f"MRN: {mrn}")
    print(f"Latest MD Note: {'Found' if latest_md else 'Not Found'}")
    print(f"Initial MD Note: {'Found' if initial_md else 'Not Found'}")
    print(f"Total Radiology Reports: {len(radiology_reports)}")
    print(f"Successfully Extracted: {len(detailed_reports)}")
    print(f"Failed Extractions: {len(radiology_reports) - len(detailed_reports)}")

    print("\n✓ Verification complete!\n")

    return detailed_reports


if __name__ == "__main__":
    # Test MRN - replace with actual MRN
    TEST_MRN = "A2451440"  # Replace with your test MRN

    print("\n" + "="*80)
    print("  RADIOLOGY EXTRACTION VERIFICATION SCRIPT")
    print("="*80)
    print(f"\nTest MRN: {TEST_MRN}")
    print("\nThis script will:")
    print("  1. Fetch MD notes (latest and initial)")
    print("  2. Extract radiology reports from FHIR")
    print("  3. Combine each report with MD notes")
    print("  4. Upload combined PDFs to Google Drive")
    print("  5. Extract radiology details using AI")
    print("  6. Display all extracted information")

    input("\nPress Enter to start verification...")

    try:
        results = verify_radiology_extraction(TEST_MRN)

        if results:
            print("\n" + "="*80)
            print("  VERIFICATION SUCCESSFUL!")
            print("="*80)
            print(f"\nExtracted details for {len(results)} radiology report(s)")
            print("\nYou can now test the API endpoints:")
            print(f"  1. POST /api/patient/all with MRN: {TEST_MRN}")
            print(f"  2. POST /api/tabs/radiology_reports with MRN: {TEST_MRN}")
        else:
            print("\n" + "="*80)
            print("  VERIFICATION FAILED")
            print("="*80)
            print("\nNo radiology details were extracted. Check the errors above.")

    except KeyboardInterrupt:
        print("\n\nVerification cancelled by user.")
    except Exception as e:
        print("\n" + "="*80)
        print("  VERIFICATION FAILED")
        print("="*80)
        print(f"\nUnexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
