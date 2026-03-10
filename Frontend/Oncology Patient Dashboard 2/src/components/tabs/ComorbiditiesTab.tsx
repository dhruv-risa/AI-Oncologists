import { Heart } from 'lucide-react';
import { PatientData } from '../../services/api';

interface ComorbiditiesTabProps {
  patientData: PatientData | null;
}

export function ComorbiditiesTab({ patientData }: ComorbiditiesTabProps) {
  if (!patientData) {
    return (
      <div className="bg-white rounded-b-xl rounded-tr-xl border border-t-0 border-gray-200 p-6">
        <p className="text-gray-500 text-center">No patient data available</p>
      </div>
    );
  }

  const comorbiditiesList = patientData.comorbidities?.comorbidities || [];
  const ecogStatus = patientData.comorbidities?.ecog_performance_status;

  // Filter out the primary cancer diagnosis from comorbidities
  const filteredComorbidities = comorbiditiesList.filter(
    item => item.condition_name &&
            !item.condition_name.toLowerCase().includes('nsclc') &&
            !item.condition_name.toLowerCase().includes('adenocarcinoma')
  );

  // Helper function to determine severity from clinical details or severity field
  const determineSeverity = (item: any): 'mild' | 'moderate' | 'severe' => {
    const severity = item.severity?.toLowerCase() || '';
    const details = item.clinical_details?.toLowerCase() || '';

    // Check severity field first
    if (severity.includes('severe') || severity.includes('stage iii') || severity.includes('stage iv')) {
      return 'severe';
    }
    if (severity.includes('moderate') || severity.includes('stage ii')) {
      return 'moderate';
    }
    if (severity.includes('mild') || severity.includes('stage i')) {
      return 'mild';
    }

    // Check clinical details for severity indicators
    if (details.includes('severe') || details.includes('critical') || details.includes('advanced')) {
      return 'severe';
    }
    if (details.includes('moderate')) {
      return 'moderate';
    }

    // Default to mild
    return 'mild';
  };

  // Helper function to get card styling based on severity
  const getCardStyle = (severity: 'mild' | 'moderate' | 'severe') => {
    if (severity === 'severe') {
      return {
        border: 'border-red-400 border-l-4',
        background: 'bg-red-50'
      };
    }
    if (severity === 'moderate') {
      return {
        border: 'border-orange-400 border-l-4',
        background: 'bg-orange-50'
      };
    }
    return {
      border: 'border-green-400 border-l-4',
      background: 'bg-green-50'
    };
  };

  // Helper function to check if severity should be displayed
  const shouldDisplaySeverity = (item: any) => {
    const severity = item.severity?.toLowerCase() || '';
    const details = item.clinical_details?.toLowerCase() || '';

    // Only show severity if explicitly mentioned in severity field or clinical details
    return severity && (
      severity.includes('severe') ||
      severity.includes('moderate') ||
      severity.includes('mild') ||
      severity.includes('stage')
    ) || (
      details.includes('severe') ||
      details.includes('moderate') ||
      details.includes('mild') ||
      details.includes('critical') ||
      details.includes('advanced')
    );
  };

  // Helper function to check if clinical details should be displayed
  const shouldDisplayClinicalDetails = (details: string | undefined) => {
    if (!details) return false;
    const detailsLower = details.toLowerCase().trim();

    // Filter out non-informative text
    const nonInformativeTexts = ['na', 'n/a', 'treated', 'none', 'unknown', '-'];
    return !nonInformativeTexts.includes(detailsLower);
  };

  // Helper function to check if medications exist and are valid
  const hasMedications = (item: any) => {
    return item.associated_medications &&
           Array.isArray(item.associated_medications) &&
           item.associated_medications.length > 0 &&
           !item.associated_medications.some((med: string) =>
             med.toLowerCase() === 'na' ||
             med.toLowerCase() === 'n/a' ||
             med.trim() === ''
           );
  };

  return (
    <div className="bg-white rounded-b-xl rounded-tr-xl border border-t-0 border-gray-200 p-6">
      <div className="flex items-center gap-2 mb-6">
        <Heart className="w-4 h-4 text-gray-400" />
        <h3 className="text-gray-900">Medical Comorbidities</h3>
      </div>

      {filteredComorbidities.length === 0 ? (
        <div className="text-center text-gray-500 py-8">
          No comorbidities recorded
        </div>
      ) : (
        <div className="space-y-3">
          {filteredComorbidities.map((item, idx) => {
            const severity = determineSeverity(item);
            const hasValidMedications = hasMedications(item);
            const showSeverity = shouldDisplaySeverity(item);
            const showClinicalDetails = shouldDisplayClinicalDetails(item.clinical_details);
            const cardStyle = getCardStyle(severity);

            return (
              <div key={idx} className={`flex items-start gap-4 p-4 border rounded-lg ${cardStyle.background} ${cardStyle.border}`}>
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h4 className="text-gray-900 font-medium">{item.condition_name}</h4>
                    {showSeverity && (
                      <span className={`px-2 py-1 rounded text-xs ${
                        severity === 'mild'
                          ? 'bg-green-100 text-green-800'
                          : severity === 'moderate'
                          ? 'bg-orange-100 text-orange-800'
                          : 'bg-red-100 text-red-800'
                      }`}>
                        {severity}
                      </span>
                    )}
                  </div>

                  {showClinicalDetails && (
                    <p className="text-sm text-gray-600 mb-2">{item.clinical_details}</p>
                  )}

                  {hasValidMedications && (
                    <div className="mt-2">
                      <p className="text-xs font-medium text-gray-500 mb-1.5">Current Medications:</p>
                      <div className="flex flex-wrap gap-1.5">
                        {item.associated_medications.map((med: string, medIdx: number) => (
                          <span
                            key={medIdx}
                            className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs"
                          >
                            {med}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {ecogStatus &&
       ecogStatus.score !== 'NA' &&
       ecogStatus.score !== 'N/A' &&
       ecogStatus.score !== 'Not applicable' && (
        <div className="mt-6 pt-6 border-t border-gray-200">
          <h4 className="text-sm text-gray-700 mb-3">ECOG Performance Status</h4>
          <div className="bg-gray-50 border border-gray-300 rounded-lg p-4">
            <p className="text-gray-900 mb-1 font-medium">ECOG {ecogStatus.score}</p>
            <p className="text-sm text-gray-600">
              {ecogStatus.description}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}