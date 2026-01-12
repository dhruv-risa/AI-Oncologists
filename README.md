# AI Oncologist - Patient Data Extraction System

A comprehensive system for extracting and managing oncology patient data from Electronic Medical Records (EMR) using FHIR API integration, Google Drive, and AI-powered data extraction.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Setup Instructions](#setup-instructions)
- [Running the Application](#running-the-application)
- [How It Works](#how-it-works)
- [Testing Individual Workflows](#testing-individual-workflows)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Security & Privacy](#security--privacy)
- [Troubleshooting](#troubleshooting)

## Overview

The AI Oncologist system automates the extraction and processing of patient data from oncology medical records. It integrates with FHIR APIs to retrieve documents, uploads them to Google Drive, and uses AI to extract structured information including:

- Patient demographics
- Diagnosis and disease status
- Treatment history and timelines
- Laboratory results
- Genomic information
- Pathology reports
- Radiology reports
- Comorbidities and functional status

## Architecture

```
┌─────────────┐
│   Frontend  │  React + TypeScript UI
│  Dashboard  │
└──────┬──────┘
       │
       ↓
┌─────────────┐
│   FastAPI   │  REST API Backend
│   Backend   │
└──────┬──────┘
       │
       ├──→ FHIR API (EMR Integration)
       │
       ├──→ Google Drive API (Document Storage)
       │
       ├──→ AI Extraction (Claude API)
       │
       └──→ SQLite Data Pool (Caching)
```

### Data Flow

1. **Document Retrieval**: Fetch medical documents from FHIR API
2. **Upload to Drive**: Upload PDFs to Google Drive for processing
3. **AI Extraction**: Use Claude AI to extract structured data
4. **Caching**: Store results in SQLite for fast retrieval
5. **API Response**: Return structured JSON data to frontend

## Features

- **Automated Data Extraction**: Extract patient information from unstructured medical documents
- **Multi-Tab Dashboard**: Comprehensive view across diagnosis, treatment, labs, genomics, pathology, and radiology
- **Parallel Processing**: Three extraction pipelines run simultaneously for optimal performance
- **Intelligent Caching**: SQLite-based data pool for instant subsequent loads
- **Test Endpoints**: Isolated test APIs for validating individual workflows
- **Real-time Updates**: RESTful API with CORS support for frontend integration

## Prerequisites

1. **Python**: Version 3.7 or higher
2. **Node.js**: Version 16 or higher (for frontend)
3. **Google Cloud Project**: With Drive API enabled
4. **FHIR API Access**: Credentials for your EMR system
5. **Claude API Access**: For AI-powered data extraction

## Setup Instructions

### 1. Clone the Repository

```bash
cd "/Users/dhruvsaraswat/Desktop/AI Oncologist"
```

### 2. Install Backend Dependencies

```bash
pip install -r requirements.txt
```

The `requirements.txt` includes:
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `google-api-python-client` - Google Drive integration
- `google-auth-oauthlib` - OAuth authentication
- `requests` - HTTP client
- `python-dotenv` - Environment variable management
- `pydantic` - Data validation

### 3. Set Up Sensitive Files

#### 3.1 Google Drive API Credentials (`credentials.json`)

**How to Generate:**

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
   - Save the file as `credentials.json` in the project root:
     ```
     /Users/dhruvsaraswat/Desktop/AI Oncologist/credentials.json
     ```

**First-Time Authentication:**

On your first run, the script will:
- Open a browser window for authentication
- Ask you to select your Google account
- Request permissions to access Google Drive
- Save authentication token in `token.pickle` for future use

#### 3.2 Authentication Token (`token.pickle`)

**Auto-Generated**: This file is created automatically during first-time authentication. You do NOT need to create it manually.

If you need to re-authenticate:
1. Delete `token.pickle`
2. Run the application again
3. Complete the browser-based authentication flow

#### 3.3 Environment Variables (`.env`)

**How to Generate:**

Create a `.env` file in the project root with your FHIR API credentials:

```bash
# Risalabs/FHIR API Credentials
RISALABS_USERNAME=your_username@example.com
RISALABS_PASSWORD=your_password
```

**Security Note**: Never commit this file to version control. It's already included in `.gitignore`.

### 4. Frontend Setup (Optional)

```bash
cd "Frontend/Oncology Patient Dashboard 2"
npm install
```

Create frontend `.env`:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## Running the Application

### Start Backend Server

```bash
cd "/Users/dhruvsaraswat/Desktop/AI Oncologist"
python Backend/app.py
```

You should see:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Start Frontend (Optional)

In a new terminal:

```bash
cd "Frontend/Oncology Patient Dashboard 2"
npm run dev
```

Frontend will be available at: `http://localhost:5173`

### Test the Main Pipeline

```bash
cd Backend
python main.py
```

This will run the complete extraction pipeline for the demo patient (MRN: A2451440).

## How It Works

### 1. Document Retrieval

The system fetches documents from the FHIR API based on:
- **Patient MRN**: Medical Record Number
- **Document Type**: MD notes, lab results, pathology reports, etc.
- **Date Range**: Last 6 months from the most recent document

### 2. Document Processing

**For MD Notes:**
```
FHIR API → PDF Bytes → Upload to Drive → Extract Data
```

**For Lab Results:**
```
FHIR API → Multiple PDFs → Combine into Single PDF → Upload to Drive → Extract Data
```

**For Genomics/Pathology:**
```
FHIR API → Pathology Reports + Molecular Reports + MD Notes → Combine → Upload to Drive → Extract Data
```

### 3. AI Extraction

Uses Claude AI to extract structured information from PDFs:

**Demographics Extraction:**
- Patient Name, MRN, DOB, Age, Gender
- Height, Weight
- Primary Oncologist
- Last Visit Date

**Diagnosis Extraction:**
- Cancer type and histology
- Diagnosis date
- TNM classification and AJCC stage
- Line of therapy
- Metastatic sites
- ECOG status and disease status

**Treatment Extraction:**
- Line of therapy (LOT) information
- Treatment timeline with dates and regimens

**Lab Extraction:**
- Lab values over time
- Trend analysis

**Genomics Extraction:**
- Genetic mutations
- Biomarkers
- NGS panel results

**Pathology Extraction:**
- Pathology summary
- Biomarker results (ER, PR, HER2, PD-L1, etc.)

**Radiology Extraction:**
- Imaging findings
- RECIST measurements
- Disease progression assessment

### 4. Data Caching

All extracted data is stored in SQLite (`Backend/data_pool.db`) for:
- **Fast Retrieval**: Subsequent loads are instant (< 1 second)
- **Reduced API Calls**: No need to re-fetch from FHIR
- **Offline Access**: Data available without external API calls

## Testing Individual Workflows

The system provides dedicated test endpoints that bypass caching and always fetch fresh data. These are useful for:
- Testing specific extraction workflows
- Debugging individual components
- Validating data quality
- Development and QA

### Available Test Endpoints

All test endpoints accept MRN in the request body:

```json
{
  "mrn": "A2451440"
}
```

#### 1. Test Demographics Workflow

```bash
curl -X POST http://localhost:8000/api/test/demographics \
  -H "Content-Type: application/json" \
  -d '{"mrn": "A2451440"}'
```

**Workflow:**
1. Fetch most recent MD note from FHIR
2. Upload to Google Drive
3. Extract demographics information

**Response:**
```json
{
  "success": true,
  "mrn": "A2451440",
  "tab_name": "demographics",
  "workflow_metadata": {
    "document_count": 1,
    "pdf_url": "https://drive.google.com/...",
    "pipeline_stages": ["fetch_md_note", "upload_to_drive", "extract_demographics"]
  },
  "extracted_data": {
    "Patient Name": "John Doe",
    "MRN number": "A2451440",
    "Date of Birth": "1960-05-15",
    "Age": "64",
    "Gender": "Male",
    "Height": "175 cm",
    "Weight": "80 kg",
    "Primary Oncologist": "Dr. Smith",
    "Last Visit": "2024-01-10"
  }
}
```

#### 2. Test Diagnosis Status Workflow

```bash
curl -X POST http://localhost:8000/api/test/diagnosis \
  -H "Content-Type: application/json" \
  -d '{"mrn": "A2451440"}'
```

**Workflow:**
1. Fetch MD note from FHIR
2. Upload to Google Drive
3. Extract diagnosis status

#### 3. Test Comorbidities Workflow

```bash
curl -X POST http://localhost:8000/api/test/comorbidities \
  -H "Content-Type: application/json" \
  -d '{"mrn": "A2451440"}'
```

#### 4. Test Treatment Workflow

```bash
curl -X POST http://localhost:8000/api/test/treatment \
  -H "Content-Type: application/json" \
  -d '{"mrn": "A2451440"}'
```

**Workflow:**
1. Fetch MD note from FHIR
2. Upload to Google Drive
3. Extract treatment information (LOT and timeline)

#### 5. Test Diagnosis Tab Workflow

```bash
curl -X POST http://localhost:8000/api/test/diagnosis-tab \
  -H "Content-Type: application/json" \
  -d '{"mrn": "A2451440"}'
```

**Workflow:**
1. Fetch MD note from FHIR
2. Upload to Google Drive
3. Extract diagnosis tab info (header, evolution timeline, footer)

#### 6. Test Lab Workflow

```bash
curl -X POST http://localhost:8000/api/test/lab \
  -H "Content-Type: application/json" \
  -d '{"mrn": "A2451440"}'
```

**Workflow:**
1. Fetch all lab results from last 6 months
2. Combine PDFs into single file
3. Upload to Google Drive
4. Extract lab information

#### 7. Test Genomics Workflow

```bash
curl -X POST http://localhost:8000/api/test/genomics \
  -H "Content-Type: application/json" \
  -d '{"mrn": "A2451440"}'
```

**Workflow:**
1. Fetch pathology reports + molecular reports + MD notes
2. Combine all into single PDF
3. Upload to Google Drive
4. Extract genomic information

#### 8. Test Pathology Workflow

```bash
curl -X POST http://localhost:8000/api/test/pathology \
  -H "Content-Type: application/json" \
  -d '{"mrn": "A2451440"}'
```

**Workflow:**
1. Fetch pathology reports + molecular reports + MD notes
2. Combine all into single PDF
3. Upload to Google Drive
4. Extract pathology information (summary and biomarkers)

#### 9. Test Radiology Workflow

```bash
curl -X POST http://localhost:8000/api/test/radiology \
  -H "Content-Type: application/json" \
  -d '{"mrn": "A2451440"}'
```

**Workflow:**
1. Fetch individual radiology reports from FHIR
2. For each report, combine with MD notes
3. Upload to Google Drive
4. Extract radiology details (summary and RECIST)

#### 10. Test Complete Patient Workflow

```bash
curl -X POST http://localhost:8000/api/test/patient-all \
  -H "Content-Type: application/json" \
  -d '{"mrn": "A2451440"}'
```

**Workflow:**
Runs all 3 parallel pipelines:
1. Patient Data Pipeline (demographics, diagnosis, treatment, etc.)
2. Lab Results Pipeline
3. Genomics & Pathology Pipeline
4. Individual Reports (pathology and radiology)

**Note:** This ALWAYS bypasses cache for testing purposes.

### Test Response Format

All test endpoints return a consistent format:

```json
{
  "success": true,
  "mrn": "A2451440",
  "tab_name": "workflow_name",
  "workflow_metadata": {
    "document_count": 5,
    "pdf_url": "https://drive.google.com/...",
    "file_id": "1abc...",
    "pipeline_stages": ["stage1", "stage2", "stage3"]
  },
  "extracted_data": {
    // Extracted information specific to the workflow
  }
}
```

## API Documentation

### Production Endpoints

#### Get All Patient Data (Cached)

```bash
POST /api/patient/all
Content-Type: application/json

{
  "mrn": "A2451440"
}
```

Returns complete patient data. Uses cache if available.

**First Load**: 10-30 seconds (fetches from FHIR)
**Subsequent Loads**: < 1 second (from cache)

#### Individual Component Endpoints

- `POST /api/patient/demographics` - Get demographics only
- `POST /api/patient/diagnosis-status` - Get diagnosis status only
- `POST /api/patient/comorbidities` - Get comorbidities only

#### Tab Endpoints

- `POST /api/tabs/treatment` - Get treatment tab info
- `POST /api/tabs/diagnosis` - Get diagnosis tab info
- `POST /api/tabs/lab` - Get lab tab info
- `POST /api/tabs/genomics` - Get genomics info
- `POST /api/tabs/pathology` - Get pathology info
- `POST /api/tabs/pathology_reports_extraction` - Get individual pathology report URLs
- `POST /api/tabs/pathology_details_extraction` - Get detailed pathology info (lazy loaded)
- `POST /api/tabs/radiology_reports_extraction` - Get individual radiology report URLs
- `POST /api/tabs/radiology_reports` - Get cached radiology reports with details

#### Data Pool Management

- `GET /api/pool/patients` - List all cached patients
- `GET /api/pool/patient/{mrn}` - Get cached patient data
- `GET /api/pool/patient/{mrn}/exists` - Check if patient is cached
- `DELETE /api/pool/patient/{mrn}` - Delete patient from cache
- `DELETE /api/pool/clear` - Clear entire cache

### Interactive API Documentation

FastAPI provides automatic interactive documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Project Structure

```
AI Oncologist/
├── credentials.json          # Google OAuth credentials (you create this)
├── token.pickle             # Auto-generated auth token (do not create manually)
├── .env                     # FHIR API credentials (you create this)
├── .gitignore              # Excludes sensitive files
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── SETUP_GUIDE.md         # Detailed setup instructions
├── QUICK_START.md         # Frontend integration guide
├── INTEGRATION_GUIDE.md   # Full integration documentation
├── GENOMICS_CHANGES_SUMMARY.md  # Genomics extraction details
│
├── Backend/
│   ├── app.py                    # FastAPI application (main server)
│   ├── main.py                   # Data extraction pipelines
│   ├── bytes_extractor.py        # FHIR document fetching
│   ├── drive_uploader.py         # Google Drive integration
│   ├── documents_reference.py    # FHIR authentication
│   ├── data_pool.py              # SQLite caching layer
│   ├── data_pool.db              # SQLite database (auto-created)
│   ├── logger_config.py          # Logging configuration
│   │
│   └── Utils/
│       ├── components/
│       │   ├── parser.py                    # AI extraction utilities
│       │   ├── patient_demographics.py      # Demographics extraction
│       │   └── patient_diagnosis_status.py  # Diagnosis extraction
│       │
│       └── Tabs/
│           ├── comorbidities.py      # Comorbidities extraction
│           ├── diagnosis_tab.py      # Diagnosis tab extraction
│           ├── treatment_tab.py      # Treatment tab extraction
│           ├── lab_tab.py            # Lab results extraction
│           ├── genomics_tab.py       # Genomics extraction
│           ├── pathology_tab.py      # Pathology extraction
│           ├── radiology_tab.py      # Radiology extraction
│           ├── llmparser.py          # LLM parsing utilities
│           ├── lab_postprocessor.py  # Lab data post-processing
│           └── lab_chart_helper.py   # Lab chart generation
│
├── Frontend/
│   └── Oncology Patient Dashboard 2/
│       ├── src/
│       │   ├── services/
│       │   │   └── api.ts                # Backend API client
│       │   ├── contexts/
│       │   │   └── PatientContext.tsx    # Patient data state management
│       │   ├── components/
│       │   │   ├── MRNInput.tsx          # MRN input screen
│       │   │   ├── PatientHeader.tsx     # Patient header component
│       │   │   ├── DiseaseSummary.tsx    # Disease summary component
│       │   │   └── tabs/
│       │   │       ├── DiagnosisTab.tsx
│       │   │       ├── TreatmentTab.tsx
│       │   │       ├── LabsTab.tsx
│       │   │       ├── GenomicsTab.tsx
│       │   │       ├── PathologyTab.tsx
│       │   │       └── RadiologyTab.tsx
│       │   └── App.tsx
│       ├── .env                    # Frontend configuration
│       ├── package.json
│       └── README.md
│
└── Onco_EMR_Files/              # Sample EMR files for testing
```

## Security & Privacy

### Sensitive Files

The following files contain sensitive information and are excluded from version control:

1. **`credentials.json`**: Google OAuth credentials
2. **`token.pickle`**: Google authentication token
3. **`.env`**: FHIR API credentials
4. **`.DS_Store`**: macOS system files
5. **`venv/`**: Python virtual environment
6. **`data_pool.db`**: SQLite database with patient data

### Data Privacy Considerations

- **HIPAA Compliance**: Ensure compliance with HIPAA regulations
- **PHI Protection**: Patient Health Information is stored in Google Drive and local cache
- **Access Control**: Implement proper authentication and authorization
- **Audit Logging**: All API calls are logged
- **Data Encryption**: Use HTTPS in production
- **Google Drive Security**: PDFs are made publicly accessible - ensure compliance with your organization's policies

### Production Checklist

Before deploying to production:

- [ ] Configure CORS to allow only specific origins
- [ ] Enable HTTPS/SSL
- [ ] Implement user authentication
- [ ] Add audit logging
- [ ] Set up data retention policies
- [ ] Configure Google Drive folder permissions
- [ ] Review PHI handling procedures
- [ ] Implement rate limiting
- [ ] Set up monitoring and alerts
- [ ] Configure backup procedures

## Troubleshooting

### Backend Issues

#### "credentials.json not found"

**Problem**: Google OAuth credentials file is missing.

**Solution**:
1. Follow [Setup Instructions](#3-set-up-sensitive-files) to create `credentials.json`
2. Place it in the project root directory
3. Ensure the file name is exactly `credentials.json`

#### "Authentication failed" / "Invalid credentials"

**Problem**: Google authentication token is invalid or expired.

**Solution**:
```bash
rm token.pickle
python Backend/app.py
# Complete browser authentication flow
```

#### "Permission denied" from Google Drive API

**Problem**: Google Drive API is not enabled or OAuth scopes are incorrect.

**Solution**:
1. Go to Google Cloud Console
2. Enable Google Drive API
3. Verify OAuth scopes include Drive access
4. Re-download `credentials.json`
5. Delete `token.pickle` and re-authenticate

#### "No module named 'uvicorn'" or other import errors

**Problem**: Python dependencies not installed.

**Solution**:
```bash
pip install -r requirements.txt
```

#### ".env file not found" or "RISALABS_USERNAME not set"

**Problem**: Environment variables file is missing.

**Solution**:
1. Create `.env` file in project root
2. Add your FHIR credentials:
```bash
RISALABS_USERNAME=your_username@example.com
RISALABS_PASSWORD=your_password
```

### Frontend Issues

#### "Failed to fetch" error in browser console

**Problem**: Frontend cannot connect to backend.

**Solution**:
1. Ensure backend is running on port 8000
2. Check `.env` in frontend folder has correct URL:
   ```
   VITE_API_BASE_URL=http://localhost:8000
   ```
3. Restart frontend after changing `.env`:
   ```bash
   npm run dev
   ```

#### First load is very slow (10-30 seconds)

**This is normal!** First load performs:
- FHIR API calls
- PDF combination
- Google Drive uploads
- AI extraction

Subsequent loads are instant (< 1 second) thanks to caching.

### Data Extraction Issues

#### AI extraction returns null values

**Problem**: PDF format may not match expected structure.

**Solution**:
1. Check PDF manually to verify data exists
2. Review extraction logs for errors
3. Try test endpoints to isolate the issue
4. Check Claude API credentials and quotas

#### "No documents found for MRN"

**Problem**: Patient MRN doesn't exist in FHIR or has no documents.

**Solution**:
1. Verify MRN is correct
2. Check FHIR API credentials
3. Try demo patient (A2451440)
4. Check date range - system looks for documents from last 6 months

### Cache Issues

#### Data not updating after changes

**Problem**: Old data is cached.

**Solution**:
```bash
# Clear specific patient
curl -X DELETE http://localhost:8000/api/pool/patient/A2451440

# Or clear entire cache
curl -X DELETE http://localhost:8000/api/pool/clear
```

## Support & Documentation

For more detailed information, refer to:

- **[SETUP_GUIDE.md](SETUP_GUIDE.md)**: Detailed Google Drive API setup
- **[QUICK_START.md](QUICK_START.md)**: Frontend integration guide
- **[INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)**: Complete integration documentation
- **[GENOMICS_CHANGES_SUMMARY.md](GENOMICS_CHANGES_SUMMARY.md)**: Genomics extraction details

## License

Copyright © 2024. All rights reserved.

## Version

**Version 1.0** - Initial Release
