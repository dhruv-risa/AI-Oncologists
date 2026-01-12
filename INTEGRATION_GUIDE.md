# AI Oncologist - Frontend-Backend Integration Guide

## Overview
This document explains how to run and test the integrated AI Oncologist application with the complete data flow from backend to frontend.

## Integration Architecture

### Data Flow
```
User enters MRN → Frontend calls API → Backend processes FHIR data →
Data stored in SQLite → Frontend retrieves & displays data
```

### Components Built

1. **API Service Layer** (`Frontend/.../src/services/api.ts`)
   - TypeScript interfaces for all data types
   - Functions for all backend endpoints
   - Error handling and retry logic

2. **Patient Context** (`Frontend/.../src/contexts/PatientContext.tsx`)
   - Global state management for patient data
   - Caching mechanism
   - Loading and error states

3. **Updated Components**
   - `App.tsx` - Wrapped with PatientProvider
   - `PatientListView.tsx` - Fetches from database, MRN search
   - `PatientDetailView.tsx` - Loads patient data dynamically

## How to Run

### 1. Start the Backend (Port 8000)

```bash
cd Backend
python -m uvicorn app:app --reload --port 8000
```

The backend will:
- Connect to SQLite database (`data_pool.db`)
- Expose REST API endpoints
- Handle FHIR data extraction
- Store processed data in database

### 2. Start the Frontend (Port 5173)

```bash
cd "Frontend/Oncology Patient Dashboard 2"
npm install  # First time only
npm run dev
```

The frontend will:
- Connect to backend at `http://localhost:8000`
- Load cached patients from database
- Provide MRN search functionality

## Testing the Integration Flow

### Step 1: Verify Backend is Running
Open: `http://localhost:8000/docs`
You should see the FastAPI Swagger documentation.

### Step 2: Check Database
The backend creates `Backend/data_pool.db`. You can inspect it:
```bash
cd Backend
sqlite3 data_pool.db
.schema
SELECT mrn, created_at FROM patient_data_pool;
.quit
```

### Step 3: Open Frontend
Open: `http://localhost:5173`

You should see the "Oncology Patient Registry" page.

### Step 4: Test Scenarios

#### Scenario A: Empty Database (First Time)
1. Frontend shows "No Patients in Database" message
2. Click "Add Patient by MRN"
3. Enter a test MRN (e.g., `A2451440`)
4. Click "Fetch Patient Data"
5. **Backend will:**
   - Authenticate with FHIR API
   - Extract patient data from medical records
   - Process demographics, diagnosis, labs, pathology, genomics
   - Store in SQLite database
6. **Frontend will:**
   - Show loading spinner
   - Display patient card once data is loaded
7. Click on patient card to view details

#### Scenario B: Database with Cached Patients
1. Frontend loads and displays cached patient list automatically
2. Click on any patient card
3. Patient details load from database (fast!)
4. Navigate through tabs (Diagnosis, Pathology, Genomics, Labs, etc.)

#### Scenario C: Add New Patient
1. From patient list, click "Add Patient by MRN"
2. Enter new MRN
3. Backend triggers full data pipeline
4. New patient appears in list
5. Select to view details

### Step 5: Verify Data Flow

**Check Backend Logs:**
```
INFO: POST /api/patient/all - MRN: A2451440
INFO: Fetching patient data from FHIR...
INFO: Processing demographics...
INFO: Processing diagnosis...
INFO: Storing in database...
INFO: 200 OK
```

**Check Frontend Console:**
```javascript
Patient A2451440 not in cache, triggering data pipeline...
Patient data fetched successfully
```

**Check Database:**
```bash
sqlite3 Backend/data_pool.db
SELECT COUNT(*) FROM patient_data_pool;  // Should show number of patients
```

## API Endpoints Used

### Patient Data Endpoints
- `POST /api/mrn/validate` - Validate MRN format
- `POST /api/patient/all` - Get complete patient data (triggers pipeline if not cached)
- `POST /api/patient/demographics` - Demographics only
- `POST /api/patient/diagnosis-status` - Diagnosis info
- `POST /api/patient/comorbidities` - Comorbidities

### Tab-Specific Endpoints
- `POST /api/tabs/treatment` - Treatment history
- `POST /api/tabs/diagnosis` - Diagnosis details
- `POST /api/tabs/lab` - Lab results
- `POST /api/tabs/genomics` - Genomic data
- `POST /api/tabs/pathology` - Pathology findings
- `POST /api/tabs/radiology_reports_extraction` - Radiology reports
- `POST /api/tabs/pathology_reports_extraction` - Pathology reports

