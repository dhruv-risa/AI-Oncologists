import { useState, useEffect } from 'react';
import { PatientListView } from './components/PatientListView';
import { PatientDetailView } from './components/PatientDetailView';
import { TrialsListView } from './components/TrialsListView';
import { TrialDetailView } from './components/TrialDetailView';
import PatientReviewPage from './components/PatientReviewPage';
import { PatientProvider } from './contexts/PatientContext';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import LoginPage from './components/LoginPage';
import { Loader2 } from 'lucide-react';

type ViewMode = 'patients' | 'patient-detail' | 'trials' | 'trial-detail';

function AppContent() {
  const { user, loading } = useAuth();

  // Check if this is a patient review page (public, no auth needed)
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

  // Render standalone review page if token detected (no auth required)
  if (reviewToken) {
    return <PatientReviewPage token={reviewToken} />;
  }

  // Show loading spinner while auth state initializes
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
      </div>
    );
  }

  // Show login page if not authenticated
  if (!user) {
    return <LoginPage />;
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

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
