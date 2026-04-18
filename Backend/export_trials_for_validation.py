"""
Export Clinical Trials Eligibility Data for Validation

This script exports trial criteria with corresponding patient values to CSV format
for accuracy verification and benchmarking.
"""

import sqlite3
import json
import csv
from datetime import datetime
from pathlib import Path
import argparse


def export_eligibility_to_csv(db_path: str, output_path: str = None, patient_mrn: str = None, trial_nct_id: str = None, exclude_patients: list = None):
    """
    Export eligibility data from database to CSV for validation.

    Args:
        db_path: Path to SQLite database
        output_path: Path for output CSV (default: auto-generated)
        patient_mrn: Optional filter for specific patient
        trial_nct_id: Optional filter for specific trial
        exclude_patients: Optional list of patient MRNs to exclude
    """

    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"clinical_trials_validation_{timestamp}.csv"

    # Ensure parent directory exists
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Build query with optional filters
    # IMPORTANT: Only include patients that exist in patient_data_pool (active patients)
    query = """
        SELECT
            patient_mrn,
            trial_nct_id,
            eligibility_status,
            eligibility_percentage,
            criteria_results,
            computed_at
        FROM eligibility_matrix
        WHERE patient_mrn IN (SELECT mrn FROM patient_data_pool)
    """
    params = []

    if patient_mrn:
        query += " AND patient_mrn = ?"
        params.append(patient_mrn)

    if trial_nct_id:
        query += " AND trial_nct_id = ?"
        params.append(trial_nct_id)

    if exclude_patients:
        placeholders = ",".join("?" * len(exclude_patients))
        query += f" AND patient_mrn NOT IN ({placeholders})"
        params.extend(exclude_patients)

    query += " ORDER BY patient_mrn, trial_nct_id"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Prepare CSV
    csv_rows = []

    for row in rows:
        patient_mrn, trial_nct_id, eligibility_status, eligibility_percentage, criteria_results_json, computed_at = row

        try:
            criteria_results = json.loads(criteria_results_json) if criteria_results_json else {}
        except json.JSONDecodeError:
            print(f"Warning: Could not parse criteria_results for {patient_mrn} / {trial_nct_id}")
            continue

        # Process inclusion criteria
        for criterion in criteria_results.get("inclusion", []):
            csv_rows.append({
                "Patient MRN": patient_mrn,
                "Trial NCT Code": trial_nct_id,
                "Inclusion / Exclusion criteria": "Inclusion",
                "Criterion Number": criterion.get("criterion_number", ""),
                "Criteria": criterion.get("original_criterion_text", criterion.get("criterion_text", "")),
                "Patient Value": criterion.get("patient_value", ""),
                "LLM Decision (met)": criterion.get("met", ""),
                "Confidence": criterion.get("confidence", ""),
                "LLM Explanation": criterion.get("explanation", ""),
                "Manually Resolved": criterion.get("manually_resolved", False),
                "Resolved By": criterion.get("resolved_by", ""),
                "Review Type": criterion.get("review_type", ""),
                "Suggested Test": criterion.get("suggested_test", ""),
                "Clinician Action": criterion.get("clinician_action", ""),
                "Ground Truth (met)": "",  # Empty for manual verification
                "Accuracy Benchmarking": "",  # Empty - to be filled during verification (100% or -)
                "Document reference": "",  # Empty - to be filled during verification
                "Observations": "",  # Empty - for reviewer notes
                "Overall Eligibility Status": eligibility_status,
                "Overall Eligibility %": eligibility_percentage,
                "Computed At": computed_at
            })

        # Process exclusion criteria
        for criterion in criteria_results.get("exclusion", []):
            csv_rows.append({
                "Patient MRN": patient_mrn,
                "Trial NCT Code": trial_nct_id,
                "Inclusion / Exclusion criteria": "Exclusion",
                "Criterion Number": criterion.get("criterion_number", ""),
                "Criteria": criterion.get("original_criterion_text", criterion.get("criterion_text", "")),
                "Patient Value": criterion.get("patient_value", ""),
                "LLM Decision (met)": criterion.get("met", ""),
                "Confidence": criterion.get("confidence", ""),
                "LLM Explanation": criterion.get("explanation", ""),
                "Manually Resolved": criterion.get("manually_resolved", False),
                "Resolved By": criterion.get("resolved_by", ""),
                "Review Type": criterion.get("review_type", ""),
                "Suggested Test": criterion.get("suggested_test", ""),
                "Clinician Action": criterion.get("clinician_action", ""),
                "Ground Truth (met)": "",  # Empty for manual verification
                "Accuracy Benchmarking": "",  # Empty - to be filled during verification (100% or -)
                "Document reference": "",  # Empty - to be filled during verification
                "Observations": "",  # Empty - for reviewer notes
                "Overall Eligibility Status": eligibility_status,
                "Overall Eligibility %": eligibility_percentage,
                "Computed At": computed_at
            })

    conn.close()

    # Write CSV
    if csv_rows:
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

        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)

        # Get absolute path for logging
        abs_path = output_file.resolve()
        print(f"✅ Exported {len(csv_rows)} criteria to {abs_path}")
        print(f"   Patients: {len(set(row['Patient MRN'] for row in csv_rows))}")
        print(f"   Trials: {len(set(row['Trial NCT Code'] for row in csv_rows))}")
        return str(abs_path)
    else:
        print("⚠️  No data found to export")
        return None


