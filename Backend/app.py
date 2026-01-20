"""
FastAPI Application for AI Oncologist Backend

This FastAPI application provides REST API endpoints for:
1. MRN selection and validation
2. Patient constant components (demographics, diagnosis status)
3. Patient tab information (diagnosis, treatment, lab, genomics, pathology, comorbidities)
"""
import sys
import os
from typing import Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import asyncio
from concurrent.futures import ThreadPoolExecutor

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
from Backend.drive_uploader import upload_and_share_pdf_bytes
from Backend.data_pool import get_data_pool
from Backend.Utils.Tabs.pathology_tab import pathology_info
from Backend.Utils.Tabs.radiology_tab import extract_radiology_details_from_report
from Backend.Utils.components.patient_demographics import extract_patient_demographics
from Backend.Utils.components.patient_diagnosis_status import extract_diagnosis_status
from Backend.Utils.Tabs.comorbidities import extract_comorbidities_status
from Backend.Utils.Tabs.treatment_tab import extract_treatment_tab_info
from Backend.Utils.Tabs.diagnosis_tab import diagnosis_extraction
from Backend.Utils.logger_config import setup_logger

# Setup logger
logger = setup_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AI Oncologist API",
    description="API for extracting and managing oncology patient data from EMR",
    version="1.0.0"
)

# Initialize data pool
data_pool = get_data_pool()

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
        if cached_data is not None:
            print(f"Returning cached data for MRN: {request.mrn}")
            return cached_data

        # If not in cache, fetch fresh data IN PARALLEL
        logger.info("="*80)
        logger.info(f"🚀 STARTING PARALLEL EXTRACTION for MRN: {request.mrn}")
        logger.info("="*80)
        logger.info("⚡ Running 3 extraction pipelines in PARALLEL:")
        logger.info("   1️⃣  Patient Data Pipeline (Demographics, Diagnosis, Treatment, etc.)")
        logger.info("   2️⃣  Lab Results Pipeline")
        logger.info("   3️⃣  Genomics & Pathology Pipeline")
        logger.info("="*80)

        # Create a thread pool executor for running sync functions in parallel
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Run all four extraction functions in parallel
            patient_data_future = loop.run_in_executor(
                executor, extract_patient_data, request.mrn, False
            )
            lab_data_future = loop.run_in_executor(
                executor, lab_tab_info, request.mrn, False
            )
            genomics_data_future = loop.run_in_executor(
                executor, genomics_tab_info, request.mrn, False
            )
            pathology_data_future = loop.run_in_executor(
                executor, pathology_tab_info_pipeline, request.mrn, False, True  # use_gemini_api=True
            )

            # Wait for all four to complete
            result, lab_result, genomics_result, pathology_result = await asyncio.gather(
                patient_data_future,
                lab_data_future,
                genomics_data_future,
                pathology_data_future
            )

        logger.info("="*80)
        logger.info(f"✅ ALL PARALLEL EXTRACTIONS COMPLETED for MRN: {request.mrn}")
        logger.info("="*80)

        result['lab_info'] = lab_result.get('lab_info')
        result['genomic_info'] = genomics_result.get('genomic_info')
        result['pathology_summary'] = pathology_result.get('pathology_summary')
        result['pathology_markers'] = pathology_result.get('pathology_markers')

        # Use pathology data already extracted by pathology_tab_info_pipeline (no duplicate extraction)
        print(f"Using pathology reports already extracted by pathology_tab_info_pipeline for MRN: {request.mrn}")

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

        # Get genomic pathology reports from pipeline result
        genomic_reports = pathology_result.get('genomic_pathology_reports', [])
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

        result['pathology_reports'] = detailed_pathology_reports
        result['genomic_alterations_reports'] = genomic_alterations_reports
        result['no_test_performed_reports'] = no_test_performed_reports

        # Log summary
        print(f"📊 Classification Summary:")
        print(f"   - Typical Pathology Reports: {len(detailed_pathology_reports)}")
        print(f"   - Genomic Alterations Reports: {len(genomic_alterations_reports)}")
        print(f"   - No Test Performed Reports: {len(no_test_performed_reports)}")

        # Extract individual radiology reports with details (during initial load)
        print(f"Extracting individual radiology reports for MRN: {request.mrn}")
        try:
            radiology_reports = upload_individual_radiology_reports_with_MD_notes_to_drive(
                mrn=request.mrn
            )

            if radiology_reports:
                # Extract radiology details for each report
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
                        # If extraction fails for a report, include error but continue
                        print(f"Warning: Failed to extract radiology details for {report['document_id']}: {str(e)}")
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

                result['radiology_reports'] = detailed_radiology_reports
            else:
                result['radiology_reports'] = []
        except Exception as e:
            # If radiology extraction completely fails, continue with other data
            print(f"Warning: Failed to extract radiology reports: {str(e)}")
            result['radiology_reports'] = []

        # Auto-store in data pool
        data_pool.store_patient_data(mrn=request.mrn, data=result)

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
        logger.info(f"🧪 STARTING TEST: PARALLEL EXTRACTION for MRN: {request.mrn}")
        logger.info("="*80)

        # Run the same parallel extraction as production, but skip cache check
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=4) as executor:
            patient_data_future = loop.run_in_executor(
                executor, extract_patient_data, request.mrn, False
            )
            lab_data_future = loop.run_in_executor(
                executor, lab_tab_info, request.mrn, False
            )
            genomics_data_future = loop.run_in_executor(
                executor, genomics_tab_info, request.mrn, False
            )
            pathology_data_future = loop.run_in_executor(
                executor, pathology_tab_info_pipeline, request.mrn, False, True  # use_gemini_api=True
            )

            result, lab_result, genomics_result, pathology_result = await asyncio.gather(
                patient_data_future,
                lab_data_future,
                genomics_data_future,
                pathology_data_future
            )

        # Combine results
        result['lab_info'] = lab_result.get('lab_info')
        result['genomic_info'] = genomics_result.get('genomic_info')
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

        # Get genomic pathology reports from pipeline result
        genomic_reports = pathology_result.get('genomic_pathology_reports', [])
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
