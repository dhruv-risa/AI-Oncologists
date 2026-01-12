"""
Verification Pipeline for Genomics Tab Extraction

This script verifies the complete genomics extraction pipeline:
1. Fetches molecular pathology reports + MD notes (only these contain genomic info)
2. Combines them into a single PDF
3. Extracts genomics data with batch processing
4. Shows raw LLM response before consolidation
5. Shows consolidated/filtered results
"""
import json
import sys
import os

# Add Backend to path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "./"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from bytes_extractor import extract_report_with_MD, fetch_and_combine_pdfs_from_urls
from Utils.Tabs.genomics_tab import extract_genomic_info, consolidate_genomic_data
from Utils.Tabs.llmparser import llmresponsedetailed


def verify_genomics_extraction_pipeline(mrn: str):
    """
    Complete verification of genomics extraction pipeline with detailed output.
    """
    print("="*80)
    print("GENOMICS EXTRACTION VERIFICATION PIPELINE")
    print("="*80)
    print(f"\nMRN: {mrn}\n")

    # Step 1: Fetch molecular pathology reports and MD notes (genomic data sources)
    print("[Step 1/5] Fetching molecular pathology reports and MD notes...")
    print("-"*80)

    pathology_documents = extract_report_with_MD(mrn=mrn, report_type="pathology", include_md_notes=True)

    if not pathology_documents:
        print("❌ No pathology reports found for this MRN")
        return

    print(f"✓ Found {len(pathology_documents)} documents:\n")

    molecular_docs = []
    md_notes_docs = []

    for idx, doc in enumerate(pathology_documents, 1):
        doc_type = doc.get('document_type', '').lower()
        description = doc.get('description', '').lower()

        # Categorize the document
        is_md_note = any(x in doc_type for x in ['md', 'physician', 'progress'])
        is_molecular = ('molecular' in description or 'genomic' in description or
                       any(keyword in description for keyword in ['ngs', 'sequencing', 'panel', 'mutation']))

        category = ""
        if is_md_note:
            category = "[MD NOTE]"
            md_notes_docs.append(doc)
        elif is_molecular:
            category = "[MOLECULAR PATHOLOGY]"
            molecular_docs.append(doc)
        else:
            category = "[PATHOLOGY]"

        print(f"  {idx}. {category} [{doc.get('document_type')}] {doc.get('description')}")
        print(f"     Date: {doc.get('date')}")
        print(f"     Document ID: {doc.get('document_id')}\n")

    # Verification summary for extracted document types
    print("\n📋 Document Type Verification:")
    print(f"   Molecular/Genomic Pathology: {len(molecular_docs)}")
    print(f"   MD Notes: {len(md_notes_docs)}")
    print(f"   ✓ Only molecular pathology and MD notes will be used for genomic extraction\n")

    # Filter to keep only molecular pathology and MD notes
    filtered_documents = molecular_docs + md_notes_docs

    if not filtered_documents:
        print("❌ No molecular pathology reports or MD notes found for genomic extraction")
        return

    print(f"✓ Filtered to {len(filtered_documents)} documents for genomic extraction")
    print(f"   (Excluded {len(pathology_documents) - len(filtered_documents)} general pathology reports)\n")

    # Step 2: Combine PDFs (only molecular pathology and MD notes)
    print("\n[Step 2/5] Combining molecular pathology and MD notes into single PDF...")
    print("-"*80)

    urls = [doc['url'] for doc in filtered_documents]

    upload_result = fetch_and_combine_pdfs_from_urls(
        fhir_urls=urls,
        output_file_name=f"{mrn}.pdf"
    )

    combined_pdf_url = upload_result['shareable_url']
    print(f"✓ Combined PDF created: {combined_pdf_url}\n")

    # Step 3: Extract genomics with batch processing (raw LLM response)
    print("\n[Step 3/5] Extracting genomics data with batch processing...")
    print("-"*80)

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
        "end_page": 30,
        "batch_size": 3,
        "enable_batch_processing": True,
        "model": "claude-sonnet-4-0"
    }

    print(f"Config: batch_size={config['batch_size']}, pages {config['start_page']}-{config['end_page']}, model={config['model']}\n")

    patient_genomics = llmresponsedetailed(
        pdf_url=combined_pdf_url,
        extraction_instructions=extraction_instructions,
        description=description,
        config=config
    )

    print("✓ Raw LLM response received\n")

    # Step 4: Show raw LLM response
    print("\n[Step 4/5] Raw LLM Response (Before Consolidation)")
    print("-"*80)
    print(json.dumps(patient_genomics, indent=2))

    # Step 5: Consolidate and show results
    print("\n[Step 5/5] Consolidated Results (After Filtering)")
    print("-"*80)

    consolidated_data = consolidate_genomic_data(patient_genomics)
    print(json.dumps(consolidated_data, indent=2))

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total documents fetched: {len(pathology_documents)}")
    print(f"Documents used for genomic extraction: {len(filtered_documents)}")
    print(f"  - Molecular/Genomic Pathology reports: {len(molecular_docs)}")
    print(f"  - MD notes: {len(md_notes_docs)}")
    print(f"Documents excluded (general pathology): {len(pathology_documents) - len(filtered_documents)}")
    print(f"\nDetected driver mutations: {len(consolidated_data['detected_driver_mutations'])}")
    print(f"Immunotherapy markers: {len(consolidated_data['immunotherapy_markers'])}")
    print(f"Additional genomic alterations: {len(consolidated_data['additional_genomic_alterations'])}")

    if consolidated_data['detected_driver_mutations']:
        print("\n✓ Driver mutations found:")
        for mutation in consolidated_data['detected_driver_mutations']:
            print(f"  - {mutation['gene']}: {mutation['status']}")

    if consolidated_data['immunotherapy_markers']:
        print("\n✓ Immunotherapy markers found:")
        for marker, data in consolidated_data['immunotherapy_markers'].items():
            print(f"  - {marker}: {data}")

    if consolidated_data['additional_genomic_alterations']:
        print(f"\n✓ Additional alterations found: {len(consolidated_data['additional_genomic_alterations'])} genes")

    if (not consolidated_data['detected_driver_mutations'] and
        not consolidated_data['immunotherapy_markers'] and
        not consolidated_data['additional_genomic_alterations']):
        print("\n⚠️  WARNING: No genomic data found in the reports.")

    print("="*80)


if __name__ == "__main__":
    # Test with MRN
    mrn = "A2451440"  # Replace with your test MRN

    if len(sys.argv) > 1:
        mrn = sys.argv[1]

    try:
        verify_genomics_extraction_pipeline(mrn)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
