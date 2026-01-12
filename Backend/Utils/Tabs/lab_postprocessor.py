"""
Postprocessing module for lab data extraction.
Cleans, deduplicates, and formats lab data for UI consumption.
"""

from typing import Dict, List, Any
from datetime import datetime


def is_empty_biomarker(biomarker_data: Dict) -> bool:
    """Check if a biomarker entry contains only NA/empty values."""
    current = biomarker_data.get("current", {})
    trend = biomarker_data.get("trend", [])

    # Check if current value is NA or empty
    value = current.get("value")
    is_current_empty = value == "NA" or value is None or value == ""

    # Check if trend is empty
    is_trend_empty = len(trend) == 0

    return is_current_empty and is_trend_empty


def merge_trends(trends_list: List[List[Dict]]) -> List[Dict]:
    """
    Merge multiple trend arrays, removing duplicates and sorting by date.

    Args:
        trends_list: List of trend arrays from different batches

    Returns:
        Consolidated, deduplicated, and sorted trend array
    """
    # Flatten all trends into a single list
    all_trends = []
    for trends in trends_list:
        all_trends.extend(trends)

    # Remove duplicates using a set of tuples (date, value)
    # Keep the entry with the most information
    seen = {}
    for trend in all_trends:
        date = trend.get("date")
        value = trend.get("value")

        # Skip entries with NA or missing date/value
        if date == "NA" or value == "NA" or date is None or value is None:
            continue

        key = (date, value)

        # If we haven't seen this combination, or this entry has more info, keep it
        if key not in seen or len(str(trend.get("source_context", ""))) > len(str(seen[key].get("source_context", ""))):
            seen[key] = trend

    # Convert back to list and sort by date
    unique_trends = list(seen.values())
    unique_trends.sort(key=lambda x: x.get("date", ""))

    return unique_trends


def merge_biomarker_data(biomarker_list: List[Dict]) -> Dict:
    """
    Merge multiple biomarker entries from different batches.

    Args:
        biomarker_list: List of biomarker dictionaries from different batches

    Returns:
        Consolidated biomarker dictionary with merged trends
    """
    # Find the entry with the most recent current value
    valid_entries = [b for b in biomarker_list if not is_empty_biomarker(b)]

    if not valid_entries:
        # Return a clean NA structure if all entries are empty
        return {
            "current": {
                "value": None,
                "unit": None,
                "date": None,
                "status": None,
                "reference_range": None
            },
            "trend": []
        }

    # Sort by date to get the most recent
    valid_entries.sort(key=lambda x: x.get("current", {}).get("date", ""), reverse=True)
    most_recent = valid_entries[0]

    # Collect all trends
    all_trends = [entry.get("trend", []) for entry in biomarker_list]
    merged_trends = merge_trends(all_trends)

    # Return merged result
    return {
        "current": most_recent.get("current", {}),
        "trend": merged_trends
    }


def consolidate_panel(panel_list: List[Dict], biomarker_names: List[str]) -> Dict:
    """
    Consolidate a panel (tumor_markers, CBC, or metabolic) from multiple batches.

    Args:
        panel_list: List of panel dictionaries from different batches
        biomarker_names: List of expected biomarker names in this panel

    Returns:
        Consolidated panel dictionary
    """
    consolidated = {}

    for biomarker_name in biomarker_names:
        # Collect this biomarker from all batches
        biomarker_entries = []
        for panel in panel_list:
            if biomarker_name in panel:
                biomarker_entries.append(panel[biomarker_name])

        if biomarker_entries:
            consolidated[biomarker_name] = merge_biomarker_data(biomarker_entries)

    return consolidated


