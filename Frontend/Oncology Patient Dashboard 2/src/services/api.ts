
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
  systemic_regimen?: string | null;
  local_therapy?: string | null;
  regimen_details?: {
    display_name: string;
  };
  cycles_data?: {
    completed: string;
    planned: string;
    display_text: string;
  };
  toxicities?: Array<{
    grade: string;
    name: string;
    display_tag: string;
  }>;
  outcome?: {
    response_tag: string;
    details: string;
  };
  reason_for_discontinuation?: string;
}

export interface TimelineEvent {
  date_display: string;
  systemic_regimen?: string | null;
  local_therapy?: string | null;
  details?: string;
  event_type?: string;
  // Legacy fields (kept for backward compatibility)
  title?: string;
  subtitle?: string;
}

export interface DiagnosisTimelineItem {
  date_label: string;
  stage_header: string;
  tnm_status: string;
  disease_status: string;
  regimen?: string;
  systemic_regimen?: string | null;
  local_therapy?: string | null;
  relapse_info?: {
    is_relapse: boolean;
    relapse_pattern?: string;
    comparison_to_initial?: string;
    remission_duration?: string;
    relapse_detected_by?: string;
  };
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
  type?: string;
  date: string;
  url: string;
  file_id?: string;
  description?: string;
  document_id?: string;
  document_type?: string;
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
  pathology_summary: PathologySummary | any | null; // Can be PathologySummary or special report type object
  pathology_markers: PathologyMarkers | null;
  extraction_error?: string;
  report_type?: string; // GENOMIC_ALTERATIONS, NO_TEST_PERFORMED, or TYPICAL_PATHOLOGY
  classification?: {
    category: string;
    confidence: string;
    reasoning: string;
    key_indicators: string[];
  };
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
    current_val?: string;
    change_percentage: string;
  };
  current_treatment_data: {
    baseline_val: string;
    current_val?: string;
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
      current_val?: string;
      change_percentage: string;
    };
    current_treatment_data: {
      baseline_val: string;
      current_val?: string;
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

// Clinical Trials interfaces
export interface CriterionResult {
  criterion_number: number;
  criterion_text: string;
  patient_value: string;
  met: boolean | null;
  confidence: string;
  explanation: string;
  criterion_type: 'inclusion' | 'exclusion';
  consent_needed?: boolean;
  review_type?: 'patient' | 'clinician' | 'testing';
  suggested_test?: string;
  manually_resolved?: boolean;
  resolved_by?: 'patient' | 'clinician';
  original_met?: boolean | null;
}

// Bucket 2: Manual criterion resolution
export interface CriterionResolutionPayload {
  criterion_number: number;
  criterion_type: 'inclusion' | 'exclusion';
  resolved_met: boolean;
  resolved_by: 'patient' | 'clinician';
}

export interface ResolveCriteriaResponse {
  success: boolean;
  nct_id: string;
  mrn: string;
  updated_eligibility: TrialEligibility;
  criteria_results: {
    inclusion: CriterionResult[];
    exclusion: CriterionResult[];
  };
  resolutions_applied: number;
}

export interface TrialEligibility {
  status: 'LIKELY_ELIGIBLE' | 'POTENTIALLY_ELIGIBLE' | 'NOT_ELIGIBLE';
  status_reason: string;
  percentage: number;
  inclusion: {
    met: number;
    not_met: number;
    unknown: number;
    consent_needed?: number;
    total: number;
  };
  exclusion: {
    clear: number;
    violated: number;
    unknown: number;
    consent_needed?: number;
    total: number;
  };
}

export interface TrialContact {
  name: string;
  phone: string;
  email: string;
}

export interface TrialLocation {
  facility: string;
  city: string;
  state: string;
  country: string;
  status: string;
}

export interface ClinicalTrial {
  nct_id: string;
  title: string;
  phase: string;
  status: string;
  study_type: string;
  brief_summary: string;
  eligibility: TrialEligibility;
  criteria_results: {
    inclusion: CriterionResult[];
    exclusion: CriterionResult[];
  };
  contact: TrialContact;
  locations: TrialLocation[];
}

export interface ClinicalTrialsResponse {
  success: boolean;
  mrn: string;
  search_queries?: string[];
  patient_cancer_type?: string;
  total_trials: number;
  trials: ClinicalTrial[];
  error?: string;
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
    initial_staging?: {
      tnm: string;
      ajcc_stage: string;
    };
    current_staging?: {
      tnm: string;
      ajcc_stage: string;
    };
    line_of_therapy?: string | number;
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
    duration_since_relapse?: string;
    reference_dates: {
      initial_diagnosis_date: string;
      last_progression_date: string | null;
      last_relapse_date?: string | null;
    }
  };
  lab_results?: LabResult[];
  lab_info?: LabInfo;
  lab_reports?: Document[]; // Individual lab result documents with URLs for Documents tab
  pathology_summary?: any;
  pathology_markers?: any;
  pathology_reports?: PathologyReportDetail[]; // Individual pathology reports with extracted details
  genomics_data?: GenomicMutation[];
  genomic_info?: GenomicInfo; // Genomic data from backend (detected_driver_mutations, immunotherapy_markers, additional_genomic_alterations)
  radiology_reports?: RadiologyReportDetail[]; // Individual radiology reports with extracted details
  genomics_reports?: Document[]; // Individual genomics documents with URLs for Documents tab
  clinical_trials_eligibility?: {
    trials: ClinicalTrial[];
    total: number;
    search_queries?: string[];
  }; // Pre-computed clinical trial eligibility data cached with patient
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

  // Clinical Trials - Get matched trials with eligibility analysis
  async getClinicalTrials(mrn: string): Promise<ClinicalTrialsResponse> {
    return this.request<ClinicalTrialsResponse>('/api/tabs/clinical-trials', {
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

  // ==================== TRIAL-CENTRIC API METHODS ====================

  // List all cached clinical trials
  async listTrials(options?: { status?: string; page?: number; limit?: number }): Promise<TrialsListResponse> {
    const params = new URLSearchParams();
    if (options?.status) params.append('status', options.status);
    if (options?.page) params.append('page', options.page.toString());
    if (options?.limit) params.append('limit', options.limit.toString());

    const queryString = params.toString();
    const endpoint = `/api/trials${queryString ? `?${queryString}` : ''}`;
    return this.request<TrialsListResponse>(endpoint);
  }

  // Get detailed information about a specific trial
  async getTrialDetails(nctId: string): Promise<TrialDetailResponse> {
    return this.request<TrialDetailResponse>(`/api/trials/${nctId}`);
  }

  // Get all patients eligible for a specific trial
  async getEligiblePatientsForTrial(
    nctId: string,
    options?: { eligibilityStatus?: string; page?: number; limit?: number }
  ): Promise<EligiblePatientsResponse> {
    const params = new URLSearchParams();
    if (options?.eligibilityStatus) params.append('eligibility_status', options.eligibilityStatus);
    if (options?.page) params.append('page', options.page.toString());
    if (options?.limit) params.append('limit', options.limit.toString());

    const queryString = params.toString();
    const endpoint = `/api/trials/${nctId}/patients${queryString ? `?${queryString}` : ''}`;
    return this.request<EligiblePatientsResponse>(endpoint);
  }

  // Get cached eligible trials for a patient (instant)
  async getCachedEligibleTrialsForPatient(mrn: string, eligibilityStatus?: string): Promise<CachedEligibleTrialsResponse> {
    const params = new URLSearchParams();
    if (eligibilityStatus) params.append('eligibility_status', eligibilityStatus);

    const queryString = params.toString();
    const endpoint = `/api/patients/${mrn}/eligible-trials${queryString ? `?${queryString}` : ''}`;
    return this.request<CachedEligibleTrialsResponse>(endpoint);
  }

  // Get eligibility computation progress for a patient
  async getEligibilityProgress(mrn: string): Promise<EligibilityProgressResponse> {
    return this.request<EligibilityProgressResponse>(`/api/patients/${mrn}/eligibility-progress`);
  }

  // Bucket 2: Resolve unknown criteria manually
  async resolveCriteria(
    mrn: string,
    nctId: string,
    resolutions: CriterionResolutionPayload[]
  ): Promise<ResolveCriteriaResponse> {
    return this.request<ResolveCriteriaResponse>(
      `/api/patients/${mrn}/trials/${nctId}/resolve-criteria`,
      {
        method: 'POST',
        body: JSON.stringify({ resolutions }),
      }
    );
  }

  // Bucket 3: Refresh a single trial's eligibility (re-run LLM)
  async refreshTrialEligibility(mrn: string, nctId: string): Promise<ResolveCriteriaResponse> {
    return this.request<ResolveCriteriaResponse>(
      `/api/patients/${mrn}/trials/${nctId}/refresh-eligibility`,
      { method: 'POST' }
    );
  }

  // Patient Review: Generate a shareable review link
  async sendPatientReview(mrn: string, nctId: string): Promise<SendPatientReviewResponse> {
    return this.request<SendPatientReviewResponse>(
      `/api/patients/${mrn}/trials/${nctId}/send-patient-review`,
      { method: 'POST' }
    );
  }

  // Patient Review: Get review page data (public)
  async getPatientReview(token: string): Promise<PatientReviewData> {
    return this.request<PatientReviewData>(`/api/review/${token}`);
  }

  // Patient Review: Submit patient responses (public)
  async submitPatientReview(
    token: string,
    responses: CriterionResolutionPayload[]
  ): Promise<PatientReviewSubmitResponse> {
    return this.request<PatientReviewSubmitResponse>(
      `/api/review/${token}/submit`,
      {
        method: 'POST',
        body: JSON.stringify({ responses }),
      }
    );
  }

  // Admin: Sync trials from ClinicalTrials.gov
  async syncTrials(options?: { maxPerQuery?: number; background?: boolean }): Promise<AdminResponse> {
    const params = new URLSearchParams();
    if (options?.maxPerQuery) params.append('max_per_query', options.maxPerQuery.toString());
    if (options?.background !== undefined) params.append('background', options.background.toString());

    const queryString = params.toString();
    const endpoint = `/api/admin/sync-trials${queryString ? `?${queryString}` : ''}`;
    return this.request<AdminResponse>(endpoint, { method: 'POST' });
  }

  // Admin: Compute eligibility matrix
  async computeEligibility(options?: { limitTrials?: number; patientMrn?: string; background?: boolean }): Promise<AdminResponse> {
    const params = new URLSearchParams();
    if (options?.limitTrials) params.append('limit_trials', options.limitTrials.toString());
    if (options?.patientMrn) params.append('patient_mrn', options.patientMrn);
    if (options?.background !== undefined) params.append('background', options.background.toString());

    const queryString = params.toString();
    const endpoint = `/api/admin/compute-eligibility${queryString ? `?${queryString}` : ''}`;
    return this.request<AdminResponse>(endpoint, { method: 'POST' });
  }

  // Admin: Full sync (trials + eligibility)
  async fullSync(options?: { maxTrialsPerQuery?: number; limitTrials?: number; background?: boolean }): Promise<AdminResponse> {
    const params = new URLSearchParams();
    if (options?.maxTrialsPerQuery) params.append('max_trials_per_query', options.maxTrialsPerQuery.toString());
    if (options?.limitTrials) params.append('limit_trials', options.limitTrials.toString());
    if (options?.background !== undefined) params.append('background', options.background.toString());

    const queryString = params.toString();
    const endpoint = `/api/admin/full-sync${queryString ? `?${queryString}` : ''}`;
    return this.request<AdminResponse>(endpoint, { method: 'POST' });
  }

  // Admin: Get sync status
  async getSyncStatus(): Promise<SyncStatusResponse> {
    return this.request<SyncStatusResponse>('/api/admin/sync-status');
  }
}

// Trial-centric response types
export interface CachedTrial {
  nct_id: string;
  title: string;
  phase: string;
  status: string;
  cancer_types: string[];
  conditions: string[];
  eligibility_criteria: string;
  locations: any[];
  contact: any;
  sponsor: string;
  start_date: string;
  completion_date: string;
  enrollment: number;
  brief_summary: string;
  fetched_at: string;
  is_active: boolean;
}

export interface TrialsListResponse {
  success: boolean;
  page: number;
  limit: number;
  total: number;
  total_pages: number;
  trials: CachedTrial[];
}

export interface EligibilityStats {
  total: number;
  // Backend returns uppercase keys
  LIKELY_ELIGIBLE?: number;
  POTENTIALLY_ELIGIBLE?: number;
  NOT_ELIGIBLE?: number;
  // Legacy title case keys (for backwards compatibility)
  "Likely Eligible"?: number;
  "Potentially Eligible"?: number;
  "Not Eligible"?: number;
}

export interface TrialDetailResponse {
  success: boolean;
  trial: CachedTrial;
  eligibility_stats: EligibilityStats;
}

export interface PatientEligibility {
  id: number;
  trial_nct_id: string;
  patient_mrn: string;
  eligibility_status: string;
  eligibility_percentage: number;
  criteria_results: any;
  key_matching_criteria: string[];
  key_exclusion_reasons: string[];
  computed_at: string;
  patient_summary: {
    mrn: string;
    name: string;
    age: string;
    gender: string;
    cancer_type: string;
    stage: string;
  };
}

export interface EligiblePatientsResponse {
  success: boolean;
  nct_id: string;
  page: number;
  limit: number;
  eligibility_stats: EligibilityStats;
  patients: PatientEligibility[];
}

export interface CachedEligibleTrialsResponse {
  success: boolean;
  mrn: string;
  total: number;
  trials: any[];
  computation_status?: string;
  computation_progress?: {
    trials_total: number;
    trials_completed: number;
    trials_eligible: number;
  } | null;
}

export interface EligibilityProgressResponse {
  success: boolean;
  mrn: string;
  status: 'not_started' | 'computing' | 'completed' | 'stale' | 'error';
  trials_total: number;
  trials_completed: number;
  trials_eligible: number;
  trials_error: number;
  started_at?: string;
  updated_at?: string;
  completed_at?: string;
  error_message?: string;
}

export interface SendPatientReviewResponse {
  success: boolean;
  token?: string;
  review_url?: string;
  criteria_count?: number;
  message?: string;
}

export interface PatientReviewData {
  status: 'pending' | 'completed';
  trial_nct_id?: string;
  trial_title?: string;
  patient_first_name?: string;
  criteria?: Array<{
    criterion_number: number;
    criterion_type: string;
    criterion_text: string;
  }>;
  message?: string;
}

export interface PatientReviewSubmitResponse {
  success: boolean;
  message: string;
  resolutions_applied: number;
}

export interface AdminResponse {
  success: boolean;
  message?: string;
  result?: any;
}

export interface SyncStatusResponse {
  success: boolean;
  trials_in_cache: number;
  last_trials_sync: any;
  last_eligibility_computation: any;
  last_full_sync: any;
}

// Export singleton instance
export const apiService = new ApiService();

// Export default
export default apiService;
