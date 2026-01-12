import { TestTube, TrendingDown, TrendingUp, Minus } from 'lucide-react';
import { LabTrendChart } from '../LabTrendChart';
import { useState } from 'react';
import { usePatient } from '../../contexts/PatientContext';

export function LabsTab() {
  const { currentPatient } = usePatient();
  const [selectedLab, setSelectedLab] = useState('CEA');
  const [selectedCBCLab, setSelectedCBCLab] = useState('WBC');
  const [selectedMetabolicLab, setSelectedMetabolicLab] = useState('Creatinine');

  // Helper function to format values - replace NA with "Not measured"
  const formatValue = (value: any): string => {
    if (!value || value === 'NA' || value === 'N/A' || value === 'null' || value === 'undefined') {
      return 'Not measured';
    }
    return String(value);
  };

  // Helper function to check if a value is measured
  const isMeasured = (value: any): boolean => {
    return value && value !== 'NA' && value !== 'N/A' && value !== 'null' && value !== 'undefined';
  };

  // Get lab data from patient context
  const labData = currentPatient?.lab_info || null;

  // Show message if no patient data
  if (!currentPatient) {
    return (
      <div className="bg-white border border-t-0 border-gray-200 rounded-b-lg shadow-sm p-6">
        <div className="text-center text-gray-500 py-8">
          No patient data available
        </div>
      </div>
    );
  }

  // Show message if no lab data
  if (!labData) {
    return (
      <div className="bg-white border border-t-0 border-gray-200 rounded-b-lg shadow-sm p-6">
        <div className="text-center text-gray-500 py-8">
          No lab data available for this patient
        </div>
      </div>
    );
  }

  // Extract data from lab_info
  const tumorMarkers = labData.tumor_markers || {};
  const cbc = labData.complete_blood_count || {};
  const metabolicPanel = labData.metabolic_panel || {};
  const clinicalInterpretation = labData.clinical_interpretation || [];
  const lastUpdated = labData.summary?.last_updated || null;

  // Helper to get biomarker data
  const getBiomarker = (panel: any, name: string) => {
    return panel[name] || { current: {}, trend: [], has_data: false };
  };

  // Helper to get status color and styling
  const getStatusStyle = (status: string) => {
    if (!status) return { bg: 'bg-white', border: 'border-gray-200', text: 'text-gray-900', badge: 'bg-gray-100 text-gray-700' };
    const statusLower = status.toLowerCase();
    if (statusLower === 'normal') {
      return { bg: 'bg-gradient-to-br from-green-50 to-emerald-50', border: 'border-green-300', text: 'text-green-950', badge: 'bg-green-600 text-white' };
    } else if (statusLower === 'low') {
      return { bg: 'bg-gradient-to-br from-amber-50 to-yellow-50', border: 'border-amber-300', text: 'text-amber-950', badge: 'bg-amber-500 text-white' };
    } else if (statusLower === 'high' || statusLower === 'elevated') {
      return { bg: 'bg-gradient-to-br from-red-50 to-rose-50', border: 'border-red-300', text: 'text-red-950', badge: 'bg-red-500 text-white' };
    }
    return { bg: 'bg-white', border: 'border-gray-200', text: 'text-gray-900', badge: 'bg-gray-100 text-gray-700' };
  };

  // Helper to get trend icon
  const getTrendIcon = (trendDirection: string) => {
    if (trendDirection === 'increasing') return <TrendingUp className="w-4 h-4" />;
    if (trendDirection === 'decreasing') return <TrendingDown className="w-4 h-4" />;
    return <Minus className="w-4 h-4 text-gray-400" />;
  };

  // Render biomarker card
  const renderBiomarkerCard = (panel: any, name: string, displayName?: string) => {
    const biomarker = getBiomarker(panel, name);
    const current = biomarker.current || {};
    const style = getStatusStyle(current.status);
    const trendIcon = getTrendIcon(biomarker.trend_direction);

    return (
      <button
        onClick={() => {
          if (panel === tumorMarkers) setSelectedLab(name);
          else if (panel === cbc) setSelectedCBCLab(name);
          else if (panel === metabolicPanel) setSelectedMetabolicLab(name);
        }}
        className={`${style.bg} border-2 rounded-lg p-5 text-left transition-all hover:shadow-md cursor-pointer ${
          (panel === tumorMarkers && selectedLab === name) ||
          (panel === cbc && selectedCBCLab === name) ||
          (panel === metabolicPanel && selectedMetabolicLab === name)
            ? 'border-blue-500 ring-2 ring-blue-200'
            : style.border
        }`}
      >
        <div className="flex items-center justify-between mb-2">
          <p className={`text-xs ${style.text}`}>{displayName || name}</p>
          {trendIcon}
        </div>
        <p className={`text-2xl ${style.text} mb-1`}>
          {biomarker.has_data && isMeasured(current.value) ? formatValue(current.value) : 'Not measured'}
        </p>
        <p className={`text-xs ${style.text} mb-3`}>
          {biomarker.has_data && isMeasured(current.unit) ? current.unit : ''}
        </p>
        <span className={`px-2.5 py-1 rounded-lg text-xs ${style.badge}`}>
          {current.status || 'N/A'}
        </span>
      </button>
    );
  };

  return (
    <div className="bg-white border border-t-0 border-gray-200 rounded-b-lg shadow-sm p-6">
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-5">
          <TestTube className="w-5 h-5 text-blue-600" />
          <h3 className="text-gray-900">Tumor Markers</h3>
          {lastUpdated && <span className="text-xs text-gray-500">Latest: {lastUpdated}</span>}
        </div>

        <div className="grid grid-cols-4 gap-4">
          {renderBiomarkerCard(tumorMarkers, 'CEA')}
          {renderBiomarkerCard(tumorMarkers, 'NSE')}
          {renderBiomarkerCard(tumorMarkers, 'proGRP')}
          {renderBiomarkerCard(tumorMarkers, 'CYFRA_21_1', 'CYFRA 21-1')}
        </div>
      </div>

      <div className="mb-8 pb-8 border-b border-gray-200">
        <h3 className="text-gray-900 mb-4">{selectedLab} Trend (12 months)</h3>
        <div className="bg-gradient-to-br from-slate-50 to-gray-50 rounded-lg p-5 border border-slate-200">
          <LabTrendChart labName={selectedLab} />
        </div>
      </div>

      <div className="mb-8">
        <h3 className="text-gray-900 mb-4">Complete Blood Count</h3>
        <div className="grid grid-cols-4 gap-4">
          {renderBiomarkerCard(cbc, 'WBC')}
          {renderBiomarkerCard(cbc, 'Hemoglobin')}
          {renderBiomarkerCard(cbc, 'Platelets')}
          {renderBiomarkerCard(cbc, 'ANC')}
        </div>
      </div>

      <div className="mb-8 pb-8 border-b border-gray-200">
        <h3 className="text-gray-900 mb-4">{selectedCBCLab} Trend (12 months)</h3>
        <div className="bg-gradient-to-br from-slate-50 to-gray-50 rounded-lg p-5 border border-slate-200">
          <LabTrendChart labName={selectedCBCLab} />
        </div>
      </div>

      <div className="mb-8">
        <h3 className="text-gray-900 mb-4">Metabolic Panel</h3>
        <div className="grid grid-cols-4 gap-4">
          {renderBiomarkerCard(metabolicPanel, 'Creatinine')}
          {renderBiomarkerCard(metabolicPanel, 'ALT')}
          {renderBiomarkerCard(metabolicPanel, 'AST')}
          {renderBiomarkerCard(metabolicPanel, 'Total Bilirubin', 'Total Bilirubin')}
        </div>
      </div>

      <div className="mb-8 pb-8 border-b border-gray-200">
        <h3 className="text-gray-900 mb-4">{selectedMetabolicLab} Trend (12 months)</h3>
        <div className="bg-gradient-to-br from-slate-50 to-gray-50 rounded-lg p-5 border border-slate-200">
          <LabTrendChart labName={selectedMetabolicLab} />
        </div>
      </div>

      {clinicalInterpretation && clinicalInterpretation.length > 0 && (
        <div className="bg-gradient-to-br from-amber-50 to-orange-50 border-2 border-amber-300 rounded-lg p-5">
          <h4 className="text-amber-950 mb-3">Clinical Interpretation</h4>
          <div className="space-y-2">
            {clinicalInterpretation.map((interpretation: string, idx: number) => (
              <div key={idx} className="flex items-start gap-2">
                <div className="w-1.5 h-1.5 bg-amber-600 rounded-full mt-1.5"></div>
                <p className="text-sm text-amber-900">{interpretation}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}