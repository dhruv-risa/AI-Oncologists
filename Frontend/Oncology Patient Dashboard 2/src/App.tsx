import { useState } from 'react';
import { PatientListView } from './components/PatientListView';
import { PatientDetailView } from './components/PatientDetailView';
import { PatientProvider } from './contexts/PatientContext';

export default function App() {
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);

  const handleSelectPatient = (patientId: string) => {
    setSelectedPatientId(patientId);
  };

  const handleBackToList = () => {
    setSelectedPatientId(null);
  };

  return (
    <PatientProvider>
      {/* Show patient detail view if a patient is selected */}
      {selectedPatientId ? (
        <PatientDetailView patientId={selectedPatientId} onBack={handleBackToList} />
      ) : (
        /* Show patient list view by default */
        <PatientListView onSelectPatient={handleSelectPatient} />
      )}
    </PatientProvider>
  );
}