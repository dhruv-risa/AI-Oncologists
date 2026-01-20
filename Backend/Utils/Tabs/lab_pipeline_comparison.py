"""
Individual Lab Result Processing Pipeline

This module implements an alternative approach to lab result extraction:
- Extracts each lab result PDF individually from FHIR
- Uploads each PDF separately to Google Drive
- Parses each PDF individually with the LLM
- Combines the extracted data from all individual reports

This allows comparison with the current chunking approach where all PDFs
are combined first before parsing.
"""

import sys
import os
import json
import time
from typing import List, Dict, Any
from Backend.Utils.Tabs.llmparser import llmresponsedetailed

# Add Backend to path for imports
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from Backend.bytes_extractor import extract_lab_results_data_md_notes_combined
from Backend.drive_uploader import upload_and_share_pdf_bytes
from Backend.documents_reference import generate_bearer_token, get_patient_id_from_mrn, generate_onco_emr_token
from Backend.Utils.Tabs.lab_postprocessor import process_lab_data_for_ui
from Backend.Utils.logger_config import setup_logger
from Backend.Utils.Tabs.lab_tab import extract_with_gemini

import requests
import tempfile

# Setup logger
logger = setup_logger(__name__)


# Reuse the same extraction instructions and schema from lab_tab.py
extracted_instructions = (
    "Extract structured lab result data for a 'Patient Labs Dashboard' from provided clinical notes and lab reports. "
    "Scope: Analyze the provided lab report document. "

    "MISSION: For EVERY biomarker listed (Tumor Markers, Complete Blood Count, and Metabolic Panel), you must extract: "
    "1. The 'Current' value with its unit, date, status, and reference range from THIS report. "
    "2. A 'Trend' array containing ALL DATA POINTS from THIS single report (if multiple values exist). "

    "Targets: "
    "- TUMOR MARKERS: CEA, NSE, proGRP, CYFRA 21-1. "
    "- CBC: WBC, Hemoglobin, Platelets, ANC (if missing, use 'Segs#' or 'Polys, Abs'). "
    "- METABOLIC: Creatinine, ALT, AST, Total Bilirubin. "

    "CLINICAL INTERPRETATION: "
    "Summarize abnormalities: Anemia (Hgb <13.5 M / <12.0 F), Hepatic (ALT/AST >40), Neutropenia (ANC <1.5)."
)


def biomarker_schema():
    return {
        "current": {
            "value": "Float or 'Pending' - The most recent value for this biomarker",
            "unit": "String - The unit of measurement (e.g., 'g/dL', 'Thousand/uL')",
            "date": "YYYY-MM-DD - Date of the most recent measurement",
            "status": "String (e.g., 'Normal', 'High', 'Low') - Status based on reference range",
            "reference_range": "String - The reference range for this biomarker"
        },
        "trend": [
            {
                "date": "YYYY-MM-DD - Date when this measurement was taken",
                "value": "Float - The measured value on this date",
                "status": "String - Status on this date (Normal/High/Low)",
                "source_context": "String - Which report this came from (e.g., 'Quest Lab Report Oct 2025')"
            }
        ]
    }


description = {
    "tumor_markers": {
        "CEA": biomarker_schema(),
        "NSE": biomarker_schema(),
        "proGRP": biomarker_schema(),
        "CYFRA_21_1": biomarker_schema()
    },
    "complete_blood_count": {
        "WBC": biomarker_schema(),
        "Hemoglobin": biomarker_schema(),
        "Platelets": biomarker_schema(),
        "ANC": biomarker_schema()
    },
    "metabolic_panel": {
        "Creatinine": biomarker_schema(),
        "ALT": biomarker_schema(),
        "AST": biomarker_schema(),
        "Total Bilirubin": biomarker_schema()
    },
    "clinical_interpretation": [
        "String summary of abnormal findings and rules applied."
    ]
}


