import { useState } from 'react';
import { PatientListView } from './components/PatientListView';
import { PatientDetailView } from './components/PatientDetailView';
import { TrialsListView } from './components/TrialsListView';
import { TrialDetailView } from './components/TrialDetailView';
import { PatientProvider } from './contexts/PatientContext';

type ViewMode = 'patients' | 'patient-detail' | 'trials' | 'trial-detail';

export default function App() {
  const [viewMode, setViewMode] = useState<ViewMode>('patients');
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);
  const [selectedTrialId, setSelectedTrialId] = useState<string | null>(null);

  const handleSelectPatient = (patientId: string) => {
    setSelectedPatientId(patientId);
    setViewMode('patient-detail');
  };

  const handleBackToPatientList = () => {
    setSelectedPatientId(null);
    setViewMode('patients');
  };

  const handleSelectTrial = (nctId: string) => {
    setSelectedTrialId(nctId);
    setViewMode('trial-detail');
  };

  const handleBackToTrialsList = () => {
    setSelectedTrialId(null);
    setViewMode('trials');
  };

  const handleGoToTrials = () => {
    setViewMode('trials');
  };

  const handleGoToPatients = () => {
    setViewMode('patients');
  };

  // Navigate from trial detail to patient detail
  const handleSelectPatientFromTrial = (mrn: string) => {
    setSelectedPatientId(mrn);
    setViewMode('patient-detail');
  };

  return (
    <PatientProvider>
      {viewMode === 'patient-detail' && selectedPatientId ? (
        <PatientDetailView
          patientId={selectedPatientId}
          onBack={handleBackToPatientList}
        />
      ) : viewMode === 'trial-detail' && selectedTrialId ? (
        <TrialDetailView
          nctId={selectedTrialId}
          onBack={handleBackToTrialsList}
          onSelectPatient={handleSelectPatientFromTrial}
        />
      ) : viewMode === 'trials' ? (
        <TrialsListView
          onSelectTrial={handleSelectTrial}
          onBackToPatients={handleGoToPatients}
        />
      ) : (
        <PatientListView
          onSelectPatient={handleSelectPatient}
          onGoToTrials={handleGoToTrials}
        />
      )}
    </PatientProvider>
  );
}