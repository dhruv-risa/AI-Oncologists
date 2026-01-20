"""
Google Drive PDF Uploader Module

Handles uploading PDF files to Google Drive, making them public,
and generating shareable links.
"""
import os
import pickle
import base64
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from io import BytesIO
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Cache for authenticated service instance to avoid repeated authentication
_drive_service_cache = None


def authenticate_drive(force_refresh=False):
    """
    Authenticate with Google Drive API.

    Args:
        force_refresh (bool): Force re-authentication even if cached service exists

    Returns:
        service: Authenticated Google Drive service instance

    Notes:
        - Service instance is cached after first authentication to avoid repeated token refreshes
        - Supports two authentication modes:
          1. Environment variables (production): Uses GOOGLE_CREDENTIALS_BASE64 and GOOGLE_TOKEN_BASE64
          2. File-based (local dev): Uses credentials.json and token.pickle files
        - First run in file-based mode will open browser for OAuth authentication
        - Credentials are saved in token.pickle for subsequent runs
        - In production, credentials should be stored as base64-encoded environment variables
    """
    global _drive_service_cache

    # Return cached service if available and not forcing refresh
    if _drive_service_cache is not None and not force_refresh:
        print("Using cached Google Drive service")
        return _drive_service_cache

    creds = None
    # Get project root directory (1 level up from Backend folder)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    token_path = os.path.join(project_root, 'token.pickle')
    credentials_path = os.path.join(project_root, 'credentials.json')

    # Check if environment variables are set (production mode)
    env_credentials_b64 = os.getenv('GOOGLE_CREDENTIALS_BASE64')
    env_token_b64 = os.getenv('GOOGLE_TOKEN_BASE64')

    # PRODUCTION MODE: Use base64-encoded credentials from environment variables
    if env_token_b64:
        print("Using base64-encoded token from environment variable")
        try:
            # Decode base64 token and load credentials
            token_bytes = base64.b64decode(env_token_b64)
            creds = pickle.loads(token_bytes)
            print("Successfully loaded credentials from environment variable")
        except Exception as e:
            print(f"Error decoding token from environment variable: {e}")
            creds = None

    # LOCAL DEV MODE: Use file-based credentials
    else:
        print("Using file-based authentication (local development mode)")
        # Load existing credentials if available
        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
                print("Loaded existing token.pickle")

    # If credentials don't exist or are invalid, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Token expired, refreshing...")
            creds.refresh(Request())
            print("Token refreshed successfully")

            # Save refreshed token back to file (only in local dev mode)
            if not env_token_b64 and os.path.exists(token_path):
                with open(token_path, 'wb') as token:
                    pickle.dump(creds, token)
                    print("Saved refreshed token to token.pickle")
        else:
            # Need to authenticate from scratch
            print("No valid credentials found, starting OAuth flow...")

            # Try to load credentials.json from environment variable first
            if env_credentials_b64:
                print("Using credentials from GOOGLE_CREDENTIALS_BASE64 environment variable")
                try:
                    credentials_json = base64.b64decode(env_credentials_b64).decode('utf-8')
                    credentials_data = json.loads(credentials_json)

                    # Create a temporary file for the OAuth flow
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                        json.dump(credentials_data, temp_file)
                        temp_credentials_path = temp_file.name

                    flow = InstalledAppFlow.from_client_secrets_file(temp_credentials_path, SCOPES)
                    creds = flow.run_local_server(port=0)

                    # Clean up temp file
                    os.unlink(temp_credentials_path)
                except Exception as e:
                    raise Exception(f"Error loading credentials from environment variable: {e}")

            # Fall back to file-based credentials.json
            elif os.path.exists(credentials_path):
                print(f"Using credentials from {credentials_path}")
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            else:
                raise FileNotFoundError(
                    "credentials.json not found and GOOGLE_CREDENTIALS_BASE64 not set.\n"
                    "For local development:\n"
                    "1. Go to https://console.cloud.google.com/\n"
                    "2. Create a project or select existing one\n"
                    "3. Enable Google Drive API\n"
                    "4. Create OAuth 2.0 credentials (Desktop app)\n"
                    "5. Download credentials.json and place it in the project root\n\n"
                    "For production:\n"
                    "1. Encode credentials.json: base64 credentials.json\n"
                    "2. Set GOOGLE_CREDENTIALS_BASE64 environment variable\n"
                    "3. Encode token.pickle: base64 token.pickle\n"
                    "4. Set GOOGLE_TOKEN_BASE64 environment variable"
                )

            # Save credentials for next run (only in local dev mode)
            if not env_token_b64:
                with open(token_path, 'wb') as token:
                    pickle.dump(creds, token)
                    print("Saved new token to token.pickle")

    service = build('drive', 'v3', credentials=creds)
    print("Google Drive service authenticated successfully")

    # Cache the service for future calls
    _drive_service_cache = service

    return service