def fetch_individual_pdf_bytes(fhir_url: str, bearer_token: str, onco_emr_token: str) -> bytes:
    """
    Fetch PDF bytes from a single FHIR DocumentReference URL.

    Args:
        fhir_url: The FHIR DocumentReference URL
        bearer_token: Bearer token for authentication
        onco_emr_token: OncoEMR token for FHIR API

    Returns:
        PDF bytes
    """
    headers = {
        "Authorization": f"Bearer {onco_emr_token}",
        "Accept": "application/fhir+json"
    }

    response = requests.get(fhir_url, headers=headers)
    response.raise_for_status()

    # Add rate limiting delay to avoid 429 errors (1.5 seconds between API calls)
    time.sleep(1.5)

    document_data = response.json()

    # Extract PDF from FHIR attachment
    for content in document_data.get("content", []):
        attachment = content.get("attachment", {})
        if attachment.get("contentType") == "application/pdf":
            # Try URL first
            pdf_url = attachment.get("url")
            if pdf_url:
                # Add rate limiting delay before PDF download
                time.sleep(1.5)
                pdf_response = requests.get(pdf_url)
                pdf_response.raise_for_status()
                return pdf_response.content

            # Try base64 data
            import base64
            pdf_data = attachment.get("data")
            if pdf_data:
                return base64.b64decode(pdf_data)

    raise ValueError(f"No PDF found in FHIR document: {fhir_url}")


def print_parsed_data_summary(parsed_data: Dict, doc_index: int, doc_date: str, verbose: bool = False):
    """Print a summary of what was extracted from the parsed data."""
    if verbose:
        logger.info(f"\n{'='*80}")
        logger.info(f"PARSED DATA FOR DOCUMENT {doc_index} ({doc_date})")
        logger.info(f"{'='*80}\n")
        logger.info(json.dumps(parsed_data, indent=2))
        logger.info(f"\n{'='*80}\n")

    logger.info("📊 Extracted Data Summary:")

    def get_value(data):
        """Get value from either flat or nested schema"""
        if isinstance(data, dict):
            # Try nested schema first
            if 'current' in data:
                return data.get('current', {}).get('value')
            # Try flat schema
            return data.get('value')
        return None

    # Tumor markers
    tm = parsed_data.get("tumor_markers", {})
    tm_with_data = [name for name, data in tm.items()
                    if get_value(data) not in [None, 'NA', '']]
    if tm_with_data:
        logger.info(f"   ✓ Tumor Markers: {len(tm_with_data)} biomarkers → {', '.join(tm_with_data)}")
    else:
        logger.info(f"   ✗ Tumor Markers: No data found")

    # CBC
    cbc = parsed_data.get("complete_blood_count", {})
    cbc_with_data = []
    cbc_trend_counts = {}
    for name, data in cbc.items():
        if isinstance(data, dict):
            value = get_value(data)
            if value not in [None, 'NA', '']:
                cbc_with_data.append(name)
                trend_count = len(data.get('trend', []))
                if trend_count > 0:
                    cbc_trend_counts[name] = trend_count

    if cbc_with_data:
        logger.info(f"   ✓ CBC: {len(cbc_with_data)} biomarkers → {', '.join(cbc_with_data)}")
        if cbc_trend_counts:
            for name, count in cbc_trend_counts.items():
                logger.info(f"      - {name}: {count} trend point(s)")
    else:
        logger.info(f"   ✗ CBC: No data found")

    # Metabolic
    met = parsed_data.get("metabolic_panel", {})
    met_with_data = []
    met_trend_counts = {}
    for name, data in met.items():
        if isinstance(data, dict):
            value = get_value(data)
            if value not in [None, 'NA', '']:
                met_with_data.append(name)
                trend_count = len(data.get('trend', []))
                if trend_count > 0:
                    met_trend_counts[name] = trend_count

    if met_with_data:
        logger.info(f"   ✓ Metabolic Panel: {len(met_with_data)} biomarkers → {', '.join(met_with_data)}")
        if met_trend_counts:
            for name, count in met_trend_counts.items():
                logger.info(f"      - {name}: {count} trend point(s)")
    else:
        logger.info(f"   ✗ Metabolic Panel: No data found")

    # Clinical interpretation
    clinical = parsed_data.get("clinical_interpretation", [])
    if clinical:
        logger.info(f"   ✓ Clinical Interpretations: {len(clinical)}")
        for interp in clinical:
            logger.info(f"      - {interp}")
    else:
        logger.info(f"   ✗ Clinical Interpretations: None")


