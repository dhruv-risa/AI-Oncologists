import React, { createContext, useContext, useState, useCallback } from 'react';
import { apiService, PatientData, CachedPatient } from '../services/api';

// Context state interface
interface PatientContextState {
  currentPatient: PatientData | null;
  cachedPatients: CachedPatient[];
  loading: boolean;
  error: string | null;
  fetchPatientData: (mrn: string) => Promise<void>;
  fetchDemoPatientData: (mrn: string) => Promise<void>;
  loadCachedPatients: () => Promise<void>;
  deletePatient: (mrn: string) => Promise<void>;
  clearError: () => void;
  clearCurrentPatient: () => void;
  setCurrentPatient: (patient: PatientData) => void;
}

// Create context
const PatientContext = createContext<PatientContextState | undefined>(undefined);

// Provider component
export const PatientProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentPatient, setCurrentPatient] = useState<PatientData | null>(null);
  const [cachedPatients, setCachedPatients] = useState<CachedPatient[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch patient data by MRN (triggers backend pipeline if not cached)
  const fetchPatientData = useCallback(async (mrn: string) => {
    setLoading(true);
    setError(null);

    try {
      // First check if patient exists in cache
      const existsResponse = await apiService.checkPatientExists(mrn);

      let patientData: PatientData;

      if (existsResponse.exists) {
        // Fetch from cache
        console.log(`Patient ${mrn} found in cache, fetching cached data...`);
        patientData = await apiService.getCachedPatient(mrn);
      } else {
        // Trigger full data extraction pipeline
        console.log(`Patient ${mrn} not in cache, triggering data pipeline...`);
        patientData = await apiService.getPatientData(mrn);
      }

      console.log('Patient data loaded:', patientData);
      console.log('Demographics:', patientData.demographics);
      setCurrentPatient(patientData);

      // Reload cached patients list
      await loadCachedPatients();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch patient data';
      setError(errorMessage);
      console.error('Error fetching patient data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch demo patient data (bypasses FHIR API, uses demo_data.json)
  const fetchDemoPatientData = useCallback(async (mrn: string) => {
    setLoading(true);
    setError(null);

    try {
      console.log(`Fetching demo data for MRN: ${mrn}...`);
      const demoData = await apiService.getPatientData(mrn);

      console.log('Demo data loaded:', demoData);

      // Transform demo data to match PatientData structure
      const patientData: PatientData = {
        success: demoData.success,
        mrn: demoData.mrn,
        demographics: demoData.demographics || {
          "Patient Name": null,
          "MRN": demoData.mrn,
          "Date of Birth": null,
          "Age": null,
          "Gender": null,
          "Height": null,
          "Weight": null,
          "Primary Oncologist": null,
          "Last Visit": null,
        },
        diagnosis: demoData.diagnosis || {
          cancer_type: "",
          histology: "",
          diagnosis_date: "",
          tnm_classification: "",
          ajcc_stage: "",
          metastatic_sites: [],
          ecog_status: "",
          disease_status: "",
        },
        comorbidities: demoData.comorbidities || {
          comorbidities: [],
          ecog_performance_status: {
            score: "",
            description: "",
          },
        },
        treatment_tab_info_LOT: demoData.treatment_tab_info_LOT || {
          treatment_history: [],
        },
        treatment_tab_info_timeline: demoData.treatment_tab_info_timeline || {
          timeline_events: [],
        },
        diagnosis_header: demoData.diagnosis_header || {
          primary_diagnosis: "",
          histologic_type: "",
          diagnosis_date: "",
          initial_staging: { ajcc_stage: "", tnm: "" },
          current_staging: { ajcc_stage: "", tnm: "" },
          metastatic_status: "",
          metastatic_sites: [],
          recurrence_status: "",
        },
        diagnosis_evolution_timeline: demoData.diagnosis_evolution_timeline || {
          timeline: [],
        },
        diagnosis_footer: demoData.diagnosis_footer || {
          duration_since_diagnosis: "",
          duration_since_progression: "",
          reference_dates: {
            initial_diagnosis_date: "",
            last_progression_date: null,
          },
        },
        lab_info: demoData.lab_info,
        genomic_info: demoData.genomic_info,
        pathology_summary: demoData.pathology_summary,
        pathology_markers: demoData.pathology_markers,
        pathology_reports: demoData.pathology_reports || [],
        radiology_reports: demoData.radiology_reports || [],
        genomics_reports: demoData.genomics_reports || [],
      };

      setCurrentPatient(patientData);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch demo patient data';
      setError(errorMessage);
      console.error('Error fetching demo patient data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load list of all cached patients
  const loadCachedPatients = useCallback(async () => {
    try {
      const patients = await apiService.getAllCachedPatients();
      setCachedPatients(patients);
    } catch (err) {
      console.error('Error loading cached patients:', err);
      // Don't set error state for this background operation
    }
  }, []);

  // Clear error
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Delete patient from cache
  const deletePatient = useCallback(async (mrn: string) => {
    setLoading(true);
    setError(null);

    try {
      await apiService.deleteCachedPatient(mrn);

      // If the deleted patient is currently selected, clear it
      if (currentPatient?.mrn === mrn) {
        setCurrentPatient(null);
      }

      // Reload cached patients list
      await loadCachedPatients();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete patient';
      setError(errorMessage);
      console.error('Error deleting patient:', err);
      throw err; // Re-throw to allow caller to handle
    } finally {
      setLoading(false);
    }
  }, [currentPatient, loadCachedPatients]);

  // Clear current patient
  const clearCurrentPatient = useCallback(() => {
    setCurrentPatient(null);
  }, []);

  // Set current patient directly (for optimization when data is already loaded)
  const setCurrentPatientDirect = useCallback((patient: PatientData) => {
    setCurrentPatient(patient);
  }, []);

  const value: PatientContextState = {
    currentPatient,
    cachedPatients,
    loading,
    error,
    fetchPatientData,
    fetchDemoPatientData,
    loadCachedPatients,
    deletePatient,
    clearError,
    clearCurrentPatient,
    setCurrentPatient: setCurrentPatientDirect,
  };

  return (
    <PatientContext.Provider value={value}>
      {children}
    </PatientContext.Provider>
  );
};

// Custom hook to use patient context
export const usePatient = (): PatientContextState => {
  const context = useContext(PatientContext);
  if (context === undefined) {
    throw new Error('usePatient must be used within a PatientProvider');
  }
  return context;
};

export default PatientContext;
