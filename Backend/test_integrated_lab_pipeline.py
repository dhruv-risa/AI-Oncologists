"""
Test the complete integrated lab extraction pipeline with FHIR Observation API.

This script tests the full pipeline:
1. Fetch lab PDFs from FHIR DocumentReference API
2. Extract data from each PDF using Gemini
3. Fetch additional lab data from FHIR Observation API
4. Merge both datasets with deduplication
5. Postprocess and consolidate
6. Display results

Usage:
    python Backend/test_integrated_lab_pipeline.py --mrn A2451440
    python Backend/test_integrated_lab_pipeline.py --mrn A2451440 --save results.json
"""

import argparse
import json
import sys
import os

# Add Backend to path for imports
BACKEND_DIR = os.path.abspath(os.path.dirname(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from main import lab_tab_info


def format_date_for_display(date_str):
    """Convert YYYY-MM-DD to MM/DD/YYYY for display."""
    if not date_str or not isinstance(date_str, str):
        return date_str

    try:
        from datetime import datetime
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%m/%d/%Y")
    except (ValueError, AttributeError):
        return date_str


def display_lab_results_summary(result):
    """Display a comprehensive summary of lab extraction results."""
    print("\n" + "="*80)
    print("  LAB EXTRACTION RESULTS SUMMARY")
    print("="*80)

    if not result['success']:
        print(f"\n❌ Extraction failed: {result.get('error', 'Unknown error')}")
        return

    print(f"\n✅ Extraction successful!")
    print(f"\nMRN: {result['mrn']}")
    print(f"Total Lab Documents Found: {result['lab_results_count']}")
    print(f"Successfully Processed: {result['processed_documents']}")

    if 'validation_summary' in result:
        val = result['validation_summary']
        print(f"\nValidation:")
        print(f"  - Total Validated: {val['total_validated']}")
        print(f"  - Passed: {val['total_passed']}")
        print(f"  - Failed: {val['total_failed']}")
        print(f"  - Warnings: {val.get('total_warnings', 0)}")

    # Display lab info summary
    lab_info = result.get('lab_info', {})
    if lab_info:
        print("\n" + "-"*80)
        print("  BIOMARKER DATA SUMMARY")
        print("-"*80)

        for panel_name in ["tumor_markers", "complete_blood_count", "metabolic_panel"]:
            panel = lab_info.get(panel_name, {})
            panel_title = panel_name.replace("_", " ").title()

            print(f"\n{panel_title}:")

            if not panel:
                print("  No data")
                continue

            for biomarker_name, biomarker_data in panel.items():
                if not isinstance(biomarker_data, dict):
                    continue

                has_data = biomarker_data.get("has_data", False)

                if has_data:
                    current = biomarker_data.get("current", {})
                    value = current.get("value")
                    unit = current.get("unit")
                    date = current.get("date")
                    status = current.get("status")
                    trend_count = len(biomarker_data.get("trend", []))

                    # Status indicator
                    status_symbol = {
                        "Normal": "✓",
                        "High": "⬆",
                        "Low": "⬇",
                        "Critical": "⚠️"
                    }.get(status, "?")

                    # Format date for display (dates are already in MM/DD/YYYY from postprocessor)
                    print(f"  {status_symbol} {biomarker_name}: {value} {unit or ''} ({status}) - {date}")
                    if trend_count > 1:
                        print(f"      Trend: {trend_count} data points")

                        # Show trend dates (dates are already in MM/DD/YYYY from postprocessor)
                        trend = biomarker_data.get("trend", [])
                        if trend:
                            trend_dates = [t.get("date") for t in trend if t.get("date")]
                            if len(trend_dates) > 3:
                                print(f"      Dates: {trend_dates[0]} ... {trend_dates[-1]}")
                            else:
                                print(f"      Dates: {', '.join(trend_dates)}")
                else:
                    print(f"  ✗ {biomarker_name}: No data")

        # Display clinical interpretation
        clinical = lab_info.get("clinical_interpretation", [])
        if clinical:
            print("\n" + "-"*80)
            print("  CLINICAL INTERPRETATION")
            print("-"*80)
            for i, interp in enumerate(clinical, 1):
                print(f"{i}. {interp}")

        # Display summary stats
        summary = lab_info.get("summary", {})
        if summary:
            print("\n" + "-"*80)
            print("  SUMMARY STATISTICS")
            print("-"*80)
            print(f"Total Abnormal Values: {summary.get('total_abnormal', 0)}")
            print(f"Last Updated: {summary.get('last_updated', 'Unknown')}")


def display_source_breakdown(result):
    """Display breakdown of data sources (LLM vs FHIR API)."""
    lab_info = result.get('lab_info', {})
    if not lab_info:
        return

    print("\n" + "="*80)
    print("  DATA SOURCE ANALYSIS")
    print("="*80)

    # Count sources from trends
    source_counts = {
        "FHIR_API": 0,
        "LAB_REPORT": 0,
        "LAB_PANEL": 0,
        "MD_NOTE": 0,
        "OTHER": 0
    }

    for panel_name in ["tumor_markers", "complete_blood_count", "metabolic_panel"]:
        panel = lab_info.get(panel_name, {})

        for biomarker_name, biomarker_data in panel.items():
            if not isinstance(biomarker_data, dict):
                continue

            # Check current value source
            current = biomarker_data.get("current", {})
            if current.get("value") not in [None, "NA", ""]:
                # This comes from the most recent trend entry
                trend = biomarker_data.get("trend", [])
                if trend:
                    # Most recent is last in trend
                    most_recent = trend[-1]
                    source_context = most_recent.get("source_context", "")

                    if "FHIR_API" in source_context or "FHIR API" in source_context:
                        source_counts["FHIR_API"] += 1
                    elif "LAB_REPORT" in source_context:
                        source_counts["LAB_REPORT"] += 1
                    elif "LAB_PANEL" in source_context:
                        source_counts["LAB_PANEL"] += 1
                    elif "MD_NOTE" in source_context:
                        source_counts["MD_NOTE"] += 1
                    else:
                        source_counts["OTHER"] += 1

    # Display counts
    print("\nCurrent Values by Source:")
    for source, count in source_counts.items():
        if count > 0:
            print(f"  - {source}: {count} biomarker(s)")

    total = sum(source_counts.values())
    if total > 0:
        print(f"\nTotal Current Values: {total}")
        if source_counts["FHIR_API"] > 0:
            print(f"✅ FHIR API Integration Active: {source_counts['FHIR_API']} values from FHIR API")


def main():
    parser = argparse.ArgumentParser(
        description="Test the complete integrated lab extraction pipeline"
    )
    parser.add_argument("--mrn", type=str, required=True, help="Medical Record Number")
    parser.add_argument("--save", type=str, help="Save complete results to JSON file")
    parser.add_argument("--verbose", action="store_true", help="Show verbose output during extraction")

    args = parser.parse_args()

    print("\n" + "="*80)
    print("  INTEGRATED LAB EXTRACTION PIPELINE TEST")
    print("="*80)
    print("\nPipeline Steps:")
    print("  1. Fetch lab PDFs from FHIR DocumentReference API")
    print("  2. Extract data from each PDF using Gemini")
    print("  3. Fetch additional data from FHIR Observation API")
    print("  4. Merge datasets with date-based deduplication")
    print("  5. Postprocess and consolidate")
    print("\n" + "="*80)
    print(f"\nMRN: {args.mrn}")
    print("Starting extraction...\n")

    try:
        # Run the complete lab extraction pipeline
        result = lab_tab_info(args.mrn, verbose=args.verbose)

        # Display comprehensive summary
        display_lab_results_summary(result)

        # Display source breakdown (FHIR API vs LLM)
        display_source_breakdown(result)

        # Save results if requested
        if args.save:
            with open(args.save, "w") as f:
                json.dump(result, f, indent=2)
            print(f"\n💾 Complete results saved to: {args.save}")

        print("\n" + "="*80)
        print("  TEST COMPLETE")
        print("="*80 + "\n")

        # Exit with appropriate code
        sys.exit(0 if result['success'] else 1)

    except Exception as e:
        print(f"\n{'='*80}")
        print(f"  ERROR")
        print(f"{'='*80}")
        print(f"\n❌ {e}")
        import traceback
        traceback.print_exc()
        print(f"\n{'='*80}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