def consolidate_clinical_interpretations(interpretations_list: List[List[str]]) -> List[str]:
    """
    Consolidate clinical interpretations, removing duplicates.

    Args:
        interpretations_list: List of interpretation arrays from different batches

    Returns:
        Unique interpretations list
    """
    all_interpretations = []
    for interps in interpretations_list:
        all_interpretations.extend(interps)

    # Remove duplicates while preserving order
    seen = set()
    unique_interpretations = []
    for interp in all_interpretations:
        # Clean up the interpretation text
        clean_interp = interp.strip()

        # Skip empty interpretations
        if not clean_interp:
            continue

        # Skip if we've seen this before (case-insensitive)
        if clean_interp.lower() not in seen:
            seen.add(clean_interp.lower())
            unique_interpretations.append(clean_interp)

    return unique_interpretations


def postprocess_lab_data(raw_lab_data: List[Dict]) -> Dict:
    """
    Main postprocessing function to consolidate and clean lab data.

    Args:
        raw_lab_data: Raw output from llmresponsedetailed (list of batch results)

    Returns:
        Clean, consolidated lab data ready for UI
    """
    # If raw_lab_data is a single dict (not a list), wrap it
    if isinstance(raw_lab_data, dict):
        raw_lab_data = [raw_lab_data]

    # Extract all tumor_markers, complete_blood_count, metabolic_panel, and clinical_interpretation
    # Handle two possible structures:
    # 1. Old structure: list of complete extractions, each with tumor_markers dict
    # 2. New structure: single dict with tumor_markers as a list of dicts
    tumor_markers_list = []
    cbc_list = []
    metabolic_list = []
    clinical_interp_list = []

    for batch in raw_lab_data:
        # Check if tumor_markers is a list (new API structure)
        if isinstance(batch.get("tumor_markers"), list):
            tumor_markers_list.extend(batch["tumor_markers"])
        elif isinstance(batch.get("tumor_markers"), dict):
            tumor_markers_list.append(batch["tumor_markers"])

        # Check if complete_blood_count is a list (new API structure)
        if isinstance(batch.get("complete_blood_count"), list):
            cbc_list.extend(batch["complete_blood_count"])
        elif isinstance(batch.get("complete_blood_count"), dict):
            cbc_list.append(batch["complete_blood_count"])

        # Check if metabolic_panel is a list (new API structure)
        if isinstance(batch.get("metabolic_panel"), list):
            metabolic_list.extend(batch["metabolic_panel"])
        elif isinstance(batch.get("metabolic_panel"), dict):
            metabolic_list.append(batch["metabolic_panel"])

        # Handle clinical_interpretation
        if isinstance(batch.get("clinical_interpretation"), list):
            clinical_interp_list.append(batch["clinical_interpretation"])

    # Consolidate each panel
    consolidated_tumor_markers = consolidate_panel(
        tumor_markers_list,
        ["CEA", "NSE", "proGRP", "CYFRA_21_1"]
    )

    consolidated_cbc = consolidate_panel(
        cbc_list,
        ["WBC", "Hemoglobin", "Platelets", "ANC"]
    )

    consolidated_metabolic = consolidate_panel(
        metabolic_list,
        ["Creatinine", "ALT", "AST", "Total Bilirubin"]
    )

    # Consolidate clinical interpretations
    consolidated_interpretations = consolidate_clinical_interpretations(clinical_interp_list)

    # Return clean structure
    return {
        "tumor_markers": consolidated_tumor_markers,
        "complete_blood_count": consolidated_cbc,
        "metabolic_panel": consolidated_metabolic,
        "clinical_interpretation": consolidated_interpretations
    }


