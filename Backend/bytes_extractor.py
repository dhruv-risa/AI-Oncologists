"""
Document Extractor Module

Unified module for extracting medical documents from FHIR API.
Supports filtering by:
- LOINC codes (document types) - optional
- Regex patterns (matching against resource.type.text field for document type)
- Date ranges (e.g., last 6 months)
- Content type (default: application/pdf)
"""
import re
import time
from typing import List, Dict, Optional, Any, Union
from datetime import datetime, timedelta
try:
    from Backend.documents_reference import (
        generate_bearer_token,
        generate_onco_emr_token,
        get_patient_id_from_mrn,
        get_document_references,
    )
except ModuleNotFoundError:
    from documents_reference import (
        generate_bearer_token,
        generate_onco_emr_token,
        get_patient_id_from_mrn,
        get_document_references,
    )
import requests
import base64
from PyPDF2 import PdfMerger
from io import BytesIO
try:
    from Backend.drive_uploader import upload_and_share_pdf_bytes, create_or_get_folder
except ModuleNotFoundError:
    from drive_uploader import upload_and_share_pdf_bytes, create_or_get_folder


# Common LOINC codes for medical documents
LOINC_CODES = {
    "progress_notes": "11506-3",      # Progress notes (includes MD notes, nurse notes)
    "discharge_summary": "18842-5",   # Discharge summary
    "consultation_note": "11488-4",   # Consultation note
    "pathology_report": "60568-3",    # Pathology report
    "radiology_report": "18748-4",    # Diagnostic imaging report
    "lab_results": "26436-6",         # Laboratory studies
}

def get_documents(
    mrn: str,
    loinc_code: Optional[str] = None,
    description_patterns: Optional[List[str]] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    most_recent_only: bool = True,
    content_type: str = "application/pdf"
) -> Union[Optional[str], List[str], List[Dict[str, Any]]]:
    """
    Unified function to fetch medical documents from FHIR API.

    Args:
        mrn (str): Patient's Medical Record Number
        loinc_code (str, optional): LOINC code for document type (e.g., "11506-3" for progress notes)
                                   Use LOINC_CODES constant for common types
                                   If None, fetches all document types
        description_patterns (List[str], optional): Regex patterns to filter by document type text
                                                   (extracted from resource.type.text field)
                                                   Case-insensitive matching
        date_from (datetime, optional): Start date for filtering (inclusive)
        date_to (datetime, optional): End date for filtering (inclusive)
        most_recent_only (bool): If True, returns only URL of most recent document
                                If False, returns list of URLs
        content_type (str): MIME type to filter (default: "application/pdf")

    Returns:
        - If most_recent_only=True: Single URL string or None if no matches
        - If most_recent_only=False: List of URL strings (empty list if no matches)
    """
    # Step 1: Authenticate
    bearer_token = generate_bearer_token()
    onco_emr_token = generate_onco_emr_token(bearer_token)

    # Step 2: Get patient ID
    patient_id, _ = get_patient_id_from_mrn(mrn, onco_emr_token)

    # Step 3: Get document references from FHIR API
    document_bundle = get_document_references(patient_id, onco_emr_token, loinc_code)

    # Step 4: Extract and filter documents
    return _extract_documents_from_bundle(
        document_bundle=document_bundle,
        description_patterns=description_patterns,
        date_from=date_from,
        date_to=date_to,
        most_recent_only=most_recent_only,
        content_type=content_type
    )

def _extract_documents_from_bundle(
    document_bundle: Dict[str, Any],
    description_patterns: Optional[List[str]] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    most_recent_only: bool = True,
    content_type: str = "application/pdf"
) -> Union[Optional[str], List[str]]:
    """
    Internal function to extract and filter documents from FHIR bundle.

    Args:
        document_bundle: FHIR DocumentReference bundle
        description_patterns: Regex patterns for filtering by document type text (resource.type.text)
        date_from: Start date filter
        date_to: End date filter
        most_recent_only: Return only most recent or all matches
        content_type: MIME type filter

    Returns:
        Single URL or list of URLs depending on most_recent_only
    """
    # Check if bundle has entries
    if "entry" not in document_bundle or not document_bundle["entry"]:
        return None if most_recent_only else []

    # Compile regex patterns if provided
    compiled_patterns = None
    if description_patterns:
        compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in description_patterns]

    matching_documents = []

    for entry in document_bundle["entry"]:
        resource = entry.get("resource", {})

        # Filter 1: Check document type patterns from resource.type.text (if provided)
        if compiled_patterns:
            document_type = resource.get("type", {}).get("text", "")
            matches_pattern = any(pattern.search(document_type) for pattern in compiled_patterns)
            if not matches_pattern:
                continue

        # Filter 2: Check content type
        content_list = resource.get("content", [])
        has_content_type = any(
            content.get("attachment", {}).get("contentType") == content_type
            for content in content_list
        )
        if not has_content_type:
            continue

        # Filter 3: Check date range (if provided)
        date_str = resource.get("date")
        if date_str:
            try:
                # Parse ISO 8601 date string
                doc_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))

                # Make date_from and date_to timezone-aware if they aren't already
                if date_from and date_from.tzinfo is None:
                    date_from_aware = date_from.replace(tzinfo=doc_date.tzinfo)
                else:
                    date_from_aware = date_from

                if date_to and date_to.tzinfo is None:
                    date_to_aware = date_to.replace(tzinfo=doc_date.tzinfo)
                else:
                    date_to_aware = date_to

                # Apply date filters
                if date_from_aware and doc_date < date_from_aware:
                    continue
                if date_to_aware and doc_date > date_to_aware:
                    continue

            except (ValueError, AttributeError):
                # Skip documents with invalid dates
                continue

        # Extract document info
        full_url = entry.get("fullUrl")
        if full_url and date_str:
            matching_documents.append({
                "url": full_url,
                "date": date_str,
                "document_type": resource.get("type", {}).get("text", ""),
                "description": resource.get("description", ""),
                "document_id": resource.get("id")
            })

    # Sort by date (most recent first)
    matching_documents.sort(key=lambda x: x["date"], reverse=True)

    # Return based on most_recent_only flag
    if most_recent_only:
        return matching_documents[0]["url"] if matching_documents else None
    else:
        return [doc["url"] for doc in matching_documents]

