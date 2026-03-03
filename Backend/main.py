"""
Main Pipeline Script

Complete patient data extraction from MRN:
1. Fetch MD note from FHIR API
2. Upload to Google Drive (no local files)
3. Extract demographics and diagnosis status

"""
import sys
import os
import json
import requests
import base64
from io import BytesIO
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None
    print("Warning: PyPDF2 not found. Report merging will be disabled.")


# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
sys.path.append(PROJECT_ROOT)

from Backend.bytes_extractor import (
    get_document_bytes,
    LOINC_CODES,
    extract_report_with_MD as get_pathology_reports_urls,
    fetch_and_combine_pdfs_from_urls,
    fetch_pdf_bytes_from_fhir_url,
    combine_pdf_bytes_and_upload
)
from Backend.documents_reference import generate_bearer_token, generate_onco_emr_token
from Backend.drive_uploader import upload_and_share_pdf_bytes
from Backend.Utils.components.patient_demographics import extract_patient_demographics
from Backend.Utils.components.patient_diagnosis_status import extract_diagnosis_status
from Backend.Utils.Tabs.comorbidities import extract_comorbidities_status
from Backend.Utils.Tabs.treatment_tab import extract_treatment_tab_info
from Backend.Utils.Tabs.genomics_tab import extract_genomic_info
from Backend.Utils.Tabs.diagnosis_tab import diagnosis_extraction
from Backend.Utils.Tabs.pathology_tab import pathology_info, classify_pathology_report_with_gemini
from Backend.Utils.logger_config import setup_logger

# Setup logger
logger = setup_logger(__name__)



def extract_patient_data(mrn: str, verbose: bool = True):
    """
    Extract patient demographics, diagnosis status, and comorbidities from MRN.

    Args:
        mrn (str): Patient's Medical Record Number
        verbose (bool): Print progress messages (default: True)

    Returns:
        dict: Contains demographics, diagnosis, comorbidities, and metadata
        {
            'success': bool,
            'mrn': str,
            'pdf_url': str,
            'demographics': dict,
            'diagnosis': dict,
            'comorbidities': dict,
            'error': str (if failed)
        }
    """
    result = {
        'success': False,
        'mrn': mrn,
        'pdf_url': None,
        'demographics': None,
        'diagnosis': None,
        'comorbidities': None,
        'error': None
    }

    try:
        if verbose:
            print("="*70)
            print("  PATIENT DATA EXTRACTION PIPELINE")
            print("="*70)
            print(f"\nMRN: {mrn}")

        # Step 1: Fetch MD note PDF bytes from FHIR API
        if verbose:
            print("\n[1/6] Fetching MD note from FHIR API...")

        # These patterns now match against resource.type.text field in FHIR bundle
        # Examples: "MD Visit", "Physician Note", "Progress Note", etc.
        document_type_patterns = [
            r'\bMD\b.*\bvisit\b',
            r'\bMD\b.*\bnote\b',
            r'\bphysician\b.*\bvisit\b',
            r'\bphysician\b.*\bnote\b',
            r'\bprogress\b.*\bnote\b'
        ]

        pdf_bytes = get_document_bytes(
            mrn=mrn,
            # loinc_code=LOINC_CODES["progress_notes"],  # Optional: can be None
            description_patterns=document_type_patterns
        )

        if not pdf_bytes:
            raise ValueError(f"No MD notes found for MRN: {mrn}")

        if verbose:
            print(f"      ✓ Retrieved {len(pdf_bytes):,} bytes ({len(pdf_bytes)/1024:.1f} KB)")

        # Step 2: Upload to Google Drive
        if verbose:
            print("\n[2/6] Uploading to Google Drive...")

        upload_result = upload_and_share_pdf_bytes(
            pdf_bytes=pdf_bytes,
            file_name=f"MD_note_{mrn}.pdf"
        )

        result['pdf_url'] = upload_result['shareable_url']

        if verbose:
            print(f"      ✓ URL: {result['pdf_url']}")

        # Step 3-7: Extract all tab information in parallel
        if verbose:
            print("\n[3/6] Extracting all tab information in parallel...")
            print("      🔄 Running 5 extraction tasks concurrently...")

        # Define extraction tasks
        def extract_demographics_task():
            try:
                return ('demographics', extract_patient_demographics(pdf_url=result['pdf_url']), None)
            except Exception as e:
                return ('demographics', None, str(e))

        def extract_diagnosis_status_task():
            try:
                return ('diagnosis', extract_diagnosis_status(pdf_url=result['pdf_url']), None)
            except Exception as e:
                return ('diagnosis', None, str(e))

        def extract_comorbidities_task():
            try:
                return ('comorbidities', extract_comorbidities_status(pdf_url=result['pdf_url']), None)
            except Exception as e:
                return ('comorbidities', None, str(e))

        def extract_treatment_task():
            try:
                lot, timeline = extract_treatment_tab_info(pdf_url=result['pdf_url'])
                return ('treatment', {'lot': lot, 'timeline': timeline}, None)
            except Exception as e:
                return ('treatment', None, str(e))

        def extract_diagnosis_tab_task():
            try:
                header, timeline, footer = diagnosis_extraction(pdf_input=result['pdf_url'])
                return ('diagnosis_tab', {'header': header, 'timeline': timeline, 'footer': footer}, None)
            except Exception as e:
                return ('diagnosis_tab', None, str(e))

        # Execute all tasks in parallel
        tasks = [
            extract_demographics_task,
            extract_diagnosis_status_task,
            extract_comorbidities_task,
            extract_treatment_task,
            extract_diagnosis_tab_task
        ]

        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all tasks
            future_to_task = {executor.submit(task): task.__name__ for task in tasks}

            # Collect results as they complete
            for future in as_completed(future_to_task):
                task_name = future_to_task[future]
                try:
                    data_type, data, error = future.result()

                    if error:
                        if verbose:
                            print(f"      ⚠️  {data_type} extraction failed: {error}")
                        result[f'{data_type}_error'] = error
                    else:
                        # Handle different data types
                        if data_type == 'treatment':
                            result['treatment_tab_info_LOT'] = data['lot']
                            result['treatment_tab_info_timeline'] = data['timeline']
                            if verbose:
                                print(f"      ✓ Treatment tab extracted ({len(data['lot'])} LOT, {len(data['timeline'])} timeline)")
                        elif data_type == 'diagnosis_tab':
                            result['diagnosis_header'] = data['header']
                            result['diagnosis_evolution_timeline'] = data['timeline']
                            result['diagnosis_footer'] = data['footer']
                            if verbose:
                                print(f"      ✓ Diagnosis tab extracted ({len(data['header'])} header, {len(data['timeline'])} timeline, {len(data['footer'])} footer)")
                        else:
                            result[data_type] = data
                            if verbose:
                                print(f"      ✓ {data_type.capitalize()} extracted ({len(data)} fields)")

                except Exception as e:
                    if verbose:
                        print(f"      ⚠️  Task {task_name} failed: {str(e)}")

        result['success'] = True

        if verbose:
            print("\n" + "="*70)
            print("  EXTRACTION COMPLETE")
            print("="*70)

        return result

    except Exception as e:
        result['error'] = str(e)
        if verbose:
            print(f"\n{'='*70}")
            print(f"ERROR: {str(e)}")
            print(f"{'='*70}")
        return result

