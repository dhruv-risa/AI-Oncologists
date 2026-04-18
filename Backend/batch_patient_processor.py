#!/usr/bin/env python3
"""
Batch Patient Processor
Processes multiple patients through complete pipeline via API and exports to CSV
"""

import argparse
import logging
from datetime import datetime
from pathlib import Path
import sys
import time
import requests

# Add parent directory to path for imports
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import for database and CSV export
from Backend.database_manager import get_database_manager
from Backend.export_trials_for_validation import export_eligibility_to_csv

# Initialize database manager
db_manager = get_database_manager()


def get_database_pool(db_type: str = "astera"):
    """
    Get the appropriate database pool based on db_type parameter.

    Args:
        db_type: Either "demo" or "astera" (default: "astera")

    Returns:
        DataPool instance for the specified database
    """
    if db_type not in ["demo", "astera"]:
        db_type = "astera"  # Default to astera for invalid values
    return db_manager.get_pool(db_type)


def main():
    """Main entry point"""

    # 1. PARSE COMMAND LINE ARGUMENTS
    args = parse_arguments()

    # 2. SETUP LOGGING
    setup_logging(args.verbose)

    # 3. LOAD MRN LIST
    mrn_list = load_mrn_list(args)
    logging.info(f"Loaded {len(mrn_list)} MRNs to process")

    # 4. INITIALIZE DATABASE (for checking already processed)
    data_pool = get_database_pool(args.db_type)
    logging.info(f"Connected to {args.db_type} database")

    # 5. FILTER OUT ALREADY PROCESSED PATIENTS (unless --force flag is used)
    # This ensures we only process NEW patients by default
    if not args.force:
        original_count = len(mrn_list)
        mrn_list = filter_unprocessed_patients(mrn_list, data_pool)
        skipped_count = original_count - len(mrn_list)

        if skipped_count > 0:
            logging.info(f"Skipped {skipped_count} patients already in database")
        logging.info(f"{len(mrn_list)} NEW patients to process")

        if len(mrn_list) == 0:
            logging.info("No NEW patients to process. All patients already exist in database.")
            logging.info("Use --force flag to reprocess existing patients.")
            sys.exit(0)
    else:
        logging.warning("⚠️  --force flag detected: Will reprocess patients already in database")
        logging.warning("   Existing eligibility data will be OVERWRITTEN")

    # 6. DRY RUN CHECK
    if args.dry_run:
        logging.info("DRY RUN - No processing will occur")
        logging.info(f"Would process {len(mrn_list)} patients:")
        for mrn in mrn_list:
            logging.info(f"  - {mrn}")
        sys.exit(0)

    # 7. DETERMINE OUTPUT PATH
    backend_dir = Path(__file__).parent
    if args.output:
        output_path = args.output
    else:
        # Default to patient_ct_results.csv (single file, not timestamped)
        output_path = str(backend_dir / "patient_ct_results.csv")

    # 8. PROCESS ALL PATIENTS with incremental CSV updates
    all_processed_mrns = []

    for idx, mrn in enumerate(mrn_list, 1):
        logging.info(f"\n{'='*60}")
        logging.info(f"Processing patient {idx}/{len(mrn_list)}: {mrn}")
        logging.info(f"{'='*60}")

        try:
            # Process patient via API
            process_single_patient_via_api(
                mrn=mrn,
                api_base_url=args.api_url,
                db_type=args.db_type,
                max_retries=args.max_retries,
                timeout=args.timeout
            )
            logging.info(f"✅ Patient {mrn} extraction complete")

            # Wait for eligibility computation to complete for THIS patient
            logging.info(f"\nWaiting for eligibility computation for {mrn}...")
            wait_for_eligibility_completion(
                patient_mrns=[mrn],
                db_type=args.db_type,
                timeout=600
            )

            # Export/update CSV with THIS patient's data
            all_processed_mrns.append(mrn)
            logging.info(f"\nUpdating CSV with results for {mrn}...")
            export_to_csv(
                output_path=output_path,
                patient_mrns=all_processed_mrns,  # All patients processed so far
                db_type=args.db_type
            )

        except Exception as e:
            logging.error(f"❌ Failed to process {mrn}: {str(e)}")

        # Delay between patients
        if idx < len(mrn_list) and args.delay > 0:
            logging.info(f"Waiting {args.delay} seconds before next patient...")
            time.sleep(args.delay)

    # 9. PRINT COMPLETION REPORT
    results = {"success": all_processed_mrns, "failed": []}
    print_completion_report(results, output_path if all_processed_mrns else None)


