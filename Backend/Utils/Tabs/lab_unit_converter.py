"""
Lab Unit Conversion Module

Provides standardized unit conversion for laboratory biomarkers to ensure
consistency between FHIR Observation API data and PDF-extracted lab data.

Standard Units:
- Tumor Markers: ng/mL (CEA, NSE, CYFRA 21-1), pg/mL (proGRP)
- CBC: 10^3/μL (WBC, Platelets, ANC), g/dL (Hemoglobin)
- Metabolic: mg/dL (Creatinine, Total Bilirubin), U/L (ALT, AST)
"""

from typing import Optional, Tuple
import re

# Standard units for each biomarker
STANDARD_UNITS = {
    # Tumor Markers
    "CEA": "ng/mL",
    "NSE": "ng/mL",
    "proGRP": "pg/mL",
    "CYFRA_21_1": "ng/mL",

    # Complete Blood Count
    "WBC": "10^3/μL",
    "Hemoglobin": "g/dL",
    "Platelets": "10^3/μL",
    "ANC": "10^3/μL",

    # Metabolic Panel
    "Creatinine": "mg/dL",
    "ALT": "U/L",
    "AST": "U/L",
    "Total Bilirubin": "mg/dL",
}


def normalize_unit_string(unit: str) -> str:
    """
    Normalize unit string for comparison by:
    - Converting to lowercase
    - Removing spaces
    - Standardizing common variations

    Args:
        unit: Raw unit string from source

    Returns:
        Normalized unit string
    """
    if not unit:
        return ""

    # Convert to lowercase and strip
    normalized = unit.lower().strip()

    # Standardize common variations
    replacements = {
        # Microliter variations
        "ul": "μl",
        "mcl": "μl",
        "/ul": "/μl",

        # Microgram/micromol variations
        "umol": "μmol",
        "mcmol": "μmol",

        # Thousands indicator variations
        "10*3": "10^3",
        "10**3": "10^3",
        "k/": "10^3/",
        "thousand/": "10^3/",
        "x10^3": "10^3",
        "x10e3": "10^3",
        "x 10^3": "10^3",

        # Remove spaces
        " ": "",
    }

    for old, new in replacements.items():
        normalized = normalized.replace(old, new)

    return normalized


def convert_to_standard_unit(
    value: Optional[float],
    source_unit: Optional[str],
    biomarker: str
) -> Tuple[Optional[float], str]:
    """
    Convert a lab value to its standard unit.

    Args:
        value: Numeric lab value
        source_unit: Source unit from data (can be None)
        biomarker: Biomarker name (e.g., "WBC", "Hemoglobin")

    Returns:
        Tuple of (converted_value, standard_unit)
        - If conversion fails or not needed, returns (original_value, standard_unit)
        - If value is None, returns (None, standard_unit)
    """
    # Get standard unit for this biomarker
    standard_unit = STANDARD_UNITS.get(biomarker)
    if not standard_unit:
        # Unknown biomarker, return as-is
        return value, source_unit or ""

    # If value is None, return with standard unit
    if value is None:
        return None, standard_unit

    # If no source unit provided, assume it's already in standard unit
    if not source_unit:
        return value, standard_unit

    # Normalize both units for comparison
    normalized_source = normalize_unit_string(source_unit)
    normalized_standard = normalize_unit_string(standard_unit)

    # If already in standard unit, no conversion needed
    if normalized_source == normalized_standard:
        return value, standard_unit

    # Apply biomarker-specific conversions
    converted_value = value

    # WBC, Platelets, ANC conversions
    if biomarker in ["WBC", "Platelets", "ANC"]:
        # If unit is /μL (no thousands indicator), divide by 1000
        if normalized_source in ["/μl", "cells/μl", "/ul", "cells/ul"]:
            converted_value = round(value / 1000, 2)
        # If already in thousands (10^3/μL, K/μL, etc.), keep as-is
        elif "10^3" in normalized_source or "k/" in normalized_source:
            converted_value = value
        # If unit is 10^9/L (SI unit), convert to 10^3/μL (multiply by 1)
        elif "10^9/l" in normalized_source:
            converted_value = value  # 10^9/L = 10^3/μL

    # Hemoglobin conversions
    elif biomarker == "Hemoglobin":
        # g/L to g/dL: divide by 10
        if normalized_source in ["g/l", "gm/l"]:
            converted_value = round(value / 10, 2)
        # mg/dL to g/dL: divide by 1000
        elif normalized_source in ["mg/dl", "mg/100ml"]:
            converted_value = round(value / 1000, 2)
        # mmol/L to g/dL: multiply by 1.611
        elif normalized_source in ["mmol/l"]:
            converted_value = round(value * 1.611, 2)

    # Creatinine conversions
    elif biomarker == "Creatinine":
        # μmol/L to mg/dL: divide by 88.4
        if normalized_source in ["μmol/l", "umol/l", "mcmol/l"]:
            converted_value = round(value / 88.4, 2)

    # Total Bilirubin conversions
    elif biomarker == "Total Bilirubin":
        # μmol/L to mg/dL: divide by 17.1
        if normalized_source in ["μmol/l", "umol/l", "mcmol/l"]:
            converted_value = round(value / 17.1, 2)

    # ALT/AST conversions (usually already in U/L)
    elif biomarker in ["ALT", "AST"]:
        # IU/L is same as U/L
        if normalized_source in ["iu/l", "u/l", "units/l"]:
            converted_value = value

    # Tumor marker conversions (usually already in standard units)
    elif biomarker in ["CEA", "NSE", "CYFRA_21_1"]:
        # ng/mL is standard, convert from μg/L if needed
        if normalized_source in ["μg/l", "ug/l", "mcg/l"]:
            converted_value = value  # μg/L = ng/mL (1:1)
        # Convert from ng/dL to ng/mL
        elif normalized_source in ["ng/dl"]:
            converted_value = round(value / 10, 2)

    elif biomarker == "proGRP":
        # pg/mL is standard
        if normalized_source in ["ng/ml"]:
            converted_value = round(value * 1000, 2)  # ng/mL to pg/mL
        elif normalized_source in ["ng/l"]:
            converted_value = value  # ng/L = pg/mL (1:1)

    return converted_value, standard_unit


