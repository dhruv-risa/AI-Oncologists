
// type: "file_update",
// fileName: "src/services/api.ts",
// fileContent: """
// API Service Layer for Backend Integration
// Base URL for the backend API
const API_BASE_URL = 'http://localhost:8000';

// Type definitions based on backend response structures
export interface PatientDemographics {
  "Patient Name": string | null;
  "MRN": string | null;
  "Date of Birth": string | null;
  "Age": string | null;
  "Gender": string | null;
  "Height": string | null;
  "Weight": string | null;
  "Primary Oncologist": string | null;
  "Last Visit": string | null;
}

export interface DiagnosisStatus {
  cancer_type: string;
  histology: string;
  diagnosis_date: string;
  tnm_classification: string;
  ajcc_stage: string;
  line_of_therapy?: string;
  metastatic_sites: string[];
  ecog_status: string;
  disease_status: string;
}

export interface TreatmentHistoryItem {
  header: {
    line_number: string | number;
    primary_drug_name: string;
    status_badge: string;
  };
  dates: {
    start_date: string;
    end_date: string;
    display_text: string;
  };
  regimen_details: {
    display_name: string;
  };
  cycles_data: {
    completed: string;
    planned: string;
    display_text: string;
  };
  toxicities: Array<{
    grade: string;
    name: string;
    display_tag: string;
  }>;
  outcome: {
    response_tag: string;
    details: string;
  };
  reason_for_discontinuation: string;
}

export interface TimelineEvent {
  date_display: string;
  title: string;
  subtitle: string;
  event_type: string;
}

export interface DiagnosisTimelineItem {
  date_label: string;
  stage_header: string;
  tnm_status: string;
  disease_status: string;
  regimen: string;
  toxicities: Array<{
    effect: string;
    grade: string;
  }>;
  key_findings: string[];
}

export interface ComorbidityItem {
  condition_name: string;
  severity: string;
  clinical_details: string;
  associated_medications: string[];
}

export interface LabResult {
  test_name: string;
  value: string;
  unit: string;
  reference_range: string;
  date: string;
  status?: string;
}

export interface PathologyMarker {
  marker: string;
  result: string;
  interpretation?: string;
}

export interface GenomicMutation {
  gene: string;
  mutation: string;
  variant: string;
  clinical_significance?: string;
}

export interface DetectedDriverMutation {
  gene: string;
  status: string;
  details: string | null;
  is_target: boolean;
}

export interface ImmunotherapyMarker {
  pd_l1?: {
    value: string;
    metric: string;
    interpretation: string;
  };
  tmb?: {
    value: string;
    interpretation: string;
  };
  msi_status?: {
    status: string;
    interpretation: string;
  };
}

export interface AdditionalGenomicAlteration {
  gene: string;
  alteration: string;
  type: string;
  significance: string;
}

export interface GenomicInfo {
  detected_driver_mutations: DetectedDriverMutation[];
  immunotherapy_markers: ImmunotherapyMarker;
  additional_genomic_alterations: AdditionalGenomicAlteration[];
}

export interface LabInfo {
  clinical_interpretation?: string[];
  // Other lab-related fields can be added as needed
}

export interface Document {
  type: string;
  date: string;
  url: string;
  file_id?: string;
}

export interface PathologySummary {
  pathology_report: {
    header: {
      report_id: string;
      alert_banner: {
        headline: string;
        subtext: string;
      };
    };
    diagnosis_section: {
      full_diagnosis: string;
      procedure_type: string;
    };
    details: {
      biopsy_site: string;
      biopsy_date: string;
      surgery_date: string;
      tumor_grade: string;
      margin_status: string;
    };
  };
}

export interface PathologyMarkers {
  pathology_combined: {
    morphology_column: {
      title: string;
      items: string[];
    };
    ihc_column: {
      title: string;
      markers: Array<{
        name: string;
        status_label: string;
        details: string;
      }>;
    };
    keywords: string[];
  };
}

export interface PathologyReportDetail {
  drive_url: string;
  drive_file_id: string;
  date: string;
  document_type: string;
  description: string;
  document_id: string;
  pathology_summary: PathologySummary | null;
  pathology_markers: PathologyMarkers | null;
  extraction_error?: string;
}

export interface PathologyDetailsResponse {
  success: boolean;
  mrn: string;
  reports_count: number;
  reports: PathologyReportDetail[];
  message?: string;
}