def process_all_patients(mrn_list, api_base_url, db_type, delay, max_retries, timeout):
    """Process all patients sequentially by calling the API"""

    results = {"success": [], "failed": []}
    total = len(mrn_list)
    start_time = time.time()

    for idx, mrn in enumerate(mrn_list, 1):
        logging.info(f"\n{'='*60}")
        logging.info(f"Processing patient {idx}/{total}: {mrn}")
        logging.info(f"{'='*60}")

        try:
            # Call API endpoint (same as UI does)
            process_single_patient_via_api(
                mrn=mrn,
                api_base_url=api_base_url,
                db_type=db_type,
                max_retries=max_retries,
                timeout=timeout
            )

            results["success"].append(mrn)
            logging.info(f"✅ Patient {mrn} processed successfully")

        except Exception as e:
            logging.error(f"❌ Failed to process {mrn}: {str(e)}")
            results["failed"].append({"mrn": mrn, "error": str(e)})

        # Progress update
        elapsed = time.time() - start_time
        avg_time = elapsed / idx
        remaining = (total - idx) * avg_time
        logging.info(f"\nProgress: {idx}/{total} ({idx/total*100:.1f}%)")
        if idx < total:
            logging.info(f"Est. remaining: {remaining/60:.1f} minutes")

        # Delay between patients (except last one)
        if idx < total and delay > 0:
            logging.info(f"Waiting {delay} seconds before next patient...")
            time.sleep(delay)

    return results


def process_single_patient_via_api(mrn, api_base_url, db_type, max_retries, timeout):
    """Process a single patient by calling the API endpoint (same as UI)"""

    retry_count = 0
    last_error = None

    while retry_count < max_retries:
        try:
            # Call the POST /api/patient/all endpoint
            # This is the EXACT same endpoint the UI calls
            url = f"{api_base_url}/api/patient/all"
            payload = {
                "mrn": mrn,
                "db_type": db_type
            }

            logging.info(f"Calling API: POST {url}")
            logging.info(f"Timeout set to: {timeout} seconds ({timeout/60:.1f} minutes)")
            logging.debug(f"Payload: {payload}")

            response = requests.post(
                url,
                json=payload,
                timeout=timeout
            )

            # Check response
            if response.status_code == 200:
                result = response.json()

                if result.get("success"):
                    logging.info("✅ API call successful")
                    logging.info(f"   - Patient data extracted and stored in database")
                    logging.info(f"   - Background eligibility computation started")
                    return result
                else:
                    error_msg = result.get("error", "Unknown error")
                    raise Exception(f"API returned success=False: {error_msg}")

            else:
                raise Exception(f"API returned status {response.status_code}: {response.text}")

        except requests.exceptions.ConnectionError as e:
            raise Exception(f"Cannot connect to API server at {api_base_url}. Make sure the server is running with: python -m uvicorn Backend.app:app --reload")

        except requests.exceptions.Timeout as e:
            retry_count += 1
            last_error = Exception(f"API timeout after 10 minutes")
            if retry_count < max_retries:
                wait_time = 2 ** retry_count  # Exponential backoff
                logging.warning(f"Retry {retry_count}/{max_retries} after {wait_time}s: Timeout")
                time.sleep(wait_time)
            else:
                logging.error(f"Max retries reached for {mrn}")
                raise last_error

        except Exception as e:
            retry_count += 1
            last_error = e
            if retry_count < max_retries:
                wait_time = 2 ** retry_count  # Exponential backoff
                logging.warning(f"Retry {retry_count}/{max_retries} after {wait_time}s: {str(e)}")
                time.sleep(wait_time)
            else:
                logging.error(f"Max retries reached for {mrn}")
                raise last_error


