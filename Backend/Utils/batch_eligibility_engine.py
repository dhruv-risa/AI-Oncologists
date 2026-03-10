"""
Batch Eligibility Engine

This module handles pre-computation of the eligibility matrix:
1. Fetches and caches trials from ClinicalTrials.gov
2. Computes eligibility for all patient×trial combinations
3. Stores results for instant queries

Can be run as a scheduled job or triggered manually.
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_pool import get_data_pool
from Utils.Tabs.clinical_trials_tab import (
    fetch_trials_from_api,
    process_single_trial,
    build_patient_context,
    build_search_queries_from_patient
)


class BatchEligibilityEngine:
    """
    Engine for batch computation of eligibility matrix.
    """

    def __init__(self, max_workers: int = 3):
        """
        Initialize the batch engine.

        Args:
            max_workers: Number of parallel workers for LLM calls
        """
        self.data_pool = get_data_pool()
        self.max_workers = max_workers

    def sync_trials(self, search_queries: List[str] = None, max_per_query: int = 100,
                    status: str = "RECRUITING") -> Dict:
        """
        Fetch and cache trials from ClinicalTrials.gov.

        Args:
            search_queries: List of search queries (e.g., cancer types)
            max_per_query: Maximum trials to fetch per query
            status: Trial status filter

        Returns:
            Summary of sync operation
        """
        if search_queries is None:
            # Default queries covering major cancer types
            search_queries = [
                "cancer",
                "solid tumor",
                "lung cancer",
                "breast cancer",
                "colorectal cancer",
                "prostate cancer",
                "pancreatic cancer",
                "melanoma",
                "leukemia",
                "lymphoma",
                "ovarian cancer",
                "bladder cancer",
                "kidney cancer",
                "liver cancer",
                "brain tumor",
                "mesothelioma",
                "sarcoma",
                "myeloma",
                "immunotherapy",
                "targeted therapy"
            ]

        print(f"\n{'='*60}")
        print("BATCH TRIALS SYNC")
        print(f"{'='*60}")
        print(f"Queries: {len(search_queries)}")
        print(f"Max per query: {max_per_query}")
        print(f"Status filter: {status}")

        all_trials = {}
        new_count = 0
        updated_count = 0

        for i, query in enumerate(search_queries, 1):
            print(f"\n[{i}/{len(search_queries)}] Fetching: '{query}'...")

            try:
                trials = fetch_trials_from_api(
                    condition=query,
                    max_results=max_per_query,
                    status=status,
                    max_pages=1
                )

                for trial in trials:
                    nct_id = trial.get("nct_id")
                    if nct_id and nct_id not in all_trials:
                        all_trials[nct_id] = self._normalize_trial_data(trial)

                print(f"   Retrieved {len(trials)} trials, total unique: {len(all_trials)}")

            except Exception as e:
                print(f"   Error fetching '{query}': {e}")
                continue

        # Store trials in database
        print(f"\n{'='*60}")
        print(f"Storing {len(all_trials)} trials in cache...")

        trials_list = list(all_trials.values())
        store_result = self.data_pool.bulk_store_trials(trials_list)
        stored = store_result["stored_count"]
        new_nct_ids = store_result["new_nct_ids"]

        # Log the sync
        self.data_pool.log_sync(
            sync_type="trials_fetch",
            new_trials=len(new_nct_ids),
            status="completed"
        )

        summary = {
            "queries_processed": len(search_queries),
            "total_trials_fetched": len(all_trials),
            "trials_stored": stored,
            "new_trials": len(new_nct_ids),
            "new_nct_ids": new_nct_ids,
            "timestamp": datetime.now().isoformat()
        }

        print(f"\nSync complete: {stored} trials stored ({len(new_nct_ids)} new)")
        return summary

    def _normalize_trial_data(self, trial: Dict) -> Dict:
        """Normalize trial data for storage - preserves all fields needed for eligibility matching."""
        return {
            "nct_id": trial.get("nct_id", ""),
            "title": trial.get("title", ""),
            "phase": trial.get("phase", ""),
            "status": trial.get("status", ""),
            "study_type": trial.get("study_type", ""),
            "cancer_types": trial.get("conditions", []),
            "conditions": trial.get("conditions", []),
            # Store both field names for compatibility
            "eligibility_criteria": trial.get("eligibility_criteria_text", trial.get("eligibility_criteria", "")),
            "eligibility_criteria_text": trial.get("eligibility_criteria_text", trial.get("eligibility_criteria", "")),
            # Age and sex fields for structured eligibility
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
            "last_updated_on_api": trial.get("last_update_posted", ""),
            "is_active": True
        }

    def compute_eligibility_matrix(self, patient_mrns: List[str] = None,
                                   trial_nct_ids: List[str] = None,
                                   limit_trials: int = None) -> Dict:
        """
        Compute eligibility for patient×trial combinations.

        Args:
            patient_mrns: List of patient MRNs (None = all patients)
            trial_nct_ids: List of trial NCT IDs (None = all cached trials)
            limit_trials: Limit number of trials to process

        Returns:
            Summary of computation
        """
        print(f"\n{'='*60}")
        print("BATCH ELIGIBILITY COMPUTATION")
        print(f"{'='*60}")

        # Get patients
        if patient_mrns:
            patients = []
            for mrn in patient_mrns:
                data = self.data_pool.get_patient_data(mrn)
                if data:
                    patients.append({"mrn": mrn, "data": data})
        else:
            all_patients = self.data_pool.list_all_patients()
            patients = []
            for p in all_patients:
                data = self.data_pool.get_patient_data(p["mrn"])
                if data:
                    patients.append({"mrn": p["mrn"], "data": data})

        print(f"Patients to process: {len(patients)}")

        # Get trials
        if trial_nct_ids:
            trials = [self.data_pool.get_trial(nct_id) for nct_id in trial_nct_ids]
            trials = [t for t in trials if t]
        else:
            trials = self.data_pool.list_all_trials(
                status="RECRUITING",
                limit=limit_trials or 1000
            )

        print(f"Trials to process: {len(trials)}")
        print(f"Total combinations: {len(patients) * len(trials)}")

        if not patients or not trials:
            print("No patients or trials to process")
            return {"error": "No data to process"}

        # Compute eligibility
        results = []
        total_combinations = len(patients) * len(trials)
        processed = 0
        errors = 0

        start_time = time.time()

        for patient in patients:
            patient_data = patient["data"]
            patient_mrn = patient["mrn"]

            print(f"\nProcessing patient {patient_mrn}...")

            # Start progress tracking
            self.data_pool.start_computation_progress(patient_mrn, len(trials))

            try:
                # Process trials in parallel — results stored incrementally per-trial
                batch_results = self._process_patient_trials_batch(
                    patient_mrn, patient_data, trials
                )

                results.extend(batch_results)
                processed += len(trials)
                errors += len(trials) - len(batch_results)

                # Mark computation complete
                self.data_pool.complete_computation_progress(patient_mrn)
            except Exception as e:
                print(f"   Error processing patient {patient_mrn}: {e}")
                self.data_pool.complete_computation_progress(patient_mrn, error_message=str(e))
                processed += len(trials)
                errors += len(trials)

            print(f"   Completed: {len(batch_results) if 'batch_results' in dir() else 0}/{len(trials)} trials")
            print(f"   Progress: {processed}/{total_combinations} ({100*processed/total_combinations:.1f}%)")

        elapsed = time.time() - start_time

        # Log the computation
        self.data_pool.log_sync(
            sync_type="eligibility_compute",
            eligibility_computed=len(results),
            status="completed"
        )

        summary = {
            "patients_processed": len(patients),
            "trials_processed": len(trials),
            "eligibility_computed": len(results),
            "errors": errors,
            "elapsed_seconds": round(elapsed, 2),
            "timestamp": datetime.now().isoformat()
        }

        print(f"\n{'='*60}")
        print(f"Computation complete!")
        print(f"Results: {len(results)} eligibility records")
        print(f"Time: {elapsed:.1f} seconds")
        print(f"{'='*60}")

        return summary

    def _process_patient_trials_batch(self, patient_mrn: str, patient_data: Dict,
                                      trials: List[Dict]) -> List[Dict]:
        """
        Process eligibility for a patient against multiple trials in parallel.

        Args:
            patient_mrn: Patient MRN
            patient_data: Patient data dictionary
            trials: List of trial dictionaries

        Returns:
            List of eligibility results
        """
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for trial in trials:
                future = executor.submit(
                    self._compute_single_eligibility,
                    patient_data, trial
                )
                futures[future] = trial["nct_id"]

            for future in as_completed(futures):
                nct_id = futures[future]
                try:
                    result = future.result()
                    if result:
                        # process_single_trial returns: {eligibility: {status, percentage, ...}, criteria_results: {...}}
                        eligibility_info = result.get("eligibility", {})
                        criteria_results = result.get("criteria_results", {})

                        # Extract key criteria for quick reference
                        inclusion_results = criteria_results.get("inclusion", [])
                        exclusion_results = criteria_results.get("exclusion", [])

                        # Get matching inclusion criteria (met=True)
                        key_matching = [
                            c.get("criterion_text", "")[:100]
                            for c in inclusion_results
                            if c.get("met") is True
                        ][:5]  # Limit to 5

                        # Get exclusion reasons (violated exclusions where met=True means BAD)
                        key_exclusions = [
                            c.get("criterion_text", "")[:100]
                            for c in exclusion_results
                            if c.get("met") is True
                        ][:5]  # Limit to 5

                        result_dict = {
                            "trial_nct_id": nct_id,
                            "patient_mrn": patient_mrn,
                            "status": eligibility_info.get("status", "Unknown"),
                            "percentage": eligibility_info.get("percentage", 0),
                            "criteria_results": criteria_results,
                            "key_matching_criteria": key_matching,
                            "key_exclusion_reasons": key_exclusions
                        }
                        results.append(result_dict)

                        # Store immediately to DB (progressive loading)
                        self.data_pool.store_eligibility(nct_id, patient_mrn, result_dict)

                        # Update progress counter
                        is_eligible = eligibility_info.get("status") in (
                            "LIKELY_ELIGIBLE", "POTENTIALLY_ELIGIBLE"
                        )
                        self.data_pool.increment_computation_progress(
                            patient_mrn, is_eligible=is_eligible
                        )
                    else:
                        # Trial returned None (skipped by pre-filter)
                        self.data_pool.increment_computation_progress(patient_mrn)
                except Exception as e:
                    print(f"      Error processing {nct_id}: {e}")
                    self.data_pool.increment_computation_progress(
                        patient_mrn, is_error=True
                    )
                    continue

        return results

    def _compute_single_eligibility(self, patient_data: Dict, trial: Dict) -> Optional[Dict]:
        """
        Compute eligibility for a single patient-trial pair.

        Args:
            patient_data: Patient data dictionary
            trial: Trial dictionary (from cache, may need field transformation)

        Returns:
            Eligibility result or None
        """
        try:
            # Build patient context for LLM
            patient_context = build_patient_context(patient_data)

            # Transform cached trial data to format expected by process_single_trial()
            # The cached data may use different field names
            trial_for_processing = {
                "nct_id": trial.get("nct_id", ""),
                "title": trial.get("title", ""),
                "phase": trial.get("phase", ""),
                "status": trial.get("status", ""),
                "study_type": trial.get("study_type", "Interventional"),  # Default if missing
                "brief_summary": trial.get("brief_summary", ""),
                # Use eligibility_criteria_text (expected by process_single_trial)
                "eligibility_criteria_text": trial.get("eligibility_criteria_text",
                                                       trial.get("eligibility_criteria", "")),
                "minimum_age": trial.get("minimum_age", ""),
                "maximum_age": trial.get("maximum_age", ""),
                "sex": trial.get("sex", "ALL"),
                "healthy_volunteers": trial.get("healthy_volunteers", False),
                "locations": trial.get("locations", []),
                "contact": trial.get("contact", {}),
                # Include conditions for disease matching
                "conditions": trial.get("conditions", trial.get("cancer_types", [])),
                "cancer_types": trial.get("cancer_types", trial.get("conditions", []))
            }

            # Process the trial - this returns the full eligibility result
            result = process_single_trial(trial_for_processing, patient_context, patient_data)
            return result
        except Exception as e:
            print(f"      LLM error: {e}")
            return None

    def compute_for_new_patients(self, patient_mrns: List[str]) -> Dict:
        """
        Compute eligibility for newly added patients against all cached trials.

        Args:
            patient_mrns: List of new patient MRNs

        Returns:
            Summary of computation
        """
        return self.compute_eligibility_matrix(
            patient_mrns=patient_mrns,
            trial_nct_ids=None
        )

    def compute_for_new_trials(self, trial_nct_ids: List[str]) -> Dict:
        """
        Compute eligibility for new trials against all patients.

        Args:
            trial_nct_ids: List of new trial NCT IDs

        Returns:
            Summary of computation
        """
        return self.compute_eligibility_matrix(
            patient_mrns=None,
            trial_nct_ids=trial_nct_ids
        )

    def full_sync(self, max_trials_per_query: int = 50, limit_trials: int = 200) -> Dict:
        """
        Perform a full sync: fetch trials and compute all eligibility.

        Args:
            max_trials_per_query: Max trials to fetch per search query
            limit_trials: Total limit on trials to process

        Returns:
            Combined summary
        """
        print("\n" + "="*60)
        print("FULL SYNC STARTING")
        print("="*60)

        # Step 1: Sync trials
        trials_summary = self.sync_trials(max_per_query=max_trials_per_query)

        # Step 2: Compute eligibility ONLY for newly added trials
        new_nct_ids = trials_summary.get("new_nct_ids", [])
        if new_nct_ids:
            print(f"\n{len(new_nct_ids)} new trials found - computing eligibility for all patients")
            eligibility_summary = self.compute_eligibility_matrix(
                trial_nct_ids=new_nct_ids
            )
        else:
            print("\nNo new trials - skipping eligibility computation")
            eligibility_summary = {
                "patients_processed": 0,
                "trials_processed": 0,
                "eligibility_computed": 0,
                "errors": 0,
                "elapsed_seconds": 0,
                "skipped": "no_new_trials"
            }

        # Log full sync
        self.data_pool.log_sync(
            sync_type="full_sync",
            new_trials=len(new_nct_ids),
            eligibility_computed=eligibility_summary.get("eligibility_computed", 0),
            status="completed"
        )

        return {
            "trials_sync": trials_summary,
            "eligibility_computation": eligibility_summary,
            "timestamp": datetime.now().isoformat()
        }


# Singleton instance
_engine_instance = None


def get_batch_engine() -> BatchEligibilityEngine:
    """Get or create the singleton batch engine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = BatchEligibilityEngine()
    return _engine_instance


# CLI interface for running batch jobs
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Batch Eligibility Engine")
    parser.add_argument(
        "--action",
        choices=["sync-trials", "compute-eligibility", "full-sync"],
        required=True,
        help="Action to perform"
    )
    parser.add_argument(
        "--max-trials",
        type=int,
        default=50,
        help="Max trials per query for sync"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Limit total trials to process"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="Number of parallel workers"
    )

    args = parser.parse_args()

    engine = BatchEligibilityEngine(max_workers=args.workers)

    if args.action == "sync-trials":
        result = engine.sync_trials(max_per_query=args.max_trials)
    elif args.action == "compute-eligibility":
        result = engine.compute_eligibility_matrix(limit_trials=args.limit)
    elif args.action == "full-sync":
        result = engine.full_sync(
            max_trials_per_query=args.max_trials,
            limit_trials=args.limit
        )

    print("\n" + json.dumps(result, indent=2))