def process_individual_lab_results(mrn: str, verbose: bool = False) -> Dict[str, Any]:
    """
    Process lab results individually - upload and parse each PDF separately.

    Args:
        mrn: Medical Record Number
        verbose: If True, print full JSON for each parsed document

    Returns:
        Dictionary containing:
        - individual_results: List of parsed results from each PDF
        - combined_data: Consolidated data from all individual results
        - metadata: Information about the individual PDFs processed
    """
    logger.info(f"🔄 Starting individual lab result processing for MRN: {mrn}")

    # Step 1: Extract lab result documents from FHIR
    logger.info("📥 Extracting lab result documents from FHIR...")
    lab_documents = extract_lab_results_data_md_notes_combined(mrn)

    if not lab_documents:
        logger.warning(f"No lab documents found for MRN: {mrn}")
        return {
            "individual_results": [],
            "combined_data": None,
            "metadata": {
                "total_documents": 0,
                "processed_documents": 0,
                "errors": []
            }
        }

    logger.info(f"✅ Found {len(lab_documents)} lab result documents")

    # Step 2: Get authentication tokens
    logger.info("🔑 Authenticating with FHIR API...")
    bearer_token = generate_bearer_token()
    onco_emr_token = generate_onco_emr_token(bearer_token)
    patient_id, _ = get_patient_id_from_mrn(mrn, onco_emr_token)

    # Step 3: Process each PDF individually
    individual_results = []
    metadata = {
        "total_documents": len(lab_documents),
        "processed_documents": 0,
        "errors": [],
        "individual_pdfs": []
    }

    for idx, doc in enumerate(lab_documents, 1):
        doc_url = doc.get("url")
        doc_date = doc.get("date")
        doc_description = doc.get("description", f"Lab Report {idx}")

        logger.info(f"\n{'='*80}")
        logger.info(f"Processing document {idx}/{len(lab_documents)}")
        logger.info(f"Date: {doc_date}")
        logger.info(f"Description: {doc_description}")
        logger.info(f"{'='*80}")

        try:
            # Fetch PDF bytes
            logger.info("📥 Fetching PDF bytes from FHIR...")
            pdf_bytes = fetch_individual_pdf_bytes(doc_url, bearer_token, onco_emr_token)
            logger.info(f"✅ Fetched PDF: {len(pdf_bytes)} bytes")

            # Upload to Google Drive
            logger.info("☁️  Uploading PDF to Google Drive...")
            upload_result = upload_and_share_pdf_bytes(
                pdf_bytes,
                file_name=f"Lab_Result_{mrn}_{doc_date}_{idx}.pdf"
            )
            drive_url = upload_result["shareable_url"]
            file_id = upload_result["file_id"]
            logger.info(f"✅ Uploaded to Drive: {drive_url}")

            # Parse with LLM
            logger.info("🤖 Parsing PDF with LLM...")
            parsed_data = llmresponsedetailed(
                drive_url,
                extraction_instructions=extracted_instructions,
                description=description,
                config={
                    "start_page": 1,
                    "end_page": 10,
                    "batch_size": 1,
                    "enable_batch_processing": False,
                    "model": "gpt-5"
                }
            )
            logger.info("✅ Parsing complete")

            # Print summary of extracted data
            print_parsed_data_summary(parsed_data, idx, doc_date, verbose)

            # Store result
            individual_results.append({
                "document_index": idx,
                "date": doc_date,
                "description": doc_description,
                "fhir_url": doc_url,
                "drive_url": drive_url,
                "file_id": file_id,
                "parsed_data": parsed_data
            })

            metadata["individual_pdfs"].append({
                "index": idx,
                "date": doc_date,
                "drive_url": drive_url,
                "file_id": file_id
            })

            metadata["processed_documents"] += 1
            logger.info(f"✅ Successfully processed document {idx}")

        except Exception as e:
            error_msg = f"Error processing document {idx} (date: {doc_date}): {str(e)}"
            logger.error(f"❌ {error_msg}")
            metadata["errors"].append(error_msg)
            continue

    logger.info(f"\n{'='*80}")
    logger.info(f"Individual processing complete!")
    logger.info(f"Processed: {metadata['processed_documents']}/{metadata['total_documents']}")
    logger.info(f"Errors: {len(metadata['errors'])}")
    logger.info(f"{'='*80}\n")

    # Step 4: Consolidate data from all individual results
    logger.info("🔄 Consolidating data from individual results...")
    logger.info(f"   Total individual results to consolidate: {len(individual_results)}")

    # Extract parsed_data from each result
    all_parsed_data = [result["parsed_data"] for result in individual_results]

    # Debug: Show what we're passing to the consolidator
    logger.info(f"   Passing {len(all_parsed_data)} parsed data objects to consolidator")

    # Use the same postprocessor to consolidate
    combined_data = process_lab_data_for_ui(all_parsed_data) if all_parsed_data else None

    logger.info("✅ Consolidation complete")

    # Print consolidation summary
    if combined_data:
        logger.info(f"\n{'='*80}")
        logger.info("CONSOLIDATION SUMMARY")
        logger.info(f"{'='*80}")

        for panel_name in ["tumor_markers", "complete_blood_count", "metabolic_panel"]:
            panel = combined_data.get(panel_name, {})
            panel_title = panel_name.replace("_", " ").title()
            logger.info(f"\n{panel_title}:")

            for biomarker_name, biomarker_data in panel.items():
                if isinstance(biomarker_data, dict):
                    has_data = biomarker_data.get("has_data", False)
                    trend_count = len(biomarker_data.get("trend", []))
                    current_date = biomarker_data.get("current", {}).get("date")

                    if has_data:
                        logger.info(f"   ✓ {biomarker_name}: Current date={current_date}, Trend points={trend_count}")
                        if trend_count > 0:
                            trend_dates = [t.get("date") for t in biomarker_data.get("trend", [])]
                            logger.info(f"      Trend dates: {', '.join(trend_dates)}")
                    else:
                        logger.info(f"   ✗ {biomarker_name}: No data")

    return {
        "individual_results": individual_results,
        "combined_data": combined_data,
        "metadata": metadata
    }