def wait_for_eligibility_completion(patient_mrns, db_type, timeout=600):
    """Wait for background eligibility computation to complete for ALL trials

    This function ensures that ALL 9 required trials have been computed for each patient
    before proceeding with CSV export.
    """

    logging.info("\n" + "="*60)
    logging.info("Waiting for COMPLETE Eligibility Computation")
    logging.info("="*60)

    data_pool = get_database_pool(db_type)

    # Expected number of trials (from app.py ALLOWED_TRIAL_NCT_IDS)
    EXPECTED_TRIAL_COUNT = 9

    for mrn in patient_mrns:
        logging.info(f"Waiting for {mrn} eligibility computation (expecting {EXPECTED_TRIAL_COUNT} trials)...")
        patient_start_time = time.time()
        last_count = 0

        while True:
            # Check if eligibility has been computed for ALL trials
            # Query eligibility_matrix directly to count trials
            try:
                # Get count of trials computed for this patient
                import sqlite3
                backend_dir = Path(__file__).parent
                if db_type == "astera":
                    db_path = backend_dir / "astera_patients.db"
                else:
                    db_path = backend_dir / "demo_patients.db"

                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM eligibility_matrix WHERE patient_mrn = ?",
                    (mrn,)
                )
                trials_computed = cursor.fetchone()[0]
                conn.close()

                # Log progress if count changed
                if trials_computed != last_count:
                    logging.info(f"   Progress: {trials_computed}/{EXPECTED_TRIAL_COUNT} trials computed")
                    last_count = trials_computed

                # Check if all trials are computed
                if trials_computed >= EXPECTED_TRIAL_COUNT:
                    logging.info(f"✅ {mrn} eligibility COMPLETE ({trials_computed} trials)")
                    break

            except Exception as e:
                logging.debug(f"Waiting for {mrn}: {str(e)}")

            # Check timeout for this patient
            elapsed = time.time() - patient_start_time
            if elapsed > timeout:
                logging.warning(f"⚠️  Timeout waiting for {mrn} eligibility (waited {int(elapsed)}s, computed {last_count}/{EXPECTED_TRIAL_COUNT} trials)")
                logging.warning(f"    Proceeding with partial data...")
                break

            # Wait before checking again
            time.sleep(3)

    logging.info("✅ All eligibility computations complete or timed out")