def get_document_bytes(
    mrn: str,
    loinc_code: Optional[str] = None,
    description_patterns: Optional[List[str]] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    content_type: str = "application/pdf"
) -> Optional[bytes]:
    """
    Get PDF bytes of the most recent document matching criteria.

    Args:
        mrn (str): Patient's Medical Record Number
        loinc_code (str, optional): LOINC code for document type (None to fetch all types)
        description_patterns (List[str], optional): Regex patterns to filter by document type text
                                                   (extracted from resource.type.text field)
        date_from (datetime, optional): Start date for filtering
        date_to (datetime, optional): End date for filtering
        content_type (str): MIME type to filter (default: "application/pdf")

    Returns:
        bytes: PDF content as bytes, or None if no document found

    Example:
        >>> pdf_bytes = get_document_bytes("A2451440",
        ...                               description_patterns=[r'\bMD\b.*\bvisit\b'])
        >>> print(f"Retrieved {len(pdf_bytes)} bytes")
    """
    # Get most recent document URL
    document_url = get_documents(
        mrn=mrn,
        loinc_code=loinc_code,
        description_patterns=description_patterns,
        date_from=date_from,
        date_to=date_to,
        most_recent_only=True,
        content_type=content_type
    )

    if not document_url:
        return None

    # Authenticate and get PDF bytes
    bearer_token = generate_bearer_token()
    onco_emr_token = generate_onco_emr_token(bearer_token)

    headers = {
        "Authorization": f"Bearer {onco_emr_token}",
        "Accept": "application/fhir+json"
    }

    response = requests.get(document_url, headers=headers)
    response.raise_for_status()

    # Add rate limiting delay to avoid 429 errors
    time.sleep(1.5)

    document_data = response.json()

    # Extract PDF from content
    pdf_url = None
    pdf_data = None

    for content in document_data.get("content", []):
        attachment = content.get("attachment", {})
        if attachment.get("contentType") == "application/pdf":
            pdf_url = attachment.get("url")
            pdf_data = attachment.get("data")
            break

    # Download PDF from URL or decode base64
    if pdf_url:
        pdf_response = requests.get(pdf_url, headers=headers)
        pdf_response.raise_for_status()
        pdf_bytes = pdf_response.content
    elif pdf_data:
        pdf_bytes = base64.b64decode(pdf_data)
    else:
        raise ValueError("No PDF content found in document")

    return pdf_bytes

def extract_lab_results_data_md_notes_combined(
    mrn: str,
    loinc_code: Optional[str] = None,
    content_type: str = "application/pdf"
) -> List[Dict[str, Any]]:
    """
    Extract lab results documents with date-based filtering.

    Gets the most recent lab result document (where type.text="Lab Results"
    and contentType="application/pdf"), then fetches all lab results
    within 6 months before that most recent date.

    Args:
        mrn (str): Patient's Medical Record Number
        loinc_code (str, optional): LOINC code for document type (e.g., "11502-2" for lab results)
        content_type (str): MIME type to filter (default: "application/pdf")

    Returns:
        List[Dict]: List of lab result documents with metadata, sorted by date (most recent first)
                   Each dict contains: url, date, document_type, description, document_id
                   Returns empty list if no lab results found

    """
    # Step 1: Authenticate
    bearer_token = generate_bearer_token()
    onco_emr_token = generate_onco_emr_token(bearer_token)

    # Step 2: Get patient ID
    patient_id, _ = get_patient_id_from_mrn(mrn, onco_emr_token)

    # Step 3: Get document references from FHIR API
    document_bundle = get_document_references(patient_id, onco_emr_token, loinc_code)

    # Step 4: Filter for lab results with application/pdf content type
    lab_results = []

    if "entry" not in document_bundle or not document_bundle["entry"]:
        return []

    for entry in document_bundle["entry"]:
        resource = entry.get("resource", {})

        # Filter: Check if document type is "Lab Results"
        document_type = resource.get("type", {}).get("text", "")
        if document_type != "Lab Results":
            continue

        # Filter: Check content type is application/pdf
        content_list = resource.get("content", [])
        has_pdf_content = any(
            content.get("attachment", {}).get("contentType") == content_type
            for content in content_list
        )
        if not has_pdf_content:
            continue

        # Extract document info
        date_str = resource.get("date")
        full_url = entry.get("fullUrl")

        if full_url and date_str:
            lab_results.append({
                "url": full_url,
                "date": date_str,
                "document_type": document_type,
                "description": resource.get("description", ""),
                "document_id": resource.get("id")
            })

    # Sort by date (most recent first)
    lab_results.sort(key=lambda x: x["date"], reverse=True)

    if not lab_results:
        return []

    # Step 5: Get most recent date and calculate 6 months before
    most_recent_date_str = lab_results[0]["date"]
    most_recent_date = datetime.fromisoformat(most_recent_date_str.replace('Z', '+00:00'))
    six_months_before = most_recent_date - timedelta(days=180)

    # Step 6: Filter for documents within 6 months of most recent
    filtered_results = []
    for doc in lab_results:
        doc_date = datetime.fromisoformat(doc["date"].replace('Z', '+00:00'))
        if six_months_before <= doc_date <= most_recent_date:
            filtered_results.append(doc)

    # Get MD note document with full metadata
    document_type_patterns = [
            r'\bMD\b.*\bvisit\b',
            r'\bMD\b.*\bnote\b',
            r'\bphysician\b.*\bvisit\b',
            r'\bphysician\b.*\bnote\b',
            r'\bprogress\b.*\bnote\b'
        ]

    # Fetch MD note bundle to get full document metadata
    md_note_bundle = get_document_references(patient_id, onco_emr_token, loinc_type=None)

    # Extract MD note document with metadata using the same logic
    md_note_docs = _extract_documents_from_bundle(
        document_bundle=md_note_bundle,
        description_patterns=document_type_patterns,
        most_recent_only=False,  # Get all matching documents
        content_type=content_type
    )

    # If we found MD notes, add the most recent one to filtered_results
    if md_note_docs:
        # md_note_docs is a list of URLs when most_recent_only=False
        # We need to get the full document metadata
        # Let's extract it directly from the bundle instead
        compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in document_type_patterns]

        for entry in md_note_bundle.get("entry", []):
            resource = entry.get("resource", {})
            document_type = resource.get("type", {}).get("text", "")

            # Check if matches MD note pattern
            if not any(pattern.search(document_type) for pattern in compiled_patterns):
                continue

            # Check content type
            content_list = resource.get("content", [])
            has_pdf_content = any(
                content.get("attachment", {}).get("contentType") == content_type
                for content in content_list
            )
            if not has_pdf_content:
                continue

            # Found matching MD note - add it to filtered_results
            date_str = resource.get("date")
            full_url = entry.get("fullUrl")

            if full_url and date_str:
                filtered_results.append({
                    "url": full_url,
                    "date": date_str,
                    "document_type": document_type,
                    "description": resource.get("description", ""),
                    "document_id": resource.get("id")
                })
                # Only add the most recent MD note
                break

    return filtered_results


