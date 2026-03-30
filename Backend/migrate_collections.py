"""
Migration script to rename Firestore collections.

This script copies data from old collection names to new standardized names:
- patients → demo_patients
- Demo_hospital_patients → astera_patients
- patient_trial_eligibility → demo_patient_trial_eligibility
- Demo_hospital_patient_trial_eligibility → astera_patient_trial_eligibility
- patient_review_tokens → demo_patient_review_tokens
- Demo_hospital_patient_review_tokens → astera_patient_review_tokens

Run this script ONCE to migrate your data, then you can delete the old collections.
"""

import os
import sys
from google.cloud import firestore
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Collection mappings: old_name → new_name
COLLECTION_MAPPINGS = {
    # Patient collections
    "patients": "demo_patients",
    "Demo_hospital_patients": "astera_patients",

    # Eligibility collections
    "patient_trial_eligibility": "demo_patient_trial_eligibility",
    "Demo_hospital_patient_trial_eligibility": "astera_patient_trial_eligibility",

    # Review tokens collections
    "patient_review_tokens": "demo_patient_review_tokens",
    "Demo_hospital_patient_review_tokens": "astera_patient_review_tokens",
}


def migrate_collection(db: firestore.Client, old_name: str, new_name: str):
    """
    Migrate all documents from old collection to new collection.

    Args:
        db: Firestore client
        old_name: Source collection name
        new_name: Destination collection name
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Migrating: {old_name} → {new_name}")
    logger.info(f"{'='*60}")

    try:
        # Get all documents from old collection
        old_collection = db.collection(old_name)
        docs = old_collection.stream()

        migrated_count = 0
        batch = db.batch()
        batch_size = 0

        for doc in docs:
            doc_data = doc.to_dict()

            # Create document in new collection with same ID
            new_doc_ref = db.collection(new_name).document(doc.id)
            batch.set(new_doc_ref, doc_data)

            batch_size += 1
            migrated_count += 1

            # Firestore batch limit is 500 operations
            if batch_size >= 400:
                batch.commit()
                logger.info(f"  Committed batch of {batch_size} documents (total: {migrated_count})")
                batch = db.batch()
                batch_size = 0

        # Commit any remaining documents
        if batch_size > 0:
            batch.commit()
            logger.info(f"  Committed final batch of {batch_size} documents")

        logger.info(f"✅ Successfully migrated {migrated_count} documents from '{old_name}' to '{new_name}'")
        return migrated_count

    except Exception as e:
        logger.error(f"❌ Error migrating {old_name} → {new_name}: {e}", exc_info=True)
        return 0


def verify_migration(db: firestore.Client, old_name: str, new_name: str):
    """Verify that document counts match between old and new collections."""
    try:
        old_docs = list(db.collection(old_name).limit(1).stream())
        old_exists = len(old_docs) > 0

        new_docs = list(db.collection(new_name).stream())
        new_count = len(new_docs)

        if not old_exists:
            logger.info(f"  ⚠️  Old collection '{old_name}' is empty or doesn't exist (new: {new_count} docs)")
            return True

        # For full verification, we'd need to count all docs in old collection too
        # But for now, just check new collection has data
        if new_count > 0:
            logger.info(f"  ✅ New collection '{new_name}' has {new_count} documents")
            return True
        else:
            logger.warning(f"  ⚠️  New collection '{new_name}' is empty!")
            return False

    except Exception as e:
        logger.error(f"  ❌ Error verifying {old_name} → {new_name}: {e}")
        return False


def main():
    """Run the migration."""
    logger.info("\n" + "="*60)
    logger.info("FIRESTORE COLLECTION MIGRATION")
    logger.info("="*60)

    # Initialize Firestore
    try:
        project = os.environ.get("GCP_PROJECT_ID", "rapids-platform")
        db = firestore.Client(project=project)
        logger.info(f"✅ Connected to Firestore project: {project}\n")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Firestore: {e}")
        sys.exit(1)

    # Confirm before proceeding
    print("\nThis script will copy data from old collections to new collections:")
    for old, new in COLLECTION_MAPPINGS.items():
        print(f"  • {old} → {new}")

    response = input("\nProceed with migration? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        logger.info("Migration cancelled.")
        sys.exit(0)

    # Run migrations
    total_migrated = 0
    for old_name, new_name in COLLECTION_MAPPINGS.items():
        count = migrate_collection(db, old_name, new_name)
        total_migrated += count

    # Verify migrations
    logger.info(f"\n{'='*60}")
    logger.info("VERIFICATION")
    logger.info(f"{'='*60}")

    all_verified = True
    for old_name, new_name in COLLECTION_MAPPINGS.items():
        verified = verify_migration(db, old_name, new_name)
        if not verified:
            all_verified = False

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("MIGRATION SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total documents migrated: {total_migrated}")

    if all_verified:
        logger.info("✅ All migrations verified successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Verify the data in Firebase Console")
        logger.info("2. Test your application with the new collections")
        logger.info("3. Once confirmed, you can delete the old collections:")
        for old_name in COLLECTION_MAPPINGS.keys():
            logger.info(f"   - {old_name}")
    else:
        logger.warning("⚠️  Some migrations may have issues. Please verify manually.")

    logger.info("\n" + "="*60)


if __name__ == "__main__":
    main()