def validate_extraction(parsed_data: Dict, doc_date: str) -> Dict[str, Any]:
    """
    Validate the extracted data for completeness and correctness.

    Args:
        parsed_data: The extracted lab data
        doc_date: The document date for reference

    Returns:
        Dictionary with validation results
    """
    validation_results = {
        "is_valid": True,
        "errors": [],
        "warnings": [],
        "stats": {
            "total_biomarkers": 0,
            "biomarkers_with_data": 0,
            "biomarkers_with_trends": 0,
            "total_trend_points": 0
        }
    }

    # Check required structure
    required_panels = ["tumor_markers", "complete_blood_count", "metabolic_panel"]
    for panel in required_panels:
        if panel not in parsed_data:
            validation_results["errors"].append(f"Missing required panel: {panel}")
            validation_results["is_valid"] = False

    # Validate each panel
    for panel_name in required_panels:
        panel = parsed_data.get(panel_name, {})
        if not isinstance(panel, dict):
            validation_results["errors"].append(f"{panel_name} is not a dictionary")
            validation_results["is_valid"] = False
            continue

        for biomarker_name, biomarker_data in panel.items():
            validation_results["stats"]["total_biomarkers"] += 1

            if not isinstance(biomarker_data, dict):
                validation_results["warnings"].append(f"{panel_name}.{biomarker_name} is not a dictionary")
                continue

            # Check if has data - handle both flat and nested schemas
            # Flat schema (Gemini): {"value": ..., "unit": ..., "date": ...}
            # Nested schema (LLM): {"current": {...}, "trend": [...]}
            if "current" in biomarker_data:
                # Nested schema
                current = biomarker_data.get("current", {})
                value = current.get("value")
                unit = current.get("unit")
                date = current.get("date")
                status = current.get("status")
            else:
                # Flat schema (Gemini)
                current = biomarker_data
                value = biomarker_data.get("value")
                unit = biomarker_data.get("unit")
                date = biomarker_data.get("date")
                status = biomarker_data.get("status")

            if value not in [None, "NA", "", "Pending"]:
                validation_results["stats"]["biomarkers_with_data"] += 1

                # Validate structure
                if not unit:
                    validation_results["warnings"].append(f"{biomarker_name}: Missing unit")
                if not date:
                    validation_results["warnings"].append(f"{biomarker_name}: Missing date")
                if not status:
                    validation_results["warnings"].append(f"{biomarker_name}: Missing status")

            # Check trends (only in nested schema)
            trend = biomarker_data.get("trend", [])
            if trend and len(trend) > 0:
                validation_results["stats"]["biomarkers_with_trends"] += 1
                validation_results["stats"]["total_trend_points"] += len(trend)

                # Validate trend entries
                for i, trend_entry in enumerate(trend):
                    if not isinstance(trend_entry, dict):
                        validation_results["warnings"].append(
                            f"{biomarker_name}: Trend entry {i} is not a dictionary"
                        )
                        continue

                    if not trend_entry.get("date"):
                        validation_results["warnings"].append(
                            f"{biomarker_name}: Trend entry {i} missing date"
                        )
                    if trend_entry.get("value") in [None, "", "NA"]:
                        validation_results["warnings"].append(
                            f"{biomarker_name}: Trend entry {i} missing value"
                        )

    # Check clinical interpretation
    clinical_interp = parsed_data.get("clinical_interpretation", [])
    if not clinical_interp or len(clinical_interp) == 0:
        validation_results["warnings"].append("No clinical interpretation provided")

    # Final validation
    if validation_results["stats"]["biomarkers_with_data"] == 0:
        validation_results["warnings"].append("No biomarkers extracted with data - document may be empty or parsing failed")

    return validation_results


