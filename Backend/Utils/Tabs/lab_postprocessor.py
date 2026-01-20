"""
Postprocessing module for lab data extraction.
Aggregates individual document extractions into trends and formats for UI consumption.

NEW ARCHITECTURE (Post-Refactor):
- Gemini extracts current values from ONE document at a time
- Post-processor builds trends by aggregating these single-document extractions
- This improves accuracy by giving Gemini simpler tasks
"""

from typing import Dict, List, Any
from datetime import datetime
import json
import vertexai
from vertexai.generative_models import GenerativeModel

# Initialize Vertex AI
vertexai.init(project="prior-auth-portal-dev", location="us-central1")


def is_empty_biomarker(biomarker_data: Dict) -> bool:
    """
    Check if a biomarker entry contains only NA/empty values.
    Updated to work with new flat schema (no nested 'current' object).
    """
    # Handle both old nested format and new flat format for backward compatibility
    if "current" in biomarker_data:
        # Old format: {"current": {...}, "trend": [...]}
        value = biomarker_data.get("current", {}).get("value")
    else:
        # New format: {"value": ..., "unit": ..., "date": ...}
        value = biomarker_data.get("value")

    is_value_empty = value == "NA" or value is None or value == ""
    return is_value_empty


def build_trend_from_values(biomarker_entries: List[Dict]) -> List[Dict]:
    """
    Build trend array from multiple single-document extractions.

    NEW APPROACH: Each entry represents one document's extraction.
    We aggregate them into a chronological trend.

    Args:
        biomarker_entries: List of biomarker dictionaries from different documents
                          Each is a flat dict: {value, unit, date, status, reference_range, source_context}

    Returns:
        Sorted trend array with deduplicated entries
    """
    trend = []
    seen = {}  # Track (date, value) combinations to avoid duplicates

    for entry in biomarker_entries:
        # Handle both old nested format and new flat format
        if "current" in entry:
            # Old format: {"current": {...}, "trend": [...]}
            data = entry.get("current", {})
        else:
            # New format: {"value": ..., "unit": ..., "date": ...}
            data = entry

        date = data.get("date")
        value = data.get("value")

        # Skip entries with NA or missing date/value
        if date == "NA" or value == "NA" or date is None or value is None or value == "":
            continue

        key = (date, value)

        # If we haven't seen this combination, or this entry has more info, keep it
        if key not in seen or len(str(data.get("source_context", ""))) > len(str(seen[key].get("source_context", ""))):
            seen[key] = {
                "date": date,
                "value": value,
                "status": data.get("status"),
                "source_context": data.get("source_context", "")
            }

    # Convert to list and sort by date (oldest to newest)
    trend = list(seen.values())
    trend.sort(key=lambda x: x.get("date", ""))

    return trend


