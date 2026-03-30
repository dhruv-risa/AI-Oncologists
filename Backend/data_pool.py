

"""
This module provides a data pool for storing patient data and trials cache.

Patient data is stored in Firestore for permanent, reliable persistence.
Trials cache, eligibility matrix, and other operational data use SQLite.
"""
import json
import logging
import sqlite3
import shutil
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path
import os

logger = logging.getLogger(__name__)


def _get_firestore_client():
    """Get a Firestore client, or None if unavailable."""
    try:
        from google.cloud import firestore
        project = os.environ.get("GCP_PROJECT_ID", "rapids-platform")
        return firestore.Client(project=project)
    except Exception as e:
        logger.warning(f"[DataPool] Firestore unavailable, falling back to SQLite for patients: {e}")
        return None


class DataPool:
    """
    Data pool for storing patient data and trials cache.

    Patient data → Firestore (permanent, survives deploys)
    Eligibility results → Firestore (permanent, survives deploys)
    Patient review tokens → Firestore (permanent, survives deploys)
    Trials cache → SQLite (ephemeral, re-syncs nightly)
    Computation progress → SQLite (ephemeral, operational)
    Sync logs → SQLite (ephemeral, operational)
    """

    # Collection names for different hospitals
    FIRESTORE_DEMO_COLLECTION = "demo_patients"
    FIRESTORE_ASTERA_COLLECTION = "astera_patients"
    FIRESTORE_DEMO_ELIGIBILITY_COLLECTION = "demo_patient_trial_eligibility"
    FIRESTORE_ASTERA_ELIGIBILITY_COLLECTION = "astera_patient_trial_eligibility"
    FIRESTORE_DEMO_REVIEW_TOKENS_COLLECTION = "demo_patient_review_tokens"
    FIRESTORE_ASTERA_REVIEW_TOKENS_COLLECTION = "astera_patient_review_tokens"
    FIRESTORE_DEMO_TRIALS_COLLECTION = "demo_clinical_trials"
    FIRESTORE_ASTERA_TRIALS_COLLECTION = "astera_clinical_trials"

    def __init__(self, db_path: str = None):
        """
        Initialize the data pool.

        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        # Initialize Firestore for patient data
        self._firestore = _get_firestore_client()
        if self._firestore:
            logger.info("[DataPool] Using Firestore for patient data storage")
        else:
            logger.warning("[DataPool] Firestore not available — using SQLite for all data")

        # Initialize SQLite for trials cache / eligibility
        if db_path is None:
            gcs_mount = os.environ.get("DB_MOUNT_PATH", "")
            if gcs_mount and os.path.isdir(gcs_mount):
                gcs_db = Path(gcs_mount) / "data_pool.db"
                local_db = Path("/tmp") / "data_pool.db"
                if gcs_db.exists() and not local_db.exists():
                    shutil.copy2(str(gcs_db), str(local_db))
                    logger.info(f"[DataPool] Copied GCS DB to local: {local_db} ({local_db.stat().st_size} bytes)")
                db_path = local_db
            else:
                backend_dir = Path(__file__).parent
                db_path = backend_dir / "data_pool.db"

        self.db_path = str(db_path)
        self.init_database()

        # One-time migration: copy patients from SQLite → Firestore
        if self._firestore:
            self._migrate_sqlite_to_firestore()

    def _get_collection_name(self, db_type: str = None) -> str:
        """Get the Firestore collection name based on db_type."""
        if db_type == 'astera':
            return self.FIRESTORE_ASTERA_COLLECTION
        else:
            return self.FIRESTORE_DEMO_COLLECTION

    def _get_eligibility_collection_name(self, db_type: str = None) -> str:
        """Get the Firestore eligibility collection name based on db_type."""
        if db_type == 'astera':
            return self.FIRESTORE_ASTERA_ELIGIBILITY_COLLECTION
        else:
            return self.FIRESTORE_DEMO_ELIGIBILITY_COLLECTION

    def _get_review_tokens_collection_name(self, db_type: str = None) -> str:
        """Get the Firestore review tokens collection name based on db_type."""
        if db_type == 'astera':
            return self.FIRESTORE_ASTERA_REVIEW_TOKENS_COLLECTION
        else:
            return self.FIRESTORE_DEMO_REVIEW_TOKENS_COLLECTION

    def _get_trials_collection_name(self, db_type: str = None) -> str:
        """Get the Firestore trials collection name based on db_type."""
        if db_type == 'astera':
            return self.FIRESTORE_ASTERA_TRIALS_COLLECTION
        else:
            return self.FIRESTORE_DEMO_TRIALS_COLLECTION

    def _migrate_sqlite_to_firestore(self):
        """One-time migration: if Firestore has 0 patients but SQLite has data, copy over to Demo collection."""
        try:
            # Check if Firestore already has patients in Demo collection
            demo_collection = self._get_collection_name('demo')
            docs = list(self._firestore.collection(demo_collection).limit(1).stream())
            if docs:
                logger.info("[DataPool] Firestore already has patients, skipping migration")
                return

            # Check SQLite for existing patients
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT mrn, data, created_at, updated_at FROM patient_data_pool WHERE mrn IS NOT NULL AND data IS NOT NULL")
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                logger.info("[DataPool] No patients in SQLite to migrate")
                return

            logger.info(f"[DataPool] Migrating {len(rows)} patients from SQLite to Firestore Demo collection...")
            batch = self._firestore.batch()
            count = 0
            for mrn, data_str, created_at, updated_at in rows:
                try:
                    # Validate the JSON is parseable
                    json.loads(data_str)
                    doc_ref = self._firestore.collection(demo_collection).document(mrn)
                    batch.set(doc_ref, {
                        "mrn": mrn,
                        "data": data_str,
                        "created_at": created_at or updated_at,
                        "updated_at": updated_at,
                    })
                    count += 1
                    # Firestore batches limited to 500 writes
                    if count % 400 == 0:
                        batch.commit()
                        batch = self._firestore.batch()
                        logger.info(f"[DataPool] Migrated {count}/{len(rows)} patients...")
                except Exception as e:
                    logger.error(f"[DataPool] Failed to migrate patient {mrn}: {e}")
                    continue

            if count % 400 != 0:
                batch.commit()
            logger.info(f"[DataPool] Migration complete: {count} patients copied to Firestore")
        except Exception as e:
            logger.error(f"[DataPool] SQLite→Firestore migration failed: {e}", exc_info=True)

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

        # Create computation progress table - tracks per-patient eligibility computation
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS computation_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_mrn TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'computing',
                trials_total INTEGER NOT NULL DEFAULT 0,
                trials_completed INTEGER NOT NULL DEFAULT 0,
                trials_eligible INTEGER NOT NULL DEFAULT 0,
                trials_error INTEGER NOT NULL DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                UNIQUE(patient_mrn)
            )
        """)

        # Create patient review tokens table - stores shareable review links
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patient_review_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL UNIQUE,
                patient_mrn TEXT NOT NULL,
                trial_nct_id TEXT NOT NULL,
                criteria_snapshot TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                responses TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (patient_mrn) REFERENCES patient_data_pool(mrn),
                FOREIGN KEY (trial_nct_id) REFERENCES trials_cache(nct_id)
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

    def store_patient_data(self, mrn: str, data: dict, db_type: str = None) -> bool:
        """
        Store patient data. Uses Firestore if available, SQLite as fallback.

        Args:
            mrn: Patient MRN
            data: Patient data dictionary
            db_type: Hospital type ('demo' or 'astera'). Defaults to 'demo'.
        """
        try:
            if not mrn or not isinstance(mrn, str) or mrn.strip() == "":
                logger.error(f"Error storing patient data: Invalid MRN '{mrn}'")
                return False
            if not data or not isinstance(data, dict):
                logger.error(f"Error storing patient data: Invalid data for MRN '{mrn}'")
                return False

            current_time = datetime.now().isoformat()

            if self._firestore:
                collection_name = self._get_collection_name(db_type)
                doc_ref = self._firestore.collection(collection_name).document(mrn)
                doc_ref.set({
                    "mrn": mrn,
                    "data": json.dumps(data),
                    "updated_at": current_time,
                })
                logger.info(f"[DataPool] Stored patient {mrn} in Firestore collection {collection_name}")
                return True

            # SQLite fallback
            conn = sqlite3.connect(self.db_path)
            self._ensure_table_exists(conn)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO patient_data_pool (mrn, data, updated_at) VALUES (?, ?, ?)",
                (mrn, json.dumps(data), current_time),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error storing patient data: {e}", exc_info=True)
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

    def get_patient_data(self, mrn: str, db_type: str = None) -> Optional[Dict]:
        """
        Retrieve patient data. Uses Firestore if available, SQLite as fallback.

        Args:
            mrn: Patient MRN
            db_type: Hospital type ('demo' or 'astera'). Defaults to 'demo'.
        """
        try:
            if self._firestore:
                collection_name = self._get_collection_name(db_type)
                doc = self._firestore.collection(collection_name).document(mrn).get()
                if doc.exists:
                    doc_data = doc.to_dict()
                    data = json.loads(doc_data["data"])
                    data['pool_updated_at'] = doc_data.get("updated_at")
                    data = self._normalize_timeline_dates(data)
                    return data
                return None

            # SQLite fallback
            conn = sqlite3.connect(self.db_path)
            self._ensure_table_exists(conn)
            cursor = conn.cursor()
            cursor.execute("SELECT data, updated_at FROM patient_data_pool WHERE mrn = ?", (mrn,))
            result = cursor.fetchone()
            conn.close()
            if result:
                data = json.loads(result[0])
                data['pool_updated_at'] = result[1]
                data = self._normalize_timeline_dates(data)
                return data
            return None
        except Exception as e:
            logger.error(f"Error retrieving patient data: {e}")
            return None

    def _build_patient_summary(self, mrn, data, created_at, updated_at, eligibility_counts):
        """Build a patient summary dict from raw data."""
        demographics = data.get("demographics") or {}
        diagnosis = data.get("diagnosis") or {}
        trial_counts = eligibility_counts.get(mrn, {
            "total_trials_analyzed": 0, "likely_eligible": 0,
            "potentially_eligible": 0, "not_eligible": 0
        })
        stage = "N/A"
        current_staging = diagnosis.get("current_staging", {})
        initial_staging = diagnosis.get("initial_staging", {})
        if current_staging and current_staging.get("ajcc_stage"):
            stage = current_staging.get("ajcc_stage")
        elif initial_staging and initial_staging.get("ajcc_stage"):
            stage = initial_staging.get("ajcc_stage")
        elif diagnosis.get("ajcc_stage"):
            stage = diagnosis.get("ajcc_stage")
        return {
            "mrn": mrn,
            "created_at": created_at,
            "updated_at": updated_at,
            "name": demographics.get("Patient Name", "Unknown"),
            "age": demographics.get("Age", "N/A"),
            "gender": demographics.get("Gender", "N/A"),
            "cancerType": diagnosis.get("cancer_type", "N/A"),
            "stage": stage,
            "status": diagnosis.get("disease_status", "N/A"),
            "lastVisit": demographics.get("Last Visit", "N/A"),
            "trialsAnalyzed": trial_counts["total_trials_analyzed"],
            "likelyEligible": trial_counts["likely_eligible"],
            "potentiallyEligible": trial_counts["potentially_eligible"],
            "matchedTrials": trial_counts["likely_eligible"] + trial_counts["potentially_eligible"],
        }

    def _get_eligibility_counts(self, db_type: str = None):
        """
        Get eligibility counts. Uses Firestore if available, SQLite as fallback.

        Args:
            db_type: Hospital type ('demo' or 'astera'). Defaults to 'demo'.
        """
        eligibility_counts = {}
        try:
            if self._firestore:
                # Query Firestore for all eligibility results
                eligibility_collection = self._get_eligibility_collection_name(db_type)
                docs = self._firestore.collection(eligibility_collection).stream()

                # Aggregate counts by patient_mrn
                for doc in docs:
                    data = doc.to_dict()
                    patient_mrn = data.get("patient_mrn")
                    status = data.get("eligibility_status")

                    if patient_mrn:
                        if patient_mrn not in eligibility_counts:
                            eligibility_counts[patient_mrn] = {
                                "total_trials_analyzed": 0,
                                "likely_eligible": 0,
                                "potentially_eligible": 0,
                                "not_eligible": 0
                            }

                        eligibility_counts[patient_mrn]["total_trials_analyzed"] += 1

                        if status == "LIKELY_ELIGIBLE":
                            eligibility_counts[patient_mrn]["likely_eligible"] += 1
                        elif status == "POTENTIALLY_ELIGIBLE":
                            eligibility_counts[patient_mrn]["potentially_eligible"] += 1
                        elif status == "NOT_ELIGIBLE":
                            eligibility_counts[patient_mrn]["not_eligible"] += 1

                logger.info(f"[DataPool] Retrieved eligibility counts for {len(eligibility_counts)} patients from Firestore")
                return eligibility_counts

            # SQLite fallback
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT patient_mrn, COUNT(*) as total,
                    SUM(CASE WHEN eligibility_status = 'LIKELY_ELIGIBLE' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN eligibility_status = 'POTENTIALLY_ELIGIBLE' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN eligibility_status = 'NOT_ELIGIBLE' THEN 1 ELSE 0 END)
                FROM eligibility_matrix GROUP BY patient_mrn
            """)
            for row in cursor.fetchall():
                eligibility_counts[row[0]] = {
                    "total_trials_analyzed": row[1], "likely_eligible": row[2],
                    "potentially_eligible": row[3], "not_eligible": row[4]
                }
            conn.close()
        except Exception as e:
            logger.error(f"Error getting eligibility counts: {e}", exc_info=True)
        return eligibility_counts

    def list_all_patients(self, db_type: str = None) -> List[Dict]:
        """
        List all patients with summary details. Uses Firestore if available.

        Args:
            db_type: Hospital type ('demo' or 'astera'). Defaults to 'demo'.
        """
        try:
            eligibility_counts = self._get_eligibility_counts(db_type)

            if self._firestore:
                patients = []
                collection_name = self._get_collection_name(db_type)
                docs = self._firestore.collection(collection_name).stream()
                for doc in docs:
                    try:
                        doc_data = doc.to_dict()
                        mrn = doc_data.get("mrn", doc.id)
                        data = json.loads(doc_data["data"])
                        updated_at = doc_data.get("updated_at")
                        created_at = doc_data.get("created_at", updated_at)
                        patients.append(self._build_patient_summary(
                            mrn, data, created_at, updated_at, eligibility_counts
                        ))
                    except Exception as e:
                        logger.error(f"Error processing Firestore patient {doc.id}: {e}")
                        continue
                patients.sort(key=lambda p: p.get("updated_at", ""), reverse=True)
                return patients

            # SQLite fallback
            conn = sqlite3.connect(self.db_path)
            self._ensure_table_exists(conn)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT mrn, data, created_at, updated_at FROM patient_data_pool
                WHERE mrn IS NOT NULL AND mrn != '' AND data IS NOT NULL AND data != ''
                ORDER BY updated_at DESC
            """)
            results = cursor.fetchall()
            conn.close()

            patients = []
            for row in results:
                try:
                    data = json.loads(row[1])
                    patients.append(self._build_patient_summary(
                        row[0], data, row[2], row[3], eligibility_counts
                    ))
                except Exception as e:
                    logger.error(f"Error processing patient {row[0]}: {e}")
                    continue
            return patients
        except Exception as e:
            logger.error(f"Error listing patients: {e}")
            return []

    def delete_patient_data(self, mrn: str, db_type: str = None) -> bool:
        """
        Delete patient data.

        Args:
            mrn: Patient's Medical Record Number
            db_type: Hospital type ('demo' or 'astera'). Defaults to 'demo'.
        """
        try:
            if self._firestore:
                collection_name = self._get_collection_name(db_type)
                self._firestore.collection(collection_name).document(mrn).delete()
                return True
            conn = sqlite3.connect(self.db_path)
            self._ensure_table_exists(conn)
            conn.cursor().execute("DELETE FROM patient_data_pool WHERE mrn = ?", (mrn,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error deleting patient data: {e}")
            return False

    def clear_pool(self) -> bool:
        """Clear all patient data."""
        try:
            if self._firestore:
                docs = self._firestore.collection(self.FIRESTORE_COLLECTION).stream()
                for doc in docs:
                    doc.reference.delete()
                return True
            conn = sqlite3.connect(self.db_path)
            self._ensure_table_exists(conn)
            conn.cursor().execute("DELETE FROM patient_data_pool")
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error clearing pool: {e}")
            return False

    def patient_exists(self, mrn: str, db_type: str = None) -> bool:
        """
        Check if patient data exists.

        Args:
            mrn: Patient's Medical Record Number
            db_type: Hospital type ('demo' or 'astera'). Defaults to 'demo'.
        """
        try:
            if self._firestore:
                collection_name = self._get_collection_name(db_type)
                return self._firestore.collection(collection_name).document(mrn).get().exists
            conn = sqlite3.connect(self.db_path)
            self._ensure_table_exists(conn)
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM patient_data_pool WHERE mrn = ?", (mrn,))
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except Exception as e:
            logger.error(f"Error checking patient existence: {e}")
            return False

    # ==================== TRIALS CACHE METHODS ====================

    def store_trial(self, trial_data: Dict, db_type: str = None) -> bool:
        """
        Store a clinical trial in Firestore.

        Args:
            trial_data: Dictionary containing trial information with nct_id as key
            db_type: Hospital type ('demo' or 'astera'). Defaults to 'demo'.

        Returns:
            True if successful, False otherwise
        """
        if not self._firestore:
            logger.warning("[store_trial] Firestore not available")
            return False

        try:
            nct_id = trial_data.get("nct_id")
            if not nct_id:
                logger.error("[store_trial] Missing nct_id")
                return False

            collection_name = self._get_trials_collection_name(db_type)

            # Prepare trial document
            trial_doc = {
                "nct_id": nct_id,
                "title": trial_data.get("title", ""),
                "phase": trial_data.get("phase", ""),
                "status": trial_data.get("status", ""),
                "study_type": trial_data.get("study_type", ""),
                "cancer_types": trial_data.get("cancer_types", []),
                "conditions": trial_data.get("conditions", []),
                "eligibility_criteria": trial_data.get("eligibility_criteria", trial_data.get("eligibility_criteria_text", "")),
                "eligibility_criteria_text": trial_data.get("eligibility_criteria_text", trial_data.get("eligibility_criteria", "")),
                "minimum_age": trial_data.get("minimum_age", ""),
                "maximum_age": trial_data.get("maximum_age", ""),
                "sex": trial_data.get("sex", "ALL"),
                "healthy_volunteers": trial_data.get("healthy_volunteers", False),
                "locations": trial_data.get("locations", []),
                "contact": trial_data.get("contact", {}),
                "sponsor": trial_data.get("sponsor", ""),
                "start_date": trial_data.get("start_date", ""),
                "completion_date": trial_data.get("completion_date", ""),
                "enrollment": trial_data.get("enrollment", 0),
                "brief_summary": trial_data.get("brief_summary", ""),
                "detailed_description": trial_data.get("detailed_description", ""),
                "last_updated_on_api": trial_data.get("last_updated_on_api", ""),
                "fetched_at": datetime.now().isoformat(),
                "is_active": trial_data.get("is_active", True)
            }

            # Store in Firestore using nct_id as document ID
            self._firestore.collection(collection_name).document(nct_id).set(trial_doc)
            return True

        except Exception as e:
            logger.error(f"[store_trial] Error storing trial {trial_data.get('nct_id', 'unknown')}: {e}")
            return False

    def bulk_store_trials(self, trials: List[Dict], db_type: str = None) -> Dict:
        """
        Store multiple trials in bulk to Firestore.

        Args:
            trials: List of trial dictionaries
            db_type: Hospital type ('demo' or 'astera'). Defaults to 'demo'.

        Returns:
            Dict with 'stored_count' and 'new_nct_ids' (trials not previously in cache)
        """
        stored_count = 0
        new_nct_ids = []

        if not self._firestore:
            logger.warning("[bulk_store_trials] Firestore not available")
            return {"stored_count": 0, "new_nct_ids": []}

        try:
            collection_name = self._get_trials_collection_name(db_type)
            collection = self._firestore.collection(collection_name)

            # Get existing NCT IDs to identify truly new trials
            incoming_ids = [t.get("nct_id") for t in trials if t.get("nct_id")]
            existing_ids = set()

            if incoming_ids:
                # Firestore has a limit of 10 items per 'in' query, so we batch it
                batch_size = 10
                for i in range(0, len(incoming_ids), batch_size):
                    batch = incoming_ids[i:i + batch_size]
                    docs = collection.where("nct_id", "in", batch).stream()
                    for doc in docs:
                        existing_ids.add(doc.id)  # Document ID is the nct_id

            # Store trials in Firestore
            for trial in trials:
                try:
                    nct_id = trial.get("nct_id")
                    if not nct_id:
                        continue

                    # Prepare trial document
                    trial_doc = {
                        "nct_id": nct_id,
                        "title": trial.get("title", ""),
                        "phase": trial.get("phase", ""),
                        "status": trial.get("status", ""),
                        "study_type": trial.get("study_type", ""),
                        "cancer_types": trial.get("cancer_types", []),
                        "conditions": trial.get("conditions", []),
                        "eligibility_criteria": trial.get("eligibility_criteria", trial.get("eligibility_criteria_text", "")),
                        "eligibility_criteria_text": trial.get("eligibility_criteria_text", trial.get("eligibility_criteria", "")),
                        "minimum_age": trial.get("minimum_age", ""),
                        "maximum_age": trial.get("maximum_age", ""),
                        "sex": trial.get("sex", "ALL"),
                        "healthy_volunteers": trial.get("healthy_volunteers", False),
                        "locations": trial.get("locations", []),
                        "contact": trial.get("contact", {}),
                        "sponsor": trial.get("sponsor", ""),
                        "start_date": trial.get("start_date", ""),
                        "completion_date": trial.get("completion_date", ""),
                        "enrollment": trial.get("enrollment", 0),
                        "brief_summary": trial.get("brief_summary", ""),
                        "detailed_description": trial.get("detailed_description", ""),
                        "last_updated_on_api": trial.get("last_updated_on_api", ""),
                        "fetched_at": datetime.now().isoformat(),
                        "is_active": trial.get("is_active", True)
                    }

                    # Use nct_id as document ID for easy retrieval
                    collection.document(nct_id).set(trial_doc)
                    stored_count += 1

                    if nct_id not in existing_ids:
                        new_nct_ids.append(nct_id)

                except Exception as e:
                    logger.error(f"[bulk_store_trials] Error storing trial {trial.get('nct_id', 'unknown')}: {e}")
                    continue

            logger.info(f"[bulk_store_trials] Stored {stored_count} trials to Firestore ({len(new_nct_ids)} new)")

        except Exception as e:
            logger.error(f"[bulk_store_trials] Error in bulk store trials: {e}")

        return {"stored_count": stored_count, "new_nct_ids": new_nct_ids}

    def get_trial(self, nct_id: str, db_type: str = None) -> Optional[Dict]:
        """
        Retrieve a trial from Firestore.

        Args:
            nct_id: ClinicalTrials.gov NCT ID
            db_type: Hospital type ('demo' or 'astera'). Defaults to 'demo'.

        Returns:
            Trial dictionary if found, None otherwise
        """
        if not self._firestore:
            logger.warning("[get_trial] Firestore not available")
            return None

        try:
            collection_name = self._get_trials_collection_name(db_type)
            doc_ref = self._firestore.collection(collection_name).document(nct_id)
            doc = doc_ref.get()

            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"[get_trial] Error retrieving trial {nct_id}: {e}")
            return None

    def list_all_trials(self, status: str = None, limit: int = 100, offset: int = 0, db_type: str = None) -> List[Dict]:
        """
        List all trials from Firestore with optional filtering.

        Args:
            status: Filter by trial status (e.g., "RECRUITING")
            limit: Maximum number of results
            offset: Offset for pagination
            db_type: Hospital type ('demo' or 'astera'). Defaults to 'demo'.

        Returns:
            List of trial dictionaries with eligible patient counts
        """
        if not self._firestore:
            logger.warning("[list_all_trials] Firestore not available")
            return []

        try:
            collection_name = self._get_trials_collection_name(db_type)
            eligibility_collection_name = self._get_eligibility_collection_name(db_type)

            # Build query
            query = self._firestore.collection(collection_name)

            # Filter by is_active
            query = query.where("is_active", "==", True)

            # Filter by status if provided
            if status:
                query = query.where("status", "==", status)

            # Order by fetched_at descending (newest first)
            query = query.order_by("fetched_at", direction="DESCENDING")

            # Get all matching documents (we'll handle pagination in memory)
            # Note: Firestore doesn't have SQL-like OFFSET, so we fetch and slice
            docs = list(query.stream())

            # Apply pagination
            paginated_docs = docs[offset:offset + limit]

            # Convert to dictionaries and add eligible patient counts
            trials = []
            for doc in paginated_docs:
                trial = doc.to_dict()
                nct_id = trial.get("nct_id")

                # Get eligible patient counts from eligibility collection
                if nct_id:
                    try:
                        # Count total patients for this trial
                        total_count = self._firestore.collection(eligibility_collection_name)\
                            .where("trial_nct_id", "==", nct_id)\
                            .count()\
                            .get()

                        # Count eligible patients (LIKELY_ELIGIBLE or POTENTIALLY_ELIGIBLE)
                        eligible_query = self._firestore.collection(eligibility_collection_name)\
                            .where("trial_nct_id", "==", nct_id)\
                            .where("eligibility_status", "in", ["LIKELY_ELIGIBLE", "POTENTIALLY_ELIGIBLE"])
                        eligible_count = eligible_query.count().get()

                        trial["eligible_patient_count"] = eligible_count[0][0].value if eligible_count else 0
                        trial["total_patient_count"] = total_count[0][0].value if total_count else 0
                    except Exception as e:
                        logger.warning(f"[list_all_trials] Error getting patient counts for {nct_id}: {e}")
                        trial["eligible_patient_count"] = 0
                        trial["total_patient_count"] = 0

                trials.append(trial)

            # Sort by eligible_patient_count descending, then by fetched_at
            trials.sort(key=lambda t: (t.get("eligible_patient_count", 0), t.get("fetched_at", "")), reverse=True)

            return trials

        except Exception as e:
            logger.error(f"[list_all_trials] Error listing trials: {e}")
            return []

    def get_trials_count(self, status: str = None, db_type: str = None) -> int:
        """
        Get total count of trials in Firestore.

        Args:
            status: Filter by trial status (e.g., "RECRUITING")
            db_type: Hospital type ('demo' or 'astera'). Defaults to 'demo'.

        Returns:
            Count of trials matching the filter
        """
        if not self._firestore:
            logger.warning("[get_trials_count] Firestore not available")
            return 0

        try:
            collection_name = self._get_trials_collection_name(db_type)
            query = self._firestore.collection(collection_name).where("is_active", "==", True)

            if status:
                query = query.where("status", "==", status)

            # Use Firestore count aggregation
            count_query = query.count()
            count_result = count_query.get()

            # count_result is a list of aggregation results
            return count_result[0][0].value if count_result else 0

        except Exception as e:
            logger.error(f"[get_trials_count] Error getting trials count: {e}")
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

    def store_eligibility(self, trial_nct_id: str, patient_mrn: str, eligibility_data: Dict, trial_data: Dict = None, db_type: str = None) -> bool:
        """
        Store eligibility result for a patient-trial pair. Uses Firestore if available, SQLite as fallback.

        Args:
            trial_nct_id: ClinicalTrials.gov NCT ID
            patient_mrn: Patient's Medical Record Number
            eligibility_data: Dictionary containing eligibility analysis
            trial_data: Optional trial details (title, phase, status, sponsor) to store with eligibility
            db_type: Hospital type ('demo' or 'astera'). Defaults to 'demo'.

        Returns:
            True if successful, False otherwise
        """
        try:
            current_time = datetime.now().isoformat()

            if self._firestore:
                # Store in Firestore - use composite key as document ID
                doc_id = f"{patient_mrn}_{trial_nct_id}"
                eligibility_collection = self._get_eligibility_collection_name(db_type)
                doc_ref = self._firestore.collection(eligibility_collection).document(doc_id)

                eligibility_doc = {
                    "trial_nct_id": trial_nct_id,
                    "patient_mrn": patient_mrn,
                    "eligibility_status": eligibility_data.get("status", "Unknown"),
                    "eligibility_percentage": eligibility_data.get("percentage", 0),
                    "criteria_results": eligibility_data.get("criteria_results", {}),
                    "key_matching_criteria": eligibility_data.get("key_matching_criteria", []),
                    "key_exclusion_reasons": eligibility_data.get("key_exclusion_reasons", []),
                    "computed_at": current_time
                }

                # Include trial details if provided
                if trial_data:
                    eligibility_doc["trial_title"] = trial_data.get("title", "")
                    eligibility_doc["trial_phase"] = trial_data.get("phase", "")
                    eligibility_doc["trial_status"] = trial_data.get("status", "")
                    eligibility_doc["trial_sponsor"] = trial_data.get("sponsor", "")

                doc_ref.set(eligibility_doc)
                logger.info(f"[DataPool] Stored eligibility for {patient_mrn} × {trial_nct_id} in Firestore")
                return True

            # SQLite fallback
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
                current_time
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error storing eligibility: {e}", exc_info=True)
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

    # ── Computation Progress Tracking ─────────────────────────────────────────

    def start_computation_progress(self, patient_mrn: str, trials_total: int) -> bool:
        """Record that eligibility computation has started for a patient."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO computation_progress
                (patient_mrn, status, trials_total, trials_completed,
                 trials_eligible, trials_error, started_at, updated_at, completed_at, error_message)
                VALUES (?, 'computing', ?, 0, 0, 0, ?, ?, NULL, NULL)
            """, (patient_mrn, trials_total,
                  datetime.now().isoformat(), datetime.now().isoformat()))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error starting computation progress: {e}")
            return False

    def increment_computation_progress(self, patient_mrn: str,
                                        is_eligible: bool = False,
                                        is_error: bool = False) -> bool:
        """Increment progress counter after a single trial completes."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            eligible_inc = 1 if is_eligible else 0
            error_inc = 1 if is_error else 0
            cursor.execute("""
                UPDATE computation_progress
                SET trials_completed = trials_completed + 1,
                    trials_eligible = trials_eligible + ?,
                    trials_error = trials_error + ?,
                    updated_at = ?
                WHERE patient_mrn = ? AND status = 'computing'
            """, (eligible_inc, error_inc, datetime.now().isoformat(), patient_mrn))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error incrementing computation progress: {e}")
            return False

    def complete_computation_progress(self, patient_mrn: str,
                                       error_message: str = None) -> bool:
        """Mark computation as completed or errored."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            new_status = "error" if error_message else "completed"
            cursor.execute("""
                UPDATE computation_progress
                SET status = ?,
                    completed_at = ?,
                    updated_at = ?,
                    error_message = ?
                WHERE patient_mrn = ?
            """, (new_status, datetime.now().isoformat(),
                  datetime.now().isoformat(), error_message, patient_mrn))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error completing computation progress: {e}")
            return False

    def get_computation_progress(self, patient_mrn: str):
        """Get current computation progress for a patient."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT patient_mrn, status, trials_total, trials_completed,
                       trials_eligible, trials_error, started_at, updated_at,
                       completed_at, error_message
                FROM computation_progress
                WHERE patient_mrn = ?
            """, (patient_mrn,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return {
                    "patient_mrn": row[0],
                    "status": row[1],
                    "trials_total": row[2],
                    "trials_completed": row[3],
                    "trials_eligible": row[4],
                    "trials_error": row[5],
                    "started_at": row[6],
                    "updated_at": row[7],
                    "completed_at": row[8],
                    "error_message": row[9]
                }
            return None
        except Exception as e:
            print(f"Error getting computation progress: {e}")
            return None

    # ── Patient Review Tokens ──────────────────────────────────────────────

    def create_review_token(self, token: str, patient_mrn: str, trial_nct_id: str,
                            criteria_snapshot: str, db_type: str = None) -> bool:
        """
        Create a new patient review token with criteria snapshot. Uses Firestore if available.

        Args:
            token: Unique token for the review
            patient_mrn: Patient's Medical Record Number
            trial_nct_id: Clinical trial NCT ID
            criteria_snapshot: Snapshot of eligibility criteria
            db_type: Hospital type ('demo' or 'astera'). Defaults to 'demo'.
        """
        try:
            current_time = datetime.now().isoformat()

            if self._firestore:
                # Store in Firestore
                review_tokens_collection = self._get_review_tokens_collection_name(db_type)
                doc_ref = self._firestore.collection(review_tokens_collection).document(token)
                doc_ref.set({
                    "token": token,
                    "patient_mrn": patient_mrn,
                    "trial_nct_id": trial_nct_id,
                    "criteria_snapshot": criteria_snapshot,
                    "status": "pending",
                    "responses": None,
                    "created_at": current_time,
                    "completed_at": None
                })
                logger.info(f"[DataPool] Created review token {token} in Firestore")
                return True

            # SQLite fallback
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO patient_review_tokens
                (token, patient_mrn, trial_nct_id, criteria_snapshot, status)
                VALUES (?, ?, ?, ?, 'pending')
            """, (token, patient_mrn, trial_nct_id, criteria_snapshot))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error creating review token: {e}", exc_info=True)
            return False

    def get_review_token(self, token: str, db_type: str = None):
        """
        Get review token data. Uses Firestore if available.

        Args:
            token: Unique token for the review
            db_type: Hospital type ('demo' or 'astera'). Defaults to 'demo'.
        """
        try:
            if self._firestore:
                # Query Firestore
                review_tokens_collection = self._get_review_tokens_collection_name(db_type)
                doc = self._firestore.collection(review_tokens_collection).document(token).get()
                if doc.exists:
                    data = doc.to_dict()
                    return {
                        "token": data.get("token"),
                        "patient_mrn": data.get("patient_mrn"),
                        "trial_nct_id": data.get("trial_nct_id"),
                        "criteria_snapshot": data.get("criteria_snapshot"),
                        "status": data.get("status"),
                        "responses": data.get("responses"),
                        "created_at": data.get("created_at"),
                        "completed_at": data.get("completed_at")
                    }
                return None

            # SQLite fallback
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT token, patient_mrn, trial_nct_id, criteria_snapshot,
                       status, responses, created_at, completed_at
                FROM patient_review_tokens
                WHERE token = ?
            """, (token,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return {
                    "token": row[0],
                    "patient_mrn": row[1],
                    "trial_nct_id": row[2],
                    "criteria_snapshot": row[3],
                    "status": row[4],
                    "responses": row[5],
                    "created_at": row[6],
                    "completed_at": row[7]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting review token: {e}", exc_info=True)
            return None

    def complete_review_token(self, token: str, responses: str, db_type: str = None) -> bool:
        """Mark a review token as completed with patient responses. Uses Firestore if available."""
        try:
            current_time = datetime.now().isoformat()

            if self._firestore:
                # Update in Firestore
                review_tokens_collection = self._get_review_tokens_collection_name(db_type)
                doc_ref = self._firestore.collection(review_tokens_collection).document(token)
                doc = doc_ref.get()

                if doc.exists and doc.to_dict().get("status") == "pending":
                    doc_ref.update({
                        "status": "completed",
                        "responses": responses,
                        "completed_at": current_time
                    })
                    logger.info(f"[DataPool] Completed review token {token} in Firestore")
                    return True
                return False

            # SQLite fallback
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE patient_review_tokens
                SET status = 'completed',
                    responses = ?,
                    completed_at = ?
                WHERE token = ? AND status = 'pending'
            """, (responses, current_time, token))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error completing review token: {e}", exc_info=True)
            return False

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
                                # Extract stage from nested diagnosis structure
                        # Priority: current_staging > initial_staging > flat ajcc_stage
                        stage = "N/A"
                        current_staging = diagnosis.get("current_staging", {})
                        initial_staging = diagnosis.get("initial_staging", {})

                        if current_staging and current_staging.get("ajcc_stage"):
                            stage = current_staging.get("ajcc_stage")
                        elif initial_staging and initial_staging.get("ajcc_stage"):
                            stage = initial_staging.get("ajcc_stage")
                        elif diagnosis.get("ajcc_stage"):
                            # Backwards compatibility for flat structure
                            stage = diagnosis.get("ajcc_stage")

                        result["patient_summary"] = {
                            "mrn": result["patient_mrn"],
                            "name": demographics.get("Patient Name", "Unknown"),
                            "age": demographics.get("Age", "N/A"),
                            "gender": demographics.get("Gender", "N/A"),
                            "cancer_type": diagnosis.get("cancer_type", "N/A"),
                            "stage": stage
                        }
                        del result["patient_data"]
                    except json.JSONDecodeError:
                        pass
                results.append(result)

            return results
        except Exception as e:
            print(f"Error getting eligible patients for trial: {e}")
            return []

    def get_eligible_trials_for_patient(self, mrn: str, status_filter: str = None, db_type: str = None) -> List[Dict]:
        """
        Get all trials a patient is eligible for. Uses Firestore if available, SQLite as fallback.

        Args:
            mrn: Patient's Medical Record Number
            status_filter: Filter by eligibility status
            db_type: Hospital type ('demo' or 'astera'). Defaults to 'demo'.

        Returns:
            List of trial eligibility results with trial details
        """
        try:
            if self._firestore:
                # Query Firestore
                eligibility_collection = self._get_eligibility_collection_name(db_type)
                query = self._firestore.collection(eligibility_collection).where("patient_mrn", "==", mrn)

                if status_filter:
                    query = query.where("eligibility_status", "==", status_filter)

                docs = query.stream()

                results = []
                for doc in docs:
                    data = doc.to_dict()
                    # Convert Firestore document to expected format
                    result = {
                        "trial_nct_id": data.get("trial_nct_id"),
                        "patient_mrn": data.get("patient_mrn"),
                        "eligibility_status": data.get("eligibility_status"),
                        "eligibility_percentage": data.get("eligibility_percentage"),
                        "criteria_results": data.get("criteria_results", {}),
                        "key_matching_criteria": data.get("key_matching_criteria", []),
                        "key_exclusion_reasons": data.get("key_exclusion_reasons", []),
                        "computed_at": data.get("computed_at"),
                        # Trial details would need to be fetched separately or stored with eligibility
                        "title": data.get("trial_title", ""),
                        "phase": data.get("trial_phase", ""),
                        "trial_status": data.get("trial_status", ""),
                        "sponsor": data.get("trial_sponsor", "")
                    }
                    results.append(result)

                # Sort by eligibility percentage descending
                results.sort(key=lambda x: x.get("eligibility_percentage", 0), reverse=True)
                logger.info(f"[DataPool] Retrieved {len(results)} eligibility results for {mrn} from Firestore")
                return results

            # SQLite fallback
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
            logger.error(f"Error getting eligible trials for patient: {e}", exc_info=True)
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