def export_by_category(db_path: str, output_dir: str = None, patient_mrn: str = None):
    """
    Export eligibility data grouped by medical category for targeted validation.

    Args:
        db_path: Path to SQLite database
        output_dir: Directory for output CSVs (default: current directory)
        patient_mrn: Optional filter for specific patient
    """

    if output_dir is None:
        output_dir = Path.cwd()
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    # Define category keywords
    categories = {
        "Demographics_Age_Gender": ["age", "years old", "gender", "sex", "male", "female", "birth"],
        "Diagnosis_Cancer_Type": ["cancer", "carcinoma", "histology", "adenocarcinoma", "squamous", "sclc", "nsclc", "tumor type"],
        "Staging_TNM_AJCC": ["tnm", "stage", "ajcc", "metastatic", "metastasis", "t1", "t2", "t3", "t4", "n0", "n1", "m0", "m1"],
        "Lab_Values": ["hemoglobin", "platelet", "wbc", "anc", "creatinine", "bilirubin", "alt", "ast", "egfr", "lab", "×uln", "x uln"],
        "Performance_Status": ["ecog", "karnofsky", "kps", "performance status", "ambulatory", "functional"],
        "Prior_Treatment": ["prior therapy", "prior treatment", "previous treatment", "chemotherapy", "immunotherapy", "radiation", "surgery", "lines of therapy"],
        "Genomics_Biomarkers": ["egfr", "alk", "ros1", "kras", "braf", "pd-l1", "tmb", "msi", "mutation", "alteration", "biomarker"],
        "Organ_Function": ["renal function", "hepatic function", "liver function", "kidney function", "adequate organ function", "bone marrow"],
        "Imaging_RECIST": ["measurable lesion", "recist", "ct scan", "pet", "mri", "imaging", "mass", "nodule"],
        "Comorbidities": ["cardiovascular", "cardiac", "diabetes", "hypertension", "copd", "autoimmune", "hiv", "hepatitis", "infection"],
        "Consent_Administrative": ["consent", "willingness", "ability to", "sign", "comply", "understand", "travel"]
    }

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # IMPORTANT: Only include patients that exist in patient_data_pool (active patients)
    query = """
        SELECT
            patient_mrn,
            trial_nct_id,
            eligibility_status,
            eligibility_percentage,
            criteria_results,
            computed_at
        FROM eligibility_matrix
        WHERE patient_mrn IN (SELECT mrn FROM patient_data_pool)
    """
    params = []

    if patient_mrn:
        query += " AND patient_mrn = ?"
        params.append(patient_mrn)

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Organize by category
    category_data = {cat: [] for cat in categories.keys()}
    category_data["Uncategorized"] = []

    for row in rows:
        patient_mrn, trial_nct_id, eligibility_status, eligibility_percentage, criteria_results_json, computed_at = row

        try:
            criteria_results = json.loads(criteria_results_json) if criteria_results_json else {}
        except json.JSONDecodeError:
            continue

        # Process all criteria
        for criterion_type in ["inclusion", "exclusion"]:
            for criterion in criteria_results.get(criterion_type, []):
                criterion_text = criterion.get("original_criterion_text", criterion.get("criterion_text", "")).lower()

                # Find matching category
                matched_category = None
                for category, keywords in categories.items():
                    if any(keyword.lower() in criterion_text for keyword in keywords):
                        matched_category = category
                        break

                if matched_category is None:
                    matched_category = "Uncategorized"

                # Add to category
                category_data[matched_category].append({
                    "Patient MRN": patient_mrn,
                    "Trial NCT Code": trial_nct_id,
                    "Inclusion / Exclusion criteria": criterion_type.capitalize(),
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
                    "Category": matched_category
                })

    conn.close()

    # Write category CSVs
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
        "Category"
    ]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    exported_files = []

    for category, data in category_data.items():
        if data:
            output_path = output_dir / f"validation_{category}_{timestamp}.csv"
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)

            print(f"✅ {category}: {len(data)} criteria → {output_path}")
            exported_files.append(str(output_path))

    return exported_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export clinical trials eligibility data for validation")
    parser.add_argument("--db", type=str, default="astera_patients.db", help="Database file path")
    parser.add_argument("--output", type=str, help="Output CSV file path")
    parser.add_argument("--patient", type=str, help="Filter by patient MRN")
    parser.add_argument("--trial", type=str, help="Filter by trial NCT ID")
    parser.add_argument("--exclude-patients", type=str, nargs="+", help="List of patient MRNs to exclude")
    parser.add_argument("--by-category", action="store_true", help="Export separate files by category")
    parser.add_argument("--output-dir", type=str, help="Output directory for category exports")

    args = parser.parse_args()

    # Get the Backend directory
    backend_dir = Path(__file__).parent
    db_path = backend_dir / args.db

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        exit(1)

    if args.by_category:
        print(f"\n📊 Exporting by category from {db_path}...")
        output_dir = args.output_dir or backend_dir / "validation_exports"
        exported_files = export_by_category(str(db_path), str(output_dir), args.patient)
        print(f"\n✅ Exported {len(exported_files)} category files to {output_dir}")
    else:
        print(f"\n📊 Exporting eligibility data from {db_path}...")

        # Generate default filename based on whether patients are excluded
        if not args.output:
            if args.exclude_patients:
                num_excluded = len(args.exclude_patients)
                output_path = str(backend_dir / f"clinical_trials_validation_26_NEW_PATIENTS.csv")
            else:
                output_path = str(backend_dir / f"clinical_trials_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        else:
            output_path = args.output

        result = export_eligibility_to_csv(str(db_path), output_path, args.patient, args.trial, args.exclude_patients)
        if result:
            print(f"\n✅ Export complete: {result}")
            print(f"\nYou can now:")
            print(f"  1. Open the CSV in Excel/Google Sheets")
            print(f"  2. Fill in 'Ground Truth (met)' column with correct values")
            print(f"  3. Fill in 'Document Reference' to cite source")
            print(f"  4. Add 'Observations' for any notes")
            print(f"  5. The 'Accuracy' column will auto-calculate when Ground Truth matches LLM Decision")
