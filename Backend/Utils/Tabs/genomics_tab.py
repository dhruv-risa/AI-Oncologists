import os, sys
import requests
import json

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from Utils.Tabs.llmparser import llmresponsedetailed
from Utils.logger_config import setup_logger, log_extraction_start, log_extraction_complete, log_extraction_output

# Setup logger
logger = setup_logger(__name__)


def consolidate_genomic_data(raw_data):
    """
    Consolidates multiple batch results into a single, clean UI-friendly structure.
    Filters to show only detected mutations and valid biomarkers.
    """

    # Initialize consolidated structure
    consolidated = {
        "detected_driver_mutations": [],
        "immunotherapy_markers": {},
        "additional_genomic_alterations": []
    }

    # Process driver mutations - consolidate and filter for detected only
    driver_mutations_all = raw_data.get("driver_mutations", [])
    all_genes = {}

    for entry in driver_mutations_all:
        if isinstance(entry, dict):
            for gene, info in entry.items():
                if isinstance(info, dict):
                    status = info.get("status", "")
                    # Only include if detected and not NA/null
                    if status and status not in ["Not detected", "NA", None]:
                        if gene not in all_genes or status == "Detected":
                            all_genes[gene] = {
                                "gene": gene,
                                "status": status,
                                "details": info.get("details") if info.get("details") not in ["NA", None] else None,
                                "is_target": info.get("is_target") if info.get("is_target") not in ["NA", None, False] else False
                            }

    consolidated["detected_driver_mutations"] = list(all_genes.values())

    # Process immunotherapy markers - get first valid entry
    immuno_markers = raw_data.get("immunotherapy_markers", [])
    for entry in immuno_markers:
        if isinstance(entry, dict):
            # PD-L1
            pd_l1 = entry.get("pd_l1", {})
            if pd_l1 and pd_l1.get("value") not in ["NA", None]:
                consolidated["immunotherapy_markers"]["pd_l1"] = {
                    "value": pd_l1.get("value"),
                    "metric": pd_l1.get("metric"),
                    "interpretation": pd_l1.get("interpretation")
                }

            # TMB
            tmb = entry.get("tmb", {})
            if tmb and tmb.get("value") not in ["NA", None]:
                consolidated["immunotherapy_markers"]["tmb"] = {
                    "value": tmb.get("value"),
                    "interpretation": tmb.get("interpretation")
                }

            # MSI Status
            msi = entry.get("msi_status", {})
            if msi and msi.get("status") not in ["NA", None]:
                consolidated["immunotherapy_markers"]["msi_status"] = {
                    "status": msi.get("status"),
                    "interpretation": msi.get("interpretation")
                }

            # Break if we found valid data
            if consolidated["immunotherapy_markers"]:
                break

    # Process additional genomic alterations - filter out NA
    alterations = raw_data.get("additional_genomic_alterations", [])
    seen_alterations = set()

    for alt in alterations:
        if isinstance(alt, dict):
            gene = alt.get("gene")
            alteration = alt.get("alteration")
            # Create unique key to avoid duplicates
            key = f"{gene}_{alteration}"
            if gene and alteration and key not in seen_alterations:
                consolidated["additional_genomic_alterations"].append({
                    "gene": gene,
                    "alteration": alteration,
                    "type": alt.get("type"),
                    "significance": alt.get("significance")
                })
                seen_alterations.add(key)

    return consolidated


def extract_genomic_info(pdf_url):

    extraction_instructions = (
        "Extract structured molecular and genomic profiling data for the patient from the provided report. "
        "MISSION: For the 'Driver Mutations' section, specifically check for and extract the status of these nine targets: "
        "EGFR, ALK, ROS1, KRAS, BRAF, MET, RET, HER2, and NTRK. "
        "For each target, indicate 'Detected' or 'Not detected' and include specific variant details "
        "(e.g., 'Exon 19 deletion', 'V600E') if present. "

        "Additionally, extract 'Biomarkers & Immunotherapy Markers': "
        "PD-L1 Expression (e.g., 75% TPS), "
        "TMB (e.g., 8 mutations/Mb), "
        "MSI Status (e.g., MSS (Stable)). "

        "Return the output strictly as a JSON object matching the schema. "
        "If a test was not performed or not found, return null."
    )

    # Helper for uniform marker structure
    def marker_status_schema():
        return {
            "status": "String ('Detected' or 'Not detected')",
            "details": "String (e.g., 'Exon 19 deletion (L747_P753delinsS)' or 'Rearrangement')",
            "is_target": "Boolean (True if flagged as a Target in the report)"
        }

    description = {
        "driver_mutations": {
            "EGFR": marker_status_schema(),
            "ALK": marker_status_schema(),
            "ROS1": marker_status_schema(),
            "KRAS": marker_status_schema(),
            "BRAF": marker_status_schema(),
            "MET": marker_status_schema(),
            "RET": marker_status_schema(),
            "HER2": marker_status_schema(),
            "NTRK": marker_status_schema()
        },
        "immunotherapy_markers": {
            "pd_l1": {
                "value": "String (e.g., '75%')",
                "metric": "String (e.g., 'TPS')",
                "interpretation": "String"
            },
            "tmb": {
                "value": "String (e.g., '8 mutations/Mb')",
                "interpretation": "String"
            },
            "msi_status": {
                "status": "String (e.g., 'MSS')",
                "interpretation": "String (e.g., 'Stable')"
            }
        },
        "additional_genomic_alterations": [
            {
                "gene": "The HUGO gene symbol.",
                "alteration": "Specific protein/cDNA change.",
                "type": "Mutation, Rearrangement, Deletion, etc.",
                "significance": "Clinical significance/Tier."
            }
        ]
    }

    # ✅ CONFIG ADDED HERE
    config = {
        "start_page": 1,
        "end_page": 40,
        "batch_size": 3,
        "enable_batch_processing": True,
        "model": "claude-sonnet-4-0"
    }

    log_extraction_start(logger, "Genomics Tab", pdf_url)
    logger.info("🔄 Extracting patient genomics data...")

    patient_genomics = llmresponsedetailed(
        pdf_url=pdf_url,
        extraction_instructions=extraction_instructions,
        description=description,
        config=config   # 👈 passed into parser
    )

    log_extraction_output(logger, "Genomics Raw Data", patient_genomics)

    # Consolidate and filter data for UI
    logger.info("🔄 Consolidating genomic data for UI...")
    consolidated_data = consolidate_genomic_data(patient_genomics)

    log_extraction_output(logger, "Genomics Consolidated Data", consolidated_data)
    log_extraction_complete(logger, "Genomics Tab", consolidated_data.keys() if isinstance(consolidated_data, dict) else None)

    return consolidated_data


if __name__ == "__main__":
    # Example usage
    genomic_info = extract_genomic_info(
        pdf_url="https://drive.google.com/file/d/1iUeOI1kjD7t5XPtyPVKfH5bq_bZPv352/view?usp=sharing"
    )
    print(json.dumps(genomic_info, indent=2))
