

"""
This module provides a database-backed data pool for storing patient data.
The data pool allows multiple patients' data to be stored and retrieved efficiently.
"""
import json
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path
import os


class DataPool:
    """
    Database-backed data pool for storing patient data.
    Uses SQLite for storage with easy migration path to PostgreSQL.
    """

    def __init__(self, db_path: str = None):
        """
        Initialize the data pool with a database connection.

        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        if db_path is None:
            # Default to Backend directory
            backend_dir = Path(__file__).parent
            db_path = backend_dir / "data_pool.db"

        self.db_path = str(db_path)
        self.init_database()

    def init_database(self):
        """Initialize database schema if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create patients data pool table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patient_data_pool (
                mrn TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create trials cache table - stores pre-fetched trials from ClinicalTrials.gov
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trials_cache (
                nct_id TEXT PRIMARY KEY,
                title TEXT,
                phase TEXT,
                status TEXT,
                study_type TEXT,
                cancer_types TEXT,
                conditions TEXT,
                eligibility_criteria TEXT,
                eligibility_criteria_text TEXT,
                minimum_age TEXT,
                maximum_age TEXT,
                sex TEXT DEFAULT 'ALL',
                healthy_volunteers BOOLEAN DEFAULT 0,
                locations TEXT,
                contact TEXT,
                sponsor TEXT,
                start_date TEXT,
                completion_date TEXT,
                enrollment INTEGER,
                brief_summary TEXT,
                detailed_description TEXT,
                last_updated_on_api TEXT,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """)

        # Add new columns to existing trials_cache table (for database migration)
        migration_columns = [
            ("study_type", "TEXT"),
            ("eligibility_criteria_text", "TEXT"),
            ("minimum_age", "TEXT"),
            ("maximum_age", "TEXT"),
            ("sex", "TEXT DEFAULT 'ALL'"),
            ("healthy_volunteers", "BOOLEAN DEFAULT 0")
        ]
        for col_name, col_type in migration_columns:
            try:
                cursor.execute(f"ALTER TABLE trials_cache ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Create eligibility matrix table - stores pre-computed patient×trial eligibility
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS eligibility_matrix (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trial_nct_id TEXT NOT NULL,
                patient_mrn TEXT NOT NULL,
                eligibility_status TEXT,
                eligibility_percentage REAL,
                criteria_results TEXT,
                key_matching_criteria TEXT,
                key_exclusion_reasons TEXT,
                computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(trial_nct_id, patient_mrn),
                FOREIGN KEY (trial_nct_id) REFERENCES trials_cache(nct_id),
                FOREIGN KEY (patient_mrn) REFERENCES patient_data_pool(mrn)
            )
        """)

        # Create sync log table - tracks sync operations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_type TEXT NOT NULL,
                sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                new_trials_count INTEGER DEFAULT 0,
                updated_trials_count INTEGER DEFAULT 0,
                eligibility_computed_count INTEGER DEFAULT 0,
                status TEXT,
                error_message TEXT
            )
        """)

        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trials_status ON trials_cache(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trials_cancer_types ON trials_cache(cancer_types)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_eligibility_trial ON eligibility_matrix(trial_nct_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_eligibility_patient ON eligibility_matrix(patient_mrn)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_eligibility_status ON eligibility_matrix(eligibility_status)
        """)

        conn.commit()
        conn.close()

    def _ensure_table_exists(self, conn):
        """
        Ensure the table exists for the current connection.
        This is called before each database operation to handle cases
        where the table was deleted after the app started.

        Args:
            conn: SQLite connection object
        """
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patient_data_pool (
                mrn TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def store_patient_data(self, mrn: str, data: dict) -> bool:
        """
        Store patient data in the pool.
        If patient already exists, updates the existing record.

        Args:
            mrn: Patient's Medical Record Number
            data: Patient data dictionary to store

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate inputs
            if not mrn or not isinstance(mrn, str) or mrn.strip() == "":
                print(f"Error storing patient data: Invalid MRN '{mrn}'")
                return False

            if not data or not isinstance(data, dict):
                print(f"Error storing patient data: Invalid data for MRN '{mrn}'")
                return False

            conn = sqlite3.connect(self.db_path)

            # Ensure table exists before operation
            self._ensure_table_exists(conn)

            cursor = conn.cursor()

            # Convert data to JSON string
            data_json = json.dumps(data)
            current_time = datetime.now().isoformat()

            # Insert or replace (upsert)
            cursor.execute("""
                INSERT OR REPLACE INTO patient_data_pool (mrn, data, updated_at)
                VALUES (?, ?, ?)
            """, (mrn, data_json, current_time))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error storing patient data: {e}")
            return False

    def _normalize_timeline_dates(self, data: Dict) -> Dict:
        """
        Normalize vague date terms in timeline data (migration for cached data).

        Converts:
        - 'Late 2025' → 'December 2025'
        - 'Early 2023' → 'January 2023'
        - 'Late 2025 - Early 2026' → 'December 2025'
        - etc.

        Args:
            data: Patient data dictionary

        Returns:
            Patient data with normalized dates
        """
        import re

        def normalize_date_label(date_str):
            """Normalize a single date label."""
            if not date_str or not isinstance(date_str, str):
                return date_str

            date_lower = date_str.lower().strip()

            # Handle "Current Status" - don't modify
            if 'current' in date_lower:
                return date_str

            # Extract year from the string
            year_match = re.search(r'\b(20\d{2})\b', date_str)
            if not year_match:
                return date_str  # Can't parse, return as-is

            year = year_match.group(1)

            # Handle vague date terms
            if 'late' in date_lower and '-' in date_str and ('early' in date_lower or 'mid' in date_lower):
                # "Late 2025 - Early 2026" → use the first year, late = December
                return f'December {year}'
            elif 'late' in date_lower:
                # "Late 2025" → "December 2025"
                return f'December {year}'
            elif 'early' in date_lower:
                # "Early 2023" → "January 2023"
                return f'January {year}'
            elif 'mid' in date_lower or 'middle' in date_lower:
                # "Mid-2024" → "June 2024"
                return f'June {year}'
            elif 'end' in date_lower:
                # "End 2024" → "December 2024"
                return f'December {year}'
            elif 'beginning' in date_lower or 'start' in date_lower:
                # "Beginning 2023" → "January 2023"
                return f'January {year}'

            # If it's already in a good format, return as-is
            return date_str

        # Normalize diagnosis_evolution_timeline dates
        if 'diagnosis_evolution_timeline' in data and isinstance(data['diagnosis_evolution_timeline'], dict):
            timeline = data['diagnosis_evolution_timeline'].get('timeline', [])
            if isinstance(timeline, list):
                for event in timeline:
                    if isinstance(event, dict) and 'date_label' in event:
                        event['date_label'] = normalize_date_label(event['date_label'])

        return data

    def get_patient_data(self, mrn: str) -> Optional[Dict]:
        """
        Retrieve patient data from the pool.

        Args:
            mrn: Patient's Medical Record Number

        Returns:
            Patient data dictionary if found, None otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)

            # Ensure table exists before operation
            self._ensure_table_exists(conn)

            cursor = conn.cursor()

            cursor.execute("""
                SELECT data, updated_at FROM patient_data_pool
                WHERE mrn = ?
            """, (mrn,))

            result = cursor.fetchone()
            conn.close()

            if result:
                data = json.loads(result[0])
                data['pool_updated_at'] = result[1]  # Add metadata about when it was stored

                # Normalize timeline dates in cached data (migration for old data with vague dates)
                data = self._normalize_timeline_dates(data)

                return data
            return None
        except Exception as e:
            print(f"Error retrieving patient data: {e}")
            return None

    def list_all_patients(self) -> List[Dict]:
        """
        List all patients in the data pool with summary details.
        Extracts key fields from the JSON blob for the list view.
        Includes trial match counts from eligibility matrix.

        Returns:
            List of dictionaries containing MRN, summary metadata, and trial counts
        """
        try:
            conn = sqlite3.connect(self.db_path)

            # Ensure table exists before operation
            self._ensure_table_exists(conn)

            cursor = conn.cursor()

            # Fetch basic info and parse JSON in Python for better error handling
            cursor.execute("""
                SELECT mrn, data, created_at, updated_at
                FROM patient_data_pool
                WHERE mrn IS NOT NULL AND mrn != '' AND data IS NOT NULL AND data != ''
                ORDER BY updated_at DESC
            """)

            results = cursor.fetchall()

            # Get trial match counts for all patients
            cursor.execute("""
                SELECT
                    patient_mrn,
                    COUNT(*) as total_trials,
                    SUM(CASE WHEN eligibility_status = 'LIKELY_ELIGIBLE' THEN 1 ELSE 0 END) as likely_eligible,
                    SUM(CASE WHEN eligibility_status = 'POTENTIALLY_ELIGIBLE' THEN 1 ELSE 0 END) as potentially_eligible,
                    SUM(CASE WHEN eligibility_status = 'NOT_ELIGIBLE' THEN 1 ELSE 0 END) as not_eligible
                FROM eligibility_matrix
                GROUP BY patient_mrn
            """)
            eligibility_rows = cursor.fetchall()
            conn.close()

            # Build eligibility lookup
            eligibility_counts = {}
            for row in eligibility_rows:
                eligibility_counts[row[0]] = {
                    "total_trials_analyzed": row[1],
                    "likely_eligible": row[2],
                    "potentially_eligible": row[3],
                    "not_eligible": row[4]
                }

            patients = []
            for row in results:
                try:
                    mrn = row[0]
                    data = json.loads(row[1])
                    created_at = row[2]
                    updated_at = row[3]

                    # Safely extract nested fields (handle None values)
                    demographics = data.get("demographics") or {}
                    diagnosis = data.get("diagnosis") or {}

                    # Get trial counts for this patient
                    trial_counts = eligibility_counts.get(mrn, {
                        "total_trials_analyzed": 0,
                        "likely_eligible": 0,
                        "potentially_eligible": 0,
                        "not_eligible": 0
                    })

                    patients.append({
                        "mrn": mrn,
                        "created_at": created_at,
                        "updated_at": updated_at,
                        "name": demographics.get("Patient Name", "Unknown"),
                        "age": demographics.get("Age", "N/A"),
                        "gender": demographics.get("Gender", "N/A"),
                        "cancerType": diagnosis.get("cancer_type", "N/A"),
                        "stage": diagnosis.get("ajcc_stage", "N/A"),
                        "status": diagnosis.get("disease_status", "N/A"),
                        "lastVisit": demographics.get("Last Visit", "N/A"),
                        # Trial match counts
                        "trialsAnalyzed": trial_counts["total_trials_analyzed"],
                        "likelyEligible": trial_counts["likely_eligible"],
                        "potentiallyEligible": trial_counts["potentially_eligible"],
                        "matchedTrials": trial_counts["likely_eligible"] + trial_counts["potentially_eligible"]
                    })
                except json.JSONDecodeError as je:
                    print(f"Error parsing JSON for patient {row[0]}: {je}")
                    continue
                except Exception as e:
                    print(f"Error processing patient {row[0]}: {e}")
                    continue

            return patients
        except Exception as e:
            print(f"Error listing patients: {e}")
            return []

    def delete_patient_data(self, mrn: str) -> bool:
        """
        Delete patient data from the pool.

        Args:
            mrn: Patient's Medical Record Number

        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)

            # Ensure table exists before operation
            self._ensure_table_exists(conn)

            cursor = conn.cursor()

            cursor.execute("DELETE FROM patient_data_pool WHERE mrn = ?", (mrn,))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error deleting patient data: {e}")
            return False

    def clear_pool(self) -> bool:
        """
        Clear all patient data from the pool.

        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)

            # Ensure table exists before operation
            self._ensure_table_exists(conn)

            cursor = conn.cursor()

            cursor.execute("DELETE FROM patient_data_pool")

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error clearing pool: {e}")
            return False

    def patient_exists(self, mrn: str) -> bool:
        """
        Check if patient data exists in the pool.

        Args:
            mrn: Patient's Medical Record Number

        Returns:
            True if patient exists, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)

            # Ensure table exists before operation
            self._ensure_table_exists(conn)

            cursor = conn.cursor()

            cursor.execute("SELECT 1 FROM patient_data_pool WHERE mrn = ?", (mrn,))
            result = cursor.fetchone()

            conn.close()
            return result is not None
        except Exception as e:
            print(f"Error checking patient existence: {e}")
            return False

    # ==================== TRIALS CACHE METHODS ====================

    def store_trial(self, trial_data: Dict) -> bool:
        """
        Store a clinical trial in the cache.

        Args:
            trial_data: Dictionary containing trial information with nct_id as key

        Returns:
            True if successful, False otherwise
        """
        try:
            nct_id = trial_data.get("nct_id")
            if not nct_id:
                print("Error storing trial: Missing nct_id")
                return False

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO trials_cache
                (nct_id, title, phase, status, study_type, cancer_types, conditions,
                 eligibility_criteria, eligibility_criteria_text, minimum_age, maximum_age,
                 sex, healthy_volunteers, locations, contact, sponsor, start_date,
                 completion_date, enrollment, brief_summary, detailed_description,
                 last_updated_on_api, fetched_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                nct_id,
                trial_data.get("title", ""),
                trial_data.get("phase", ""),
                trial_data.get("status", ""),
                trial_data.get("study_type", ""),
                json.dumps(trial_data.get("cancer_types", [])),
                json.dumps(trial_data.get("conditions", [])),
                trial_data.get("eligibility_criteria", trial_data.get("eligibility_criteria_text", "")),
                trial_data.get("eligibility_criteria_text", trial_data.get("eligibility_criteria", "")),
                trial_data.get("minimum_age", ""),
                trial_data.get("maximum_age", ""),
                trial_data.get("sex", "ALL"),
                trial_data.get("healthy_volunteers", False),
                json.dumps(trial_data.get("locations", [])),
                json.dumps(trial_data.get("contact", {})),
                trial_data.get("sponsor", ""),
                trial_data.get("start_date", ""),
                trial_data.get("completion_date", ""),
                trial_data.get("enrollment", 0),
                trial_data.get("brief_summary", ""),
                trial_data.get("detailed_description", ""),
                trial_data.get("last_updated_on_api", ""),
                datetime.now().isoformat(),
                trial_data.get("is_active", True)
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error storing trial: {e}")
            return False

    def bulk_store_trials(self, trials: List[Dict]) -> int:
        """
        Store multiple trials in bulk.

        Args:
            trials: List of trial dictionaries

        Returns:
            Number of successfully stored trials
        """
        stored_count = 0
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            for trial in trials:
                try:
                    nct_id = trial.get("nct_id")
                    if not nct_id:
                        continue

                    cursor.execute("""
                        INSERT OR REPLACE INTO trials_cache
                        (nct_id, title, phase, status, study_type, cancer_types, conditions,
                         eligibility_criteria, eligibility_criteria_text, minimum_age, maximum_age,
                         sex, healthy_volunteers, locations, contact, sponsor, start_date,
                         completion_date, enrollment, brief_summary, detailed_description,
                         last_updated_on_api, fetched_at, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        nct_id,
                        trial.get("title", ""),
                        trial.get("phase", ""),
                        trial.get("status", ""),
                        trial.get("study_type", ""),
                        json.dumps(trial.get("cancer_types", [])),
                        json.dumps(trial.get("conditions", [])),
                        trial.get("eligibility_criteria", trial.get("eligibility_criteria_text", "")),
                        trial.get("eligibility_criteria_text", trial.get("eligibility_criteria", "")),
                        trial.get("minimum_age", ""),
                        trial.get("maximum_age", ""),
                        trial.get("sex", "ALL"),
                        trial.get("healthy_volunteers", False),
                        json.dumps(trial.get("locations", [])),
                        json.dumps(trial.get("contact", {})),
                        trial.get("sponsor", ""),
                        trial.get("start_date", ""),
                        trial.get("completion_date", ""),
                        trial.get("enrollment", 0),
                        trial.get("brief_summary", ""),
                        trial.get("detailed_description", ""),
                        trial.get("last_updated_on_api", ""),
                        datetime.now().isoformat(),
                        trial.get("is_active", True)
                    ))
                    stored_count += 1
                except Exception as e:
                    print(f"Error storing trial {trial.get('nct_id', 'unknown')}: {e}")
                    continue

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error in bulk store trials: {e}")

        return stored_count

    def get_trial(self, nct_id: str) -> Optional[Dict]:
        """
        Retrieve a trial from the cache.

        Args:
            nct_id: ClinicalTrials.gov NCT ID

        Returns:
            Trial dictionary if found, None otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM trials_cache WHERE nct_id = ?", (nct_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                return self._row_to_trial_dict(row, cursor.description)
            return None
        except Exception as e:
            print(f"Error retrieving trial: {e}")
            return None

    def list_all_trials(self, status: str = None, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        List all trials in the cache with optional filtering.

        Args:
            status: Filter by trial status (e.g., "RECRUITING")
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of trial dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Join with eligibility_matrix to get eligible patient counts and sort by them
            if status:
                cursor.execute("""
                    SELECT t.*,
                           COALESCE(e.eligible_count, 0) as eligible_patient_count,
                           COALESCE(e.total_count, 0) as total_patient_count
                    FROM trials_cache t
                    LEFT JOIN (
                        SELECT trial_nct_id,
                               SUM(CASE WHEN eligibility_status IN ('LIKELY_ELIGIBLE', 'POTENTIALLY_ELIGIBLE') THEN 1 ELSE 0 END) as eligible_count,
                               COUNT(*) as total_count
                        FROM eligibility_matrix
                        GROUP BY trial_nct_id
                    ) e ON t.nct_id = e.trial_nct_id
                    WHERE t.status = ? AND t.is_active = 1
                    ORDER BY eligible_count DESC, t.fetched_at DESC
                    LIMIT ? OFFSET ?
                """, (status, limit, offset))
            else:
                cursor.execute("""
                    SELECT t.*,
                           COALESCE(e.eligible_count, 0) as eligible_patient_count,
                           COALESCE(e.total_count, 0) as total_patient_count
                    FROM trials_cache t
                    LEFT JOIN (
                        SELECT trial_nct_id,
                               SUM(CASE WHEN eligibility_status IN ('LIKELY_ELIGIBLE', 'POTENTIALLY_ELIGIBLE') THEN 1 ELSE 0 END) as eligible_count,
                               COUNT(*) as total_count
                        FROM eligibility_matrix
                        GROUP BY trial_nct_id
                    ) e ON t.nct_id = e.trial_nct_id
                    WHERE t.is_active = 1
                    ORDER BY eligible_count DESC, t.fetched_at DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset))

            rows = cursor.fetchall()
            description = cursor.description
            conn.close()

            return [self._row_to_trial_dict(row, description) for row in rows]
        except Exception as e:
            print(f"Error listing trials: {e}")
            return []

    def get_trials_count(self, status: str = None) -> int:
        """Get total count of trials in cache."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if status:
                cursor.execute(
                    "SELECT COUNT(*) FROM trials_cache WHERE status = ? AND is_active = 1",
                    (status,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM trials_cache WHERE is_active = 1")

            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            print(f"Error getting trials count: {e}")
            return 0

    def _row_to_trial_dict(self, row, description) -> Dict:
        """Convert a database row to a trial dictionary."""
        columns = [col[0] for col in description]
        trial = dict(zip(columns, row))

        # Parse JSON fields
        for field in ["cancer_types", "conditions", "locations", "contact"]:
            if trial.get(field):
                try:
                    trial[field] = json.loads(trial[field])
                except json.JSONDecodeError:
                    trial[field] = []

        return trial

    # ==================== ELIGIBILITY MATRIX METHODS ====================

    def store_eligibility(self, trial_nct_id: str, patient_mrn: str, eligibility_data: Dict) -> bool:
        """
        Store eligibility result for a patient-trial pair.

        Args:
            trial_nct_id: ClinicalTrials.gov NCT ID
            patient_mrn: Patient's Medical Record Number
            eligibility_data: Dictionary containing eligibility analysis

        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO eligibility_matrix
                (trial_nct_id, patient_mrn, eligibility_status, eligibility_percentage,
                 criteria_results, key_matching_criteria, key_exclusion_reasons, computed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trial_nct_id,
                patient_mrn,
                eligibility_data.get("status", "Unknown"),
                eligibility_data.get("percentage", 0),
                json.dumps(eligibility_data.get("criteria_results", {})),
                json.dumps(eligibility_data.get("key_matching_criteria", [])),
                json.dumps(eligibility_data.get("key_exclusion_reasons", [])),
                datetime.now().isoformat()
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error storing eligibility: {e}")
            return False

    def bulk_store_eligibility(self, eligibility_results: List[Dict]) -> int:
        """
        Store multiple eligibility results in bulk.

        Args:
            eligibility_results: List of dicts with trial_nct_id, patient_mrn, and eligibility_data

        Returns:
            Number of successfully stored results
        """
        stored_count = 0
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            for result in eligibility_results:
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO eligibility_matrix
                        (trial_nct_id, patient_mrn, eligibility_status, eligibility_percentage,
                         criteria_results, key_matching_criteria, key_exclusion_reasons, computed_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        result["trial_nct_id"],
                        result["patient_mrn"],
                        result.get("status", "Unknown"),
                        result.get("percentage", 0),
                        json.dumps(result.get("criteria_results", {})),
                        json.dumps(result.get("key_matching_criteria", [])),
                        json.dumps(result.get("key_exclusion_reasons", [])),
                        datetime.now().isoformat()
                    ))
                    stored_count += 1
                except Exception as e:
                    print(f"Error storing eligibility result: {e}")
                    continue

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error in bulk store eligibility: {e}")

        return stored_count

    def get_eligible_patients_for_trial(self, nct_id: str, status_filter: str = None,
                                        limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        Get all patients eligible for a specific trial.

        Args:
            nct_id: ClinicalTrials.gov NCT ID
            status_filter: Filter by eligibility status ("Likely Eligible", "Potentially Eligible", etc.)
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of patient eligibility results with patient details
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if status_filter:
                cursor.execute("""
                    SELECT e.*, p.data as patient_data
                    FROM eligibility_matrix e
                    JOIN patient_data_pool p ON e.patient_mrn = p.mrn
                    WHERE e.trial_nct_id = ? AND e.eligibility_status = ?
                    ORDER BY e.eligibility_percentage DESC
                    LIMIT ? OFFSET ?
                """, (nct_id, status_filter, limit, offset))
            else:
                cursor.execute("""
                    SELECT e.*, p.data as patient_data
                    FROM eligibility_matrix e
                    JOIN patient_data_pool p ON e.patient_mrn = p.mrn
                    WHERE e.trial_nct_id = ?
                    ORDER BY e.eligibility_percentage DESC
                    LIMIT ? OFFSET ?
                """, (nct_id, limit, offset))

            rows = cursor.fetchall()
            description = cursor.description
            conn.close()

            results = []
            for row in rows:
                result = self._row_to_eligibility_dict(row, description)
                # Parse patient data and add summary
                if result.get("patient_data"):
                    try:
                        patient = json.loads(result["patient_data"])
                        demographics = patient.get("demographics") or {}
                        diagnosis = patient.get("diagnosis") or {}
                        result["patient_summary"] = {
                            "mrn": result["patient_mrn"],
                            "name": demographics.get("Patient Name", "Unknown"),
                            "age": demographics.get("Age", "N/A"),
                            "gender": demographics.get("Gender", "N/A"),
                            "cancer_type": diagnosis.get("cancer_type", "N/A"),
                            "stage": diagnosis.get("ajcc_stage", "N/A")
                        }
                        del result["patient_data"]
                    except json.JSONDecodeError:
                        pass
                results.append(result)

            return results
        except Exception as e:
            print(f"Error getting eligible patients for trial: {e}")
            return []

    def get_eligible_trials_for_patient(self, mrn: str, status_filter: str = None) -> List[Dict]:
        """
        Get all trials a patient is eligible for (from cache).

        Args:
            mrn: Patient's Medical Record Number
            status_filter: Filter by eligibility status

        Returns:
            List of trial eligibility results with trial details
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if status_filter:
                cursor.execute("""
                    SELECT e.*, t.title, t.phase, t.status as trial_status, t.sponsor
                    FROM eligibility_matrix e
                    JOIN trials_cache t ON e.trial_nct_id = t.nct_id
                    WHERE e.patient_mrn = ? AND e.eligibility_status = ?
                    ORDER BY e.eligibility_percentage DESC
                """, (mrn, status_filter))
            else:
                cursor.execute("""
                    SELECT e.*, t.title, t.phase, t.status as trial_status, t.sponsor
                    FROM eligibility_matrix e
                    JOIN trials_cache t ON e.trial_nct_id = t.nct_id
                    WHERE e.patient_mrn = ?
                    ORDER BY e.eligibility_percentage DESC
                """, (mrn,))

            rows = cursor.fetchall()
            description = cursor.description
            conn.close()

            return [self._row_to_eligibility_dict(row, description) for row in rows]
        except Exception as e:
            print(f"Error getting eligible trials for patient: {e}")
            return []

    def get_eligibility_stats_for_trial(self, nct_id: str) -> Dict:
        """
        Get eligibility statistics for a trial.

        Returns:
            Dictionary with counts by eligibility status
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT eligibility_status, COUNT(*) as count
                FROM eligibility_matrix
                WHERE trial_nct_id = ?
                GROUP BY eligibility_status
            """, (nct_id,))

            rows = cursor.fetchall()
            conn.close()

            stats = {"total": 0}
            for row in rows:
                stats[row[0]] = row[1]
                stats["total"] += row[1]

            return stats
        except Exception as e:
            print(f"Error getting eligibility stats: {e}")
            return {}

    def _row_to_eligibility_dict(self, row, description) -> Dict:
        """Convert a database row to an eligibility dictionary."""
        columns = [col[0] for col in description]
        result = dict(zip(columns, row))

        # Parse JSON fields
        for field in ["criteria_results", "key_matching_criteria", "key_exclusion_reasons"]:
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except json.JSONDecodeError:
                    result[field] = []

        return result

    # ==================== SYNC LOG METHODS ====================

    def log_sync(self, sync_type: str, new_trials: int = 0, updated_trials: int = 0,
                 eligibility_computed: int = 0, status: str = "completed", error: str = None) -> bool:
        """
        Log a sync operation.

        Args:
            sync_type: Type of sync ("trials_fetch", "eligibility_compute", "full_sync")
            new_trials: Number of new trials added
            updated_trials: Number of trials updated
            eligibility_computed: Number of eligibility computations
            status: Status of sync operation
            error: Error message if any

        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO sync_log
                (sync_type, new_trials_count, updated_trials_count, eligibility_computed_count, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (sync_type, new_trials, updated_trials, eligibility_computed, status, error))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error logging sync: {e}")
            return False

    def get_last_sync(self, sync_type: str = None) -> Optional[Dict]:
        """
        Get the last sync operation.

        Args:
            sync_type: Filter by sync type

        Returns:
            Last sync log entry or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if sync_type:
                cursor.execute("""
                    SELECT * FROM sync_log
                    WHERE sync_type = ?
                    ORDER BY sync_date DESC LIMIT 1
                """, (sync_type,))
            else:
                cursor.execute("SELECT * FROM sync_log ORDER BY sync_date DESC LIMIT 1")

            row = cursor.fetchone()
            description = cursor.description
            conn.close()

            if row:
                columns = [col[0] for col in description]
                return dict(zip(columns, row))
            return None
        except Exception as e:
            print(f"Error getting last sync: {e}")
            return None


# Singleton instance for the data pool
_data_pool_instance = None

def get_data_pool() -> DataPool:
    """
    Get or create the singleton data pool instance.

    Returns:
        DataPool instance
    """
    global _data_pool_instance
    if _data_pool_instance is None:
        _data_pool_instance = DataPool()
    return _data_pool_instance

