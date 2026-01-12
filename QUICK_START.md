# Quick Start Guide - Frontend-Backend Integration

## Overview

The frontend has been successfully integrated with the backend! Here's what you need to know to test it.

## What Was Integrated

### ✅ Completed Features

1. **API Service Module** (`Frontend/Oncology Patient Dashboard/src/services/api.ts`)
   - Complete TypeScript API client
   - All backend endpoints wrapped in typed functions
   - Automatic error handling

2. **Patient Data Context** (`Frontend/Oncology Patient Dashboard/src/contexts/PatientContext.tsx`)
   - Global state management for patient data
   - Automatic caching check
   - Loading and error states

3. **MRN Input Screen** (`Frontend/Oncology Patient Dashboard/src/components/MRNInput.tsx`)
   - Beautiful landing page for entering MRN
   - "Load Demo Patient" button for MRN A2451440
   - Loading states and error handling

4. **Updated Components**
   - **PatientHeader**: Now displays real demographics from backend
   - **DiseaseSummary**: Now displays real diagnosis data from backend
   - **App**: Integrated with PatientProvider and shows MRN input when no patient loaded

5. **Environment Configuration**
   - `.env` and `.env.example` files created
   - Backend URL configurable via `VITE_API_BASE_URL`

6. **Documentation**
   - `INTEGRATION_GUIDE.md`: Complete integration documentation
   - This `QUICK_START.md`: Quick setup instructions

## How to Test

### Step 1: Install Backend Dependencies (if not already done)

```bash
cd Backend
pip install uvicorn fastapi pydantic
# Install any other dependencies your backend needs
```

### Step 2: Start Backend Server

```bash
cd Backend
python app.py
```

You should see:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 3: Start Frontend Development Server

Open a new terminal:

```bash
cd "Frontend/Oncology Patient Dashboard"
npm install  # If not already done
npm run dev
```

The frontend will start on `http://localhost:5173`

### Step 4: Test the Integration

1. Open browser to `http://localhost:5173`
2. You'll see the MRN Input screen
3. Click **"Load Demo Patient (A2451440)"** button
4. Wait for data to load (first time: 10-30 seconds)
5. You'll see the patient dashboard with real data!

### Expected Flow

```
User enters MRN
    ↓
Frontend calls /api/patient/all
    ↓
Backend checks data pool (cache)
    ↓
If not cached: Backend fetches from FHIR
    ↓
Backend stores in data pool
    ↓
Backend returns data to frontend
    ↓
PatientContext updates state
    ↓
All components re-render with real data
```

## What You'll See

### Before Loading Patient
- Clean MRN input screen with:
  - Input field for MRN
  - "Load Patient" button
  - "Load Demo Patient (A2451440)" button

### After Loading Patient (MRN A2451440)
- **PatientHeader**: Real patient name, demographics, oncologist info
- **DiseaseSummary**: Cancer type, stage, diagnosis info
- **All Tabs**: Tab components will have access to patient data via context

### First Load vs Cached Load

**First Load** (data not in cache):
- Takes 10-30 seconds
- Backend fetches from FHIR
- Combines PDFs
- Uploads to Google Drive
- Extracts information

**Subsequent Loads** (data in cache):
- Instant (< 1 second)
- Retrieved from SQLite data pool
- No FHIR calls needed

## Tab Components

All tab components can now access patient data using:

```typescript
import { usePatient } from '../../contexts/PatientContext';

export function MyTab() {
  const { patientData } = usePatient();

  // Access any data:
  const demographics = patientData?.demographics;
  const diagnosis = patientData?.diagnosis;
  const treatment = patientData?.treatment_tab_info_LOT;
  const labInfo = patientData?.lab_info;
  // etc...

  return (
    // Render using real data
  );
}
```

### Data Available in patientData

