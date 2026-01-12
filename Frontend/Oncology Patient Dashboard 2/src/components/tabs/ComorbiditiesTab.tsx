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

  // Helper function to determine border color based on severity
  const getBorderColor = (severity: 'mild' | 'moderate' | 'severe') => {
    if (severity === 'severe') {
      return 'border-red-300 border-l-4';
    }
    if (severity === 'moderate') {
      return 'border-yellow-300 border-l-4';
    }
    return 'border-green-300 border-l-4';
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

            return (
              <div key={idx} className={`flex items-start gap-4 p-4 bg-gray-50 border rounded-lg ${getBorderColor(severity)}`}>
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h4 className="text-gray-900 font-medium">{item.condition_name}</h4>
                    <span className={`px-2 py-1 rounded text-xs ${
                      severity === 'mild'
                        ? 'bg-green-100 text-green-800'
                        : severity === 'moderate'
                        ? 'bg-yellow-100 text-yellow-800'
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {severity}
                    </span>
                  </div>

                  {item.clinical_details && (
                    <p className="text-sm text-gray-600 mb-3">{item.clinical_details}</p>
                  )}

                  <div className="mt-3 bg-white border border-gray-300 rounded-lg p-3">
                    <p className="text-xs font-medium text-gray-500 mb-2">Current Medications</p>
                    {hasValidMedications ? (
                      <div className="flex flex-wrap gap-2">
                        {item.associated_medications.map((med: string, medIdx: number) => (
                          <span
                            key={medIdx}
                            className="px-2 py-1 bg-blue-50 text-blue-700 border border-blue-200 rounded text-xs"
                          >
                            {med}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-gray-500 italic">
                        No medication currently prescribed for this comorbidity
                      </p>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {ecogStatus && (
        <div className="mt-6 pt-6 border-t border-gray-200">
          <h4 className="text-sm text-gray-700 mb-3">ECOG Performance Status</h4>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-blue-900 mb-1">ECOG {ecogStatus.score}</p>
            <p className="text-sm text-blue-800">
              {ecogStatus.description}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}