def lab_tab_info(mrn: str, verbose: bool = True):
    """
    Extract lab results for a patient using Gemini individual processing via REST API.

    Workflow:
    1. Fetches all lab result documents from the last 6 months from FHIR
    2. For each report:
       - Passes PDF bytes directly to Gemini REST API (no file downloads)
       - Extracts current values: most recent measurement with unit, date, status, reference range
       - Extracts trends: historical data points from that specific report
    3. Consolidates all individual results into UI-ready format
    4. Merges trend data from all reports for each biomarker

    Biomarkers extracted:
    - Tumor markers: CEA, NSE, proGRP, CYFRA 21-1
    - Complete blood count: WBC, Hemoglobin, Platelets, ANC
    - Metabolic panel: Creatinine, ALT, AST, Total Bilirubin

    Args:
        mrn (str): Patient's Medical Record Number
        verbose (bool): Print progress messages (default: True)

    Returns:
        dict: Contains success status and consolidated lab data
        {
            'success': bool,
            'mrn': str,
            'lab_results_count': int,
            'processed_documents': int,
            'lab_info': dict,  # Consolidated lab data in UI-ready format
            'lab_reports': list,  # List of lab document URLs with metadata
            'metadata': dict,  # Processing metadata
            'validation_summary': dict,  # Validation statistics
            'error': str (if failed)
        }
    """
    from Backend.Utils.Tabs.lab_pipeline_comparison import process_individual_lab_results_gemini

    result = {
        'success': False,
        'mrn': mrn,
        'lab_results_count': 0,
        'processed_documents': 0,
        'lab_info': None,
        'lab_reports': [],
        'metadata': None,
        'error': None
    }

    try:
        if verbose:
            print("="*70)
            print("  LAB EXTRACTION WITH GEMINI (INDIVIDUAL PROCESSING)")
            print("="*70)
            print(f"\nMRN: {mrn}")
            print("\nWorkflow:")
            print("  1. Fetch each individual lab report as bytes from FHIR")
            print("  2. Pass bytes directly to Gemini (no file downloads)")
            print("  3. Extract data from each report using Gemini")
            print("  4. Consolidate all results")
            print("")

        # Process all lab results individually with Gemini
        processing_result = process_individual_lab_results_gemini(mrn, verbose=verbose)

        # Extract results
        result['lab_results_count'] = processing_result['metadata']['total_documents']
        result['processed_documents'] = processing_result['metadata']['processed_documents']
        result['lab_info'] = processing_result['combined_data']
        result['metadata'] = processing_result['metadata']

        # Include FHIR metadata
        if 'fhir_metadata' in processing_result:
            result['fhir_metadata'] = processing_result['fhir_metadata']
            # Add summary counts for clarity
            fhir_meta = processing_result['fhir_metadata']
            if fhir_meta.get('fhir_integration_successful'):
                result['total_data_sources'] = result['lab_results_count'] + 1  # PDFs + FHIR
                result['fhir_observations_count'] = fhir_meta.get('fhir_observations_fetched', 0)

        # Format lab documents for Documents tab
        if 'lab_documents' in processing_result and processing_result['lab_documents']:
            result['lab_reports'] = [
                {
                    'url': doc.get('url'),  # FHIR URL (will need Drive upload for user access)
                    'date': doc.get('date'),
                    'document_type': 'Lab Results',
                    'description': doc.get('description', 'Lab Results'),
                    'document_id': doc.get('document_id')
                }
                for doc in processing_result['lab_documents']
            ]

        # Include validation summary
        if 'validation_summary' in processing_result:
            result['validation_summary'] = processing_result['validation_summary']

        # Check if we successfully extracted any data
        if result['lab_info']:
            result['success'] = True

            if verbose:
                print("\n" + "="*70)
                print("  LAB EXTRACTION COMPLETE")
                print("="*70)
                print(f"Total Lab Documents (PDFs): {result['lab_results_count']}")
                print(f"Successfully Processed: {result['processed_documents']}")
                if 'fhir_metadata' in result:
                    fhir_meta = result['fhir_metadata']
                    if fhir_meta.get('fhir_integration_successful'):
                        print(f"FHIR Observations Fetched: {fhir_meta.get('fhir_observations_fetched', 0)}")
                        print(f"FHIR Biomarkers Converted: {fhir_meta.get('fhir_observations_converted', 0)}")
                        print(f"Total Data Sources: {result.get('total_data_sources', result['lab_results_count'])}")
                    else:
                        print("FHIR Integration: Not available")
                if 'validation_summary' in result:
                    val_sum = result['validation_summary']
                    print(f"Validation: {val_sum['total_passed']}/{val_sum['total_validated']} passed")
                print("="*70)
        else:
            result['success'] = False
            result['error'] = "No lab data could be extracted"

            if verbose:
                print("\n" + "="*70)
                print("  WARNING: No lab data extracted")
                print("="*70)

        return result

    except Exception as e:
        result['error'] = str(e)
        if verbose:
            print(f"\n{'='*70}")
            print(f"ERROR: {str(e)}")
            print(f"{'='*70}")
        return result