def extract_report_with_MD(
    mrn: str,
    loinc_code: Optional[str] = None,
    content_type: str = "application/pdf",
    report_type: str = "pathology",
    include_md_notes: bool = True
) -> List[Dict[str, Any]]:
    """
    Extract pathology/radiology reports documents with date-based filtering.

    Gets the most recent report document (where type.text contains the report_type
    and contentType="application/pdf"), then fetches all reports
    within 6 months before that most recent date.

    Args:
        mrn (str): Patient's Medical Record Number
        loinc_code (str, optional): LOINC code for document type (e.g., "60568-3" for pathology reports)
        content_type (str): MIME type to filter (default: "application/pdf")
        report_type (str): Type of report to extract (default: "pathology")
        include_md_notes (bool): Whether to include MD notes with the reports (default: True)

    Returns:
        List[Dict]: List of report documents with metadata, sorted by date (most recent first)
                   Each dict contains: url, date, document_type, description, document_id
                   Returns empty list if no reports found

    """
    # Step 1: Authenticate
    bearer_token = generate_bearer_token()
    onco_emr_token = generate_onco_emr_token(bearer_token)

    # Step 2: Get patient ID
    patient_id, _ = get_patient_id_from_mrn(mrn, onco_emr_token)

    # Step 3: Get document references from FHIR API
    document_bundle = get_document_references(patient_id, onco_emr_token, loinc_code)

    # Step 4: Filter for pathology reports with application/pdf content type
    reports = []

    if "entry" not in document_bundle or not document_bundle["entry"]:
        return []

    for entry in document_bundle["entry"]:
        resource = entry.get("resource", {})

        # Filter: Check if document type contains "Pathology"
        document_type = resource.get("type", {}).get("text", "")
        if report_type not in document_type.lower():
            continue

        # Filter: Check content type is application/pdf
        content_list = resource.get("content", [])
        has_pdf_content = any(
            content.get("attachment", {}).get("contentType") == content_type
            for content in content_list
        )
        if not has_pdf_content:
            continue

        # Extract document info
        date_str = resource.get("date")
        full_url = entry.get("fullUrl")

        if full_url and date_str:
            reports.append({
                "url": full_url,
                "date": date_str,
                "document_type": document_type,
                "description": resource.get("description", ""),
                "document_id": resource.get("id")
            })

    # Sort by date (most recent first)
    reports.sort(key=lambda x: x["date"], reverse=True)

    if not reports:
        return []

    # Step 5: Get most recent date and calculate 6 months before
    most_recent_date_str = reports[0]["date"]
    most_recent_date = datetime.fromisoformat(most_recent_date_str.replace('Z', '+00:00'))
    six_months_before = most_recent_date - timedelta(days=180)

    # Step 6: Filter for documents within 6 months of most recent
    filtered_results = []
    for doc in reports:
        doc_date = datetime.fromisoformat(doc["date"].replace('Z', '+00:00'))
        if six_months_before <= doc_date <= most_recent_date:
            filtered_results.append(doc)

    # Step 7: Add the most recent MD note to filtered_results (only if include_md_notes is True)
    if include_md_notes:
        document_type_patterns = [
            r'\bMD\b.*\bvisit\b',
            r'\bMD\b.*\bnote\b',
            r'\bphysician\b.*\bvisit\b',
            r'\bphysician\b.*\bnote\b',
            r'\bprogress\b.*\bnote\b'
        ]

        # Fetch MD note bundle to get full document metadata
        md_note_bundle = get_document_references(patient_id, onco_emr_token, loinc_type=None)
        compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in document_type_patterns]

        for entry in md_note_bundle.get("entry", []):
            resource = entry.get("resource", {})
            document_type = resource.get("type", {}).get("text", "")

            # Check if matches MD note pattern
            if not any(pattern.search(document_type) for pattern in compiled_patterns):
                continue

            # Check content type
            content_list = resource.get("content", [])
            has_pdf_content = any(
                content.get("attachment", {}).get("contentType") == content_type
                for content in content_list
            )
            if not has_pdf_content:
                continue

            # Found matching MD note - add it to filtered_results
            date_str = resource.get("date")
            full_url = entry.get("fullUrl")

            if full_url and date_str:
                filtered_results.append({
                    "url": full_url,
                    "date": date_str,
                    "document_type": document_type,
                    "description": resource.get("description", ""),
                    "document_id": resource.get("id")
                })
                # Only add the most recent MD note
                break

    return filtered_results


