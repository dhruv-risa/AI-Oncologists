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
    extract_lab_results_data_md_notes_combined as get_lab_results_urls,
    extract_report_with_MD as get_pathology_reports_urls,
    fetch_and_combine_pdfs_from_urls
)
from Backend.documents_reference import generate_bearer_token, generate_onco_emr_token
from Backend.drive_uploader import upload_and_share_pdf_bytes
from Backend.Utils.components.patient_demographics import extract_patient_demographics
from Backend.Utils.components.patient_diagnosis_status import extract_diagnosis_status
from Backend.Utils.Tabs.comorbidities import extract_comorbidities_status
from Backend.Utils.Tabs.lab_tab import extract_lab_info
from Backend.Utils.Tabs.treatment_tab import extract_treatment_tab_info
from Backend.Utils.Tabs.genomics_tab import extract_genomic_info
from Backend.Utils.Tabs.diagnosis_tab import diagnosis_extraction
from Backend.Utils.Tabs.pathology_tab import pathology_info
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

        # Step 3: Extract Demographics
        if verbose:
            print("\n[3/6] Extracting patient demographics...")

        demographics = extract_patient_demographics(pdf_url=result['pdf_url'])
        result['demographics'] = demographics

        if verbose:
            print(f"      ✓ Extracted {len(demographics)} demographic fields")

        # Step 4: Extract Diagnosis Status
        if verbose:
            print("\n[4/6] Extracting diagnosis status...")

        diagnosis = extract_diagnosis_status(pdf_url=result['pdf_url'])
        result['diagnosis'] = diagnosis

        if verbose:
            print(f"      ✓ Extracted {len(diagnosis)} diagnosis fields")

        if verbose:
            print("\n[5/6] Extracting Comorbidities status...")

        comorbidities = extract_comorbidities_status(pdf_url=result['pdf_url'])
        result['comorbidities'] = comorbidities

        if verbose:
            print(f"      ✓ Extracted {len(comorbidities)} comorbidities fields")

        if verbose:
            print("\n[6/6] Extracting Treatment Tab info status...")

        treatment_tab_info_LOT, treatment_tab_info_timeline = extract_treatment_tab_info(pdf_url=result['pdf_url'])
        result['treatment_tab_info_LOT'] = treatment_tab_info_LOT
        result['treatment_tab_info_timeline'] = treatment_tab_info_timeline

        if verbose:
            print(f"      ✓ Extracted {len(treatment_tab_info_LOT)} treatment_tab_info_LOT fields")
            print(f"      ✓ Extracted {len(treatment_tab_info_timeline)} treatment_tab_info_timeline fields")


        if verbose:
            print("\n[6/6] Extracting Diagnosis Tab info status...")

        diagnosis_header, diagnosis_evolution_timeline, diagnosis_footer = diagnosis_extraction(pdf_url=result['pdf_url'])
        result['diagnosis_header'] = diagnosis_header
        result['diagnosis_evolution_timeline'] = diagnosis_evolution_timeline
        result['diagnosis_footer'] = diagnosis_footer

        if verbose:
            print(f"      ✓ Extracted {len(diagnosis_header)} diagnosis_header fields")
            print(f"      ✓ Extracted {len(diagnosis_evolution_timeline)} diagnosis_evolution_timeline fields")
            print(f"      ✓ Extracted {len(diagnosis_footer)} diagnosis_footer fields")
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
    Extract lab results for a patient and combine them into a single PDF on Google Drive.

    This function:
    1. Fetches all lab result documents from the last 6 months
    2. Combines them into a single PDF
    3. Uploads to Google Drive and returns a shareable link

    Args:
        mrn (str): Patient's Medical Record Number
        verbose (bool): Print progress messages (default: True)

    Returns:
        dict: Contains success status, file info, and metadata
        {
            'success': bool,
            'mrn': str,
            'lab_results_count': int,
            'pdf_url': str,
            'file_id': str,
            'lab_documents': list,  # List of individual lab result documents
            'error': str (if failed)
        }
    """
    result = {
        'success': False,
        'mrn': mrn,
        'lab_results_count': 0,
        'pdf_url': None,
        'file_id': None,
        'lab_documents': None,
        'error': None
    }

    try:
        if verbose:
            print("="*70)
            print("  LAB RESULTS EXTRACTION & COMBINATION PIPELINE")
            print("="*70)
            print(f"\nMRN: {mrn}")

        # Step 1: Get lab results URLs using extract_lab_results_data
        if verbose:
            print("\n[1/2] Fetching lab results from FHIR API...")

        lab_documents = get_lab_results_urls(mrn=mrn)

        if not lab_documents:
            raise ValueError(f"No lab results found for MRN: {mrn}")

        result['lab_documents'] = lab_documents
        result['lab_results_count'] = len(lab_documents)

        if verbose:
            print(f"      ✓ Found {len(lab_documents)} lab result documents")
            for idx, doc in enumerate(lab_documents, 1):
                print(f"        {idx}. {doc['date']}: {doc.get('description', 'Lab Results')}")

        # Step 2: Extract URLs and combine PDFs
        if verbose:
            print(f"\n[2/2] Combining {len(lab_documents)} lab results into single PDF...")

        urls = [doc['url'] for doc in lab_documents]

        upload_result = fetch_and_combine_pdfs_from_urls(
            fhir_urls=urls,
            output_file_name=f"Lab_Results_Combined_{mrn}.pdf"
        )

        result['pdf_url'] = upload_result['shareable_url']
        result['file_id'] = upload_result['file_id']
        result['success'] = True
        result['lab_info'] = ""

        if verbose:
            print("\n" + "="*70)
            print("  LAB RESULTS EXTRACTION COMPLETE")
            print("="*70)
            print(f"Combined PDF URL: {result['pdf_url']}")
            print(f"Total Lab Results: {result['lab_results_count']}")
            print("="*70)

        lab_info = extract_lab_info(pdf_url=result['pdf_url'])
        result['lab_info'] = lab_info

        return result

    except Exception as e:
        result['error'] = str(e)
        if verbose:
            print(f"\n{'='*70}")
            print(f"ERROR: {str(e)}")
            print(f"{'='*70}")
        return result

def genomics_tab_pathology_tab_info(mrn: str, verbose: bool = True):
    """
    Extract pathology reports (all types), molecular reports, and MD notes for genomic data extraction and combine them into a single PDF on Google Drive.

    Note: ALL pathology reports (general + molecular), AND recent MD notes are included for comprehensive genomic information retrieval.

    This function:
    1. Fetches all pathology report documents from the last 6 months (from latest report date)
    2. Fetches recent MD notes
    3. Combines ALL reports (general pathology, molecular pathology, MD notes) into a single PDF for genomic extraction
    4. Uploads to Google Drive and returns a shareable link

    Args:
        mrn (str): Patient's Medical Record Number
        verbose (bool): Print progress messages (default: True)

    Returns:
        dict: Contains success status, file info, and metadata
        {
            'success': bool,
            'mrn': str,
            'pathology_reports_count': int,
            'pdf_url': str,
            'file_id': str,
            'pathology_documents': list,  # List of individual pathology report documents
            'md_notes_documents': list,  # List of MD notes documents
            'error': str (if failed)
        }
    """
    result = {
        'success': False,
        'mrn': mrn,
        'pathology_reports_count': 0,
        'md_notes_count': 0,
        'total_documents_count': 0,
        'pdf_url': None,
        'file_id': None,
        'pathology_documents': None,
        'md_notes_documents': None,
        'error': None
    }

    try:
        if verbose:
            print("="*70)
            print("  GENOMICS & PATHOLOGY DATA EXTRACTION PIPELINE")
            print("="*70)
            print(f"\nMRN: {mrn}")

        # Step 1: Get pathology report URLs (INCLUDING MD notes)
        if verbose:
            print("\n[1/3] Fetching pathology reports and MD notes from FHIR API...")

        all_documents = get_pathology_reports_urls(mrn=mrn, include_md_notes=True)

        if not all_documents:
            raise ValueError(f"No pathology reports or MD notes found for MRN: {mrn}")

        if verbose:
            print(f"      ✓ Found {len(all_documents)} documents total")

        # Step 2: Categorize documents (for reporting, but we'll use ALL of them)
        if verbose:
            print("\n[2/3] Categorizing documents for genomic extraction...")

        pathology_docs = []
        molecular_docs = []
        md_notes_docs = []
        general_pathology_docs = []

        for doc in all_documents:
            description = doc.get('description', '').lower()
            doc_type = doc.get('document_type', '').lower()

            # Check if it's an MD note
            is_md_note = ('md' in doc_type or 'physician' in doc_type or
                         'progress' in doc_type or 'visit' in doc_type)

            if is_md_note:
                md_notes_docs.append(doc)
            else:
                # It's a pathology report
                pathology_docs.append(doc)

                # Check if it's molecular/genomic pathology
                is_molecular = ('molecular' in description or 'genomic' in description or
                               any(keyword in description for keyword in ['ngs', 'sequencing', 'panel', 'mutation']))

                if is_molecular:
                    molecular_docs.append(doc)
                else:
                    general_pathology_docs.append(doc)

        # Use ALL documents (general pathology + molecular pathology + MD notes)
        all_documents_for_genomics = all_documents

        if not all_documents_for_genomics:
            raise ValueError(f"No documents found for genomic extraction for MRN: {mrn}")

        result['pathology_documents'] = pathology_docs
        result['md_notes_documents'] = md_notes_docs
        result['pathology_reports_count'] = len(pathology_docs)
        result['md_notes_count'] = len(md_notes_docs)
        result['total_documents_count'] = len(all_documents_for_genomics)

        if verbose:
            print(f"      ✓ Using ALL {len(all_documents_for_genomics)} documents for comprehensive genomic extraction:")
            print(f"         - Molecular/Genomic Pathology: {len(molecular_docs)}")
            print(f"         - General Pathology: {len(general_pathology_docs)}")
            print(f"         - MD Notes: {len(md_notes_docs)}")
            print(f"\n      Documents being used:")
            for idx, doc in enumerate(all_documents_for_genomics, 1):
                doc_type_label = "MD NOTE" if doc in md_notes_docs else ("MOLECULAR PATH" if doc in molecular_docs else "GENERAL PATH")
                print(f"        {idx}. [{doc_type_label}] {doc['date']}: {doc.get('description', 'Report')}")

        # Step 3: Extract URLs and combine PDFs
        if verbose:
            print(f"\n[3/3] Combining {len(all_documents_for_genomics)} documents into single PDF for genomic extraction...")

        urls = [doc['url'] for doc in all_documents_for_genomics]

        upload_result = fetch_and_combine_pdfs_from_urls(
            fhir_urls=urls,
            output_file_name=f"Genomics_Combined_{mrn}.pdf"
        )

        result['pdf_url'] = upload_result['shareable_url']
        result['file_id'] = upload_result['file_id']
        result['success'] = True

        if verbose:
            print("\n" + "="*70)
            print("  GENOMICS DATA EXTRACTION COMPLETE")
            print("="*70)
            print(f"Combined PDF URL: {result['pdf_url']}")
            print(f"Total documents used for genomic extraction: {result['total_documents_count']}")
            print(f"   - Molecular/Genomic Pathology: {len(molecular_docs)}")
            print(f"   - General Pathology: {len(general_pathology_docs)}")
            print(f"   - MD Notes: {len(md_notes_docs)}")
            print("="*70)

        result['genomic_info'] = extract_genomic_info(pdf_url=result['pdf_url'])
        patient_pathology_summary, patient_pathology_markers = pathology_info(pdf_url=result['pdf_url'])

        result['pathology_summary'] = patient_pathology_summary
        result['pathology_markers'] = patient_pathology_markers 

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

        genomic_pathology_result = genomics_tab_pathology_tab_info(mrn, verbose=True)

        if genomic_pathology_result['success']:
            print("\n" + "="*70)
            print("  GENOMICS TAB INFORMATION")
            print("="*70)
            print(json.dumps(genomic_pathology_result['genomic_info'], indent=2))
            print("\n" + "="*70)
            print("  PATHOLOGY TAB INFORMATION")
            print("="*70)
            print(json.dumps(genomic_pathology_result['pathology_summary'], indent=2))
            print(json.dumps(genomic_pathology_result['pathology_markers'], indent=2))
        else:
            print(f"\nGenomics and Pathology results extraction failed: {genomic_pathology_result['error']}")

        # Summary
        print("\n" + "="*70)
        print("  SUMMARY")
        print("="*70)
        print(f"Patient: {result['demographics'].get('Patient Name', 'N/A')}")
        print(f"MRN: {result['mrn']}")
        print(f"Cancer Type: {result['diagnosis'].get('cancer_type', 'N/A')}")
        print(f"Disease Status: {result['diagnosis'].get('disease_status', 'N/A')}")

        print(f"\nMain MD Note URL: {result['pdf_url']}")
        print(f"\nReport URL for Lab Tab: {lab_result['pdf_url']}")
        print(f"\nReport URL for Genomic Tab: {genomic_pathology_result['pdf_url']}")

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