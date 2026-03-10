"""
FHIR Observation API Integration Module

This module fetches laboratory data from the FHIR Observation API and converts it
to the same schema as LLM-extracted data for seamless integration.

The FHIR data is merged with LLM data before postprocessing, with date-based
deduplication to avoid duplicate entries.
"""

import requests
import time
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from Backend.Utils.logger_config import setup_logger
from Backend.Utils.Tabs.lab_unit_converter import convert_to_standard_unit

# Setup logger
logger = setup_logger(__name__)

# Regex patterns for biomarker matching (case-insensitive)
# These patterns match against the display name or text field from FHIR observations
BIOMARKER_PATTERNS = {
    # Tumor Markers
    "CEA": [
        r"\bCEA\b",
        r"carcinoembryonic\s+antigen",
    ],
    "NSE": [
        r"\bNSE\b",
        r"neuron\s+specific\s+enolase",
        r"neuron[-\s]specific[-\s]enolase",
    ],
    "proGRP": [
        r"\bproGRP\b",
        r"pro[-\s]?gastrin[-\s]?releasing\s+peptide",
        r"\bpro\s*GRP\b",
    ],
    "CYFRA_21_1": [
        r"\bCYFRA\b",
        r"CYFRA\s*21[-\s]?1",
        r"cytokeratin\s+19\s+fragment",
        r"cytokeratin[-\s]19[-\s]fragment",
    ],

    # Complete Blood Count
    "WBC": [
        r"\bWBC\b",
        r"\bwhite\s+blood\s+cell",
        r"\bleukocytes?\b",
        r"white\s+cell\s+count",
    ],
    "Hemoglobin": [
        r"\bhemoglobin\b",
        r"\bhaemoglobin\b",
        r"\bHGB\b",
        r"\bHgb\b",
        r"\bHb\b(?!A1c)",  # Match Hb but not HbA1c
    ],
    "Platelets": [
        r"\bplatelets?\b",
        r"\bPLT\b",
        r"platelet\s+count",
    ],
    "ANC": [
        r"\bANC\b",
        r"absolute\s+neutrophil\s+count",
        r"neutrophils?\s+(?:absolute|abs)",
        r"(?:segs|polys)(?:\s+|,\s*)(?:absolute|abs)",
    ],

    # Metabolic Panel
    "Creatinine": [
        r"\bcreatinine\b(?!\s*clearance)(?!\s*ratio)",  # Match creatinine but not clearance or ratio
        r"\bcreat\b",
        r"\bCr\b(?!\s*clearance)",
    ],
    "ALT": [
        r"\bALT\b",
        r"alanine\s+aminotransferase",
        r"\bSGPT\b",
        r"alanine\s+transaminase",
    ],
    "AST": [
        r"\bAST\b",
        r"aspartate\s+aminotransferase",
        r"\bSGOT\b",
        r"aspartate\s+transaminase",
    ],
    "Total Bilirubin": [
        r"(?:total\s+)?bilirubin(?:\s+total)?",
        r"\bT\.?\s*Bili\b",
        r"\bTBIL\b",
        r"\bbili\b(?!\s*direct)(?!\s*indirect)",
    ],
}

# Biomarker categories for organizing data
BIOMARKER_CATEGORIES = {
    "tumor_markers": ["CEA", "NSE", "proGRP", "CYFRA_21_1"],
    "complete_blood_count": ["WBC", "Hemoglobin", "Platelets", "ANC"],
    "metabolic_panel": ["Creatinine", "ALT", "AST", "Total Bilirubin"]
}


