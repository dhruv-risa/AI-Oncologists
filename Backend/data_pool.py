

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

        Returns:
            List of dictionaries containing MRN and summary metadata
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
            conn.close()

            patients = []
            for row in results:
                try:
                    mrn = row[0]
                    data = json.loads(row[1])
                    created_at = row[2]
                    updated_at = row[3]

                    # Safely extract nested fields
                    demographics = data.get("demographics", {})
                    diagnosis = data.get("diagnosis", {})

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
                        "lastVisit": demographics.get("Last Visit", "N/A")
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