```typescript
{
  demographics: {
    'Patient Name': string,
    'MRN number': string,
    'Date of Birth': string,
    'Age': string,
    'Gender': string,
    'Height': string,
    'Weight': string,
    'Primary Oncologist': string,
    'Last Visit': string
  },

  diagnosis: {
    cancer_type: string,
    histology: string,
    diagnosis_date: string,
    tnm_classification: string,
    ajcc_stage: string,
    line_of_therapy: string,
    metastatic_sites: string,
    ecog_status: string,
    disease_status: string
  },

  comorbidities: { ... },
  treatment_tab_info_LOT: { ... },
  treatment_tab_info_timeline: { ... },
  diagnosis_header: { ... },
  diagnosis_evolution_timeline: { ... },
  diagnosis_footer: { ... },
  lab_info: { ... },
  pathology_summary: { ... },
  pathology_markers: { ... }
}
```

## Additional Features

### Loading Additional Reports

The context also provides methods to load additional reports:

```typescript
const { loadPathologyReports, loadRadiologyReports, pathologyReports, radiologyReports } = usePatient();

// Load pathology reports (returns Google Drive URLs)
await loadPathologyReports(mrn);

// Load radiology reports (returns Google Drive URLs)
await loadRadiologyReports(mrn);

// Access the reports
console.log(pathologyReports?.documents);
console.log(radiologyReports?.documents);
```

### Checking Data Pool

You can check which patients are cached:

```bash
curl http://localhost:8000/api/pool/patients
```

Response:
```json
{
  "success": true,
  "count": 1,
  "patients": [
    {
      "mrn": "A2451440",
      "created_at": "2024-01-10T10:30:00",
      "updated_at": "2024-01-10T10:30:00"
    }
  ]
}
```

## Troubleshooting

### Backend Won't Start

**Error**: `ModuleNotFoundError: No module named 'uvicorn'`

**Fix**: Install dependencies
```bash
pip install uvicorn fastapi pydantic
```

### Frontend Can't Connect to Backend

**Error**: `Failed to fetch` in browser console

**Fix**:
1. Ensure backend is running on port 8000
2. Check `.env` has correct URL
3. Restart frontend after changing `.env`

### Slow First Load

**This is normal!** First load takes 10-30 seconds because:
- Backend fetches data from FHIR
- Combines multiple PDF documents
- Uploads to Google Drive
- Uses Claude AI to extract information

Subsequent loads are instant!

## Next Steps

1. **Test with Demo Patient**: Load MRN A2451440 to verify everything works
2. **Update Tab Components**: Follow the pattern in `PatientHeader.tsx` and `DiseaseSummary.tsx`
3. **Test with Other MRNs**: Try loading other patient records
4. **Add More Features**: Implement refresh button, patient switching, etc.

## File Structure

```
Frontend/Oncology Patient Dashboard/
├── src/
│   ├── services/
│   │   └── api.ts                 # Backend API client
│   ├── contexts/
│   │   └── PatientContext.tsx     # Patient data state management
│   ├── components/
│   │   ├── MRNInput.tsx           # MRN input screen
│   │   ├── PatientHeader.tsx      # ✅ Updated with real data
│   │   ├── DiseaseSummary.tsx     # ✅ Updated with real data
│   │   └── tabs/
│   │       ├── DiagnosisTab.tsx   # Can access patientData via usePatient()
│   │       ├── TreatmentTab.tsx   # Can access patientData via usePatient()
│   │       ├── LabsTab.tsx        # Can access patientData via usePatient()
│   │       ├── GenomicsTab.tsx    # Can access patientData via usePatient()
│   │       ├── PathologyTab.tsx   # Can access patientData via usePatient()
│   │       └── ...
│   └── App.tsx                    # ✅ Integrated with PatientProvider
├── .env                           # Backend URL configuration
├── .env.example                   # Example configuration
├── INTEGRATION_GUIDE.md           # Detailed integration docs
└── package.json

Backend/
├── app.py                         # ✅ FastAPI server with all endpoints
├── main.py                        # ✅ Data extraction functions
├── data_pool.py                   # ✅ SQLite caching
└── data_pool.db                   # Created automatically
```

## Summary

The integration is complete and ready to test! The frontend now:

- ✅ Connects to FastAPI backend
- ✅ Loads real patient data from FHIR
- ✅ Caches data for fast subsequent loads
- ✅ Displays real data in header and summary
- ✅ Provides data to all components via context
- ✅ Has beautiful loading states and error handling

Just start both servers and click "Load Demo Patient" to see it in action!