def fetch_fhir_observations(
    patient_id: str,
    onco_emr_token: str,
    category: str = "laboratory",
    url: str = "https://fhir.prod.flatiron.io/fhir/Observation"
) -> List[Dict[str, Any]]:
    """
    Fetch ALL laboratory observations from FHIR Observation API with pagination support.

    Args:
        patient_id: FHIR patient ID
        onco_emr_token: OncoEMR access token for authentication
        category: Observation category (default: "laboratory")
        url: FHIR Observation endpoint URL

    Returns:
        List of ALL observation entries from FHIR API (aggregated across all pages)

    Raises:
        requests.RequestException: If API request fails
    """
    logger.info(f"🔍 Fetching FHIR Observations for patient: {patient_id}")

    params = {
        "patient": patient_id,
        "category": category,
        "_count": 100  # Fetch 100 observations per page
    }

    headers = {
        "Authorization": f"Bearer {onco_emr_token}",
        "Accept": "application/fhir+json"
    }

    all_entries = []
    current_url = url
    page_count = 0

    try:
        while current_url:
            page_count += 1
            logger.info(f"📄 Fetching page {page_count}...")

            # Make request
            if page_count == 1:
                response = requests.get(current_url, headers=headers, params=params)
            else:
                # For subsequent pages, use the next link directly (no params)
                response = requests.get(current_url, headers=headers)

            response.raise_for_status()

            # Add rate limiting delay
            time.sleep(1.5)

            data = response.json()
            entries = data.get("entry", [])
            all_entries.extend(entries)

            logger.info(f"✅ Page {page_count}: Fetched {len(entries)} observations (Total so far: {len(all_entries)})")

            # Check for next page link
            links = data.get("link", [])
            next_link = None
            for link in links:
                if link.get("relation") == "next":
                    next_link = link.get("url")
                    break

            if next_link:
                current_url = next_link
                logger.info(f"🔗 Next page found, continuing...")
            else:
                logger.info(f"✅ No more pages. Pagination complete.")
                break

        total = data.get("total", len(all_entries))
        logger.info(f"✅ Fetched {len(all_entries)} FHIR Observations out of {total} total")
        return all_entries

    except requests.RequestException as e:
        logger.error(f"❌ Failed to fetch FHIR Observations: {e}")
        return all_entries if all_entries else []


