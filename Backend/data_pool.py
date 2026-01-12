

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

