#!/usr/bin/env python3
"""
Extract all lab results for a specific patient by MRN
"""

import json
import sys
import os
from datetime import datetime

# Add Backend to path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from Utils.Tabs.lab_tab import extract_lab_info

def load_demo_data():
    """Load patient data from demo_data.json"""
    demo_path = os.path.join(BACKEND_DIR, "demo_data.json")
    with open(demo_path, 'r') as f:
        return json.load(f)

def extract_all_labs_for_patient(mrn):
    """
    Extract all lab results for a patient with given MRN

    Args:
        mrn: Medical Record Number (Patient ID)

    Returns:
        Dictionary containing all lab results organized by date and by marker
    """
    # Load demo data
    demo_data = load_demo_data()

    # Check if patient exists
    if mrn not in demo_data:
        print(f"❌ Error: Patient MRN '{mrn}' not found in demo_data.json")
        print(f"\nAvailable MRNs:")
        for patient_id in demo_data.keys():
            print(f"  • {patient_id}")
        return None

    patient_data = demo_data[mrn]
    lab_urls = patient_data.get('lab_results', [])

    if not lab_urls:
        print(f"⚠️  Warning: No lab reports found for patient {mrn}")
        return None

    print("="*100)
    print(f"EXTRACTING ALL LAB RESULTS FOR PATIENT: {mrn}")
    print("="*100)
    print(f"Total lab reports to process: {len(lab_urls)}\n")

    # Structure to store all results
    patient_results = {
        "patient_mrn": mrn,
        "extraction_timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "total_reports": len(lab_urls),
        "reports_processed": 0,
        "reports_failed": 0,
        "reports_by_date": {},  # Date -> marker data
        "markers_timeline": {},  # Marker -> list of {date, value, unit, status}
        "all_raw_extractions": []  # Store raw data from each report
    }

    # Process each lab report
    for idx, url in enumerate(lab_urls, 1):
        print(f"\n{'='*100}")
        print(f"📄 Processing Report {idx}/{len(lab_urls)}")
        print(f"URL: {url}")
        print(f"{'='*100}")

        try:
            # Extract lab info using Gemini
            lab_data = extract_lab_info(pdf_url=url, return_raw=False, use_gemini=True)
            patient_results["reports_processed"] += 1

            # Store raw extraction
            patient_results["all_raw_extractions"].append({
                "report_index": idx,
                "report_url": url,
                "extraction_data": lab_data
            })

            # Process each category
            for category in ['tumor_markers', 'complete_blood_count', 'metabolic_panel']:
                if category not in lab_data:
                    continue

                category_display = {
                    'tumor_markers': '🔬 Tumor Markers',
                    'complete_blood_count': '🩸 Complete Blood Count',
                    'metabolic_panel': '⚗️  Metabolic Panel'
                }

                print(f"\n{category_display[category]}:")

                for marker_name, marker_data in lab_data[category].items():
                    # Handle nested structure from format_for_ui
                    # Data is in marker_data['current'] after postprocessing
                    if not marker_data:
                        print(f"  • {marker_name}: Not found")
                        continue

                    # Extract current values (postprocessed format has 'current' nested dict)
                    current_data = marker_data.get('current', marker_data)

                    value = current_data.get('value')
                    if value is None or value == 'NA':
                        print(f"  • {marker_name}: Not found")
                        continue

                    date = current_data.get('date', 'Unknown')
                    unit = current_data.get('unit', '')
                    status = current_data.get('status', 'N/A')
                    reference_range = current_data.get('reference_range', '')
                    source = current_data.get('source_context', '')

                    print(f"  • {marker_name}: {value} {unit} ({status}) - Date: {date}")

                    # Organize by date
                    if date not in patient_results["reports_by_date"]:
                        patient_results["reports_by_date"][date] = {
                            "tumor_markers": {},
                            "complete_blood_count": {},
                            "metabolic_panel": {},
                            "report_urls": []
                        }

                    if url not in patient_results["reports_by_date"][date]["report_urls"]:
                        patient_results["reports_by_date"][date]["report_urls"].append(url)

                    patient_results["reports_by_date"][date][category][marker_name] = {
                        "value": value,
                        "unit": unit,
                        "status": status,
                        "reference_range": reference_range,
                        "source_context": source
                    }

                    # Organize by marker (timeline)
                    if marker_name not in patient_results["markers_timeline"]:
                        patient_results["markers_timeline"][marker_name] = {
                            "category": category,
                            "measurements": []
                        }

                    patient_results["markers_timeline"][marker_name]["measurements"].append({
                        "date": date,
                        "value": value,
                        "unit": unit,
                        "status": status,
                        "reference_range": reference_range,
                        "source_context": source,
                        "report_url": url,
                        "report_index": idx
                    })

            # Display clinical interpretation if available
            if 'clinical_interpretation' in lab_data:
                print(f"\n📋 Clinical Interpretation:")
                interp = lab_data['clinical_interpretation']
                if isinstance(interp, list):
                    for item in interp:
                        print(f"  {item}")
                else:
                    print(f"  {interp}")

            print(f"\n✅ Report {idx} processed successfully")

        except Exception as e:
            print(f"\n❌ EXTRACTION FAILED for Report {idx}")
            print(f"Error: {str(e)}")
            patient_results["reports_failed"] += 1
            import traceback
            print(traceback.format_exc())

    # Sort markers_timeline by date
    for marker_name in patient_results["markers_timeline"]:
        measurements = patient_results["markers_timeline"][marker_name]["measurements"]
        # Sort by date
        measurements.sort(key=lambda x: x["date"] if x["date"] != "Unknown" else "9999-99-99")

    # Sort reports_by_date
    patient_results["reports_by_date"] = dict(sorted(
        patient_results["reports_by_date"].items(),
        key=lambda x: x[0] if x[0] != "Unknown" else "9999-99-99"
    ))

    return patient_results