def genomics_tab_info(mrn: str, verbose: bool = True):
    """
    Extract genomic alterations data from molecular results and pathology reports containing genomic/molecular profiling.

    Pipeline:
    - First fetches "Molecular Results" documents (automatically included as genomic)
    - Uses AI classification to identify pathology reports containing genomic alterations
    - ONLY includes pathology reports classified as GENOMIC_ALTERATIONS (NGS panels, molecular profiling)
    - ALWAYS includes MD notes for clinical context
    - Filters out typical pathology reports (histological examinations without genomic data)

    Workflow:
    1. Fetches "Molecular Results" documents (auto-included as genomic)
    2. Fetches pathology report documents and MD notes from the last 6 months
    3. Classifies each pathology report to identify genomic alterations
    4. Filters to keep only genomic reports (molecular + genomic pathology) and MD notes
    5. Combines filtered documents into a single PDF
    6. Uploads to Google Drive
    7. Extracts genomic information from the filtered combined PDF

    Args:
        mrn (str): Patient's Medical Record Number
        verbose (bool): Print progress messages (default: True)

    Returns:
        dict: Contains success status, file info, and genomic data
        {
            'success': bool,
            'mrn': str,
            'molecular_results_count': int,  # Molecular Results documents found
            'pathology_reports_count': int,  # Total pathology reports found
            'genomic_pathology_reports_count': int,  # Reports with genomic alterations
            'typical_pathology_reports_count': int,  # Reports excluded (typical pathology)
            'md_notes_count': int,  # Number of MD notes included
            'total_documents_count': int,  # Total documents used (molecular + genomic path + MD notes)
            'pdf_url': str,
            'file_id': str,
            'molecular_results_documents': list,  # Molecular Results documents
            'pathology_documents': list,  # All pathology report documents
            'genomic_pathology_documents': list,  # Pathology reports with genomic alterations
            'typical_pathology_documents': list,  # Typical pathology reports (excluded)
            'md_notes_documents': list,  # MD notes documents
            'classification_results': list,  # Classification details for each report
            'genomic_info': dict,  # Extracted genomic information
            'error': str (if failed)
        }
    """
    result = {
        'success': False,
        'mrn': mrn,
        'molecular_results_count': 0,
        'pathology_reports_count': 0,
        'md_notes_count': 0,
        'total_documents_count': 0,
        'pdf_url': None,
        'file_id': None,
        'molecular_results_documents': None,
        'pathology_documents': None,
        'md_notes_documents': None,
        'error': None
    }

    try:
        if verbose:
            print("="*70)
            print("  GENOMICS TAB DATA EXTRACTION PIPELINE")
            print("="*70)
            print(f"\nMRN: {mrn}")

        # Step 1: Fetch "Molecular Results" documents (automatically genomic)
        if verbose:
            print("\n[1/5] Fetching Molecular Results documents from FHIR API...")

        molecular_results_docs = get_pathology_reports_urls(mrn=mrn, report_type="molecular", include_md_notes=False)

        if verbose:
            if molecular_results_docs:
                print(f"      ✓ Found {len(molecular_results_docs)} Molecular Results documents")
                for doc in molecular_results_docs:
                    print(f"         - {doc['date']}: {doc.get('description', 'Molecular Results')}")
            else:
                print(f"      ℹ️  No Molecular Results documents found")

        # Step 2: Get pathology report URLs (INCLUDING MD notes)
        if verbose:
            print("\n[2/5] Fetching pathology reports and MD notes from FHIR API...")

        all_documents = get_pathology_reports_urls(mrn=mrn, include_md_notes=True)

        if not all_documents and not molecular_results_docs:
            raise ValueError(f"No molecular results, pathology reports, or MD notes found for MRN: {mrn}")

        if verbose:
            print(f"      ✓ Found {len(all_documents)} pathology/MD documents")

        # Step 3: Classify and filter pathology reports for genomic extraction
        if verbose:
            print("\n[3/5] Classifying pathology reports to identify genomic alterations...")

        # Authenticate once for all document fetches
        bearer_token = generate_bearer_token()
        onco_emr_token = generate_onco_emr_token(bearer_token)

        pathology_docs = []
        genomic_pathology_docs = []
        typical_pathology_docs = []
        md_notes_docs = []
        classification_results = []

        # Cache PDF bytes to avoid redundant downloads
        pdf_bytes_cache = {}  # {doc_url: pdf_bytes}

        # Fetch and cache PDF bytes for Molecular Results (no classification needed)
        if molecular_results_docs:
            if verbose:
                print(f"\n      Fetching PDF bytes for {len(molecular_results_docs)} Molecular Results documents...")

            for doc in molecular_results_docs:
                try:
                    pdf_bytes = fetch_pdf_bytes_from_fhir_url(doc['url'], bearer_token, onco_emr_token)
                    if pdf_bytes:
                        pdf_bytes_cache[doc['url']] = pdf_bytes
                        if verbose:
                            print(f"         ✓ Cached: {doc['date']}: {doc.get('description', 'Molecular Results')}")
                except Exception as e:
                    if verbose:
                        print(f"         ⚠️  Failed to fetch: {str(e)}")

        for doc in all_documents:
            description = doc.get('description', '').lower()
            doc_type = doc.get('document_type', '').lower()

            # Check if it's an MD note
            is_md_note = ('md' in doc_type or 'physician' in doc_type or
                         'progress' in doc_type or 'visit' in doc_type)

            if is_md_note:
                # Fetch and cache MD note PDF bytes
                try:
                    pdf_bytes = fetch_pdf_bytes_from_fhir_url(doc['url'], bearer_token, onco_emr_token)
                    if pdf_bytes:
                        pdf_bytes_cache[doc['url']] = pdf_bytes
                        md_notes_docs.append(doc)
                        if verbose:
                            print(f"      ✓ MD Note identified and cached: {doc['date']}: {doc.get('description', 'Report')}")
                except Exception as e:
                    if verbose:
                        print(f"      ⚠️  Failed to fetch MD note: {str(e)}")
                    continue
            else:
                # It's a pathology report - classify it
                pathology_docs.append(doc)

                if verbose:
                    print(f"      Classifying pathology report: {doc['date']}: {doc.get('description', 'Report')}")

                try:
                    # Fetch PDF bytes for classification AND cache them
                    pdf_bytes = fetch_pdf_bytes_from_fhir_url(doc['url'], bearer_token, onco_emr_token)

                    if pdf_bytes:
                        # Cache the bytes to avoid re-downloading
                        pdf_bytes_cache[doc['url']] = pdf_bytes

                        # Classify the report
                        classification = classify_pathology_report_with_gemini(pdf_bytes)
                        doc['classification'] = classification
                        classification_results.append({
                            'document': doc,
                            'classification': classification
                        })

                        if classification['category'] == 'GENOMIC_ALTERATIONS':
                            genomic_pathology_docs.append(doc)
                            if verbose:
                                print(f"         ✓ GENOMIC ALTERATIONS detected (confidence: {classification['confidence']})")
                                print(f"           Reasoning: {classification['reasoning']}")
                        else:
                            typical_pathology_docs.append(doc)
                            if verbose:
                                print(f"         ℹ️  TYPICAL PATHOLOGY (will be processed by pathology tab)")
                    else:
                        if verbose:
                            print(f"         ⚠️  Could not fetch PDF bytes, skipping classification")

                except Exception as e:
                    if verbose:
                        print(f"         ⚠️  Classification failed: {str(e)}, including by default")
                    # If classification fails, include it by default to be safe
                    genomic_pathology_docs.append(doc)

        # Use Molecular Results + Genomic Pathology Reports + MD Notes for genomic extraction
        all_documents_for_genomics = molecular_results_docs + genomic_pathology_docs + md_notes_docs

        if not all_documents_for_genomics:
            raise ValueError(f"No molecular results, genomic pathology reports, or MD notes found for MRN: {mrn}")

        result['molecular_results_documents'] = molecular_results_docs
        result['pathology_documents'] = pathology_docs
        result['genomic_pathology_documents'] = genomic_pathology_docs
        result['typical_pathology_documents'] = typical_pathology_docs
        result['md_notes_documents'] = md_notes_docs
        result['classification_results'] = classification_results
        result['molecular_results_count'] = len(molecular_results_docs)
        result['pathology_reports_count'] = len(pathology_docs)
        result['genomic_pathology_reports_count'] = len(genomic_pathology_docs)
        result['typical_pathology_reports_count'] = len(typical_pathology_docs)
        result['md_notes_count'] = len(md_notes_docs)
        result['total_documents_count'] = len(all_documents_for_genomics)

        if verbose:
            print(f"\n      ✓ Classification Complete:")
            print(f"         - Molecular Results: {len(molecular_results_docs)}")
            print(f"         - Total Pathology Reports: {len(pathology_docs)}")
            print(f"         - Genomic Alterations Reports: {len(genomic_pathology_docs)}")
            print(f"         - Typical Pathology Reports (for pathology tab): {len(typical_pathology_docs)}")
            print(f"         - MD Notes: {len(md_notes_docs)}")
            print(f"\n      Documents selected for genomic extraction ({len(all_documents_for_genomics)} total):")
            for idx, doc in enumerate(all_documents_for_genomics, 1):
                if doc in molecular_results_docs:
                    doc_type_label = "MOLECULAR RESULTS"
                elif doc in md_notes_docs:
                    doc_type_label = "MD NOTE"
                else:
                    doc_type_label = "GENOMIC PATH"
                print(f"        {idx}. [{doc_type_label}] {doc['date']}: {doc.get('description', 'Report')}")

        # Step 4: Combine cached PDF bytes and upload to Drive
        if verbose:
            print(f"\n[4/5] Combining {len(all_documents_for_genomics)} filtered documents from cached bytes...")

        # Collect cached bytes for selected documents
        cached_pdf_bytes_list = []
        for doc in all_documents_for_genomics:
            if doc['url'] in pdf_bytes_cache:
                cached_pdf_bytes_list.append(pdf_bytes_cache[doc['url']])
            else:
                if verbose:
                    print(f"      ⚠️  Warning: PDF bytes not cached for {doc.get('description', 'document')}, fetching...")
                # Fallback: fetch if not cached (shouldn't happen)
                try:
                    pdf_bytes = fetch_pdf_bytes_from_fhir_url(doc['url'], bearer_token, onco_emr_token)
                    if pdf_bytes:
                        cached_pdf_bytes_list.append(pdf_bytes)
                except Exception as e:
                    if verbose:
                        print(f"      ⚠️  Failed to fetch: {str(e)}")

        if not cached_pdf_bytes_list:
            raise ValueError("No PDF bytes available for combining")

        # Use optimized function that returns both URL and bytes
        upload_result = combine_pdf_bytes_and_upload(
            pdf_bytes_list=cached_pdf_bytes_list,
            output_file_name=f"Genomics_Combined_{mrn}.pdf"
        )

        result['pdf_url'] = upload_result['shareable_url']
        result['file_id'] = upload_result['file_id']
        # Store bytes temporarily for extraction only (not for API response)
        combined_pdf_bytes = upload_result['combined_pdf_bytes']
        result['success'] = True

        if verbose:
            print("\n" + "="*70)
            print("  GENOMICS DATA EXTRACTION READY")
            print("="*70)
            print(f"Combined PDF URL: {result['pdf_url']}")
            print(f"Total documents used for genomic extraction: {result['total_documents_count']}")
            print(f"   - Molecular Results: {len(molecular_results_docs)}")
            print(f"   - Genomic Pathology Reports: {len(genomic_pathology_docs)}")
            print(f"   - MD Notes: {len(md_notes_docs)}")
            print(f"   - Typical Pathology Reports (excluded, for pathology tab): {len(typical_pathology_docs)}")
            print("="*70)

        # Step 5: Extract genomic information using cached bytes (no download needed!)
        if verbose:
            print(f"\n[5/5] Extracting genomic information from combined PDF bytes...")

        # Pass bytes directly instead of URL to avoid re-downloading
        result['genomic_info'] = extract_genomic_info(pdf_input=combined_pdf_bytes)

        # Format genomics documents for Documents tab (molecular results + genomic pathology reports, not MD notes)
        genomic_documents_for_tab = []

        # Add molecular results
        for doc in molecular_results_docs:
            genomic_documents_for_tab.append({
                'url': doc.get('url'),  # FHIR URL
                'date': doc.get('date'),
                'document_type': 'Molecular Results',
                'description': doc.get('description', 'Molecular Results'),
                'document_id': doc.get('document_id')
            })

        # Add genomic pathology reports
        for doc in genomic_pathology_docs:
            genomic_documents_for_tab.append({
                'url': doc.get('url'),  # FHIR URL
                'date': doc.get('date'),
                'document_type': 'Genomic Report',
                'description': doc.get('description', 'Genomic Pathology Report'),
                'document_id': doc.get('document_id')
            })

        result['genomics_reports'] = genomic_documents_for_tab

        if verbose:
            print("\n" + "="*70)
            print("  GENOMICS TAB EXTRACTION COMPLETE")
            print("="*70)

        return result

    except Exception as e:
        result['error'] = str(e)
        if verbose:
            print(f"\n{'='*70}")
            print(f"ERROR: {str(e)}")
            print(f"{'='*70}")
        return result


