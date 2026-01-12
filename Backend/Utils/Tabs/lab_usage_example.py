"""
Example usage of lab data extraction and UI preparation.

This file demonstrates how to:
1. Extract lab data from PDF
2. Process it for UI consumption
3. Prepare data for charts and current value displays
"""

import json
from lab_tab import extract_lab_info
from lab_chart_helper import (
    prepare_all_panels_for_display,
    prepare_for_chartjs,
    prepare_for_recharts,
    prepare_for_plotly
)


def example_basic_usage():
    """Basic usage: Extract and get processed data."""
    pdf_url = "https://drive.google.com/file/d/1O-0tgjgRqXUSNDw9LsWkvw-8V7bk8e7N/view?usp=sharing"

    # Extract and process lab data
    processed_data = extract_lab_info(pdf_url)

    # The processed_data now contains:
    # - tumor_markers: dict with CEA, NSE, proGRP, CYFRA_21_1
    # - complete_blood_count: dict with WBC, Hemoglobin, Platelets, ANC
    # - metabolic_panel: dict with Creatinine, ALT, AST, Total Bilirubin
    # - clinical_interpretation: list of interpretation strings
    # - summary: dict with total_abnormal count and last_updated date

    return processed_data


def example_display_current_values(processed_data):
    """Example: Display current values for all biomarkers."""
    print("\n" + "="*80)
    print("CURRENT LAB VALUES")
    print("="*80)

    # Tumor Markers
    print("\nTUMOR MARKERS:")
    for name, data in processed_data["tumor_markers"].items():
        current = data["current"]
        value = current["value"]
        unit = current["unit"]
        status = current["status"]
        date = current["date"]

        # Skip if no data
        if not data["has_data"]:
            print(f"  {name}: No data available")
            continue

        # Display with status indicator
        status_symbol = "✓" if status == "Normal" else "⚠" if status in ["High", "Low"] else "✗"
        print(f"  {status_symbol} {name}: {value} {unit} ({status}) - {date}")

    # Complete Blood Count
    print("\nCOMPLETE BLOOD COUNT:")
    for name, data in processed_data["complete_blood_count"].items():
        current = data["current"]
        value = current["value"]
        unit = current["unit"]
        status = current["status"]
        date = current["date"]

        if not data["has_data"]:
            print(f"  {name}: No data available")
            continue

        status_symbol = "✓" if status == "Normal" else "⚠" if status in ["High", "Low"] else "✗"
        print(f"  {status_symbol} {name}: {value} {unit} ({status}) - {date}")

    # Metabolic Panel
    print("\nMETABOLIC PANEL:")
    for name, data in processed_data["metabolic_panel"].items():
        current = data["current"]
        value = current["value"]
        unit = current["unit"]
        status = current["status"]
        date = current["date"]

        if not data["has_data"]:
            print(f"  {name}: No data available")
            continue

        status_symbol = "✓" if status == "Normal" else "⚠" if status in ["High", "Low"] else "✗"
        print(f"  {status_symbol} {name}: {value} {unit} ({status}) - {date}")


def example_prepare_for_ui(processed_data):
    """Example: Prepare data for frontend UI framework."""
    # This prepares data in a format that's easy to use in React, Vue, etc.
    ui_data = prepare_all_panels_for_display(processed_data)

    print("\n" + "="*80)
    print("UI-READY DATA STRUCTURE")
    print("="*80)
    print(json.dumps(ui_data, indent=2))

    return ui_data


def example_chart_data_for_biomarker(processed_data, biomarker_name, panel_name):
    """Example: Get chart data for a specific biomarker."""
    # Get the biomarker data
    panel_map = {
        "tumor_markers": processed_data["tumor_markers"],
        "complete_blood_count": processed_data["complete_blood_count"],
        "metabolic_panel": processed_data["metabolic_panel"]
    }

    panel = panel_map.get(panel_name, {})
    biomarker_data = panel.get(biomarker_name)

    if not biomarker_data:
        print(f"Biomarker {biomarker_name} not found in {panel_name}")
        return None

    # Prepare for different chart libraries
    print(f"\n{'='*80}")
    print(f"CHART DATA FOR {biomarker_name}")
    print('='*80)

    # Chart.js format
    chartjs_data = prepare_for_chartjs(biomarker_data, biomarker_name)
    if chartjs_data:
        print("\nChart.js format:")
        print(json.dumps(chartjs_data, indent=2))

    # Recharts format
    recharts_data = prepare_for_recharts(biomarker_data)
    if recharts_data:
        print("\nRecharts format:")
        print(json.dumps(recharts_data, indent=2))

    # Plotly format
    plotly_data = prepare_for_plotly(biomarker_data, biomarker_name)
    if plotly_data:
        print("\nPlotly format:")
        print(json.dumps(plotly_data, indent=2))

    return {
        "chartjs": chartjs_data,
        "recharts": recharts_data,
        "plotly": plotly_data
    }


def example_summary_stats(processed_data):
    """Example: Display summary statistics."""
    summary = processed_data.get("summary", {})

    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    print(f"Total Abnormal Values: {summary.get('total_abnormal', 0)}")
    print(f"Last Updated: {summary.get('last_updated', 'N/A')}")

    # Clinical interpretations
    interpretations = processed_data.get("clinical_interpretation", [])
    if interpretations:
        print("\nClinical Interpretations:")
        for i, interp in enumerate(interpretations, 1):
            print(f"{i}. {interp}")


def example_trend_analysis(processed_data):
    """Example: Analyze trends for all biomarkers."""
    print("\n" + "="*80)
    print("TREND ANALYSIS")
    print("="*80)

    all_panels = [
        ("Tumor Markers", processed_data["tumor_markers"]),
        ("Complete Blood Count", processed_data["complete_blood_count"]),
        ("Metabolic Panel", processed_data["metabolic_panel"])
    ]

    for panel_name, panel_data in all_panels:
        print(f"\n{panel_name}:")
        for biomarker_name, biomarker_data in panel_data.items():
            if not biomarker_data.get("has_data"):
                continue

            trend_direction = biomarker_data.get("trend_direction", "insufficient_data")
            trend_count = len(biomarker_data.get("trend", []))

            symbol_map = {
                "increasing": "↑",
                "decreasing": "↓",
                "stable": "→",
                "insufficient_data": "?"
            }

            symbol = symbol_map.get(trend_direction, "?")
            print(f"  {symbol} {biomarker_name}: {trend_direction} ({trend_count} data points)")


def run_complete_example():
    """Run complete example workflow."""
    # Step 1: Extract and process data
    print("Step 1: Extracting lab data...")
    processed_data = example_basic_usage()

    # Step 2: Display current values
    example_display_current_values(processed_data)

    # Step 3: Show summary statistics
    example_summary_stats(processed_data)

    # Step 4: Show trend analysis
    example_trend_analysis(processed_data)

    # Step 5: Prepare UI data
    ui_data = example_prepare_for_ui(processed_data)

    # Step 6: Show chart data for specific biomarker
    # Example: CEA from tumor markers
    if processed_data["tumor_markers"].get("CEA", {}).get("has_data"):
        example_chart_data_for_biomarker(processed_data, "CEA", "tumor_markers")

    # Save to file for frontend consumption
    print("\n" + "="*80)
    print("Saving data to file...")
    with open("lab_data_for_ui.json", "w") as f:
        json.dump(ui_data, f, indent=2)
    print("Data saved to lab_data_for_ui.json")

    return processed_data, ui_data


if __name__ == "__main__":
    run_complete_example()
