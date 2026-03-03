#!/usr/bin/env python3
"""
Test lab results extraction with FHIR integration for a specific MRN.

This script tests the current implementation which:
1. Fetches lab PDFs from FHIR DocumentReference API
2. Extracts data from each PDF using Gemini
3. Fetches FHIR Observations from FHIR Observation API
4. Merges both data sources
5. Returns consolidated lab results
"""

import json
import sys
import os
from datetime import datetime

# Add Backend to path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from main import lab_tab_info
from documents_reference import generate_bearer_token, generate_onco_emr_token, get_patient_id_from_mrn
from Utils.Tabs.fhir_lab_integration import (
    fetch_fhir_observations,
    convert_fhir_observations_to_lab_schema,
    match_biomarker_by_regex,
    extract_value_and_unit
)
from Utils.Tabs.lab_unit_converter import convert_to_standard_unit, get_standard_unit


def test_fhir_observations_directly(mrn: str):
    """
    Directly test FHIR Observations API to see raw data.

    Args:
        mrn: Medical Record Number
    """
    print("\n" + "="*100)
    print("STEP 1: TESTING FHIR OBSERVATIONS API DIRECTLY")
    print("="*100)

    try:
        # Authenticate
        print("\n🔑 Authenticating...")
        bearer_token = generate_bearer_token()
        onco_emr_token = generate_onco_emr_token(bearer_token)
        patient_id, _ = get_patient_id_from_mrn(mrn, onco_emr_token)
        print(f"✅ Patient ID: {patient_id}")

        # Fetch FHIR observations
        print(f"\n🔍 Fetching FHIR Observations for patient {patient_id}...")
        fhir_entries = fetch_fhir_observations(
            patient_id=patient_id,
            onco_emr_token=onco_emr_token,
            category="laboratory"
        )

        print(f"✅ Fetched {len(fhir_entries)} FHIR Observations")

        # Analyze what tests are in the observations
        print("\n📊 Analyzing FHIR Observations...")
        test_types = {}
        dates_seen = set()
        recognized_biomarkers = {}
        unit_conversions = []

        for entry in fhir_entries:  # Analyze ALL observations
            resource = entry.get("resource", {})

            # Get test name
            code = resource.get("code", {})
            codings = code.get("coding", [])

            loinc_code = None
            display_name = None

            for coding in codings:
                if coding.get("system") == "http://loinc.org":
                    loinc_code = coding.get("code")
                    display_name = coding.get("display", "Unknown")
                    break

            if not loinc_code:
                continue

            # Track test types
            if loinc_code not in test_types:
                test_types[loinc_code] = {
                    "display_name": display_name,
                    "count": 0
                }
            test_types[loinc_code]["count"] += 1

            # Check if this biomarker is recognized by regex matching
            biomarker_name = match_biomarker_by_regex(display_name)
            if biomarker_name:
                if biomarker_name not in recognized_biomarkers:
                    recognized_biomarkers[biomarker_name] = {
                        "loinc_code": loinc_code,
                        "display_name": display_name,
                        "count": 0,
                        "standard_unit": get_standard_unit(biomarker_name)
                    }
                recognized_biomarkers[biomarker_name]["count"] += 1

                # Check for unit conversions
                value, unit = extract_value_and_unit(resource)
                if value and unit:
                    standard_unit = get_standard_unit(biomarker_name)
                    if standard_unit and unit != standard_unit:
                        converted_value, _ = convert_to_standard_unit(value, unit, biomarker_name)
                        unit_conversions.append({
                            "biomarker": biomarker_name,
                            "original": f"{value} {unit}",
                            "converted": f"{converted_value} {standard_unit}"
                        })

            # Get date
            effective_date = (
                resource.get("effectiveDateTime") or
                resource.get("effectivePeriod", {}).get("start") or
                resource.get("issued")
            )
            if effective_date:
                date_part = effective_date.split('T')[0]
                dates_seen.add(date_part)

        print(f"\n📅 Unique dates found: {len(dates_seen)}")
        print(f"   Date range: {min(dates_seen)} to {max(dates_seen)}")
        print(f"\n📝 Total unique test types: {len(test_types)}")
        print(f"✅ Recognized biomarkers (mapped to our schema): {len(recognized_biomarkers)}")

        # Show recognized biomarkers
        if recognized_biomarkers:
            print("\n🎯 Recognized Biomarkers (matched via regex patterns):")
            for biomarker_name, info in sorted(recognized_biomarkers.items(), key=lambda x: x[1]['count'], reverse=True):
                print(f"   • {biomarker_name}: {info['count']} observations")
                print(f"      Sample Display: {info['display_name']}")
                print(f"      Standard Unit: {info['standard_unit']}")

        # Show unit conversions
        if unit_conversions:
            print(f"\n🔄 Unit Conversions Detected: {len(unit_conversions)} conversions")
            print("   Sample conversions:")
            for conversion in unit_conversions[:5]:
                print(f"   • {conversion['biomarker']}: {conversion['original']} → {conversion['converted']}")

        # Show top 15 most frequent tests
        print("\n🔬 Top 15 Most Frequent Test Types:")
        sorted_tests = sorted(test_types.items(), key=lambda x: x[1]["count"], reverse=True)
        for loinc, info in sorted_tests[:15]:
            # Check if this display name would match any biomarker
            is_recognized = match_biomarker_by_regex(info['display_name']) is not None
            status = "✅ RECOGNIZED" if is_recognized else "⚠️  Not matched"
            print(f"   • {info['display_name']} ({info['count']} occurrences) - {status}")

        # Convert FHIR observations to lab schema
        print("\n🔄 Converting FHIR Observations to Lab Schema...")
        fhir_lab_data_list = convert_fhir_observations_to_lab_schema(fhir_entries)

        # Save complete FHIR data
        fhir_output_filename = f"fhir_observations_complete_{mrn}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        fhir_output_path = os.path.join(BACKEND_DIR, fhir_output_filename)

        with open(fhir_output_path, 'w') as f:
            json.dump(fhir_lab_data_list, f, indent=2, ensure_ascii=False, default=str)

        print(f"✅ Complete FHIR data saved to: {fhir_output_filename}")

        # Show summary of converted data
        tm_count = sum(len(d.get('tumor_markers', {})) for d in fhir_lab_data_list)
        cbc_count = sum(len(d.get('complete_blood_count', {})) for d in fhir_lab_data_list)
        mp_count = sum(len(d.get('metabolic_panel', {})) for d in fhir_lab_data_list)

        print(f"\n📊 Converted FHIR Data Summary:")
        print(f"   • Date Groups: {len(fhir_lab_data_list)}")
        print(f"   • Total Tumor Marker observations: {tm_count}")
        print(f"   • Total CBC observations: {cbc_count}")
        print(f"   • Total Metabolic Panel observations: {mp_count}")

        return {
            "success": True,
            "total_observations": len(fhir_entries),
            "total_test_types": len(test_types),
            "total_unique_dates": len(dates_seen),
            "recognized_biomarkers": len(recognized_biomarkers),
            "unit_conversions": len(unit_conversions),
            "fhir_output_file": fhir_output_filename
        }

    except Exception as e:
        print(f"\n❌ FHIR API Test Failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def test_lab_extraction_with_fhir(mrn: str):
    """
    Test the complete lab extraction pipeline with FHIR integration.

    Args:
        mrn: Medical Record Number

    Returns:
        Dictionary with test results
    """
    print("\n" + "="*100)
    print("STEP 2: TESTING COMPLETE LAB EXTRACTION PIPELINE (PDFs + FHIR)")
    print("="*100)
    print(f"\nMRN: {mrn}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Extract lab info using the main pipeline
        print("\n🔄 Running lab extraction pipeline...")
        result = lab_tab_info(mrn, verbose=True)

        print("\n" + "="*100)
        print("EXTRACTION RESULTS SUMMARY")
        print("="*100)

        # Basic info
        print(f"\n✅ Success: {result.get('success')}")
        print(f"📄 Lab Results Count (PDFs): {result.get('lab_results_count')}")
        print(f"✅ Processed Documents: {result.get('processed_documents')}")

        # FHIR metadata
        if 'fhir_metadata' in result:
            fhir_meta = result['fhir_metadata']
            print(f"\n🔬 FHIR INTEGRATION:")
            print(f"   • Enabled: {fhir_meta.get('fhir_integration_enabled')}")
            print(f"   • Successful: {fhir_meta.get('fhir_integration_successful')}")
            print(f"   • Observations Fetched: {fhir_meta.get('fhir_observations_fetched')}")
            print(f"   • Biomarkers Converted: {fhir_meta.get('fhir_observations_converted')}")

        if 'total_data_sources' in result:
            print(f"\n📊 Total Data Sources: {result.get('total_data_sources')} (PDFs + FHIR)")

        # Lab data summary
        if result.get('lab_info'):
            lab_info = result['lab_info']

            print("\n📊 LAB DATA EXTRACTED:")

            total_biomarkers_with_data = 0
            total_trend_points = 0
            total_fhir_points = 0
            total_pdf_points = 0

            for panel_name in ['tumor_markers', 'complete_blood_count', 'metabolic_panel']:
                if panel_name in lab_info:
                    panel_data = lab_info[panel_name]
                    panel_title = panel_name.replace('_', ' ').title()

                    print(f"\n  {panel_title}:")
                    for marker_name, marker_data in panel_data.items():
                        if isinstance(marker_data, dict):
                            has_data = marker_data.get('has_data', False)
                            if has_data:
                                total_biomarkers_with_data += 1
                                current = marker_data.get('current', {})
                                trend = marker_data.get('trend', [])

                                value = current.get('value')
                                unit = current.get('unit')
                                date = current.get('date')
                                status = current.get('status')
                                source = current.get('source_context', '')

                                # Determine source type
                                source_icon = "🔬" if "FHIR" in source else "📄"

                                print(f"    • {marker_name}: {value} {unit} ({status}) - {date} {source_icon}")
                                print(f"      Current Source: {source}")
                                print(f"      Trend points: {len(trend)}")

                                total_trend_points += len(trend)

                                # Analyze trend sources
                                if trend:
                                    fhir_sources = [t for t in trend if 'FHIR' in str(t.get('source_context', ''))]
                                    pdf_sources = [t for t in trend if 'FHIR' not in str(t.get('source_context', ''))]

                                    total_fhir_points += len(fhir_sources)
                                    total_pdf_points += len(pdf_sources)

                                    trend_dates = [t.get('date') for t in trend]
                                    print(f"      Trend dates: {', '.join(trend_dates)}")
                                    print(f"      📄 PDF data points: {len(pdf_sources)} | 🔬 FHIR data points: {len(fhir_sources)}")

                                    # Show first few trend values
                                    if len(trend) > 0:
                                        print(f"      Sample trend values:")
                                        for t in trend[:3]:
                                            t_date = t.get('date')
                                            t_value = t.get('value')
                                            t_unit = t.get('unit')
                                            t_source = "🔬" if "FHIR" in str(t.get('source_context', '')) else "📄"
                                            print(f"         {t_source} {t_date}: {t_value} {t_unit}")
                                        if len(trend) > 3:
                                            print(f"         ... and {len(trend) - 3} more")
                            else:
                                print(f"    • {marker_name}: No data")

            # Summary statistics
            print(f"\n  📈 Data Summary:")
            print(f"     • Total Biomarkers with Data: {total_biomarkers_with_data}")
            print(f"     • Total Trend Points: {total_trend_points}")
            print(f"     • PDF Data Points: {total_pdf_points}")
            print(f"     • FHIR Data Points: {total_fhir_points}")

            # Clinical interpretation
            if 'clinical_interpretation' in lab_info:
                print("\n  📋 Clinical Interpretation:")
                for interp in lab_info['clinical_interpretation']:
                    print(f"    {interp}")

        # Save detailed results
        output_filename = f"lab_extraction_fhir_test_{mrn}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path = os.path.join(BACKEND_DIR, output_filename)

        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        print(f"\n💾 Full results saved to: {output_filename}")

        return {
            "success": True,
            "result": result,
            "output_file": output_filename
        }

    except Exception as e:
        print(f"\n❌ EXTRACTION FAILED")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


def main():
    """Main test function"""
    print("="*100)
    print("LAB EXTRACTION TEST WITH FHIR INTEGRATION")
    print("="*100)

    # Get MRN from command line or use default
    if len(sys.argv) > 1:
        mrn = sys.argv[1]
    else:
        mrn = input("\nEnter MRN to test (default: 2512120056): ").strip() or "2512120056"

    print(f"\n🎯 Testing with MRN: {mrn}")

    # Step 1: Test FHIR Observations API directly
    fhir_test = test_fhir_observations_directly(mrn)

    # Step 2: Test complete pipeline
    extraction_test = test_lab_extraction_with_fhir(mrn)

    # Final summary
    print("\n" + "="*100)
    print("TEST COMPLETE")
    print("="*100)

    print(f"\n📊 Summary:")
    print(f"   • MRN Tested: {mrn}")

    if fhir_test.get('success'):
        print(f"   • FHIR Observations Available: {fhir_test.get('total_observations')}")
        print(f"   • Unique Test Types: {fhir_test.get('total_test_types')}")
        print(f"   • Unique Dates: {fhir_test.get('total_unique_dates')}")
        print(f"   • Recognized Biomarkers: {fhir_test.get('recognized_biomarkers')}")
        print(f"   • Unit Conversions Applied: {fhir_test.get('unit_conversions')}")
        print(f"   • FHIR Data File: {fhir_test.get('fhir_output_file')}")
    else:
        print(f"   • FHIR Test: Failed - {fhir_test.get('error')}")

    if extraction_test.get('success'):
        result = extraction_test['result']
        print(f"   • Pipeline Execution: Success")
        print(f"   • PDF Documents: {result.get('lab_results_count')}")
        if 'fhir_metadata' in result:
            fhir_obs = result['fhir_metadata'].get('fhir_observations_fetched', 0)
            print(f"   • FHIR Observations Merged: {fhir_obs}")
        print(f"   • Output File: {extraction_test.get('output_file')}")
    else:
        print(f"   • Pipeline Execution: Failed - {extraction_test.get('error')}")

    print("\n" + "="*100)


if __name__ == "__main__":
    main()