def pathology_tab_info_pipeline(mrn: str, verbose: bool = True, use_gemini_api: bool = True):
    """
    Extract pathology data from typical pathology reports (histological examinations).

    Pipeline:
    - Uses AI classification to identify typical pathology reports
    - ONLY processes reports classified as TYPICAL_PATHOLOGY
    - EXCLUDES genomic alterations reports (those are handled by genomics tab)
    - Extracts pathology summary and markers from typical pathology reports

    Workflow:
    1. Fetches all pathology report documents from FHIR
    2. Classifies each pathology report
    3. Filters to keep only typical pathology reports
    4. Processes each typical pathology report individually
    5. Uploads to Google Drive
    6. Extracts pathology summary and markers

    Args:
        mrn (str): Patient's Medical Record Number
        verbose (bool): Print progress messages (default: True)
        use_gemini_api (bool): Use Gemini API for extraction (default: True)

    Returns:
        dict: Contains success status and pathology data
        {
            'success': bool,
            'mrn': str,
            'pathology_reports_count': int,  # Total pathology reports found
            'typical_pathology_reports_count': int,  # Reports with typical pathology
            'genomic_pathology_reports_count': int,  # Reports excluded (genomic alterations)
            'typical_pathology_reports': list,  # Individual typical pathology reports with data
            'genomic_pathology_reports': list,  # Genomic reports (excluded)
            'classification_results': list,  # Classification details for each report
            'pathology_summary': dict,  # Pathology summary from most recent typical report
            'pathology_markers': dict,  # Pathology markers from most recent typical report
            'error': str (if failed)
        }
    """
    result = {
        'success': False,
        'mrn': mrn,
        'pathology_reports_count': 0,
        'typical_pathology_reports_count': 0,
        'genomic_pathology_reports_count': 0,
        'typical_pathology_reports': [],
        'genomic_pathology_reports': [],
        'classification_results': [],
        'pathology_summary': None,
        'pathology_markers': None,
        'error': None
    }

    try:
        if verbose:
            print("="*70)
            print("  PATHOLOGY TAB DATA EXTRACTION PIPELINE")
            print("="*70)
            print(f"\nMRN: {mrn}")

        # Step 1: Get pathology report URLs (NO MD notes)
        if verbose:
            print("\n[1/3] Fetching pathology reports from FHIR API...")

        all_documents = get_pathology_reports_urls(mrn=mrn, include_md_notes=False)

        if not all_documents:
            raise ValueError(f"No pathology reports found for MRN: {mrn}")

        if verbose:
            print(f"      ✓ Found {len(all_documents)} pathology reports")

        # Step 2: Classify and filter pathology reports
        if verbose:
            print("\n[2/3] Classifying pathology reports...")

        # Authenticate once for all document fetches
        bearer_token = generate_bearer_token()
        onco_emr_token = generate_onco_emr_token(bearer_token)

        typical_pathology_docs = []
        genomic_pathology_docs = []
        classification_results = []

        for doc in all_documents:
            if verbose:
                print(f"      Classifying: {doc['date']}: {doc.get('description', 'Report')}")

            try:
                # Fetch PDF bytes for classification
                pdf_bytes = fetch_pdf_bytes_from_fhir_url(doc['url'], bearer_token, onco_emr_token)

                if pdf_bytes:
                    # Classify the report
                    classification = classify_pathology_report_with_gemini(pdf_bytes)
                    doc['classification'] = classification
                    doc['pdf_bytes'] = pdf_bytes  # Store temporarily for processing

                    # Add to classification results WITHOUT pdf_bytes
                    classification_results.append({
                        'document': {k: v for k, v in doc.items() if k != 'pdf_bytes'},
                        'classification': classification
                    })

                    if classification['category'] == 'TYPICAL_PATHOLOGY':
                        typical_pathology_docs.append(doc)
                        if verbose:
                            print(f"         ✓ TYPICAL PATHOLOGY detected (confidence: {classification['confidence']})")
                            print(f"           Reasoning: {classification['reasoning']}")
                    else:
                        genomic_pathology_docs.append(doc)
                        if verbose:
                            print(f"         ℹ️  GENOMIC ALTERATIONS (will be processed by genomics tab)")
                else:
                    if verbose:
                        print(f"         ⚠️  Could not fetch PDF bytes, skipping")

            except Exception as e:
                if verbose:
                    print(f"         ⚠️  Classification failed: {str(e)}, skipping")

        if not typical_pathology_docs:
            result['pathology_reports_count'] = len(all_documents)
            result['typical_pathology_reports_count'] = 0
            result['genomic_pathology_reports_count'] = len(genomic_pathology_docs)
            result['classification_results'] = classification_results
            result['success'] = True
            if verbose:
                print("\n      ⚠️  No typical pathology reports found (all reports are genomic alterations)")
            return result

        result['pathology_reports_count'] = len(all_documents)
        result['typical_pathology_reports_count'] = len(typical_pathology_docs)
        result['genomic_pathology_reports_count'] = len(genomic_pathology_docs)
        result['classification_results'] = classification_results

        if verbose:
            print(f"\n      ✓ Classification Complete:")
            print(f"         - Total Pathology Reports: {len(all_documents)}")
            print(f"         - Typical Pathology Reports: {len(typical_pathology_docs)}")
            print(f"         - Genomic Alterations Reports (excluded): {len(genomic_pathology_docs)}")

        # Step 3: Process typical pathology reports
        if verbose:
            print(f"\n[3/3] Processing {len(typical_pathology_docs)} typical pathology reports...")

        # Upload each typical pathology report to Drive and extract data
        for idx, doc in enumerate(typical_pathology_docs, 1):
            try:
                if verbose:
                    print(f"\n      Processing report {idx}/{len(typical_pathology_docs)}: {doc['date']}")

                # Upload to Google Drive (use pdf_bytes then remove from doc)
                pdf_bytes_for_upload = doc.pop('pdf_bytes')  # Remove bytes from doc immediately after use
                upload_result = upload_and_share_pdf_bytes(
                    pdf_bytes=pdf_bytes_for_upload,
                    file_name=f"Pathology_{mrn}_{doc['date']}.pdf"
                )
                doc['drive_url'] = upload_result['shareable_url']
                doc['file_id'] = upload_result['file_id']

                if verbose:
                    print(f"         ✓ Uploaded to Drive")

                # Extract pathology information
                if verbose:
                    print(f"         Extracting pathology data...")

                pathology_summary, pathology_markers = pathology_info(
                    pdf_url=doc['drive_url'],
                    use_gemini_api=use_gemini_api
                )

                doc['pathology_summary'] = pathology_summary
                doc['pathology_markers'] = pathology_markers

                result['typical_pathology_reports'].append(doc)

                if verbose:
                    print(f"         ✓ Extraction complete")

            except Exception as e:
                if verbose:
                    print(f"         ⚠️  Processing failed: {str(e)}")
                doc['error'] = str(e)
                result['typical_pathology_reports'].append(doc)

        # Set the most recent typical pathology report as the primary result
        if result['typical_pathology_reports']:
            most_recent = result['typical_pathology_reports'][0]  # Already sorted by date
            result['pathology_summary'] = most_recent.get('pathology_summary')
            result['pathology_markers'] = most_recent.get('pathology_markers')

        result['success'] = True

        if verbose:
            print("\n" + "="*70)
            print("  PATHOLOGY TAB EXTRACTION COMPLETE")
            print("="*70)
            print(f"Total Typical Pathology Reports Processed: {len(result['typical_pathology_reports'])}")
            print("="*70)

        return result

    except Exception as e:
        result['error'] = str(e)
        if verbose:
            print(f"\n{'='*70}")
            print(f"ERROR: {str(e)}")
            print(f"{'='*70}")
        return result

