import os, sys
import requests
import json
import re
import vertexai
from vertexai.generative_models import GenerativeModel, Part

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from Backend.Utils.Tabs.llmparser import llmresponsedetailed
from Backend.Utils.logger_config import setup_logger, log_extraction_start, log_extraction_complete, log_extraction_output

# Setup logger
logger = setup_logger(__name__)

# Initialize Vertex AI
vertexai.init(project="prior-auth-portal-dev", location="us-central1")


def extract_genomic_info_with_gemini(pdf_input):
    """
    Extract genomic/molecular profiling data using Vertex AI Gemini.

    Args:
        pdf_input: Either bytes (PDF content), local path to PDF file, or Google Drive URL

    Returns:
        Dictionary containing extracted genomic data
    """
    logger.info("🔄 Extracting genomic information using Vertex AI Gemini...")

    # Handle different input types and get PDF bytes
    if isinstance(pdf_input, bytes):
        logger.info(f"📤 Using PDF bytes ({len(pdf_input)} bytes)")
        pdf_bytes = pdf_input
    elif isinstance(pdf_input, str):
        if "drive.google.com" in pdf_input:
            # Handle Google Drive URLs
            logger.info(f"📥 Downloading PDF from Google Drive: {pdf_input}")
            match = re.search(r'/file/d/([^/]+)', pdf_input)
            if match:
                file_id = match.group(1)
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            else:
                raise ValueError("Could not extract file ID from Google Drive URL")

            response = requests.get(download_url, allow_redirects=True)
            response.raise_for_status()
            pdf_bytes = response.content
            logger.info(f"✅ Downloaded {len(pdf_bytes)} bytes")
        else:
            # Assume it's a local file path
            logger.info(f"📤 Reading PDF from local path: {pdf_input}")
            with open(pdf_input, "rb") as f:
                pdf_bytes = f.read()
    else:
        raise ValueError("pdf_input must be bytes, a local file path, or a Google Drive URL")

    logger.info(f"✅ PDF ready for processing ({len(pdf_bytes)} bytes)")

    # Create extraction prompt
    EXTRACTION_PROMPT = """
You are an Expert Molecular Pathologist and Genomic Analyst specialized in extracting clinically relevant molecular and genomic profiling data from pathology reports and molecular test results or the MD visit notes for use in oncology decision-support systems.

========================
YOUR MISSION
========================

Extract structured, CLINICALLY RELEVANT molecular and genomic profiling data for a precision oncology patient dashboard.

The output must reflect what a practicing medical oncologist would consider meaningful for treatment decisions, prognosis assessment, or clinical trial consideration TODAY.

========================
CRITICAL FOCUS
========================

1. DRIVER MUTATIONS (MANDATORY)
Check for and extract the status of these NINE key oncogenic drivers:

- EGFR, ALK, ROS1, KRAS, BRAF, MET, RET, HER2, NTRK

For EACH driver, always report:
- Status: 'Detected' or 'Not detected'
- Details: Specific variant information or 'Not detected'
- Is_target: True ONLY if explicitly marked as actionable/targetable or visually highlighted as a target in the report

2. BIOMARKERS & IMMUNOTHERAPY MARKERS
Extract if present:
- PD-L1 Expression (value + scoring metric)
- Tumor Mutational Burden (TMB)
- Microsatellite Instability (MSI) status

3. ADDITIONAL GENOMIC ALTERATIONS (STRICTLY FILTERED)
Only include additional alterations that are CLINICALLY RELEVANT.

========================
CLINICAL RELEVANCE DEFINITION (STRICT)
========================

Include an alteration in "additional_genomic_alterations" ONLY if it meets AT LEAST ONE of the following:

TIER 1 – ACTIONABLE
- FDA-approved or guideline-supported targeted therapy
- Biomarker-linked immunotherapy relevance
- Explicitly labeled as Target / Actionable / Matched Therapy

TIER 2 – BIOLOGICALLY / PROGNOSTICALLY RELEVANT
- Pathogenic or likely pathogenic mutations in established cancer genes
- Tumor suppressor or oncogene alterations impacting prognosis, resistance, or disease biology
- Examples include (but are not limited to): TP53, RB1, PTEN, STK11, KEAP1, SMAD4, PIK3CA

TIER 3 – TRIAL-RELEVANT
- Alterations with approved therapies in OTHER indications
- Alterations commonly used for clinical trial enrollment

========================
EXCLUDE COMPLETELY (DO NOT OUTPUT)
========================

- Variants of Uncertain Significance (VUS)
- Alterations labeled as “Potential Clonal Hematopoiesis”
- CHIP-associated genes (e.g., DNMT3A, TET2, ASXL1, PPM1D, NCOR1) unless explicitly confirmed as tumor-derived
- Germline-suspected alterations without clinical confirmation
- Negative results (e.g., “Fusion Not Detected”, “Mutation Not Detected”)
- Redundant or duplicate alterations
- Any alteration that would NOT influence treatment, prognosis, or trial consideration

If NO additional clinically relevant alterations exist, return an EMPTY ARRAY.

========================
EXTRACTION SOURCES
========================

The provided document may include:
- NGS reports (FoundationOne, Guardant360, Tempus, Caris, etc.)
- MD notes summarizing molecular findings
- Molecular pathology reports
- IHC / biomarker reports
- Multiple combined reports or UI-rendered summaries

Extract from ALL available sources.

========================
OUTPUT SCHEMA (STRICT – MUST MATCH EXACTLY)
========================

{
  "driver_mutations": {
    "EGFR": {
      "status": "Detected or Not detected",
      "details": "Specific variant details or Not detected",
      "is_target": "Boolean"
    },
    "ALK": {
      "status": "Detected or Not detected",
      "details": "Specific variant details or Not detected",
      "is_target": "Boolean"
    },
    "ROS1": {
      "status": "Detected or Not detected",
      "details": "Specific variant details or Not detected",
      "is_target": "Boolean"
    },
    "KRAS": {
      "status": "Detected or Not detected",
      "details": "Specific variant details or Not detected",
      "is_target": "Boolean"
    },
    "BRAF": {
      "status": "Detected or Not detected",
      "details": "Specific variant details or Not detected",
      "is_target": "Boolean"
    },
    "MET": {
      "status": "Detected or Not detected",
      "details": "Specific variant details or Not detected",
      "is_target": "Boolean"
    },
    "RET": {
      "status": "Detected or Not detected",
      "details": "Specific variant details or Not detected",
      "is_target": "Boolean"
    },
    "HER2": {
      "status": "Detected or Not detected",
      "details": "Specific variant details or Not detected",
      "is_target": "Boolean"
    },
    "NTRK": {
      "status": "Detected or Not detected",
      "details": "Specific variant details or Not detected",
      "is_target": "Boolean"
    }
  },
  "immunotherapy_markers": {
    "pd_l1": {
      "value": "String or null",
      "metric": "TPS, CPS, IC, or null",
      "interpretation": "High, Low, or null"
    },
    "tmb": {
      "value": "String or null",
      "interpretation": "Low, Intermediate, High, or null"
    },
    "msi_status": {
      "status": "MSS, MSI-High, Stable, Unstable, or null",
      "interpretation": "Microsatellite stable, Microsatellite unstable, or null"
    }
  },
  "additional_genomic_alterations": [
    {
      "gene": "HUGO gene symbol",
      "alteration": "Specific protein or cDNA change",
      "type": "Mutation, Rearrangement, Deletion, Amplification, Copy Number Variation",
      "significance": "Pathogenic, Likely pathogenic, Tier 1, Tier 2, or Tier 3"
    }
  ]
}

========================
DETAILED EXTRACTION RULES
========================

- Driver mutations MUST always be reported, even if not detected
- Additional alterations MUST be filtered using relevance rules above
- If numeric TMB is provided:
  - <5 mutations/Mb → Low
  - 5–9 mutations/Mb → Intermediate
  - ≥10 mutations/Mb → High
- MSS or Stable → Microsatellite stable
- MSI-High or Unstable → Microsatellite unstable
- Visual cues (icons, highlights, badges) indicating “Target” count as actionable

========================
QUALITY CHECKS BEFORE SUBMISSION
========================

✓ Output matches schema EXACTLY  
✓ No VUS or CHIP mutations included  
✓ No negative or non-influential alterations included  
✓ All 9 drivers present  
✓ JSON is valid and machine-parsable  

========================
OUTPUT FORMAT
========================

Return VALID JSON ONLY.
No explanations.
No markdown.
No commentary.
Only the JSON object.
"""

    logger.info("🤖 Requesting genomic data extraction from Vertex AI Gemini...")

    # Initialize model
    model = GenerativeModel("gemini-2.5-flash")

    # Wrap PDF bytes in Part object
    doc_part = Part.from_data(data=pdf_bytes, mime_type="application/pdf")

    # Make API request
    try:
        response = model.generate_content(
            [doc_part, EXTRACTION_PROMPT],
            generation_config={
                "temperature": 0,
                "top_p": 1
            }
        )
        logger.info("✅ Gemini extraction complete")
    except Exception as e:
        logger.error(f"❌ API request failed: {e}")
        raise

    # Parse JSON response
    try:
        # Extract text from the Vertex AI response
        response_text = response.text.strip()

        logger.info(f"📄 Extracted response text ({len(response_text)} chars)")

        # Clean markdown code blocks if present
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, response_text)

        if match:
            response_text = match.group(1).strip()
            logger.info("🧹 Cleaned markdown code blocks from response")
        else:
            response_text = response_text.strip()
            logger.info("ℹ️  No markdown code blocks found, using response as is")

        # Parse JSON
        extracted_data = json.loads(response_text)
        logger.info("✅ Genomic data parsed successfully")
        return extracted_data

    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error(f"❌ Failed to parse Gemini response: {e}")
        logger.error(f"Raw response (first 500 chars): {response_text[:500]}")
        raise


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

            # TM
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


