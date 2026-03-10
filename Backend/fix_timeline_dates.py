"""
Utility script to fix timeline date ordering in cached patient data.

This script:
1. Reads cached patient data from the data pool
2. Normalizes vague date terms (e.g., "Late 2025" → "December 2025")
3. Updates the cache with normalized dates
4. Shows before/after comparison

Usage:
    python fix_timeline_dates.py --mrn <MRN>
    python fix_timeline_dates.py --all  # Fix all cached patients
"""
import sys
import os
import json
from typing import Dict, List

# Add Backend to path
BACKEND_DIR = os.path.dirname(__file__)
sys.path.insert(0, BACKEND_DIR)

from data_pool import get_data_pool


def print_timeline_dates(timeline: List[Dict], label: str):
    """Print timeline dates for comparison."""
    print(f"\n{label}:")
    print("-" * 60)
    for idx, event in enumerate(timeline, 1):
        date_label = event.get('date_label', 'N/A')
        stage = event.get('stage_header', 'N/A')
        print(f"  {idx}. {date_label:30} [{stage}]")
    print("-" * 60)


def fix_patient_timeline(mrn: str, data_pool, verbose: bool = True):
    """Fix timeline dates for a single patient."""
    print(f"\n{'='*70}")
    print(f"Processing MRN: {mrn}")
    print(f"{'='*70}")

    # Get cached data (this now automatically normalizes dates)
    patient_data = data_pool.get_patient_data(mrn)

    if not patient_data:
        print(f"❌ No cached data found for MRN: {mrn}")
        return False

    # Check if timeline exists
    if 'diagnosis_evolution_timeline' not in patient_data:
        print(f"⚠️  No diagnosis_evolution_timeline found for MRN: {mrn}")
        return False

    timeline = patient_data.get('diagnosis_evolution_timeline', {}).get('timeline', [])

    if not timeline:
        print(f"⚠️  Timeline is empty for MRN: {mrn}")
        return False

    # Show dates
    if verbose:
        print_timeline_dates(timeline, "Timeline dates (after normalization)")

    # Update cache with normalized data
    success = data_pool.store_patient_data(mrn=mrn, data=patient_data)

    if success:
        print(f"\n✅ Successfully updated cache for MRN: {mrn}")
        print(f"   Timeline entries: {len(timeline)}")
    else:
        print(f"\n❌ Failed to update cache for MRN: {mrn}")

    return success


def fix_all_patients(data_pool, verbose: bool = True):
    """Fix timeline dates for all cached patients."""
    patients = data_pool.list_all_patients()

    if not patients:
        print("No patients found in data pool.")
        return

    print(f"\nFound {len(patients)} patients in data pool")
    print(f"{'='*70}\n")

    success_count = 0
    error_count = 0

    for patient in patients:
        mrn = patient['mrn']
        try:
            if fix_patient_timeline(mrn, data_pool, verbose=verbose):
                success_count += 1
            else:
                error_count += 1
        except Exception as e:
            print(f"❌ Error processing MRN {mrn}: {str(e)}")
            error_count += 1

    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"✅ Successfully processed: {success_count}")
    print(f"❌ Errors: {error_count}")
    print(f"Total: {len(patients)}")
    print(f"{'='*70}\n")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Fix timeline date ordering in cached patient data'
    )
    parser.add_argument(
        '--mrn',
        type=str,
        help='MRN of patient to fix'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Fix all cached patients'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Minimize output'
    )

    args = parser.parse_args()

    if not args.mrn and not args.all:
        parser.print_help()
        print("\nError: Must specify either --mrn or --all")
        sys.exit(1)

    # Initialize data pool
    data_pool = get_data_pool()
    verbose = not args.quiet

    if args.all:
        fix_all_patients(data_pool, verbose=verbose)
    else:
        fix_patient_timeline(args.mrn, data_pool, verbose=verbose)


if __name__ == '__main__':
    main()