def fetch_pdf_bytes_from_fhir_url(fhir_url: str, bearer_token: Optional[str] = None, onco_emr_token: Optional[str] = None) -> Optional[bytes]:
    """
    Fetch PDF bytes from a single FHIR DocumentReference URL.

    Args:
        fhir_url (str): FHIR DocumentReference URL
        bearer_token (str, optional): Pre-generated bearer token (will generate if not provided)
        onco_emr_token (str, optional): Pre-generated onco EMR token (will generate if not provided)

    Returns:
        bytes: PDF content as bytes, or None if no PDF found

    Raises:
        Exception: If fetching fails

    Example:
        >>> pdf_bytes = fetch_pdf_bytes_from_fhir_url("https://fhir-api.com/DocumentReference/12345")
        >>> print(f"Fetched {len(pdf_bytes)} bytes")
    """
    # Authenticate if tokens not provided
    if not bearer_token:
        bearer_token = generate_bearer_token()
    if not onco_emr_token:
        onco_emr_token = generate_onco_emr_token(bearer_token)

    headers = {
        "Authorization": f"Bearer {onco_emr_token}",
        "Accept": "application/fhir+json"
    }

    # Add rate limiting delay to avoid 429 errors
    time.sleep(1.5)

    # Get document data from FHIR URL
    response = requests.get(fhir_url, headers=headers)
    response.raise_for_status()
    document_data = response.json()

    # Extract PDF from content
    pdf_url = None
    pdf_data = None

    for content in document_data.get("content", []):
        attachment = content.get("attachment", {})
        if attachment.get("contentType") == "application/pdf":
            pdf_url = attachment.get("url")
            pdf_data = attachment.get("data")
            break

    # Download PDF from URL or decode base64
    if pdf_url:
        pdf_response = requests.get(pdf_url, headers=headers)
        pdf_response.raise_for_status()
        pdf_bytes = pdf_response.content
    elif pdf_data:
        pdf_bytes = base64.b64decode(pdf_data)
    else:
        return None

    return pdf_bytes


def fetch_and_combine_pdfs_from_urls(
    fhir_urls: List[str],
    output_file_name: str = "combined_documents.pdf",
    folder_id: Optional[str] = None
) -> Dict[str, str]:
    """
    Fetch PDFs from multiple FHIR document URLs, combine them, and upload to Google Drive.

    This function:
    1. Authenticates with FHIR API
    2. Fetches PDF content from each provided FHIR document URL
    3. Merges all PDFs into a single document
    4. Uploads the combined PDF to Google Drive
    5. Makes it publicly accessible and returns the shareable link

    Args:
        fhir_urls (List[str]): List of FHIR DocumentReference URLs to fetch
        output_file_name (str): Name for the combined PDF file (default: "combined_documents.pdf")
        folder_id (str, optional): Google Drive folder ID to upload to

    Returns:
        dict: Contains file_id and shareable_url
              Example: {'file_id': '1abc...xyz', 'shareable_url': 'https://drive.google.com/...'}

    Raises:
        ValueError: If fhir_urls is empty or no PDFs found
        Exception: If fetching, combining, or uploading fails

    Example:
        >>> urls = [
        ...     "https://fhir-api.com/DocumentReference/12345",
        ...     "https://fhir-api.com/DocumentReference/67890"
        ... ]
        >>> result = fetch_and_combine_pdfs_from_urls(urls, "patient_reports.pdf")
        >>> print(f"Combined PDF available at: {result['shareable_url']}")
    """
    if not fhir_urls:
        raise ValueError("fhir_urls list cannot be empty")

    if not output_file_name.lower().endswith('.pdf'):
        output_file_name += '.pdf'

    # Step 1: Authenticate
    print(f"Authenticating with FHIR API...")
    bearer_token = generate_bearer_token()
    onco_emr_token = generate_onco_emr_token(bearer_token)

    headers = {
        "Authorization": f"Bearer {onco_emr_token}",
        "Accept": "application/fhir+json"
    }

    # Step 2: Fetch PDF bytes from each URL
    print(f"Fetching {len(fhir_urls)} documents...")
    pdf_bytes_list = []

    for idx, url in enumerate(fhir_urls, 1):
        print(f"  Fetching document {idx}/{len(fhir_urls)}: {url}")

        try:
            # Add rate limiting delay to avoid 429 errors
            time.sleep(1.5)

            # Get document data from FHIR URL
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            document_data = response.json()

            # Extract PDF from content
            pdf_url = None
            pdf_data = None

            for content in document_data.get("content", []):
                attachment = content.get("attachment", {})
                if attachment.get("contentType") == "application/pdf":
                    pdf_url = attachment.get("url")
                    pdf_data = attachment.get("data")
                    break

            # Download PDF from URL or decode base64
            if pdf_url:
                pdf_response = requests.get(pdf_url, headers=headers)
                pdf_response.raise_for_status()
                pdf_bytes = pdf_response.content
            elif pdf_data:
                pdf_bytes = base64.b64decode(pdf_data)
            else:
                print(f"  Warning: No PDF content found in document {idx}, skipping...")
                continue

            pdf_bytes_list.append(pdf_bytes)
            print(f"  Successfully fetched document {idx} ({len(pdf_bytes)} bytes)")

        except Exception as e:
            print(f"  Error fetching document {idx}: {str(e)}")
            # Continue with other documents instead of failing completely
            continue

    if not pdf_bytes_list:
        raise ValueError("No PDFs were successfully fetched from the provided URLs")

    # Step 3: Combine all PDFs
    print(f"\nCombining {len(pdf_bytes_list)} PDFs...")
    merger = PdfMerger()

    for idx, pdf_bytes in enumerate(pdf_bytes_list, 1):
        try:
            pdf_stream = BytesIO(pdf_bytes)
            merger.append(pdf_stream)
            print(f"  Added PDF {idx} to merger")
        except Exception as e:
            print(f"  Warning: Failed to add PDF {idx} to merger: {str(e)}")
            continue

    # Write combined PDF to bytes
    combined_pdf_stream = BytesIO()
    merger.write(combined_pdf_stream)
    merger.close()
    combined_pdf_bytes = combined_pdf_stream.getvalue()
    combined_pdf_stream.close()

    print(f"Successfully combined PDFs (total size: {len(combined_pdf_bytes)} bytes)")

    # Step 4: Upload to Google Drive
    print(f"\nUploading combined PDF to Google Drive...")
    result = upload_and_share_pdf_bytes(
        pdf_bytes=combined_pdf_bytes,
        file_name=output_file_name,
        folder_id=folder_id
    )

    print(f"\nUpload complete!")
    print(f"File ID: {result['file_id']}")
    print(f"Shareable URL: {result['shareable_url']}")

    return result


