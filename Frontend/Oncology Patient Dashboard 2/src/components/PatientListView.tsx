import { useState, useEffect } from 'react';
import { Users, Search, Filter, ArrowRight, AlertCircle, Activity, Plus, Loader2, Trash2, Beaker } from 'lucide-react';
import { usePatient } from '../contexts/PatientContext';
import { apiService } from '../services/api';
import { PatientListSkeleton } from './PatientCardSkeleton';
import { LoadingModal } from './LoadingModal';
import { normalizePatientName } from '../utils/stringFormatters';

interface Patient {
  id: string;
  mrn: string;
  name: string;
  age: number;
  gender: string;
  diagnosis: string;
  stage: string;
  currentTreatment: string;
  nextAppt: string;
  diseaseStatus: string | null;
  lastVisit: string;
  // Trial match counts
  trialsAnalyzed?: number;
  likelyEligible?: number;
  potentiallyEligible?: number;
  matchedTrials?: number;
}

interface PatientListViewProps {
  onSelectPatient: (patientId: string) => void;
  onGoToTrials?: () => void;
}

export function PatientListView({ onSelectPatient, onGoToTrials }: PatientListViewProps) {
  const { cachedPatients, loadCachedPatients, fetchPatientData, deletePatient, error, clearError, setCurrentPatient } = usePatient();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [patientDataMap, setPatientDataMap] = useState<Map<string, any>>(new Map());
  const [searchMRN, setSearchMRN] = useState('');
  const [showAddPatient, setShowAddPatient] = useState(false);
  const [loadingPatients, setLoadingPatients] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [addingNewPatient, setAddingNewPatient] = useState(false);

  // Load cached patients on mount
  useEffect(() => {
    const loadInitialData = async () => {
      setLoadingPatients(true);
      await loadCachedPatients();
      setLoadingPatients(false);
    };
    loadInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only run once on mount

  // Load full patient details for display
  useEffect(() => {
    const loadPatientDetails = async () => {
      // Don't try to load details if there are no cached patients
      if (cachedPatients.length === 0) {
        setPatients([]);
        setLoadingDetails(false);
        return;
      }

      setLoadingDetails(true);

      try {
        const newDataMap = new Map();
        const patientPromises = cachedPatients.map(async (cached) => {
          try {
            const fullData = await apiService.getCachedPatient(cached.mrn);

            // Store full data in map for later use
            newDataMap.set(cached.mrn, fullData);

          // Derive current staging from timeline (most recent entry) or fall back to header
          const timeline = fullData.diagnosis_evolution_timeline?.timeline || [];

          // Sort timeline by date (most recent first) and find first entry with valid staging data
          const sortedTimeline = [...timeline].sort((a, b) => {
            const parseDate = (dateStr: string) => {
              if (!dateStr) return new Date(0);
              if (dateStr.toLowerCase().includes('current')) return new Date();

              const monthNames = ['january', 'february', 'march', 'april', 'may', 'june',
                                  'july', 'august', 'september', 'october', 'november', 'december'];
              const lowerStr = dateStr.toLowerCase().trim();

              for (let i = 0; i < monthNames.length; i++) {
                if (lowerStr.startsWith(monthNames[i])) {
                  const yearMatch = dateStr.match(/\d{4}/);
                  if (yearMatch) return new Date(parseInt(yearMatch[0]), i, 1);
                }
              }

              const date = new Date(dateStr);
              return !isNaN(date.getTime()) ? date : new Date(0);
            };

            return parseDate(b.date_label).getTime() - parseDate(a.date_label).getTime();
          });

          // Find first timeline entry with valid staging data (excluding special values)
          const currentTimelineEntry = sortedTimeline.find(entry => {
            const hasValidStage = entry.stage_header &&
              entry.stage_header !== 'N/A' &&
              entry.stage_header !== 'Pre-diagnosis finding' &&
              entry.stage_header !== 'Staging not performed';
            const hasValidTNM = entry.tnm_status &&
              entry.tnm_status !== 'NA' &&
              entry.tnm_status !== 'N/A';
            return hasValidStage || hasValidTNM;
          });

          const currentStage = currentTimelineEntry
            ? currentTimelineEntry.stage_header || currentTimelineEntry.tnm_status || 'Not staged'
            : fullData.diagnosis_header?.current_staging?.ajcc_stage || fullData.diagnosis_header?.current_staging?.tnm || 'Not staged';

          // Get current treatment - check multiple possible fields
          let currentTreatment = 'Not available';
          if (fullData.treatment_tab_info_LOT?.treatment_history && fullData.treatment_tab_info_LOT.treatment_history.length > 0) {
            const latestTreatment = fullData.treatment_tab_info_LOT.treatment_history[fullData.treatment_tab_info_LOT.treatment_history.length - 1];
            currentTreatment = latestTreatment.systemic_regimen ||
                              latestTreatment.regimen_details?.display_name ||
                              latestTreatment.header?.primary_drug_name ||
                              'Not available';
          }

          // Get disease status from diagnosis (same as DiseaseSummary and patient demographics)
          const diseaseStatus = fullData.diagnosis?.disease_status || null;

          return {
            id: cached.mrn,
            mrn: cached.mrn,
            name: normalizePatientName(fullData.demographics["Patient Name"]) || `Patient ${cached.mrn}`,
            age: fullData.demographics["Age"] ? parseInt(fullData.demographics["Age"]) : 0,
            gender: fullData.demographics["Gender"] || '-',
            diagnosis: fullData.diagnosis_header?.primary_diagnosis || 'Not available',
            stage: currentStage,
            currentTreatment,
            nextAppt: fullData.demographics["Last Visit"] || new Date(cached.updated_at).toLocaleDateString(),
            diseaseStatus,
            lastVisit: fullData.demographics["Last Visit"] || new Date(cached.updated_at).toLocaleDateString(),
            // Trial match counts from cached data
            trialsAnalyzed: (cached as any).trialsAnalyzed || 0,
            likelyEligible: (cached as any).likelyEligible || 0,
            potentiallyEligible: (cached as any).potentiallyEligible || 0,
            matchedTrials: (cached as any).matchedTrials || 0
          };
        } catch (err) {
          console.error(`Error loading patient ${cached.mrn}:`, err);
          return {
            id: cached.mrn,
            mrn: cached.mrn,
            name: `Patient ${cached.mrn}`,
            age: 0,
            gender: 'Unknown',
            diagnosis: 'Click to load full details',
            stage: 'N/A',
            currentTreatment: 'N/A',
            nextAppt: 'N/A',
            diseaseStatus: null,
            lastVisit: new Date(cached.updated_at).toLocaleDateString(),
            // Trial match counts from cached data
            trialsAnalyzed: (cached as any).trialsAnalyzed || 0,
            likelyEligible: (cached as any).likelyEligible || 0,
            potentiallyEligible: (cached as any).potentiallyEligible || 0,
            matchedTrials: (cached as any).matchedTrials || 0
          };
          }
        });

        const loadedPatients = await Promise.all(patientPromises);
        setPatients(loadedPatients);
        setPatientDataMap(newDataMap);
      } catch (error) {
        console.error('Error loading patient details:', error);
      } finally {
        setLoadingDetails(false);
      }
    };

    loadPatientDetails();
  }, [cachedPatients]);

  // Handle selecting a patient - pre-load data into context for instant display
  const handleSelectPatient = (patientId: string) => {
    const fullData = patientDataMap.get(patientId);
    if (fullData) {
      // Pre-load the patient data into context so detail view can use it immediately
      console.log(`Pre-loading patient ${patientId} from cache`);
      setCurrentPatient(fullData);
    } else {
      console.log(`Patient ${patientId} not found in cache, will fetch from API`);
    }
    // Navigate to detail view
    onSelectPatient(patientId);
  };

  // Handle adding a new patient by MRN
  const handleAddPatient = async () => {
    if (!searchMRN.trim()) {
      alert('Please enter a valid MRN');
      return;
    }

    try {
      setAddingNewPatient(true);
      // Use FHIR API to fetch patient data
      await fetchPatientData(searchMRN.trim());
      setSearchMRN('');
      setShowAddPatient(false);
      // Reload cached patients to include the new one
      await loadCachedPatients();
    } catch (err) {
      console.error('Failed to add patient:', err);
    } finally {
      setAddingNewPatient(false);
    }
  };

  // Fallback mock data if no cached patients (removed - not used anymore)

  // Use cached patients if available, otherwise show empty state
  const displayPatients = patients.length > 0 ? patients : [];

  const getDiseaseStatusColor = (diseaseStatus: string | null) => {
    if (!diseaseStatus || diseaseStatus === 'N/A' || diseaseStatus === 'NA') {
      return null; // Don't display if null or N/A
    }

    const statusLower = diseaseStatus.toLowerCase();

    // Positive/Good status (light green)
    if (
      statusLower.includes('complete response') ||
      statusLower.includes('partial response') ||
      statusLower.includes('responding to treatment') ||
      statusLower.includes('remission') ||
      statusLower.includes('no evidence of disease') ||
      statusLower.includes('ned')
    ) {
      return 'bg-green-100 text-green-700 border-green-300';
    }

    // Negative/Bad status (light red)
    if (
      statusLower.includes('progressive disease') ||
      statusLower.includes('recurrent disease') ||
      statusLower.includes('active disease') ||
      statusLower.includes('progression')
    ) {
      return 'bg-red-100 text-red-700 border-red-300';
    }

    // Mild/Neutral status (light grey)
    if (
      statusLower.includes('stable disease') ||
      statusLower.includes('newly diagnosed')
    ) {
      return 'bg-gray-100 text-gray-700 border-gray-300';
    }

    // Default to grey if unknown status
    return 'bg-gray-100 text-gray-700 border-gray-300';
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-[1800px] mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-600 rounded-lg">
                <Users className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-gray-900 text-2xl">Oncology Patient Registry</h1>
                <p className="text-sm text-gray-500">Select a patient to view detailed clinical information</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg text-sm border border-blue-200">
                {displayPatients.length} Active Patients
              </span>
              {onGoToTrials && (
                <button
                  onClick={onGoToTrials}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg transition-colors border-2 border-green-600 bg-green-600 text-white hover:bg-green-700"
                  style={{ backgroundColor: '#059669', color: 'white', borderColor: '#047857' }}
                >
                  <Beaker className="w-4 h-4" />
                  <span>Clinical Trials</span>
                </button>
              )}
              <button
                onClick={() => setShowAddPatient(!showAddPatient)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                <Plus className="w-4 h-4" />
                <span>Add Patient by MRN</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-[1800px] mx-auto px-6 py-6">
        {/* Add Patient by MRN Section */}
        {showAddPatient && (
          <div className="bg-white rounded-lg shadow-sm border-2 border-blue-200 p-6 mb-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Add New Patient</h3>
            <p className="text-sm text-gray-600 mb-4">
              Enter patient MRN to load their clinical data and documents from the system.
            </p>
            <div className="flex items-center gap-3">
              <input
                type="text"
                value={searchMRN}
                onChange={(e) => setSearchMRN(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddPatient()}
                placeholder="Enter Patient MRN (e.g., A2451440)"
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                disabled={addingNewPatient}
              />
              <button
                onClick={handleAddPatient}
                disabled={addingNewPatient || !searchMRN.trim()}
                className="flex items-center gap-2 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                {addingNewPatient ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Processing...</span>
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4" />
                    <span>Fetch Patient Data</span>
                  </>
                )}
              </button>
              <button
                onClick={() => setShowAddPatient(false)}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                disabled={addingNewPatient}
              >
                Cancel
              </button>
            </div>
            {error && (
              <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm text-red-700">{error}</p>
                <button
                  onClick={clearError}
                  className="text-xs text-red-600 underline mt-1"
                >
                  Dismiss
                </button>
              </div>
            )}
          </div>
        )}

        {/* Search and Filter Bar */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
          <div className="flex items-center gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search by name, MRN, diagnosis..."
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <button className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors">
              <Filter className="w-4 h-4" />
              <span>Filters</span>
            </button>
          </div>
        </div>

        {/* Loading State - show skeleton while loading initial data or patient details, but NOT when adding a new patient */}
        {(loadingPatients || loadingDetails) && <PatientListSkeleton />}

        {/* Empty State - only show when truly no patients exist and not loading anything */}
        {!loadingPatients && !loadingDetails && displayPatients.length === 0 && !addingNewPatient && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
            <Users className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No Patients in Database</h3>
            <p className="text-gray-600 mb-6">
              Click "Add Patient by MRN" to fetch patient data from the system
            </p>
            <button
              onClick={() => setShowAddPatient(true)}
              className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors mx-auto"
            >
              <Plus className="w-5 h-5" />
              Add Your First Patient
            </button>
          </div>
        )}

        {/* Patient Cards Grid - show when we have patients OR when adding a new one */}
        {!loadingPatients && !loadingDetails && (displayPatients.length > 0 || addingNewPatient) && (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-5">
            {/* Loading Card - show as first card when processing new patient */}
            {addingNewPatient && (
              <LoadingModal open={addingNewPatient} title="Fetching Patient Data" variant="card" />
            )}

            {displayPatients.map((patient) => (
              <div
                key={patient.id}
                onClick={() => handleSelectPatient(patient.id)}
                className="bg-white rounded-xl shadow-sm border border-gray-200 hover:border-blue-500 hover:shadow-md transition-all group cursor-pointer p-5 flex flex-col gap-3"
              >
                {/* Patient Header */}
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1.5">
                      <h3 className="text-gray-900 group-hover:text-blue-600 transition-colors text-base font-normal">
                        {patient.name}
                      </h3>
                      {getDiseaseStatusColor(patient.diseaseStatus) && (
                        <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border ${getDiseaseStatusColor(patient.diseaseStatus)}`}>
                          <span className="truncate max-w-[100px]">{patient.diseaseStatus}</span>
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 mb-0.5">MRN: {patient.mrn}</p>
                    <p className="text-xs text-gray-500">
                      {patient.age > 0 && patient.gender !== '-'
                        ? `${patient.age} years • ${patient.gender}`
                        : patient.age > 0
                          ? `${patient.age} years`
                          : patient.gender !== '-'
                            ? patient.gender
                            : '-'}
                    </p>
                  </div>
                  <ArrowRight className="w-5 h-5 text-gray-400 group-hover:text-blue-600 group-hover:translate-x-1 transition-all flex-shrink-0" />
                </div>

                {/* Diagnosis */}
                <div>
                  <p className="text-xs text-gray-500 mb-1">Diagnosis</p>
                  <p className="text-sm text-gray-900 font-normal line-clamp-2">{patient.diagnosis !== 'Not available' ? patient.diagnosis : '-'}</p>
                </div>

                {/* Stage */}
                <div>
                  <p className="text-xs text-gray-500 mb-1">Stage</p>
                  <p className="text-sm text-gray-900 font-normal">{patient.stage !== '-' ? patient.stage : '-'}</p>
                </div>

                {/* Treatment */}
                <div className="flex-grow">
                  <p className="text-xs text-gray-500 mb-1">Current Treatment</p>
                  <p className="text-sm text-gray-900 font-normal line-clamp-2" title={patient.currentTreatment}>
                    {patient.currentTreatment !== 'Not available' ? patient.currentTreatment : '-'}
                  </p>
                </div>

                {/* Last Visit */}
                <div className="flex items-center justify-between bg-blue-50 rounded-lg px-4 py-3 border border-blue-200">
                  <p className="text-xs text-blue-600 font-normal">Last Visit</p>
                  <p className="text-sm text-gray-900 font-normal">{patient.nextAppt}</p>
                </div>

                {/* Clinical Trials Match Badge - only show when eligibility has been computed */}
                {patient.trialsAnalyzed !== undefined && patient.trialsAnalyzed > 0 && (patient.likelyEligible! > 0 || patient.potentiallyEligible! > 0) && (
                  <div className="mt-1 pt-3 border-t border-gray-200">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Beaker className="w-4 h-4 text-green-600" />
                        <span className="text-xs font-medium text-gray-700">Clinical Trials</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {patient.likelyEligible !== undefined && patient.likelyEligible > 0 && (
                          <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs font-medium">
                            {patient.likelyEligible} Likely
                          </span>
                        )}
                        {patient.potentiallyEligible !== undefined && patient.potentiallyEligible > 0 && (
                          <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded-full text-xs font-medium">
                            {patient.potentiallyEligible} Potential
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Footer Summary */}
        {!loadingPatients && displayPatients.length > 0 && (
          <div className="mt-6 bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                <span className="text-gray-600">Positive: {displayPatients.filter(p => {
                  const status = p.diseaseStatus?.toLowerCase() || '';
                  return status.includes('complete response') || status.includes('partial response') ||
                         status.includes('responding') || status.includes('remission') || status.includes('ned');
                }).length}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-gray-500 rounded-full"></div>
                <span className="text-gray-900">Stable: {displayPatients.filter(p => {
                  const status = p.diseaseStatus?.toLowerCase() || '';
                  return status.includes('stable') || status.includes('newly diagnosed');
                }).length}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                <span className="text-gray-600">Negative: {displayPatients.filter(p => {
                  const status = p.diseaseStatus?.toLowerCase() || '';
                  return status.includes('progressive') || status.includes('recurrent') || status.includes('active disease');
                }).length}</span>
              </div>
            </div>
            <p className="text-gray-500">Showing {displayPatients.length} patients</p>
          </div>
          </div>
        )}
      </div>
    </div>
  );
}