def process_individual_lab_results_gemini(mrn: str, verbose: bool = False) -> Dict[str, Any]:
    """
    Process lab results individually using Gemini - download and parse each PDF separately.

    Args:
        mrn: Medical Record Number
        verbose: If True, print full JSON for each parsed document

    Returns:
        Dictionary containing:
        - individual_results: List of parsed results from each PDF with validation
        - combined_data: Consolidated data from all individual results
        - metadata: Information about the individual PDFs processed
        - validation_summary: Overall validation statistics
    """
    logger.info(f"🔄 Starting individual lab result processing with Gemini for MRN: {mrn}")

    # Step 1: Extract lab result documents from FHIR
    logger.info("📥 Extracting lab result documents from FHIR...")
    lab_documents = extract_lab_results_data_md_notes_combined(mrn)

    if not lab_documents:
        logger.warning(f"No lab documents found for MRN: {mrn}")
        return {
            "individual_results": [],
            "combined_data": None,
            "metadata": {
                "total_documents": 0,
                "processed_documents": 0,
                "errors": []
            },
            "validation_summary": {
                "total_validated": 0,
                "total_passed": 0,
                "total_failed": 0
            }
        }

    logger.info(f"✅ Found {len(lab_documents)} lab result documents")

    # Step 2: Get authentication tokens
    logger.info("🔑 Authenticating with FHIR API...")
    bearer_token = generate_bearer_token()
    onco_emr_token = generate_onco_emr_token(bearer_token)
    patient_id, _ = get_patient_id_from_mrn(mrn, onco_emr_token)

    # Step 3: Process each PDF individually with Gemini
    individual_results = []
    metadata = {
        "total_documents": len(lab_documents),
        "processed_documents": 0,
        "errors": [],
        "individual_pdfs": []
    }

    validation_summary = {
        "total_validated": 0,
        "total_passed": 0,
        "total_failed": 0,
        "total_warnings": 0
    }

    for idx, doc in enumerate(lab_documents, 1):
        doc_url = doc.get("url")
        doc_date = doc.get("date")
        doc_description = doc.get("description", f"Lab Report {idx}")

        logger.info(f"\n{'='*80}")
        logger.info(f"Processing document {idx}/{len(lab_documents)} with Gemini")
        logger.info(f"Date: {doc_date}")
        logger.info(f"Description: {doc_description}")
        logger.info(f"{'='*80}")

        try:
            # Fetch PDF bytes from FHIR
            logger.info("📥 Fetching PDF bytes from FHIR...")
            pdf_bytes = fetch_individual_pdf_bytes(doc_url, bearer_token, onco_emr_token)
            logger.info(f"✅ Fetched PDF: {len(pdf_bytes)} bytes")

            # Parse with Gemini using bytes directly (no file download!)
            logger.info(f"🤖 Parsing PDF bytes with Gemini...")
            parsed_data = extract_with_gemini(pdf_bytes)
            logger.info("✅ Gemini parsing complete")

            # Validate extraction
            logger.info("🔍 Validating extraction...")
            validation = validate_extraction(parsed_data, doc_date)
            validation_summary["total_validated"] += 1

            if validation["is_valid"]:
                validation_summary["total_passed"] += 1
                logger.info("✅ Validation PASSED")
            else:
                validation_summary["total_failed"] += 1
                logger.info("⚠️  Validation FAILED")

            validation_summary["total_warnings"] += len(validation["warnings"])

            # Print validation results
            if validation["errors"]:
                logger.warning("  Errors:")
                for error in validation["errors"]:
                    logger.warning(f"    - {error}")

            if validation["warnings"]:
                logger.info("  Warnings:")
                for warning in validation["warnings"]:
                    logger.info(f"    - {warning}")

            logger.info(f"  Stats:")
            logger.info(f"    - Biomarkers with data: {validation['stats']['biomarkers_with_data']}/{validation['stats']['total_biomarkers']}")
            logger.info(f"    - Biomarkers with trends: {validation['stats']['biomarkers_with_trends']}")
            logger.info(f"    - Total trend points: {validation['stats']['total_trend_points']}")

            # Print summary of extracted data
            print_parsed_data_summary(parsed_data, idx, doc_date, verbose)

            # Store result (no file path - using bytes directly!)
            individual_results.append({
                "document_index": idx,
                "date": doc_date,
                "description": doc_description,
                "fhir_url": doc_url,
                "parsed_data": parsed_data,
                "validation": validation
            })

            metadata["individual_pdfs"].append({
                "index": idx,
                "date": doc_date,
                "validation_passed": validation["is_valid"]
            })

            metadata["processed_documents"] += 1
            logger.info(f"✅ Successfully processed document {idx}")

        except Exception as e:
            error_msg = f"Error processing document {idx} (date: {doc_date}): {str(e)}"
            logger.error(f"❌ {error_msg}")
            import traceback
            logger.error(traceback.format_exc())
            metadata["errors"].append(error_msg)
            continue

    logger.info(f"\n{'='*80}")
    logger.info(f"Individual Gemini processing complete!")
    logger.info(f"Processed: {metadata['processed_documents']}/{metadata['total_documents']}")
    logger.info(f"Errors: {len(metadata['errors'])}")
    logger.info(f"Validation: {validation_summary['total_passed']}/{validation_summary['total_validated']} passed")
    logger.info(f"{'='*80}\n")

    # Step 4: Consolidate data from all individual results
    logger.info("🔄 Consolidating data from individual Gemini results...")
    logger.info(f"   Total individual results to consolidate: {len(individual_results)}")

    # Extract parsed_data from each result
    all_parsed_data = [result["parsed_data"] for result in individual_results]

    # Debug: Show what we're passing to the consolidator
    logger.info(f"   Passing {len(all_parsed_data)} parsed data objects to consolidator")

    # Use the same postprocessor to consolidate
    combined_data = process_lab_data_for_ui(all_parsed_data) if all_parsed_data else None

    logger.info("✅ Consolidation complete")

    # Print consolidation summary
    if combined_data:
        logger.info(f"\n{'='*80}")
        logger.info("CONSOLIDATION SUMMARY")
        logger.info(f"{'='*80}")

        for panel_name in ["tumor_markers", "complete_blood_count", "metabolic_panel"]:
            panel = combined_data.get(panel_name, {})
            panel_title = panel_name.replace("_", " ").title()
            logger.info(f"\n{panel_title}:")

            for biomarker_name, biomarker_data in panel.items():
                if isinstance(biomarker_data, dict):
                    has_data = biomarker_data.get("has_data", False)
                    trend_count = len(biomarker_data.get("trend", []))
                    current_date = biomarker_data.get("current", {}).get("date")

                    if has_data:
                        logger.info(f"   ✓ {biomarker_name}: Current date={current_date}, Trend points={trend_count}")
                        if trend_count > 0:
                            trend_dates = [t.get("date") for t in biomarker_data.get("trend", [])]
                            logger.info(f"      Trend dates: {', '.join(trend_dates)}")
                    else:
                        logger.info(f"   ✗ {biomarker_name}: No data")

    return {
        "individual_results": individual_results,
        "combined_data": combined_data,
        "metadata": metadata,
        "validation_summary": validation_summary
    }