def get_standard_unit(biomarker: str) -> Optional[str]:
    """
    Get the standard unit for a biomarker.

    Args:
        biomarker: Biomarker name

    Returns:
        Standard unit string or None if biomarker not recognized
    """
    return STANDARD_UNITS.get(biomarker)


def is_unit_compatible(source_unit: str, biomarker: str) -> bool:
    """
    Check if a source unit is compatible/convertible for a biomarker.

    Args:
        source_unit: Source unit string
        biomarker: Biomarker name

    Returns:
        True if unit can be converted to standard, False otherwise
    """
    standard_unit = STANDARD_UNITS.get(biomarker)
    if not standard_unit:
        return False

    # Try conversion and check if value changes or unit becomes standard
    try:
        _, resulting_unit = convert_to_standard_unit(100.0, source_unit, biomarker)
        return normalize_unit_string(resulting_unit) == normalize_unit_string(standard_unit)
    except Exception:
        return False


if __name__ == "__main__":
    # Test conversions
    print("="*60)
    print("Lab Unit Converter - Test Cases")
    print("="*60)

    test_cases = [
        # WBC conversions
        ("WBC", 6850, "/μL", "Should convert /μL to 10^3/μL"),
        ("WBC", 6.85, "10^3/μL", "Already in standard unit"),
        ("WBC", 6.85, "K/μL", "K/μL is same as 10^3/μL"),

        # Hemoglobin conversions
        ("Hemoglobin", 112, "g/L", "Should convert g/L to g/dL"),
        ("Hemoglobin", 11.2, "g/dL", "Already in standard unit"),

        # Creatinine conversions
        ("Creatinine", 88, "μmol/L", "Should convert μmol/L to mg/dL"),
        ("Creatinine", 1.0, "mg/dL", "Already in standard unit"),

        # Total Bilirubin conversions
        ("Total Bilirubin", 17.1, "μmol/L", "Should convert μmol/L to mg/dL"),
        ("Total Bilirubin", 1.0, "mg/dL", "Already in standard unit"),
    ]

    for biomarker, value, source_unit, description in test_cases:
        converted_value, standard_unit = convert_to_standard_unit(value, source_unit, biomarker)
        print(f"\n{description}")
        print(f"  {biomarker}: {value} {source_unit}")
        print(f"  → {converted_value} {standard_unit}")