def combine_pdf_bytes_and_upload(
    pdf_bytes_list: List[bytes],
    output_file_name: str = "combined_documents.pdf",
    folder_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Combine multiple PDF bytes and upload to Google Drive, returning both URL and bytes.

    This function is optimized for scenarios where PDF bytes are already in memory
    (e.g., from classification pipeline) to avoid redundant downloads.

    Args:
        pdf_bytes_list (List[bytes]): List of PDF content as bytes
        output_file_name (str): Name for the combined PDF file (default: "combined_documents.pdf")
        folder_id (str, optional): Google Drive folder ID to upload to

    Returns:
        dict: Contains file_id, shareable_url, and combined_pdf_bytes
              Example: {
                  'file_id': '1abc...xyz',
                  'shareable_url': 'https://drive.google.com/...',
                  'combined_pdf_bytes': b'...'  # The combined PDF as bytes
              }

    Raises:
        ValueError: If pdf_bytes_list is empty
        Exception: If combining or uploading fails

    Example:
        >>> pdf_bytes_list = [pdf1_bytes, pdf2_bytes, pdf3_bytes]
        >>> result = combine_pdf_bytes_and_upload(pdf_bytes_list, "patient_reports.pdf")
        >>> print(f"Combined PDF URL: {result['shareable_url']}")
        >>> # Use bytes directly without downloading
        >>> extract_data(result['combined_pdf_bytes'])
    """
    if not pdf_bytes_list:
        raise ValueError("pdf_bytes_list cannot be empty")

    if not output_file_name.lower().endswith('.pdf'):
        output_file_name += '.pdf'

    # Step 1: Combine all PDFs
    print(f"\nCombining {len(pdf_bytes_list)} PDFs from cached bytes...")
    merger = PdfMerger()

    for idx, pdf_bytes in enumerate(pdf_bytes_list, 1):
        try:
            pdf_stream = BytesIO(pdf_bytes)
            merger.append(pdf_stream)
            print(f"  Added PDF {idx} to merger ({len(pdf_bytes)} bytes)")
        except Exception as e:
            print(f"  Warning: Failed to add PDF {idx} to merger: {str(e)}")
            continue

    # Write combined PDF to bytes
    combined_pdf_stream = BytesIO()
    merger.write(combined_pdf_stream)
    merger.close()
    combined_pdf_bytes = combined_pdf_stream.getvalue()
    combined_pdf_stream.close()

    print(f"Successfully combined PDFs (total size: {len(combined_pdf_bytes)} bytes)")

    # Step 2: Upload to Google Drive
    print(f"\nUploading combined PDF to Google Drive...")
    upload_result = upload_and_share_pdf_bytes(
        pdf_bytes=combined_pdf_bytes,
        file_name=output_file_name,
        folder_id=folder_id
    )

    print(f"\nUpload complete!")
    print(f"File ID: {upload_result['file_id']}")
    print(f"Shareable URL: {upload_result['shareable_url']}")

    # Return both URL info AND the bytes for direct use
    return {
        'file_id': upload_result['file_id'],
        'shareable_url': upload_result['shareable_url'],
        'combined_pdf_bytes': combined_pdf_bytes  # Include bytes for direct extraction
    }


def get_md_notes(
    mrn: str,
    most_recent_only: bool = True,
    initial_only: bool = False,
    content_type: str = "application/pdf"
) -> Optional[Dict[str, Any]]:
    """
    Get MD notes for a patient.

    Args:
        mrn (str): Patient's Medical Record Number
        most_recent_only (bool): If True, returns only the most recent MD note
        initial_only (bool): If True, returns only the oldest/initial MD note
        content_type (str): MIME type to filter (default: "application/pdf")

    Returns:
        Dict with MD note metadata (url, date, document_type, description, document_id)
        or None if no MD notes found
    """
    # Step 1: Authenticate
    bearer_token = generate_bearer_token()
    onco_emr_token = generate_onco_emr_token(bearer_token)

    # Step 2: Get patient ID
    patient_id, _ = get_patient_id_from_mrn(mrn, onco_emr_token)

    # Step 3: Get document references from FHIR API
    document_bundle = get_document_references(patient_id, onco_emr_token, loinc_type=None)

    # Step 4: Define MD note patterns
    document_type_patterns = [
        r'\bMD\b.*\bvisit\b',
        r'\bMD\b.*\bnote\b',
        r'\bphysician\b.*\bvisit\b',
        r'\bphysician\b.*\bnote\b',
        r'\bprogress\b.*\bnote\b'
    ]

    compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in document_type_patterns]

    # Step 5: Extract MD notes from bundle
    md_notes = []

    if "entry" not in document_bundle or not document_bundle["entry"]:
        return None

    for entry in document_bundle.get("entry", []):
        resource = entry.get("resource", {})
        document_type = resource.get("type", {}).get("text", "")

        # Check if matches MD note pattern
        if not any(pattern.search(document_type) for pattern in compiled_patterns):
            continue

        # Check content type
        content_list = resource.get("content", [])
        has_pdf_content = any(
            content.get("attachment", {}).get("contentType") == content_type
            for content in content_list
        )
        if not has_pdf_content:
            continue

        # Found matching MD note
        date_str = resource.get("date")
        full_url = entry.get("fullUrl")

        if full_url and date_str:
            md_notes.append({
                "url": full_url,
                "date": date_str,
                "document_type": document_type,
                "description": resource.get("description", ""),
                "document_id": resource.get("id")
            })

    if not md_notes:
        return None

    # Sort by date
    md_notes.sort(key=lambda x: x["date"], reverse=True)

    # Return based on flags
    if initial_only:
        return md_notes[-1]  # Return the oldest (initial) MD note
    elif most_recent_only:
        return md_notes[0]   # Return the most recent MD note
    else:
        return md_notes[0]   # Default to most recent


def upload_individual_reports_to_drive(
    mrn: str,
    report_type: str = "pathology",
    loinc_code: Optional[str] = None,
    content_type: str = "application/pdf"
) -> List[Dict[str, Any]]:
    """
    Extract individual reports, upload each to Google Drive in a folder based on report type,
    and return Google Drive URLs.

    This function:
    1. Extracts report URLs from FHIR (pathology or radiology)
    2. Creates/gets a Google Drive folder based on report type
    3. Uploads each report individually to the folder
    4. Returns list of documents with Google Drive URLs

    Args:
        mrn (str): Patient's Medical Record Number
        report_type (str): Type of report - "pathology" or "radiology" (default: "pathology")
        loinc_code (str, optional): LOINC code for document type
        content_type (str): MIME type to filter (default: "application/pdf")

    Returns:
        List[Dict]: List of report documents with Google Drive URLs
                   Each dict contains: original_url, drive_url, drive_file_id, date, document_type, description, document_id
                   Returns empty list if no reports found

    Raises:
        ValueError: If report_type is not "pathology" or "radiology"
        Exception: If upload fails

    Example:
        >>> result = upload_individual_reports_to_drive("A2451440", report_type="pathology")
        >>> for doc in result:
        ...     print(f"Document: {doc['document_type']}")
        ...     print(f"Drive URL: {doc['drive_url']}")
    """
    if report_type not in ["pathology", "radiology"]:
        raise ValueError("report_type must be either 'pathology' or 'radiology'")

    # Step 1: Extract report URLs from FHIR (excluding MD notes)
    print(f"Extracting {report_type} reports for MRN: {mrn}")
    report_docs = extract_report_with_MD(
        mrn=mrn,
        loinc_code=loinc_code,
        content_type=content_type,
        report_type=report_type,
        include_md_notes=False  # Exclude MD notes from report lists
    )

    if not report_docs:
        print(f"No {report_type} reports found")
        return []

    print(f"Found {len(report_docs)} {report_type} report(s)")

    # Step 2: Create or get Google Drive folder for this report type
    folder_name = f"{report_type.capitalize()} Reports"
    print(f"Creating/getting Google Drive folder: {folder_name}")
    folder_id = create_or_get_folder(folder_name)

    # Step 3: Authenticate with FHIR API
    bearer_token = generate_bearer_token()
    onco_emr_token = generate_onco_emr_token(bearer_token)

    headers = {
        "Authorization": f"Bearer {onco_emr_token}",
        "Accept": "application/fhir+json"
    }

    # Step 4: Upload each report individually to Google Drive
    uploaded_docs = []

    for idx, doc in enumerate(report_docs, 1):
        fhir_url = doc['url']
        print(f"\nProcessing report {idx}/{len(report_docs)}: {doc['document_type']}")

        try:
            # Add rate limiting delay to avoid 429 errors
            time.sleep(1.5)

            # Fetch PDF from FHIR URL
            print(f"  Fetching from FHIR...")
            response = requests.get(fhir_url, headers=headers)
            response.raise_for_status()
            document_data = response.json()

            # Extract PDF bytes
            pdf_url = None
            pdf_data = None

            for content in document_data.get("content", []):
                attachment = content.get("attachment", {})
                if attachment.get("contentType") == "application/pdf":
                    pdf_url = attachment.get("url")
                    pdf_data = attachment.get("data")
                    break

            # Download PDF from URL or decode base64
            if pdf_url:
                pdf_response = requests.get(pdf_url, headers=headers)
                pdf_response.raise_for_status()
                pdf_bytes = pdf_response.content
            elif pdf_data:
                pdf_bytes = base64.b64decode(pdf_data)
            else:
                print(f"  Warning: No PDF content found, skipping...")
                continue

            print(f"  Fetched PDF ({len(pdf_bytes)} bytes)")

            # Generate file name based on document metadata
            date_str = doc['date'].split('T')[0]  # Extract date part (YYYY-MM-DD)
            file_name = f"{mrn}_{report_type}_{date_str}_{doc['document_id']}.pdf"

            # Upload to Google Drive
            print(f"  Uploading to Google Drive as: {file_name}")
            upload_result = upload_and_share_pdf_bytes(
                pdf_bytes=pdf_bytes,
                file_name=file_name,
                folder_id=folder_id
            )

            # Add to results with both original and Drive URLs
            uploaded_docs.append({
                "original_url": fhir_url,
                "drive_url": upload_result['shareable_url'],
                "drive_file_id": upload_result['file_id'],
                "date": doc['date'],
                "document_type": doc['document_type'],
                "description": doc['description'],
                "document_id": doc['document_id']
            })

            print(f"  Successfully uploaded! Drive URL: {upload_result['shareable_url']}")

        except Exception as e:
            print(f"  Error processing report {idx}: {str(e)}")
            # Continue with other documents instead of failing completely
            continue

    print(f"\n{'='*60}")
    print(f"Upload Summary: {len(uploaded_docs)}/{len(report_docs)} reports uploaded successfully")
    print(f"{'='*60}")

    return uploaded_docs


def upload_individual_radiology_reports_with_MD_notes_to_drive(
    mrn: str,
    loinc_code: Optional[str] = None,
    content_type: str = "application/pdf"
) -> List[Dict[str, Any]]:
    """
    Extract individual radiology reports, combine each with latest and initial MD notes,
    upload to Google Drive, and return URLs.

    This function:
    1. Extracts radiology reports from FHIR
    2. For each report:
       - Fetches the radiology report PDF
       - Fetches the most recent MD note PDF
       - Fetches the initial MD note PDF
       - Combines all three into a single PDF
    3. Uploads combined PDFs to Google Drive in a "Radiology Reports" folder
    4. Returns list of documents with Google Drive URLs

    Args:
        mrn (str): Patient's Medical Record Number
        loinc_code (str, optional): LOINC code for document type
        content_type (str): MIME type to filter (default: "application/pdf")

    Returns:
        List[Dict]: List of radiology reports with Google Drive URLs
                   Each dict contains: original_url, drive_url (radiology only),
                   drive_url_with_MD (combined with MD notes), drive_file_id,
                   date, document_type, description, document_id
                   Returns empty list if no reports found

    Raises:
        Exception: If upload fails

    Example:
        >>> result = upload_individual_radiology_reports_with_MD_notes_to_drive("A2451440")
        >>> for doc in result:
        ...     print(f"Radiology URL: {doc['drive_url']}")
        ...     print(f"Combined URL: {doc['drive_url_with_MD']}")
    """
    # Step 1: Extract radiology report URLs from FHIR (excluding MD notes from list)
    print(f"Extracting radiology reports for MRN: {mrn}")
    radiology_docs = extract_report_with_MD(
        mrn=mrn,
        loinc_code=loinc_code,
        content_type=content_type,
        report_type="radiology",
        include_md_notes=False  # Exclude MD notes from report lists
    )

    if not radiology_docs:
        print("No radiology reports found")
        return []

    print(f"Found {len(radiology_docs)} radiology report(s)")

    # Step 2: Get MD notes
    print("\nFetching MD notes...")
    latest_md_note = get_md_notes(mrn, most_recent_only=True, initial_only=False)
    initial_md_note = get_md_notes(mrn, most_recent_only=False, initial_only=True)

    if not latest_md_note:
        print("Warning: No latest MD note found")
    else:
        print(f"  Latest MD note: {latest_md_note['date']}")

    if not initial_md_note:
        print("Warning: No initial MD note found")
    else:
        print(f"  Initial MD note: {initial_md_note['date']}")

    # Step 3: Create or get Google Drive folder
    folder_name = "Radiology Reports"
    print(f"\nCreating/getting Google Drive folder: {folder_name}")
    folder_id = create_or_get_folder(folder_name)

    # Step 4: Authenticate with FHIR API
    bearer_token = generate_bearer_token()
    onco_emr_token = generate_onco_emr_token(bearer_token)

    headers = {
        "Authorization": f"Bearer {onco_emr_token}",
        "Accept": "application/fhir+json"
    }

    # Step 5: Process each radiology report
    uploaded_docs = []

    for idx, doc in enumerate(radiology_docs, 1):
        fhir_url = doc['url']
        print(f"\nProcessing report {idx}/{len(radiology_docs)}: {doc['document_type']}")

        try:
            # Add rate limiting delay to avoid 429 errors
            time.sleep(1.5)

            # Fetch radiology report PDF
            print(f"  Fetching radiology report from FHIR...")
            response = requests.get(fhir_url, headers=headers)
            response.raise_for_status()
            document_data = response.json()

            # Extract PDF bytes
            pdf_url = None
            pdf_data = None

            for content in document_data.get("content", []):
                attachment = content.get("attachment", {})
                if attachment.get("contentType") == "application/pdf":
                    pdf_url = attachment.get("url")
                    pdf_data = attachment.get("data")
                    break

            # Download radiology PDF
            if pdf_url:
                pdf_response = requests.get(pdf_url, headers=headers)
                pdf_response.raise_for_status()
                radiology_pdf_bytes = pdf_response.content
            elif pdf_data:
                radiology_pdf_bytes = base64.b64decode(pdf_data)
            else:
                print(f"  Warning: No PDF content found, skipping...")
                continue

            print(f"  Fetched radiology PDF ({len(radiology_pdf_bytes)} bytes)")

            # Upload radiology report only (without MD notes)
            date_str = doc['date'].split('T')[0]
            radiology_only_file_name = f"{mrn}_radiology_{date_str}_{doc['document_id']}.pdf"

            print(f"  Uploading radiology report only to Google Drive...")
            radiology_only_result = upload_and_share_pdf_bytes(
                pdf_bytes=radiology_pdf_bytes,
                file_name=radiology_only_file_name,
                folder_id=folder_id
            )

            # Now combine with MD notes if available
            pdf_bytes_list = [radiology_pdf_bytes]
            combined_file_name = f"{mrn}_radiology_with_MD_{date_str}_{doc['document_id']}.pdf"

            # Fetch and add latest MD note
            if latest_md_note:
                print(f"  Fetching latest MD note...")
                try:
                    # Add rate limiting delay to avoid 429 errors
                    time.sleep(1.5)

                    md_response = requests.get(latest_md_note['url'], headers=headers)
                    md_response.raise_for_status()
                    md_document_data = md_response.json()

                    md_pdf_url = None
                    md_pdf_data = None
                    for content in md_document_data.get("content", []):
                        attachment = content.get("attachment", {})
                        if attachment.get("contentType") == "application/pdf":
                            md_pdf_url = attachment.get("url")
                            md_pdf_data = attachment.get("data")
                            break

                    if md_pdf_url:
                        md_pdf_response = requests.get(md_pdf_url, headers=headers)
                        md_pdf_response.raise_for_status()
                        latest_md_pdf_bytes = md_pdf_response.content
                    elif md_pdf_data:
                        latest_md_pdf_bytes = base64.b64decode(md_pdf_data)
                    else:
                        latest_md_pdf_bytes = None

                    if latest_md_pdf_bytes:
                        pdf_bytes_list.append(latest_md_pdf_bytes)
                        print(f"    Added latest MD note ({len(latest_md_pdf_bytes)} bytes)")
                except Exception as e:
                    print(f"    Warning: Failed to fetch latest MD note: {str(e)}")

            # Fetch and add initial MD note
            if initial_md_note:
                print(f"  Fetching initial MD note...")
                try:
                    # Add rate limiting delay to avoid 429 errors
                    time.sleep(1.5)

                    md_response = requests.get(initial_md_note['url'], headers=headers)
                    md_response.raise_for_status()
                    md_document_data = md_response.json()

                    md_pdf_url = None
                    md_pdf_data = None
                    for content in md_document_data.get("content", []):
                        attachment = content.get("attachment", {})
                        if attachment.get("contentType") == "application/pdf":
                            md_pdf_url = attachment.get("url")
                            md_pdf_data = attachment.get("data")
                            break

                    if md_pdf_url:
                        md_pdf_response = requests.get(md_pdf_url, headers=headers)
                        md_pdf_response.raise_for_status()
                        initial_md_pdf_bytes = md_pdf_response.content
                    elif md_pdf_data:
                        initial_md_pdf_bytes = base64.b64decode(md_pdf_data)
                    else:
                        initial_md_pdf_bytes = None

                    if initial_md_pdf_bytes:
                        pdf_bytes_list.append(initial_md_pdf_bytes)
                        print(f"    Added initial MD note ({len(initial_md_pdf_bytes)} bytes)")
                except Exception as e:
                    print(f"    Warning: Failed to fetch initial MD note: {str(e)}")

            # Combine all PDFs
            print(f"  Combining {len(pdf_bytes_list)} PDFs...")
            merger = PdfMerger()

            for pdf_idx, pdf_bytes in enumerate(pdf_bytes_list, 1):
                try:
                    pdf_stream = BytesIO(pdf_bytes)
                    merger.append(pdf_stream)
                except Exception as e:
                    print(f"    Warning: Failed to add PDF {pdf_idx} to merger: {str(e)}")
                    continue

            # Write combined PDF to bytes
            combined_pdf_stream = BytesIO()
            merger.write(combined_pdf_stream)
            merger.close()
            combined_pdf_bytes = combined_pdf_stream.getvalue()
            combined_pdf_stream.close()

            print(f"  Combined PDF size: {len(combined_pdf_bytes)} bytes")

            # Upload combined PDF to Google Drive
            print(f"  Uploading combined PDF to Google Drive as: {combined_file_name}")
            combined_upload_result = upload_and_share_pdf_bytes(
                pdf_bytes=combined_pdf_bytes,
                file_name=combined_file_name,
                folder_id=folder_id
            )

            # Add to results
            uploaded_docs.append({
                "original_url": fhir_url,
                "drive_url": radiology_only_result['shareable_url'],
                "drive_file_id": radiology_only_result['file_id'],
                "drive_url_with_MD": combined_upload_result['shareable_url'],
                "drive_file_id_with_MD": combined_upload_result['file_id'],
                "date": doc['date'],
                "document_type": doc['document_type'],
                "description": doc['description'],
                "document_id": doc['document_id'],
                "has_latest_md_note": latest_md_note is not None,
                "has_initial_md_note": initial_md_note is not None
            })

            print(f"  Successfully uploaded!")
            print(f"    Radiology only: {radiology_only_result['shareable_url']}")
            print(f"    Combined with MD: {combined_upload_result['shareable_url']}")

        except Exception as e:
            print(f"  Error processing report {idx}: {str(e)}")
            continue

    print(f"\n{'='*60}")
    print(f"Upload Summary: {len(uploaded_docs)}/{len(radiology_docs)} reports uploaded successfully")
    print(f"{'='*60}")

    return uploaded_docs