def normalize_date_from_fhir(date_str: str) -> Optional[str]:
    """
    Normalize FHIR date to YYYY-MM-DD format.

    Args:
        date_str: Date string from FHIR (ISO format or other)

    Returns:
        Normalized date string in YYYY-MM-DD format, or None if parsing fails
    """
    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip()

    # Try parsing ISO format with timezone
    try:
        # Handle ISO format: 2025-12-15T10:30:00Z or 2025-12-15T10:30:00+00:00
        if 'T' in date_str:
            # Remove timezone info for parsing
            date_part = date_str.split('T')[0]
            dt = datetime.strptime(date_part, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        else:
            # Already in YYYY-MM-DD format
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        logger.warning(f"Failed to parse date: {date_str}")
        return None


def extract_value_and_unit(observation: Dict[str, Any]) -> tuple[Optional[float], Optional[str]]:
    """
    Extract value and unit from FHIR Observation resource.

    Args:
        observation: FHIR Observation resource dict

    Returns:
        Tuple of (value, unit) where value is float or None, unit is string or None
    """
    # Check for valueQuantity (most common for lab results)
    value_quantity = observation.get("valueQuantity", {})
    if value_quantity:
        value = value_quantity.get("value")
        unit = value_quantity.get("unit") or value_quantity.get("code")  # Use unit text or code

        # Try to convert value to float
        try:
            numeric_value = float(value) if value is not None else None
            return numeric_value, unit
        except (ValueError, TypeError):
            return None, unit

    # Check for valueString (less common but possible)
    value_string = observation.get("valueString")
    if value_string:
        try:
            numeric_value = float(value_string)
            return numeric_value, None  # No unit available in valueString
        except (ValueError, TypeError):
            return None, None

    # Check for valueInteger
    value_integer = observation.get("valueInteger")
    if value_integer is not None:
        return float(value_integer), None

    # Check for valueDecimal
    value_decimal = observation.get("valueDecimal")
    if value_decimal is not None:
        return float(value_decimal), None

    return None, None


def determine_status(
    value: Optional[float],
    reference_range: Optional[str]
) -> str:
    """
    Determine status (Normal/High/Low) based on value and reference range.

    Args:
        value: Numeric value
        reference_range: Reference range string (e.g., "10-20", "<5", ">100")

    Returns:
        Status string: "Normal", "High", "Low", or "Unknown"
    """
    if value is None or not reference_range:
        return "Unknown"

    # Simple parsing for common reference range formats
    # Format examples: "10-20", "10 - 20", "<5", ">100", "<=10", ">=5"

    import re

    # Try to extract low and high values
    range_match = re.search(r'([\d.]+)\s*-\s*([\d.]+)', reference_range)
    if range_match:
        try:
            low = float(range_match.group(1))
            high = float(range_match.group(2))

            if value < low:
                return "Low"
            elif value > high:
                return "High"
            else:
                return "Normal"
        except (ValueError, TypeError):
            pass

    # Check for less than (<) or less than or equal (<=)
    less_match = re.search(r'<\s*=?\s*([\d.]+)', reference_range)
    if less_match:
        try:
            threshold = float(less_match.group(1))
            if value <= threshold:
                return "Normal"
            else:
                return "High"
        except (ValueError, TypeError):
            pass

    # Check for greater than (>) or greater than or equal (>=)
    greater_match = re.search(r'>\s*=?\s*([\d.]+)', reference_range)
    if greater_match:
        try:
            threshold = float(greater_match.group(1))
            if value >= threshold:
                return "Normal"
            else:
                return "Low"
        except (ValueError, TypeError):
            pass

    return "Unknown"


def extract_reference_range(observation: Dict[str, Any]) -> Optional[str]:
    """
    Extract reference range from FHIR Observation resource.

    Args:
        observation: FHIR Observation resource dict

    Returns:
        Reference range string or None
    """
    reference_ranges = observation.get("referenceRange", [])
    if not reference_ranges:
        return None

    # Get first reference range
    ref_range = reference_ranges[0]

    # Try to construct range from low and high
    low = ref_range.get("low", {}).get("value")
    high = ref_range.get("high", {}).get("value")
    unit = ref_range.get("low", {}).get("unit") or ref_range.get("high", {}).get("unit")

    if low is not None and high is not None:
        if unit:
            return f"{low}-{high} {unit}"
        else:
            return f"{low}-{high}"
    elif low is not None:
        if unit:
            return f">={low} {unit}"
        else:
            return f">={low}"
    elif high is not None:
        if unit:
            return f"<={high} {unit}"
        else:
            return f"<={high}"

    # Try text representation
    text = ref_range.get("text")
    if text:
        return text

    return None


def match_biomarker_by_regex(display_text: str) -> Optional[str]:
    """
    Match a biomarker using regex patterns on the display text.

    This approach is more flexible than LOINC code mapping because:
    - Display names are more consistent across systems
    - Can handle variations in naming conventions
    - Doesn't require maintaining a large LOINC code dictionary

    Args:
        display_text: Display name or text description from FHIR observation

    Returns:
        Standardized biomarker name or None if not recognized
    """
    if not display_text:
        return None

    # Clean the text for better matching
    text = display_text.strip()

    # Try to match each biomarker's patterns
    for biomarker_name, patterns in BIOMARKER_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                logger.debug(f"✅ Matched '{text}' to {biomarker_name} using pattern: {pattern}")
                return biomarker_name

    return None


def convert_fhir_observations_to_lab_schema(
    fhir_entries: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Convert FHIR Observation entries to a list of lab data dictionaries grouped by date.

    Each unique date gets its own dictionary with all biomarkers measured on that date.
    This preserves complete temporal data for trend analysis.

    Output format: List of dictionaries, one per unique date:
    [
        {
            "tumor_markers": {"CEA": {...}, ...},
            "complete_blood_count": {"WBC": {...}, ...},
            "metabolic_panel": {"Creatinine": {...}, ...},
            "clinical_interpretation": []
        },
        ... (one dict per unique measurement date)
    ]

    Args:
        fhir_entries: List of FHIR Observation entry dictionaries

    Returns:
        List of lab data dictionaries (one per unique date) in Gemini schema format
    """
    logger.info(f"🔄 Converting {len(fhir_entries)} FHIR Observations to lab schema")

    # Group observations by date to preserve complete temporal data
    observations_by_date = {}  # date -> {biomarker_name -> biomarker_entry}

    for entry in fhir_entries:
        resource = entry.get("resource", {})

        # Extract effective date
        effective_date = (
            resource.get("effectiveDateTime") or
            resource.get("effectivePeriod", {}).get("start") or
            resource.get("issued")
        )

        if not effective_date:
            continue

        normalized_date = normalize_date_from_fhir(effective_date)
        if not normalized_date:
            continue

        # Extract display text from observation
        code = resource.get("code", {})

        # Try to get display text from multiple sources (in order of preference)
        display_text = None

        # 1. Check code.text (often the most descriptive)
        display_text = code.get("text")

        # 2. If not found, check LOINC coding display
        if not display_text:
            codings = code.get("coding", [])
            for coding in codings:
                if coding.get("system") == "http://loinc.org":
                    display_text = coding.get("display")
                    break

        # 3. If still not found, try any coding display
        if not display_text:
            codings = code.get("coding", [])
            if codings:
                display_text = codings[0].get("display")

        if not display_text:
            continue

        # Match biomarker using regex patterns
        biomarker_name = match_biomarker_by_regex(display_text)
        if not biomarker_name:
            continue

        # Extract value and unit
        value, unit = extract_value_and_unit(resource)
        if value is None:
            continue

        # Apply unit conversion to standard unit
        converted_value, standard_unit = convert_to_standard_unit(value, unit, biomarker_name)

        # Log conversion if unit changed
        if unit and unit != standard_unit:
            logger.debug(f"🔄 Converted {biomarker_name}: {value} {unit} → {converted_value} {standard_unit}")

        # Extract reference range
        reference_range = extract_reference_range(resource)

        # Determine status
        status = determine_status(converted_value, reference_range)

        # Create biomarker entry
        biomarker_entry = {
            "value": converted_value,
            "unit": standard_unit,
            "date": normalized_date,
            "status": status,
            "reference_range": reference_range,
            "source_context": "FHIR_API - Laboratory Observation"
        }

        # Group by date to preserve complete temporal data
        if normalized_date not in observations_by_date:
            observations_by_date[normalized_date] = {}

        # Store biomarker for this date (if duplicate on same date, keep latest processed)
        observations_by_date[normalized_date][biomarker_name] = biomarker_entry

    # Convert grouped observations to list of lab data dicts (one per date)
    result_list = []

    for date in sorted(observations_by_date.keys(), reverse=True):  # Most recent first
        # Initialize panels for this date
        date_result = {
            "tumor_markers": {},
            "complete_blood_count": {},
            "metabolic_panel": {},
            "clinical_interpretation": []
        }

        # Organize biomarkers by panel for this date
        for biomarker_name, biomarker_entry in observations_by_date[date].items():
            panel = None
            for panel_name, biomarkers in BIOMARKER_CATEGORIES.items():
                if biomarker_name in biomarkers:
                    panel = panel_name
                    break

            if panel:
                date_result[panel][biomarker_name] = biomarker_entry

        result_list.append(date_result)

    # Calculate total observations per panel
    total_tm = sum(len(r["tumor_markers"]) for r in result_list)
    total_cbc = sum(len(r["complete_blood_count"]) for r in result_list)
    total_mp = sum(len(r["metabolic_panel"]) for r in result_list)

    logger.info(f"✅ Converted FHIR Observations into {len(result_list)} date groups:")
    logger.info(f"   - Total Tumor Marker observations: {total_tm}")
    logger.info(f"   - Total CBC observations: {total_cbc}")
    logger.info(f"   - Total Metabolic Panel observations: {total_mp}")

    return result_list


def merge_lab_data_with_fhir(
    llm_data: List[Dict[str, Any]],
    fhir_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Merge FHIR Observation data with LLM-extracted data.

    The merge strategy:
    1. LLM data is a list of extractions (one per PDF document)
    2. FHIR data is now also a list (one dict per unique date with all observations from that date)
    3. Combine both lists
    4. The postprocessor will handle deduplication by date

    Args:
        llm_data: List of lab data dictionaries from LLM extraction
        fhir_data: List of lab data dictionaries from FHIR API (grouped by date)

    Returns:
        Merged list of lab data dictionaries
    """
    logger.info(f"🔄 Merging LLM data ({len(llm_data)} documents) with FHIR data ({len(fhir_data)} date groups)")

    # Check if FHIR data has any biomarkers
    if not fhir_data:
        logger.info("ℹ️  No FHIR data to merge, returning LLM data only")
        return llm_data

    # Combine both lists
    merged_data = llm_data + fhir_data

    logger.info(f"✅ Merged data: {len(merged_data)} total documents (LLM + FHIR)")
    return merged_data