// Radiology interfaces
export interface RadiologyReportSummary {
  report_summary: {
    study_type: string;
    study_date: string;
    overall_response: string;
    prior_comparison: string;
  };
}

export interface RecistLesion {
  lesion_name: string;
  initial_diagnosis_data: {
    baseline_val: string;
    change_percentage: string;
  };
  current_treatment_data: {
    baseline_val: string;
    change_percentage: string;
  };
}

export interface RecistMeasurements {
  column_headers: {
    initial_diagnosis_label: string;
    current_treatment_label: string;
  };
  lesions: RecistLesion[];
  sum_row: {
    lesion_name: string;
    initial_diagnosis_data: {
      baseline_val: string;
      change_percentage: string;
    };
    current_treatment_data: {
      baseline_val: string;
      change_percentage: string;
    };
  };
}

export interface RadiologyImpRECIST {
  impression: string | string[];
  recist_measurements: RecistMeasurements;
  additional_findings?: string | string[];
}

export interface RadiologyReportDetail {
  drive_url: string;
  drive_file_id: string;
  drive_url_with_MD: string;
  drive_file_id_with_MD: string;
  date: string;
  document_type: string;
  description: string;
  document_id: string;
  has_latest_md_note: boolean;
  has_initial_md_note: boolean;
  radiology_summary: RadiologyReportSummary | null;
  radiology_imp_RECIST: RadiologyImpRECIST | null;
  extraction_error?: string;
}

export interface RadiologyReportsResponse {
  success: boolean;
  mrn: string;
  reports_count: number;
  reports: RadiologyReportDetail[];
}

export interface PatientData {
  success: boolean;
  mrn: string;
  pdf_url?: string;
  demographics: {
    "Patient Name": string | null;
    "MRN": string | null;
    "Date of Birth": string | null;
    "Age": string | null;
    "Gender": string | null;
    "Height": string | null;
    "Weight": string | null;
    "Primary Oncologist": string | null;
    "Last Visit": string | null;
  };
  diagnosis: {
    cancer_type: string;
    histology: string;
    diagnosis_date: string;
    tnm_classification: string;
    ajcc_stage: string;
    line_of_therapy?: string;
    metastatic_sites: string[];
    ecog_status: string;
    disease_status: string;
  };
  diagnosis_status?: DiagnosisStatus; // For legacy compatibility if needed
  comorbidities: {
    comorbidities: ComorbidityItem[];
    ecog_performance_status: {
      score: string;
      description: string;
    };
  };
  treatment_tab_info_LOT: {
    treatment_history: TreatmentHistoryItem[];
  };
  treatment_tab_info_timeline: {
    timeline_events: TimelineEvent[];
  };
  diagnosis_header: {
    primary_diagnosis: string;
    histologic_type: string;
    diagnosis_date: string;
    initial_staging: { ajcc_stage: string; tnm: string };
    current_staging: { ajcc_stage: string; tnm: string };
    metastatic_status: string;
    metastatic_sites: string[];
    recurrence_status: string;
  };
  diagnosis_evolution_timeline: {
    timeline: DiagnosisTimelineItem[];
  };
  diagnosis_footer: {
    duration_since_diagnosis: string;
    duration_since_progression: string;
    reference_dates: {
        initial_diagnosis_date: string;
        last_progression_date: string | null;
    }
  };
  lab_results?: LabResult[];
  lab_info?: LabInfo;
  pathology_summary?: any;
  pathology_markers?: any;
  pathology_reports?: PathologyReportDetail[]; // Individual pathology reports with extracted details
  genomics_data?: GenomicMutation[];
  genomic_info?: GenomicInfo; // Genomic data from backend (detected_driver_mutations, immunotherapy_markers, additional_genomic_alterations)
  radiology_reports?: RadiologyReportDetail[]; // Individual radiology reports with extracted details
  genomics_reports?: Document[];
}