def export_to_csv(output_path, patient_mrns, db_type):
    """Export eligibility results to CSV for newly processed patients only

    This exports ONLY the patients that were just processed (not existing patients).
    If the output file exists, it will be OVERWRITTEN (not appended).
    """

    logging.info("\n" + "="*60)
    logging.info("Exporting to CSV")
    logging.info("="*60)

    # Determine database path
    backend_dir = Path(__file__).parent
    if db_type == "astera":
        db_path = backend_dir / "astera_patients.db"
    else:
        db_path = backend_dir / "demo_patients.db"

    logging.info(f"Exporting eligibility data for {len(patient_mrns)} NEW patients:")
    for mrn in patient_mrns:
        logging.info(f"  - {mrn}")

    # Check if file exists to determine mode
    file_exists = Path(output_path).exists()
    if file_exists:
        logging.info(f"⚠️  File exists: {output_path}")
        logging.info(f"   Mode: OVERWRITE (will replace existing content)")
    else:
        logging.info(f"📝 Creating new file: {output_path}")

    # Export CSV for ONLY the newly processed patients
    # We export each patient individually and combine results
    import sqlite3
    import json
    import csv

    all_csv_rows = []

    for mrn in patient_mrns:
        logging.info(f"Extracting data for patient {mrn}...")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Get all eligibility data for this patient
        cursor.execute("""
            SELECT
                patient_mrn,
                trial_nct_id,
                eligibility_status,
                eligibility_percentage,
                criteria_results,
                computed_at
            FROM eligibility_matrix
            WHERE patient_mrn = ?
            ORDER BY trial_nct_id
        """, (mrn,))

        rows = cursor.fetchall()
        logging.info(f"  Found {len(rows)} trials for patient {mrn}")

        for row in rows:
            patient_mrn, trial_nct_id, eligibility_status, eligibility_percentage, criteria_results_json, computed_at = row

            try:
                criteria_results = json.loads(criteria_results_json) if criteria_results_json else {}
            except json.JSONDecodeError:
                logging.warning(f"  Could not parse criteria_results for {patient_mrn} / {trial_nct_id}")
                continue

            # Process inclusion criteria
            for criterion in criteria_results.get("inclusion", []):
                all_csv_rows.append({
                    "Patient MRN": patient_mrn,
                    "Trial NCT Code": trial_nct_id,
                    "Inclusion / Exclusion criteria": "Inclusion",
                    "Criterion Number": criterion.get("criterion_number", ""),
                    "Criteria": criterion.get("original_criterion_text", criterion.get("criterion_text", "")),
                    "Patient Value": criterion.get("patient_value", ""),
                    "LLM Decision (met)": criterion.get("met", ""),
                    "Confidence": criterion.get("confidence", ""),
                    "LLM Explanation": criterion.get("explanation", ""),
                    "Ground Truth (met)": "",
                    "Accuracy Benchmarking": "",
                    "Document reference": "",
                    "Observations": "",
                    "Manually Resolved": criterion.get("manually_resolved", False),
                    "Resolved By": criterion.get("resolved_by", ""),
                    "Review Type": criterion.get("review_type", ""),
                    "Suggested Test": criterion.get("suggested_test", ""),
                    "Clinician Action": criterion.get("clinician_action", ""),
                    "Overall Eligibility Status": eligibility_status,
                    "Overall Eligibility %": eligibility_percentage,
                    "Computed At": computed_at
                })

            # Process exclusion criteria
            for criterion in criteria_results.get("exclusion", []):
                all_csv_rows.append({
                    "Patient MRN": patient_mrn,
                    "Trial NCT Code": trial_nct_id,
                    "Inclusion / Exclusion criteria": "Exclusion",
                    "Criterion Number": criterion.get("criterion_number", ""),
                    "Criteria": criterion.get("original_criterion_text", criterion.get("criterion_text", "")),
                    "Patient Value": criterion.get("patient_value", ""),
                    "LLM Decision (met)": criterion.get("met", ""),
                    "Confidence": criterion.get("confidence", ""),
                    "LLM Explanation": criterion.get("explanation", ""),
                    "Ground Truth (met)": "",
                    "Accuracy Benchmarking": "",
                    "Document reference": "",
                    "Observations": "",
                    "Manually Resolved": criterion.get("manually_resolved", False),
                    "Resolved By": criterion.get("resolved_by", ""),
                    "Review Type": criterion.get("review_type", ""),
                    "Suggested Test": criterion.get("suggested_test", ""),
                    "Clinician Action": criterion.get("clinician_action", ""),
                    "Overall Eligibility Status": eligibility_status,
                    "Overall Eligibility %": eligibility_percentage,
                    "Computed At": computed_at
                })

        conn.close()

    # Write CSV (OVERWRITE mode)
    if all_csv_rows:
        fieldnames = [
            "Patient MRN",
            "Trial NCT Code",
            "Inclusion / Exclusion criteria",
            "Criterion Number",
            "Criteria",
            "Patient Value",
            "LLM Decision (met)",
            "Confidence",
            "LLM Explanation",
            "Ground Truth (met)",
            "Accuracy Benchmarking",
            "Document reference",
            "Observations",
            "Manually Resolved",
            "Resolved By",
            "Review Type",
            "Suggested Test",
            "Clinician Action",
            "Overall Eligibility Status",
            "Overall Eligibility %",
            "Computed At"
        ]

        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_csv_rows)

        logging.info(f"✅ CSV exported to: {output_path}")
        logging.info(f"   Total criteria: {len(all_csv_rows)}")
        logging.info(f"   Patients: {len(set(row['Patient MRN'] for row in all_csv_rows))}")
        logging.info(f"   Trials: {len(set(row['Trial NCT Code'] for row in all_csv_rows))}")
    else:
        logging.error(f"❌ Failed to export CSV - no eligibility data found")
        logging.error(f"   Patients: {patient_mrns}")
        raise Exception("CSV export failed - no eligibility data found for processed patients")


# HELPER FUNCTIONS

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Batch process patients through complete pipeline via API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Basic Usage:
  # 1. Create patients.txt in Backend directory with one MRN per line
  # 2. Run the processor:
  python batch_patient_processor.py

  # The script will:
  #  - Read MRNs from patients.txt
  #  - Skip any patients already in the database
  #  - Process only NEW patients
  #  - Wait for ALL 9 trials to be computed
  #  - Export results to patient_ct_results.csv

Examples:
  # Use default patients.txt file
  python batch_patient_processor.py

  # Use custom MRN file
  python batch_patient_processor.py --mrn-file my_patients.txt

  # Provide MRNs directly from command line
  python batch_patient_processor.py --mrns MRN001 MRN002 MRN003

  # Custom output filename
  python batch_patient_processor.py --output my_results.csv

  # Dry run to see which patients will be processed
  python batch_patient_processor.py --dry-run

  # Force reprocess existing patients (WARNING: overwrites data)
  python batch_patient_processor.py --force

Important Notes:
  - Only NEW patients (not in database) will be processed by default
  - Existing patients are automatically skipped (use --force to override)
  - Output defaults to patient_ct_results.csv (overwrites if exists)
  - Waits for ALL 9 trials to be computed before exporting
  - Each patient takes ~2-3 minutes to process completely

