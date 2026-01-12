# Patient PDF Processing - Setup Guide

This guide walks you through setting up and using the complete PDF processing pipeline that uploads PDFs to Google Drive and extracts patient information.

## Overview

The pipeline performs the following steps:
1. Uploads a PDF to Google Drive
2. Makes it publicly accessible
3. Extracts patient demographics using AI
4. Extracts diagnosis and disease status using AI
5. Validates and evaluates the extracted JSON data

## Prerequisites

1. Python 3.7 or higher
2. Google Cloud Project with Drive API enabled
3. OAuth 2.0 credentials from Google Cloud Console

## Setup Instructions

### Step 1: Install Dependencies

```bash
cd "/Users/dhruvsaraswat/Desktop/AI Oncologist"
pip install -r requirements.txt
```

### Step 2: Set Up Google Drive API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)

2. Create a new project or select an existing one

3. Enable the Google Drive API:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Drive API"
   - Click "Enable"

4. Create OAuth 2.0 Credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Desktop app" as the application type
   - Give it a name (e.g., "AI Oncologist PDF Uploader")
   - Click "Create"

5. Download the credentials:
   - Click the download button next to your newly created OAuth client
   - Save the file as `credentials.json` in your project root directory:
     ```
     /Users/dhruvsaraswat/Desktop/AI Oncologist/credentials.json
     ```

### Step 3: First-Time Authentication

On your first run, the script will open a browser window for authentication:
- Select your Google account
- Grant permissions to access Google Drive
- The credentials will be saved in `token.pickle` for future use

## Usage

### Basic Usage - Upload and Process PDF

```bash
cd "/Users/dhruvsaraswat/Desktop/AI Oncologist"
python Backend/process_patient_pdf.py /path/to/patient_report.pdf
```

### Save Results to JSON File

```bash
python Backend/process_patient_pdf.py /path/to/patient_report.pdf --save-results
```

### Use Existing Drive URL (Skip Upload)

If you already have a PDF on Google Drive:

```bash
python Backend/process_patient_pdf.py dummy.pdf --skip-upload --url "https://drive.google.com/file/d/FILE_ID/view"
```

### Save Results to Specific File

```bash
python Backend/process_patient_pdf.py patient_report.pdf --save-results --output results.json
```

## Command-Line Options

- `<path_to_pdf>` - Required: Path to the PDF file to process
- `--skip-upload` - Skip uploading and use an existing Drive URL
- `--url <url>` - Google Drive URL to use (requires --skip-upload)
- `--save-results` - Save the complete results to a JSON file
- `--output <path>` - Specify output file path for results

## Output

The script provides:

1. **Console Output**: Detailed progress and results printed to terminal
   - Upload status
   - Extracted demographics (JSON)
   - Extracted diagnosis data (JSON)
   - Validation results for both extractions
   - Summary statistics

2. **JSON File** (if `--save-results` is used):
   ```json
   {
     "success": true,
     "pdf_path": "/path/to/file.pdf",
     "pdf_url": "https://drive.google.com/...",
     "demographics": { ... },
     "diagnosis": { ... },
     "validation": {
       "demographics": { ... },
       "diagnosis": { ... }
     }
   }
   ```

## Validation

The script automatically validates extracted data:

- **Fields Present**: Which expected fields were found
- **Fields Missing**: Which expected fields are missing
- **Fields Null**: Which fields have null/empty values
- **Warnings**: Any data quality issues
- **Errors**: Any processing errors

### Expected Demographics Fields
- Patient Name
- MRN number
- Date of Birth
- Age
- Gender
- Height
- Weight
- Primary Oncologist
- Last Visit date

### Expected Diagnosis Fields
- cancer_type
- histology
- diagnosis_date
- tnm_classification
- ajcc_stage
- line_of_therapy
- metastatic_sites
- ecog_status
- disease_status

## Standalone Module Usage

### Upload PDF Only

```bash
python Backend/Utils/drive_uploader.py /path/to/file.pdf
```

### Extract Demographics Only

```python
from Backend.Utils.components.patient_demographics import extract_patient_demographics

demographics = extract_patient_demographics("https://drive.google.com/file/d/FILE_ID/view")
print(demographics)
```

### Extract Diagnosis Only

```python
from Backend.Utils.components.patient_diagnosis_status import extract_diagnosis_status

diagnosis = extract_diagnosis_status("https://drive.google.com/file/d/FILE_ID/view")
print(diagnosis)
```

## Troubleshooting

### "credentials.json not found"
- Make sure you've downloaded OAuth credentials from Google Cloud Console
- Place the file in the project root directory

### "Authentication failed"
- Delete `token.pickle` and try again
- Ensure your Google account has Drive access

### "Permission denied" errors
- Check that the Google Drive API is enabled in your project
- Verify OAuth scopes in credentials.json

### Import errors
- Make sure all dependencies are installed: `pip install -r requirements.txt`
- Check that you're running from the correct directory

### API extraction fails
- Verify the PDF URL is accessible
- Check that the file is publicly readable
- Ensure you have valid API credentials for the extraction service

## File Structure

```
AI Oncologist/
├── credentials.json          # Google OAuth credentials (you create this)
├── token.pickle             # Auto-generated auth token
├── requirements.txt         # Python dependencies
├── SETUP_GUIDE.md          # This file
├── Backend/
│   ├── process_patient_pdf.py    # Main orchestration script
│   └── Utils/
│       ├── drive_uploader.py     # Google Drive upload module
│       └── components/
│           ├── patient_demographics.py
│           └── patient_diagnosis_status.py
```

## Security Notes

- `credentials.json` and `token.pickle` contain sensitive authentication data
- Do not commit these files to version control
- Add them to `.gitignore`
- The uploaded PDFs are made publicly accessible on Google Drive
- Ensure compliance with HIPAA and data privacy regulations

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Verify all setup steps were completed
3. Check that dependencies are correctly installed