def extract_lab_info_individual(mrn: str) -> Dict[str, Any]:
    """
    Main function to extract lab info using individual processing approach.

    Args:
        mrn: Medical Record Number

    Returns:
        Processed lab data ready for UI consumption
    """
    result = process_individual_lab_results(mrn)
    return result["combined_data"]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Process lab results individually")
    parser.add_argument("--mrn", type=str, default="A236987", help="Medical Record Number")
    parser.add_argument("--output", type=str, help="Output JSON file path")
    parser.add_argument("--verbose", action="store_true", help="Show full JSON for each parsed document")
    parser.add_argument("--use-gemini", action="store_true", help="Use Gemini instead of LLM parser")

    args = parser.parse_args()

    # Process lab results with selected parser
    if args.use_gemini:
        logger.info("🤖 Using Gemini for individual processing")
        result = process_individual_lab_results_gemini(args.mrn, verbose=args.verbose)
    else:
        logger.info("🤖 Using LLM parser for individual processing")
        result = process_individual_lab_results(args.mrn, verbose=args.verbose)

    # Print summary
    print("\n" + "="*80)
    print("INDIVIDUAL LAB RESULT PROCESSING SUMMARY")
    print("="*80)
    print(f"MRN: {args.mrn}")
    print(f"Parser: {'Gemini' if args.use_gemini else 'LLM'}")
    print(f"Total Documents: {result['metadata']['total_documents']}")
    print(f"Processed Documents: {result['metadata']['processed_documents']}")
    print(f"Errors: {len(result['metadata']['errors'])}")

    # Print validation summary if using Gemini
    if args.use_gemini and 'validation_summary' in result:
        val_sum = result['validation_summary']
        print(f"\nValidation Summary:")
        print(f"  Total Validated: {val_sum['total_validated']}")
        print(f"  Passed: {val_sum['total_passed']}")
        print(f"  Failed: {val_sum['total_failed']}")
        print(f"  Total Warnings: {val_sum['total_warnings']}")

    if result['metadata']['errors']:
        print("\nErrors:")
        for error in result['metadata']['errors']:
            print(f"  - {error}")

    print("\nIndividual PDFs:")
    for pdf_info in result['metadata']['individual_pdfs']:
        print(f"  {pdf_info['index']}. Date: {pdf_info['date']}")
        if 'pdf_file_path' in pdf_info:
            print(f"     File Path: {pdf_info['pdf_file_path']}")
        if 'drive_url' in pdf_info:
            print(f"     Drive URL: {pdf_info['drive_url']}")
        if 'validation_passed' in pdf_info:
            validation_status = "✓ PASSED" if pdf_info['validation_passed'] else "✗ FAILED"
            print(f"     Validation: {validation_status}")

    print("\n" + "="*80)
    print("COMBINED LAB DATA (UI-READY)")
    print("="*80)
    print(json.dumps(result['combined_data'], indent=2))

    # Save to file if specified
    if args.output:
        output_path = args.output
    else:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"individual_result_{args.mrn}_{timestamp}.json"

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n✅ Results saved to: {output_path}")
