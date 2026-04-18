"""
Database Manager for handling multiple patient databases.
Manages separate databases for demo patients and Astera (real) patients.
"""
from pathlib import Path
from typing import Literal
from data_pool import DataPool


DatabaseType = Literal["demo", "astera"]


class DatabaseManager:
    """
    Manages multiple patient databases (demo and astera).
    Provides a unified interface to access either database.
    """

    def __init__(self, base_dir: str = None):
        """
        Initialize the database manager with two separate databases.

        Args:
            base_dir: Base directory for databases. If None, uses Backend directory.
        """
        if base_dir is None:
            base_dir = Path(__file__).parent
        else:
            base_dir = Path(base_dir)

        # Initialize two separate database instances
        self.demo_db_path = base_dir / "demo_patients.db"
        self.astera_db_path = base_dir / "astera_patients.db"

        self.demo_pool = DataPool(db_path=str(self.demo_db_path))
        self.astera_pool = DataPool(db_path=str(self.astera_db_path))

        print(f"✅ Demo database initialized at: {self.demo_db_path}")
        print(f"✅ Astera database initialized at: {self.astera_db_path}")

    def get_pool(self, db_type: DatabaseType = "astera") -> DataPool:
        """
        Get the appropriate database pool.

        Args:
            db_type: Type of database - "demo" or "astera" (default: "astera")

        Returns:
            DataPool instance for the specified database
        """
        if db_type == "demo":
            return self.demo_pool
        elif db_type == "astera":
            return self.astera_pool
        else:
            raise ValueError(f"Invalid database type: {db_type}. Must be 'demo' or 'astera'")

    def get_database_info(self) -> dict:
        """
        Get information about both databases.

        Returns:
            Dictionary with patient counts for each database
        """
        demo_patients = self.demo_pool.list_all_patients()
        astera_patients = self.astera_pool.list_all_patients()

        return {
            "demo": {
                "path": str(self.demo_db_path),
                "patient_count": len(demo_patients),
                "trials_count": self.demo_pool.get_trials_count()
            },
            "astera": {
                "path": str(self.astera_db_path),
                "patient_count": len(astera_patients),
                "trials_count": self.astera_pool.get_trials_count()
            }
        }


# Singleton instance for the database manager
_db_manager_instance = None


def get_database_manager() -> DatabaseManager:
    """
    Get or create the singleton database manager instance.

    Returns:
        DatabaseManager instance
    """
    global _db_manager_instance
    if _db_manager_instance is None:
        _db_manager_instance = DatabaseManager()
    return _db_manager_instance