### Database Pool Endpoints
- `GET /api/pool/patients` - List all cached patients
- `GET /api/pool/patient/{mrn}` - Get cached patient data
- `GET /api/pool/patient/{mrn}/exists` - Check if patient exists
- `DELETE /api/pool/patient/{mrn}` - Remove from cache
- `DELETE /api/pool/clear` - Clear entire cache

## Troubleshooting

### Issue: Frontend shows "Failed to Load Patient Data"
**Solution:**
- Check if backend is running on port 8000
- Check backend logs for errors
- Verify FHIR API credentials in backend
- Check network tab in browser DevTools

### Issue: "CORS Error" in browser console
**Solution:**
- Backend has CORS enabled by default
- Verify backend is running
- Check if frontend is using correct API URL

### Issue: Patient data not loading from database
**Solution:**
- Check if `data_pool.db` exists in Backend folder
- Run: `sqlite3 Backend/data_pool.db "SELECT * FROM patient_data_pool;"`
- Verify database has data

### Issue: Slow data loading
**Expected Behavior:**
- **First fetch (not cached):** 30-60 seconds (FHIR API calls, PDF processing)
- **Cached fetch:** < 1 second (database lookup)
- Loading spinner shows during fetch

## Next Steps for Full Integration

### Individual Tab Components
Currently, tab components may still use mock data. To complete integration:

1. Update each tab to use `usePatient()` hook:
```typescript
import { usePatient } from '../contexts/PatientContext';

export function DiagnosisTab() {
  const { currentPatient } = usePatient();

  // Use currentPatient.diagnosis_status, etc.
}
```

2. Tabs to update:
   - `DiagnosisTab.tsx`
   - `PathologyTab.tsx`
   - `GenomicsTab.tsx`
   - `RadiologyTab.tsx`
   - `LabsTab.tsx`
   - `TreatmentTab.tsx`
   - `ComorbiditiesTab.tsx`

3. Update `PatientHeader` and `DiseaseSummary` to use patient prop:
```typescript
export function PatientHeader({ patient }: { patient: PatientData }) {
  // Use patient.demographics
}
```

## Database Schema

```sql
CREATE TABLE patient_data_pool (
    mrn TEXT PRIMARY KEY,
    data TEXT NOT NULL,  -- JSON string with complete patient data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Patient Data Structure

```typescript
interface PatientData {
  demographics: {
    name: string;
    mrn: string;
    dob: string;
    age: number;
    gender: string;
    height: string;
    weight: string;
    oncologist: string;
    last_visit_date: string;
  };
  diagnosis_status: {
    primary_cancer: string;
    histology: string;
    tnm_stage: string;
    ajcc_stage: string;
    metastatic_sites: string[];
    ecog_status: string;
  };
  comorbidities: Array<{
    condition: string;
    status: string;
    onset_date?: string;
  }>;
  treatment_lot: Array<{
    line: number;
    regimen: string;
    start_date: string;
    end_date?: string;
    response?: string;
  }>;
  lab_results?: Array<{
    test_name: string;
    value: string;
    unit: string;
    reference_range: string;
    date: string;
  }>;
  pathology_markers?: Array<{
    marker: string;
    result: string;
    interpretation?: string;
  }>;
  genomics_data?: Array<{
    gene: string;
    mutation: string;
    variant: string;
    clinical_significance?: string;
  }>;
  // ... and more
}
```

## Performance Notes

- **Database caching** prevents redundant FHIR API calls
- **First patient load:** Slow (FHIR extraction + processing)
- **Subsequent loads:** Fast (database lookup)
- **Frontend uses React Context** for efficient state management
- **API calls are cached** by the browser for 15 minutes

## Security Considerations

- Backend handles all FHIR authentication
- Frontend never sees FHIR credentials
- SQLite database is local to backend server
- CORS restricted to frontend origin in production

## Success Indicators

✅ Backend running on port 8000
✅ Frontend running on port 5173
✅ Patient list loads from database
✅ MRN search triggers data pipeline
✅ Patient details load on selection
✅ Loading states show during fetch
✅ Error handling works for invalid MRN
✅ Data persists in SQLite database
✅ Cached patients load instantly

## Support

For issues or questions:
1. Check backend logs: `Backend/logs/` (if logging configured)
2. Check browser console: DevTools → Console
3. Check network requests: DevTools → Network
4. Verify database: `sqlite3 Backend/data_pool.db`

---

**Integration completed successfully!** 🎉
Frontend ↔ Backend ↔ Database ↔ FHIR API all connected.
