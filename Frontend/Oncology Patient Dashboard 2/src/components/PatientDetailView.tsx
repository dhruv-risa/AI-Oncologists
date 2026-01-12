import { useState, useEffect } from 'react';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { PatientHeader } from './PatientHeader';
import { DiseaseSummary } from './DiseaseSummary';
import { TabNavigation } from './TabNavigation';
import { RightSidebar } from './RightSidebar';
import { VoiceAssistant } from './VoiceAssistant';
import { DiagnosisTab } from './tabs/DiagnosisTab';
import { DocumentsSection } from './DocumentsSection';
import { PathologyTab } from './tabs/PathologyTab';
import { GenomicsTab } from './tabs/GenomicsTab';
import { RadiologyTab } from './tabs/RadiologyTab';
import { LabsTab } from './tabs/LabsTab';
import { TreatmentTab } from './tabs/TreatmentTab';
import { ComorbiditiesTab } from './tabs/ComorbiditiesTab';
import { usePatient } from '../contexts/PatientContext';

interface PatientDetailViewProps {
  patientId: string;
  onBack: () => void;
}

export function PatientDetailView({ patientId, onBack }: PatientDetailViewProps) {
  const [activeTab, setActiveTab] = useState('diagnosis');
  const { currentPatient, fetchPatientData, loading, error } = usePatient();

  // Fetch patient data when component mounts or patientId changes
  useEffect(() => {
    fetchPatientData(patientId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patientId]); // Only re-run when patientId changes

  const renderTabContent = () => {
    switch (activeTab) {
      case 'diagnosis':
        return <DiagnosisTab patientData={currentPatient} />;
      case 'pathology':
        return <PathologyTab patientData={currentPatient} />;
      case 'genomics':
        return <GenomicsTab />;
      case 'radiology':
        return <RadiologyTab patientData={currentPatient} />;
      case 'labs':
        return <LabsTab />;
      case 'treatment':
        return <TreatmentTab patientData={currentPatient} />;
      case 'comorbidities':
        return <ComorbiditiesTab patientData={currentPatient} />;
      case 'documents':
        return <DocumentsSection />;
      default:
        return <DiagnosisTab patientData={currentPatient} />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Back Button */}
      <div className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-[1600px] mx-auto px-6 py-3">
          <button
            onClick={onBack}
            className="flex items-center gap-2 px-3 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="text-sm">Back to Patient List</span>
          </button>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-24">
          <Loader2 className="w-12 h-12 text-blue-600 animate-spin mb-4" />
          <p className="text-gray-600 text-lg">Loading patient data...</p>
          <p className="text-gray-500 text-sm mt-2">This may take a moment if fetching from FHIR system</p>
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="max-w-[1600px] mx-auto px-6 py-12">
          <div className="bg-red-50 border-2 border-red-200 rounded-lg p-8 text-center">
            <h3 className="text-lg font-medium text-red-900 mb-2">Failed to Load Patient Data</h3>
            <p className="text-red-700 mb-4">{error}</p>
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={() => fetchPatientData(patientId)}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              >
                Retry
              </button>
              <button
                onClick={onBack}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Back to List
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Patient Data View */}
      {!loading && !error && currentPatient && currentPatient.demographics && (
        <>
          <PatientHeader patient={currentPatient} />
          <main className="max-w-[1600px] mx-auto px-6 py-6">
            {/* Disease Summary - Full Width */}
            <DiseaseSummary patient={currentPatient} />

            {/* Horizontal Tabs */}
            <div className="mt-6">
              <TabNavigation activeTab={activeTab} onTabChange={setActiveTab} />
            </div>

            {/* Two Column Layout: Content | Sidebar */}
            <div className="flex gap-6 mt-6">
              {/* Main Content Area */}
              <div className="flex-1">
                {renderTabContent()}
              </div>

              {/* Right Sidebar */}
              <RightSidebar />
            </div>
          </main>
          <VoiceAssistant onNavigate={setActiveTab} />
        </>
      )}
    </div>
  );
}