# def upload_pdf_to_drive(file_path, folder_id=None):
#     """
#     Upload a PDF file to Google Drive.

#     Args:
#         file_path (str): Local path to the PDF file
#         folder_id (str, optional): Google Drive folder ID to upload to

#     Returns:
#         str: File ID of the uploaded file

#     Raises:
#         FileNotFoundError: If the file doesn't exist
#         Exception: If upload fails
#     """
#     if not os.path.exists(file_path):
#         raise FileNotFoundError(f"File not found: {file_path}")

#     if not file_path.lower().endswith('.pdf'):
#         raise ValueError("File must be a PDF")

#     service = authenticate_drive()

#     file_name = os.path.basename(file_path)
#     file_metadata = {
#         'name': file_name,
#         'mimeType': 'application/pdf'
#     }

#     if folder_id:
#         file_metadata['parents'] = [folder_id]

#     media = MediaFileUpload(file_path, mimetype='application/pdf', resumable=True)

#     try:
#         file = service.files().create(
#             body=file_metadata,
#             media_body=media,
#             fields='id'
#         ).execute()

#         file_id = file.get('id')
#         print(f"File uploaded successfully. File ID: {file_id}")
#         return file_id

#     except Exception as e:
#         raise Exception(f"Failed to upload file: {str(e)}")


def upload_pdf_bytes_to_drive(pdf_bytes, file_name, folder_id=None):
    """
    Upload PDF bytes directly to Google Drive without saving to local file.

    Args:
        pdf_bytes (bytes): PDF content as bytes
        file_name (str): Name for the uploaded file (should end with .pdf)
        folder_id (str, optional): Google Drive folder ID to upload to

    Returns:
        str: File ID of the uploaded file

    Raises:
        ValueError: If file_name doesn't end with .pdf
        Exception: If upload fails
    """
    if not file_name.lower().endswith('.pdf'):
        raise ValueError("File name must end with .pdf")

    service = authenticate_drive()

    file_metadata = {
        'name': file_name,
        'mimeType': 'application/pdf'
    }

    if folder_id:
        file_metadata['parents'] = [folder_id]

    # Create a file-like object from bytes
    pdf_stream = BytesIO(pdf_bytes)
    media = MediaIoBaseUpload(
        pdf_stream,
        mimetype='application/pdf',
        resumable=True
    )

    try:
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        file_id = file.get('id')
        print(f"File uploaded successfully. File ID: {file_id}")
        return file_id

    except Exception as e:
        raise Exception(f"Failed to upload file: {str(e)}")


def make_file_public(file_id):
    """
    Make a Google Drive file publicly accessible.

    Args:
        file_id (str): Google Drive file ID

    Returns:
        bool: True if successful

    Raises:
        Exception: If permission setting fails
    """
    service = authenticate_drive()

    try:
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }

        service.permissions().create(
            fileId=file_id,
            body=permission
        ).execute()

        print(f"File {file_id} is now publicly accessible")
        return True

    except Exception as e:
        raise Exception(f"Failed to make file public: {str(e)}")


