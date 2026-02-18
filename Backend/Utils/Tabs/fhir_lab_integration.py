"""
FHIR Observation API Integration Module

This module fetches laboratory data from the FHIR Observation API and converts it
to the same schema as LLM-extracted data for seamless integration.

The FHIR data is merged with LLM data before postprocessing, with date-based
deduplication to avoid duplicate entries.
"""

import requests
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from Backend.Utils.logger_config import setup_logger

# Setup logger
logger = setup_logger(__name__)

# Mapping of LOINC codes to biomarker names
LOINC_TO_BIOMARKER = {
    # Tumor Markers
    "2039-6": "CEA",  # Carcinoembryonic antigen
    "9679-7": "NSE",  # Neuron specific enolase
    "30166-8": "proGRP",  # Pro-Gastrin-Releasing Peptide
    "15158-9": "CYFRA_21_1",  # Cytokeratin 19 fragment

    # Complete Blood Count
    "6690-2": "WBC",  # Leukocytes [#/volume] in Blood by Automated count
    "789-8": "WBC",  # Erythrocytes [#/volume] in Blood by Automated count (alternative)
    "718-7": "Hemoglobin",  # Hemoglobin [Mass/volume] in Blood
    "777-3": "Platelets",  # Platelets [#/volume] in Blood by Automated count
    "751-8": "ANC",  # Neutrophils [#/volume] in Blood by Automated count
    "26499-4": "ANC",  # Neutrophils [#/volume] in Blood (alternative)

    # Metabolic Panel
    "2160-0": "Creatinine",  # Creatinine [Mass/volume] in Serum or Plasma
    "1742-6": "ALT",  # Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma
    "1920-8": "AST",  # Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma
    "1975-2": "Total Bilirubin",  # Bilirubin.total [Mass/volume] in Serum or Plasma
    "14631-6": "Total Bilirubin",  # Bilirubin.total [Moles/volume] in Serum or Plasma
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
    Fetch laboratory observations from FHIR Observation API.

    Args:
        patient_id: FHIR patient ID
        onco_emr_token: OncoEMR access token for authentication
        category: Observation category (default: "laboratory")
        url: FHIR Observation endpoint URL

    Returns:
        List of observation entries from FHIR API

    Raises:
        requests.RequestException: If API request fails
    """
    logger.info(f"🔍 Fetching FHIR Observations for patient: {patient_id}")

    params = {
        "patient": patient_id,
        "category": category,
        "_summary": "true"
    }

    headers = {
        "Authorization": f"Bearer {onco_emr_token}",
        "Accept": "application/fhir+json"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        # Add rate limiting delay
        time.sleep(1.5)

        data = response.json()
        entries = data.get("entry", [])

        logger.info(f"✅ Fetched {len(entries)} FHIR Observations")
        return entries

    except requests.RequestException as e:
        logger.error(f"❌ Failed to fetch FHIR Observations: {e}")
        return []


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


def map_loinc_to_biomarker(loinc_code: str, display_name: str) -> Optional[str]:
    """
    Map LOINC code or display name to standardized biomarker name.

    Args:
        loinc_code: LOINC code from FHIR
        display_name: Display name from FHIR coding

    Returns:
        Standardized biomarker name or None if not recognized
    """
    # First try direct LOINC mapping
    if loinc_code in LOINC_TO_BIOMARKER:
        return LOINC_TO_BIOMARKER[loinc_code]

    # Try fuzzy matching on display name
    if not display_name:
        return None

    display_upper = display_name.upper()

    # Tumor markers
    if "CEA" in display_upper or "CARCINOEMBRYONIC" in display_upper:
        return "CEA"
    if "NSE" in display_upper or "NEURON SPECIFIC ENOLASE" in display_upper:
        return "NSE"
    if "PROGRP" in display_upper or "PRO-GASTRIN" in display_upper:
        return "proGRP"
    if "CYFRA" in display_upper or "CYTOKERATIN 19" in display_upper:
        return "CYFRA_21_1"

    # CBC
    if "WBC" in display_upper or "LEUKOCYTE" in display_upper or "WHITE BLOOD" in display_upper:
        return "WBC"
    if "HEMOGLOBIN" in display_upper or "HGB" in display_upper:
        return "Hemoglobin"
    if "PLATELET" in display_upper or "PLT" in display_upper:
        return "Platelets"
    if "NEUTROPHIL" in display_upper and ("ABSOLUTE" in display_upper or "ANC" in display_upper):
        return "ANC"

    # Metabolic
    if "CREATININE" in display_upper:
        return "Creatinine"
    if "ALT" in display_upper or "ALANINE AMINOTRANSFERASE" in display_upper:
        return "ALT"
    if "AST" in display_upper or "ASPARTATE AMINOTRANSFERASE" in display_upper:
        return "AST"
    if "BILIRUBIN" in display_upper and ("TOTAL" in display_upper or display_upper.strip() == "BILIRUBIN"):
        return "Total Bilirubin"

    return None


def convert_fhir_observations_to_lab_schema(
    fhir_entries: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Convert FHIR Observation entries to the same schema as Gemini-extracted lab data.

    The output schema matches the flat schema used by Gemini:
    {
        "tumor_markers": {
            "CEA": {"value": ..., "unit": ..., "date": ..., "status": ..., "reference_range": ..., "source_context": ...},
            ...
        },
        "complete_blood_count": {...},
        "metabolic_panel": {...},
        "clinical_interpretation": []
    }

    Args:
        fhir_entries: List of FHIR Observation entry dictionaries

    Returns:
        Dictionary with lab data in Gemini schema format
    """
    logger.info(f"🔄 Converting {len(fhir_entries)} FHIR Observations to lab schema")

    # Initialize result structure
    result = {
        "tumor_markers": {},
        "complete_blood_count": {},
        "metabolic_panel": {},
        "clinical_interpretation": []
    }

    # Track biomarkers we've seen (for deduplication by date - keep most recent)
    biomarker_data = {}  # biomarker_name -> list of measurements

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

        # Extract LOINC code and display name
        code = resource.get("code", {})
        codings = code.get("coding", [])

        loinc_code = None
        display_name = None

        for coding in codings:
            if coding.get("system") == "http://loinc.org":
                loinc_code = coding.get("code")
                display_name = coding.get("display")
                break

        if not loinc_code:
            continue

        # Map to biomarker name
        biomarker_name = map_loinc_to_biomarker(loinc_code, display_name)
        if not biomarker_name:
            continue

        # Extract value and unit
        value, unit = extract_value_and_unit(resource)
        if value is None:
            continue

        # Extract reference range
        reference_range = extract_reference_range(resource)

        # Determine status
        status = determine_status(value, reference_range)

        # Create biomarker entry
        biomarker_entry = {
            "value": value,
            "unit": unit,
            "date": normalized_date,
            "status": status,
            "reference_range": reference_range,
            "source_context": "FHIR_API - Laboratory Observation"
        }

        # Store in biomarker_data for later aggregation
        if biomarker_name not in biomarker_data:
            biomarker_data[biomarker_name] = []
        biomarker_data[biomarker_name].append(biomarker_entry)

    # Aggregate biomarkers: keep most recent for each biomarker
    for biomarker_name, entries in biomarker_data.items():
        # Sort by date descending to get most recent
        entries.sort(key=lambda x: x["date"], reverse=True)
        most_recent = entries[0]

        # Determine which panel this biomarker belongs to
        panel = None
        for panel_name, biomarkers in BIOMARKER_CATEGORIES.items():
            if biomarker_name in biomarkers:
                panel = panel_name
                break

        if panel:
            result[panel][biomarker_name] = most_recent

    logger.info(f"✅ Converted FHIR Observations:")
    logger.info(f"   - Tumor Markers: {len(result['tumor_markers'])} biomarkers")
    logger.info(f"   - CBC: {len(result['complete_blood_count'])} biomarkers")
    logger.info(f"   - Metabolic Panel: {len(result['metabolic_panel'])} biomarkers")

    return result


def merge_lab_data_with_fhir(
    llm_data: List[Dict[str, Any]],
    fhir_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Merge FHIR Observation data with LLM-extracted data.

    The merge strategy:
    1. LLM data is a list of extractions (one per document)
    2. FHIR data is a single extraction with most recent values
    3. Add FHIR data as an additional "document" in the list
    4. The postprocessor will handle deduplication by date

    Args:
        llm_data: List of lab data dictionaries from LLM extraction
        fhir_data: Lab data dictionary from FHIR API

    Returns:
        Merged list of lab data dictionaries
    """
    logger.info(f"🔄 Merging LLM data ({len(llm_data)} documents) with FHIR data")

    # Check if FHIR data has any biomarkers
    has_fhir_data = False
    for panel_name in ["tumor_markers", "complete_blood_count", "metabolic_panel"]:
        if fhir_data.get(panel_name):
            has_fhir_data = True
            break

    if not has_fhir_data:
        logger.info("ℹ️  No FHIR data to merge, returning LLM data only")
        return llm_data

    # Add FHIR data to the list
    merged_data = llm_data + [fhir_data]

    logger.info(f"✅ Merged data: {len(merged_data)} total documents (LLM + FHIR)")
    return merged_data
