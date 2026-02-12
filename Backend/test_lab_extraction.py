#!/usr/bin/env python3
"""
Test lab results extraction for all patients in demo_data.json
"""

import json
import sys
import os
from datetime import datetime

# Add Backend to path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from Backend.Utils.Tabs.lab_tab import extract_lab_info

def load_demo_data():
    """Load patient data from demo_data.json"""
    demo_path = os.path.join(BACKEND_DIR, "demo_data.json")
    with open(demo_path, 'r') as f:
        return json.load(f)

def test_patient_lab_extraction(patient_id, lab_urls, test_first_only=True):
    """
    Test lab extraction for a patient

    Args:
        patient_id: Patient identifier
        lab_urls: List of lab report URLs
        test_first_only: If True, only test the first lab report

    Returns:
        Dictionary with patient's lab data organized by date
    """
    print("\n" + "="*100)
    print(f"PATIENT: {patient_id}")
    print("="*100)
    print(f"Total lab reports: {len(lab_urls)}")

    urls_to_test = [lab_urls[0]] if test_first_only else lab_urls

    # Structure to store all results for this patient
    patient_results = {
        "patient_id": patient_id,
        "total_reports_processed": 0,
        "reports_by_date": {},  # Date -> marker data
        "all_markers_timeline": {}  # Marker -> list of {date, value, unit, status}
    }

    for idx, url in enumerate(urls_to_test, 1):
        print(f"\n📄 Testing Lab Report {idx}/{len(urls_to_test)}")
        print(f"URL: {url}")
        print("-" * 100)

        try:
            # Extract lab info using Gemini
            lab_data = extract_lab_info(pdf_url=url, return_raw=False, use_gemini=True)
            patient_results["total_reports_processed"] += 1

            # Organize data by date and by marker
            for category in ['tumor_markers', 'complete_blood_count', 'metabolic_panel']:
                if category not in lab_data:
                    continue

                for marker_name, marker_data in lab_data[category].items():
                    if not marker_data or marker_data.get('value') is None:
                        continue

                    date = marker_data.get('date', 'Unknown')
                    value = marker_data.get('value')
                    unit = marker_data.get('unit', '')
                    status = marker_data.get('status', 'N/A')
                    reference_range = marker_data.get('reference_range', '')
                    source = marker_data.get('source_context', '')

                    # Organize by date
                    if date not in patient_results["reports_by_date"]:
                        patient_results["reports_by_date"][date] = {
                            "tumor_markers": {},
                            "complete_blood_count": {},
                            "metabolic_panel": {},
                            "report_url": url
                        }

                    patient_results["reports_by_date"][date][category][marker_name] = {
                        "value": value,
                        "unit": unit,
                        "status": status,
                        "reference_range": reference_range,
                        "source_context": source
                    }

                    # Organize by marker (timeline)
                    if marker_name not in patient_results["all_markers_timeline"]:
                        patient_results["all_markers_timeline"][marker_name] = {
                            "category": category,
                            "measurements": []
                        }

                    patient_results["all_markers_timeline"][marker_name]["measurements"].append({
                        "date": date,
                        "value": value,
                        "unit": unit,
                        "status": status,
                        "reference_range": reference_range,
                        "source_context": source,
                        "report_url": url
                    })

            # Display summary
            print("\n✅ EXTRACTION SUCCESSFUL")
            print("\n📊 SUMMARY:")

            # Display tumor markers
            if 'tumor_markers' in lab_data:
                print("\n  🔬 Tumor Markers:")
                for marker, data in lab_data['tumor_markers'].items():
                    if data and data.get('value') is not None:
                        print(f"    • {marker}: {data.get('value')} {data.get('unit', '')} ({data.get('status', 'N/A')}) - {data.get('date', 'N/A')}")
                    else:
                        print(f"    • {marker}: Not found")

            # Display CBC
            if 'complete_blood_count' in lab_data:
                print("\n  🩸 Complete Blood Count:")
                for test, data in lab_data['complete_blood_count'].items():
                    if data and data.get('value') is not None:
                        print(f"    • {test}: {data.get('value')} {data.get('unit', '')} ({data.get('status', 'N/A')}) - {data.get('date', 'N/A')}")
                    else:
                        print(f"    • {test}: Not found")

            # Display metabolic panel
            if 'metabolic_panel' in lab_data:
                print("\n  ⚗️  Metabolic Panel:")
                for test, data in lab_data['metabolic_panel'].items():
                    if data and data.get('value') is not None:
                        print(f"    • {test}: {data.get('value')} {data.get('unit', '')} ({data.get('status', 'N/A')}) - {data.get('date', 'N/A')}")
                    else:
                        print(f"    • {test}: Not found")

            # Display clinical interpretation
            if 'clinical_interpretation' in lab_data:
                print("\n  📋 Clinical Interpretation:")
                interp = lab_data['clinical_interpretation']
                if isinstance(interp, list):
                    for item in interp:
                        print(f"    {item}")
                else:
                    print(f"    {interp}")

            print("\n" + "-" * 100)

        except Exception as e:
            print(f"\n❌ EXTRACTION FAILED")
            print(f"Error: {str(e)}")
            import traceback
            print(traceback.format_exc())
            print("-" * 100)

    return patient_results