def merge_biomarker_data(biomarker_list: List[Dict]) -> Dict:
    """
    Aggregate biomarker entries from multiple documents into current + trend structure.

    NEW APPROACH: Each entry in biomarker_list is from a different document.
    We build the trend from all these single-document extractions.

    Args:
        biomarker_list: List of biomarker dictionaries from different documents
                       Each is either:
                       - New format: {value, unit, date, status, reference_range, source_context}
                       - Old format: {"current": {...}, "trend": [...]}

    Returns:
        Consolidated biomarker with structure:
        {
            "current": {most recent value data},
            "trend": [{historical values sorted by date}]
        }
    """
    # Filter out empty entries
    valid_entries = [b for b in biomarker_list if not is_empty_biomarker(b)]

    if not valid_entries:
        # Return clean empty structure
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

    # Build trend from all entries
    trend = build_trend_from_values(valid_entries)

    # Find most recent entry for "current"
    # Handle both old and new formats
    sorted_entries = []
    for entry in valid_entries:
        if "current" in entry:
            # Old format
            date = entry.get("current", {}).get("date", "")
            sorted_entries.append((date, entry.get("current", {})))
        else:
            # New format
            date = entry.get("date", "")
            sorted_entries.append((date, entry))

    # Sort by date descending to get most recent
    sorted_entries.sort(key=lambda x: x[0], reverse=True)
    most_recent_data = sorted_entries[0][1] if sorted_entries else {}

    # Return unified structure
    return {
        "current": {
            "value": most_recent_data.get("value"),
            "unit": most_recent_data.get("unit"),
            "date": most_recent_data.get("date"),
            "status": most_recent_data.get("status"),
            "reference_range": most_recent_data.get("reference_range")
        },
        "trend": trend
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


def refine_clinical_interpretations_with_ai(
    raw_interpretations: List[str],
    consolidated_data: Dict
) -> List[str]:
    """
    Use Gemini to refine and enhance clinical interpretations based on lab data.

    Args:
        raw_interpretations: List of raw interpretation strings
        consolidated_data: Consolidated lab data with current values and trends

    Returns:
        Refined list of clinical interpretations
    """
    if not raw_interpretations:
        return []

    # Extract current lab values for context
    lab_summary = {}

    for panel_name in ["tumor_markers", "complete_blood_count", "metabolic_panel"]:
        panel_data = consolidated_data.get(panel_name, {})
        lab_summary[panel_name] = {}

        for biomarker_name, biomarker_data in panel_data.items():
            current = biomarker_data.get("current", {})
            trend = biomarker_data.get("trend", [])

            lab_summary[panel_name][biomarker_name] = {
                "current_value": current.get("value"),
                "current_unit": current.get("unit"),
                "current_date": current.get("date"),
                "current_status": current.get("status"),
                "reference_range": current.get("reference_range"),
                "trend_count": len(trend),
                "has_data": current.get("value") not in [None, "NA", ""]
            }

    # Build prompt for Gemini
    prompt = f"""You are a clinical oncology expert reviewing laboratory results for a cancer patient.

I have extracted raw clinical interpretations from multiple lab reports. Your task is to refine these into a concise, well-organized clinical summary.

RAW INTERPRETATIONS:
{chr(10).join(f"- {interp}" for interp in raw_interpretations)}

CURRENT LAB VALUES SUMMARY:
{json.dumps(lab_summary, indent=2)}

INSTRUCTIONS:
1. Synthesize the raw interpretations into a coherent clinical summary
2. Organize by clinical significance (most important findings first)
3. Remove redundancies and contradictions
4. Use precise medical terminology
5. Focus on actionable findings relevant to cancer treatment
6. Include trend information where relevant
7. Keep each point concise (1-2 sentences maximum)
8. Return EXACTLY 4-6 most important clinical points (prioritize critical findings)

PRIORITIZATION RULES:
- Critical abnormalities (e.g., severe anemia, neutropenia requiring intervention) = Highest priority
- Treatment-limiting toxicities (e.g., hepatotoxicity, renal dysfunction) = High priority
- Tumor markers and disease monitoring = Medium-high priority
- Stable or normal findings with clinical context = Include only if space permits

OUTPUT FORMAT:
Return a JSON array of exactly 4-6 strings, each string being one refined clinical interpretation.
Example:
["Mild anemia (Hgb 10.2 g/dL) with stable trend over 3 measurements, consider transfusion if symptomatic", "Hepatic transaminases mildly elevated (ALT 58 U/L, AST 52 U/L) consistent with drug-induced liver injury, recommend monitoring", "Preserved bone marrow function (WBC 6.8 K/uL, ANC 3.8 K/uL, Platelets 185 K/uL) - safe to continue chemotherapy", "Renal function normal (Creatinine 0.9 mg/dL) - no dose adjustments required"]

Return ONLY the JSON array, no other text."""

    try:
        model = GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.3,
                "top_p": 0.95,
                "max_output_tokens": 1024
            }
        )

        response_text = response.text.strip()

        # Extract JSON from potential markdown code blocks
        import re
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, response_text)

        if match:
            response_text = match.group(1).strip()

        # Parse the JSON response
        refined_interpretations = json.loads(response_text)

        if isinstance(refined_interpretations, list) and all(isinstance(item, str) for item in refined_interpretations):
            # Validate count (should be 4-6 points)
            count = len(refined_interpretations)
            if count < 4 or count > 6:
                print(f"⚠️ AI returned {count} points (expected 4-6), trimming/keeping as is")
                if count > 6:
                    refined_interpretations = refined_interpretations[:6]  # Keep top 6
                # If less than 4, keep what we have

            print(f"✅ AI refinement successful: {len(refined_interpretations)} interpretations")
            return refined_interpretations
        else:
            print(f"⚠️ AI refinement returned invalid format, using raw interpretations")
            return raw_interpretations

    except Exception as e:
        print(f"❌ AI refinement failed: {str(e)}, using raw interpretations")
        return raw_interpretations


def postprocess_lab_data(raw_lab_data: List[Dict], use_ai_refinement: bool = True) -> Dict:
    """
    Main postprocessing function to consolidate and clean lab data.

    Args:
        raw_lab_data: Raw output from llmresponsedetailed (list of batch results)
        use_ai_refinement: Whether to use AI to refine clinical interpretations (default: True)

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

    # Optionally refine clinical interpretations with AI
    if use_ai_refinement and consolidated_interpretations:
        # Prepare consolidated data structure for AI refinement
        consolidated_data_for_ai = {
            "tumor_markers": consolidated_tumor_markers,
            "complete_blood_count": consolidated_cbc,
            "metabolic_panel": consolidated_metabolic
        }

        # Refine clinical interpretations with AI
        print(f"🤖 Refining {len(consolidated_interpretations)} clinical interpretations with AI...")
        refined_interpretations = refine_clinical_interpretations_with_ai(
            raw_interpretations=consolidated_interpretations,
            consolidated_data=consolidated_data_for_ai
        )
    else:
        refined_interpretations = consolidated_interpretations
        if not use_ai_refinement:
            print("ℹ️  AI refinement disabled, using raw interpretations")

    # Return clean structure
    return {
        "tumor_markers": consolidated_tumor_markers,
        "complete_blood_count": consolidated_cbc,
        "metabolic_panel": consolidated_metabolic,
        "clinical_interpretation": refined_interpretations
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
def process_lab_data_for_ui(raw_lab_data: List[Dict], use_ai_refinement: bool = True) -> Dict:
    """
    Complete pipeline: consolidate raw data and format for UI.

    Args:
        raw_lab_data: Raw output from llmresponsedetailed
        use_ai_refinement: Whether to use AI to refine clinical interpretations (default: True)

    Returns:
        Clean, formatted data ready for UI rendering
    """
    try:
        consolidated = postprocess_lab_data(raw_lab_data, use_ai_refinement=use_ai_refinement)
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