def create_or_get_folder(folder_name, parent_folder_id=None):
    """
    Create a new folder in Google Drive or get existing folder by name.

    Args:
        folder_name (str): Name of the folder to create/get
        parent_folder_id (str, optional): Parent folder ID to create this folder in

    Returns:
        str: Folder ID of the created or existing folder

    Raises:
        Exception: If folder creation fails
    """
    service = authenticate_drive()

    try:
        # Search for existing folder
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_folder_id:
            query += f" and '{parent_folder_id}' in parents"

        response = service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()

        folders = response.get('files', [])

        if folders:
            folder_id = folders[0]['id']
            print(f"Found existing folder '{folder_name}' with ID: {folder_id}")
            return folder_id

        # Create new folder if not found
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }

        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]

        folder = service.files().create(
            body=file_metadata,
            fields='id'
        ).execute()

        folder_id = folder.get('id')
        print(f"Created new folder '{folder_name}' with ID: {folder_id}")
        return folder_id

    except Exception as e:
        raise Exception(f"Failed to create/get folder: {str(e)}")


def get_shareable_link(file_id):
    """
    Get the shareable link for a Google Drive file.

    Args:
        file_id (str): Google Drive file ID

    Returns:
        str: Shareable URL in the format suitable for the extraction functions

    Raises:
        Exception: If link generation fails
    """
    service = authenticate_drive()

    try:
        file = service.files().get(
            fileId=file_id,
            fields='webViewLink, webContentLink'
        ).execute()

        # Return the webViewLink which is the standard shareable link format
        link = file.get('webViewLink')
        print(f"Shareable link: {link}")
        return link

    except Exception as e:
        raise Exception(f"Failed to get shareable link: {str(e)}")


def upload_and_share_pdf_bytes(pdf_bytes, file_name, folder_id=None):
    """
    Complete workflow: Upload PDF bytes directly, make public, get shareable link.

    Args:
        pdf_bytes (bytes): PDF content as bytes
        file_name (str): Name for the uploaded file (should end with .pdf)
        folder_id (str, optional): Google Drive folder ID to upload to

    Returns:
        dict: Contains file_id and shareable_url

    Raises:
        Exception: If any step fails
    """
    print(f"Starting upload process for: {file_name} ({len(pdf_bytes)} bytes)")

    # Step 1: Upload the file from bytes
    file_id = upload_pdf_bytes_to_drive(pdf_bytes, file_name, folder_id)

    # Step 2: Make it public
    make_file_public(file_id)

    # Step 3: Get shareable link
    shareable_url = get_shareable_link(file_id)

    return {
        'file_id': file_id,
        'shareable_url': shareable_url
    }


# def upload_and_share_pdf(file_path, folder_id=None):
#     """
#     Complete workflow: Upload PDF, make it public, and get shareable link.

#     Args:
#         file_path (str): Local path to the PDF file
#         folder_id (str, optional): Google Drive folder ID to upload to

#     Returns:
#         dict: Contains file_id and shareable_url

#     Raises:
#         Exception: If any step fails
#     """
#     print(f"Starting upload process for: {file_path}")

#     # Step 1: Upload the file
#     file_id = upload_pdf_to_drive(file_path, folder_id)

#     # Step 2: Make it public
#     make_file_public(file_id)

#     # Step 3: Get shareable link
#     shareable_url = get_shareable_link(file_id)

#     return {
#         'file_id': file_id,
#         'shareable_url': shareable_url
#     }


# def main():
#     """Main function for standalone testing."""
#     import sys

#     if len(sys.argv) < 2:
#         print("Usage: python drive_uploader.py <path_to_pdf>")
#         print("Example: python drive_uploader.py /path/to/document.pdf")
#         sys.exit(1)

#     pdf_path = sys.argv[1]

#     try:
#         result = upload_and_share_pdf_bytes(pdf_path)
#         print("\n" + "="*50)
#         print("Upload Complete!")
#         print("="*50)
#         print(f"File ID: {result['file_id']}")
#         print(f"Shareable URL: {result['shareable_url']}")
#         print("="*50)
#     except Exception as e:
#         print(f"Error: {str(e)}")
#         sys.exit(1)


# if __name__ == "__main__":
#     main()