def main():
    """Main execution with example usage."""
    # Example MRN
    mrn = "A2451440"

    # Extract patient data
    result = extract_patient_data(mrn, verbose=True)

    if result['success']:
        # Display Demographics
        print("\n" + "="*70)
        print("  DEMOGRAPHICS")
        print("="*70)
        print(json.dumps(result['demographics'], indent=2))

        # Display Diagnosis
        print("\n" + "="*70)
        print("  DIAGNOSIS STATUS")
        print("="*70)
        print(json.dumps(result['diagnosis'], indent=2))

        # Display Comorbidities
        print("\n" + "="*70)
        print("  COMORBIDITIES & FUNCTIONAL STATUS")
        print("="*70)
        print(json.dumps(result['comorbidities'], indent=2))

        #Display Treatment Tab info
        print("\n" + "="*70)
        print("  TREATMENT TAB INFORMATION")
        print("="*70)
        print(json.dumps(result['treatment_tab_info_LOT'], indent=2))
        print(json.dumps(result['treatment_tab_info_timeline'], indent=2))

        #Display Diagnosis Tab info
        print("\n" + "="*70)
        print("  Diagnosis TAB INFORMATION")
        print("="*70)
        print(json.dumps(result['diagnosis_header'], indent=2))
        print(json.dumps(result['diagnosis_evolution_timeline'], indent=2))
        print(json.dumps(result['diagnosis_footer'], indent=2))
        
        # Extract and combine lab results
        print("\n")
        lab_result = lab_tab_info(mrn, verbose=True)

        if lab_result['success']:
            print("\n" + "="*70)
            print("  LAB RESULTS TAB INFORMATION")
            print("="*70)
            print(json.dumps(lab_result['lab_info'], indent=2))
        else:
            print(f"\nLab results extraction failed: {lab_result['error']}")

        # Extract genomics tab info
        genomics_result = genomics_tab_info(mrn, verbose=True)

        if genomics_result['success']:
            print("\n" + "="*70)
            print("  GENOMICS TAB INFORMATION")
            print("="*70)
            print(json.dumps(genomics_result['genomic_info'], indent=2))
        else:
            print(f"\nGenomics results extraction failed: {genomics_result['error']}")

        # Extract pathology tab info
        pathology_result = pathology_tab_info_pipeline(mrn, verbose=True, use_gemini_api=True)

        if pathology_result['success']:
            print("\n" + "="*70)
            print("  PATHOLOGY TAB INFORMATION")
            print("="*70)
            print(json.dumps(pathology_result['pathology_summary'], indent=2))
            print(json.dumps(pathology_result['pathology_markers'], indent=2))
        else:
            print(f"\nPathology results extraction failed: {pathology_result['error']}")

        # Summary
        print("\n" + "="*70)
        print("  SUMMARY")
        print("="*70)
        print(f"Patient: {result['demographics'].get('Patient Name', 'N/A')}")
        print(f"MRN: {result['mrn']}")
        print(f"Cancer Type: {result['diagnosis'].get('cancer_type', 'N/A')}")
        print(f"Disease Status: {result['diagnosis'].get('disease_status', 'N/A')}")

        print(f"\nMain MD Note URL: {result['pdf_url']}")
        print(f"\nReport URL for Lab Tab: {lab_result.get('pdf_url', 'N/A')}")
        print(f"\nReport URL for Genomic Tab: {genomics_result.get('pdf_url', 'N/A')}")

    else:
        print(f"\nExtraction failed: {result['error']}")
        sys.exit(1)


    

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nFATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)