export interface CachedPatient {
  mrn: string;
  created_at: string;
  updated_at: string;
  name: string;
  age: string;
  gender: string;
  cancerType: string;
  stage: string;
  status: string;
  lastVisit: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

// API Service Class
class ApiService {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  // Generic request handler with error handling
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || errorData.error || `HTTP ${response.status}: ${response.statusText}`
        );
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error(`API request failed: ${endpoint}`, error);
      throw error;
    }
  }

  // MRN Validation
  async validateMRN(mrn: string): Promise<ApiResponse<{ valid: boolean }>> {
    return this.request<ApiResponse<{ valid: boolean }>>('/api/mrn/validate', {
      method: 'POST',
      body: JSON.stringify({ mrn }),
    });
  }

  // Get complete patient data
  async getPatientData(mrn: string): Promise<PatientData> {
    return this.request<PatientData>('/api/patient/all', {
      method: 'POST',
      body: JSON.stringify({ mrn }),
    });
  }

  // Get patient demographics only
  async getPatientDemographics(mrn: string): Promise<PatientDemographics> {
    return this.request<PatientDemographics>('/api/patient/demographics', {
      method: 'POST',
      body: JSON.stringify({ mrn }),
    });
  }

  // Get diagnosis status
  async getDiagnosisStatus(mrn: string): Promise<DiagnosisStatus> {
    return this.request<DiagnosisStatus>('/api/patient/diagnosis-status', {
      method: 'POST',
      body: JSON.stringify({ mrn }),
    });
  }

  // Get comorbidities
  async getComorbidities(mrn: string): Promise<any> {
    return this.request<any>('/api/patient/comorbidities', {
      method: 'POST',
      body: JSON.stringify({ mrn }),
    });
  }

  // Tab-specific endpoints
  async getTreatmentTab(mrn: string): Promise<any> {
    return this.request<any>('/api/tabs/treatment', {
      method: 'POST',
      body: JSON.stringify({ mrn }),
    });
  }

  async getDiagnosisTab(mrn: string): Promise<any> {
    return this.request<any>('/api/tabs/diagnosis', {
      method: 'POST',
      body: JSON.stringify({ mrn }),
    });
  }

  async getLabTab(mrn: string): Promise<any> {
    return this.request<any>('/api/tabs/lab', {
      method: 'POST',
      body: JSON.stringify({ mrn }),
    });
  }

  async getGenomicsTab(mrn: string): Promise<any> {
    return this.request<any>('/api/tabs/genomics', {
      method: 'POST',
      body: JSON.stringify({ mrn }),
    });
  }

  async getGenomicsPathologyTab(mrn: string): Promise<any> {
    return this.request<any>('/api/tabs/genomics-pathology', {
      method: 'POST',
      body: JSON.stringify({ mrn }),
    });
  }

  async getPathologyReports(mrn: string): Promise<Document[]> {
    return this.request<Document[]>('/api/tabs/pathology_reports_extraction', {
      method: 'POST',
      body: JSON.stringify({ mrn }),
    });
  }

  async getRadiologyReports(mrn: string): Promise<any[]> {
    return this.request<any[]>('/api/tabs/radiology_reports_extraction', {
      method: 'POST',
      body: JSON.stringify({ mrn }),
    });
  }

  async getPathologyDetails(mrn: string): Promise<PathologyDetailsResponse> {
    return this.request<PathologyDetailsResponse>('/api/tabs/pathology_details_extraction', {
      method: 'POST',
      body: JSON.stringify({ mrn }),
    });
  }

  // Get cached radiology reports (returns cached data from data pool)
  async getRadiologyReportsCached(mrn: string): Promise<RadiologyReportsResponse> {
    return this.request<RadiologyReportsResponse>('/api/tabs/radiology_reports', {
      method: 'POST',
      body: JSON.stringify({ mrn }),
    });
  }

  // Data pool endpoints (for cached data)
  async getCachedPatient(mrn: string): Promise<PatientData> {
    return this.request<PatientData>(`/api/pool/patient/${mrn}`);
  }

  async getAllCachedPatients(): Promise<CachedPatient[]> {
    const response = await this.request<{ success: boolean; count: number; patients: CachedPatient[] }>('/api/pool/patients');
    return response.patients || [];
  }

  async checkPatientExists(mrn: string): Promise<{ exists: boolean }> {
    return this.request<{ exists: boolean }>(`/api/pool/patient/${mrn}/exists`);
  }

  async deleteCachedPatient(mrn: string): Promise<ApiResponse<any>> {
    return this.request<ApiResponse<any>>(`/api/pool/patient/${mrn}`, {
      method: 'DELETE',
    });
  }

  async clearCache(): Promise<ApiResponse<any>> {
    return this.request<ApiResponse<any>>('/api/pool/clear', {
      method: 'DELETE',
    });
  }
}

// Export singleton instance
export const apiService = new ApiService();

// Export default
export default apiService;
