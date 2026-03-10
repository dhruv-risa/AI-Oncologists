"""
Demo Data Loader Module

Loads patient data from demo_data.json file and fetches file metadata
from Google Drive URLs for demo purposes.
"""
import json
import os
from typing import Dict, List, Any
from drive_uploader import get_file_metadata_from_url


def load_demo_data_json():
    """
    Load the demo_data.json file.

    Returns:
        dict: Demo data mapping MRNs to document URLs

    Raises:
        FileNotFoundError: If demo_data.json doesn't exist
        json.JSONDecodeError: If JSON is invalid
    """
    current_dir = os.path.dirname(__file__)
    json_path = os.path.join(current_dir, 'demo_data.json')

    if not os.path.exists(json_path):
        raise FileNotFoundError(f"demo_data.json not found at {json_path}")

    with open(json_path, 'r') as f:
        return json.load(f)


def fetch_documents_metadata_for_urls(urls: List[str], doc_type: str = "Document") -> List[Dict[str, Any]]:
    """
    Fetch metadata for a list of Google Drive URLs.

    Args:
        urls (list): List of Google Drive URLs (first URL is latest, second is oldest for MD notes)
        doc_type (str): Type of document for fallback naming

    Returns:
        list: List of document metadata dictionaries with:
            - name: Document name from Google Drive
            - date: Last modified date
            - drive_url: The shareable link
    """
    documents = []

    for idx, url in enumerate(urls, 1):
        try:
            metadata = get_file_metadata_from_url(url)

            doc_info = {
                'name': metadata['name'],
                'date': metadata['date'],
                'drive_url': metadata['drive_url']
            }

            documents.append(doc_info)

        except Exception as e:
            print(f"Error fetching metadata for URL {url}: {str(e)}")
            # Add placeholder with document type and index for failed URLs
            documents.append({
                'name': f'{doc_type} #{idx}',
                'date': 'N/A',
                'drive_url': url
            })

    return documents


def get_demo_patient_data(mrn: str) -> Dict[str, Any]:
    """
    Get demo patient data for a given MRN from demo_data.json.
    Fetches all document metadata from Google Drive URLs.

    Args:
        mrn (str): Medical Record Number

    Returns:
        dict: Patient data with document metadata in the format:
            {
                'mrn': mrn,
                'md_notes': [{'name': str, 'date': str, 'drive_url': str}, ...],
                'latest_md_note_url': str (first URL - latest),
                'oldest_md_note_url': str (second URL - oldest, for radiology),
                'pathology_reports': [...],
                'radiology_reports': [...],
                'genomics_reports': [...],
                'lab_results': [...]
            }

    Raises:
        ValueError: If MRN not found in demo data
    """
    demo_data = load_demo_data_json()

    if mrn not in demo_data:
        raise ValueError(f"MRN {mrn} not found in demo data. Available MRNs: {list(demo_data.keys())}")

    patient_data = demo_data[mrn]

    # Fetch metadata for each document type
    result = {
        'mrn': mrn,
        'md_notes': [],
        'latest_md_note_url': None,
        'oldest_md_note_url': None,
        'pathology_reports': [],
        'radiology_reports': [],
        'genomics_reports': [],
        'lab_results': []
    }

    # Map JSON keys to result keys
    key_mapping = {
        'md_notes': 'md_notes',
        'pathology': 'pathology_reports',
        'radiology': 'radiology_reports',
        'genomics': 'genomics_reports',
        'lab_results': 'lab_results'
    }

    for json_key, result_key in key_mapping.items():
        if json_key in patient_data and patient_data[json_key]:
            print(f"Fetching metadata for {result_key}...")
            result[result_key] = fetch_documents_metadata_for_urls(
                patient_data[json_key]
            )

    # Handle MD notes ordering: first URL = latest, second URL = oldest
    if 'md_notes' in patient_data and patient_data['md_notes']:
        md_note_urls = patient_data['md_notes']
        result['latest_md_note_url'] = md_note_urls[0] if len(md_note_urls) > 0 else None
        result['oldest_md_note_url'] = md_note_urls[1] if len(md_note_urls) > 1 else md_note_urls[0]

    return result


def get_raw_demo_urls(mrn: str) -> Dict[str, List[str]]:
    """
    Get raw URLs from demo_data.json without fetching metadata.
    Useful for getting URLs to pass to extraction functions.

    Args:
        mrn (str): Medical Record Number

    Returns:
        dict: URLs by document type:
            {
                'md_notes': [url1, url2],
                'pathology': [url1],
                'radiology': [url1, url2],
                'genomics': [url1],
                'lab_results': [url1, url2]
            }

    Raises:
        ValueError: If MRN not found in demo data
    """
    demo_data = load_demo_data_json()

    if mrn not in demo_data:
        raise ValueError(f"MRN {mrn} not found in demo data. Available MRNs: {list(demo_data.keys())}")

    return demo_data[mrn]


def list_available_demo_mrns() -> List[str]:
    """
    List all available MRNs in demo_data.json.

    Returns:
        list: List of MRN strings
    """
    try:
        demo_data = load_demo_data_json()
        return list(demo_data.keys())
    except Exception as e:
        print(f"Error loading demo data: {str(e)}")
        return []