def main():
    """Main test function"""
    print("="*100)
    print("LAB EXTRACTION TEST - ALL PATIENTS")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*100)

    # Load demo data
    demo_data = load_demo_data()
    print(f"\n📋 Found {len(demo_data)} patients in demo_data.json")

    # Ask user if they want to test all reports or just first one
    print("\nOptions:")
    print("1. Test FIRST lab report only for each patient (recommended)")
    print("2. Test ALL lab reports for each patient (may take longer)")
    choice = input("\nEnter choice (1 or 2): ").strip()

    test_first_only = choice != "2"

    # Dictionary to store all patient results
    all_patients_results = {
        "extraction_timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "total_patients": len(demo_data),
        "test_mode": "first_report_only" if test_first_only else "all_reports",
        "patients": {}
    }

    # Test each patient
    for patient_id, patient_data in demo_data.items():
        lab_urls = patient_data.get('lab_results', [])

        if not lab_urls:
            print(f"\n⚠️  Patient {patient_id}: No lab reports found")
            all_patients_results["patients"][patient_id] = {
                "status": "no_lab_reports",
                "message": "No lab reports found for this patient"
            }
            continue

        # Extract and store results
        patient_results = test_patient_lab_extraction(patient_id, lab_urls, test_first_only)
        all_patients_results["patients"][patient_id] = patient_results

    # Save results to JSON file
    output_filename = f"lab_extraction_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path = os.path.join(BACKEND_DIR, output_filename)

    with open(output_path, 'w') as f:
        json.dump(all_patients_results, f, indent=2, ensure_ascii=False)

    print("\n" + "="*100)
    print("✅ TEST COMPLETE")
    print("="*100)
    print(f"\n💾 Results saved to: {output_path}")
    print(f"\n📊 Summary:")
    print(f"   • Total patients processed: {len(all_patients_results['patients'])}")
    print(f"   • Extraction mode: {all_patients_results['test_mode']}")

    # Display patient summary
    for patient_id, results in all_patients_results["patients"].items():
        if results.get("status") == "no_lab_reports":
            print(f"   • {patient_id}: No reports")
        else:
            reports_processed = results.get("total_reports_processed", 0)
            dates_found = len(results.get("reports_by_date", {}))
            markers_found = len(results.get("all_markers_timeline", {}))
            print(f"   • {patient_id}: {reports_processed} report(s), {dates_found} date(s), {markers_found} unique marker(s)")

    print("\n" + "="*100)

if __name__ == "__main__":
    main()