def format_for_ui(consolidated_data: Dict) -> Dict:
    """
    Format consolidated data specifically for UI consumption.
    Adds helpful metadata and flags.

    Args:
        consolidated_data: Output from postprocess_lab_data

    Returns:
        UI-ready formatted data
    """
    def format_biomarker(biomarker_data: Dict, name: str) -> Dict:
        """Format individual biomarker with UI-friendly fields."""
        current = biomarker_data.get("current", {})
        trend = biomarker_data.get("trend", [])

        # Determine if data is available
        has_data = current.get("value") not in [None, "NA", ""]

        return {
            "name": name,
            "has_data": has_data,
            "current": {
                "value": current.get("value"),
                "unit": current.get("unit"),
                "date": current.get("date"),
                "status": current.get("status"),
                "reference_range": current.get("reference_range"),
                "is_abnormal": current.get("status") in ["High", "Low", "Critical"]
            },
            "trend": trend,
            "trend_direction": calculate_trend_direction(trend) if len(trend) >= 2 else None
        }

    def calculate_trend_direction(trend: List[Dict]) -> str:
        """Calculate if trend is increasing, decreasing, or stable."""
        if len(trend) < 2:
            return "insufficient_data"

        # Get last two values
        try:
            last_value = float(trend[-1].get("value", 0))
            prev_value = float(trend[-2].get("value", 0))

            # Calculate percentage change
            if prev_value != 0:
                pct_change = ((last_value - prev_value) / prev_value) * 100

                if pct_change > 5:
                    return "increasing"
                elif pct_change < -5:
                    return "decreasing"
                else:
                    return "stable"
            else:
                return "insufficient_data"
        except (ValueError, TypeError):
            return "insufficient_data"

    # Format each panel with safety checks
    def safe_get_panel(panel_name):
        """Safely get panel data, ensuring it's a dict."""
        panel = consolidated_data.get(panel_name, {})
        return panel if isinstance(panel, dict) else {}

    formatted = {
        "tumor_markers": {
            name: format_biomarker(data, name)
            for name, data in safe_get_panel("tumor_markers").items()
            if isinstance(data, dict)
        },
        "complete_blood_count": {
            name: format_biomarker(data, name)
            for name, data in safe_get_panel("complete_blood_count").items()
            if isinstance(data, dict)
        },
        "metabolic_panel": {
            name: format_biomarker(data, name)
            for name, data in safe_get_panel("metabolic_panel").items()
            if isinstance(data, dict)
        },
        "clinical_interpretation": consolidated_data.get("clinical_interpretation", []),
        "summary": {
            "total_abnormal": sum(
                1 for panel_name in ["tumor_markers", "complete_blood_count", "metabolic_panel"]
                for biomarker in safe_get_panel(panel_name).values()
                if isinstance(biomarker, dict) and biomarker.get("current", {}).get("status") in ["High", "Low", "Critical"]
            ),
            "last_updated": get_most_recent_date(consolidated_data)
        }
    }

    return formatted


def get_most_recent_date(data: Dict) -> str:
    """Get the most recent date across all biomarkers."""
    all_dates = []

    for panel_name in ["tumor_markers", "complete_blood_count", "metabolic_panel"]:
        panel = data.get(panel_name, {})

        # Ensure panel is a dict
        if not isinstance(panel, dict):
            continue

        for biomarker in panel.values():
            # Ensure biomarker is a dict
            if not isinstance(biomarker, dict):
                continue

            date = biomarker.get("current", {}).get("date")
            if date and date != "NA":
                all_dates.append(date)

    if all_dates:
        all_dates.sort(reverse=True)
        return all_dates[0]

    return None


# Convenience function that does both consolidation and formatting
def process_lab_data_for_ui(raw_lab_data: List[Dict]) -> Dict:
    """
    Complete pipeline: consolidate raw data and format for UI.

    Args:
        raw_lab_data: Raw output from llmresponsedetailed

    Returns:
        Clean, formatted data ready for UI rendering
    """
    try:
        consolidated = postprocess_lab_data(raw_lab_data)
        formatted = format_for_ui(consolidated)
        return formatted
    except Exception as e:
        import traceback
        print(f"\n{'='*70}")
        print(f"ERROR in process_lab_data_for_ui:")
        print(f"{'='*70}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        traceback.print_exc()
        print(f"{'='*70}\n")
        raise
