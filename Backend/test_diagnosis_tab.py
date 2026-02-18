"""
Test script for diagnosis tab extraction - Patient MRN: 2512120056
"""
import json
import sys
from Utils.Tabs.diagnosis_tab import diagnosis_extraction

def test_diagnosis_for_patient(mrn):
    """Test diagnosis extraction for a specific patient MRN"""

    print(f"\n{'='*80}")
    print(f"Testing Diagnosis Tab for Patient MRN: {mrn}")
    print(f"{'='*80}\n")

    # Load demo data
    try:
        with open('demo_data.json', 'r') as f:
            demo_data = json.load(f)
    except FileNotFoundError:
        print("❌ Error: demo_data.json not found")
        return

    # Check if patient exists
    if mrn not in demo_data:
        print(f"❌ Error: Patient MRN {mrn} not found in demo data")
        print(f"Available MRNs: {list(demo_data.keys())}")
        return

    patient_data = demo_data[mrn]
    print(f"✓ Found patient data for MRN: {mrn}")
    print(f"\nPatient has the following document types:")
    for doc_type, docs in patient_data.items():
        print(f"  - {doc_type}: {len(docs)} document(s)")

    # Get MD notes (which typically contain diagnosis information)
    md_notes = patient_data.get('md_notes', [])
    if not md_notes:
        
        print("\n❌ No MD notes found for this patient")
        return

    print(f"\n{'='*80}")
    print(f"Testing Diagnosis Extraction on {len(md_notes)} MD Note(s)")
    print(f"{'='*80}\n")

    # Test diagnosis extraction on each MD note
    for idx, doc_url in enumerate(md_notes, 1):
        print(f"\n{'─'*80}")
        print(f"Document {idx}/{len(md_notes)}")
        print(f"URL: {doc_url}")
        print(f"{'─'*80}\n")

        try:
            # Extract diagnosis information
            diagnosis_header, diagnosis_evolution, diagnosis_footer = diagnosis_extraction(
                pdf_input=doc_url,
                use_gemini=True
            )

            # Display results
            print("✓ Extraction completed successfully!\n")

            print("📋 DIAGNOSIS HEADER:")
            print("-" * 40)
            print(json.dumps(diagnosis_header, indent=2))

            print("\n📊 DIAGNOSIS EVOLUTION TIMELINE:")
            print("-" * 40)
            print(json.dumps(diagnosis_evolution, indent=2))

            print("\n📈 DIAGNOSIS FOOTER:")
            print("-" * 40)
            print(json.dumps(diagnosis_footer, indent=2))

            print("\n" + "="*80)

        except Exception as e:
            print(f"❌ Error during extraction:")
            print(f"   {type(e).__name__}: {str(e)}")
            import traceback
            print("\nFull traceback:")
            traceback.print_exc()

    print("\n" + "="*80)
    print("Testing Complete")
    print("="*80 + "\n")

if __name__ == "__main__":
    # Test for MRN 2512120056
    test_diagnosis_for_patient("2512120056")
