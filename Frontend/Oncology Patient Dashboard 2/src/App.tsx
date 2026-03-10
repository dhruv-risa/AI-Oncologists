import { useState, useEffect } from 'react';
import { PatientListView } from './components/PatientListView';
import { PatientDetailView } from './components/PatientDetailView';
import { TrialsListView } from './components/TrialsListView';
import { TrialDetailView } from './components/TrialDetailView';
import PatientReviewPage from './components/PatientReviewPage';
import { PatientProvider } from './contexts/PatientContext';

type ViewMode = 'patients' | 'patient-detail' | 'trials' | 'trial-detail';

export default function App() {
  // Check if this is a patient review page
  const [reviewToken, setReviewToken] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('patients');
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);
  const [selectedTrialId, setSelectedTrialId] = useState<string | null>(null);
  const [initialTab, setInitialTab] = useState<string | undefined>(undefined);
  const [focusTrialId, setFocusTrialId] = useState<string | undefined>(undefined);

  useEffect(() => {
    const match = window.location.pathname.match(/^\/review\/([a-f0-9-]+)$/);
    if (match) {
      setReviewToken(match[1]);
    }
  }, []);

  // Render standalone review page if token detected
  if (reviewToken) {
    return <PatientReviewPage token={reviewToken} />;
  }

  const handleSelectPatient = (patientId: string) => {
    setInitialTab(undefined);
    setFocusTrialId(undefined);
    setSelectedPatientId(patientId);
    setViewMode('patient-detail');
  };

  const handleSelectPatientWithTab = (patientId: string, tab: string, trialId?: string) => {
    setInitialTab(tab);
    setFocusTrialId(trialId);
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

  // Navigate from trial detail to patient detail (open Clinical Trials tab focused on this trial)
  const handleSelectPatientFromTrial = (mrn: string, trialNctId?: string) => {
    setInitialTab('clinical-trials');
    setFocusTrialId(trialNctId);
    setSelectedPatientId(mrn);
    setViewMode('patient-detail');
  };

  return (
    <PatientProvider>
      {viewMode === 'patient-detail' && selectedPatientId ? (
        <PatientDetailView
          patientId={selectedPatientId}
          onBack={handleBackToPatientList}
          initialTab={initialTab}
          focusTrialId={focusTrialId}
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
          onSelectPatientWithTab={handleSelectPatientWithTab}
          onGoToTrials={handleGoToTrials}
        />
      )}
    </PatientProvider>
  );
}
