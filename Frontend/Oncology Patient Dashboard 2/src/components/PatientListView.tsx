import { useState, useEffect } from 'react';
import { Users, Search, Filter, ArrowRight, AlertCircle, Activity, Plus, Loader2, Trash2 } from 'lucide-react';
import { usePatient } from '../contexts/PatientContext';
import { apiService } from '../services/api';
import { PatientListSkeleton } from './PatientCardSkeleton';
import { LoadingModal } from './LoadingModal';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from './ui/alert-dialog';

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
  status: 'active' | 'critical' | 'stable';
  lastVisit: string;
}

interface PatientListViewProps {
  onSelectPatient: (patientId: string) => void;
}

export function PatientListView({ onSelectPatient }: PatientListViewProps) {
  const { cachedPatients, loadCachedPatients, fetchPatientData, deletePatient, loading, error, clearError } = usePatient();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [searchMRN, setSearchMRN] = useState('');
  const [showAddPatient, setShowAddPatient] = useState(false);
  const [loadingPatients, setLoadingPatients] = useState(false);
  const [deletingMRN, setDeletingMRN] = useState<string | null>(null);

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
      if (cachedPatients.length === 0) {
        setPatients([]);
        return;
      }

      const patientPromises = cachedPatients.map(async (cached) => {
        try {
          const fullData = await apiService.getCachedPatient(cached.mrn);

          // Derive current staging from timeline (most recent entry) or fall back to header
          const timeline = fullData.diagnosis_evolution_timeline?.timeline || [];
          const currentStage = timeline.length > 0
            ? timeline[0]?.stage_header || timeline[0]?.tnm_status || '-'
            : fullData.diagnosis_header?.current_staging?.ajcc_stage || fullData.diagnosis_header?.current_staging?.tnm || '-';

          return {
            id: cached.mrn,
            mrn: cached.mrn,
            name: fullData.demographics["Patient Name"] || `Patient ${cached.mrn}`,
            age: fullData.demographics["Age"] ? parseInt(fullData.demographics["Age"]) : 0,
            gender: fullData.demographics["Gender"] || '-',
            diagnosis: fullData.diagnosis_header?.primary_diagnosis || 'Not available',
            stage: currentStage,
            currentTreatment: fullData.treatment_tab_info_LOT?.treatment_history && fullData.treatment_tab_info_LOT.treatment_history.length > 0
              ? fullData.treatment_tab_info_LOT.treatment_history[fullData.treatment_tab_info_LOT.treatment_history.length - 1].regimen_details.display_name
              : 'Not available',
            nextAppt: fullData.demographics["Last Visit"] || new Date(cached.updated_at).toLocaleDateString(),
            status: 'active' as const,
            lastVisit: fullData.demographics["Last Visit"] || new Date(cached.updated_at).toLocaleDateString()
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
            status: 'active' as const,
            lastVisit: new Date(cached.updated_at).toLocaleDateString()
          };
        }
      });

      const loadedPatients = await Promise.all(patientPromises);
      setPatients(loadedPatients);
    };

    loadPatientDetails();
  }, [cachedPatients]);

  // Handle adding a new patient by MRN
  const handleAddPatient = async () => {
    if (!searchMRN.trim()) {
      alert('Please enter a valid MRN');
      return;
    }

    try {
      await fetchPatientData(searchMRN.trim());
      setSearchMRN('');
      setShowAddPatient(false);
      // Reload cached patients to include the new one
      await loadCachedPatients();
    } catch (err) {
      console.error('Failed to add patient:', err);
    }
  };

  // Handle deleting a patient
  const handleDeletePatient = async (mrn: string, patientName: string) => {
    setDeletingMRN(mrn);
    try {
      await deletePatient(mrn);
      console.log(`Successfully deleted patient ${patientName} (${mrn})`);
    } catch (err) {
      console.error('Failed to delete patient:', err);
      alert(`Failed to delete patient: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setDeletingMRN(null);
    }
  };

  // Fallback mock data if no cached patients
  const mockPatients: Patient[] = [
    {
      id: '1',
      mrn: 'MRN-2847563',
      name: 'Sarah Mitchell',
      age: 58,
      gender: 'Female',
      diagnosis: 'Non-Small Cell Lung Cancer',
      stage: 'Stage IVA',
      currentTreatment: 'Osimertinib 80mg daily',
      nextAppt: 'Jan 15, 2025',
      status: 'critical',
      lastVisit: 'Dec 10, 2024'
    },
    {
      id: '2',
      mrn: 'MRN-2847891',
      name: 'Robert Chen',
      age: 62,
      gender: 'Male',
      diagnosis: 'Colorectal Adenocarcinoma',
      stage: 'Stage IIIB',
      currentTreatment: 'FOLFOX + Bevacizumab',
      nextAppt: 'Jan 18, 2025',
      status: 'active',
      lastVisit: 'Jan 04, 2025'
    },
    {
      id: '3',
      mrn: 'MRN-2848012',
      name: 'Maria Rodriguez',
      age: 45,
      gender: 'Female',
      diagnosis: 'Breast Cancer (Triple Negative)',
      stage: 'Stage IIA',
      currentTreatment: 'AC-T chemotherapy',
      nextAppt: 'Jan 20, 2025',
      status: 'active',
      lastVisit: 'Jan 06, 2025'
    },
    {
      id: '4',
      mrn: 'MRN-2848234',
      name: 'James Patterson',
      age: 71,
      gender: 'Male',
      diagnosis: 'Prostate Adenocarcinoma',
      stage: 'Stage IVB',
      currentTreatment: 'Enzalutamide + ADT',
      nextAppt: 'Jan 22, 2025',
      status: 'stable',
      lastVisit: 'Dec 18, 2024'
    },
    {
      id: '5',
      mrn: 'MRN-2848567',
      name: 'Linda Washington',
      age: 54,
      gender: 'Female',
      diagnosis: 'Ovarian Cancer',
      stage: 'Stage IIIC',
      currentTreatment: 'Carboplatin + Paclitaxel',
      nextAppt: 'Jan 16, 2025',
      status: 'active',
      lastVisit: 'Jan 02, 2025'
    },
    {
      id: '6',
      mrn: 'MRN-2848723',
      name: 'David Kumar',
      age: 67,
      gender: 'Male',
      diagnosis: 'Pancreatic Adenocarcinoma',
      stage: 'Stage IIB',
      currentTreatment: 'FOLFIRINOX',
      nextAppt: 'Jan 19, 2025',
      status: 'critical',
      lastVisit: 'Jan 05, 2025'
    },
    {
      id: '7',
      mrn: 'MRN-2848891',
      name: 'Jennifer Taylor',
      age: 49,
      gender: 'Female',
      diagnosis: 'Melanoma',
      stage: 'Stage IIIB',
      currentTreatment: 'Pembrolizumab',
      nextAppt: 'Jan 24, 2025',
      status: 'stable',
      lastVisit: 'Dec 27, 2024'
    },
    {
      id: '8',
      mrn: 'MRN-2849034',
      name: 'Michael Johnson',
      age: 59,
      gender: 'Male',
      diagnosis: 'Renal Cell Carcinoma',
      stage: 'Stage IVA',
      currentTreatment: 'Nivolumab + Cabozantinib',
      nextAppt: 'Jan 17, 2025',
      status: 'active',
      lastVisit: 'Jan 03, 2025'
    }
  ];

  // Use cached patients if available, otherwise show empty state
  const displayPatients = patients.length > 0 ? patients : [];

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'critical':
        return 'bg-red-100 text-red-700 border-red-300';
      case 'active':
        return 'bg-blue-100 text-blue-700 border-blue-300';
      case 'stable':
        return 'bg-green-100 text-green-700 border-green-300';
      default:
        return 'bg-gray-100 text-gray-700 border-gray-300';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'critical':
        return <AlertCircle className="w-3.5 h-3.5" />;
      case 'active':
        return <Activity className="w-3.5 h-3.5" />;
      default:
        return <Activity className="w-3.5 h-3.5" />;
    }
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
              Enter patient MRN to fetch data from the system. This will trigger the data pipeline and store results in the database.
            </p>
            <div className="flex items-center gap-3">
              <input
                type="text"
                value={searchMRN}
                onChange={(e) => setSearchMRN(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddPatient()}
                placeholder="Enter Patient MRN (e.g., A2451440)"
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                disabled={loading}
              />
              <button
                onClick={handleAddPatient}
                disabled={loading || !searchMRN.trim()}
                className="flex items-center gap-2 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                {loading ? (
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
                disabled={loading}
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

        {/* Loading State */}
        {loadingPatients && <PatientListSkeleton />}

        {/* Empty State */}
        {!loadingPatients && displayPatients.length === 0 && (
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

        {/* Patient Cards Grid */}
        {!loadingPatients && displayPatients.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-5">
            {displayPatients.map((patient) => (
            <div
              key={patient.id}
              className="bg-white rounded-lg shadow-sm border-2 border-gray-200 hover:border-blue-500 hover:shadow-md transition-all group"
            >
              {/* Patient Card - Clickable */}
              <button
                onClick={() => onSelectPatient(patient.id)}
                className="w-full text-left p-5"
              >
                {/* Patient Header */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1 pr-10">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <h3 className="text-gray-900 group-hover:text-blue-600 transition-colors font-medium">
                        {patient.name}
                      </h3>
                      <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border ${getStatusColor(patient.status)}`}>
                        {getStatusIcon(patient.status)}
                        <span className="capitalize">{patient.status}</span>
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mb-1">MRN: {patient.mrn}</p>
                    {(patient.age > 0 || patient.gender !== '-') && (
                      <p className="text-xs text-gray-500">
                        {patient.age > 0 && patient.gender !== '-'
                          ? `${patient.age} years • ${patient.gender}`
                          : patient.age > 0
                            ? `${patient.age} years`
                            : patient.gender}
                      </p>
                    )}
                  </div>
                  <ArrowRight className="w-5 h-5 text-gray-400 group-hover:text-blue-600 group-hover:translate-x-1 transition-all flex-shrink-0 mt-1" />
                </div>

              {/* Diagnosis Info */}
              {(patient.diagnosis !== 'Not available' || patient.stage !== '-') && (
                <div className="space-y-3 mb-4 pb-4 border-b border-gray-200">
                  {patient.diagnosis !== 'Not available' && (
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Diagnosis</p>
                      <p className="text-sm text-gray-900">{patient.diagnosis}</p>
                    </div>
                  )}
                  {patient.stage !== '-' && (
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Stage</p>
                      <p className="text-sm text-gray-900">{patient.stage}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Treatment & Appointment */}
              <div className="space-y-2">
                {patient.currentTreatment !== 'Not available' && (
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Current Treatment</p>
                    <p className="text-sm text-gray-900">{patient.currentTreatment}</p>
                  </div>
                )}
                <div className="flex items-center justify-between bg-blue-50 rounded-lg px-3 py-2 border border-blue-200">
                  <p className="text-xs text-blue-700">Last Visit</p>
                  <p className="text-sm text-blue-900">{patient.nextAppt}</p>
                </div>
              </div>
              </button>

              {/* Delete Button */}
              <div className="border-t border-gray-200 px-5 py-3">
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <button
                      onClick={(e) => e.stopPropagation()}
                      className="flex items-center gap-2 text-sm text-gray-600 hover:text-red-600 transition-colors"
                      disabled={deletingMRN === patient.mrn}
                    >
                      {deletingMRN === patient.mrn ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span>Deleting...</span>
                        </>
                      ) : (
                        <>
                          <Trash2 className="w-4 h-4" />
                          <span>Delete Patient Record</span>
                        </>
                      )}
                    </button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete Patient Record</AlertDialogTitle>
                      <AlertDialogDescription>
                        Are you sure you want to delete the record for <strong>{patient.name}</strong> (MRN: {patient.mrn})? This action cannot be undone and will remove all cached patient data.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() => handleDeletePatient(patient.mrn, patient.name)}
                        className="bg-red-600 hover:bg-red-700"
                      >
                        Delete
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
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
                <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                <span className="text-gray-600">Critical: {displayPatients.filter(p => p.status === 'critical').length}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                <span className="text-gray-600">Active: {displayPatients.filter(p => p.status === 'active').length}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                <span className="text-gray-600">Stable: {displayPatients.filter(p => p.status === 'stable').length}</span>
              </div>
            </div>
            <p className="text-gray-500">Showing {displayPatients.length} patients</p>
          </div>
          </div>
        )}
      </div>

      {/* Loading Modal */}
      <LoadingModal open={loading} title="Fetching Patient Data" />
    </div>
  );
}
