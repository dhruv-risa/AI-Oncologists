"""
Test script to check the genomics tab extraction pipeline for a specific MRN.

This will show:
- What documents are fetched (Molecular Results, Pathology Reports, MD Notes)
- How pathology reports are classified (Genomic vs Typical)
- What documents are combined for genomic extraction
- The final extracted genomic data
"""

import sys
import os
import json

# Add Backend directory to path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from main import genomics_tab_info

def test_genomics_pipeline(mrn: str):
    """
    Test the genomics tab extraction pipeline for a specific MRN.

    Args:
        mrn: Patient's Medical Record Number
    """
    print("\n" + "="*80)
    print(f"TESTING GENOMICS TAB EXTRACTION PIPELINE")
    print(f"MRN: {mrn}")
    print("="*80 + "\n")

    try:
        # Run the genomics pipeline with verbose output
        result = genomics_tab_info(mrn=mrn, verbose=True)

        # Print summary
        print("\n" + "="*80)
        print("EXTRACTION SUMMARY")
        print("="*80)
        print(f"\nSuccess: {result.get('success', False)}")

        if result.get('error'):
            print(f"\n❌ Error: {result['error']}")
            return result

        print(f"\n📊 Document Counts:")
        print(f"   - Molecular Results: {result.get('molecular_results_count', 0)}")
        print(f"   - Genomic Pathology Reports: {result.get('genomic_pathology_reports_count', 0)}")
        print(f"   - Typical Pathology Reports (excluded): {result.get('typical_pathology_reports_count', 0)}")
        print(f"   - MD Notes: {result.get('md_notes_count', 0)}")
        print(f"   - Total Combined for Extraction: {result.get('total_documents_count', 0)}")

        print(f"\n📄 Combined PDF URL: {result.get('pdf_url', 'N/A')}")

        # Print genomic data summary
        genomic_info = result.get('genomic_info', {})
        if genomic_info:
            print(f"\n🧬 Extracted Genomic Data:")

            # Driver mutations
            detected_mutations = genomic_info.get('detected_driver_mutations', [])
            print(f"\n   Detected Driver Mutations: {len(detected_mutations)}")
            for mutation in detected_mutations:
                target_marker = "⭐ TARGET" if mutation.get('is_target') else ""
                print(f"      - {mutation['gene']}: {mutation['details']} {target_marker}")

            # Immunotherapy markers
            immuno_markers = genomic_info.get('immunotherapy_markers', {})
            print(f"\n   Immunotherapy Markers:")

            pd_l1 = immuno_markers.get('pd_l1')
            if pd_l1 and pd_l1.get('value'):
                print(f"      - PD-L1: {pd_l1.get('value')} ({pd_l1.get('metric')})")
            else:
                print(f"      - PD-L1: Not measured")

            tmb = immuno_markers.get('tmb')
            if tmb and tmb.get('value'):
                print(f"      - TMB: {tmb.get('value')}")
            else:
                print(f"      - TMB: Not measured")

            msi = immuno_markers.get('msi_status')
            if msi and msi.get('status'):
                print(f"      - MSI Status: {msi.get('status')}")
            else:
                print(f"      - MSI Status: Not measured")

            # Additional alterations
            additional = genomic_info.get('additional_genomic_alterations', [])
            if additional:
                print(f"\n   Additional Genomic Alterations: {len(additional)}")
                for alt in additional:
                    print(f"      - {alt['gene']}: {alt['alteration']} ({alt['type']})")

        # Save full result to file
        output_file = f"genomics_pipeline_result_{mrn}.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n💾 Full result saved to: {output_file}")

        print("\n" + "="*80)
        print("PIPELINE TEST COMPLETE")
        print("="*80 + "\n")

        return result

    except Exception as e:
        print(f"\n❌ Pipeline test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Default test MRN - replace with the MRN you want to test
    test_mrn = input("Enter MRN to test (or press Enter for default '1011109'): ").strip()

    if not test_mrn:
        test_mrn = "1011109"  # Default test MRN

    result = test_genomics_pipeline(test_mrn)
