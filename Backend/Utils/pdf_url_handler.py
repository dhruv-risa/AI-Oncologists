"""
PDF URL Handler Utility

Provides utilities to handle PDF URLs from different sources (Google Drive, direct URLs, etc.)
and convert them to bytes for extraction functions.
"""
import sys
import os

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(PROJECT_ROOT)

try:
    from Backend.storage_uploader import download_pdf_bytes_from_url as download_pdf_bytes_from_drive_url
except ModuleNotFoundError:
    from storage_uploader import download_pdf_bytes_from_url as download_pdf_bytes_from_drive_url


def is_google_drive_url(url):
    """
    Check if a URL is a Google Drive URL.

    Args:
        url (str): URL to check

    Returns:
        bool: True if it's a Google Drive URL, False otherwise
    """
    if not isinstance(url, str):
        return False

    drive_patterns = [
        'drive.google.com',
        'docs.google.com/file'
    ]

    return any(pattern in url.lower() for pattern in drive_patterns)


def get_pdf_bytes_from_url(pdf_url):
    """
    Get PDF bytes from any URL (Google Drive, Firebase Storage, or direct URL).

    This function automatically detects the URL type and handles it appropriately:
    - Firebase Storage paths (/api/documents/...): Downloads from Firebase Storage
    - Google Drive URLs: Downloads using Google Drive API
    - Other URLs: Downloads directly via HTTP request

    Args:
        pdf_url (str): PDF URL (Google Drive, Firebase Storage path, or direct URL)

    Returns:
        bytes: PDF content as bytes

    Raises:
        Exception: If download fails

    Example:
        >>> # Works with Firebase Storage paths
        >>> bytes1 = get_pdf_bytes_from_url("/api/documents/documents%2FMD_note_123.pdf")
        >>>
        >>> # Works with Google Drive URLs
        >>> bytes2 = get_pdf_bytes_from_url("https://drive.google.com/file/d/FILE_ID/view")
        >>>
        >>> # Works with direct URLs
        >>> bytes3 = get_pdf_bytes_from_url("https://example.com/document.pdf")
    """
    # Check for Firebase Storage paths first
    if isinstance(pdf_url, str) and pdf_url.startswith("/api/documents/"):
        print(f"Detected Firebase Storage path, downloading from storage...")
        try:
            from Backend.storage_uploader import download_pdf_bytes_from_url as download_from_storage
        except ModuleNotFoundError:
            from storage_uploader import download_pdf_bytes_from_url as download_from_storage
        return download_from_storage(pdf_url)
    elif is_google_drive_url(pdf_url):
        print(f"Detected Google Drive URL, downloading via Drive API...")
        return download_pdf_bytes_from_drive_url(pdf_url)
    else:
        # For non-Google Drive URLs, download via HTTP request
        import requests
        print(f"Downloading PDF from URL: {pdf_url}")
        response = requests.get(pdf_url)
        response.raise_for_status()
        return response.content


def handle_pdf_input(pdf_url=None, pdf_bytes=None):
    """
    Universal PDF input handler for extraction functions.

    This function handles multiple input formats:
    1. If pdf_bytes is provided, use it directly
    2. If pdf_url is provided, download bytes from URL (supports Google Drive)
    3. If neither provided, raise error

    Args:
        pdf_url (str, optional): PDF URL (Google Drive or direct URL)
        pdf_bytes (bytes, optional): PDF content as bytes

    Returns:
        bytes: PDF content as bytes

    Raises:
        ValueError: If neither pdf_url nor pdf_bytes is provided
        Exception: If download fails

    Example:
        >>> # In your extraction function:
        >>> def extract_data(pdf_url=None, pdf_bytes=None):
        >>>     pdf_bytes = handle_pdf_input(pdf_url=pdf_url, pdf_bytes=pdf_bytes)
        >>>     # Now process pdf_bytes...
    """
    if pdf_bytes is not None:
        # Bytes already provided, use directly
        return pdf_bytes
    elif pdf_url is not None:
        # Download bytes from URL
        return get_pdf_bytes_from_url(pdf_url)
    else:
        raise ValueError("Either pdf_url or pdf_bytes must be provided")
