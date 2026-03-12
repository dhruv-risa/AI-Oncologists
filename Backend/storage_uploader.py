"""
Firebase Storage (Google Cloud Storage) Document Uploader Module

Replaces Google Drive for document storage. Uploads PDFs to a GCS bucket
and serves them via a backend proxy endpoint.
"""
import os
import logging
import urllib.parse
from io import BytesIO
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

BUCKET_NAME = os.environ.get("FIREBASE_STORAGE_BUCKET", "rapids-platform.firebasestorage.app")

_storage_client_cache = None
_bucket_cache = None


def _get_bucket():
    """Get the GCS bucket, initializing client if needed."""
    global _storage_client_cache, _bucket_cache
    if _bucket_cache is None:
        from google.cloud import storage
        project = os.environ.get("GCP_PROJECT_ID", "rapids-platform")
        _storage_client_cache = storage.Client(project=project)
        _bucket_cache = _storage_client_cache.bucket(BUCKET_NAME)
    return _bucket_cache


def _get_base_url() -> str:
    """Get the base URL for document serving (our own API)."""
    # On Cloud Run, use the service URL; locally, use localhost
    port = os.environ.get("PORT", "8000")
    return os.environ.get("SERVICE_URL", f"http://localhost:{port}")


def upload_pdf_bytes_to_storage(pdf_bytes: bytes, blob_path: str) -> str:
    """
    Upload PDF bytes to Firebase Storage.

    Args:
        pdf_bytes: Raw PDF bytes
        blob_path: Full path in bucket (e.g., "documents/pathology/file.pdf")

    Returns:
        URL string pointing to our document serving endpoint
    """
    bucket = _get_bucket()
    blob = bucket.blob(blob_path)
    blob.upload_from_file(BytesIO(pdf_bytes), content_type="application/pdf")
    # Return a URL via our own serving endpoint (avoids GCS public access issues)
    encoded_path = urllib.parse.quote(blob_path, safe="")
    return f"/api/documents/{encoded_path}"


def upload_and_share_pdf_bytes(
    pdf_bytes: bytes,
    file_name: str,
    folder_id: Optional[str] = None,
) -> Dict[str, str]:
    """
    Upload PDF bytes and return shareable URL.

    Drop-in replacement for drive_uploader.upload_and_share_pdf_bytes().
    Returns same dict shape: {'file_id': blob_path, 'shareable_url': url}
    """
    if folder_id:
        blob_path = f"{folder_id}/{file_name}"
    else:
        blob_path = f"documents/{file_name}"

    url = upload_pdf_bytes_to_storage(pdf_bytes, blob_path)
    logger.info(f"Uploaded {file_name} to Firebase Storage: {blob_path}")
    return {"file_id": blob_path, "shareable_url": url}


def create_or_get_folder(folder_name: str, parent_folder_id: Optional[str] = None) -> str:
    """
    Return a folder path prefix. GCS uses flat namespace with / delimiters.

    Drop-in replacement for drive_uploader.create_or_get_folder().
    Returns a path prefix string instead of a Drive folder ID.
    """
    if parent_folder_id:
        return f"{parent_folder_id}/{folder_name}"
    return f"documents/{folder_name}"


def download_pdf_bytes(blob_path: str) -> bytes:
    """Download PDF bytes from Firebase Storage by blob path."""
    bucket = _get_bucket()
    blob = bucket.blob(blob_path)
    return blob.download_as_bytes()


def download_pdf_bytes_from_url(url: str) -> bytes:
    """
    Download PDF bytes from a Firebase Storage URL or Google Drive URL.

    Handles Firebase Storage paths, URLs, and legacy Google Drive URLs.
    """
    # Our own document endpoint path
    if url.startswith("/api/documents/"):
        blob_path = urllib.parse.unquote(url.replace("/api/documents/", "", 1))
        return download_pdf_bytes(blob_path)

    # Firebase Storage URL
    if "storage.googleapis.com" in url or "firebasestorage.googleapis.com" in url:
        blob_path = _extract_blob_path_from_url(url)
        return download_pdf_bytes(blob_path)

    # Legacy Google Drive URL
    if "drive.google.com" in url:
        return _download_from_drive(url)

    # Direct URL
    import requests
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def _download_from_drive(url: str) -> bytes:
    """Download from Google Drive URL (legacy support)."""
    try:
        from Backend.drive_uploader import download_pdf_bytes_from_drive_url
    except (ModuleNotFoundError, ImportError):
        from drive_uploader import download_pdf_bytes_from_drive_url
    return download_pdf_bytes_from_drive_url(url)


def get_file_metadata_from_url(url: str) -> Dict[str, Any]:
    """
    Get file metadata from a Firebase Storage URL.

    Returns dict with: name, date, drive_url (kept for compat), mime_type, size
    """
    blob_path = None
    if url.startswith("/api/documents/"):
        blob_path = urllib.parse.unquote(url.replace("/api/documents/", "", 1))
    elif "storage.googleapis.com" in url or "firebasestorage.googleapis.com" in url:
        blob_path = _extract_blob_path_from_url(url)

    if blob_path:
        try:
            bucket = _get_bucket()
            blob = bucket.blob(blob_path)
            blob.reload()
            return {
                "name": blob.name.split("/")[-1],
                "date": blob.updated.isoformat() if blob.updated else "",
                "drive_url": f"/api/documents/{urllib.parse.quote(blob_path, safe='')}",
                "mime_type": blob.content_type or "application/pdf",
                "size": blob.size or 0,
            }
        except Exception as e:
            logger.warning(f"Failed to get blob metadata for {blob_path}: {e}")
            return {
                "name": blob_path.split("/")[-1] if blob_path else "unknown",
                "date": "",
                "drive_url": url,
                "mime_type": "application/pdf",
                "size": 0,
            }

    # Legacy Drive URL - delegate
    try:
        from Backend.drive_uploader import get_file_metadata_from_url as drive_metadata
    except (ModuleNotFoundError, ImportError):
        from drive_uploader import get_file_metadata_from_url as drive_metadata
    return drive_metadata(url)


def _extract_blob_path_from_url(url: str) -> str:
    """Extract the blob path from a GCS public URL."""
    # Format: https://storage.googleapis.com/BUCKET/path/to/file.pdf
    if "storage.googleapis.com" in url:
        parts = url.split(f"storage.googleapis.com/{BUCKET_NAME}/", 1)
        if len(parts) == 2:
            return urllib.parse.unquote(parts[1])
    # Format: https://firebasestorage.googleapis.com/v0/b/BUCKET/o/path?alt=media
    if "firebasestorage.googleapis.com" in url:
        import re
        match = re.search(r"/o/([^?]+)", url)
        if match:
            return urllib.parse.unquote(match.group(1))
    return url


def extract_file_id_from_url(url: str) -> str:
    """
    Extract identifier from URL. For GCS URLs returns blob path.
    For Drive URLs returns file ID. Kept for backward compatibility.
    """
    if url.startswith("/api/documents/"):
        return urllib.parse.unquote(url.replace("/api/documents/", "", 1))

    if "storage.googleapis.com" in url or "firebasestorage.googleapis.com" in url:
        return _extract_blob_path_from_url(url)

    # Legacy Drive URL
    try:
        from Backend.drive_uploader import extract_file_id_from_url as drive_extract
    except (ModuleNotFoundError, ImportError):
        from drive_uploader import extract_file_id_from_url as drive_extract
    return drive_extract(url)
