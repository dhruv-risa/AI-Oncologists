"""
FastAPI Application for AI Oncologist Backend

This FastAPI application provides REST API endpoints for:
1. MRN selection and validation
2. Patient constant components (demographics, diagnosis status)
3. Patient tab information (diagnosis, treatment, lab, genomics, pathology, comorbidities)
"""
import sys
import os
import json
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
import threading

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
sys.path.append(PROJECT_ROOT)

# Import backend functions
from Backend.main import (
    extract_patient_data,
    lab_tab_info,
    genomics_tab_info,
    pathology_tab_info_pipeline
)

from Backend.bytes_extractor import (
    upload_individual_reports_to_drive,
    upload_individual_radiology_reports_with_MD_notes_to_drive,
    get_document_bytes
)
from Backend.storage_uploader import upload_and_share_pdf_bytes
from Backend.data_pool import get_data_pool
from Backend.Utils.Tabs.pathology_tab import pathology_info
from Backend.Utils.Tabs.radiology_tab import extract_radiology_details_from_report
from Backend.Utils.components.patient_demographics import extract_patient_demographics
from Backend.Utils.components.patient_diagnosis_status import extract_diagnosis_status
from Backend.Utils.Tabs.comorbidities import extract_comorbidities_status
from Backend.Utils.Tabs.treatment_tab import extract_treatment_tab_info
from Backend.Utils.Tabs.diagnosis_tab import diagnosis_extraction
from Backend.Utils.Tabs.clinical_trials_tab import extract_clinical_trials
from Backend.Utils.logger_config import setup_logger

# Setup logger
logger = setup_logger(__name__)


# ============================================================================
# Utility Functions
# ============================================================================

def parse_date_for_sorting(date_str):
    """Parse various date formats into a comparable datetime object for sorting."""
    from datetime import datetime

    if not date_str or not isinstance(date_str, str):
        return datetime(1900, 1, 1)

    date_str = date_str.strip()

    if date_str.endswith('Z'):
        date_str = date_str[:-1]

    date_formats = [
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%B %d, %Y",
        "%m/%d/%Y",
        "%Y-%m-%d",
        "%d-%b-%Y",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%b %d, %Y",
    ]

    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, AttributeError):
            continue

    logger.warning(f"Could not parse date: {date_str}")
    return datetime(1900, 1, 1)


def sort_reports_by_date(reports, descending=True):
    """Sort reports by date field, with most recent first (by default)."""
    if not reports:
        return reports

    sorted_reports = sorted(
        reports,
        key=lambda x: parse_date_for_sorting(x.get('date', '')),
        reverse=descending
    )

    return sorted_reports


# Initialize data pool (before lifespan so it's available at startup)
data_pool = get_data_pool()

_sync_lock = threading.Lock()

# Track active eligibility computations for stale detection after server restart
_active_computations = {}   # mrn → threading.Thread
_computation_lock = threading.Lock()

def scheduled_trial_sync():
    """Nightly job: sync trials and recompute eligibility for all patients."""
    if not _sync_lock.acquire(blocking=False):
        logger.info("Sync already in progress - skipping")
        return
    try:
        logger.info("SCHEDULED TRIAL SYNC STARTING")
        from Backend.Utils.batch_eligibility_engine import get_batch_engine
        engine = get_batch_engine()
        result = engine.full_sync(max_trials_per_query=50, limit_trials=50)
        logger.info(f"Scheduled sync completed: {result}")
    except Exception as e:
        logger.error(f"Scheduled trial sync failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        _sync_lock.release()

@asynccontextmanager
async def lifespan(app):
    # STARTUP
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        scheduled_trial_sync,
        trigger='cron',
        hour=2, minute=0,
        id='nightly_trial_sync',
        replace_existing=True,
    )
    scheduler.start()
    logger.info("APScheduler started - nightly trial sync at 2:00 AM")

    # Initial sync if cache is empty
    try:
        trials_count = data_pool.get_trials_count()
        if trials_count == 0:
            logger.info("Trials cache empty - triggering initial sync in background")
            thread = threading.Thread(target=scheduled_trial_sync, daemon=True)
            thread.start()
        else:
            logger.info(f"Trials cache has {trials_count} trials - skipping initial sync")
    except Exception as e:
        logger.error(f"Error checking trials cache on startup: {e}")

    # Auto-seed demo patients if pool is empty
    try:
        patient_count = len(data_pool.list_all_patients())
        if patient_count == 0:
            logger.info("No patients in pool - triggering demo data seed in background")

            def seed_demo_patients():
                import time
                import requests as req

                demo_data_path = Path(__file__).parent / "demo_data.json"
                if not demo_data_path.exists():
                    logger.warning("demo_data.json not found, skipping seed")
                    return

                with open(demo_data_path) as f:
                    demo_mrns = list(json.load(f).keys())

                logger.info(f"Seeding {len(demo_mrns)} demo patients...")

                # Wait for server to be ready
                port = os.environ.get("PORT", "8000")
                base = f"http://localhost:{port}"
                for _ in range(30):
                    try:
                        req.get(f"{base}/docs", timeout=2)
                        break
                    except Exception:
                        time.sleep(2)

                for mrn in demo_mrns:
                    try:
                        if not data_pool.patient_exists(mrn):
                            resp = req.post(
                                f"{base}/api/patient/all",
                                json={"mrn": mrn},
                                timeout=300,
                            )
                            logger.info(f"Seeded patient {mrn}: {resp.status_code}")
                        else:
                            logger.info(f"Patient {mrn} already exists, skipping")
                    except Exception as e:
                        logger.error(f"Failed to seed patient {mrn}: {e}")

                logger.info("Demo patient seeding complete")

            thread = threading.Thread(target=seed_demo_patients, daemon=True)
            thread.start()
        else:
            logger.info(f"Pool has {patient_count} patients - skipping seed")
    except Exception as e:
        logger.error(f"Error checking patient pool on startup: {e}")

    yield

    # SHUTDOWN
    scheduler.shutdown(wait=False)
    logger.info("APScheduler shut down")