def extract_genomic_info(pdf_url=None, pdf_input=None, use_gemini_api=True):
    """
    Extract genomic/molecular profiling information from a PDF.

    This function supports two extraction approaches controlled by the use_gemini_api toggle:

    1. Gemini API approach (use_gemini_api=True, DEFAULT): Uses Vertex AI Gemini for extraction
    2. Legacy approach (use_gemini_api=False): Uses llmresponsedetailed with Claude

    Args:
        pdf_url (str, optional): URL to the genomic report PDF (Google Drive URL or local path)
        pdf_input (bytes or str, optional): PDF bytes or path. If provided, takes precedence over pdf_url.
        use_gemini_api (bool): Toggle for extraction approach
            - True (default): Use Vertex AI Gemini for extraction
            - False: Use legacy llmresponsedetailed approach with Claude

    Returns:
        dict: Consolidated genomic data including:
            - detected_driver_mutations: List of detected mutations in key driver genes
            - immunotherapy_markers: PD-L1, TMB, MSI status
            - additional_genomic_alterations: Other significant genomic findings
    """
    # Use pdf_input if provided, otherwise fall back to pdf_url
    pdf_source = pdf_input if pdf_input is not None else pdf_url

    if pdf_source is None:
        raise ValueError("Either pdf_url or pdf_input must be provided")

    log_extraction_start(logger, "Genomics Tab", str(pdf_source) if not isinstance(pdf_source, bytes) else f"PDF bytes ({len(pdf_source)} bytes)")

    # Toggle between extraction approaches
    if use_gemini_api:
        logger.info("🔧 Using Vertex AI Gemini approach for extraction")
        logger.info("🔄 Extracting patient genomics data via Gemini API...")

        # Extract using Gemini API (supports both bytes and URLs)
        patient_genomics = extract_genomic_info_with_gemini(pdf_source)

        log_extraction_output(logger, "Genomics Raw Data", patient_genomics)

        # Consolidate and filter data for UI
        logger.info("🔄 Consolidating genomic data for UI...")
        consolidated_data = consolidate_genomic_data(patient_genomics)

        log_extraction_output(logger, "Genomics Consolidated Data", consolidated_data)
        log_extraction_complete(logger, "Genomics Tab", consolidated_data.keys() if isinstance(consolidated_data, dict) else None)

        return consolidated_data

    else:
        logger.info("🔧 Using legacy llmresponsedetailed approach (Claude) for extraction")

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

        config = {
            "start_page": 1,
            "end_page": 40,
            "batch_size": 3,
            "enable_batch_processing": True,
            "model": "claude-sonnet-4-0"
        }

        logger.info("🔄 Extracting patient genomics data via llmresponsedetailed...")

        patient_genomics = llmresponsedetailed(
            pdf_url=pdf_source,
            extraction_instructions=extraction_instructions,
            description=description,
            config=config
        )

        log_extraction_output(logger, "Genomics Raw Data", patient_genomics)

        # Consolidate and filter data for UI
        logger.info("🔄 Consolidating genomic data for UI...")
        consolidated_data = consolidate_genomic_data(patient_genomics)

        log_extraction_output(logger, "Genomics Consolidated Data", consolidated_data)
        log_extraction_complete(logger, "Genomics Tab", consolidated_data.keys() if isinstance(consolidated_data, dict) else None)

        return consolidated_data


# if __name__ == "__main__":
#     # Example usage
#     genomic_info = extract_genomic_info(
#         pdf_url="https://drive.google.com/file/d/1iUeOI1kjD7t5XPtyPVKfH5bq_bZPv352/view?usp=sharing"
#     )
#     print(json.dumps(genomic_info, indent=2))
