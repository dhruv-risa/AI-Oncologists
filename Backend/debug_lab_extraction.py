"""
Debug script to see raw LLM output from lab extraction
"""
import sys
import os
import json

# Add Backend to path for imports
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from Backend.Utils.Tabs.lab_tab import extract_lab_info

if __name__ == "__main__":
    pdf_url = "https://drive.google.com/file/d/1O-0tgjgRqXUSNDw9LsWkvw-8V7bk8e7N/view?usp=sharing"

    # Get raw data (before postprocessing)
    print("\n" + "="*80)
    print("RAW LLM OUTPUT (BEFORE POSTPROCESSING)")
    print("="*80)
    raw_data = extract_lab_info(pdf_url, return_raw=True)
    print(json.dumps(raw_data, indent=2))

    # Get processed data
    print("\n" + "="*80)
    print("PROCESSED LAB DATA FOR UI (AFTER POSTPROCESSING)")
    print("="*80)
    processed_data = extract_lab_info(pdf_url, return_raw=False)
    print(json.dumps(processed_data, indent=2))

    # Analysis
    print("\n" + "="*80)
    print("ANALYSIS")
    print("="*80)

    if isinstance(raw_data, list):
        print(f"Raw data type: List with {len(raw_data)} batches")
        for i, batch in enumerate(raw_data):
            print(f"\nBatch {i+1}:")
            print(f"  - Keys: {list(batch.keys())}")
            if "tumor_markers" in batch:
                print(f"  - Tumor markers keys: {list(batch['tumor_markers'].keys())}")
            if "complete_blood_count" in batch:
                print(f"  - CBC keys: {list(batch['complete_blood_count'].keys())}")
            if "metabolic_panel" in batch:
                print(f"  - Metabolic panel keys: {list(batch['metabolic_panel'].keys())}")
    else:
        print(f"Raw data type: Dictionary")
        print(f"  - Keys: {list(raw_data.keys())}")
        if "tumor_markers" in raw_data:
            print(f"  - Tumor markers keys: {list(raw_data['tumor_markers'].keys())}")
        if "complete_blood_count" in raw_data:
            print(f"  - CBC keys: {list(raw_data['complete_blood_count'].keys())}")
        if "metabolic_panel" in raw_data:
            print(f"  - Metabolic panel keys: {list(raw_data['metabolic_panel'].keys())}")