def save_results(mrn, results):
    """Save extraction results to JSON file"""
    if results is None:
        return None

    output_filename = f"patient_{mrn}_lab_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path = os.path.join(BACKEND_DIR, output_filename)

    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return output_path

def main():
    """Main function"""
    if len(sys.argv) > 1:
        # MRN provided as command line argument
        mrn = sys.argv[1]
    else:
        # Interactive mode
        demo_data = load_demo_data()
        print("Available Patient MRNs:")
        for patient_id in demo_data.keys():
            lab_count = len(demo_data[patient_id].get('lab_results', []))
            print(f"  • {patient_id} ({lab_count} lab reports)")

        mrn = "4006762"

    # Extract all labs
    results = extract_all_labs_for_patient(mrn)

    if results:
        # Save to file
        output_path = save_results(mrn, results)

        print("\n" + "="*100)
        print("✅ EXTRACTION COMPLETE")
        print("="*100)
        print(f"\n💾 Results saved to: {output_path}")
        print(f"\n📊 Summary:")
        print(f"   • Patient MRN: {results['patient_mrn']}")
        print(f"   • Total reports: {results['total_reports']}")
        print(f"   • Reports processed: {results['reports_processed']}")
        print(f"   • Reports failed: {results['reports_failed']}")
        print(f"   • Unique dates found: {len(results['reports_by_date'])}")
        print(f"   • Unique markers found: {len(results['markers_timeline'])}")

        # Display markers summary
        if results['markers_timeline']:
            print(f"\n📈 Markers Timeline:")
            for marker_name, marker_data in results['markers_timeline'].items():
                measurements = marker_data['measurements']
                print(f"   • {marker_name}: {len(measurements)} measurement(s)")

        # Display dates summary
        if results['reports_by_date']:
            print(f"\n📅 Data by Date:")
            for date in sorted(results['reports_by_date'].keys()):
                date_data = results['reports_by_date'][date]
                total_markers = (
                    len(date_data.get('tumor_markers', {})) +
                    len(date_data.get('complete_blood_count', {})) +
                    len(date_data.get('metabolic_panel', {}))
                )
                print(f"   • {date}: {total_markers} marker(s)")

        print("\n" + "="*100)

if __name__ == "__main__":
    main()