Prerequisites:
  - API server must be running: python -m uvicorn Backend.app:app --reload
  - Server should be accessible at http://localhost:8000 (or use --api-url)
  - Trials must be synced to the database first
        """
    )

    # MRN input (defaults to patients.txt)
    mrn_group = parser.add_mutually_exclusive_group(required=False)
    mrn_group.add_argument("--mrn-file", type=str, default="patients.txt",
                          help="Path to file with MRNs (default: patients.txt in Backend directory)")
    mrn_group.add_argument("--mrns", nargs="+", help="Space-separated list of MRNs (overrides --mrn-file)")

    # API configuration
    parser.add_argument("--api-url", type=str, default="http://localhost:8000",
                       help="API base URL (default: http://localhost:8000)")

    # Optional arguments
    parser.add_argument("--output", type=str, help="Output CSV path (default: patient_ct_results.csv)")
    parser.add_argument("--db-type", choices=["demo", "astera"], default="astera",
                       help="Database type (default: astera)")
    parser.add_argument("--delay", type=int, default=5,
                       help="Delay between patients in seconds (default: 5)")
    parser.add_argument("--max-retries", type=int, default=2,
                       help="Max retries per patient (default: 2)")
    parser.add_argument("--timeout", type=int, default=3600,
                       help="API timeout per patient in seconds (default: 3600 = 1 hour)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Validate inputs without processing")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable detailed logging")
    parser.add_argument("--force", action="store_true",
                       help="Force reprocessing of patients already in database (WARNING: will overwrite existing data)")

    return parser.parse_args()


def load_mrn_list(args):
    """Load MRN list from file or command line

    If --mrns is provided, use those MRNs.
    Otherwise, read from file specified by --mrn-file (defaults to patients.txt in Backend dir).
    """
    if args.mrns:
        # Command line MRNs take precedence
        mrns = args.mrns
        logging.info(f"Using MRNs from command line: {len(mrns)} patients")
    else:
        # Read from file (default: patients.txt in Backend directory)
        backend_dir = Path(__file__).parent
        file_path = Path(args.mrn_file)

        # If path is not absolute, make it relative to Backend directory
        if not file_path.is_absolute():
            file_path = backend_dir / file_path

        if not file_path.exists():
            logging.error(f"MRN file not found: {file_path}")
            logging.error(f"Please create a patients.txt file in the Backend directory with one MRN per line")
            logging.error(f"Or use --mrns to provide MRNs directly from command line")
            sys.exit(1)

        with open(file_path, 'r') as f:
            mrns = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

        if not mrns:
            logging.error(f"No MRNs found in file: {file_path}")
            logging.error(f"Please add at least one MRN (one per line)")
            sys.exit(1)

        logging.info(f"Loaded MRNs from file: {file_path}")

    # Remove duplicates while preserving order
    seen = set()
    unique_mrns = []
    for mrn in mrns:
        if mrn not in seen:
            seen.add(mrn)
            unique_mrns.append(mrn)

    if len(unique_mrns) < len(mrns):
        logging.warning(f"Removed {len(mrns) - len(unique_mrns)} duplicate MRNs")

    return unique_mrns


def setup_logging(verbose):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )


def filter_unprocessed_patients(mrn_list, data_pool):
    """Filter out patients already in database"""
    unprocessed = []
    for mrn in mrn_list:
        if not data_pool.patient_exists(mrn):
            unprocessed.append(mrn)
        else:
            logging.info(f"Skipping {mrn} (already processed)")
    return unprocessed


def generate_output_filename():
    """Generate timestamped output filename"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"batch_results_{timestamp}.csv"


def print_completion_report(results, output_path):
    """Print final completion report"""
    print("\n" + "="*60)
    print("BATCH PROCESSING COMPLETE")
    print("="*60)
    print(f"Total patients: {len(results['success']) + len(results['failed'])}")
    print(f"✅ Successful: {len(results['success'])}")
    print(f"❌ Failed: {len(results['failed'])}")

    if results['success']:
        print("\nSuccessfully processed patients:")
        for mrn in results['success']:
            print(f"  ✅ {mrn}")

    if results['failed']:
        print("\nFailed patients:")
        for failure in results['failed']:
            print(f"  ❌ {failure['mrn']}: {failure['error']}")

    if output_path:
        print(f"\n📄 CSV output: {output_path}")

    print("="*60)


if __name__ == "__main__":
    main()