# Initialize FastAPI app
app = FastAPI(
    title="AI Oncologist API",
    description="API for extracting and managing oncology patient data from EMR",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Request/Response Models
# ============================================================================

class MRNRequest(BaseModel):
    mrn: str = Field(..., description="Patient's Medical Record Number", example="A2451440")


class MRNResponse(BaseModel):
    success: bool
    mrn: str
    message: str


class PatientDataResponse(BaseModel):
    success: bool
    mrn: str
    pdf_url: Optional[str]
    demographics: Optional[dict]
    diagnosis: Optional[dict]
    comorbidities: Optional[dict]
    treatment_tab_info_LOT: Optional[dict]
    treatment_tab_info_timeline: Optional[dict]
    diagnosis_header: Optional[dict]
    diagnosis_evolution_timeline: Optional[dict]
    diagnosis_footer: Optional[dict]
    lab_info: Optional[dict]
    pathology_summary: Optional[dict]
    pathology_markers: Optional[dict]
    pathology_reports: Optional[list]
    radiology_reports: Optional[list]
    error: Optional[str]


class LabDataResponse(BaseModel):
    success: bool
    mrn: str
    lab_results_count: Optional[int] = None
    processed_documents: Optional[int] = None
    lab_info: Optional[dict] = None
    metadata: Optional[dict] = None
    validation_summary: Optional[dict] = None
    fhir_metadata: Optional[dict] = None
    fhir_observations_count: Optional[int] = None
    total_data_sources: Optional[int] = None
    error: Optional[str] = None


class GenomicsPathologyResponse(BaseModel):
    success: bool
    mrn: str
    pathology_reports_count: Optional[int]
    pdf_url: Optional[str]
    file_id: Optional[str]
    pathology_documents: Optional[list]
    genomic_info: Optional[dict]
    pathology_summary: Optional[dict]
    pathology_markers: Optional[dict]
    error: Optional[str]

class URLGENERATION(BaseModel):
    mrn: str


class TestWorkflowMetadata(BaseModel):
    document_count: Optional[int] = None
    pdf_url: Optional[str] = None
    file_id: Optional[str] = None
    pipeline_stages: Optional[list] = None


class TestTabResponse(BaseModel):
    success: bool
    mrn: str
    tab_name: str
    workflow_metadata: Optional[TestWorkflowMetadata] = None
    extracted_data: Optional[dict] = None
    error: Optional[str] = None


# ============================================================================
# API Routes
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint - API health check"""
    return {
        "message": "AI Oncologist API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


# ============================================================================
# MRN Selection Routes
# ============================================================================

@app.post("/api/mrn/validate", response_model=MRNResponse, tags=["MRN"])
async def validate_mrn(request: MRNRequest):
    """
    Validate if MRN exists and can be processed.

    This is a basic validation endpoint. In production, you might want to
    add more sophisticated validation against your EMR system.
    """
    if not request.mrn or len(request.mrn.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MRN cannot be empty"
        )

    return {
        "success": True,
        "mrn": request.mrn,
        "message": f"MRN {request.mrn} is valid"
    }


# ============================================================================
# Constant Components Routes (Demographics, Diagnosis Status, etc.)
# ============================================================================

@app.post("/api/patient/all", response_model=PatientDataResponse, tags=["Patient Data"])
async def get_patient_data(request: MRNRequest):
    """
    Get all patient constant component data (demographics, diagnosis, comorbidities, treatment, diagnosis tab).

    This endpoint fetches:
    - Patient demographics
    - Diagnosis status
    - Comorbidities
    - Treatment tab information (LOT and timeline)
    - Diagnosis tab information (header, evolution timeline, footer)
    - Lab information
    - Genomics information
    - Individual pathology reports with extracted details

    The fetched data is automatically stored in the data pool for later retrieval.
    If data already exists in the pool, it returns the cached data instead of re-fetching.
    """
    try:
        # Check if patient data already exists in pool
        cached_data = data_pool.get_patient_data(request.mrn)
        logger.info(f"Cache check for MRN {request.mrn}: {'HIT' if cached_data is not None else 'MISS'} (db_path={data_pool.db_path})")
        if cached_data is not None:
            logger.info(f"Returning cached data for MRN: {request.mrn}")
            return cached_data

        # If not in cache, fetch fresh data with TWO SEQUENTIAL PIPELINES
        logger.info("="*80)
        logger.info(f"🚀 STARTING DUAL PIPELINE EXTRACTION for MRN: {request.mrn}")
        logger.info("="*80)
        logger.info("⚡ Running 2 pipelines SEQUENTIALLY (to optimize classification caching):")
        logger.info("   📊 PIPELINE 1 (3 tasks in parallel):")
        logger.info("      1️⃣  Patient Data (Demographics, Diagnosis, Treatment, etc.)")
        logger.info("      2️⃣  Lab Results")
        logger.info("      3️⃣  Pathology (classifies & caches reports)")
        logger.info("   🧬 PIPELINE 2 (2 tasks in parallel - uses cached classifications):")
        logger.info("      4️⃣  Genomics (reuses cached classifications - no duplicate API calls)")
        logger.info("      5️⃣  Radiology")
        logger.info("="*80)

        # Define extraction tasks
        def extract_patient_task():
            try:
                logger.info(f"📋 [Pipeline 1] Starting patient data extraction for MRN: {request.mrn}...")
                result = extract_patient_data(request.mrn, False)
                logger.info(f"✅ [Pipeline 1] Patient data extraction completed")
                return ('patient', result, None)
            except Exception as e:
                logger.error(f"❌ [Pipeline 1] Patient data extraction failed: {str(e)}")
                return ('patient', None, str(e))

        def extract_lab_task():
            try:
                logger.info(f"🧪 [Pipeline 1] Starting lab results extraction for MRN: {request.mrn}...")
                lab_result = lab_tab_info(request.mrn, False)
                logger.info(f"✅ [Pipeline 1] Lab results extraction completed")
                return ('lab', lab_result, None)
            except Exception as e:
                logger.error(f"❌ [Pipeline 1] Lab results extraction failed: {str(e)}")
                return ('lab', None, str(e))

        def extract_genomics_task():
            try:
                logger.info(f"🧬 [Pipeline 2] Starting genomics extraction for MRN: {request.mrn}...")
                genomics_result = genomics_tab_info(request.mrn, True)
                logger.info(f"✅ [Pipeline 2] Genomics extraction completed")
                return ('genomics', genomics_result, None)
            except Exception as e:
                logger.error(f"❌ [Pipeline 2] Genomics extraction failed: {str(e)}")
                return ('genomics', None, str(e))

        def extract_pathology_task():
            try:
                logger.info(f"🔬 [Pipeline 1] Starting pathology extraction for MRN: {request.mrn}...")
                pathology_result = pathology_tab_info_pipeline(request.mrn, False, True)
                logger.info(f"✅ [Pipeline 1] Pathology extraction completed")
                return ('pathology', pathology_result, None)
            except Exception as e:
                logger.error(f"❌ [Pipeline 1] Pathology extraction failed: {str(e)}")
                return ('pathology', None, str(e))

        def extract_radiology_task():
            try:
                logger.info(f"🏥 [Pipeline 2] Starting radiology extraction for MRN: {request.mrn}...")
                radiology_reports = upload_individual_radiology_reports_with_MD_notes_to_drive(
                    mrn=request.mrn
                )

                if radiology_reports:
                    detailed_radiology_reports = []
                    for report in radiology_reports:
                        try:
                            # Use PDF bytes directly (no download needed!)
                            radiology_summary, radiology_imp_RECIST = extract_radiology_details_from_report(
                                pdf_input=report['pdf_bytes'],  # Direct bytes extraction
                                use_gemini_api=True
                            )
                            detailed_radiology_reports.append({
                                "drive_url": report['drive_url'],
                                "drive_file_id": report['drive_file_id'],
                                "date": report['date'],
                                "document_type": report['document_type'],
                                "description": report['description'],
                                "document_id": report['document_id'],
                                "radiology_summary": radiology_summary,
                                "radiology_imp_RECIST": radiology_imp_RECIST
                            })
                        except Exception as e:
                            logger.warning(f"[Pipeline 2] Failed to extract radiology details for {report['document_id']}: {str(e)}")
                            detailed_radiology_reports.append({
                                "drive_url": report['drive_url'],
                                "drive_file_id": report['drive_file_id'],
                                "date": report['date'],
                                "document_type": report['document_type'],
                                "description": report['description'],
                                "document_id": report['document_id'],
                                "radiology_summary": None,
                                "radiology_imp_RECIST": None,
                                "extraction_error": str(e)
                            })

                    # Sort by date
                    detailed_radiology_reports = sort_reports_by_date(detailed_radiology_reports, descending=True)
                    logger.info(f"✅ [Pipeline 2] Radiology extraction completed: {len(detailed_radiology_reports)} reports")
                    return ('radiology', {'radiology_reports': detailed_radiology_reports}, None)
                else:
                    logger.info(f"✅ [Pipeline 2] Radiology extraction completed: No reports found")
                    return ('radiology', {'radiology_reports': []}, None)
            except Exception as e:
                logger.error(f"❌ [Pipeline 2] Radiology extraction failed: {str(e)}")
                return ('radiology', {'radiology_reports': []}, str(e))

        # Define pipeline runners
        def run_pipeline_1():
            """Run Pipeline 1: Patient Data, Lab, Pathology in parallel

            NOTE: Pathology runs in Pipeline 1 to classify and cache reports first.
            This allows Genomics in Pipeline 2 to reuse cached classifications.
            """
            logger.info("🚀 [Pipeline 1] Starting parallel execution...")
            tasks = [extract_patient_task, extract_lab_task, extract_pathology_task]
            results = {}
            errors = []

            with ThreadPoolExecutor(max_workers=3) as executor:
                future_to_task = {executor.submit(task): task.__name__ for task in tasks}

                for future in as_completed(future_to_task):
                    task_name = future_to_task[future]
                    try:
                        data_type, data, error = future.result()
                        if error:
                            errors.append(f"{data_type}: {error}")
                            logger.error(f"⚠️  [Pipeline 1] {data_type} extraction had errors: {error}")
                        else:
                            results[data_type] = data
                    except Exception as e:
                        logger.error(f"⚠️  [Pipeline 1] Task {task_name} failed unexpectedly: {str(e)}")
                        errors.append(f"{task_name}: {str(e)}")

            logger.info("✅ [Pipeline 1] All parallel tasks completed")
            return results, errors

        def run_pipeline_2():
            """Run Pipeline 2: Genomics and Radiology in parallel

            NOTE: Genomics runs in Pipeline 2 to reuse cached classifications from Pipeline 1.
            This eliminates duplicate Gemini API calls and reduces processing time by ~50%.
            """
            logger.info("🚀 [Pipeline 2] Starting parallel execution...")
            tasks = [extract_genomics_task, extract_radiology_task]
            results = {}
            errors = []

            with ThreadPoolExecutor(max_workers=2) as executor:
                future_to_task = {executor.submit(task): task.__name__ for task in tasks}

                for future in as_completed(future_to_task):
                    task_name = future_to_task[future]
                    try:
                        data_type, data, error = future.result()
                        if error:
                            errors.append(f"{data_type}: {error}")
                            logger.error(f"⚠️  [Pipeline 2] {data_type} extraction had errors: {error}")
                        else:
                            results[data_type] = data
                    except Exception as e:
                        logger.error(f"⚠️  [Pipeline 2] Task {task_name} failed unexpectedly: {str(e)}")
                        errors.append(f"{task_name}: {str(e)}")

            logger.info("✅ [Pipeline 2] All parallel tasks completed")
            return results, errors

        # Execute pipelines SEQUENTIALLY (Pipeline 1 then Pipeline 2)
        # This ensures Pathology classifies first, then Genomics reuses cached classifications
        logger.info("🔄 Launching Pipeline 1 first (Patient + Lab + Pathology)...")

        pipeline1_results = {}
        pipeline2_results = {}
        all_errors = []

        # Run Pipeline 1 first
        pipeline1_results, pipeline1_errors = run_pipeline_1()
        all_errors.extend(pipeline1_errors)

        logger.info("✅ Pipeline 1 completed. Classifications cached for Pipeline 2.")

        # Run Pipeline 2 second (Genomics will use cached classifications)
        logger.info("🔄 Launching Pipeline 2 (Genomics + Radiology)...")
        pipeline2_results, pipeline2_errors = run_pipeline_2()
        all_errors.extend(pipeline2_errors)

        # Combine results from both pipelines
        result = pipeline1_results.get('patient')
        lab_result = pipeline1_results.get('lab')
        pathology_result = pipeline1_results.get('pathology')  # Now in Pipeline 1
        genomics_result = pipeline2_results.get('genomics')    # Now in Pipeline 2
        radiology_result = pipeline2_results.get('radiology')
        errors = all_errors

        # Check if we got the essential patient data
        if result is None:
            raise Exception(f"Failed to extract patient data. Errors: {', '.join(errors)}")

        logger.info("="*80)
        logger.info(f"✅ DUAL PIPELINE EXTRACTION COMPLETED for MRN: {request.mrn}")
        logger.info(f"   📊 Pipeline 1 (Parallel): Patient Data, Lab, Pathology")
        logger.info(f"   🧬 Pipeline 2 (Parallel): Genomics, Radiology")
        if errors:
            logger.warning(f"⚠️  Some extractions had errors: {', '.join(errors)}")
        logger.info("="*80)

        # Check if patient data extraction succeeded
        if not result.get('success', False):
            # If patient data extraction failed, return error response with all required fields
            logger.error(f"❌ Patient data extraction failed: {result.get('error', 'Unknown error')}")
            return {
                'success': False,
                'mrn': request.mrn,
                'pdf_url': None,
                'demographics': None,
                'diagnosis': None,
                'comorbidities': None,
                'treatment_tab_info_LOT': None,
                'treatment_tab_info_timeline': None,
                'diagnosis_header': None,
                'diagnosis_evolution_timeline': None,
                'diagnosis_footer': None,
                'lab_info': None,
                'pathology_summary': None,
                'pathology_markers': None,
                'pathology_reports': [],
                'radiology_reports': [],
                'error': result.get('error', 'Patient data extraction failed')
            }

        # Merge results (handle None values gracefully)
        result['lab_info'] = lab_result.get('lab_info') if lab_result else None
        result['lab_reports'] = lab_result.get('lab_reports', []) if lab_result else []
        result['genomic_info'] = genomics_result.get('genomic_info') if genomics_result else None
        result['genomics_reports'] = genomics_result.get('genomics_reports', []) if genomics_result else []
        result['pathology_summary'] = pathology_result.get('pathology_summary') if pathology_result else None
        result['pathology_markers'] = pathology_result.get('pathology_markers') if pathology_result else None

        # Use pathology data already extracted by pathology_tab_info_pipeline (no duplicate extraction)
        print(f"Using pathology reports already extracted by pathology_tab_info_pipeline for MRN: {request.mrn}")

        # Transform the pathology pipeline results into the format expected by the frontend
        detailed_pathology_reports = []
        genomic_alterations_reports = []
        no_test_performed_reports = []

        # Get the typical pathology reports from the pipeline result (handle None)
        typical_reports = pathology_result.get('typical_pathology_reports', []) if pathology_result else []
        for report in typical_reports:
            detailed_pathology_reports.append({
                "drive_url": report.get('drive_url'),
                "drive_file_id": report.get('file_id'),
                "date": report.get('date'),
                "document_type": report.get('document_type'),
                "description": report.get('description', 'Pathology Report'),
                "document_id": report.get('document_id', report.get('date')),
                "pathology_summary": report.get('pathology_summary'),
                "pathology_markers": report.get('pathology_markers')
            })

        # Get genomic pathology reports from pipeline result (handle None)
        genomic_reports = pathology_result.get('genomic_pathology_reports', []) if pathology_result else []
        for report in genomic_reports:
            genomic_alterations_reports.append({
                "drive_url": report.get('drive_url', ''),
                "drive_file_id": report.get('file_id', ''),
                "date": report.get('date'),
                "document_type": report.get('document_type'),
                "description": report.get('description', 'Genomic Alterations Report'),
                "document_id": report.get('document_id', report.get('date')),
                "classification": report.get('classification'),
                "report_type": "GENOMIC_ALTERATIONS"
            })

        # Sort pathology reports by date (most recent first)
        detailed_pathology_reports = sort_reports_by_date(detailed_pathology_reports, descending=True)
        logger.info(f"✅ Sorted {len(detailed_pathology_reports)} pathology reports by date (most recent first)")

        result['pathology_reports'] = detailed_pathology_reports
        result['genomic_alterations_reports'] = genomic_alterations_reports
        result['no_test_performed_reports'] = no_test_performed_reports

        # Log summary
        print(f"📊 Classification Summary:")
        print(f"   - Typical Pathology Reports: {len(detailed_pathology_reports)}")
        print(f"   - Genomic Alterations Reports: {len(genomic_alterations_reports)}")
        print(f"   - No Test Performed Reports: {len(no_test_performed_reports)}")

        # Merge radiology results from parallel extraction
        result['radiology_reports'] = radiology_result.get('radiology_reports', []) if radiology_result else []
        logger.info(f"📊 Radiology Reports: {len(result['radiology_reports'])} reports")

        # Auto-store in data pool
        logger.info(f"Storing patient {request.mrn} in data pool (db_path={data_pool.db_path}, result_keys={list(result.keys()) if result else 'None'})")
        store_ok = data_pool.store_patient_data(mrn=request.mrn, data=result)
        logger.info(f"Store result for {request.mrn}: {store_ok}")

        # Auto-compute eligibility for this patient against all cached trials (background)
        try:
            trials_count = data_pool.get_trials_count()
            if trials_count > 0:
                print(f"\n{'='*60}")
                print(f"AUTO-COMPUTING ELIGIBILITY for new patient {request.mrn}")
                print(f"Matching against {trials_count} cached trials...")
                print(f"{'='*60}")

                # Run in background thread so it doesn't block the response
                def compute_eligibility_background(mrn: str, patient_data: dict):
                    try:
                        from Utils.batch_eligibility_engine import get_batch_engine
                        engine = get_batch_engine()
                        engine.compute_eligibility_matrix(
                            patient_mrns=[mrn],
                            limit_trials=100  # Limit for performance
                        )
                        print(f"Eligibility computation complete for patient {mrn}")
                    except Exception as e:
                        print(f"Background eligibility computation failed: {e}")
                        try:
                            data_pool.complete_computation_progress(mrn, error_message=str(e))
                        except:
                            pass
                    finally:
                        with _computation_lock:
                            _active_computations.pop(mrn, None)

                import threading
                thread = threading.Thread(
                    target=compute_eligibility_background,
                    args=(request.mrn, result)
                )
                thread.daemon = True

                # Register thread for stale detection
                with _computation_lock:
                    _active_computations[request.mrn] = thread

                thread.start()

                result['eligibility_computation'] = "started_in_background"
            else:
                result['eligibility_computation'] = "skipped_no_trials_cached"
        except Exception as e:
            print(f"Warning: Could not start eligibility computation: {e}")
            result['eligibility_computation'] = "failed"

        return result
    except Exception as e:
        import traceback
        # Print full traceback for debugging
        print(f"\n{'='*70}")
        print(f"ERROR in /api/patient/all endpoint:")
        print(f"{'='*70}")
        traceback.print_exc()
        print(f"{'='*70}\n")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/patient/demographics", tags=["Patient Data"])
async def get_demographics(request: MRNRequest):
    """
    Get patient demographics only.

    Returns:
    - Patient Name
    - MRN
    - Date of Birth
    - Age
    - Gender
    - Height
    - Weight
    - Primary Oncologist
    - Last Visit date
    """
    try:
        result = extract_patient_data(mrn=request.mrn, verbose=False)

        if not result['success']:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get('error', 'Failed to extract demographics')
            )

        return {
            "success": True,
            "mrn": request.mrn,
            "demographics": result['demographics']
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/patient/diagnosis-status", tags=["Patient Data"])
async def get_diagnosis_status(request: MRNRequest):
    """
    Get patient diagnosis status only.

    Returns:
    - cancer_type
    - histology
    - diagnosis_date
    - tnm_classification
    - ajcc_stage
    - line_of_therapy
    - metastatic_sites
    - ecog_status
    - disease_status
    """
    try:
        result = extract_patient_data(mrn=request.mrn, verbose=False)

        if not result['success']:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get('error', 'Failed to extract diagnosis status')
            )

        return {
            "success": True,
            "mrn": request.mrn,
            "diagnosis": result['diagnosis']

        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/patient/comorbidities", tags=["Patient Data"])
async def get_comorbidities(request: MRNRequest):
    """
    Get patient comorbidities information.
    """
    try:
        result = extract_patient_data(mrn=request.mrn, verbose=False)

        if not result['success']:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get('error', 'Failed to extract comorbidities')
            )

        return {
            "success": True,
            "mrn": request.mrn,
            "comorbidities": result['comorbidities']
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# Tab Routes
# ============================================================================

@app.post("/api/tabs/treatment", tags=["Tabs"])
async def get_treatment_tab(request: MRNRequest):
    """
    Get treatment tab information.

    Returns:
    - treatment_tab_info_LOT: Line of therapy information
    - treatment_tab_info_timeline: Treatment timeline
    """
    try:
        result = extract_patient_data(mrn=request.mrn, verbose=False)

        if not result['success']:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get('error', 'Failed to extract treatment information')
            )

        return {
            "success": True,
            "mrn": request.mrn,
            "treatment_tab_info_LOT": result['treatment_tab_info_LOT'],
            "treatment_tab_info_timeline": result['treatment_tab_info_timeline']
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/tabs/diagnosis", tags=["Tabs"])
async def get_diagnosis_tab(request: MRNRequest):
    """
    Get diagnosis tab information.

    Returns:
    - diagnosis_header: Header information
    - diagnosis_evolution_timeline: Stage evolution timeline
    - diagnosis_footer: Footer with duration information
    """
    try:
        result = extract_patient_data(mrn=request.mrn, verbose=False)

        if not result['success']:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get('error', 'Failed to extract diagnosis tab information')
            )

        return {
            "success": True,
            "mrn": request.mrn,
            "diagnosis_header": result['diagnosis_header'],
            "diagnosis_evolution_timeline": result['diagnosis_evolution_timeline'],
            "diagnosis_footer": result['diagnosis_footer']
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/tabs/lab", response_model=LabDataResponse, tags=["Tabs"])
async def get_lab_tab(request: MRNRequest):
    """
    Get lab tab information using Gemini individual processing.

    This endpoint implements the following workflow:
    1. Fetches all lab result documents from the last 6 months from FHIR
    2. For each report, extracts data using Gemini API (REST):
       - Passes PDF bytes directly to Gemini (no file downloads)
       - Extracts current values (most recent measurement with unit, date, status, reference range)
       - Extracts trends (historical data points from each report)
    3. Consolidates all individual results into final UI-ready format
    4. Merges trend data from all reports for each biomarker

    Returns:
        LabDataResponse with consolidated lab data including:
        - Tumor markers (CEA, NSE, proGRP, CYFRA 21-1)
        - Complete blood count (WBC, Hemoglobin, Platelets, ANC)
        - Metabolic panel (Creatinine, ALT, AST, Total Bilirubin)
    """
    try:
        result = lab_tab_info(mrn=request.mrn, verbose=False)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post('/api/tabs/pathology_reports_extraction', tags = ["Tabs"])
async def get_pathology_reports(request : MRNRequest):
    """
    Get pathology report URLs from the last 6 months, uploaded to Google Drive.

    This endpoint:
    1. Extracts pathology reports from FHIR
    2. Uploads each report to Google Drive in a "Pathology Reports" folder
    3. Returns Google Drive URLs for each report

    Returns:
    - List of documents with Google Drive URLs
    """
    try:
        result = upload_individual_reports_to_drive(
            mrn=request.mrn,
            report_type='pathology'
        )

        if not result:
            return {
                "success": True,
                "mrn": request.mrn,
                "documents": [],
                "message": "No pathology reports found"
            }

        # Extract drive URLs and metadata
        documents = [{
            "drive_url": doc['drive_url'],
            "drive_file_id": doc['drive_file_id'],
            "date": doc['date'],
            "document_type": doc['document_type'],
            "description": doc['description']
        } for doc in result]

        return {
            "success": True,
            "mrn": request.mrn,
            "reports_count": len(documents),
            "documents": documents
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post('/api/tabs/radiology_reports_extraction', tags = ["Tabs"])
async def get_radiology_reports(request : MRNRequest):
    """
    Get radiology report URLs from the last 6 months, uploaded to Google Drive.

    This endpoint:
    1. Extracts radiology reports from FHIR
    2. Uploads each report to Google Drive in a "Radiology Reports" folder
    3. Returns Google Drive URLs for each report

    Returns:
    - List of documents with Google Drive URLs
    """
    try:
        result = upload_individual_reports_to_drive(
            mrn=request.mrn,
            report_type='radiology'
        )

        if not result:
            return {
                "success": True,
                "mrn": request.mrn,
                "documents": [],
                "message": "No radiology reports found"
            }

        # Extract drive URLs and metadata
        documents = [{
            "drive_url": doc['drive_url'],
            "drive_file_id": doc['drive_file_id'],
            "date": doc['date'],
            "document_type": doc['document_type'],
            "description": doc['description']
        } for doc in result]

        return {
            "success": True,
            "mrn": request.mrn,
            "reports_count": len(documents),
            "documents": documents
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post('/api/tabs/radiology_reports', tags = ["Tabs"])
async def get_radiology_reports_cached(request: MRNRequest):
    """
    Get cached radiology reports for a patient.

    This endpoint returns radiology reports that were extracted during the initial
    patient data load in /api/patient/all. It does NOT perform extraction - it only
    returns cached data from the data pool.

    Returns:
    - List of cached radiology reports with their extracted details
    - Each report includes: URLs, metadata, radiology_summary, and radiology_imp_RECIST
    """
    try:
        # Get cached patient data from data pool
        cached_patient_data = data_pool.get_patient_data(request.mrn)

        if not cached_patient_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with MRN {request.mrn} not found in data pool. Please fetch the data first using /api/patient/all endpoint."
            )

        radiology_reports = cached_patient_data.get('radiology_reports', [])

        return {
            "success": True,
            "mrn": request.mrn,
            "reports_count": len(radiology_reports),
            "reports": radiology_reports
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post('/api/tabs/pathology_details_extraction', tags = ["Tabs"])
async def get_pathology_details(request: MRNRequest):
    """
    Get detailed pathology information for each pathology report (lazy loading).

    This endpoint:
    1. Checks if pathology reports are already cached in the data pool
    2. If cached, returns them immediately
    3. If not cached:
       - Fetches all pathology report URLs from Google Drive
       - For each report, extracts detailed pathology information using AI
       - Caches the results in the data pool
       - Returns structured data with both report metadata and extracted details

    Returns:
    - List of reports with their extracted pathology details
    - Each report includes: URL, metadata, pathology_summary, and pathology_markers
    """
    try:
        # Step 1: Check if pathology reports are already cached
        cached_patient_data = data_pool.get_patient_data(request.mrn)

        if cached_patient_data and cached_patient_data.get('pathology_reports') is not None:
            print(f"Returning cached pathology reports for MRN: {request.mrn}")
            return {
                "success": True,
                "mrn": request.mrn,
                "reports_count": len(cached_patient_data['pathology_reports']),
                "reports": cached_patient_data['pathology_reports']
            }

        # Step 2: If not cached, fetch and extract pathology reports
        print(f"Extracting pathology reports for MRN: {request.mrn}")
        reports = upload_individual_reports_to_drive(
            mrn=request.mrn,
            report_type='pathology'
        )

        if not reports:
            # Cache empty result
            if cached_patient_data:
                cached_patient_data['pathology_reports'] = []
                data_pool.store_patient_data(mrn=request.mrn, data=cached_patient_data)

            return {
                "success": True,
                "mrn": request.mrn,
                "reports": [],
                "message": "No pathology reports found"
            }

        # Step 3: Extract pathology details for each report
        detailed_reports = []
        genomic_alterations_reports = []  # Store genomic reports separately
        no_test_performed_reports = []  # Store no test performed reports

        for report in reports:
            try:
                # Extract pathology information from the Drive URL
                pathology_summary, pathology_markers = pathology_info(pdf_url=report['drive_url'], use_gemini_api=True)

                # Check report type and classify accordingly
                if isinstance(pathology_summary, dict):
                    report_type = pathology_summary.get('report_type')

                    if report_type == 'GENOMIC_ALTERATIONS':
                        # Store in genomic alterations list
                        genomic_alterations_reports.append({
                            "drive_url": report['drive_url'],
                            "drive_file_id": report['drive_file_id'],
                            "date": report['date'],
                            "document_type": report['document_type'],
                            "description": report['description'],
                            "document_id": report['document_id'],
                            "classification": pathology_summary.get('classification'),
                            "report_type": "GENOMIC_ALTERATIONS"
                        })

                    elif report_type == 'NO_TEST_PERFORMED':
                        # Store in no test performed list
                        no_test_performed_reports.append({
                            "drive_url": report['drive_url'],
                            "drive_file_id": report['drive_file_id'],
                            "date": report['date'],
                            "document_type": report['document_type'],
                            "description": report['description'],
                            "document_id": report['document_id'],
                            "classification": pathology_summary.get('classification'),
                            "report_type": "NO_TEST_PERFORMED"
                        })

                    else:
                        # Store as typical pathology report
                        detailed_reports.append({
                            "drive_url": report['drive_url'],
                            "drive_file_id": report['drive_file_id'],
                            "date": report['date'],
                            "document_type": report['document_type'],
                            "description": report['description'],
                            "document_id": report['document_id'],
                            "pathology_summary": pathology_summary,
                            "pathology_markers": pathology_markers
                        })
                else:
                    # Fallback: if pathology_summary is not a dict, treat as typical pathology
                    detailed_reports.append({
                        "drive_url": report['drive_url'],
                        "drive_file_id": report['drive_file_id'],
                        "date": report['date'],
                        "document_type": report['document_type'],
                        "description": report['description'],
                        "document_id": report['document_id'],
                        "pathology_summary": pathology_summary,
                        "pathology_markers": pathology_markers
                    })
            except Exception as e:
                # If extraction fails for a report, include error but continue with others
                detailed_reports.append({
                    "drive_url": report['drive_url'],
                    "drive_file_id": report['drive_file_id'],
                    "date": report['date'],
                    "document_type": report['document_type'],
                    "description": report['description'],
                    "document_id": report['document_id'],
                    "pathology_summary": None,
                    "pathology_markers": None,
                    "extraction_error": str(e)
                })

        # Step 4: Cache the extracted pathology reports in the data pool
        if cached_patient_data:
            cached_patient_data['pathology_reports'] = detailed_reports
            cached_patient_data['genomic_alterations_reports'] = genomic_alterations_reports
            cached_patient_data['no_test_performed_reports'] = no_test_performed_reports
            data_pool.store_patient_data(mrn=request.mrn, data=cached_patient_data)

        return {
            "success": True,
            "mrn": request.mrn,
            "pathology_reports_count": len(detailed_reports),
            "genomic_alterations_count": len(genomic_alterations_reports),
            "no_test_performed_count": len(no_test_performed_reports),
            "pathology_reports": detailed_reports,
            "genomic_alterations_reports": genomic_alterations_reports,
            "no_test_performed_reports": no_test_performed_reports
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    

@app.post("/api/tabs/genomics", tags=["Tabs"])
async def get_genomics_tab(request: MRNRequest):
    """
    Get genomics tab information.

    This endpoint:
    1. Fetches all pathology report documents
    2. Classifies each report to identify genomic alterations
    3. Filters to keep only genomic pathology reports + MD notes
    4. Combines filtered documents into a single PDF
    5. Uploads to Google Drive
    6. Extracts genomic information
    """
    try:
        result = genomics_tab_info(mrn=request.mrn, verbose=False)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/tabs/pathology", tags=["Tabs"])
async def get_pathology_tab(request: MRNRequest):
    """
    Get pathology tab information.

    This endpoint:
    1. Fetches all pathology report documents
    2. Classifies each report to identify typical pathology
    3. Filters to keep only typical pathology reports
    4. Processes each typical pathology report individually
    5. Uploads to Google Drive
    6. Extracts pathology summary and markers
    """
    try:
        result = pathology_tab_info_pipeline(mrn=request.mrn, verbose=False, use_gemini_api=True)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/tabs/clinical-trials", tags=["Tabs"])
async def get_clinical_trials(request: MRNRequest):
    """
    Get matched clinical trials for a patient using smart multi-query search.

    NEW STRATEGY:
    1. Gets patient data from the data pool (must be loaded first via /api/patient/all)
    2. Builds targeted search queries from patient data (cancer type, biomarkers, genomics, etc.)
    3. Searches ClinicalTrials.gov API with multiple queries (250+ trials per query, 2 pages)
    4. Deduplicates and analyzes ALL eligibility criteria against patient data with LLM
    5. Returns trials sorted by eligibility percentage

    Expected to fetch 500-1000 unique trials for comprehensive matching.

    Returns:
    - List of matched trials with full eligibility criteria breakdown
    - Each criterion shows: what the trial requires, patient's value, and match status
    - Summary statistics (likely_eligible, potentially_eligible, not_eligible counts)
    """
    try:
        # Get patient data from pool
        patient_data = data_pool.get_patient_data(request.mrn)

        if not patient_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with MRN {request.mrn} not found. Please load patient data first using /api/patient/all"
            )

        # Extract clinical trials matches using smart multi-query strategy
        # max_trials_per_query=250, max_pages=2 -> ~500 trials per query
        result = extract_clinical_trials(patient_data, max_trials_per_query=50, max_pages=1)

        return {
            "success": result.get("success", False),
            "mrn": request.mrn,
            "search_queries": result.get("search_queries", []),
            "total_queries": result.get("total_queries", 0),
            "patient_cancer_type": result.get("patient_cancer_type", ""),
            "total_trials_fetched": result.get("total_trials_fetched", 0),
            "total_trials_analyzed": result.get("total_trials_analyzed", 0),
            "summary": result.get("summary", {}),
            "trials": result.get("trials", []),
            "message": result.get("message"),
            "error": result.get("error")
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# Helper Functions for Testing
# ============================================================================

def _test_get_md_note_url(mrn: str) -> str:
    """
    Helper function to fetch MD note and upload to Drive for testing.

    This function is used by test endpoints that need MD notes.
    It fetches the most recent MD note from FHIR and uploads to Google Drive.

    Args:
        mrn (str): Patient's Medical Record Number

    Returns:
        str: Google Drive shareable URL

    Raises:
        ValueError: If no MD notes found for the MRN
    """
    document_type_patterns = [
        r'\bMD\b.*\bvisit\b',
        r'\bMD\b.*\bnote\b',
        r'\bphysician\b.*\bvisit\b',
        r'\bphysician\b.*\bnote\b',
        r'\bprogress\b.*\bnote\b'
    ]

    pdf_bytes = get_document_bytes(
        mrn=mrn,
        description_patterns=document_type_patterns
    )

    if not pdf_bytes:
        raise ValueError(f"No MD notes found for MRN: {mrn}")

    upload_result = upload_and_share_pdf_bytes(
        pdf_bytes=pdf_bytes,
        file_name=f"TEST_MD_note_{mrn}.pdf"
    )

    return upload_result['shareable_url']


# ============================================================================
# Data Pool Routes
# ============================================================================

@app.get("/api/pool/patient/{mrn}", tags=["Data Pool"])
async def get_patient_from_pool(mrn: str):
    """
    Retrieve patient data from the data pool.

    This endpoint retrieves previously fetched patient data from the pool.
    If the patient data is not in the pool, returns 404.

    Use this endpoint in your static UI to fetch patient data without
    making expensive API calls to the EMR system.
    """
    patient_data = data_pool.get_patient_data(mrn)

    if patient_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with MRN {mrn} not found in data pool. Please fetch the data first using /api/patient/all endpoint."
        )

    return patient_data


@app.get("/api/pool/patients", tags=["Data Pool"])
async def list_patients_in_pool():
    """
    List all patients in the data pool.

    Returns a list of all patients currently stored in the pool
    with their MRN and timestamp information.
    """
    patients = data_pool.list_all_patients()

    return {
        "success": True,
        "count": len(patients),
        "patients": patients
    }


@app.get("/api/pool/debug", tags=["Data Pool"])
async def debug_data_pool():
    """Debug endpoint to diagnose data pool state."""
    import sqlite3 as _sql
    db_path = data_pool.db_path
    info = {
        "db_path": db_path,
        "storage": "firestore" if data_pool._firestore else "sqlite",
    }
    try:
        # Patient count from whichever backend is active
        patients = data_pool.list_all_patients()
        info["patient_count"] = len(patients)
        info["mrns"] = [p["mrn"] for p in patients]
    except Exception as e:
        info["patient_error"] = str(e)
    try:
        conn = _sql.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM trials_cache")
        info["trials_count"] = cur.fetchone()[0]
        conn.close()
    except Exception as e:
        info["trials_error"] = str(e)
    return info


@app.post("/api/admin/migrate-documents-to-firebase", tags=["Admin"])
async def migrate_documents_to_firebase():
    """
    One-time migration: download all document PDFs from Google Drive,
    upload to Firebase Storage, and update Firestore patient records.
    """
    from Backend.storage_uploader import upload_pdf_bytes_to_storage
    from Backend.drive_uploader import download_pdf_bytes_from_drive_url

    if not data_pool._firestore:
        raise HTTPException(status_code=500, detail="Firestore not available")

    results = {"migrated": 0, "failed": 0, "skipped": 0, "errors": []}
    docs = data_pool._firestore.collection(data_pool.FIRESTORE_COLLECTION).stream()

    for doc in docs:
        try:
            doc_data = doc.to_dict()
            mrn = doc_data.get("mrn", doc.id)
            patient_data = json.loads(doc_data["data"])
            updated = False

            # Migrate pathology_reports
            for report in patient_data.get("pathology_reports", []):
                url = report.get("drive_url", "")
                if "drive.google.com" in url:
                    try:
                        pdf_bytes = download_pdf_bytes_from_drive_url(url)
                        fname = f"{mrn}_pathology_{report.get('document_id', 'unknown')}.pdf"
                        blob_path = f"documents/pathology/{fname}"
                        new_url = upload_pdf_bytes_to_storage(pdf_bytes, blob_path)
                        report["drive_url"] = new_url
                        report["drive_file_id"] = blob_path
                        results["migrated"] += 1
                        updated = True
                        logger.info(f"Migrated pathology doc for {mrn}: {fname}")
                    except Exception as e:
                        results["failed"] += 1
                        results["errors"].append(f"{mrn}/pathology: {str(e)[:100]}")
                else:
                    results["skipped"] += 1

            # Migrate radiology_reports
            for report in patient_data.get("radiology_reports", []):
                for url_field, id_field, suffix in [
                    ("drive_url", "drive_file_id", ""),
                    ("drive_url_with_MD", "drive_file_id_with_MD", "_with_MD"),
                ]:
                    url = report.get(url_field, "")
                    if "drive.google.com" in url:
                        try:
                            pdf_bytes = download_pdf_bytes_from_drive_url(url)
                            fname = f"{mrn}_radiology{suffix}_{report.get('document_id', 'unknown')}.pdf"
                            blob_path = f"documents/radiology/{fname}"
                            new_url = upload_pdf_bytes_to_storage(pdf_bytes, blob_path)
                            report[url_field] = new_url
                            report[id_field] = blob_path
                            results["migrated"] += 1
                            updated = True
                            logger.info(f"Migrated radiology{suffix} doc for {mrn}: {fname}")
                        except Exception as e:
                            results["failed"] += 1
                            results["errors"].append(f"{mrn}/radiology{suffix}: {str(e)[:100]}")
                    else:
                        results["skipped"] += 1

            # Migrate genomics_reports
            for report in patient_data.get("genomics_reports", []):
                url = report.get("url", report.get("drive_url", ""))
                if "drive.google.com" in url:
                    try:
                        pdf_bytes = download_pdf_bytes_from_drive_url(url)
                        fname = f"{mrn}_genomics_{report.get('document_id', 'unknown')}.pdf"
                        blob_path = f"documents/genomics/{fname}"
                        new_url = upload_pdf_bytes_to_storage(pdf_bytes, blob_path)
                        if "url" in report:
                            report["url"] = new_url
                        if "drive_url" in report:
                            report["drive_url"] = new_url
                        if "file_id" in report:
                            report["file_id"] = blob_path
                        results["migrated"] += 1
                        updated = True
                        logger.info(f"Migrated genomics doc for {mrn}: {fname}")
                    except Exception as e:
                        results["failed"] += 1
                        results["errors"].append(f"{mrn}/genomics: {str(e)[:100]}")
                else:
                    results["skipped"] += 1

            # Migrate lab_results
            for report in patient_data.get("lab_results", []):
                url = report.get("url", report.get("drive_url", ""))
                if "drive.google.com" in url:
                    try:
                        pdf_bytes = download_pdf_bytes_from_drive_url(url)
                        fname = f"{mrn}_lab_{report.get('document_id', 'unknown')}.pdf"
                        blob_path = f"documents/lab/{fname}"
                        new_url = upload_pdf_bytes_to_storage(pdf_bytes, blob_path)
                        if "url" in report:
                            report["url"] = new_url
                        if "drive_url" in report:
                            report["drive_url"] = new_url
                        if "file_id" in report:
                            report["file_id"] = blob_path
                        results["migrated"] += 1
                        updated = True
                        logger.info(f"Migrated lab doc for {mrn}: {fname}")
                    except Exception as e:
                        results["failed"] += 1
                        results["errors"].append(f"{mrn}/lab: {str(e)[:100]}")
                else:
                    results["skipped"] += 1

            # Migrate top-level pdf_url
            pdf_url = patient_data.get("pdf_url", "")
            if pdf_url and "drive.google.com" in pdf_url:
                try:
                    pdf_bytes = download_pdf_bytes_from_drive_url(pdf_url)
                    blob_path = f"documents/combined/{mrn}_combined.pdf"
                    new_url = upload_pdf_bytes_to_storage(pdf_bytes, blob_path)
                    patient_data["pdf_url"] = new_url
                    results["migrated"] += 1
                    updated = True
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(f"{mrn}/combined: {str(e)[:100]}")

            # Save updated patient data back to Firestore
            if updated:
                data_pool.store_patient_data(mrn, patient_data)
                logger.info(f"Updated Firestore record for {mrn}")

        except Exception as e:
            results["errors"].append(f"{doc.id}: {str(e)[:100]}")
            results["failed"] += 1

    return results


@app.get("/api/pool/patient/{mrn}/exists", tags=["Data Pool"])
async def check_patient_in_pool(mrn: str):
    """
    Check if patient data exists in the pool.

    Returns whether the specified patient's data is available in the pool.
    """
    exists = data_pool.patient_exists(mrn)

    return {
        "success": True,
        "mrn": mrn,
        "exists": exists
    }


@app.delete("/api/pool/patient/{mrn}", tags=["Data Pool"])
async def delete_patient_from_pool(mrn: str):
    """
    Delete patient data from the pool.

    Removes the specified patient's data from the data pool.
    """
    success = data_pool.delete_patient_data(mrn)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete patient with MRN {mrn} from data pool"
        )

    return {
        "success": True,
        "mrn": mrn,
        "message": f"Patient with MRN {mrn} deleted from data pool"
    }


@app.delete("/api/pool/clear", tags=["Data Pool"])
async def clear_data_pool():
    """
    Clear all patient data from the pool.

    WARNING: This will delete all patient data from the data pool.
    Use with caution.
    """
    success = data_pool.clear_pool()

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear data pool"
        )

    return {
        "success": True,
        "message": "Data pool cleared successfully"
    }


# ============================================================================
# Trial-Centric Routes (Trials → Patients)
# ============================================================================

@app.get("/api/trials", tags=["Clinical Trials"])
async def list_trials(
    status: str = None,
    page: int = 1,
    limit: int = 50
):
    """
    List all cached clinical trials with pagination.

    This endpoint returns trials that have been pre-fetched and cached.
    Use the /api/admin/sync-trials endpoint to populate the cache.

    Query parameters:
    - status: Filter by trial status (e.g., "RECRUITING")
    - page: Page number (default: 1)
    - limit: Items per page (default: 50, max: 100)
    """
    try:
        limit = min(limit, 100)
        offset = (page - 1) * limit

        trials = data_pool.list_all_trials(
            status=status,
            limit=limit,
            offset=offset
        )

        total = data_pool.get_trials_count(status=status)

        return {
            "success": True,
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
            "trials": trials
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/trials/{nct_id}", tags=["Clinical Trials"])
async def get_trial_details(nct_id: str):
    """
    Get detailed information about a specific clinical trial.

    Returns the cached trial data including eligibility criteria,
    locations, contacts, and eligibility statistics.
    """
    try:
        trial = data_pool.get_trial(nct_id)

        if not trial:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trial {nct_id} not found in cache. Run sync-trials first."
            )

        # Get eligibility stats for this trial
        stats = data_pool.get_eligibility_stats_for_trial(nct_id)

        return {
            "success": True,
            "trial": trial,
            "eligibility_stats": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/trials/{nct_id}/patients", tags=["Clinical Trials"])
async def get_eligible_patients_for_trial(
    nct_id: str,
    eligibility_status: str = None,
    page: int = 1,
    limit: int = 50
):
    """
    Get all patients eligible for a specific clinical trial.

    This endpoint returns pre-computed eligibility results from the matrix.
    Use /api/admin/compute-eligibility to populate the matrix.

    Query parameters:
    - eligibility_status: Filter by status ("Likely Eligible", "Potentially Eligible", "Not Eligible")
    - page: Page number (default: 1)
    - limit: Items per page (default: 50, max: 100)
    """
    try:
        limit = min(limit, 100)
        offset = (page - 1) * limit

        # Get eligible patients
        patients = data_pool.get_eligible_patients_for_trial(
            nct_id=nct_id,
            status_filter=eligibility_status,
            limit=limit,
            offset=offset
        )

        # Get stats
        stats = data_pool.get_eligibility_stats_for_trial(nct_id)

        return {
            "success": True,
            "nct_id": nct_id,
            "page": page,
            "limit": limit,
            "eligibility_stats": stats,
            "patients": patients
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/patients/{mrn}/eligible-trials", tags=["Clinical Trials"])
async def get_eligible_trials_for_patient_cached(
    mrn: str,
    eligibility_status: str = None
):
    """
    Get all trials a patient is eligible for from the pre-computed cache.

    This is faster than /api/tabs/clinical-trials as it uses pre-computed results.
    Use /api/admin/compute-eligibility to populate the matrix.

    Query parameters:
    - eligibility_status: Filter by status ("Likely Eligible", "Potentially Eligible", "Not Eligible")
    """
    try:
        # Check if patient exists
        if not data_pool.patient_exists(mrn):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient {mrn} not found in data pool"
            )

        trials = data_pool.get_eligible_trials_for_patient(
            mrn=mrn,
            status_filter=eligibility_status
        )

        # Classify unknown criteria on the fly for old data missing review_type
        from Backend.Utils.Tabs.clinical_trials_tab import classify_unknown_criteria, add_suggested_tests
        for trial in trials:
            cr = trial.get("criteria_results")
            if cr and isinstance(cr, dict):
                all_cr = cr.get("inclusion", []) + cr.get("exclusion", [])
                classify_unknown_criteria(all_cr)
                add_suggested_tests(all_cr)

        # Include computation progress so frontend knows if more results are coming
        progress = data_pool.get_computation_progress(mrn)
        computation_status = "not_started"
        computation_progress = None
        if progress:
            computation_status = progress["status"]
            if computation_status == "computing":
                with _computation_lock:
                    thread = _active_computations.get(mrn)
                    if thread is None or not thread.is_alive():
                        computation_status = "stale"
            computation_progress = {
                "trials_total": progress["trials_total"],
                "trials_completed": progress["trials_completed"],
                "trials_eligible": progress["trials_eligible"],
            }

        return {
            "success": True,
            "mrn": mrn,
            "total": len(trials),
            "trials": trials,
            "computation_status": computation_status,
            "computation_progress": computation_progress
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/patients/{mrn}/eligibility-progress", tags=["Clinical Trials"])
async def get_eligibility_progress(mrn: str):
    """Get the current computation progress for a patient's eligibility analysis."""
    try:
        progress = data_pool.get_computation_progress(mrn)

        if progress is None:
            return {
                "success": True,
                "mrn": mrn,
                "status": "not_started",
                "trials_total": 0,
                "trials_completed": 0,
                "trials_eligible": 0,
                "trials_error": 0
            }

        comp_status = progress["status"]
        if comp_status == "computing":
            with _computation_lock:
                thread = _active_computations.get(mrn)
                if thread is None or not thread.is_alive():
                    comp_status = "stale"

        return {
            "success": True,
            "mrn": mrn,
            "status": comp_status,
            "trials_total": progress["trials_total"],
            "trials_completed": progress["trials_completed"],
            "trials_eligible": progress["trials_eligible"],
            "trials_error": progress["trials_error"],
            "started_at": progress.get("started_at"),
            "updated_at": progress.get("updated_at"),
            "completed_at": progress.get("completed_at"),
            "error_message": progress.get("error_message")
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ── Bucket 2: Manual criterion resolution ──────────────────────────────────

class CriterionResolution(BaseModel):
    criterion_number: int
    criterion_type: str = Field(..., description="'inclusion' or 'exclusion'")
    resolved_met: bool = Field(..., description="True = Yes (met), False = No (not met)")
    resolved_by: str = Field(..., description="'patient' or 'clinician'")

class ResolveCriteriaRequest(BaseModel):
    resolutions: List[CriterionResolution]


@app.post("/api/patients/{mrn}/trials/{nct_id}/resolve-criteria", tags=["Clinical Trials"])
async def resolve_criteria(mrn: str, nct_id: str, request: ResolveCriteriaRequest):
    """
    Manually resolve unknown eligibility criteria for a patient-trial pair.

    When a doctor or patient answers Yes/No for unknown criteria, this endpoint
    updates the stored criteria_results and recalculates the eligibility score.
    """
    import json
    import sqlite3
    from datetime import datetime

    try:
        # 1. Fetch existing eligibility row
        conn = sqlite3.connect(data_pool.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT criteria_results
            FROM eligibility_matrix
            WHERE trial_nct_id = ? AND patient_mrn = ?
        """, (nct_id, mrn))
        row = cursor.fetchone()

        if not row:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No eligibility data found for patient {mrn} and trial {nct_id}"
            )

        criteria_results = json.loads(row[0]) if row[0] else {}

        # 2. Apply resolutions
        applied = 0
        for resolution in request.resolutions:
            criteria_list = criteria_results.get(resolution.criterion_type, [])
            for criterion in criteria_list:
                if criterion.get("criterion_number") == resolution.criterion_number:
                    # Preserve original value before overwriting
                    if "original_met" not in criterion:
                        criterion["original_met"] = criterion.get("met")
                    criterion["met"] = resolution.resolved_met
                    criterion["manually_resolved"] = True
                    criterion["resolved_by"] = resolution.resolved_by
                    criterion["resolved_at"] = datetime.now().isoformat()
                    criterion["confidence"] = "manual_review"
                    applied += 1
                    break

        # 3. Recalculate eligibility score
        from Backend.Utils.Tabs.clinical_trials_tab import (
            calculate_eligibility_score, classify_unknown_criteria, add_suggested_tests
        )
        all_criteria = criteria_results.get("inclusion", []) + criteria_results.get("exclusion", [])
        all_criteria = classify_unknown_criteria(all_criteria)
        all_criteria = add_suggested_tests(all_criteria)
        eligibility = calculate_eligibility_score(all_criteria)

        # 4. Update the database
        cursor.execute("""
            UPDATE eligibility_matrix
            SET criteria_results = ?,
                eligibility_status = ?,
                eligibility_percentage = ?,
                computed_at = ?
            WHERE trial_nct_id = ? AND patient_mrn = ?
        """, (
            json.dumps(criteria_results),
            eligibility["status"],
            eligibility["percentage"],
            datetime.now().isoformat(),
            nct_id, mrn
        ))
        conn.commit()
        conn.close()

        # 5. Return updated data
        return {
            "success": True,
            "nct_id": nct_id,
            "mrn": mrn,
            "updated_eligibility": eligibility,
            "criteria_results": criteria_results,
            "resolutions_applied": applied
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ── Bucket 3: Per-trial refresh (re-run LLM for one patient×trial pair) ───

@app.post("/api/patients/{mrn}/trials/{nct_id}/refresh-eligibility", tags=["Clinical Trials"])
async def refresh_single_trial_eligibility(mrn: str, nct_id: str):
    """
    Re-run the LLM eligibility analysis for a single patient×trial pair.

    Use this after new test results enter the system so that previously-unknown
    criteria can be resolved with fresh data.  The call takes 1-3 min (LLM).
    """
    import json
    import sqlite3
    from datetime import datetime
    from concurrent.futures import ThreadPoolExecutor

    try:
        # 1. Get patient data
        patient_data = data_pool.get_patient_data(mrn)
        if patient_data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient {mrn} not found in data pool"
            )

        # 2. Get trial data
        trial = data_pool.get_trial(nct_id)
        if trial is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trial {nct_id} not found in trials cache"
            )

        # 3. Build patient context and re-run eligibility via LLM
        from Backend.Utils.Tabs.clinical_trials_tab import (
            build_patient_context, process_single_trial,
            calculate_eligibility_score, mark_consent_criteria,
            classify_unknown_criteria, add_suggested_tests,
        )

        patient_context = build_patient_context(patient_data)

        # Run the (blocking) LLM call in a thread so we don't block the event loop
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = await loop.run_in_executor(
                pool,
                process_single_trial,
                trial, patient_context, patient_data
            )

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="LLM eligibility analysis returned no result"
            )

        # 4. Persist updated results into the eligibility_matrix
        criteria_results = result.get("criteria_results", {})
        eligibility = result.get("eligibility", {})

        conn = sqlite3.connect(data_pool.db_path)
        cursor = conn.cursor()

        # Check if row exists
        cursor.execute(
            "SELECT id FROM eligibility_matrix WHERE trial_nct_id = ? AND patient_mrn = ?",
            (nct_id, mrn),
        )
        existing = cursor.fetchone()

        now = datetime.now().isoformat()
        if existing:
            cursor.execute("""
                UPDATE eligibility_matrix
                SET criteria_results = ?,
                    eligibility_status = ?,
                    eligibility_percentage = ?,
                    computed_at = ?
                WHERE trial_nct_id = ? AND patient_mrn = ?
            """, (
                json.dumps(criteria_results),
                eligibility.get("status", ""),
                eligibility.get("percentage", 0),
                now,
                nct_id, mrn,
            ))
        else:
            cursor.execute("""
                INSERT INTO eligibility_matrix
                (trial_nct_id, patient_mrn, eligibility_status, eligibility_percentage,
                 criteria_results, computed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                nct_id, mrn,
                eligibility.get("status", ""),
                eligibility.get("percentage", 0),
                json.dumps(criteria_results),
                now,
            ))

        conn.commit()
        conn.close()

        # 5. Return in the same shape as resolve-criteria for frontend reuse
        return {
            "success": True,
            "nct_id": nct_id,
            "mrn": mrn,
            "updated_eligibility": eligibility,
            "criteria_results": criteria_results,
            "resolutions_applied": 0,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing trial {nct_id} for patient {mrn}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# Patient Review Link Endpoints
# ============================================================================

@app.post("/api/patients/{mrn}/trials/{nct_id}/send-patient-review", tags=["Clinical Trials"])
async def send_patient_review(mrn: str, nct_id: str):
    """
    Generate a shareable patient review link for a specific trial.

    Extracts patient-review criteria from the eligibility data,
    creates a token, and returns a URL that can be shared with the patient.
    """
    import json
    import sqlite3
    import uuid

    try:
        # 1. Fetch eligibility data
        conn = sqlite3.connect(data_pool.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT criteria_results
            FROM eligibility_matrix
            WHERE trial_nct_id = ? AND patient_mrn = ?
        """, (nct_id, mrn))
        row = cursor.fetchone()
        conn.close()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No eligibility data found for patient {mrn} and trial {nct_id}"
            )

        criteria_results = json.loads(row[0]) if row[0] else {}

        # 2. Filter for patient-review criteria that haven't been resolved
        patient_criteria = []
        for ctype in ["inclusion", "exclusion"]:
            for c in criteria_results.get(ctype, []):
                if (c.get("review_type") == "patient" and
                        not c.get("manually_resolved")):
                    patient_criteria.append({
                        "criterion_number": c.get("criterion_number"),
                        "criterion_type": ctype,
                        "criterion_text": c.get("criterion_text", ""),
                    })

        if not patient_criteria:
            return {
                "success": False,
                "message": "No unresolved patient-review criteria found for this trial"
            }

        # 3. Generate token and store
        token = str(uuid.uuid4())
        data_pool.create_review_token(
            token=token,
            patient_mrn=mrn,
            trial_nct_id=nct_id,
            criteria_snapshot=json.dumps(patient_criteria)
        )

        # 4. Build review URL (use frontend origin for Vite dev server)
        review_url = f"http://localhost:3000/review/{token}"

        return {
            "success": True,
            "token": token,
            "review_url": review_url,
            "criteria_count": len(patient_criteria)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/review/{token}", tags=["Patient Review"])
async def get_patient_review(token: str):
    """
    Public endpoint: Get patient review data for a token.

    Returns the criteria questions the patient needs to answer.
    """
    import json

    try:
        token_data = data_pool.get_review_token(token)
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review link not found or expired"
            )

        if token_data["status"] == "completed":
            return {
                "status": "completed",
                "message": "You have already submitted your responses. Thank you!"
            }

        # Get trial title
        trial = data_pool.get_trial(token_data["trial_nct_id"])
        trial_title = trial.get("title", "Clinical Trial") if trial else "Clinical Trial"

        # Get patient first name for greeting (stored in demographics.Patient Name)
        patient_data = data_pool.get_patient_data(token_data["patient_mrn"])
        patient_first_name = ""
        if patient_data:
            demographics = patient_data.get("demographics", {})
            full_name = demographics.get("Patient Name", "") if isinstance(demographics, dict) else ""
            if full_name:
                # Name format: "Last, First M" → extract first name
                parts = full_name.split(",")
                if len(parts) > 1:
                    patient_first_name = parts[1].strip().split()[0]
                else:
                    patient_first_name = full_name.split()[0]

        criteria = json.loads(token_data["criteria_snapshot"])

        return {
            "status": "pending",
            "trial_nct_id": token_data["trial_nct_id"],
            "trial_title": trial_title,
            "patient_first_name": patient_first_name,
            "criteria": criteria
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


class PatientReviewSubmission(BaseModel):
    responses: List[CriterionResolution]


@app.post("/api/review/{token}/submit", tags=["Patient Review"])
async def submit_patient_review(token: str, request: PatientReviewSubmission):
    """
    Public endpoint: Submit patient review responses.

    Applies the patient's Yes/No answers to the eligibility criteria
    and recalculates the eligibility score in real-time.
    """
    import json
    import sqlite3
    from datetime import datetime

    try:
        # 1. Validate token
        token_data = data_pool.get_review_token(token)
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review link not found or expired"
            )

        if token_data["status"] == "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This review has already been submitted"
            )

        mrn = token_data["patient_mrn"]
        nct_id = token_data["trial_nct_id"]

        # 2. Apply resolutions using the same logic as resolve-criteria
        conn = sqlite3.connect(data_pool.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT criteria_results
            FROM eligibility_matrix
            WHERE trial_nct_id = ? AND patient_mrn = ?
        """, (nct_id, mrn))
        row = cursor.fetchone()

        if not row:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Eligibility data no longer exists"
            )

        criteria_results = json.loads(row[0]) if row[0] else {}

        # Apply each resolution
        applied = 0
        for resolution in request.responses:
            criteria_list = criteria_results.get(resolution.criterion_type, [])
            for criterion in criteria_list:
                if criterion.get("criterion_number") == resolution.criterion_number:
                    if "original_met" not in criterion:
                        criterion["original_met"] = criterion.get("met")
                    criterion["met"] = resolution.resolved_met
                    criterion["manually_resolved"] = True
                    criterion["resolved_by"] = "patient"
                    criterion["resolved_at"] = datetime.now().isoformat()
                    criterion["confidence"] = "manual_review"
                    applied += 1
                    break

        # 3. Recalculate eligibility
        from Backend.Utils.Tabs.clinical_trials_tab import (
            calculate_eligibility_score, classify_unknown_criteria, add_suggested_tests
        )
        all_criteria = criteria_results.get("inclusion", []) + criteria_results.get("exclusion", [])
        all_criteria = classify_unknown_criteria(all_criteria)
        all_criteria = add_suggested_tests(all_criteria)
        eligibility = calculate_eligibility_score(all_criteria)

        # 4. Update database
        cursor.execute("""
            UPDATE eligibility_matrix
            SET criteria_results = ?,
                eligibility_status = ?,
                eligibility_percentage = ?,
                computed_at = ?
            WHERE trial_nct_id = ? AND patient_mrn = ?
        """, (
            json.dumps(criteria_results),
            eligibility["status"],
            eligibility["percentage"],
            datetime.now().isoformat(),
            nct_id, mrn
        ))
        conn.commit()
        conn.close()

        # 5. Mark token as completed
        data_pool.complete_review_token(token, json.dumps([
            {"criterion_number": r.criterion_number,
             "criterion_type": r.criterion_type,
             "resolved_met": r.resolved_met}
            for r in request.responses
        ]))

        return {
            "success": True,
            "message": "Thank you for your responses! Your care team will review the updated eligibility.",
            "resolutions_applied": applied
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# Admin Routes for Batch Operations
# ============================================================================

@app.post("/api/admin/sync-trials", tags=["Admin"])
async def sync_trials_batch(
    max_per_query: int = 50,
    background: bool = False,
    auto_compute_eligibility: bool = True
):
    """
    Sync clinical trials from ClinicalTrials.gov API to local cache.

    This fetches trials for multiple cancer types and stores them in the database.
    Can run in foreground (blocking) or background (async).
    After syncing, automatically computes eligibility for all existing patients.

    Query parameters:
    - max_per_query: Maximum trials to fetch per search query (default: 50)
    - background: Run in background (default: False)
    - auto_compute_eligibility: Auto-compute eligibility for all patients after sync (default: True)
    """
    try:
        from Utils.batch_eligibility_engine import get_batch_engine

        engine = get_batch_engine()

        def sync_and_compute():
            # First sync trials
            sync_result = engine.sync_trials(max_per_query=max_per_query)

            # Then auto-compute eligibility ONLY for newly added trials
            new_nct_ids = sync_result.get("new_nct_ids", [])
            if auto_compute_eligibility and new_nct_ids:
                patients = data_pool.list_all_patients()
                if patients:
                    print(f"\n{'='*60}")
                    print(f"AUTO-COMPUTING ELIGIBILITY for {len(patients)} patients against {len(new_nct_ids)} NEW trials")
                    print(f"{'='*60}")
                    engine.compute_eligibility_matrix(trial_nct_ids=new_nct_ids)
            elif not new_nct_ids:
                print("No new trials added - skipping eligibility computation")

            return sync_result

        if background:
            # Run in background using thread pool
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:
                loop.run_in_executor(executor, sync_and_compute)

            return {
                "success": True,
                "message": "Trial sync started in background (will auto-compute eligibility)",
                "max_per_query": max_per_query
            }
        else:
            result = sync_and_compute()
            return {
                "success": True,
                "result": result
            }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/admin/compute-eligibility", tags=["Admin"])
async def compute_eligibility_batch(
    limit_trials: int = 100,
    patient_mrn: str = None,
    background: bool = False
):
    """
    Compute eligibility matrix for all patient×trial combinations.

    This pre-computes eligibility for all patients against all cached trials.
    Results are stored in the eligibility_matrix table for instant queries.

    Query parameters:
    - limit_trials: Maximum number of trials to process (default: 100)
    - patient_mrn: Compute only for specific patient (optional)
    - background: Run in background (default: False)
    """
    try:
        from Utils.batch_eligibility_engine import get_batch_engine

        engine = get_batch_engine()

        patient_mrns = [patient_mrn] if patient_mrn else None

        if background:
            # Prevent duplicate computations for the same patient
            if patient_mrn:
                with _computation_lock:
                    existing = _active_computations.get(patient_mrn)
                    if existing and existing.is_alive():
                        return {
                            "success": True,
                            "message": "Eligibility computation already in progress",
                            "already_running": True,
                            "limit_trials": limit_trials,
                            "patient_mrn": patient_mrn
                        }

            import threading
            def _run_eligibility():
                try:
                    engine.compute_eligibility_matrix(
                        patient_mrns=patient_mrns,
                        limit_trials=limit_trials
                    )
                except Exception as e:
                    print(f"Background eligibility computation failed: {e}")
                finally:
                    if patient_mrn:
                        with _computation_lock:
                            _active_computations.pop(patient_mrn, None)

            thread = threading.Thread(target=_run_eligibility, daemon=True)
            thread.start()

            # Register so we can detect duplicates
            if patient_mrn:
                with _computation_lock:
                    _active_computations[patient_mrn] = thread

            return {
                "success": True,
                "message": "Eligibility computation started in background",
                "limit_trials": limit_trials,
                "patient_mrn": patient_mrn
            }
        else:
            result = engine.compute_eligibility_matrix(
                patient_mrns=patient_mrns,
                limit_trials=limit_trials
            )
            return {
                "success": True,
                "result": result
            }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/admin/full-sync", tags=["Admin"])
async def full_sync_batch(
    max_trials_per_query: int = 50,
    limit_trials: int = 50,
    background: bool = True
):
    """
    Perform a full sync: fetch trials and compute all eligibility.

    This is a convenience endpoint that runs both sync-trials and compute-eligibility.
    Recommended to run in background for large datasets.

    Query parameters:
    - max_trials_per_query: Max trials to fetch per search query (default: 50)
    - limit_trials: Total limit on trials to process for eligibility (default: 100)
    - background: Run in background (default: True)
    """
    try:
        from Utils.batch_eligibility_engine import get_batch_engine

        engine = get_batch_engine()

        if background:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:
                loop.run_in_executor(
                    executor,
                    engine.full_sync,
                    max_trials_per_query,
                    limit_trials
                )

            return {
                "success": True,
                "message": "Full sync started in background",
                "max_trials_per_query": max_trials_per_query,
                "limit_trials": limit_trials
            }
        else:
            result = engine.full_sync(
                max_trials_per_query=max_trials_per_query,
                limit_trials=limit_trials
            )
            return {
                "success": True,
                "result": result
            }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/admin/sync-status", tags=["Admin"])
async def get_sync_status():
    """
    Get the status of the last sync operations.

    Returns information about the most recent trials sync and eligibility computation.
    """
    try:
        last_trials_sync = data_pool.get_last_sync("trials_fetch")
        last_eligibility_sync = data_pool.get_last_sync("eligibility_compute")
        last_full_sync = data_pool.get_last_sync("full_sync")

        trials_count = data_pool.get_trials_count()

        # Check scheduler status
        scheduler_active = False
        next_scheduled_sync = None
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            # The scheduler is created in lifespan; check via the job store
            # We look for any running BackgroundScheduler instances
            import gc
            for obj in gc.get_referrers(BackgroundScheduler):
                if isinstance(obj, BackgroundScheduler) and obj.running:
                    scheduler_active = True
                    job = obj.get_job('nightly_trial_sync')
                    if job and job.next_run_time:
                        next_scheduled_sync = job.next_run_time.isoformat()
                    break
        except Exception:
            pass

        return {
            "success": True,
            "trials_in_cache": trials_count,
            "last_trials_sync": last_trials_sync,
            "last_eligibility_computation": last_eligibility_sync,
            "last_full_sync": last_full_sync,
            "scheduler_active": scheduler_active,
            "next_scheduled_sync": next_scheduled_sync
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# Testing Routes
# ============================================================================

@app.post("/api/test/demographics", response_model=TestTabResponse, tags=["Testing"])
async def test_demographics_tab(request: MRNRequest):
    """
    Test end-to-end workflow for Demographics tab.

    Workflow:
    1. Fetch most recent MD note from FHIR
    2. Upload to Google Drive
    3. Extract demographics information

    Note: This endpoint ALWAYS bypasses cache for testing purposes.
    """
    try:
        # Fetch MD note and upload
        pdf_url = _test_get_md_note_url(request.mrn)

        # Extract demographics
        demographics = extract_patient_demographics(pdf_url=pdf_url)

        return {
            "success": True,
            "mrn": request.mrn,
            "tab_name": "demographics",
            "workflow_metadata": {
                "document_count": 1,
                "pdf_url": pdf_url,
                "pipeline_stages": ["fetch_md_note", "upload_to_drive", "extract_demographics"]
            },
            "extracted_data": demographics
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/test/diagnosis", response_model=TestTabResponse, tags=["Testing"])
async def test_diagnosis_tab(request: MRNRequest):
    """
    Test end-to-end workflow for Diagnosis Status tab.

    Workflow:
    1. Fetch most recent MD note from FHIR
    2. Upload to Google Drive
    3. Extract diagnosis status information

    Note: This endpoint ALWAYS bypasses cache for testing purposes.
    """
    try:
        # Fetch MD note and upload
        pdf_url = _test_get_md_note_url(request.mrn)

        # Extract diagnosis status
        diagnosis = extract_diagnosis_status(pdf_url=pdf_url)

        return {
            "success": True,
            "mrn": request.mrn,
            "tab_name": "diagnosis",
            "workflow_metadata": {
                "document_count": 1,
                "pdf_url": pdf_url,
                "pipeline_stages": ["fetch_md_note", "upload_to_drive", "extract_diagnosis_status"]
            },
            "extracted_data": diagnosis
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/test/comorbidities", response_model=TestTabResponse, tags=["Testing"])
async def test_comorbidities_tab(request: MRNRequest):
    """
    Test end-to-end workflow for Comorbidities tab.

    Workflow:
    1. Fetch most recent MD note from FHIR
    2. Upload to Google Drive
    3. Extract comorbidities information

    Note: This endpoint ALWAYS bypasses cache for testing purposes.
    """
    try:
        # Fetch MD note and upload
        pdf_url = _test_get_md_note_url(request.mrn)

        # Extract comorbidities
        comorbidities = extract_comorbidities_status(pdf_url=pdf_url)

        return {
            "success": True,
            "mrn": request.mrn,
            "tab_name": "comorbidities",
            "workflow_metadata": {
                "document_count": 1,
                "pdf_url": pdf_url,
                "pipeline_stages": ["fetch_md_note", "upload_to_drive", "extract_comorbidities"]
            },
            "extracted_data": comorbidities
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/test/treatment", response_model=TestTabResponse, tags=["Testing"])
async def test_treatment_tab(request: MRNRequest):
    """
    Test end-to-end workflow for Treatment tab.

    Workflow:
    1. Fetch most recent MD note from FHIR
    2. Upload to Google Drive
    3. Extract treatment information (LOT and timeline)

    Note: This endpoint ALWAYS bypasses cache for testing purposes.
    """
    try:
        # Fetch MD note and upload
        pdf_url = _test_get_md_note_url(request.mrn)

        # Extract treatment info (returns 2 parts)
        treatment_lot, treatment_timeline = extract_treatment_tab_info(pdf_url=pdf_url)

        return {
            "success": True,
            "mrn": request.mrn,
            "tab_name": "treatment",
            "workflow_metadata": {
                "document_count": 1,
                "pdf_url": pdf_url,
                "pipeline_stages": ["fetch_md_note", "upload_to_drive", "extract_treatment_info"]
            },
            "extracted_data": {
                "treatment_tab_info_LOT": treatment_lot,
                "treatment_tab_info_timeline": treatment_timeline
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/test/diagnosis-tab", response_model=TestTabResponse, tags=["Testing"])
async def test_diagnosis_tab_full(request: MRNRequest):
    """
    Test end-to-end workflow for Diagnosis Tab (header, evolution, footer).

    Workflow:
    1. Fetch most recent MD note from FHIR
    2. Upload to Google Drive
    3. Extract diagnosis tab information (header, evolution timeline, footer)

    Note: This endpoint ALWAYS bypasses cache for testing purposes.
    """
    try:
        # Fetch MD note and upload
        pdf_url = _test_get_md_note_url(request.mrn)

        # Extract diagnosis tab info (returns 3 parts)
        diagnosis_header, diagnosis_evolution_timeline, diagnosis_footer = diagnosis_extraction(pdf_input=pdf_url)

        return {
            "success": True,
            "mrn": request.mrn,
            "tab_name": "diagnosis_tab",
            "workflow_metadata": {
                "document_count": 1,
                "pdf_url": pdf_url,
                "pipeline_stages": ["fetch_md_note", "upload_to_drive", "extract_diagnosis_tab"]
            },
            "extracted_data": {
                "diagnosis_header": diagnosis_header,
                "diagnosis_evolution_timeline": diagnosis_evolution_timeline,
                "diagnosis_footer": diagnosis_footer
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/test/lab", response_model=TestTabResponse, tags=["Testing"])
async def test_lab_tab(request: MRNRequest):
    """
    Test end-to-end workflow for Lab tab.

    Workflow:
    1. Fetch all lab results from last 6 months
    2. Combine PDFs into single file
    3. Upload to Google Drive
    4. Extract lab information

    Note: This endpoint ALWAYS bypasses cache for testing purposes.
    """
    try:
        # Run the lab pipeline (already handles fetching, combining, uploading)
        result = lab_tab_info(mrn=request.mrn, verbose=False)

        if not result['success']:
            raise ValueError(result.get('error', 'Lab extraction failed'))

        return {
            "success": True,
            "mrn": request.mrn,
            "tab_name": "lab",
            "workflow_metadata": {
                "document_count": result['lab_results_count'],
                "pdf_url": result['pdf_url'],
                "file_id": result['file_id'],
                "pipeline_stages": ["fetch_lab_results", "combine_pdfs", "upload_to_drive", "extract_lab_info"]
            },
            "extracted_data": result['lab_info']
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/test/genomics", response_model=TestTabResponse, tags=["Testing"])
async def test_genomics_tab(request: MRNRequest):
    """
    Test end-to-end workflow for Genomics tab.

    Workflow:
    1. Fetch pathology reports + MD notes
    2. Classify reports to identify genomic alterations
    3. Filter to keep only genomic pathology reports + MD notes
    4. Combine filtered documents into single PDF
    5. Upload to Google Drive
    6. Extract genomic information

    Note: This endpoint ALWAYS bypasses cache for testing purposes.
    """
    try:
        # Run the genomics pipeline
        result = genomics_tab_info(mrn=request.mrn, verbose=False)

        if not result['success']:
            raise ValueError(result.get('error', 'Genomics extraction failed'))

        return {
            "success": True,
            "mrn": request.mrn,
            "tab_name": "genomics",
            "workflow_metadata": {
                "document_count": result['total_documents_count'],
                "pdf_url": result['pdf_url'],
                "file_id": result['file_id'],
                "pipeline_stages": ["fetch_pathology_and_md_notes", "classify_reports", "filter_genomic_reports", "combine_pdfs", "upload_to_drive", "extract_genomics"]
            },
            "extracted_data": result['genomic_info']
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/test/pathology", response_model=TestTabResponse, tags=["Testing"])
async def test_pathology_tab(request: MRNRequest):
    """
    Test end-to-end workflow for Pathology tab.

    Workflow:
    1. Fetch individual pathology reports from FHIR (NOT combined with MD notes)
    2. Upload each report to Google Drive
    3. Extract pathology information from most recent typical pathology report

    Note: This endpoint ALWAYS bypasses cache for testing purposes.
    Note: Now processes INDIVIDUAL reports consistently with production /api/tabs/pathology
    """
    try:
        # Fetch individual pathology reports
        print(f"Fetching individual pathology reports for MRN: {request.mrn}")
        pathology_reports = upload_individual_reports_to_drive(
            mrn=request.mrn,
            report_type='pathology'
        )

        if not pathology_reports:
            return {
                "success": True,
                "mrn": request.mrn,
                "tab_name": "pathology",
                "workflow_metadata": {
                    "document_count": 0,
                    "pipeline_stages": ["fetch_individual_pathology_reports"]
                },
                "extracted_data": {
                    "message": "No pathology reports found",
                    "pathology_summary": None,
                    "pathology_markers": None
                }
            }

        # Process ALL reports and collect all typical pathology reports
        typical_pathology_reports = []
        genomic_reports = []
        no_test_performed_reports = []
        processing_errors = []

        for report in pathology_reports:
            try:
                # Extract pathology information
                pathology_summary, pathology_markers = pathology_info(
                    pdf_url=report['drive_url'],
                    use_gemini_api=True
                )

                # Check report type and classify accordingly
                if isinstance(pathology_summary, dict):
                    report_type = pathology_summary.get('report_type')

                    if report_type == 'GENOMIC_ALTERATIONS':
                        genomic_reports.append({
                            "document_id": report['document_id'],
                            "date": report['date'],
                            "drive_url": report['drive_url'],
                            "classification": pathology_summary.get('classification'),
                            "report_type": "GENOMIC_ALTERATIONS"
                        })

                    elif report_type == 'NO_TEST_PERFORMED':
                        no_test_performed_reports.append({
                            "document_id": report['document_id'],
                            "date": report['date'],
                            "drive_url": report['drive_url'],
                            "classification": pathology_summary.get('classification'),
                            "report_type": "NO_TEST_PERFORMED"
                        })

                    else:
                        # This is a typical pathology report - store ALL of them
                        typical_pathology_reports.append({
                            "document_id": report['document_id'],
                            "date": report['date'],
                            "drive_url": report['drive_url'],
                            "pathology_summary": pathology_summary,
                            "pathology_markers": pathology_markers
                        })
                else:
                    # Fallback: if pathology_summary is not a dict, treat as typical pathology
                    typical_pathology_reports.append({
                        "document_id": report['document_id'],
                        "date": report['date'],
                        "drive_url": report['drive_url'],
                        "pathology_summary": pathology_summary,
                        "pathology_markers": pathology_markers
                    })

            except Exception as e:
                print(f"Warning: Failed to extract pathology details for {report['document_id']}: {str(e)}")
                processing_errors.append({
                    "document_id": report['document_id'],
                    "date": report['date'],
                    "drive_url": report['drive_url'],
                    "error": str(e)
                })
                continue

        if not typical_pathology_reports:
            return {
                "success": True,
                "mrn": request.mrn,
                "tab_name": "pathology",
                "workflow_metadata": {
                    "document_count": len(pathology_reports),
                    "typical_pathology_count": 0,
                    "genomic_alterations_count": len(genomic_reports),
                    "no_test_performed_count": len(no_test_performed_reports),
                    "errors_count": len(processing_errors),
                    "pipeline_stages": ["fetch_individual_pathology_reports", "upload_to_drive", "extract_pathology"]
                },
                "extracted_data": {
                    "message": "No typical pathology reports found",
                    "typical_pathology_reports": [],
                    "genomic_alterations_reports": genomic_reports,
                    "no_test_performed_reports": no_test_performed_reports,
                    "processing_errors": processing_errors
                }
            }

        return {
            "success": True,
            "mrn": request.mrn,
            "tab_name": "pathology",
            "workflow_metadata": {
                "document_count": len(pathology_reports),
                "typical_pathology_count": len(typical_pathology_reports),
                "genomic_alterations_count": len(genomic_reports),
                "no_test_performed_count": len(no_test_performed_reports),
                "errors_count": len(processing_errors),
                "pipeline_stages": ["fetch_individual_pathology_reports", "upload_to_drive", "extract_pathology"]
            },
            "extracted_data": {
                "typical_pathology_reports": typical_pathology_reports,
                "genomic_alterations_reports": genomic_reports,
                "no_test_performed_reports": no_test_performed_reports,
                "processing_errors": processing_errors
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/test/radiology", response_model=TestTabResponse, tags=["Testing"])
async def test_radiology_tab(request: MRNRequest):
    """
    Test end-to-end workflow for Radiology tab.

    Workflow:
    1. Fetch individual radiology reports from FHIR
    2. For each report, combine with MD notes and upload to Drive
    3. Extract radiology details from each report

    Note: This endpoint ALWAYS bypasses cache for testing purposes.
    """
    try:
        # Upload individual reports to Drive
        radiology_reports = upload_individual_radiology_reports_with_MD_notes_to_drive(
            mrn=request.mrn
        )

        if not radiology_reports:
            return {
                "success": True,
                "mrn": request.mrn,
                "tab_name": "radiology",
                "workflow_metadata": {
                    "document_count": 0,
                    "pipeline_stages": ["fetch_radiology_reports", "combine_with_md_notes", "upload_to_drive"]
                },
                "extracted_data": {"reports": []}
            }

        # Extract details for each report
        detailed_reports = []
        for report in radiology_reports:
            try:
                radiology_summary, radiology_imp_RECIST = extract_radiology_details_from_report(
                    radiology_url=report['drive_url']
                )
                detailed_reports.append({
                    "drive_url": report['drive_url'],
                    "drive_file_id": report['drive_file_id'],
                    "date": report['date'],
                    "document_type": report['document_type'],
                    "description": report['description'],
                    "document_id": report['document_id'],
                    "radiology_summary": radiology_summary,
                    "radiology_imp_RECIST": radiology_imp_RECIST
                })
            except Exception as e:
                detailed_reports.append({
                    "drive_url": report['drive_url'],
                    "drive_file_id": report['drive_file_id'],
                    "date": report['date'],
                    "document_type": report['document_type'],
                    "description": report['description'],
                    "document_id": report['document_id'],
                    "extraction_error": str(e)
                })

        return {
            "success": True,
            "mrn": request.mrn,
            "tab_name": "radiology",
            "workflow_metadata": {
                "document_count": len(radiology_reports),
                "pipeline_stages": ["fetch_radiology_reports", "combine_with_md_notes", "upload_to_drive", "extract_radiology_details"]
            },
            "extracted_data": {"reports": detailed_reports}
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/test/patient-all", response_model=TestTabResponse, tags=["Testing"])
async def test_patient_all_tabs(request: MRNRequest):
    """
    Test complete end-to-end workflow for ALL tabs.

    Runs the same 3 parallel pipelines as production /api/patient/all,
    but ALWAYS bypasses cache for testing.

    Workflow:
    1. Patient Data Pipeline (demographics, diagnosis, comorbidities, treatment, diagnosis tab)
    2. Lab Results Pipeline (fetch → combine → extract)
    3. Genomics & Pathology Pipeline (fetch → combine → extract)
    4. Individual Reports (pathology and radiology)

    Note: This endpoint ALWAYS bypasses cache for testing purposes.
    """
    try:
        logger.info("="*80)
        logger.info(f"🧪 STARTING TEST: SEQUENTIAL EXTRACTION for MRN: {request.mrn}")
        logger.info("="*80)

        # Run the same sequential extraction as production, but skip cache check

        # Step 1: Extract patient data
        logger.info(f"🧪 Step 1/4: Extracting patient data for MRN: {request.mrn}...")
        result = extract_patient_data(request.mrn, False)
        logger.info("🧪 ✅ Patient data extraction completed!")

        # Step 2: Extract lab results
        logger.info(f"🧪 Step 2/4: Extracting lab results for MRN: {request.mrn}...")
        lab_result = lab_tab_info(request.mrn, False)
        logger.info("🧪 ✅ Lab results extraction completed!")

        # Step 3: Extract genomics data
        logger.info(f"🧪 Step 3/4: Extracting genomics data for MRN: {request.mrn}...")
        genomics_result = genomics_tab_info(request.mrn, False)
        logger.info("🧪 ✅ Genomics data extraction completed!")

        # Step 4: Extract pathology data
        logger.info(f"🧪 Step 4/4: Extracting pathology data for MRN: {request.mrn}...")
        pathology_result = pathology_tab_info_pipeline(request.mrn, False, True)  # use_gemini_api=True
        logger.info("🧪 ✅ Pathology data extraction completed!")

        # Combine results
        result['lab_info'] = lab_result.get('lab_info')
        result['lab_reports'] = lab_result.get('lab_reports', [])  # Lab documents for Documents tab
        result['genomic_info'] = genomics_result.get('genomic_info')
        result['genomics_reports'] = genomics_result.get('genomics_reports', [])  # Genomics documents for Documents tab
        result['pathology_summary'] = pathology_result.get('pathology_summary')
        result['pathology_markers'] = pathology_result.get('pathology_markers')

        # Use pathology data already extracted by pathology_tab_info_pipeline (no duplicate extraction)
        logger.info(f"🧪 Using pathology reports already extracted by pathology_tab_info_pipeline for MRN: {request.mrn}")

        # Transform the pathology pipeline results into the format expected by the frontend
        detailed_pathology_reports = []
        genomic_alterations_reports = []
        no_test_performed_reports = []

        # Get the typical pathology reports from the pipeline result
        typical_reports = pathology_result.get('typical_pathology_reports', [])
        for report in typical_reports:
            detailed_pathology_reports.append({
                "drive_url": report.get('drive_url'),
                "drive_file_id": report.get('file_id'),
                "date": report.get('date'),
                "document_type": report.get('document_type'),
                "description": report.get('description', 'Pathology Report'),
                "document_id": report.get('document_id', report.get('date')),
                "pathology_summary": report.get('pathology_summary'),
                "pathology_markers": report.get('pathology_markers')
            })

        # Get genomic pathology reports from pipeline result (handle None)
        genomic_reports = pathology_result.get('genomic_pathology_reports', []) if pathology_result else []
        for report in genomic_reports:
            genomic_alterations_reports.append({
                "drive_url": report.get('drive_url', ''),
                "drive_file_id": report.get('file_id', ''),
                "date": report.get('date'),
                "document_type": report.get('document_type'),
                "description": report.get('description', 'Genomic Alterations Report'),
                "document_id": report.get('document_id', report.get('date')),
                "classification": report.get('classification'),
                "report_type": "GENOMIC_ALTERATIONS"
            })

        # Sort pathology reports by date (most recent first)
        detailed_pathology_reports = sort_reports_by_date(detailed_pathology_reports, descending=True)
        logger.info(f"✅ Sorted {len(detailed_pathology_reports)} pathology reports by date (most recent first)")

        result['pathology_reports'] = detailed_pathology_reports
        result['genomic_alterations_reports'] = genomic_alterations_reports
        result['no_test_performed_reports'] = no_test_performed_reports

        # Log summary
        logger.info(f"📊 Classification Summary:")
        logger.info(f"   - Typical Pathology Reports: {len(detailed_pathology_reports)}")
        logger.info(f"   - Genomic Alterations Reports: {len(genomic_alterations_reports)}")
        logger.info(f"   - No Test Performed Reports: {len(no_test_performed_reports)}")

        # Extract individual radiology reports
        logger.info(f"🧪 Extracting individual radiology reports for MRN: {request.mrn}")
        try:
            radiology_reports = upload_individual_radiology_reports_with_MD_notes_to_drive(
                mrn=request.mrn
            )

            if radiology_reports:
                detailed_radiology_reports = []
                for report in radiology_reports:
                    try:
                        radiology_summary, radiology_imp_RECIST = extract_radiology_details_from_report(
                            radiology_url=report['drive_url_with_MD'],
                            use_gemini_api=True
                        )
                        detailed_radiology_reports.append({
                            "drive_url": report['drive_url'],
                            "drive_url_with_MD": report['drive_url_with_MD'],
                            "drive_file_id": report['drive_file_id'],
                            "drive_file_id_with_MD": report['drive_file_id_with_MD'],
                            "date": report['date'],
                            "document_type": report['document_type'],
                            "description": report['description'],
                            "document_id": report['document_id'],
                            "radiology_summary": radiology_summary,
                            "radiology_imp_RECIST": radiology_imp_RECIST
                        })
                    except Exception as e:
                        detailed_radiology_reports.append({
                            "drive_url": report['drive_url'],
                            "drive_url_with_MD": report['drive_url_with_MD'],
                            "drive_file_id": report['drive_file_id'],
                            "drive_file_id_with_MD": report['drive_file_id_with_MD'],
                            "date": report['date'],
                            "document_type": report['document_type'],
                            "description": report['description'],
                            "document_id": report['document_id'],
                            "radiology_summary": None,
                            "radiology_imp_RECIST": None,
                            "extraction_error": str(e)
                        })

                # Sort radiology reports by date (most recent first)
                detailed_radiology_reports = sort_reports_by_date(detailed_radiology_reports, descending=True)
                logger.info(f"✅ Sorted {len(detailed_radiology_reports)} radiology reports by date (most recent first)")

                result['radiology_reports'] = detailed_radiology_reports
            else:
                result['radiology_reports'] = []
        except Exception as e:
            logger.warning(f"Warning: Failed to extract radiology reports: {str(e)}")
            result['radiology_reports'] = []

        logger.info("="*80)
        logger.info(f"✅ TEST COMPLETE: ALL EXTRACTIONS FINISHED for MRN: {request.mrn}")
        logger.info("="*80)

        # NOTE: We intentionally DO NOT store in data_pool for testing

        return {
            "success": True,
            "mrn": request.mrn,
            "tab_name": "patient_all",
            "workflow_metadata": {
                "pipeline_stages": [
                    "parallel_extraction",
                    "patient_data_pipeline",
                    "lab_results_pipeline",
                    "genomics_pathology_pipeline",
                    "individual_reports_extraction"
                ]
            },
            "extracted_data": result
        }
    except Exception as e:
        logger.error(f"❌ TEST FAILED for MRN {request.mrn}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
